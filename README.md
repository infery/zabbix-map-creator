# Zabbix map creator
The collection of the scripts that helps you build L2 network topology map in Zabbix

```bash
# Load arp table into database
./arp.py example.ini

# Collect fdb (mac address table) from switches
./get_mac_form_switches.py example.ini

# Build topology
./build_map.py example.ini

# Or you can check path to any switch in your network
./build_map.py example.ini --ip 10.0.0.245

# You can check any device in your network
cd device_modules
./dlink.py 10.0.0.1 admin admin
./snr.py 10.0.0.2 admin admin
```


You may have any number of topologies, each described in dedicated ini file.
For example, `./arp.py example.ini`
```ini
[network]
; switch's default gateway mac address
uplink_mac = 8479.735f.7dcd
; switches creditionals
sw_username = admin
sw_password = password
; sqlite database filename
database = db/example.db
; from wich file to load 'show ip arp'
file_with_arp = example_arp.txt
; cisco (sh ip arp) or linux (ip nei show)
arp_file_type = cisco

[zabbix]
; use zabbix.
; yes, true - build map in zabbix
; no, false - dont touch zabbix, generate only dot file with <mapname>
use_zabbix = yes
; zabbix api creditionals
username = Admin
password = zabbix
; zabbix server url
zbx_url = http://zabbix.example.com
; zabbix map to be created
mapname = Example_map
```

Collection of mac address tables from network devices 
Mac address tables are collected usin pexpect with telnet. No snmp, cdp, lldp, etc. Only screen scraping.
