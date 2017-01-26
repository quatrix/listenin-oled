import dateutil.parser
import socket

from subprocess import check_output, CalledProcessError, Popen, PIPE
from collections import namedtuple
from consts import LOOPER, LAST_UPLOAD, BLINK_EVENT

DEVNULL=open('/dev/null', 'w')

WAITING_FOR_SIGNAL = 'INFO:root:waiting for audio signal'
RECORDING = 'INFO:root:recording'
UPLOADING = 'INFO:root:uploading'
UPLOADED = 'INFO:root:sample recorded and uploaded'
BLINK = 'INFO:root:blink'
ERROR = 'RuntimeError:'

LooperState = namedtuple('LooperState', ['ts', 'state'])


def get_last_upload():
    try:
        last_upload = open('/var/lib/listenin-looper/last_upload').read()
        return dateutil.parser.parse(last_upload)
    except Exception:
        return None


def get_looper_state(line):
    line = line.split()

    try:
        ts, msg = dateutil.parser.parse(line[0]), ' '.join(line[3:])
    except Exception:
        return None

    if msg.startswith(WAITING_FOR_SIGNAL):
        return LooperState(ts, 'Waiting for Audio')

    if msg.startswith(RECORDING):
        return LooperState(ts, 'Recording')
    
    if msg.startswith(UPLOADING):
        return LooperState(ts, 'Uploading')

    if msg.startswith(UPLOADED):
        return LooperState(ts, 'Uploaded')

    if msg.startswith(ERROR):
        return LooperState(ts, 'Error:{}'.format(msg.split(ERROR)[-1]))

    if msg.startswith(BLINK):
        return LooperState(ts, 'Blink')


def looper_log_watcher(q):
    cmd = ['journalctl', '-o', 'short-iso', '-u', 'listenin-looper']
    f = Popen(cmd + ['-n', '1000'], stdout=PIPE, stderr=PIPE, bufsize=1)
    f.stdout.readline()

    last_known_state = LooperState(None, None)

    for line in f.stdout:
        current_state = get_looper_state(line)

        if current_state and current_state.state != 'Blink':
            last_known_state = current_state

    if last_known_state.state:
        q.put((LOOPER, last_known_state.state))

    f = Popen(cmd + ['-f', '-n', '0'], stdout=PIPE, stderr=PIPE)
    f.stdout.readline()

    while True:
        current_state = get_looper_state(f.stdout.readline())

        if current_state:
            if current_state.state == 'Blink':
                q.put((BLINK_EVENT, None))
            else:
                q.put((LOOPER, current_state.state))

            if current_state.state == 'Uploaded':
                q.put((LAST_UPLOAD, current_state.ts))
