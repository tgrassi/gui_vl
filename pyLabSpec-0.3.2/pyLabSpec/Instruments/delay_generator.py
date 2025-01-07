#!/usr/bin/env python
# -*- coding: utf8 -*-
#
"""
This module provides classes and methods to control SRS DG645 Delay Generator.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import sys
import os
import time
import types

import numpy as np

if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from settings import *
if sys.version_info[0] == 3:
    from .instrument import *
else:
    from instrument import *

if sys.version_info[0] == 3:
    long = int


DELAY_CHANNEL = {'T0':0, 'T1':1, 'A':2, 'B':3, 'C':4, 'D':5, 'E':6, 'F':7,
                 'G':8, 'H':9}
DELAY_CHANNEL_IDX = {DELAY_CHANNEL[i]:i for i in DELAY_CHANNEL.keys()}

BNC_OUTPUT = {'T0':0, 'AB':1, 'CD':2, 'EF':3, 'GH':4}
BNC_OUTPUT_IDX = {BNC_OUTPUT[i]:i for i in BNC_OUTPUT.keys()}

class DelayGenerator():
    """
    General class to connect and control SRS DG645 Delay Generator.
    """
    __TERM = '\n'
    connected = False
    settings = Settings()

    def __init__(self, host, port=None, com='TCPIP'):
        """
        Initializes the object, essentially forwarding its arguments to
        the open() method.
        
        :param host: the name of the device
        :param port: (optional) the port number
        :param com: (optional) the means of communication (TCPIP or GPIB)
        :type host: str
        :type port: int
        :type com: str
        """
        self.open(host, port=port, com=com)
    
    def open(self, host, port=None, com=None):
        """
        Opens the socket.
        
        :param host: the name of the device
        :param port: (optional) the port number
        :param com: (optional) the means of communication (TCPIP or GPIB)
        :type host: str
        :type port: int
        :type com: str
        """
        try:
            self.socket = InstSocket(com, host = host, port = port, __TERM =
                                     self.__TERM)
            connected = True
        except:
            raise RuntimeError("Could not connect to Delay Generator.")
        self.identifier = self.identify()
    
    def close(self):
        """
        Removes the socket.
        """
        self.socket._close()
    
    def query(self, string):
        """
        Sends a query to the device.
        
        :param string: the query string to send
        :type string: str
        :returns: the response
        :rtype: str
        """
        #if string[-len(self.__TERM)] != self.__TERM:
        #    string += self.__TERM
        self.socket.clear()
        self.write(string)
        return self.read()
    
    def write(self, string):
        """
        Sends a command to the device.
        
        :param string: the command string to send
        :type string: str
        """
        #self.socket.clear()
        self.socket.write(string)
    
    def read(self):
        return self.socket.readline().strip()
    
    def identify(self):
        """
        Returns the identification string of the device.
        
        :returns: the identification string
        :rtype: str
        """
        return self.query('*IDN?')
    
    def clear(self):
        """
        Send a device clear status to the instrument.
        """
        self.write('*CLS')
    
    def esr(self):
        """
        Returns the contents of the Standard Event Status Register
        """
        self.query('*ESR?')
    
    def reset(self):
        """
        The Reset (RST) command resets most signal generator functions to a
        factory-defined state.
        """
        self.write('*RST')    

class SRS_Delay_Generator(DelayGenerator):
    """
    A subclass of Delay Generator specifically for the SRS_Delay_Generator.
    """
    def __init__(self, host, port=None, com='TCPIP'):
        """
        See the documentation for the parent class about the input arguments.
        """
        DelayGenerator.__init__(self, host, port=port, com=com)
        self.read_settings()

    def check_for_error(self):
        """
        Checks and reads errors from the instruments error
        queue.

        Returns all errors (up to 20 are stored) from
        the queue as a list.
        """
        errors = []
        while 1:
            error = self.query('LERR?').split(',')
            if int(error[0]):
                errors.append(int(error[0]))
            else:
                break
        return errors

    def read_settings(self):
        """
        """
        self.settings.trigger_source = self.get_trigger_source()
        self.settings.trigger_level = self.get_trigger_level()
        self.settings.trigger_rate = self.get_trigger_rate()

        # read out delay settings
        for ch in DELAY_CHANNEL:
            ref_ch, d = self.get_delay(ch)
            vars(self.settings)['delay_%s' % ch] = (ref_ch, d)

            #if ('delay_%s' % ch) in vars(self).keys():
            #    self.__dict__.update({'delay_%s' % ch: (ref_ch, d)})
            #else:
            #    setattr(self, 'delay_%s' % ch, (ref_ch, d))

        # read out BNC-Output-Settings
        for bnc  in BNC_OUTPUT:
            l = self.get_level_output(bnc)
            p = self.get_level_polarity(bnc)
            o = self.get_level_offset(bnc)
            vars(self.settings)['level_out_%s' % bnc] = l

            #if ('level_out_%s' % bnc) in vars(self).keys():
            #    self.__dict__.update({'level_out_%s' % bnc: l})
            #else:
            #    setattr(self, 'level_out_%s' % bnc, l)
            vars(self.settings)['level_offset_%s' % bnc] = o

            #if ('level_offset_%s' % bnc) in vars(self).keys():
            #    self.__dict__.update({'level_offset_%s' % bnc: o})
            #else:
            #    setattr(self, 'level_offset_%s' % bnc, o)
            vars(self.settings)['level_polarity_%s' % bnc] = p
            #if ('level_polarity_%s' % bnc) in vars(self).keys():
            #    self.__dict__.update({'level_polarity_%s' % bnc: p})
            #else:
            #    setattr(self, 'level_polarity_%s' % bnc, p)

    def print_settings(self):
        self.read_settings()
        print("Trigger source: %s" % self.settings.trigger_source)
        print("Trigger level: %lf" % self.settings.trigger_level)
        print("Trigger rate (internal): %lf" % self.settings.trigger_rate)
        print("BNC-OUTPUTS")
        for ch in sorted(DELAY_CHANNEL):
            print("Delay %s: %s + %5.12lf" % (ch, vars(self.settings)["delay_%s" % ch][0],
                                          vars(self.settings)["delay_%s" % ch][1]))
        for bnc in sorted(BNC_OUTPUT):
            print("Output Level %s: %lf" % (bnc, vars(self.settings)["level_out_%s" %
                                                           bnc]))
            print("Output Offset %s: %lf" % (bnc, vars(self.settings)["level_offset_%s" %
                                                            bnc]))
            print("Polarity %s: %s" % (bnc, vars(self.settings)["level_polarity_%s" %
                                                           bnc]))

    def apply_settings(self, **kwds):

        for ck in kwds.keys():
            if ck == 'settings':
                self.settings.apply_settings(kwds[ck])
            else:
                self.settings.set(ck, kwds[ck])
            #if ck in vars(self).keys():
            #    self.__dict__.update({ck: kwds[ck]})
            #else:
            #    setattr(self, ck, kwds[ck])

        self.set_trigger_source(self.settings.get('trigger_source'))
        self.set_trigger_level(self.settings.get('trigger_level'))
        for ch in DELAY_CHANNEL:
            delay = self.settings.get("delay_%s" % ch)
            self.set_delay(ch, delay[0], delay[1])
        for bnc in BNC_OUTPUT:
            
            self.set_level_output(bnc, self.settings.get('level_out_%s' % bnc))
            self.set_level_offset(bnc, self.settings.get('level_offset_%s' \
                                                         % bnc))
            self.set_level_polarity(bnc, self.settings.get('level_polarity_%s'\
                                                           % bnc))

        self.read_settings()

    def set_trigger_source(self, trigger_source = 1):
        """
        Set the trigger source (trigger_source). The parameter trigger_source determines the trigger
        source according to the following table:
        
        i Trigger Source
        0 Internal
        1 External rising edges
        2 External falling edges
        3 Single shot external rising edges
        4 Single shot external falling edges
        5 Single shot
        6 Line
        
        :param trigger_source: Set the trigger source 
        :type trigger_source: int
        """
        if (not isinstance(trigger_source, (int, long, float))) or \
           (trigger_source not in [0, 1, 2, 3, 4, 5, 6] ):
            print("trigger_source has to be a integer between 0 and 6")
            return
        
        self.write('TSRC %i' % trigger_source)

    def send_trigger(self):
        """
        Sends a trigger signal. This is only useful for single-shot mode.
        """
        self.write('*TRG')
        
    def get_trigger_source(self):
        """
        Queries the trigger source.
        
        :returns: the state of the trigger source
        :rtype: int
        """
        return int(self.query('TSRC?'))
    
   
    def set_trigger_rate(self, trigger_rate):
        """
        Sets the trigger source rate.

        :param trigger_rate: the rate for the internal trigger source
        :type trigger_rate: float
        """

        if not isinstance(trigger_rate, float):
            print("trigger_rate has to be a float")
            return

        self.write('TRAT %f' % trigger_rate)

    def get_trigger_rate(self):
        """
        Queries the trigger source rate.

        :returns: the state of the trigger source level
        :rtype: float
        """
        return float(self.query('TRAT?'))


    def set_trigger_level(self, trigger_level):
        """
        Sets the trigger source level.
        
        :param trigger_level: the state of the trigger source level
        :type trigger_level: float
        """
        
        if not isinstance(trigger_level, float):
            print("trigger_level has to be a float")
            return
        
        self.write('TLVL %f' % trigger_level)
        
    def get_trigger_level(self):
        """
        Queries the trigger source level.
        
        :returns: the state of the trigger source level
        :rtype: float
        """
        return float(self.query('TLVL?'))

    ####Es fehlt noch Amplitude (offset, setup)  
    ##unterer syntax ist von synthesizer script übernommen  

    def set_delay(self, channel, ref_channel, delay):
        """
        Sets the delay (length_ch_delay) for channel (channel) to equal channel (equal_ch_delay) puls in s.
        
        :param channel: sets the channel with showed have a delay
        :type channel: string
        :param ref_ch_delay:  reference channel 
        :type ref_ch_delay: string
        :param delay: delay of CH in s (reference: ref_channel)
        :type delay: float
        """

        if channel in DELAY_CHANNEL:
            #idx_ch = DELAY_CHANNEL.values()
            idx_ch = DELAY_CHANNEL[channel]
            #print(idx_ch)
        else:
            idx_ch = channel
                
        if ref_channel in DELAY_CHANNEL:
            idx_ref_ch = DELAY_CHANNEL[ref_channel]
            #print(idx_ref_ch)
        else:
            idx_ref_ch = ref_channel            

        try:            
            #ch_delay = float(ch_delay)
            #print(idx_ch)
            #print(idx_equal_ch)
            #print(ch_delay)
            self.write('DLAY %i,%i,%g' % (idx_ch, idx_ref_ch, delay))
        except:
            print("Could not process result!")
            return '', None 

    
        
    def get_delay(self, channel):
        """
        Queries the delay for channel in s.
        
        :param channel: gives back the delay length of the channel ch_delay in s
        :type channel: int
        """
        if channel in DELAY_CHANNEL:
            idx_ch = DELAY_CHANNEL[channel]
        else:
            idx_ch = channel

        try:
            ret_ch, ret_delay = self.query('DLAY?%i' % idx_ch).split(',')
            delay = float(ret_delay)
            ch = DELAY_CHANNEL_IDX[int(ret_ch)]
        except:
            print("Could not process result!")
            return '', None
        
        return ch, delay


    def set_level_output(self, bnc_output, level = 2.5):
        """
        Set the output level for a BNC - output
        
        :param bnc_output: bnc output (T0, AB, CD, EF, GH)
        :type bnc_output: string
        :param level: Level to be set (in V)
        :type level: float
        """
        if bnc_output in BNC_OUTPUT:
            idx_output_bnc = BNC_OUTPUT[bnc_output]
        else:
            print('bnc_output has to be one of: %s' % (', '.join(list(BNC_OUTPUT.keys()))))
            return

        if not isinstance(idx_output_bnc, int) and isinstance(level, float):
           raise NotANumberError
        
        self.write('LAMP %i,%f' % (idx_output_bnc, level))
        
    def get_level_output(self, bnc_output):
        """
        Query the output-level for bnc output 
        
        :param bnc_output: bnc-output (T0, AB, CD, EF, GH)
        :type bnc_output: string 

        :returns: the EF output amplitude
        :rtype: float
        """
        if bnc_output in BNC_OUTPUT:
            idx_output_bnc = BNC_OUTPUT[bnc_output]
        else:
            print('bnc_output has to be one of: %s' % (', '.join(list(BNC_OUTPUT.keys()))))
            return

        return float(self.query('LAMP?%i' % idx_output_bnc))
  
    
    def set_level_offset(self, bnc_output, level = 0.0):
        """
        Set the level (level_ch_offset) for output (ch_offset)
        
        :param bnc_output: BNC - output (T0, AB, CD, EF, GH)
        :type bnc_output: string
        :param level: Offset in V (Default = 0.0V)
        :type level: float
        """
        if bnc_output in BNC_OUTPUT:
            idx_output_bnc = BNC_OUTPUT[bnc_output]
        else:
            print('bnc_output has to be one of: %s' % (', '.join(list(BNC_OUTPUT.keys()))))
            return

        if not isinstance(idx_output_bnc, int) and isinstance(level, float):
            raise NotANumberError
        
        self.write('LOFF %i,%f' % (idx_output_bnc, level))
        
    def get_level_offset(self, bnc_output):
        """
        Queries offset-level for BNC output 

        :param bnc_output: BNC-Output (T0, AB, CD, EF, GH)
        :type bnc_output: string
                
        :returns: the output offset for BNC output in V
        :rtype: float
        """
        if bnc_output in BNC_OUTPUT:
            idx_output_bnc = BNC_OUTPUT[bnc_output]
        else:
            print('bnc_output has to be one of: %s' % (', '.join(list(BNC_OUTPUT.keys()))))
            return

        return float(self.query('LOFF?%i' % idx_output_bnc)) 
         
    
    def set_level_polarity(self, bnc_output, polarity):
        """
        Set the polarity of BNC-output.
        
        :param bnc_output: BNC-Output (T0, AB, CD, EF, GH
        :type bnc_output: string
        :param polarity: polarity ('pos', 'neg') 
        :type polarity: string
        """
        if bnc_output in BNC_OUTPUT:
            idx_output_bnc = BNC_OUTPUT[bnc_output]
        else:
            print('bnc_output has to be one of: %s' % (', '.join(list(BNC_OUTPUT.keys()))))
            return
        
        if (polarity[:3] == 'pos'):
            pol = 1
        if (polarity[:3] == 'neg'):
            pol = 0
        self.write('LPOL %i,%i' %  (idx_output_bnc, pol))

    def get_level_polarity(self, bnc_output):
        """
        Queries the polarity (positive or negative) for specified bnc output 
        
        :param bnc_output: BNC-Output (T0, AB, CD, EF, GH)
        :type bnc_output: string
        :returns: the polarity ('neg', 'pos') for output 
        :rtype: string
        """
        if bnc_output in BNC_OUTPUT:
            idx_output_bnc = BNC_OUTPUT[bnc_output]
        else:
            print('bnc_output has to be one of: %s' % (', '.join(list(BNC_OUTPUT.keys()))))
            return

        polarity = int(self.query('LPOL?%i' % idx_output_bnc))

        if polarity == 1:
            return 'pos'
        elif polarity == 0:
            return 'neg'
        else:
            return ''


    def set_IP_address(self, IP_address):
        """
        Set the static IP Adress
        
        :param IP_address: the IP Adress for the DG645’s
        :type IP_address: float
        """
        if not isinstance(IP_address, float):
            raise NotANumberError
        
        self.write('IFCF 11,%f' %  IP_address)
    
    def get_MAC_Address(self):
        """
        Query the DG645 Ethernet MAC address.
        """
        return str(self.query('EMAC?')) 
        
        
    def set_burst_mode(self, burst_mode = 0):
        """
        Set the burst mode on (1) or off (0).
        If i is 0 (OFF), burst mode is disabled. If i is 1 (ON), burst mode is enabled.
        
        :param burst_mode: Determines wether the burst mode is on (1) or off (1)
        :type burst_mode: int
        """
        if not isinstance(burst_mode, int):
            raise NotANumberError
        
        self.write('BURM %i' % burst_mode)
        
    def get_burst_mode(self):
        """
        Query the burst mode on (1) or off (0).
        If i is 0 (OFF), burst mode is disabled. If i is 1 (ON), burst mode is enabled.
        """
        return int(self.query('BURM?')) 
