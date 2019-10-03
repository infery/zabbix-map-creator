#!/usr/bin/env python3
# coding: utf-8


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
    """Recreate mac_address_table in the database every run"""
    with sqlite3.connect(dbname) as con:
        con.execute("drop table if exists mac_address_table")
        con.execute("create table mac_address_table (id integer primary key autoincrement, ip text, mac text, port text)")
        con.execute("create INDEX mac_idx ON mac_address_table(ip,mac,port)")


def get_devices_ip_list():
    """Get arp table from the database to the dict"""
    with sqlite3.connect(dbname) as con:
        con.row_factory = sqlite3.Row
        result = con.execute("select ip, mac from arp")
        for row in result:
            devices_ips.add(row['ip'])
            devices_macs.add(row['mac'])
            devices[row['ip']] = row['mac']


def remove_abonents_mac_addresses(switch_mac_table):
    """After receiving fdb from switch we should remove user's mac addresses. We will use SET for that"""
    temporary_dict = switch_mac_table.copy()
    for port in temporary_dict.keys():
        # convert to set
        switch_mac_table[port] = set(switch_mac_table[port])
        # use intersection frature of sets
        switch_mac_table[port] = switch_mac_table[port].intersection(devices_macs)
        if len(switch_mac_table[port]) == 0:
            # del port from dict if no macs left on it
            del switch_mac_table[port]
    # return fdb
    return switch_mac_table


def add_mac_address_table_to_database(switch_ip, mac_address_table):
    """Save fdb in the database"""
    with sqlite3.connect(dbname) as con:
        for port in mac_address_table.keys():
            for mac in mac_address_table[port]:
                con.execute("insert into mac_address_table (ip, mac, port) values ('{ip}', '{mac}', '{port}')".format(
                    ip = switch_ip,
                    mac = mac,
                    port = port
                ))
                print(switch_ip + ' added mac ' + mac + ' on port ' + port)


get_devices_ip_list()
inicialize_switch_tables()
to_debug = []

def collect_fdb(ip_addresses):
    global devices, to_debug
    for sw_ip in ip_addresses:
        vendor = mac.get_vendor_by_mac(devices[sw_ip])
        if not vendor:
            print('Please, add mac ' + devices[sw_ip] + ' to vendors.txt')
            continue
        print('Connect to ' + sw_ip + ', vendor ' + vendor)

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
            print('Collected mac from ' + str(len(mac_table.keys())) + ' ports')
            # In the very end of this script we will show switches, from which we couldn't collect fdb
            # to_debug.remove(sw_ip) is necessary for second try
            if sw_ip in to_debug:
                to_debug.remove(sw_ip)
        else:
            print('Cant collect mac-address-table from ' + sw_ip)
            to_debug.append(sw_ip)
            continue
        mac_table = remove_abonents_mac_addresses(mac_table)
        print('After cleaning left ' + str(len(mac_table.keys())) + ' ports')
        add_mac_address_table_to_database(sw_ip, mac_table)
        print('='*20)

# first try
collect_fdb(list(devices.keys()))

# second try
if to_debug:
    print("\n\n=== Second try ===\n\n")
    collect_fdb(to_debug)

# final message if we still have unresponsive switches
to_debug = set(to_debug)
for sw_ip in to_debug:
    print('Cant collect fdb from ' + mac.get_vendor_by_mac(devices[sw_ip]) + ' ' + sw_ip)
