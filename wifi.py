from __future__ import division

import re
import time
from subprocess import check_output, CalledProcessError
from collections import namedtuple
from consts import WIFI

Wifi = namedtuple('Wifi', ['state', 'ssid'])

WIFI_CONNECTING_RE = re.compile(r'connecting \([^\)]+\) (.+)')

class WifiState(object):
    CONNECTING = 'CONNECTING'
    CONNECTED = 'CONNECTED'
    DISCONNECTED = 'DISCONNECTED'
    UNKNOWN = 'UNKNOWN'


def get_wifi_strength():
    '''
    link level is in a 0-70 scale, we want it on a 0-5 scale
    '''

    try:
        link_level = int(open('/proc/net/wireless').readlines()[-1].split()[2][:-1])
        return int(link_level/70*4) + 1
    except Exception:
        return 'unknown'


def get_wifi_status():
    try:
        res = check_output('nmcli d | grep wifi | grep -v unmanaged | head -n 1', shell=True).strip()
        res = ' '.join(res.split()[2:])

        if 'disconnected' in res:
            return Wifi(WifiState.DISCONNECTED, None)

        if 'connected' in res:
            return Wifi(WifiState.CONNECTED, res.split('connected ')[-1])

        if 'connecting' in res:
            return Wifi(WifiState.CONNECTING, WIFI_CONNECTING_RE.match(res).group(1))

    except CalledProcessError:
        pass

    return Wifi(WifiState.UNKNOWN, None)


def wifi_watcher(q):
    while True:
        wifi = get_wifi_status()
        q.put((WIFI, wifi))

        if wifi.state == WifiState.CONNECTED:
            time.sleep(3)
        else:
            time.sleep(1)

