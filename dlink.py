#!/usr/bin/env python
# coding: utf-8

import sys
import pexpect
import re
import mac
# import sys

def get_mac_address_table(switch_ip, login, password):
    """Принимает в качестве аргумента адрес свича и доступ"""
    des_small_cli = False
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
    # проверяем приглашение (PS). Это может быть DES-1100 или аналоги
    if re.search('CMD>>', t.before, re.IGNORECASE): des_small_cli = True
    t.sendline('disable clipaging')
    t.expect('#')
    t.sendline('show fdb')
    # если не хватает прав, clipaging не отключится
    # проще отловить All, чем переходить в enable и вводить пароль
    ret = t.expect(['#', 'All'], timeout=120)
    mac_table = t.before
    if ret == 1:
        t.sendline('a')
        t.expect('#', timeout=120)
        mac_table += t.before
    t.sendline('enable clipaging')
    t.expect('#')
    t.sendline('logout')
    mac_dict = {}
    for entry in mac_table.split('\n'):
        if des_small_cli:
            match = re.search('(?P<port>\d+)\s+(?P<mac_addr>\S+)\s+', entry)
        else:
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
