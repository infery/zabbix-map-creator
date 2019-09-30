#!/usr/bin/env python3
# coding: utf-8

import sys
import pexpect
import re
import mac


def get_mac_address_table(switch_ip, login, password, stdout=False):
    t = pexpect.spawn('telnet {}'.format(switch_ip), encoding='utf-8')
    if stdout:
        t.logfile = sys.stdout
    try:
        t.expect_exact('Login: ')
        t.sendline(login + u'+ct')
        t.expect_exact('Password: ')
        t.sendline(password)
        t.expect('] > ', timeout=5)
        t.sendline(u"/interface bridge host print without-paging terse\r\n")
        t.expect('] >', timeout=600)
        mac_table = t.before
        t.sendline(u'quit')
        mac_dict = {}
        for entry in mac_table.split('\n'):
            match = re.search('^\s+mac-address=(?P<mac_addr>\S+)\s+on-interface=(?P<port>\S+)\s+', entry, re.IGNORECASE)
            if match:
                if not match.group('port') in mac_dict:
                    mac_dict[match.group('port')] = []
                mac_addr = mac.normalize_mac(match.group('mac_addr'))
                mac_dict[match.group('port')].append(mac_addr)
    except pexpect.TIMEOUT:
        return False
    return mac_dict

if __name__ == '__main__':
    if len(sys.argv) == 4:
        mac.print_port_and_mac(get_mac_address_table(sys.argv[1], sys.argv[2], sys.argv[3], True))
    else:
        print('Please, run with [ip login password] arguments')
