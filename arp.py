#!/usr/bin/env python
# coding: utf-8

"""
Этот скрипт загружает ARP-таблицу с агрегации в базу,
"""
import argparse
import configparser
import sqlite3
import re
import mac
from sys import stdout
from pyzabbix import ZabbixAPI
import zabbix

parser = argparse.ArgumentParser(description="ARP|Zabbix loader")
parser.add_argument('config', type=str, help="Config file name")
args = parser.parse_args()

cfg = configparser.ConfigParser()
cfg.read(args.config)

dbname = cfg['network']['database']

def progress(i, msg):
    prgs = ['|', '/', '-', '\\']
    stdout.write("\r" + '[' + prgs[i % 4] + ']' + ' ' + msg)
    stdout.flush()


def create_tables():
    global dbname
    """Создаем таблицу в базе."""
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


def load_arp_to_db(filename, empty_before_insert=True):
    global dbname
    """Загружаем данные из файла с арп-таблицей в базу данных"""
    with sqlite3.connect(dbname) as con:
        if empty_before_insert:
            con.execute('delete from arp')
        # проверяем каждую строку на ip и мак, добавляем их в таблицу arp
        with (open(filename, 'r')) as arp_file:
            for line in arp_file:
                if line.startswith('#'): 
                    continue
                match = re.search('Internet\s+(?P<ip>\S+)\s+[\d\-]+\s+(?P<mac_addr>\S+)\s+ARPA', line)
                if not match: 
                    continue
                mac_addr = mac.normalize_mac(match.group('mac_addr'))
                vendor = mac.get_vendor_by_mac(mac_addr)
                if not vendor:
                    print 'Vendor for mac ', mac_addr, 'not found. Dont insert to DB'
                    continue
                if vendor == 'ignore':
                    continue
                con.execute("insert into arp (ip, mac) values ('{ip}', '{mac_addr}')".format(
                    ip=match.group('ip'),
                    mac_addr=mac_addr
                ))
                print 'added', mac_addr, 'ip', match.group('ip')


def get_hostids_from_zbx():
    global dbname
    with sqlite3.connect(dbname) as con:
        con.row_factory = sqlite3.Row
        # выбираем все ипы, для которых не задан hostid
        result = con.execute("SELECT ip FROM arp WHERE ip NOT IN (SELECT ip FROM zbxhosts WHERE hostid is NOT NULL)")
        if result:
            z = ZabbixAPI(url=cfg['zabbix']['zbx_url'], user=cfg['zabbix']['username'], password=cfg['zabbix']['password'])
            for i, row in enumerate(result):
                hostid = zabbix.get_hostid_by_ip(ip=row['ip'], z_api=z)
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
