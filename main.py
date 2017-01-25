#!/usr/bin/env python

import os
import sys
import socket
import humanize
import datetime
import textwrap
import luma.oled.device
import luma.core.serial
import logging

from Queue import Queue
from threading import Thread
from luma.core.render import canvas
from PIL import ImageFont, Image
from consts import LOOPER, WIFI, LAST_UPLOAD, BLINK_EVENT
from wifi import Wifi, WifiState, get_wifi_strength, wifi_watcher
from looper import get_last_upload, looper_log_watcher


logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
logging.getLogger('PIL').setLevel(logging.ERROR)


def get_box_id():
    return int(socket.gethostname().split('box-')[-1])




class Screen(object):
    def __init__(self, oled):
        self._state = {
            'id': get_box_id(),
            WIFI: Wifi(WifiState.UNKNOWN, None),
            LOOPER: 'Initializing',
            LAST_UPLOAD: get_last_upload(),
            BLINK_EVENT: None,
        }

        self.device = oled
        self.q = Queue()

    def get_image(self, name):
        image_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'images', '{}.png'.format(name)))
        return Image.open(image_path).convert(self.device.mode)

    def start(self):
        self.start_worker(wifi_watcher)
        self.start_worker(looper_log_watcher)

        while True:
            event, msg = self.q.get()

            if event == BLINK_EVENT:
                self._state[event] = not self._state[event]
            else:
                self._state[event] = msg

            self.render()
    
    def start_worker(self, f):
        worker = Thread(target=f, args=(self.q,))
        worker.setDaemon(True)
        worker.start()

    def get_wifi_state(self):
        wifi = self._state[WIFI]

        if wifi.state == WifiState.UNKNOWN:
            return 'wifi/unknown', 'Unknown'

        if wifi.state == WifiState.DISCONNECTED:
            return 'wifi/disconnected', 'No wifi'

        if wifi.state == WifiState.CONNECTING:
            return 'wifi/connecting', wifi.ssid

        if wifi.state == WifiState.CONNECTED:
            return 'wifi/{}'.format(get_wifi_strength()), wifi.ssid

    def render_header(self, draw):
        wifi_icon, wifi_ssid = self.get_wifi_state()
        cell_icon = self.get_image('3g/3')
        font = self.font(12)

        draw.bitmap((0, 0), cell_icon, fill='white')
        draw.text((33, -1), '{0:02d}'.format(self._state['id']), font=font, fill='white')
        draw.bitmap((49, -1), self.get_image(wifi_icon), fill='white')
        draw.text((67, -1), wifi_ssid, font=font, fill='white')
        draw.line((0, 12, self.width, 12), fill='white')

    def render_body(self, draw):
        looper_state = self._state[LOOPER]

        if looper_state.startswith('Error:'):
            error = looper_state.split('Error:', 1)[-1]
            error = '\n'.join(textwrap.wrap(error, 23)[0:3])
            draw.multiline_text((0, 15), error, font=self.font(12), fill='white')
        else:
            font = self.font(15)
            w, h = draw.textsize(looper_state, font=font)
            draw.text(((self.width - w)/2,(self.height - h)/2), looper_state, font=font, fill='white')

    def render_footer(self, draw):
        last_upload = self._state[LAST_UPLOAD]
        uploaded_icon = self.get_image('uploaded')
        heart_icon = self.get_image('heart')

        if last_upload is None:
            last_upload = 'unknown'
        else:
            last_upload = humanize.naturaltime(datetime.datetime.now() - last_upload)

        draw.line((0, self.height - 12, self.width, self.height - 12), fill='white')
        draw.bitmap((1, self.height - 10), uploaded_icon, fill='white')
        draw.text((12, self.height - 11), ' {}'.format(last_upload), font=self.font(12), fill='white')

        if self._state[BLINK_EVENT]:
            draw.bitmap((self.width - 9, self.height - 9), heart_icon, fill='white')

    @property
    def width(self):
        return self.device.width

    @property
    def height(self):
        return self.device.height

    def font(self, size):
        font_name = 'C&C Red Alert [INET].ttf'
        font_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'fonts', font_name))
        return ImageFont.truetype(font_path, size)

    def render(self):
        with canvas(self.device) as draw:
            if self._state[BLINK_EVENT] is None:
                draw.bitmap((0, 0), self.get_image('splash'), fill='white')
            else:
                self.render_header(draw)
                self.render_body(draw)
                self.render_footer(draw)


def get_device():
    try:
        Device = getattr(luma.oled.device, 'ssd1306')
        serial = luma.core.serial.i2c(port=1, address='0x3C')
        return Device(serial, width=128, height=64, rotate=0)
    except Exception:
        logging.exception('get_device')

def main():
    device = get_device()

    if device is None:
        logging.error('oled screen not found, exiting')
    else:
        Screen(device).start()


if __name__ == '__main__':
    main()
