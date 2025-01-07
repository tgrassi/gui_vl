#!/usr/bin/env python
# -*- coding: utf8 -*-
#
# TODO
# - add delay controls
# - find out how to clear existing errors
#
"""
This module provides classes and methods to control fancy (tabletop)
multimeters.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
import time
# third-party libraries
import numpy as np
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from settings import *
from . import instrument as instr

class usbtmcdmm(instr.InstSocket):
    """
    Provides a general socket for tabletop digital multimeters via USB.
    
    Supported devices (known):
    - Keithley 2100 DMM
    - Keysight 34465A DMM
    """
    
    modes = [
        'VOLT:AC', 'VOLT:DC',
        'CURR:AC', 'CURR:DC',
        'RES',
        'FRES',
        'TEMP',
        'FREQ'
    ]
    averaging_types = ['MOV', 'REP']
    
    def __init__(self, host='', com='direct'):
        instr.InstSocket.__init__(self, host=host, com=com)
        
        # initialize statuses & check ID
        self.isconnected = True
    
    def clear(self):
        """
        Clears the device.
        """
        self.write("*CLS")
    def reset(self):
        """
        Resets the device.
        """
        self.write("*RST")
    
    def send_trigger(self):
        '''
        Send trigger to Keithley, use when triggering is not continuous.
        '''
        self.write('INIT')
    def clear_trigger(self):
        '''
        Sets trigger back to continuous mode
        '''
        self.write('TRIGger:SOURce IMMediate')
    
    def display_clear(self):
        """
        Clears the display text.
        """
        self.write('DISPLAY:TEXT:CLEar')
    def display_text(self, text):
        """
        Sets the display to show a text string.
        """
        self.write('DISPLAY:TEXT "%s"' % text)
    
    def fetch(self):
        '''
        Get data at this instance, not recommended, use get_readval.
        Use send_trigger() to trigger the device.
        Note that Readval is not updated since this triggers itself.
        '''
        num = self.get_datapoints()
        reply = self.query('FETCH?', num=num)
        return reply
    def do_readval(self, num=0):
        '''
        Waits for the next value available and returns it as a float.
        Note that if the reading is triggered manually, a trigger must
        be send first to avoid a time-out.
        '''
        text = self.query('READ?', num=num)
        return text
    def set_delay(self, num=0):
        """
        Sets the trigger delay.
        """
        if num:
            cmd = "TRIGger:DELay %s" % num
        else:
            cmd = "TRIGger:DELay:AUTO ON"
        self.write(cmd)
    
    def set_count(self, num=0):
        """
        Sets the readings count.
        """
        if num:
            cmd = "TRIGger:COUNT %s" % num
        else:
            cmd = "TRIGger:COUNT INFinite"
        self.write(cmd)
        #if num:
        #    cmds = ["SAMP:COUNT %s" % num]
        #    cmds += ["TRIGger:COUNT %s" % num]
        #else:
        #    cmds = ["SAMP:COUNT MAXimum"]
        #    cmds += ["TRIGger:COUNT INFinite"]
        #for c in cmds:
        #    self.write(c)
    def get_count(self):
        """
        Gets the readings count.
        """
        num = self.query('SAMP:COUNT?')
        return int(float(num))
    
    def get_datapoints(self):
        """
        Queries the device about the number of stored readings.
        """
        num = self.query('DATA:POINts?')
        return int(float(num))
    
    
    def set_mode_volt_ac(self):
        '''
        Set mode to AC Voltage
        '''
        self.set_mode('VOLT:AC')
    def set_mode_volt_dc(self):
        '''
        Set mode to DC Voltage
        '''
        self.set_mode('VOLT:DC')
    def set_mode_curr_ac(self):
        '''
        Set mode to AC Current
        '''
        self.set_mode('CURR:AC')
    def set_mode_curr_dc(self):
        '''
        Set mode to DC Current
        '''
        self.set_mode('CURR:DC')
    def set_mode_res(self):
        '''
        Set mode to Resistance
        '''
        self.set_mode('RES')
    def set_mode_fres(self):
        '''
        Set mode to 'four wire Resistance'
        '''
        self.set_mode('FRES')
    def set_mode_temp(self):
        '''
        Set mode to Temperature
        '''
        self.set_mode('TEMP')
    def set_mode_freq(self):
        '''
        Set mode to Frequency
        '''
        self.set_mode('FREQ')
    def set_mode(self, mode):
        '''
        Set the mode to the specified value
        '''
        if mode in self._modes:
            string = 'SENS:FUNC "%s"' % mode
            self.write(string)
            
            if mode.startswith('VOLT'):
                self._change_units('V')
            elif mode.startswith('CURR'):
                self._change_units('A')
            elif mode.startswith('RES'):
                self._change_units('Ohm')
            elif mode.startswith('FREQ'):
                self._change_units('Hz')
    
    def get_mode(self):
        '''
        Returns the current measurement mode
        '''
        return self.query('FUNCtion?')
    
    
    def set_autorange(self, mode=None):
        '''
        Old function to set autorange, links to set_autorange()
        '''
        self.set_autorange(True)
    
    def get_input_terminal(self):
        '''
        Queries the input terminals (front or rear)
        '''
        num = self.query('ROUTe:TERMinals?')
    
