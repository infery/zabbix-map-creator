#!/usr/bin/env python
# coding: utf-8

import sys
import pexpect
import re
import mac
# import sys

def get_mac_address_table(switch_ip, login, password):
    """Принимает в качестве аргумента адрес свича и доступ"""
    old_snr = False
    t = pexpect.spawn('telnet {}'.format(switch_ip))
    # t.logfile = sys.stdout
    try:
        t.expect(['login:', '[Uu]sername:'])
    except:
        return False
    t.sendline(login)
    t.expect('[Pp]assword:')
    t.sendline(password)
    ret = t.expect(['#', '>'])
    if ret == 1:
        old_snr = True
        t.sendline('enable')
        t.expect('#')
    t.sendline('terminal length 0')
    t.expect('#')
    if old_snr:
        t.sendline('show mac address-table')
    else:
        t.sendline('show mac-address-table')
    t.expect('#', timeout=120)
    mac_table = t.before
    t.sendline('exit')
    mac_dict = {}
    for entry in mac_table.split('\n'):
        # 104 VLAN104 00-1A-A1-7F-6C-4B 28 Dynamic
        match = re.search('\d+\s+(?P<mac_addr>\S+)\s+DYNAMIC (Hardware)?\s+(?P<port>\S+)', entry)
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
