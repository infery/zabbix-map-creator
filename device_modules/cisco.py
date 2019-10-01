#!/usr/bin/env python3
# coding: utf-8

import sys
import pexpect
import re
if __name__ == '__main__':
    import mac
else:
    from device_modules import mac


def get_mac_address_table(switch_ip, login, password, stdout=False):
    t = pexpect.spawn('telnet {}'.format(switch_ip), encoding='utf-8')
    if stdout:
        t.logfile = sys.stdout
    nexus = False
    old_cisco = False # like c3500XL
    try:
        ret = t.expect(['[Uu]ser[Nn]ame:', 'login:'], timeout=5)
        if ret == 1:
            nexus = True

        t.sendline(login)
        t.expect('[Pp]ass[Ww]ord:')
        t.sendline(password)
        t.expect('#', timeout=5)
        t.sendline(u'terminal length 0')
        t.expect('#')
        t.sendline(u'show mac address-table dynamic')
        t.expect('#', timeout=600)
        mac_table = t.before
        if re.search('Invalid input detected', mac_table):
            # maybe this is old cisco
            t.sendline(u'show mac-address-table dynamic')
            t.expect('#', timeout=600)
            old_cisco = True
            mac_table = t.before
        t.sendline(u'logout')
        mac_dict = {}
        for entry in mac_table.split('\n'):
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
    except pexpect.TIMEOUT:
        return False
    return mac_dict

if __name__ == '__main__':
    if len(sys.argv) == 4:
        mac.print_port_and_mac(get_mac_address_table(sys.argv[1], sys.argv[2], sys.argv[3], True))
    else:
        print('Please, run with [ip login password] arguments')
