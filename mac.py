#!/usr/bin/env python
# coding: utf-8

import re
import sys

def normalize_mac(mac):
    """Приводит любой мак к виду 11:22:33:44:55:66"""
    mac = mac.lower()
    mac = re.sub('[^a-f0-9]', '', mac)
    mac = re.sub('([0-9a-f]{2})', r'\1:', mac, 5)
    return mac

def get_vendor_by_mac(mac):
    """Пытаемся найти имя вендора в файле. Если нет, то вернем False"""
    with open('vendors.txt', 'r') as v:
        for vendor in v:
            vendor = vendor.strip()
            if vendor.startswith('#'): continue
            if len(vendor) == 0: continue
            oui, v_name = vendor.split(';')
            if oui == mac[0:8]:
                return v_name.strip()
        else:
            return False

def print_port_and_mac(mac_address_table):
    for port in mac_address_table.keys():
        print 'Interface:', port
        for mac in mac_address_table[port]:
            print '{:>22s}'.format(mac)

if __name__ == '__main__':
    if len(sys.argv) == 2:
        print 'mac:', normalize_mac(sys.argv[1])
        print 'vendor:', get_vendor_by_mac(normalize_mac(sys.argv[1]))
    else:
        print 'Please, run with [mac_addr] argument'
