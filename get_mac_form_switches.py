#!/usr/bin/env python
# coding: utf-8

"""
Этот скрипт берет все ипы из БД-таблитцы ARP,
обходит эти свичи телнетом и собирает маки.
"""

import sys
import sqlite3
import argparse
import configparser

from device_modules import mac, snr, qtech, dlink, cisco, bdcom, mikrotik, cdata


parser = argparse.ArgumentParser(description="Craft macs")
parser.add_argument('config', type=str, help="Config file name")
args = parser.parse_args()

cfg = configparser.ConfigParser()
cfg.read(args.config)

sw_username = cfg['network']['sw_username']
sw_password = cfg['network']['sw_password']
dbname = cfg['network']['database']

devices_ips = set()
devices_macs = set()
devices = {}


def inicialize_switch_tables():
    """Создаем таблицу для записи маков"""
    with sqlite3.connect(dbname) as con:
        con.execute("drop table if exists mac_address_table")
        con.execute("create table mac_address_table (id integer primary key autoincrement, ip text, mac text, port text)")
        con.execute("create INDEX mac_idx ON mac_address_table(ip,mac,port)")


def get_devices_ip_list():
    """Достаем из базы все маки железок, чтобы на этапе сбора информации
    отсеять абонентские маки. Это ускорит поиск в дальнейшем.
    Если передать last_id, то сбор информции начнется с этого адреса"""
    with sqlite3.connect(dbname) as con:
        con.row_factory = sqlite3.Row
        result = con.execute("select ip, mac from arp")
        for row in result:
            devices_ips.add(row['ip'])
            devices_macs.add(row['mac'])
            devices[row['ip']] = row['mac']


def remove_abonents_mac_addresses(switch_mac_table):
    """Принимает словарь списков на вход и удаляем все маки, которых НЕТ в devices_macs"""
    for port in switch_mac_table.keys():
        # конвертируем список маков на порту во множество
        switch_mac_table[port] = set(switch_mac_table[port])
        # удаляем все маки, которых нет в devices_macs, т.е. абонентские маки
        switch_mac_table[port] = switch_mac_table[port].intersection(devices_macs)
        if len(switch_mac_table[port]) == 0:
            # если этом порту нет маков железок, удаляем этот порт
            del switch_mac_table[port]
    # возвращаем словарь портов с маками на них
    return switch_mac_table


def add_mac_address_table_to_database(switch_ip, mac_address_table):
    """Принимаем на вход ип свича и словарь списков с порт(список-маков), заносим в базу"""
    with sqlite3.connect(dbname) as con:
        for port in mac_address_table.keys():
            for mac in mac_address_table[port]:
                con.execute("insert into mac_address_table (ip, mac, port) values ('{ip}', '{mac}', '{port}')".format(
                    ip = switch_ip,
                    mac = mac,
                    port = port
                ))
                print switch_ip, 'added mac', mac, 'on port', port


get_devices_ip_list()
inicialize_switch_tables()
to_debug = [] # лист свичей, с которых по каким то причинам не собрались данные

for sw_ip in devices.keys():
    vendor = mac.get_vendor_by_mac(devices[sw_ip])
    if not vendor:
        print 'Please, add mac', devices[sw_ip], 'to vendor.txt'
        continue
    print 'Connect to', sw_ip, ', vendor', vendor

    if vendor == 'ignore':
        continue
    elif vendor == 'dlink':
        mac_table = dlink.get_mac_address_table(sw_ip, sw_username, sw_password)
    elif vendor == 'cisco':
        mac_table = cisco.get_mac_address_table(sw_ip, sw_username, sw_password)
    elif vendor == 'mikrotik':
        mac_table = mikrotik.get_mac_address_table(sw_ip, sw_username, sw_password)
    elif vendor == 'bdcom':
        mac_table = bdcom.get_mac_address_table(sw_ip, sw_username, sw_password)
    elif vendor == 'snr':
        mac_table = snr.get_mac_address_table(sw_ip, sw_username, sw_password)    
    elif vendor == 'cdata':
        mac_table = cdata.get_mac_address_table(sw_ip, sw_username, sw_password)
    elif vendor == 'qtech':
        mac_table = qtech.get_mac_address_table(sw_ip, sw_username, sw_password)
    if mac_table:
        print 'Collected mac from', str(len(mac_table.keys())), 'ports'
    else:
        'Cant collect mac-address-table from', sw_ip
        to_debug.append(sw_ip)
        continue

    mac_table = remove_abonents_mac_addresses(mac_table)
    print 'After cleaning left', str(len(mac_table.keys())), 'ports'
    add_mac_address_table_to_database(sw_ip, mac_table)
    print '='*20


for sw_ip in to_debug:
    print 'Cant collect fdb from', mac.get_vendor_by_mac(devices[sw_ip]), sw_ip
