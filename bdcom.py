#!/usr/bin/env python
# coding: utf-8

import sys
import pexpect
import re
import mac

def get_mac_address_table(switch_ip, login, password):
    t = pexpect.spawn('telnet {}'.format(switch_ip))
    try:
        t.expect('[Uu]ser[Nn]ame:')
    except:
        return False
    t.sendline(login)
    t.expect('[Pp]ass[Ww]ord:')
    t.sendline(password)
    t.expect('#')
    t.sendline('terminal length 0')
    t.expect('#')
    t.sendline('show mac address-table dynamic')
    t.expect('#')
    mac_table = t.before
    t.sendline('exit')
    t.expect('>')
    t.sendline('exit')
    mac_dict = {}
    for entry in mac_table.split('\n'):
        match = re.search('\d+\s+(?P<mac_addr>\S+)\s+DYNAMIC\s+(?P<port>\S+)', entry)
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
