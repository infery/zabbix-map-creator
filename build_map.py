#!/usr/bin/env python3
# coding: utf-8
'''
Create network map in zabbix or just check transit for one ip
'''


from itertools import groupby
from operator import itemgetter
from sys import stdout
import configparser
import argparse
import sqlite3
import re
from pyzabbix.api import ZabbixAPI
import zabbix

from device_modules import mac


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
        print("Can't understend option use_zabbix, default is True")

# For begining we will try to find all nontransit switches (edge switch)
# Nontransit is that switch, which has MACs only on uplink port
edge_devices = []
devices = {}
debug = True 
edge_with_transits = {} # dict of edge with list of transit switches


def progress(i, msg):
    prgs = ['|', '/', '-', '\\']
    stdout.write("\r" + '[' + prgs[i % 4] + ']' + ' ' + msg)
    stdout.flush()


def get_devices_list_from_db():
    '''Get all info form database'''
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
    '''Returns most popular mac address. It is uplink mac usually'''
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
    '''Set uplink port for switch in the database and in the dict'''
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
    '''show mac address-table address (`all arp table`) and port != uplink
    If we will find any mac on port, other than uplink, this switch is not edge.
    Otherwise switch is edge. Save this info to the database'''
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
    '''Build edge_devices dict for feature use'''
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
            print('Uplink not found on ' + device_ip)


def get_transit_devices(edge_device_mac):
    '''We will find transit devices for edge switch.
    Transit switch has uplink mac-address on uplink port and mac of edge switch on other port'''
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
    '''Get port where we see this mac on swith with this ip'''
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
    '''We will try to sort transit switches. Sorting is a process of creating a chain of switches
    like in a real network. Last switch is edge. For every switch in transit list we calculate
    their own transit list and check length of this list. The lenght will be index of the switch in
    transit list. For example, uplink switch has no transit switches, his index is 0. 
    Edge switch may have 3 transit switches, his index in result list in 3. And so on'''

    tmp_tr_list = [None] * len(transit_devices)
    for dev_ip in transit_devices:
        if 'transit' not in devices[dev_ip].keys():
            # We save transit list in order to don't calculate transit switches twise for the switch
            devices[dev_ip]['transit'] = get_transit_devices(devices[dev_ip]['mac'])
        index = len(devices[dev_ip]['transit'])
        try:
            tmp_tr_list[index] = dev_ip
        except IndexError:
            print('Error occurred. It seems that one of your transit switches erroneously has longer transit path than his parent')
            print("Tarnsit switch with ip {ip} has transit path:\n{ip_transit}\nwith same length as it's parent's transit path:\n{par_transit}\nbut it has to be shorter".format(
                ip=dev_ip,
                ip_transit=str(devices[dev_ip]['transit']),
                par_transit=str(transit_devices)
            ))
            print("\nYou can find transit path for each switch with this command:\n./build_map.py {config} --ip=<IP>\n".format(
                config=args.config
            ))
            print("I can't build map with this. Exiting")
            exit()
    return tmp_tr_list


possible_uplink_mac = calc_uplink_mac()
# check uplink mac in config. If no mac, we will try to calculate it
if 'uplink_mac' in cfg['network']:
    uplink_mac = mac.normalize_mac(cfg['network']['uplink_mac'])
    print('Using configured uplink mac {mac}'.format(mac=uplink_mac))
else:
    uplink_mac = possible_uplink_mac
    print('Configured uplink mac not found, using calculated mac {mac}'.formac(mac=possible_uplink_mac))

uplink_ip = ''


get_devices_list_from_db()
print()
get_set_uplinks()
print()


# If we specified --ip, we will calculate transit devices for this ip and exit
if args.ip:
    print('Work with ' + args.ip)
    ip_transit = get_transit_devices(edge_device_mac=devices[args.ip]['mac'])
    print('Transit: ' + str(ip_transit))
    ip_tansit_sorted = sort_transit_devices(transit_devices=ip_transit)
    print('Sorted transit: ' + str(ip_tansit_sorted))
    exit()

get_edge_devices()
print()

# Creating grapthviz. This wil allow us to check result without zabbix
dot = open(cfg['zabbix']['mapname'] + '.gv', 'w')
dot.write('strict digraph switches {\n')


# Start position on zabbix-map
x = 100
y = 75

added_hosts = [] # list with hostid already added to the map
selements = [] # host will be added to the map
links = [] # link between nodes
cnt = 1 # host id count on map. Incrementing for every host added to the map
max_height = 480 
# 

all_lists = []

for counter, edge in enumerate(edge_devices, 1):
    # get transit devices
    transit_list = get_transit_devices(edge_device_mac=devices[edge]['mac'])
    # sort transit devices
    sorted_transit_list = sort_transit_devices(transit_devices=transit_list)
    # insert uplink switch in the begining and edge at the end of list
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
            sorted_all_lists.append(i)
except:
    print('Problem while sorting')
    sorted_all_lists = all_lists.copy()

# ==============================
for counter, sorted_transit_list in enumerate(sorted_all_lists):
    # Place host in chess order
    if counter % 2:
        y = 120
    else:
        y = 60
    j = 1 # j - is the row number on the map. Edge device in the bottom of map. Uplink on the top

    if use_zabbix: 
        for dev in sorted_transit_list:
            j += 1
            # this host is not yet added to the map
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
                cnt += 1 # selemetid is unique for every host
            y += 120    
        if max_height < y:
            max_height = y + 100
        x += 100 # move to right

        # example: dev1 dev2 dev3 dev4 dev5
        for i in range(1, len(sorted_transit_list)):
            # we should add link between dev2 and dev1 now
            # on the next iteration we will add link between dev3 and dev2
            # on the last iteration we will add link between dev5 and dev4
            eselement1 = sorted_transit_list[i - 1] # i-1 is the first device during first iteration
            eselement2 = sorted_transit_list[i]     # this is the second one during first iteration

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
    print('Check map in ' + cfg['zabbix']['mapname'] + '.gv')
print('Done')
