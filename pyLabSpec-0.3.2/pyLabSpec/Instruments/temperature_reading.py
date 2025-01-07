#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module provides a class for communicating with a thermocouple
reader.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import serial
from serial.tools import list_ports

def get_serial_usb_devices():

   return [i for i in list_ports.grep('USB')]


class PressureReadingError(Exception):

   statuscodes = {0: 'OK', 
                  1: 'pressure below measurement range', 
                  2: 'pressure above measurement range',
                  3: 'transmitter error',
                  4: 'transmitter switched off',
                  5: 'no transmitter',
                  6: 'identification error',
                  7: 'ITR error',
                 }

   def __init__(self, status):
      self.status = status
      self.msg = self.statuscodes[status]
   
   def __str__(self):
      return "Exception occured while reading the pressure:\n%s" % self.statuscodes[self.status]

   def __unicode__(self):
      return u"Exception occured while reading the pressure:\n%s" % self.statuscodes[self.status]

class TemperatureMonitor():

    BAUDRATE = 9600
    BYTESIZE = serial.SEVENBITS
    PARITY = serial.PARITY_ODD
    STOPBITS = serial.STOPBITS_ONE

    __TERM = "\r\n"

    port = None
    socket = None
    isopen = False

    #device = 'VID:PID=1a86:7523'

    def __init__(self, port = None, baudrate = 9600, parity = serial.PARITY_ODD, bytesize = serial.SEVENBITS, stopbits = serial.STOPBITS_ONE, timeout = 3.0):
        """
        Initializes the comminication to the temperature monitor
        """

        if port is None:
            portlist = [i for i in list_ports.grep(self.device)]
        else:
            portlist = [i for i in list_ports.grep(port)]

        if len(portlist) == 0:
           print("No serial usb devices found!")
           return
        else:
           for device in portlist:
              print("Try to connect to %s on port %s" % (device[1], device[0]))
              try:
                 port = device[0]
                 self.socket = serial.Serial(port, baudrate = baudrate, timeout = timeout, parity = parity, bytesize = bytesize, stopbits = stopbits, xonxoff = 1)
                 self.isopen = self.socket.isOpen()
                 self.port = port
                 self.device_name = device[1]
                 self.vidpid = device[2]
                 print("Connected")
                 break
              except Exception as e:
                 print("Failed: %s" % e)
                 pass

    def __del__(self):
        self.close()

    def close(self):
        """
        Close communication
        """
        if self.socket is None:
            return
        if self.socket.isOpen():
            self.socket.close()
        self.isopen == False

    def write(self, cmd):
        """
        Send write command to instrument.
        """
        if not self.isopen:
           print("Device not open!")
           return

        # append line feed if not present
        if cmd[-len(self.__TERM):] != self.__TERM:
           cmd += self.__TERM

        # clear buffer in order to assure that the next commands are processed as expected
        self.socket.flushInput()

        # send command to return the pressure
        x = self.socket.write(cmd)


    def query(self, cmd):
 
        # send command to return the pressure
        self.write(cmd)
        data = self.socket.readline()

        return data.strip()

    def identify(self):
        """
        Returns the identification string of the instrument.
        """
        return self.query('*IDN?')

    def getTemperature(self, unit = 'K'):
        """
        Returns the temperature read by the device.

        :param unit: Temperature unit (C, F, K; default: K)
        """
        if unit == 'C':
            cmd = 'CRDG?'
        elif unit == 'F':
            cmd = 'FRDG?'
        else:
            cmd = 'KRDG?'

        return float(self.query(cmd))

    def getStatus(self):
        """
        Queries the status of the instrument.
        """
        return self.query('RDGST?')

    def reset(self):
        """
        Reset the instrument parameters to start-up values.
        """
        self.write('*RST')


