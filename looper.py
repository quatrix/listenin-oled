import socket
import logging
import datetime

from subprocess import check_output, CalledProcessError, Popen, PIPE
from consts import LOOPER, BLINK_EVENT

DEVNULL=open('/dev/null', 'w')

WAITING_FOR_SIGNAL = 'INFO:root:waiting for audio signal'
RECORDING = 'INFO:root:recording'
UPLOADING = 'INFO:root:uploading'
UPLOADED = 'INFO:root:sample recorded and uploaded'
BLINK = 'INFO:root:blink'
ERROR = 'RuntimeError:'


UPLOADED_SUCCESSFULLY = 'Idle until next sample'

def get_last_upload():
    try:
        last_uploaded = int(open('/var/lib/listenin-looper/last_uploaded').read())
        return datetime.datetime.fromtimestamp(last_uploaded)
    except Exception:
        logging.exception('get_last_upload')
        return None


def get_looper_state(line):
    line = line.split()

    try:
        msg = ' '.join(line[3:])
    except Exception:
        return None

    if msg.startswith(WAITING_FOR_SIGNAL):
        return 'Waiting for Audio'

    if msg.startswith(RECORDING):
        return 'Recording'

    if msg.startswith(UPLOADING):
        return 'Uploading'

    if msg.startswith(UPLOADED):
        return UPLOADED_SUCCESSFULLY

    if msg.startswith(ERROR):
        return 'Error:{}'.format(msg.split(ERROR)[-1])

    if msg.startswith(BLINK):
        return 'Blink'


def looper_log_watcher(q):
    cmd = ['journalctl', '-o', 'short-iso', '-u', 'listenin-looper']
    f = Popen(cmd + ['-n', '1000'], stdout=PIPE, stderr=PIPE, bufsize=1)
    f.stdout.readline()

    last_known_state = None

    for line in f.stdout:
        current_state = get_looper_state(line)

        if current_state and current_state != 'Blink':
            last_known_state = current_state

    if last_known_state:
        q.put((LOOPER, last_known_state))

    f = Popen(cmd + ['-f', '-n', '0'], stdout=PIPE, stderr=PIPE)
    f.stdout.readline()

    while True:
        current_state = get_looper_state(f.stdout.readline())

        if current_state:
            if current_state == 'Blink':
                q.put((BLINK_EVENT, None))
            else:
                q.put((LOOPER, current_state))
