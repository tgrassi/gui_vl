#!/usr/bin/env python
# -*- coding: utf8 -*-
#
"""
This module provides a class for communicating with a variety of pressure
readouts.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
import time
import binascii
# third-party
import serial
from serial.tools import list_ports
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from . import instrument as instr

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

class PressureGaugeError(Exception):
    statuscodes = {'0000': 'No error',
                   '1000': 'Controller error (see display)',
                   '0100': 'No hardware',
                   '0010': 'Inadmissible parameter',
                   '0001': 'Syntax error',
                  }

    def __init__(self, status):
        self.status = status
        self.msg = self.statuscodes[status]

    def __str__(self):
        return "Gauge error:\n%s" % self.msg

    def __unicode__(self):
        return u"Gauge error:\n%s" % self.msg


class Gauge():
    """
    General class to connect and control pressure gauges.
    """
    identifier = 'Unknown'
    def __init__(self, com, **kwds):
        """
        """
        self.open(com, **kwds)

    def open(self, com, **kwds):
        try:
            self.socket = instr.InstSocket(com, **kwds )
            self.connected = True
        except:
            raise RuntimeError("Could not connect to pressure gauge!")
        # clear the buffer
        self.clear()
        # identify gauge and set identifier
        try:
            self.identifier = self.identify()
        except:
            pass
        #print("Connected:", self.identifier)

    def close(self):
        """
        Closes and removes the socket.
        """
        # clear the buffer
        self.socket.clear()
        # close socket
        self.socket.close()

class OerlikonGauge():

   port = None
   socket = None
   isopen = False

   device = 'VID:PID=1a86:7523'
   transmitter1 = None
   transmitter2 = None

   def __init__(self, port = None, baudrate = 9600, timeout = 3.0):

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
               self.socket = serial.Serial(port, baudrate = baudrate, timeout = timeout)
               self.isopen = self.socket.isOpen()
              #self.identify_transmitters()
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

      if self.socket is None:
          return
      if self.socket.isOpen():
          self.socket.close()
      self.isopen == False

   def query(self, cmd):
 
      if not self.isopen:
         print("Device not open!")
         return

      # append line feed if not present
      if cmd[-1] != '\n':
         cmd += '\n'

      # clear buffer in order to assure that the next commands are processed as expected
      self.socket.flushInput()

      # send command to return the pressure
      x = self.socket.write(cmd)
      data = self.socket.readline()

      # center two returns acknoledgement first
      if not data == '\x06\r\n':
         print("Could not process command '%s'" % cmd)
         return

      # send enquiry to start data transfer
      x = self.socket.write('\x05\n')
      data = self.socket.readline()
      
      return data.strip()
        

   def read_pressure(self, gauge = 1):

      data = self.query('PR%d' % gauge)
      status, pressure = data.split(',')
      
      status = int(status)
      
      if status > 2:
         raise PressureReadingError(status)
      try:
         pressure = float(pressure)
      except:
         pass
      
      return pressure

   def identify_transmitters(self):
      
      data = self.query('TID')
      tr = data.split(',')
      self.transmitter1 = tr[0]
      self.transmitter2 = tr[1]


class PfeifferDualGauge(Gauge):
    """
    Provides a general socket for the Pfeiffer SingleGauge/DualGauge (i.e.
    TPG 36x) via the serial port. All the commands are based on the mnemonic
    communication protocol.
    
    Note that the communication protocol demands the use of a COMMAND ->
    INCOMING ACKNOWLEDGMENT -> OUTGOING ACKNOWLEDGMENT -> FINAL    RESPONSE.
    This necessitates the use of the self.query() scheme, whereby all
    communication with the device---whether it be a setting or the
    receiving of a parameter---involves multiple transmissions.
    """
    
    __TERM = "\r"
    
    known_gases = [
        "air",
        "argon",
        "hydrogen",
        "helium",
        "neon",
        "krypton",
        "xenon",
        "other"]
 
    units = {0: 'mbar/bar',
             1: 'Torr',
             2: 'Pascal',
             3: 'Micron',
             4: 'hPascal',
             5: 'Volt',
            }

   
    def __init__(self, com, **kwds):
        """
        Initializes the communication to the pressure readout/controller.
        
        :param port: the serial port to use (e.g. '/dev/ttyS2')
        :param baudrate: (optional) the baudrate of the communication
        :param parity: (optional) the type of parity checking to use
        :param bytesize: (optional) the number of data bits in each signal
        :param stopbits: (optional) the number of stop bits for each signal
        :param timeout: (optional) the timeout to wait before exiting the input buffer
        :param xonxoff: (optional) whether to use software flow control
        :param rtscts: (optional) whether to use hardware (RTS/CTS) flow control
        :type port: str
        :type baudrate: int
        :type parity: int
        :type bytesize: int
        :type stopbits: int
        :type timeout: float
        :type xonxoff: bool
        :type rtscts: bool
        """
        Gauge.__init__(self, com, **kwds)
        #self.write('AYT')
    
    def to_hex(self, s):
        """
        Helper function that converts a string to hexadecimal form.
        
        :param s: an arbitrary string
        :type s: str
        :returns: a string in hex form
        :rtype: str
        """
        if sys.version_info[0] == 3:
            s = s.encode('utf-8')
            return binascii.hexlify(s)
        else:
            return s.encode("hex")
    def from_hex(self, s):
        """
        Helper function that converts a hexadecimal string to ASCII.
        
        :param s: a string in hex form
        :type s: str
        :returns: the ASCII string
        :rtype: str
        """
        if sys.version_info[0] == 3:
            s = s.decode('utf-8')
            return binascii.unhexlify(s)
        else:
            return s.decode("hex")
    
    def clear(self):
        """
        Reset the serial interface buffer.
        """
        self.socket.clear()
    
    def write(self, cmd):
        """
        Writes a command to the instrument.
        
        :param cmd: an arbitrary command to send to the instrument
        :type cmd: str
        """
        if not self.socket.isOpen():
            return
        # append line feed if not present
        if cmd[-len(self.__TERM):] != self.__TERM:
            cmd += self.__TERM
        # clear buffer in order to assure that the next commands are processed as expected
        self.clear()
        # send command to return the pressure
        x = self.socket.write(cmd)
    def get_ack(self):
        """
        Processes the acknowledgment, which is very specific to    the
        Pfeiffer communication protocol.
        
        :returns: the acknowledgment response
        :rtype: bool
        """
        ack = self.socket.readline().strip()
        if ack=="\x06":
            self.write("\x05")
            return True
        elif ack=="\x15":
            return "ERR: received NAK"
        else:
            return False
    def query(self, cmd, size=0):
        """
        Sends a query to the instrument.
        
        :param cmd: the command string
        :param size: (optional) the expected size of the response in units [bytes]
        :type cmd: str
        :type size: int
        :returns: the answer to the query
        :rtype: str
        """
        # send command to pressure readout
        self.write(cmd)
        # see what the acknowledgment is
        ack = self.get_ack()
        if ack=="ERR: received NAK": # probably a syntax error
            return ack
        elif not ack:
            raise RuntimeError
        # all must be well, so get the response
        if not size:
            data = self.socket.readline().strip()
        elif isinstance(size, int):
            data = self.socket.read(size=size).strip()
        else:
            raise SyntaxError("You requested a strange integer size: %s" % size)
        # process the response, based on a couple possibilities
        if data == "\x15": # this means there was a problem
            return "ERR: received NAK"
        if self.to_hex(data)[-4:]=="0d15": # this is the typical ending
            data = self.from_hex(self.to_hex(data)[:-4])
        # finally return the response
        return data
    
    def identify(self):
        """
        Returns the identification string of the connected gauge(s).
        
        :returns: the identification string(s)
        :rtype: str
        """
        self.identifier = self.query('TID')
        return self.identifier

    def poke(self):
        """
        Invokes a thorough probe of the instrument.
        
        :returns: many strings describing the unit/gauge(s)
        :rtype: str
        """
        return self.query('AYT')
    
    def get_hardware_version(self):
        """
        Returns the hardware version.
        
        :returns: a string of the hardware version
        :rtype: str
        """
        return self.query('HDW')
    def get_firmware_version(self):
        """
        Returns the firmware version.
        
        :returns: a string of the firmware version
        :rtype: str
        """
        return self.query('PNR')
    
    def get_uptime(self):
        """
        Returns the uptime of the device (unit: hours).
        
        :returns: the operating hours
        :rtype: float
        """
        return float(self.query('RHR'))
    
    def get_error_status(self):
        """
        Returns the error status of the readout.
        
        :returns: the error string
        :rtype: str
        """
        return self.query('ERR')

    def reset(self):
        """
        Clears all errors on the readout, returns it to measurement mode,
        and returns the list of all present error messages (if any).
        
        :returns: list of all present error messages
        """
        return self.query('RES')
    
    def get_pressure(self, channel=0):
        """
        Returns the current measurement data from the gauge(s).
        
        :param channel: (optional) the channel of the connected gauge(s)
        :type channel: int
        :returns: the current pressure and status of the gauge(s)
        :rtype: tuple(str, float)
        """
        # sanity check for the channel input
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in list(range(0,3)):
            raise SyntaxError("The requested channel is not 1 or 2 (or 0 for both): %s" % channel)
        # define a lookup table for the possible statuses of the pressure
        status = {
            '0':"OK",
            '1':"Underrange",
            '2':"Overrange",
            '3':"Sensor error",
            '4':"Sensor off",
            '5':"No sensor",
            '6':"ID error"}
        # perform query
        if not channel:
            response = self.query('PRX').split(',')
        else:
            response = self.query('PR%s' % int(channel)).split(',')
        # process the response, based on three scenarios
        if len(response)==1:
            response = None
        elif len(response)>2:
            response[0] = status[response[0]]
            response[1] = float(response[1])
            response[2] = status[response[2]]
            response[3] = float(response[3])
        else:
            response[0] = status[response[0]]
            response[1] = float(response[1])
        return response
    
    def set_gauge_state(self, channel, state = 'ON'):
        """
        Turns the gauge on/off.
        
        Note that not all types of pressure gauges can be 'shut off'.
        
        :param channel: the channel of the gauge
        :param state: the desired state of the gauge
        :type channel: int
        :type state: str
        """
        states = self.get_gauge_state() # no status change
        change_state = False # indicator if state change is required

        # sanity check for the channel input
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in [1,2]:
            raise SyntaxError("The requested channel is not 1 or 2: %s" % channel)
        if not state.upper() in ["ON", "OFF"]: # for the desired state
            raise SyntaxError("The requested state must be ON or OFF: %s" % state)

        cmd = 'SEN,'
        if state.upper()=="OFF" and states[channel -1] == 2:
            states[channel - 1] = 1
            change_state = True
        elif state.upper()=="ON" and states[channel - 1] == 1:
            states[channel - 1] = 2
            change_state = True

        if change_state:
            self.write('SEN,%d,%d' % (states[0], states[1]))
            # Wait 2 seconds until operation has finished
            time.sleep(2)

        # check for error
        err_status = self.get_error_status()
        if err_status != '0000':
            raise PressureGaugeError(err_status)

        return self.get_gauge_state()
       
    def get_gauge_state(self):
        """
        Reads the state of both channels of the gauge.
          states:
              0 -> Gauge cannot be turned on/off
              1 -> Gauge turned off
              2 -> Gauge turned on

        returns states
        """
        states = self.query('SEN')
        states = [int(i) for i in states.split(',')]
        return states

    def set_display_resolution(self, channel, digits):
        """
        Sets the display resolution.
        
        :param channel: the channel of the gauge
        :param digits: the number of desired digits in the pressure readout
        :type channel: int
        :type digits: int
        """
        # sanity check for the channel input
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in list(range(0,3)):
            raise SyntaxError("The requested channel is not 1 or 2: %s" % channel)
        # sanity check for the desired display resolution
        if not isinstance(digits, int):
            return NotANumberError
        elif not digits in list(range(0,5)):
            raise SyntaxError("You must specify up to four digits: %s" % digits)
        # do the actual query
        if not channel:
            return self.query('DCD %s,%s' % (digits,digits))
        if channel==1:
            return self.query('DCD %s,' % digits)
        elif channel==2:
            return self.query('DCD ,%s' % digits)
    
    def set_gas_correction(self, channel, gas):
        """
        Sets the gas correction factor for the pressure reading.
        
        See the user manual or self.known_gases for options.
        
        :param channel: the channel of the gauge
        :param gas: the desired gas to use for the correction
        :type channel: int
        :type gas: str
        """
        # sanity check for the channel input
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in [1,2]:
            raise SyntaxError("The requested channel is not 1 or 2: %s" % channel)
        # sanity check for the gas type
        if not gas in self.known_gases:
            raise SyntaxError("The requested gas is not known: %s" % gas)
        gas_index = self.known_gases.index(gas.lower())
        # do the actual query
        if channel==1:
            return self.query('GAS %s,' % gas_index)
        elif channel==2:
            return self.query('GAS ,%s' % gas_index)
    
    def set_language(self, channel, lang):
        """
        Sets the display language of the readout.
        
        :param channel: the channel of the gauge
        :param lang: the desired language
        :type channel: int
        :type lang: str
        """
        # sanity check for the channel input
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in [1,2]:
            raise SyntaxError("The requested channel is not 1 or 2: %s" % channel)
        # do the actual query (including a sanity check)
        if lang.lower() in ["english", "englisch", "en"]:
            return self.query('LNG 0')
        elif lang.lower() in ["german", "deutsch", "de"]:
            return self.query('LNG 1')
        elif lang.lower() in ["french", "fr"]:
            return self.query('LNG 2')
        else:
            raise SyntaxError("The requested language is not known: %s" % lang)
    
    def set_unit(self, channel, unit):
        """
        Sets the unit to use for the pressure readings.
        
        :param channel: the channel of the gauge
        :param unit: the desired pressure unit
        :type channel: int
        :type unit: str
        """
        # sanity check for the channel input
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in [1,2]:
            raise SyntaxError("The requested channel is not 1 or 2: %s" % channel)
        # do the actual query (including a sanity check)
        if unit.lower() in ["bar", "mbar"]:
            return self.query('UNI 0')
        elif unit.lower() in ["torr", "mtorr"]:
            return self.query('UNI 1')
        elif unit.lower() in ["pascal", "pa"]:
            return self.query('UNI 2')
        elif unit.lower() in ["micron", "μ"]:
            return self.query('UNI 3')
        elif unit.lower() in ["hpascal", "hpa"]:
            return self.query('UNI 4')
        elif unit.lower() in ["volt", "v"]:
            return self.query('UNI 5')
        else:
            raise SyntaxError("The requested unit is not known: %s" % unit)

    def get_unit(self):
        """
        Reads the unit, which is selected on the gauge controller.

        returns string
        """
        unit = self.query('UNI')
        try:
            unit = int(unit)
        except:
            print(unit)
            return
        return self.units[unit]



