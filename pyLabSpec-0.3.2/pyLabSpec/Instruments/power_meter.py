#!/usr/bin/env python
# -*- coding: utf-8 -*-

import usb.core
import usb.util
import struct

from instrument import Settings

IDVENDOR = 0x403
IDPRODUCT = 0x6001


def match_endpoint_in(e):
    return usb.util.endpoint_direction(
        e.bEndpointAddress) == usb.util.ENDPOINT_IN


def match_endpoint_out(e):
    return usb.util.endpoint_direction(
        e.bEndpointAddress) == usb.util.ENDPOINT_OUT


class PowerMeter():

    def __init__(self, idVendor=IDVENDOR, idProduct=IDPRODUCT):
        self.idVendor = idVendor
        self.idProduct = idProduct
        self.settings = Settings()

        self.connect_device()

    def connect_device(self):

        print("Connect to power meter ...")
        try:
            self.conn = usb.core.find(idVendor=self.idVendor,
                                      idProduct=self.idProduct)

            if self.conn.is_kernel_driver_active(0) is True:
                self.conn.detach_kernel_driver(0)
            self.conn.set_configuration()

            self.cfg = self.conn.get_active_configuration()
            self.intf = self.cfg[(0, 0)]

            self.ep_out = usb.util.find_descriptor(
                self.intf,
                custom_match=match_endpoint_out)

            self.ep_in = usb.util.find_descriptor(
                self.intf,
                custom_match=match_endpoint_in)

            self.connected = True
            print("Connection established!")
        except Exception as e:
            print("Connection failed: %s" % e)
            self.connected = False

    def identify(self):
        pass

    def write(self, msg):
        self.conn.write(self.ep_out, msg)

    def read(self):
        return self.conn.read(self.ep_in, 10)

    def query_value(self):
        self.write('\x3f\x44\x31\x00\x00\x00\x00\x0d')
        ret = self.conn.read(self.ep_in, 10)

        bytevalue = ret.tobytes()[4:6]

        self.parse_status1(ret[6])
        self.parse_status2(ret[7])
        self.parse_status3(ret[8])

        countvalue = struct.unpack('<h', bytevalue)[0]

        #  int(array.array('B', [ret[5],ret[4]]).tobytes().hex(),
        #      16) *2.0 * rangemax / 59576

        reading = countvalue * 2.0 * self.settings.get(
            'range_selected') / 59576.0

        return reading * 10**self.settings.get('cal_factor_tens_digit')

    def parse_status1(self, status):

        if status >> 7 & 1 == 1:
            self.settings.set('auto_range', True)
        else:
            self.settings.set('auto_range', False)

        if status >> 4 & 0b111 == 0b100:
            self.settings.set('cal_heater', 100.0)
        elif status >> 4 & 0b111 == 0b011:
            self.settings.set('cal_heater', 10.0)
        elif status >> 4 & 0b111 == 0b010:
            self.settings.set('cal_heater', 1.0)
        elif status >> 4 & 0b111 == 0b001:
            self.settings.set('cal_heater', 0.1)
        elif status >> 4 & 0b111 == 0b000:
            self.settings.set('cal_heater', None)  # 'Off'

        if status >> 1 & 0b111 == 0b100:
            self.settings.set('rear_cal_switch', 100.0)
        elif status >> 1 & 0b111 == 0b011:
            self.settings.set('rear_cal_switch', 10.0)
        elif status >> 1 & 0b111 == 0b010:
            self.settings.set('rear_cal_switch', 1.0)
        elif status >> 1 & 0b111 == 0b001:
            self.settings.set('rear_cal_switch', 0.1)
        elif status >> 1 & 0b111 == 0b000:
            self.settings.set('rear_cal_switch', None)  # 'Off'

        if status >> 0 & 1 == 1:
            self.settings.set('control', 'Remote')
        else:
            self.settings.set('control', 'Local')

    def parse_status2(self, status):

        self.settings.set('cal_factor_ones_digit', status >> 4 & 0b1111)
        self.settings.set('cal_factor_ones_digit', status >> 0 & 0b1111)

    def parse_status3(self, status):

        if status >> 5 & 0b111 == 0b100:
            self.settings.set('range_selected', 200.0)
        elif status >> 5 & 0b111 == 0b011:
            self.settin5s.set('range_selected', 20.0)
        elif status >> 5 & 0b111 == 0b010:
            self.settings.set('range_selected', 2.0)
        elif status >> 5 & 0b111 == 0b001:
            self.settings.set('range_selected', 0.2)
        elif status >> 5 & 0b111 == 0b000:
            self.settings.set('range_selected', None)  # 'Off'
        elif status >> 5 & 0b111 == 0b111:
            #  Error mutliple ranges selected
            self.settings.set('range_selected', -1)

        if status >> 4 & 1 == 1:
            self.settings.set('cal_factor_sign_digit', '-')
        else:
            self.settings.set('cal_factor_sign_digit', '+')

        self.settings.set('cal_factor_tens_digit', int(status >> 0 & 0b1111))
