#!/usr/bin/env python
# coding: utf-8

import sys
import pexpect
import re
import mac
# import sys

def get_mac_address_table(switch_ip, login, password):
    """Принимает в качестве аргумента адрес свича и доступ"""
    t = pexpect.spawn('telnet {}'.format(switch_ip))
    # t.logfile = sys.stdout
    nexus = False
    old_cisco = False # like c3500XL
    try:
        ret = t.expect(['[Uu]ser[Nn]ame:', 'login:'])
        if ret == 1:
            nexus = True
    except:
        return False
    t.sendline(login)
    t.expect('[Pp]ass[Ww]ord:')
    t.sendline(password)
    # предусмотрим ситуацию, когда наши логин и пароль не подошли
    try:
        t.expect('#')
    except:
        return False
    t.sendline('terminal length 0')
    t.expect('#')
    t.sendline('show mac address-table dynamic')
    t.expect('#')
    mac_table = t.before
    if re.search('Invalid input detected', mac_table):
        # maybe this is old cisco
        t.sendline('show mac-address-table dynamic')
        t.expect('#')
        old_cisco = True
        mac_table = t.before
    t.sendline('logout')
    mac_dict = {}
    for entry in mac_table.split('\n'):
        # 104 VLAN104 00-1A-A1-7F-6C-4B 28 Dynamic
        if nexus:
            match = re.search('\d+\s+(?P<mac_addr>\S+)\s+DYNAMIC\s+\S+\s+\S+\s+\S+\s+(?P<port>\S+)', entry, re.IGNORECASE)
        elif old_cisco:
            match = re.search('(?P<mac_addr>\S+)\s+DYNAMIC\s+\d+\s+(?P<port>\S+)', entry, re.IGNORECASE)
        else:
            match = re.search('\d+\s+(?P<mac_addr>\S+)\s+DYNAMIC ?([,ipxotherasigned]+)?\s+(?P<port>\S+)', entry, re.IGNORECASE)
        if match:
            if match.group('port') == 'CPU':
                continue
            if not match.group('port') in mac_dict:
                mac_dict[match.group('port')] = []
            mac_addr = mac.normalize_mac(match.group('mac_addr'))
            mac_dict[match.group('port')].append(mac_addr)
    return mac_dict

if __name__ == '__main__':
    if len(sys.argv) == 4:
        mac.print_port_and_mac(get_mac_address_table(sys.argv[1], sys.argv[2], sys.argv[3]))
    else:
        print 'Please, run with [ip login password] arguments'
