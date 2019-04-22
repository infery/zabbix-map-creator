#!/usr/bin/env python
# coding: utf-8

import sqlite3
import re
from sys import stdout
import argparse
import configparser
from pyzabbix.api import ZabbixAPI
import zabbix
import mac

parser = argparse.ArgumentParser(description="ARP|Zabbix loader")
parser.add_argument('config', type=str, help="Config file name")
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
        print 'Cant understend option use_zabbix, default is True'


def progress(i, msg):
    prgs = ['|', '/', '-', '\\']
    stdout.write("\r" + '[' + prgs[i % 4] + ']' + ' ' + msg)
    stdout.flush()


def create_tables():
    '''Создаем/Пересоздаем таблицу ARP при каждом запуске. Таблицу zbxhosts создаем, если не было, но
    не пересоздаем и не очищаем, в ней хранятся hostid из zabbix. Это нужно, чтобы
    каждый раз не опрашивать zabbix, т.к. это может занимать много времени'''
    global dbname
    with sqlite3.connect(dbname) as con:
        con.execute("drop table if exists arp")
        con.execute("""create table arp (
                                    id integer primary key autoincrement, 
                                    ip text, mac text, 
                                    edge integer default 0, 
                                    uplink text, zbxhostid integer)""")
        con.execute("create INDEX arp_idx ON arp(ip,mac)")
        con.execute("""CREATE TABLE IF NOT EXISTS zbxhosts (
                                    id integer primary key autoincrement,
                                    ip text,
                                    hostid integer default NULL)""")
        con.execute("create INDEX IF NOT EXISTS zbx_idx ON zbxhosts(ip,hostid)")


def load_arp_to_db(filename):
    '''Парсим файл с arp и добавляем все записи в базу. Если вендор для мак-адреса не найден или ignore,
    то запись в базу не попадает, сообщаем об этом'''
    global dbname

    with sqlite3.connect(dbname) as con:
        # проверяем каждую строку на ip и мак, добавляем их в таблицу arp
        with (open(filename, 'r')) as arp_file:
            for line in arp_file:
                if line.startswith('#'): 
                    continue

                if cfg['network']['arp_file_type'] == 'linux':
                    match = re.search('^(?P<ip>\S+)\s+dev\s+\S+\s+lladdr\s+(?P<mac_addr>\S+)\s+[RS]', line)
                elif cfg['network']['arp_file_type'] == 'cisco':
                    match = re.search('Internet\s+(?P<ip>\S+)\s+[\d\-]+\s+(?P<mac_addr>\S+)\s+ARPA', line)

                if not match: 
                    continue
                mac_addr = mac.normalize_mac(match.group('mac_addr'))
                vendor = mac.get_vendor_by_mac(mac_addr)
                if not vendor:
                    print 'Vendor for mac ', mac_addr, 'ip', match.group('ip'), 'not found. Dont insert to DB'
                    continue
                if vendor == 'ignore':
                    continue
                con.execute("insert into arp (ip, mac) values ('{ip}', '{mac_addr}')".format(
                    ip=match.group('ip'),
                    mac_addr=mac_addr
                ))
                print 'added', mac_addr, 'ip', match.group('ip')


def get_hostids_from_zbx():
    '''Достаем из базы все IP, для которых zbx-hostid еще неизвестен и опрашиваем заббикс для них'''
    global dbname
    global use_zabbix
    if not use_zabbix:
        return
    with sqlite3.connect(dbname) as con:
        con.row_factory = sqlite3.Row
        # выбираем все ипы, для которых не задан hostid
        result = con.execute("SELECT ip FROM arp WHERE ip NOT IN (SELECT ip FROM zbxhosts WHERE hostid is NOT NULL)")
        if result:
            z = ZabbixAPI(url=cfg['zabbix']['zbx_url'], user=cfg['zabbix']['username'], password=cfg['zabbix']['password'])
            for i, row in enumerate(result):
                hostid = zabbix.get_hostid_by_ip(z_api=z, ip=row['ip'])
                if not hostid:
                    print 'Cant find host id for', row['ip']
                    continue
                con.execute("INSERT INTO zbxhosts (ip, hostid) values ('{ip}', '{hostid}')".format(
                    ip = row['ip'],
                    hostid = hostid
                ))
                progress(i, 'Add hostids from zabbix to database')


if __name__ == "__main__":
    create_tables()
    load_arp_to_db(filename=cfg['network']['file_with_arp'])
    get_hostids_from_zbx()
    print '\n!UPLINK MAC-ADDRESS MUST BE IN ARP TABLE!\n'
