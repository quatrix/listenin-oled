from consts import MODEM
from subprocess import check_output, CalledProcessError
import time


class ModemState(object):
    CONNECTING = 'CONNECTING'
    CONNECTED = 'CONNECTED'
    DISCONNECTED = 'DISCONNECTED'
    UNKNOWN = 'UNKNOWN'


def get_state():
    try:
        res = check_output('nmcli d | grep gsm | head -n 1', shell=True).strip()
        res = ' '.join(res.split()[2:])

        if 'disconnected' in res or 'unavailable' in res:
            return ModemState.DISCONNECTED

        if 'connected' in res:
            return ModemState.CONNECTED

        if 'connecting' in res:
            return ModemState.CONNECTING

    except CalledProcessError:
        pass

    return ModemState.UNKNOWN


def get_modem_id():
    res = check_output('mmcli -L | grep /org/freedesktop/ | head -n 1', shell=True).strip()

    if not res:
        return

    modem_path = res.split()[0]
    return modem_path.split('/')[-1]

def get_modem_strength():
    modem_id = get_modem_id()

    if modem_id is None:
        return

    res = check_output('mmcli -m {} | grep \'signal quality\''.format(modem_id), shell=True).strip()

    quality = res.split('signal quality: \'')[1]
    return int(quality.split('\'')[0])

def modem_watcher(q):
    while True:
        state = get_state()
        q.put((MODEM, state))

        if state == ModemState.CONNECTED:
            time.sleep(3)
        else:
            time.sleep(1)
