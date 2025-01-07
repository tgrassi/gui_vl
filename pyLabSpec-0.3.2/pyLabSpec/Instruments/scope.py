#!/usr/bin/env python
# -*- coding: utf8 -*-
#
"""
This module provides classes and methods to control devices related to
the Chirped Pulse Spectrometer (Scope, AWG, ...).

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import sys
import os
import socket
import time
import struct

import numpy as np

if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from settings import *
if sys.version_info[0] == 3:
    from .instrument import *
else:
    from instrument import *
import Simulations.waveformbuilder as wb
from Spectrum import spectrum

BUFFERSIZE = 8192

if sys.version_info[0] == 3:
    xrange = range

def initScope(host = SCOPE_HOST, port = SCOPE_PORT, com = 'TCPIP'):
    """
    Tries to identify the scope and returns an instance of the corresponding scope-class.
    """
    s = Scope(host = host, port = port)
    if not s.connected:
       return None

    if 'keysight' in s.identifier.lower():
        scope = Agilent(host = host, port = port)
    elif 'tektronix' in s.identifier.lower():
        scope = Tektronix(host = host, port = port)
    else:
        scope = Scope(host = host, port = port)
    s.close()
    return scope     

class Scope(object):
    """
    Absract class to control the Scope 
    """
    data_encoding = None
    samplerate = None
    connected = False
    identifier = None
    settings = Settings()

    def __init__(self, host = SCOPE_HOST, port = SCOPE_PORT, com = 'TCPIP'):
        try:
            self.socket = InstSocket(com, host = host, port = port)
        except:
            print("Could not connect to Scope")
            return
        #self.identity = self.identify()
        try:
           self.get_encoding()
           self.get_samplerate()
        except:
           pass
        self.connected = True
        self.identifier = self.identify()

    def close(self):
        self.socket.close()

    def query(self, string):
        return self.socket.query(string)

    def write(self, string):
        self.socket.write(string)

    def read(self, length = 1):
        return self.socket.read(length)

    def readall(self):
        return self.socket.readall()

    def identify(self):
        return self.query('*IDN?')

    def clear(self):
        """
        Send a device clear message to the instrument.        
        """
        self.write('*DCL')

    def esr(self):
        """
        Returns the contents of the Standard Event Status Register        
        """
        self.query('*ESR?')

    def wait(self):
        """
        Send a wait command. Later commands are only processed if
        previous commands are completed.
        """
        self.write('*WAI')

    def display_waveform(self, display = True):
        """
        Turn the display of waveforms in the scope on or off.

        display : Boolean (True -> On, False -> Off)
        """
        raise MethodNotAvailableError

    def get_file_dir(self):
        """
        Returns the current directory.
        """
        raise MethodNotAvailableError

    def set_file_dir(self, dir_name):
        """
        Changes the current working directory.
        
        :param dir_name: new working directory
        """
        raise MethodNotAvailableError

    def define_spectral_mag(self, channel, math):
        """
        Defines the spectal-magnitude function on channel as math.
        """
        raise MethodNotAvailableError
        
    def define_average(self, channel, math, numavg):
        """
        Defines the average function on channel as math.
        """
        raise MethodNotAvailableError


    def get_num_acquisitions(self):
        """
        Queries the number of acquisitions.
        """
        raise MethodNotAvailableError

    def set_data_source(self, source):
        """
        Sets the data source to CH1-4, MATH1-4
        """
        raise MethodNotAvailableError

    def get_data_source(self):
        """
        Queries the data source (CH1-4, MATH1-4,...).
        """
        raise MethodNotAvailableError

    def get_encoding(self):
        """
        Queries the encoding for the data transfer.
        """
        raise MethodNotAvailableError

    def set_encoding(self, encoding = 'FPBINARY'):
        """
        Sets the encoding for data transfer from the scope (Default: FPBINARY)
        """
        raise MethodNotAvailableError
     
    def get_curve(self):
        """
        Queries the data for the selected source from the scope.
        """
        raise MethodNotAvailableError

    def get_next_curve(self):
        """
        Queries unique data for the selected source from the scope.
        """
        raise MethodNotAvailableError

    def get_samplerate(self):
        """
        Queries the current samplerate.
        """
        raise MethodNotAvailableError

    def set_samplerate(self, samplerate):
        """
        Sets the samplerate.
        """
        raise MethodNotAvailableError

    def get_recordlength(self):
        """
        Queries the recordlength.
        """
        raise MethodNotAvailableError

    def get_acquisition_duration(self):
        """
        Queries the duration of acquisition.
        """
        raise MethodNotAvailableError

    def set_horizontal_scale(self, scale):
        """
        Sets the horizontal scale in time per division.
       
        :param scale: time per division in seconds
        :type scale: float
        """
        raise MethodNotAvailableError

    def display_curve(self, source, shown):
        """
        Controls the display of a curve (on or off).
        
        :param source: channel which is controlled (CH1-4, MATH1-4,...)
        :type source: str
        :param shown: True if channel shall be displayed otherwise False
        :type shown: boolean
        """
        raise MethodNotAvailableError

    def get_waveform_pre(self):
        """
        Queries the waveform preamble.
        """
        raise MethodNotAvailableError

    def set_transfer_range(self, start = None, stop = None):
        """
        Sets the range of points within a waveform that will be transfered.
        If not specified range will start with first and end with the last
        recorded point.
        """
        raise MethodNotAvailableError

    def get_transfer_range(self):
        """
        Query the point range for data transfer.
        """
        raise MethodNotAvailableError

    ######################################################
    # FAST FRAME
    ######################################################
    def get_fast_frame_source(self):
        """
        Get the selected source of the fast frame mode
        """
        raise MethodNotAvailableError

    def set_fast_frame_source(self, source):
        """
        Sets the selected source of the fast frame mode.

        :param source: Source (CH1-4, MATH1-4)
        :type source: str
        """
        raise MethodNotAvailableError

    def get_num_frames(self):
        """
        Queries the number of frames set in the fast frame mode
        """
        raise MethodNotAvailableError

    def set_num_frames(self, num_frames):
        """
        Sets the number of frames.
        """
        raise MethodNotAvailableError

    def get_selected_frame(self):
        """
        Query the selected frame of the fast frame mode.
        """
        raise MethodNotAvailableError

    def select_last_frame(self):
        """
        Selects the last frame.
        """
        raise MethodNotAvailableError

    def get_summary_frame_mode(self):
        """
        Query the summary frame mode.
        """
        raise MethodNotAvailableError

    def set_summary_frame_mode(self, mode = 'AVERAGE'):
        """
        Set the summary frame mode (default to average all frames into summary frame)
        """
        raise MethodNotAvailableError

    def set_math_on_summaryframe(self, enabled = True):
        """
        Sets the math on only the summary frame if enabled.
        """
        raise MethodNotAvailableError

    def get_fast_frame_state(self):
        """
        Queries wethter the fast frame mode is enabled.
        """
        raise MethodNotAvailableError

    def set_fast_frame(self, enable = True):
        """
        Set the fast frame mode.
        
        :param enable: If true, fast frame is switched on
        :type enable: Boolean
        """
        raise MethodNotAvailableError

    def get_frame_for_transfer(self):
        """
        Query selected frame for data transfer.
        """
        raise MethodNotAvailableError
        
    def select_frame_for_transfer(self, frame = None):
        """
        select frame for data transfer (default = last-frame)
        """
        raise MethodNotAvailableError


class Agilent(Scope):
    """
    Class to control the Agilent Scope.
    """
    ACQUISITION_MODES = ['HRES', 'SEGH', 'ETIM', 'RTIM', 'PDET', 'SEGM', 'SEGP']
    TIMEOUT = 5

    def __init__(self, host = SCOPE_HOST, port = SCOPE_PORT):
        Scope.__init__(self, host = host, port = port)
        self.settings.byte_order = self.get_byte_order()
        self.socket._sock.settimeout(self.TIMEOUT)
        #self.read_settings()
        #self.print_settings()

    def read_settings(self):
        
        self.get_samplerate()
        self.settings.encoding = self.get_encoding()

        self.get_timebase_range()
        self.get_timebase_position()

        self.get_average_mode()
        self.get_num_averages()
       
        self.get_reference_clock()
        self.get_acquisition_mode()
        # query channel specific parameters
        for ch in xrange(1,5):
            self.get_signal_range(ch)
            self.get_signal_unit(ch)
            self.get_signal_scale(ch)
            self.get_display_state('CHAN%d' % ch)

        for func in xrange(1,17):
            self.get_display_state('FUNC%d' % func)

    def apply_settings(self, **kwds):
        """
        Apply the current settings (to the scope).
        """
        for ck in kwds.keys():
            if ck == 'settings':
                self.settings.apply_settings(kwds[ck])
            else:
                self.settings.set(ck, kwds[ck])

        if hasattr(self.settings, 'samplerate'):
            self.set_samplerate(self.settings.samplerate)
        if hasattr(self.settings, 'encoding'):
            self.set_encoding(self.settings.encoding)
        if hasattr(self.settings, 'byte_order'):
            self.set_byte_order(self.settings.byte_order)
        if hasattr(self.settings, 'horizontal_position'):
            self.set_timebase_position(position = self.settings.horizontal_position)
        if hasattr(self.settings, 'horizontal_range'):
            self.set_timebase_range(self.settings.horizontal_range)
        if hasattr(self.settings, 'average_mode'):
            self.set_average_mode(self.settings.average_mode)
        if hasattr(self.settings, 'num_averages'):
            self.set_num_averages(self.settings.num_averages)
        if hasattr(self.settings, 'acquisition_mode'):
            self.set_acquisition_mode(self.settings.acquisition_mode)
        if hasattr(self.settings, 'reference_clock'):
            self.set_reference_clock(self.settings.reference_clock)

        for ch in xrange(1,5):
            if hasattr(self.settings, 'vertical_range_ch%d' % ch):
                self.set_signal_range(ch, vars(self.settings)['vertical_range_ch%d'
                                                              % ch])
            if hasattr(self.settings, 'vertical_unit_ch%d' % ch):
                self.set_signal_unit(ch, vars(self.settings)['vertical_unit_ch%d' 
                                                              % ch])
            if hasattr(self.settings, 'display_chan%d' % ch):
                self.set_display_state('CHAN%d' % ch,
                                       vars(self.settings)['display_chan%d' % ch])

        for func in xrange(1,17):
            if hasattr(self.settings, 'display_func%d' % func):
                self.set_display_state('FUNC%d' % func,
                                       vars(self.settings)['display_func%d' % func])

        self.read_settings()

    def print_settings(self):
        """
        print the settings.
        """
        for ck in sorted( self.settings.__dict__.keys() ):
            print("%s: %s" % (ck, vars(self.settings)[ck]))

    def check_for_error(self):
        """
        Checks and reads errors from the instruments error queue.

        Returns all errors (up to 30 are stored) from the queue as a list.
        """
        errors = []
        while 1:
           error = self.query(':SYST:ERR?').split(',')
           if int(error[0]):
               errors.append(error)
           else:
               break
              
        return errors

    def set_reference_clock(self, clock = 'INT'):
        """
        Selects the reference clock.

        :param clock: 'Int' for internal, 'Ext' for external.
        :type clock: string
        """
        if clock.upper() == 'EXT':
            self.write(':TIM:REFC 1')
        else:
            self.write(':TIM:REFC 0')

        clock = self.get_reference_clock()
        print("Clock set to %s" % clock)

    def get_reference_clock(self):
        """
        Determines the reference clock
        """
        cl = self.query(':TIM:REFC?')
        if cl == '1':
            cl = 'EXT'
        else:
            cl = 'INT'
        self.settings.set('reference_clock', cl)
        return cl

    def display_waveform(self, display = True):
        """
        Turn the display of waveforms in the scope on or off.

        display : Boolean (True -> On, False -> Off)
        """
        if display:
            self.write('DISPLAY:MAIN ON')
            print("Display has been turned on.")
        else:
            self.write('DISPLAY:MAIN OFF')
            print("Display has been turned off.")

    def display_channel(self, channel, display = True):
        """
        Show the specified channel on the scope.
        """
        if display:
            self.write(':CHANnel%d:DISPLAY ON' % channel)
        else:
            self.write(':CHANnel%d:DISPLAY OFF' % channel)

    def set_display_state(self, channel, display = True):
        """
        """
        if type(channel) == int:
            channel = 'CHAN%d' % channel
        elif type(channel) == str and len(channel) == 1:
            channel = 'CHAN%s' % channel
        else:
            if channel[:4] not in ('CHAN', 'FUNC', 'WMEM'):
                print("channel has to be 'CHAN[1-4], FUNC[1-16], or WMEM[]")
                return 
        if display:
            self.write(':%s:DISPLAY ON' % channel)
        else:
            self.write(':%s:DISPLAY OFF' % channel)
        print("Display for %s is %s" % (channel,
                                        self.get_display_state(channel)))

       
    def get_display_state(self, channel):
        """
        Returns if the waveform is displayed or not.
        """
        if type(channel) == int:
            channel = 'CHAN%d' % channel
        elif type(channel) == str and len(channel) == 1:
            channel = 'CHAN%s' % channel
        else:
            if channel[:4].upper() not in ('CHAN', 'FUNC', 'WMEM'):
                print("channel has to be 'CHAN[1-4], FUNC[1-16], or WMEM[]")
                return False
        s = int(self.query(':%s:DISPLAY?' % channel.upper()))

        if s == 0:
            state = False
        else:
            state = True

        self.settings.set('display_%s' % channel.lower(), state)
        return state

    def get_samplerate(self):
        """
        Queries the current samplerate.
        """
        samplerate = float(self.query(':ACQuire:SRATe?'))
        self.settings.set('samplerate', samplerate)
        return samplerate

    def set_samplerate(self, samplerate):
        """
        Sets the samplerate.
        """
        # select manual mode in order to be able to change the samplerate
        self.write(':ACQuire:SRATe:AUTO OFF')
        self.write(':ACQuire:SRATe %lf' % samplerate)
        
        sr = self.get_samplerate()
        print("Samplerate set to %lf GSa/s" % (sr / 1.0e9))

    def set_data_source(self, source):
        """
        Sets the data source to CH1-4, FUNC1-16
        """
        if source[:2] == "CH":
            source = int(source.upper().replace('CH','').replace('AN','').replace('NEL',''))
            self.write(':WAVEFORM:SOURCE CHANNEL%d' % source)
        elif source[:4] == "FUNC":
            source = int(source.upper().replace('FUNC','').replace('TION',''))
            self.write(':WAVEFORM:SOURCE FUNC%d' % source)
        else:
            print("Source has to be one of CH1-4 or FUNC1-16")
        return self.query(':WAVEFORM:SOURCE?')
     
    def get_data_source(self):
        """
        Queries the data source (CH1-4, MATH1-16,...).
        """
        return self.query(':WAVEFORM:SOURCE?')


    def get_encoding(self):
        """
        Queries the encoding for the data transfer.
        """
        data_encoding = self.query(':WAV:FORM?')
        self.settings.set('data_encoding', data_encoding)
        return data_encoding

    def set_encoding(self, encoding = 'WORD'):
        """
        Sets the encoding for data transfer from the scope (Default: WORD)
        """
        if not encoding in ('ASCII', 'BINARY', 'BYTE', 'WORD'):
           print("Encoding has to be one of 'ASCII', 'BINARY', BYTE or WORD")
           return
        self.write(':WAV:FORM %s' % encoding)
        enc = self.get_encoding()
        print("Encoding set to %s" % enc)

    def get_byte_order(self):
        """
        Returns the selected byte order for data transfer (words / long).
        Possible values are LSBFirst (faster) or MSBFirst.
        """
        ret_val = self.query(':WAV:BYT?')
        if ret_val == 'MSBF':
            self.settings.byte_order_conversion = '>h'
        else:
            self.settings.byte_order_conversion = '<h'
        self.settings.set('byte_order', ret_val)
        return ret_val

    def set_byte_order(self, order = 'LSBF'):
        """
        Sets the byte order for data transfer (words).

        Possble values are LSBFirst (Least significant byte first; faster) or
        MSBFirst (Most significant byte first).

        :param order: Byte order (MSBF|LSBF)
        :type order: string
        """
        self.write(':WAV:BYT %s' % order)
        print("Byte order set to %s" % self.get_byte_order())

    def get_recordlength(self):
        """
        Query the number of points to be recorded.
        """
        return int(self.query(':ACQ:POINTS?'))

    def set_recordlength(self, num_points):
        """
        Sets the number of points to be recorded.
        """
        self.write(':ACQ:POINTS %d' % num_points)

    def get_curve(self, start = None, size = None):
        """
        Queries the data for the selected source from the scope.
        """
        if size:
           if not start:
              start = 0
           data = self.write(':WAVeform:DATA? %d, %d' % (start, size))
        elif start:
           data = self.write(':WAVeform:DATA? %d' % start)
        else:
           data = self.write(':WAVeform:DATA?')
        #esr = self.query('*ESR?')
        if self.settings.data_encoding == 'ASC':
            data = self.readall()
            esr = self.query('*ESR?')
            data = np.array([float(i) for i in data.split(',') if len(i)>0])
        elif self.settings.data_encoding == 'WORD':
            if self.read(1)!='#':
                print("Data does not start with #")
                return None
            len_data_length = int(self.read(1))
            data_length = int(self.read(len_data_length))

            length_read = 0
            data = []
            while length_read < data_length:
                new_data = self.read(min(BUFFERSIZE, data_length - length_read))
                data += [struct.unpack('<h', new_data[2*i:2*i+2])[0] for i in \
                         xrange(len(new_data)//2)]
                length_read += len(new_data)
            term_str = self.read(1)
        return data

    def set_signal_range(self, channel, range_value, unit = None):
       """
       Set the vertical full-scale range in current units if not specified otherwise.
       """
       if unit:
          self.set_unit(channel, unit)
       self.write(':CHAN%d:RANG %lf' % (channel, range_value))
       print("Set vertical range for channel %d to %lf" % (channel,
                                                         self.get_signal_range(channel)))

    def get_signal_range(self, channel):
       """
       Returns the current vertical full-scale range.
       """
       #unit = self.get_signal_unit(channel)
       range_value = float(self.query(':CHAN%d:RANG?' % channel))
       self.settings.set('vertical_range_ch%d' % channel, range_value)
       return range_value

    def get_signal_unit(self, channel):
       """
       Returns the current vertical unit.
       """
       unit = self.query( ':CHAN%d:UNIT?' % channel)
       self.settings.set('vertical_unit_ch%d' % channel, unit)
       return unit

    def set_signal_unit(self, channel, unit):
       """
       Sets the current vertical unit (VOLT | AMP | WATT | UNKN).
       """
       if unit[:4].upper() not in ('AMP', 'VOLT', 'WATT', 'UNKN', 'AMPE'):
           print("Unit has to be one of (VOLT | AMP | WATT | UNKN).")
           return
       self.write(':CHAN%d:UNIT %s' % (channel, unit))
       print("Vertical unit for channel %d set to %s" % (channel,
                                                         self.get_signal_unit(channel)))

    def set_signal_scale(self, channel, scale):
       """
       Set the vertical scale (units per division).
       """
       self.write(':CHAN%d:SCAL %lf' % (channel, scale))
       print("Vertical scale for channel %d set to %lf" % (channel,
                                                         self.get_signal_scale(channel)))
  
    def get_signal_scale(self, channel):
        """
        Returns the vertical scale (units per division) for the selected
        channel.

        :param channel: Channel
        :type channel: int
        """
        scale = float(self.query(':CHAN%d:SCAL?' % channel))
        self.settings.set('vertical_scale_ch%d' % channel, scale)
        return scale

    def set_function_vertical_range(self, function, range_value, unit = None):
       """
       Set the vertical full-scale range in current units if not specified otherwise.
       """
       if unit:
          self.set_unit(channel, unit)
       self.write(':FUNC%d:VERT:RANG %lf' % (function, range_value))

    def set_function_vertical_offset(self, function, offset):
       """
       Set the vertical offset in the currently selected Y-axis units.
       """
       self.write(':FUNC%d:VERT:OFFS %lf' % (function, offset))

    def get_function_vertical_offset(self, function):
       """
       Get the vertical offset in the currently selected Y-axis units.
       """
       return float(self.query(':FUNC%d:VERT:OFFS?' % function))

    def get_function_vertical_range(self, function):
       """
       Returns the current vertical full-scale range.
       """
       yrange = self.query(':FUNC%d:VERT:RANG?' % function)
       return float(yrange)
   
    def set_function_horizontal_range(self, function, range_value, unit = None):
       """
       Set the horizontal full-scale range in current units if not specified otherwise.
       """
       if unit:
          self.set_unit(function, unit)
       self.write(':FUNC%d:HOR:RANG %lf' % (function, range_value))

    def set_function_horizontal_position(self, function, position):
       """
       Set the horizontal position in seconds.
       """
       self.write(':FUNC%d:HOR:POS %lf' % (function, position))

    def get_function_horizontal_position(self, function):
       """
       Get the horizontal position in seconds.
       """
       return float(self.query(':FUNC%d:HOR:POS?' % function))

    def get_function_horizontal_range(self, function):
       """
       Returns the current horizontal full-scale range.
       """
       return float(self.query(':FUNC%d:HOR:RANG?' % function))

    def set_timebase_position(self, position):
       """
       Sets the time interval between the trigger event
       and the delay reference point. The delay reference point is set with the
       :TIMebase:REFerence command.

       :param position: Position in seconds.
       :type position: float
       """
       self.write(':TIM:POS %lf' % position)
       return self.get_timebase_position()

    def get_timebase_position(self):
       """
       Returns the time interval between the trigger event
       and the delay reference point. The delay reference point is set with the
       :TIMebase:REFerence command.
       """
       horizontal_position = float(self.query(':TIM:POS?'))
       self.settings.set('horizontal_position', horizontal_position)
       return horizontal_position

    def set_timebase_range(self, full_scale_range):
       """
       Sets the full-scale horizontal time in seconds.
       The range value is ten times the time-per-division value.

       :param full_scale_range: full-scale horizontal time range
       :type full_scale_range: float
       """
       self.write(':TIM:RANG %lf' % full_scale_range)
       return self.get_timebase_range()

    def get_timebase_range(self):
       """
       Returns the full-scale horizontal time in seconds.
       The range value is ten times the time-per-division value.
       """
       horizontal_range = float(self.query(':TIM:RANG?'))
       self.settings.set('horizontal_range', horizontal_range)
       return horizontal_range

    def get_timebase_reference_percent(self):
       """
       Returns the reference_point in percent of the screen.
       """
       percent = float(self.query(':TIM:REF:PERC?'))
       self.settings.set('horizontal_reference_percent', percent)
       return percent

    def set_timebase_reference_percent(self, percent):
       """
       Sets the horizontal reference position to percent-of-screen location,
       from left to right

       :param percent: percent-of-screen location
       :type percent: float
       """
       self.write(':TIM:REF:PERC %lf' % full_scale_range)
       return self.get_timebase_reference_percent()


    def get_voltage_conversion_factors(self):
       """
       Read values which are used to convert data to voltage values.
       """
       fac = float(self.query(':WAVeform:YINCrement?'))
       origin = float(self.query(':WAVeform:YORigin?'))
       
       return origin, fac

    def get_time_conversion_factors(self):
       """
       Read values which are used to create time values.
       """
       fac = float(self.query(':WAVeform:XINCrement?'))
       origin = float(self.query(':WAVeform:XORigin?'))
       
       return origin, fac

    def get_x_unit(self):
       """
       Returns the X-axis units of the currently selected waveform source.
       """
       return self.query(':WAV:XUN?')

    def get_y_unit(self):
       """
       Returns the Y-axis units of the currently selected waveform source.
       """
       return self.query(':WAV:YUN?')

    def get_x_range(self):
       """
       Returns the X-axis range of the displayed waveform.
       """
       return float(self.query(':WAV:XRAN?'))

    def get_y_range(self):
       """
       Returns the Y-axis range of the displayed waveform.
       """
       return float(self.query(':WAV:YRAN?'))

    def acquire_data(self, channel = None, display_waveform = True):
       """
       The root level :DIGitize command is recommended for
       acquiring new waveform data. It initializes the
       oscilloscope's data buffers, acquires new data,
       and ensures that acquisition criteria are met before the
       acquisition is stopped. Note that the display is
       automatically turned off when you use this form of the
       :DIGitize command and must be turned on to view the
       captured data on screen.
       """
       if channel:
          self.write(':DIGitize CHAN%d' % channel)
          if display_waveform:
             self.display_channel(channel = channel)
       else:
          self.write(':DIGitize')

    def get_num_acquisitions(self):
       """
       Reads the number of acquired waveforms.
       """
       num = int(self.query(':WAV:COUNT?'))
       return num

    def set_num_averages(self, num_averages):
       """
       Sets the number of averages used in Averaging Acquisition.
       """
       self.write(':ACQ:AVERage:COUNt %d' % num_averages)
       return self.get_num_averages()

    def get_num_averages(self):
        """
        Returns the number of averages used in average-mode.
        """
        num_averages = int(self.query(':ACQ:AVER:COUN?'))
        self.settings.set('num_averages', num_averages)
        return num_averages

    def acquire_averaged_data(self, num_averages):
       """
       Acquire averaged waveforms.
       """
       self.query(':STOP;*OPC?')
       self.query(':TER?')
       self.set_num_averages(num_averages)
       self.acquire_data()
       num_acq = 0
       while num_acq < num_averages:
           time.sleep(0.1)
           num_acq = self.get_num_acquisitions()
       self.query(':STOP;*OPC?')

    def get_acquisition_mode(self):
        """
        Determines the acqusition mode.
        """
        mode = self.query(':ACQ:MODE?')
        self.settings.set('acquisition_mode', mode)
        return mode

    def set_acquisition_mode(self, mode = 'HRES'):
        """
        Sets the acquisition mode of the scope:
            HRES = Real time - High Resolution
            SEGH = Segmented - High Resolution
            ETIM = Equivalent time
            RTIM = Roll Mode
            PDET = Peak Detect 
            SEGM = Segmented - Normal
            SEGP = Segmented - Peak Detect
        """
        if not mode in self.ACQUISITION_MODES:
            print("%s not a valid mode. Valid modes are : \n")
            for m in self.ACQUISITION_MODES:
                print(m)
        else:
            self.write(':ACQ:MODE %s' % mode)
        print("Mode set to %s" % self.get_acquisition_mode())

    def get_num_segments_acquired(self):
        """
        Returns the number of segments in segmented mode.
        """
        return int(self.query(':WAV:SEGM:COUN?'))

    def get_num_segments_requested(self):
        """
        Returns the number of segments in segmented mode.
        """
        return int(self.query(':ACQ:SEGM:COUN?'))
   
    def set_num_segments(self, num):
        """
        Sets the number of segments that will be acquired
        """
        self.write(':ACQ:SEGM:COUN %d' % num)
        print("Number acquired segments set to: %d" % \
                self.get_num_segments_requested())

    def set_average_mode(self, enable = True):
        """
        Enable or disable the average mode.
        """
        if enable:
           self.write(':ACQ:AVER ON')
        else:
           self.write(':ACQ:AVER OFF')
        return self.get_average_mode()

    def get_average_mode(self):
        """
        Returns if average mode is switched on or off.
        """
        s = int(self.query(':ACQ:AVER?'))
        if s == 1:
            enabled = True
        else:
            enabled = False
        self.settings.set('average_mode', enabled)
        return enabled

    def define_average(self, channel, math, num_averages):
       """
       Defines the average function on channel as function #math.
       """
       if type(channel) == int:
          channel = 'CHAN%d' % channel
       elif type(channel) == str and len(channel) == 1:
          channel = 'CHAN%s' % channel
       else:
          if channel[:4] in ('CHAN', 'FUNC', 'WMEM'):
             pass

       self.write(':FUNCTION%d:AVERAGE %s,%d' % (math, channel, numavg))

    def define_spectral_mag(self, channel, math):
        """
        Defines the spectal-magnitude function on channel as math.
        """
        if type(channel) == int:
           channel = 'CHAN%d' % channel
        elif type(channel) == str and len(channel) == 1:
           channel = 'CHAN%s' % channel
        else:
           if channel[:4] in ('CHAN', 'FUNC', 'WMEM'):
              pass

        self.write(':FUNCTION%d:FFTMAGNITUDE %s' % (math, channel))

    def get_fft_resolution(self, math):
        """
        Returns the current resolution of the FFT function #math.
        """
        if type(math) == str:
           if math[:4] == 'FUNC':
              math = int(math.upper().replace('FUNC','').replace('TION',''))
                     
        res = self.query(':FUNC%d:FFT:RES?' % math)
        return float(res)

    def set_fft_center_frequency(self, math, frequency):
       """
       Sets the center frequency for the FFT when FFT is defined for the selected function.
       """
       if type(math) == str:
          if math[:4] == 'FUNC':
             math = int(math.upper().replace('FUNC','').replace('TION',''))
                     
       self.write(':FUNC%d:FFT:FREQ %lf' % (math, frequency))

    def set_gate(self, math, channel, time_start, time_stop):
       """
       This command defines a horizontal gating function of another waveform (similar to
       horizontal zoom). Measurements on horizontal gating functions are essentially gated measurements.
       """
       if type(math) == str:
          if math[:4] == 'FUNC':
             math = int(math.upper().replace('FUNC','').replace('TION',''))
                        
       self.write(':FUNC%d:GAT %s, %lf, %lf' % (math, channel, time_start, time_stop))


    def acquire_segments_multipulse(self, 
                                    filename, 
                                    num_segments,
                                    num_pulses,
                                    start = None, 
                                    size = None, 
                                    signal_channel = 1,
                                    probe_channel = None,
                                    probe_point = 1500
                                   ):
        """
        Transfers all the segments from scope to computer

        :param filename: if not None, spectra will be saved to this file
        :type filename: str
        :param num_segments: Number of segments to acquire
        :type num_segments: int
        :param num_pulses: Number of pulses to acquire
        :type num_pulses: int
        :param start: index of the first sample to save
        :type start: int
        :param size: number of samples to save
        :type size: int
        :param signal_channel: channel-id(s) to record
        :type signal_channel: int or list(int)
        :param probe_channel: channel-id of sync - trigger signal
        :type probe_channel: int
        :param probe_point: sample-index used to probe sync - trigger
        :type probe_point: int
        """
        if np.mod(num_segments, num_pulses) != 0:
            print("Number of segments as to be multiple of num_pulses!")
            print("Last pulses will not be used")
            return

        if probe_channel is not None:
            # Get marker point from p chanmel  
            self.set_data_source('CHAN%d' % probe_channel)
            data_probe = np.array(self.get_curve(start = probe_point, 
                                                 size = 1))[:num_pulses]
            print("Marker Levels", data_probe)
            # determine marked pulse
            marked_pulse = \
                    np.argmax( (data_probe > 0.5 * \
                                (np.max(data_probe)-np.min(data_probe))) \
                              == True )
            print("Marked: %d" % marked_pulse)
        else:
            marked_pulse = 0


        probe = {}
        probe_spec = {}
        # Make sure all segments will be transfered
        self.write('WAV:SEGM:ALL 1')

        # Transfer all segments for signal-channel
        self.set_data_source('CHAN%d' % signal_channel)

        xorigin, xfac = self.get_time_conversion_factors()
        yorigin, yfac = self.get_voltage_conversion_factors()
        segs_acquired = self.get_num_segments_acquired()
        num_avg = num_segments / num_pulses


        if start is None:
            start = 0

        if size:
          if not start:
            start = 0
          data = self.get_curve(start = start, size = size)
        elif start:
          data = self.get_curve(start = start)
        else:
          data = self.get_curve()

        # command will retrieve all the acquired segments
        data = np.split(np.array(data), segs_acquired)

        record_length = len(data[0])
        x = [xorigin + (start + i) * xfac for i in xrange(record_length)]

        # Create separate spectra for iterating pulses
        for i in xrange(num_pulses):
            # map data with marker to spec 0, following to 1, ...
            ii = np.mod(i - marked_pulse, num_pulses)
            probe_spec[i] = spectrum.FID(x, np.zeros(record_length))
            for j in xrange(num_avg):
                probe_spec[i].y += data[num_pulses * j + ii]
            probe_spec[i].y = yorigin + yfac / float(num_avg) * probe_spec[i].y

        # save the spectra if a filename is given
        if filename is not None:
            for i in probe_spec.keys():
                probe_spec[i].save('%s_probe%d' % (filename, i), 
                                   ftype = 'npy')
        return probe_spec




class Tektronix(Scope):
    """
    Class to control the Tektronix Scope 
    """
    def __init__(self, host = SCOPE_HOST, port = SCOPE_PORT):
        Scope.__init__(self, host = host, port = port)

    def display_waveform(self, display = True):
        """
        Turn the display of waveforms in the scope on or off.

        display : Boolean (True -> On, False -> Off)
        """
        if display:
            self.write('DISPLAY:WAVEFORM ON')
            print("Display has been turned on.")
        else:
            self.write('DISPLAY:WAVEFORM OFF')
            print("Display has been turned off.")

    def get_file_dir(self):
        """
        Returns the current directory.
        """
        return self.query('FILES:CWD?')

    def set_file_dir(self, dir_name):
        """
        Changes the current working directory.
        
        :param dir_name: new working directory
        """
        self.write('FILES:CWD "%s" % dir_name')
        return self.get_file_dir()
    
    def define_spectral_mag(self, channel, math):
        """
        Defines the spectal-magnitude function on channel as math.
        """
        if len(channel) == 1:
           channel = 'CH%d' % int(channel)

        self.write(':MATH%d:DEFINE "SpectralMag(%s)"' % (math, channel))
        
    def define_average(self, channel, math, numavg):
        """
        Defines the average function on channel as math.
        """
        if type(channel) == int:
           channel = 'CH%d' % channel
        elif type(channel) == str and len(channel) == 1:
           channel = 'CH%s' % channel
        else:
           pass

        self.write(':MATH%d:NUMAV %d' % (math, numavg))
        self.write(':MATH%d:DEFINE "Avg(%s)"' % (math, channel))

    def get_num_acquisitions(self):
        """
        Queries the number of acquisitions.
        """
        return int(self.query('*WAI;ACQUIRE:NUMACQ?'))

    def set_data_source(self, source):
        """
        Sets the data source to CH1-4, MATH1-4
        """
        if source in ("CH1", "CH2", "CH3", "CH4", "MATH1", "MATH2", "MATH3", "MATH4"):
            self.write(':DATA:SOUR %s' % source)
        else:
            print("Source has to be one of CH1-4 or MATH1-4")
        return self.query(':DATA:SOUR?')
     
    def get_data_source(self):
        """
        Queries the data source (CH1-4, MATH1-4,...).
        """
        return self.query(':DATA:SOUR?')

    def get_encoding(self):
        """
        Queries the encoding for the data transfer.
        """
        self.data_encoding = self.query(':DATA:ENCDG?')
        return self.data_encoding

    def set_encoding(self, encoding = 'FPBINARY'):
        """
        Sets the encoding for data transfer from the scope (Default: FPBINARY)
        """
        if not encoding in ('ASCII', 'FPBINARY'):
           print("Encoding has to be one of 'ASCII', 'FPBINARY', ...")
           return
        self.write(':DATA:ENCDG %s' % encoding)
        enc = self.get_encoding()
        print("Encoding set to %s" % enc)
     
    def get_curve(self):
        """
        Queries the data for the selected source from the scope.
        """
        data = self.query(':CURVE?')
        esr = self.query('*ESR?')
        if self.data_encoding == 'ASCII':
           data = np.array([float(i) for i in data.split(',')])
        return data

    def get_next_curve(self):
        """
        Queries unique data for the selected source from the scope.
        """
        data = self.query(':CURVEN?')
        esr = self.query('*ESR?')
        if self.data_encoding == 'ASCII':
           data = np.array([float(i) for i in data.split(',')])
        return data

    def get_samplerate(self):
        """
        Queries the current samplerate.
        """
        self.samplerate = float(self.query('HOR:MODE:SAMPLER?'))
        return self.samplerate

    def set_samplerate(self, samplerate):
        """
        Sets the samplerate.
        """
        # select manual mode in order to be able to change the samplerate
        self.write(':HOR:MODE MANUAL')
        self.write(':HOR:MODE:SAMPLER %lf' % samplerate)
        self.write(':HOR:MODE CONST')
        sr = self.get_samplerate()
        print("Samplerate set to %lf GSa/s" % (sr / 1.0e9))

    def get_recordlength(self):
        """
        Queries the recordlength.
        """
        return int(self.query(':HOR:MODE:RECO?'))

    def get_acquisition_duration(self):
        """
        Queries the duration of acquisition.
        """
        duration = float(self.query(':HOR:ACQDURATION?'))
        return duration

    def set_horizontal_scale(self, scale):
        """
        Sets the horizontal scale in time per division.
       
        :param scale: time per division in seconds
        :type scale: float
        """
        self.write(':HOR:MODE:SCA %lf' % scale)
        acqduration = self.get_acquisition_duration()
        recordlength = self.get_recordlength()
        print('Duration: %lf s \nRecordlength: %d' % (acqduration, recordlength))

    def display_curve(self, source, shown):
        """
        Controls the display of a curve (on or off).
        
        :param source: channel which is controlled (CH1-4, MATH1-4,...)
        :type source: str
        :param shown: True if channel shall be displayed otherwise False
        :type shown: boolean
        """
        on = 0
        if shown:
           on = 1
        self.write(':SELECT:%s %d' % (source, on))

    def get_waveform_pre(self):
        """
        Queries the waveform preamble.
        """
        return self.query(':WFMO?')

    def set_transfer_range(self, start = None, stop = None):
        """
        Sets the range of points within a waveform that will be transfered.
        If not specified range will start with first and end with the last
        recorded point.
        """
        if not start:
           start = 1
        recolength = self.get_recordlength()
        if not stop or stop > recolength:
           stop = recolength
        self.write(":DAT:STAR %d" % start)
        self.write(":DAT:STOP %d" % stop)

    def get_transfer_range(self):
        """
        Query the point range for data transfer.
        """
        first = int(self.query(':DAT:STAR?'))
        last = int(self.query(':DAT:STOP?'))
        return first, last

    ######################################################
    # FAST FRAME
    ######################################################
    def get_fast_frame_source(self):
        """
        Get the selected source of the fast frame mode
        """
        return self.query(':HOR:FAST:SELECTED:SOU?')

    def set_fast_frame_source(self, source):
        """
        Sets the selected source of the fast frame mode.

        :param source: Source (CH1-4, MATH1-4)
        :type source: str
        """
        if source not in ('CH1', 'CH2', 'CH3', 'CH4', 'MATH1', 'MATH2', 'MATH3', 'MATH4'):
           print("Source has to be one of CH1-4 or Math1-4.")
           return
        self.write(':HOR:FAST:SELECTED:SOU %s' % source)
        print("Selected source: %s" % self.get_fast_frame_source())

    def get_num_frames(self):
        """
        Queries the number of frames set in the fast frame mode
        """
        self.num_frames = int(self.query(':HOR:FAST:COUN?'))
        return self.num_frames

    def set_num_frames(self, num_frames):
        """
        Sets the number of frames.
        """
        self.write(':HOR:FAST:COUN %d' % num_frames)
        self.get_num_frames()
        print("Number of frames set to %d" % self.num_frames)

    def get_selected_frame(self):
        """
        Query the selected frame of the fast frame mode.
        """
        source = self.get_data_source()
        self.selected_frame = int(self.query(':HOR:FAST:SELECTED:%s?' % source))
        return self.selected_frame

    def select_last_frame(self):
        """
        Selects the last frame.
        """
        source = self.get_data_source()
        last_frame = self.get_num_frames()
        self.write(':HOR:FAST:SELECTED:%s %d' % (source, last_frame))
        self.get_selected_frame()
        print("Selected frame %d of %d frames" % (self.selected_frame, last_frame))

    def get_summary_frame_mode(self):
        """
        Query the summary frame mode.
        """
        return self.query(':HOR:FAST:SUMF?')

    def set_summary_frame_mode(self, mode = 'AVERAGE'):
        """
        Set the summary frame mode (default to average all frames into summary frame)
        """
        self.write(':HOR:FAST:SUMF %s' % mode)
        # set math on only the summary frame
        self.set_math_on_summaryframe(True)

        print("Summary frame mode: %s" % self.get_summary_frame_mode())

    def set_math_on_summaryframe(self, enabled = True):
        """
        Sets the math on only the summary frame if enabled.
        """
        if enabled:
            self.write(':HOR:FAST:SINGLEF 1')
        else:
            self.write(':HOR:FAST:SINGLEF 0')

    def get_fast_frame_state(self):
        """
        Queries wethter the fast frame mode is enabled.
        """
        fast_frame_state = int(self.query(':HOR:FAST:STATE?'))
        if fast_frame_state == 1:
           self.fast_frame_state = True
        else:
           self.fast_frame_state = False
        return self.fast_frame_state

    def set_fast_frame(self, enable = True):
        """
        Set the fast frame mode.
        
        :param enable: If true, fast frame is switched on
        :type enable: Boolean
        """
        if enable:
            self.write(':HOR:FAST:STATE 1')
        else:
            self.write(':HOR:FAST:STATE 0')

        self.get_fast_frame_state()
        if self.fast_frame_state:
             print("Fast Frame mode is switched on")
        else:
             print("Fast Frame mode is switched off")

    def get_frame_for_transfer(self):
        """
        Query selected frame for data transfer.
        """
        start = int(self.query(':DAT:FRAMESTAR?'))
        stop = int(self.query(':DAT:FRAMESTOP?'))
        if start == stop:
           print("Frame %d selected for transfer" % start)
           return start
        else:
           print("Frames from %d to %d selected for data transfer" % (start, stop))
           return start, stop
        
    def select_frame_for_transfer(self, frame = None):
        """
        select frame for data transfer (default = last-frame)
        """
        self.get_num_frames()
        if not frame:
           frame = self.num_frames
        if frame > self.num_frames:
           frame = self.num_frames
           print("frame number exceeds number of frames. Set to last frame.")
        self.write(':DAT:FRAMESTAR %d' % frame)
        self.write(':DAT:FRAMESTOP %d' % frame)

