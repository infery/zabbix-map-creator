# Zabbix map creator
Набор скриптов для сбора мак-адресов с коммутаторов и автоматического создания карты сети в zabbix по ним.

```bash
# загрузить данные в базу
./arp.py example.ini

# собрать данные с коммутаторов
./get_mac_form_switches.py example.ini

# построить топологию
./build_map.py example.ini

# проверить модуль dlink, должен выдать список портов и маков на них
./dlink.py 10.0.0.1 admin admin
```

У вас может быть несколько топологий. Для каждой создается своя конфигурация в ini-файле.
Каждый скрипт в качестве аргумента принимает имя файла с конфигурацией.
Например, `./arp.py example.ini`
```ini
[network]
; switch's default gateway mac address
uplink_mac = 001a.a17f.6c41
; switches creditionals
sw_username = admin
sw_password = admin
; sqlite database filename
database = example.db
; from wich file to load 'show ip arp'
file_with_arp = example-cisco-show-ip-arp.txt

[zabbix]
; use zabbix.
; yes, true - build map in zabbix
; no, false - dont touch zabbix, generate only dot file with <mapname>
use_zabbix = yes
; zabbix api creditionals
username = Admin
password = zabbix
; zabbix server url
zbx_url = https://example.com/zabbix
; zabbix map to be created
mapname = Network
```

Сбор мак-адресов реализован на pexpect. Вендор коммутатора определяется по мак-адресу, список заполняется вручную в файле `vendors.txt`. Поддержку своих вендоров легко добавить по аналогии с теми, что уже есть (см. `get_mac_form_switches.py`)
