#!/usr/bin/env python
# coding: utf-8

from pyzabbix.api import ZabbixAPI


def get_hostid_by_ip(z_api, ip):
    result = z_api.do_request('hostinterface.get',
        {
            'filter': {
                'ip': ip
            },
            'output': ['hostid','host']
        })
    if result['result']:
        return result['result'].pop()['hostid']
    else:
        return False


def create_or_update_map(z_api, mapname, selements, links, mwidth=1920, mheight=1280):
    # возвращает ID карты
    result = z_api.do_request('map.get',
    {
        'filter': {
            'name': mapname
        },
        'output': ['sysmapid']
    })
    if result['result']:
       result = z_api.do_request('map.update',
       {
               'sysmapid': result['result'][0]['sysmapid'],
               'width': mwidth,
               'height': mheight,
               'selements': selements,
               'links': links
       })
    else:
       result = z_api.do_request('map.create',
       {
               'name': mapname,
               'width': mwidth,
               'height': mheight,
               'selements': selements,
               'links': links
       })
       if result['result']:
           return  result['result']['sysmapids'][0]
    return False


# hst1 = get_hostid_by_ip('10.0.0.253')
# hst2 = get_hostid_by_ip('10.0.0.252')
# i = 1
# selements = []
# selements.append({
#         'selementid': i,
#         'elements': [{
#             'hostid': hst1,

#         }],
#         'elementtype': 0,
#         'iconid_off': '2',
#         'x': 100,
#         'y': 100
#     })
# i += 1
# selements.append({
#         'selementid': i,
#         'elements': [{
#             'hostid': hst2,
#         }],
#         'elementtype': 0,
#         'iconid_off': '2',
#         'x': 200,
#         'y': 200
#     })

# links = []
# links.append({
#         'selementid1': 1,
#         'selementid2': 2,
#         'color': '00FF00'
#     })
# create_or_update_map('testapi11', selements, links)

# z.user.logout()
