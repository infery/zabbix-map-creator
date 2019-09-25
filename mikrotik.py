#!/usr/bin/env python
# coding: utf-8

import sys
import pexpect
import re
import mac
# import time

def get_mac_address_table(switch_ip, login, password, stdout=False):
    """Принимает в качестве аргумента адрес свича и доступ"""
    t = pexpect.spawn('telnet {}'.format(switch_ip))
    if stdout:
        t.logfile = sys.stdout
    try:
        t.expect_exact('Login: ')
    except:
        return False
    t.sendline(login + '+ct')
    t.expect_exact('Password: ')
    t.sendline(password)
    t.expect('] > ')
    # time.sleep(1)
    t.sendline("/interface bridge host print without-paging terse\r\n")
    t.expect('] >')
    # time.sleep(1)
    mac_table = t.before
    t.sendline('quit')
    mac_dict = {}
    for entry in mac_table.split('\n'):
        match = re.search('^\s+mac-address=(?P<mac_addr>\S+)\s+on-interface=(?P<port>\S+)\s+', entry, re.IGNORECASE)
        if match:
            if not match.group('port') in mac_dict:
                mac_dict[match.group('port')] = []
            mac_addr = mac.normalize_mac(match.group('mac_addr'))
            mac_dict[match.group('port')].append(mac_addr)
    return mac_dict

if __name__ == '__main__':
    if len(sys.argv) == 4:
        mac.print_port_and_mac(get_mac_address_table(sys.argv[1], sys.argv[2], sys.argv[3], True))
    else:
        print 'Please, run with [ip login password] arguments'
