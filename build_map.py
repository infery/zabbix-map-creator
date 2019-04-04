#!/usr/bin/env python
# coding: utf-8

from itertools import groupby
from operator import itemgetter
from sys import stdout
import configparser
import argparse
import sqlite3
import re
import mac
from pyzabbix.api import ZabbixAPI
import zabbix


parser = argparse.ArgumentParser(description="Craft macs")
parser.add_argument('config', type=str, help="Config file name")
parser.add_argument('--ip', type=str, help="Trace ip")
args = parser.parse_args()

cfg = configparser.ConfigParser()
cfg.read(args.config)


dbname = cfg['network']['database']

if 'use_zabbix' in cfg['zabbix']:
    if cfg['zabbix']['use_zabbix'] in ['yes', 'true']:
        use_zabbix = True
    elif cfg['zabbix']['use_zabbix'] in ['no', 'false']:
        use_zabbix = False 
    else:
        use_zabbix = True
        print 'Cant understent option use_zabbix, default is True'


# для начала попытаемся найти все "крайние свичи", которые не являются транзитными
# это те свичи, у которых маки железок или на аплинке или нет в fdb
edge_devices = []
devices = {}
debug = True 
edge_with_transits = {} # словарь edge с отсортированным списком транзитов


def progress(i, msg):
    prgs = ['|', '/', '-', '\\']
    stdout.write("\r" + '[' + prgs[i % 4] + ']' + ' ' + msg)
    stdout.flush()


def get_devices_list_from_db():
    '''ДОстаем всю информацию о железках из базы для последующего быстрого доступа'''
    with sqlite3.connect(dbname) as con:
        con.row_factory = sqlite3.Row
        result = con.execute("""SELECT arp.ip AS ip,
                                    arp.mac AS mac,
                                    arp.edge AS edge,
                                    arp.uplink AS uplink,
                                    zbxhosts.hostid AS zbxhostid
                                FROM
                                    arp
                                    LEFT JOIN zbxhosts
                                            ON zbxhosts.ip = arp.ip
        """)
        for row in result:
            if row['ip'] not in devices: 
                devices[row['ip']] = {}
            devices[row['ip']]['mac'] = row['mac']
            devices[row['ip']]['hostid'] = row['zbxhostid']


def calc_uplink_mac():
    '''Фунция возвращает самый "популярный" мак-адрес в mac_address_table.'''
    macs = []
    with sqlite3.connect(dbname) as con:
        con.row_factory = sqlite3.Row
        for row in con.execute('SELECT mac FROM mac_address_table'):
            macs.append(row['mac'])
    # delete duplicate record
    macs_uniq = set(macs)
    macs_with_counter = [] # [[105, '12:34:56:67:11:22'], [104, '12:34:56:67:11:33']]
    for mac_addr in macs_uniq:
        macs_with_counter.append([
            macs.count(mac_addr),
            mac_addr
        ])
    macs_with_counter.sort(key=itemgetter(0), reverse=True)
    return macs_with_counter.pop(0)[1]


def get_set_uplinks():
    '''Функиция заполняет поле аплинка в словаре свича и проставляет поле uplink в базе.
    Это поле потом понадобится, чтобы найти транзитные свичи и отсортировтаь их'''
    with sqlite3.connect(dbname) as con:
        for i, device in enumerate(devices.keys()):
            uplink = get_port_by_mac(ip=device, mac=uplink_mac)
            if uplink:
                devices[device]['uplink'] = uplink
                con.execute("UPDATE arp SET uplink = '{uplink}' WHERE ip = '{ip}'".format(
                    uplink = uplink,
                    ip = device
                ))
            else:
                devices[device]['uplink'] = False
            progress(i, 'Update info about uplinks in db')


def switch_is_edge(switch_ip, uplink_port):
    '''для всех маков в таблице ARP проверяем на этом свиче, есть ли мак
       на каком-нибудь порту, отличном от аплинка. Если нет, значит железка крайняя.
       На вход принимает IP свича, который нужно проверить является ли он крайним.
       Если свич является edge - заносим эту информацию в базу, она нам пригодится'''
    edge = True
    with sqlite3.connect(dbname) as con:
        cursor = con.cursor()
        for device in devices.keys():
            if switch_ip == device: continue
            sql = """SELECT port FROM mac_address_table WHERE
                        mac_address_table.ip = '{switch_ip}'
                            AND mac_address_table.port != '{uplink_port}'
                            AND mac_address_table.mac IN
                                (SELECT mac FROM arp where ip != '{switch_ip}' AND uplink IS NOT NULL)""".format(
                            uplink_port = uplink_port,
                            switch_ip = switch_ip)
            cursor.execute(sql)
            if len(cursor.fetchall()) > 0: # если на других портах что-то нашлось..
                edge = False
                break
        if edge:
            cursor.execute("UPDATE arp SET edge = 1 WHERE ip = '{ip}'".format(ip = switch_ip))
            con.commit()
    return edge


def get_edge_devices():
    '''Функция заполняет список edge-свичей. Это нужно, чтобы потом
    не опрашивать их, когда будем работать с транзитными девайсами.
    И дополнительно они послужат нам опорой, когда будем строить линии от центра к edge'''
    global uplink_ip
    for i, device_ip in enumerate(devices.keys()):
        progress(i, 'Check edge status of device')
        if devices[device_ip]['mac'] == uplink_mac:
            uplink_ip = device_ip
            continue
        if devices[device_ip]['uplink']:
            if switch_is_edge(device_ip, devices[device_ip]['uplink']):
                edge_devices.append(device_ip)
        else:
            print 'Uplink not found on', device_ip


def get_transit_devices(edge_device_mac):
    '''В этой функции попытаемся найти все транзитные свичи. Это те свичи,
        у которых в базе есть мак edge-свича на одном порту и мак аплинка на другом'''
    transit = []
    with sqlite3.connect(dbname) as con:
        con.row_factory = sqlite3.Row
        query = """
            SELECT
                arp.ip
            FROM
                arp,
                mac_address_table
            WHERE 
                mac_address_table.mac = '{edge_device_mac}'
                    AND mac_address_table.ip = arp.ip
                    AND arp.edge = 0
                    AND mac_address_table.port != arp.uplink
                    AND arp.uplink IS NOT NULL""".format(edge_device_mac=edge_device_mac)
        for row in con.execute(query):
            transit.append(row['ip'])
        return transit


def get_port_by_mac(ip, mac):
    '''Поучаем IP свича, на котором искать мак и отдаем порт,
    на котором нашли этот мак. Так же определяем аплинк по мак-адресу агрегации'''
    with sqlite3.connect(dbname) as con:
        con.row_factory = sqlite3.Row
        cursor = con.cursor()
        cursor.execute("SELECT port FROM mac_address_table WHERE ip='{ip}' AND mac='{mac}' LIMIT 1".format(
            ip=ip,
            mac=mac
        ))
        result = cursor.fetchone()
        if not result:
            return False
        else:
            return result['port']


def sort_transit_devices(transit_devices):
    '''Эта функция пытается отсортировать список свичей так, чтобы в итоге получилась
    линия, такая же как в реальной сети. Для каждого девайса из списка находим кол-во транзитных свичей.
    Это кол-во и будет являтся индексом в готовом массиве. Т.е. для агрегации кол-во транзита = 0, значит он в
    начале списка. И так далее'''
    tmp_tr_list = [None] * len(transit_devices)
    for dev_ip in transit_devices:
        if 'transit' not in devices[dev_ip].keys():
            # это нужно, чтобы вычислять транзит для одной железки только один раз
            # одна железка в транзитах может встречаться несколько раз
            devices[dev_ip]['transit'] = get_transit_devices(devices[dev_ip]['mac'])
        index = len(devices[dev_ip]['transit'])  
        try:
            tmp_tr_list[index] = dev_ip
        except IndexError:
            print 'Cant sort for dev_ip:', dev_ip, ', transit count:', index, 'tmp_tr_list len =', str(len(tmp_tr_list))
            print 'Transit list on enter:', transit_devices, 'and searched mac', devices[dev_ip]['mac']
            print 'Trying to continue calculation'
            continue
    return tmp_tr_list


possible_uplink_mac = calc_uplink_mac()
# эта переменная нужна, чтобы понять, где у свича аплинк
if 'uplink_mac' in cfg['network']:
    uplink_mac = mac.normalize_mac(cfg['network']['uplink_mac'])
    print 'Using configured uplink mac', uplink_mac
else:
    uplink_mac = possible_uplink_mac
    print 'Configured uplink mac not found, using calculated mac', possible_uplink_mac

uplink_ip = ''


get_devices_list_from_db() # заполняем массив служебной информацией из таблицы ARP
print
get_set_uplinks() # заполняем в базе информацию у кого какой аплинк
print


# проверка для отдельного свича, если он передан в аргументе
if args.ip:
    print 'Work with', args.ip
    ip_transit = get_transit_devices(edge_device_mac=devices[args.ip]['mac'])
    print 'Transit:', ip_transit
    ip_tansit_sorted = sort_transit_devices(transit_devices=ip_transit)
    print 'Sorted transit:', ip_tansit_sorted
    exit()

get_edge_devices() # находим edge-девайсы. Потом мы пойдем по списке и будем искать промежуточные свичи
print

# Создаем файл для grapthviz. Можно проверить результат работы без zabbix
dot = open(cfg['zabbix']['mapname'] + '.gv', 'w')
dot.write('strict digraph switches {\n')


# начальные значение координат в карте zabbix
x = 100
y = 75

added_hosts = [] # массив с hostid, которые уже были добавлены на карту, чтобы не добавлять повторно
selements = [] # хранит хосты, которые будут добавлены на карту
links = [] # хранит связи между узлами
cnt = 1 # инкрементируется каждый раз, когда на карту добавляется хост. Сохраняется в виде id_on_map в массиве devices
max_height = 480 # здесь будем хранить ширину карты. Чем больше хостов, тем шире. Это начальное значение

all_lists = []

for counter, edge in enumerate(edge_devices, 1):
    # получаем все транзитные девайсы
    transit_list = get_transit_devices(edge_device_mac=devices[edge]['mac'])
    # теперь нужно их отсортировать так, чтобы они шли в листе в том порядке,
    # в котором подключены в сети
    sorted_transit_list = sort_transit_devices(transit_devices=transit_list)
    # добавляем в начало узел агрегации, а в конец - узел edge
    sorted_transit_list.insert(0, uplink_ip)
    sorted_transit_list.append(edge)
    all_lists.append(sorted_transit_list)


# Попробуем отсортировать листы так, чтобы ветви с одинаковыми транзитными свичами находились рядом
min_transit_count = min(len(tmp) for tmp in all_lists) - 1

all_lists.sort(key=itemgetter(min_transit_count))

sorted_all_lists = []
# y = groupby(all_lists, itemgetter(1))

try:
    for elt, items in groupby(all_lists, itemgetter(min_transit_count)):
        for i in items:
            # print(i)
            sorted_all_lists.append(i)
except:
    print 'Problem while sorting'
    sorted_all_lists = all_lists.copy()

# ==============================
for counter, sorted_transit_list in enumerate(sorted_all_lists):
    # Начальное значение для первго хоста по списку.
    # Нужно, чтобы они не стояли рядом друго с другом, иначе надписи пересекаются
    if counter % 2:
        y = 120
    else:
        y = 60
    j = 1 # j - это "номер" строки, на которую добавляем хост. Чем дальше свич от агрегации, тем ниже он на карте

    # после того, как линию построили, нужно сделать из нее строку 
    # вида ip==ip==ip==ip, чтоб попарно добавить линии
    lnk_str = '=='.join(sorted_transit_list)
    if use_zabbix: 
        for dev in sorted_transit_list:
            j += 1
            # этот хост еще не добавляли на карту
            if devices[dev]['hostid'] not in added_hosts:
                selements.append({
                        'selementid': cnt,
                        'elements': [{
                            'hostid': devices[dev]['hostid']
                        }],
                        'elementtype': 0,
                        'iconid_off': '2',
                        'x': x,
                        'y': y
                })
                y += 120    
                devices[dev]['id_on_map'] = cnt
                added_hosts.append(devices[dev]['hostid'])
                cnt += 1 # selemetid Для каждого хоста будет уникален
            y += 120    
        if max_height < y:
            max_height = y + 100
        x += 100 # сдвигаемся правее

        # находим все пары, они должны быть перекрывающимися, regexp с флагом ?=
        for m in re.findall(r'(?=([1-9][0-9]+\.\d+\.\d+\.\d+)==([1-9][0-9]+\.\d+\.\d+\.\d+))', lnk_str):
            eselement1, eselement2 = m
            tmp = {
                'selementid1': devices[eselement1]['id_on_map'],
                'selementid2': devices[eselement2]['id_on_map'],
                'color': '00FF00'
            }
            if tmp not in links: 
                links.append(tmp)

    gv_list = ['"'+item+'"' for item in sorted_transit_list]  
    graph = ' -> '.join(gv_list)
    dot.write(graph + '\n')

dot.write('}')
dot.close()

if use_zabbix:
    z_api = ZabbixAPI(url=cfg['zabbix']['zbx_url'], user=cfg['zabbix']['username'], password=cfg['zabbix']['password'])
    zabbix.create_or_update_map(z_api=z_api,
        mapname=cfg['zabbix']['mapname'], 
        selements=selements, 
        links=links, 
        mwidth=x+100, 
        mheight=max_height)
else:
    print 'Check map in', cfg['zabbix']['mapname'] + '.gv'
print 'Done'
