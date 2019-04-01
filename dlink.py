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
        t.expect(['[Uu]ser[Nn]ame:','login:'])
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
    t.sendline('disable clipaging')
    t.expect('#')
    t.sendline('show fdb')
    # если не хватает прав, clipaging не отключится
    # проще отловить All, чем переходить в enable и вводить пароль
    ret = t.expect(['#', 'All']) 
    mac_table = t.before
    if ret == 1:
        t.sendline('a')
        t.expect('#')
        mac_table += t.before
    t.sendline('logout')
    mac_dict = {}
    for entry in mac_table.split('\n'):
        # 104 VLAN104 00-1A-A1-7F-6C-4B 28 Dynamic
        match = re.search('\d+\s+\S+\s+(?P<mac_addr>\S+)\s+(?P<port>\S+)\s+', entry)
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
