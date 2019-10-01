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
    des_small_cli = False
    t = pexpect.spawn('telnet {}'.format(switch_ip), encoding='utf-8')
    if stdout:
        t.logfile = sys.stdout
    try:
        t.expect(['[Uu]ser[Nn]ame:', 'login:'])
        t.sendline(login)
        t.expect('[Pp]ass[Ww]ord:')
        t.sendline(password)
        t.expect('#', timeout=5)
        if re.search('CMD>>', t.before, re.IGNORECASE): 
            des_small_cli = True
        t.sendline(u'disable clipaging')
        t.expect('#')
        t.sendline(u'show fdb')

        # if we havn't enought right, we can't disable clipaging
        # we will better simulate tap on <ALL>
        ret = t.expect(['#', 'All'], timeout=120)
        mac_table = t.before
        if ret == 1:
            t.sendline(u'a')
            t.expect('#', timeout=600)
            mac_table += t.before

        t.sendline(u'enable clipaging')
        t.expect('#')
        t.sendline(u'logout')
        mac_dict = {}
        for entry in mac_table.split('\n'):
            if des_small_cli:
                match = re.search('^(?P<port>\d+)\s+(?P<mac_addr>\S+)\s+', entry)
            else:
                match = re.search('\d+\s+\S+\s+(?P<mac_addr>\S+)\s+(?P<port>\S+)\s+', entry)

            if match:
                if match.group('port') == 'CPU':
                    continue
                if match.group('port') not in mac_dict:
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
