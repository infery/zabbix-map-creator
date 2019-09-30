#!/usr/bin/env python3
# coding: utf-8

import sys
import pexpect
import re
import mac


def get_mac_address_table(switch_ip, login, password, stdout=False):
    old_snr = False
    t = pexpect.spawn('telnet {}'.format(switch_ip), encoding='utf-8')
    if stdout:
        t.logfile = sys.stdout
    try:
        t.expect(['login:', '[Uu]sername:'])
        t.sendline(login)
        t.expect('[Pp]assword:')
        t.sendline(password)
        t.expect('#', timeout=5)
        t.sendline(u'terminal length 0')
        t.expect('#')
        t.sendline(u'show mac address-table')
        t.expect('#', timeout=600)
        if 'Ambiguous command' in t.before:
            ret = t.sendline(u'show mac-address-table')
            t.expect('#', timeout=600)

        mac_table = t.before
        t.sendline(u'exit')
        mac_dict = {}
        for entry in mac_table.split('\n'):
            match = re.search('\d+\s+(?P<mac_addr>\S+)\s+DYNAMIC( Hardware)?\s+(?P<port>\S+)', entry, re.IGNORECASE)
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
