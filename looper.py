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


def syslog_to_ts_and_msg(line):
    line = line.split(socket.gethostname() + ' ', 1)
    return dateutil.parser.parse(line[0]), line[1:]


def get_last_upload():
    try:
        cmd = '/bin/zgrep uploaded /var/log/syslog* | head -n 1'
        res = check_output(cmd, shell=True, stderr=DEVNULL).strip()

        if not res:
            return None

        res = res.split(':', 1)[1]
        ts, _ = syslog_to_ts_and_msg(res)

        return ts
    except Exception:
        return None


def get_looper_state(line):
    line = line.split()

    try:
        ts, msg = syslog_to_ts_and_msg(line)
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
    cmd = ['journalctl', '-o', 'short', '-u', 'listenin-looper']
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
