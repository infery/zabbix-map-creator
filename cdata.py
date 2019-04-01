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
    try:
        t.expect('>>User name:')
    except:
        return False
    t.sendline(login + '\r\n')
    t.expect('>>User password:')
    t.sendline(password + '\r\n')
    # предусмотрим ситуацию, когда наши логин и пароль не подошли
    try:
        t.expect('>')
    except:
        return False
    t.sendline('enable\r\n')
    t.expect('#')
    t.sendline('config\r\n')
    t.expect('#')
    t.sendline('show mac-address dynamic\r\n')
    ret = t.expect(['#', 'Press'])
    mac_table = t.before
    while ret == 1:
        t.sendline('v\r\n')
        ret = t.expect(['#', 'Press'])
        mac_table += t.before
    t.sendline('end\r\n')
    t.expect('>')
    t.sendline('logout\r\n')
    mac_dict = {}
    for entry in mac_table.split('\n'):
        # 104 VLAN104 00-1A-A1-7F-6C-4B 28 Dynamic
        match = re.search('\s+(?P<mac_addr>\S+)\s+\d+\s+(?P<port>\S+)\s+', entry)
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
