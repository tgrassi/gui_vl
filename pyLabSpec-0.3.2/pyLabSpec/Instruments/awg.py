#!/usr/bin/env python
# -*- coding: utf-8 -*-
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

import numpy as np

if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from settings import *
if sys.version_info[0] == 3:
    from .instrument import *
else:
    from instrument import *
import Simulations.waveformbuilder as wb

if sys.version_info[0] == 3:
    xrange = range

BUFFERSIZE = 8192

# CONTROL-BITS FOR THE STABI-SYSTEM (Sequence-System)
DATA = 0
COMMAND = 1
AUTO = 0
CONDITIONAL = 1
REPEAT = 2
SINGLE = 3
ENABLE = 1
DISABLE = 0
ON = 1
OFF = 0
IDLE_DELAY = 1
CONFIG = 2

# function to convert integer value into signed binary
tobin = lambda x, count=8: "".join(map(lambda y:str((x>>y)&1), range(count-1, -1, -1)))

class AWG(object):
    """
    Class to control the Arbitrary Waveform Generator.
    """
    def __init__(self, host = AWG_HOST, port = AWG_PORT, com = 'TCPIP'):
        try:
            self.socket = InstSocket(com, host = host, port = port)
        except:
            print("Could not connect to AWG")
            return

        self.settings = Settings()
        self.identity = self.identify()
        self.settings.set('identity', self.identity)
        self.read_settings()
        self.print_settings()

    # -----------------------------------------------------------
    # IO - Commands (Communication)
    # -----------------------------------------------------------
    def query(self, string):
        return self.socket.query(string)

    def write(self, string):
        self.socket.write(string)

    def read(self):
        return self.socket.readall()

    def identify(self):
        return self.query('*IDN?')

    def clear_error_queue(self):
        """
        Clear the event register and clear the error queue.
        """
        self.write('*CLS')

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
    
    def wait_until_command_completes(self):
        """
        Sends an "Operation Complete" command. Other commands cannot be executed until this command
        completes.
        """
        return self.query('*OPC?') 

    def command_completed(self):
        """
        Check wether the previous commands have been completed. 
        """
        if self.query('*OPC?') == '1':
           return True
        else:
           return False

    # -----------------------------------------------------------------
    # Commands to manage settings (load, save, apply, ...)
    # -----------------------------------------------------------------
    def apply_settings(self, **kwds):
        """
        Applies the settings specified by the keywords:

            direct_mode
            samplerate
            oscillator_frequency
            reference_oscillator
            current_mode
            selected_out_ch1
            selected_out_ch2
            output_voltage_ch1
            output_voltage_ch2
            amp_output_ch1
            amp_output_ch2
            trigger_mode_ch1
            trigger_mode_ch2
            trigger_frequency
            trigger_source
            arming_mode_ch1
            arming_mode_ch2

        """
        for ck in kwds.keys():
            if ck == 'settings':
                self.settings.apply_settings(kwds[ck])
            else:
                self.settings.set(ck, kwds[ck])

        self.select_direct_mode(1, self.settings.get('direct_mode'))
        self.select_direct_mode(2, self.settings.get('direct_mode'))
        self.set_samplerate(self.settings.get('samplerate'))
        self.set_oscillator_frequency(self.settings.get('oscillator_frequency'))
        try:
            self.set_reference_oscillator(self.settings.get('reference_oscillator'))
        except:
            print("Could not set reference oscillator to %s" % \
                    self.settings.get('reference_oscillator'))

        self.set_current_mode(channel = 1, mode =
                              self.settings.get('current_mode'))
        self.set_current_mode(channel = 2, mode =
                              self.settings.get('current_mode'))
        # output channels
        self.select_output(1, self.settings.get('selected_out_ch1'))
        self.select_output(2, self.settings.get('selected_out_ch2'))        
        self.set_output_voltage(1, self.settings.get('output_voltage_ch1'))
        self.set_output_voltage(2, self.settings.get('output_voltage_ch2'))
        self.set_amp_output(1, self.settings.get('amp_output_ch1'))
        self.set_amp_output(2, self.settings.get('amp_output_ch2'))

        # marker outputs
        self.set_marker_amplitude('SYNC1', self.settings.get('sync1_marker_amplitude'))
        self.set_marker_amplitude('SYNC2', self.settings.get('sync2_marker_amplitude'))
        self.set_marker_amplitude('SAMP1', self.settings.get('samp1_marker_amplitude'))
        self.set_marker_amplitude('SAMP2', self.settings.get('samp2_marker_amplitude'))
        self.set_marker_offset('SYNC1', self.settings.get('sync1_marker_offset'))
        self.set_marker_offset('SYNC2', self.settings.get('sync2_marker_offset'))
        self.set_marker_offset('SAMP1', self.settings.get('samp1_marker_offset'))
        self.set_marker_offset('SAMP2', self.settings.get('samp2_marker_offset'))

        # Trigger Mode
        self.set_trigger_mode(1, self.settings.get('trigger_mode_ch1'))
        self.set_trigger_mode(2, self.settings.get('trigger_mode_ch2'))
        self.set_trigger_frequency(self.settings.get('trigger_frequency'))
        self.set_trigger_source(source = self.settings.get('trigger_source'))

        self.set_arming_mode(1, self.settings.get('arming_mode_ch1'))
        self.set_arming_mode(2, self.settings.get('arming_mode_ch2'))

    def read_settings(self):
        """
        Queries the current settings from the instruments.
        """
        
        self.get_samplerate()
        self.get_selected_output(1)
        self.get_selected_output(2)
        self.read_output_voltage(1)
        self.read_output_voltage(2)
        self.get_amp_output(1)
        self.get_amp_output(2)
        self.get_current_mode()
        self.get_direct_mode()
        self.get_defined_segments()
        self.get_selected_segment()
        # Trigger mode
        self.read_trigger_mode(1)
        self.read_trigger_mode(2)
        self.query_trigger_frequency()
        self.query_trigger_source()
        self.query_arming_mode(1)
        self.query_arming_mode(2)
        self.get_oscillator_frequency()
        self.get_reference_oscillator()

        self.check_reference_oscillator('INT')
        self.check_reference_oscillator('EXT')
        self.check_reference_oscillator('AXI')

        # marker outputs
        self.get_marker_amplitude('SYNC1')
        self.get_marker_amplitude('SYNC2')
        self.get_marker_amplitude('SAMP1')
        self.get_marker_amplitude('SAMP2')
        self.get_marker_offset('SYNC1')
        self.get_marker_offset('SYNC2')
        self.get_marker_offset('SAMP1')
        self.get_marker_offset('SAMP2')

    def print_settings(self):
        """
        Prints the current settings to the standard output.
        """
        print("Samplerate: %s" % self.settings.get('samplerate'))
        print("Current Mode: %s" % self.settings.get('current_mode'))
        print("Direct Mode: %s" % self.settings.get('direct_mode'))
        print("\n")
        print("TRIGGER:")
        print("Frequency: %lf" % self.settings.get('trigger_frequency'))
        print("Source: %s " % self.settings.get('trigger_source'))
        print("\n")
        print("CHANNEL 1: ")
        print("Selected output: %s" % self.settings.get('selected_out_ch1'))
        print("Output Status: %s" % self.settings.get('amp_output_ch1'))
        print("Output Voltage: %lf" % self.settings.get('output_voltage_ch1'))
        print("Trigger Mode: %s" % self.settings.get('trigger_mode_ch1'))
        print("Arming Mode: %s" % self.settings.get('arming_mode_ch1'))
        print("\n")
        print("CHANNEL 2: ")
        print("Selected output: %s" % self.settings.get('selected_out_ch2'))
        print("Output Status: %s" % self.settings.get('amp_output_ch2'))
        print("Output Voltage: %lf" % self.settings.get('output_voltage_ch2'))
        print("Trigger Mode: %s" % self.settings.get('trigger_mode_ch2'))
        print("Arming Mode: %s" % self.settings.get('arming_mode_ch2'))
        print("\n")
        print("Reference oscillator: ")
        print("Oscillator frequency: %lf" % self.settings.get('oscillator_frequency'))
        print("Reference Oscillator: %s" % \
                self.settings.get('reference_oscillator'))
        print("Ext-Reference available: %s" % \
                self.settings.get('reference_oscillator_EXT_available'))
        print("Int-Reference available: %s" % \
                self.settings.get('reference_oscillator_INT_available'))
        print("Axi-Reference available: %s" % \
                self.settings.get('reference_oscillator_AXI_available'))

    def read_current_settings(self):
        """
        Query the instrument and return a block of data containing the current settings.
        """
        return self.query('*LRN?')


    ################################################################
    # Methods to control settings of the AWG
    ################################################################
    def set_samplerate(self, frequency):
        """
        Sets the sample frequency.

        :param frequency: Sample frequency in GSa/s
        :type frequency: float
        :returns: the new sample frequnency in Hz
        """
        self.write(':FREQ:RAST %lf' % frequency)
        return self.get_samplerate()

    def get_samplerate(self):
        """
        Reads the sample frequency.
        returns frequency in Hz
        """
        sr = float(self.query(':FREQ:RAST?'))
        self.settings.set('samplerate', sr)
        return sr

    def get_current_mode(self, channel = 1):
        """
        Determenines the current mode of the AWG (arbitrary waveform segment, sequence or scenario).
        """
        mode = self.query(":FUNC%d:MODE?" % channel)
        self.settings.set('current_mode', mode)
        return mode

    def set_current_mode(self, channel = None, mode = 'ARB'):
        """
        Sets the mode of the AWG (ARB = arbitrary waveform segment, STS = sequence, STSC = scenario).
        """
        if mode not in ['ARB', 'STS', 'STSC']:
            print("You have to select one of 'ARB', 'STS', 'STSC'")
            return
        if channel:
            self.write(":FUNC1:MODE %s" % mode)
            self.write(":FUNC2:MODE %s" % mode)
        else:
            self.write(":FUNC%d:MODE %s" % (channel, mode))

        return self.get_current_mode()

    def select_direct_mode(self, channel = 1, mode = 'SPEED'):
        """
        Set the waveform output mode (precission: 14bit, speed: 12bit, interpolated (DUC-option).
        """
        if mode.upper() not in ('SPEED', 'PRECISION', 'X3', 'X12', 'X24', 'X48'):
            print("Mode unkown. Please select one of the following 'SPEED', 'PRECISION', 'X3', 'X12', 'X24', 'X48'.")
            return
        if mode.upper() in ('SPEED', 'PRECISION'):
            self.write (":TRAC%d:DWID W%s" % (channel, mode.upper()[:2]))
        else:
            self.write (":TRAC%d:DWID INT%s" % (channel, mode.upper()))
        return self.get_direct_mode(channel)

    def get_direct_mode(self, channel = 1):
        """
        Query the waveform output mode.
        """
        direct_mode = self.query(":TRAC%d:DWID?" % channel)
        if direct_mode == 'WSP':
            mode = 'SPEED'
        elif direct_mode == 'WPR':
            mode = 'PRECISION'
        else:
            mode = direct_mode
        self.settings.set('direct_mode', mode)
        return mode

    #-------------------------------------------------------------------
    # clock commands
    #-------------------------------------------------------------------
    def set_sample_clock(self, output= 'INT'):
        """
          Select wich clock source is routed to the SCLK output
          INT the internally generated clock
          EXT the clock that is received at SCLK input
        """
        if output.upper() not in ('INT', 'EXT'):
           print("Please choose one of the following: INT, EXT")
           return

        self.write(':OUTP:SCLK:SOUR %s' % (output))


    #------------------------------------------------------------------------------------------
    # Oscillator commands
    #------------------------------------------------------------------------------------------
    def get_reference_oscillator(self):
        """
        Queries the selected reference oscillator source.
        """
        source = self.query(':ROSC:SOUR?')
        self.settings.set('reference_oscillator', source)
        return source
    
    def check_reference_oscillator(self, source = 'EXT'):
        """
        Checks if the reference clock source is available
        """
        self.write(":ROSC:SOUR:CHEC? %s" % source)       
        available = int(self.read())
        if available == 1:
            available = True
        else:
            available = False

        self.settings.set('reference_oscillator_%s_available' % source,
                           available)
        return available

    def set_reference_oscillator(self, source = 'INT'):
        """
        Sets the reference oscillator source (EXT, INT, AXI)
        """
        if self.check_reference_oscillator(source = source):
            self.write(":ROSC:SOUR %s" % source)
        else:
            print("Reference oscillator %s is not available." % source)

        return self.get_reference_oscillator()

    def get_oscillator_frequency(self):
        """
        Queries the expected frequency of the external reference oscillator
        """
        freq = float(self.query(":ROSC:FREQ?"))
        self.settings.set('oscillator_frequency', freq)
        return freq

    def set_oscillator_frequency(self, freq = 10000000):
        # make sure that the reference oscillator is already set
        source = self.settings.get('reference_oscillator')
        ref = self.set_reference_oscillator(source = source)

        # set new frequency
        self.write(":ROSC:FREQ %d" % freq)
        freq = self.get_oscillator_frequency()
        #ref = self.get_reference_oscillator()
        avail = self.check_reference_oscillator(ref)
        print("Reference oscillator frequency set to %lf" % freq)
        if not avail:
            print("WARNING: Reference oscillator %s not available" % ref)

    #-----------------------------------------------------------------------------------------
    # Noise floor commands
    #-----------------------------------------------------------------------------------------
    def enable_noise_floor_reduction(self):
        """
        Switch on 'Reduced Noise Floor' feature.
        """
        self.write(':ARM:RNO ON')

    def disable_noise_floor_reduction(self):
        """
        Switch off 'Reduced Noise Floor' feature.
        """
        self.write(':ARM:RNO OFF')

    def query_noise_floor_reduction(self):
        """
        Queries the state of the reduced noise floor feature.
        """
        self.query(':ARM:RNO?')

    #-----------------------------------------------------------------------------------------
    # SIGNAL GENERATION
    #-----------------------------------------------------------------------------------------

    def start_immediate(self, channel = 1):
        """
        Start signal generation on a channel. If channels are coupled, both channels are started.
        """
        self.write(':INIT:IMM%d' % channel)

    def stop_immediate(self, channel = 1):
        """
        Stop signal generation on a channel. If channels are coupled, both channels are started.
        """
        self.write(':ABOR%d' % channel)

    def set_output_voltage(self, channel, volt):
        self.write('VOLT%d %lf' % (channel,volt))
        return self.read_output_voltage(channel)

    def read_output_voltage(self, channel):
        out = float(self.query('VOLT%d?' % channel))
        self.settings.set('output_voltage_ch%d' % channel, out)
        return out

    #-------------------------------------------------------------------------------------------
    # OUTPUT Subsystem
    #-------------------------------------------------------------------------------------------
    def select_output(self, channel, output = 'AC'):
        """
        Select the output path: AC, DC or DAC.
        """
        if output.upper() not in ('AC', 'DC', 'DAC'):
           print("Please choose one of the following: AC, DC, DAC")
           return

        self.write(':OUTP%d:ROUT %s' % (channel, output))
        return self.get_selected_output(channel)

    def get_selected_output(self, channel):
        """
        Returns the selected output path for channel: AC, DC or DAC.

        :param channel: Channel
        :type channel: int

        returns string
        """
        out = self.query(':OUTP%d:ROUT?' % channel)
        self.settings.set('selected_out_ch%d' % channel, out)
        return out

    def set_amp_output(self, channel, status = 'OFF'):
        """
        Switch the AMP OUT from the AWG  on or off
        OFF|ON|0|1
        """
       #if output.upper() not in ('ON', 'OFF'):
       #   print("Please choose one of the following: ON, OFF")
       #   return

        self.write(':OUTP%d:NORM %s' % (channel, status))
        return self.get_amp_output(channel)

    def get_amp_output(self, channel):
        """
        Returns the output status (ON/OFF) of the current output.

        :param channel: Channel
        :type channel: int

        returns status
        """
        out = self.query(':OUTP%d:NORM?' % channel)
        self.settings.set('amp_output_ch%d' % channel, out)
        return out
 

    #------------------------------------------------------------------------------------------
    # TRIGGER COMMANDS
    #------------------------------------------------------------------------------------------

    def set_arming_mode(self, channel = 1, mode = 'self'):
        """
        Set the arming mode ('SELF' or 'ARMed')
        """
        if mode.upper() not in ('SELF', 'ARM', 'ARMED'):
           # raise error
           print('Mode %s unknown: Should be "SELF" or "ARMed"' % mode)
           return

        self.write(':INIT:CONT%d:ENAB %s' % (channel, mode))
        return self.query_arming_mode(channel = channel)

    def query_arming_mode(self, channel = 1):
        """
        Query the arming mode.
        """
        mode = self.query(':INIT:CONT%d:ENAB?' % channel)
        self.settings.set('arming_mode_ch%d' % channel, mode)
        return mode

    def set_continuous_mode(self, channel = 1, status = 'ON'):
        """
        Set or query the continuous mode. This command must be used together with INIT:GATE[1|2] to set the trigger mode.
        If continuous mode and gate mode are off, the trigger mode is 'triggered'; If only continuous mode is off trigger mode
        is 'gated'. If continuous mode is on. Trigger mode is 'automatic' and the value of gate mode is not relevant.
        """
        if status.upper() not in ('ON', 'OFF'):
           print('Status has to be "ON" or "OFF"')
           return

        self.write(':INIT:CONT%d:STAT %s' % (channel, status))

    def read_continuous_mode(self, channel = 1):
        """
        Queries wether continous mode is switched on or off
        """
        return int(self.query(':INIT:CONT%d:STAT?' % channel))

    def set_gate_mode(self, status = 'ON'):
        """
        Set or query the gate mode. This command must be used together with the continuous mode. 
        If continuous mode is off, the trigger mode is 'gated'.
        """
        if status.upper() not in ('ON', 'OFF'):
           print('Status has to be "ON" or "OFF"')
           return

        self.write(':INIT:GATE1:STAT %s;:INIT:GATE2:STAT %s' % (status, status))

    def read_gate_mode(self, channel = 1):
        """
        Queries wether gate mode is switched on or off
        """
        return int(self.query(':INIT:GATE%d:STAT?' % channel))

    def set_trigger_mode(self, channel = 1, mode = 'Continuous'):
        """
        Set trigger mode (gate + continuous mode).

        :param channel: AWG - Channel (1 or 2)
        :param mode: One of the following ('Continuous', 'Gated', 'Triggered')
        """
        if mode.upper() not in ('CONTINUOUS', 'GATED', 'TRIGGERED'):
           print('Mode %s is unkown. It has to be "Continuous", "Gated" or "Triggered"' % mode)
           return

        if mode.upper() == 'CONTINUOUS':
           self.set_continuous_mode(channel, status = 'ON')
           return
        else:
           self.set_continuous_mode(channel, status = 'OFF')

        if mode.upper() == 'GATED':
           self.set_gate_mode(status = 'ON')
        else:
           self.set_gate_mode(status = 'OFF')

    def read_trigger_mode(self, channel = 1):
        """
        Queries the trigger mode.
        """
        cont = self.read_continuous_mode(channel)
        gate = self.read_gate_mode(channel)
        if cont:
           mode = 'Continuous'
        elif gate:
           mode = 'Gated'
        else:
           mode = 'Triggered'
        self.settings.set('trigger_mode_ch%d' % channel, mode)
        return mode

    def set_trigger_source(self, source = 'INT'):
        """
        Sets the trigger source to external (EXT) or internal (INT).
        """
        if source.upper() not in ('INT', 'EXT'):
           print('Source %s unkown. Should be "INT" or "EXT".' % source)
        self.write(':ARM:TRIG:SOUR %s' % source.upper() )
        return self.query_trigger_source()

    def query_trigger_source(self):
        """
        Queries the trigger source.
        """
        source = self.query(':ARM:TRIG:SOUR?')
        self.settings.set('trigger_source', source)
        return source

    def set_trigger_frequency(self, frequency = 1000.0):
        """
        Sets the frequency of the internal trigger source.

        :param frequency: Frequency in Hz
        :type frequency: float
        """
        self.write(':ARM:TRIG:FREQ %lf' % frequency )
        return self.query_trigger_frequency()

    def query_trigger_frequency(self):
        """
        Queries the frequency of the internal trigger source.
        """
        freq = float(self.query(':ARM:TRIG:FREQ?'))
        self.settings.set('trigger_frequency', freq)
        return freq

    def set_marker_amplitude(self, marker, amplitude = 0.5):
        """
        Sets the amplitude of a marker.

        :param marker: String that idenfies the marker \
                (SYNC1, SYNC2, SAMP1, SAMP2)
        :type marker: string
        :param amplitude: Peak-to-Peak Amplitude in Volt
        :type amplitude: float
        """
        marker = marker.upper()
        if marker not in ('SYNC1', 'SYNC2', 'SAMP1', 'SAMP2'):
            print("Marker unkown. Valid markers are: \
                    'SYNC1', 'SYNC2', 'SAMP1', 'SAMP2'")
            return
        channel = int(marker[-1])
        self.write(':MARK%d:%s:VOLT:AMPL %g' % (channel, marker[:-1], amplitude))
        return self.get_marker_amplitude(marker)

    def get_marker_amplitude(self, marker):
        """
        Queries the marker amplitude.

        :param marker: String that idenfies the marker \
                (SYNC1, SYNC2, SAMP1, SAMP2)
        :type marker: string

        :returns: Amplitude in Volt
        :rtype: float
        """
        marker = marker.upper()
        if marker not in ('SYNC1', 'SYNC2', 'SAMP1', 'SAMP2'):
            print("Marker unkown. Valid markers are: \
                    'SYNC1', 'SYNC2', 'SAMP1', 'SAMP2'")
            return
        channel = int(marker[-1])
        amplitude = float(self.query(':MARK%d:%s:VOLT:AMPL?' % (channel,
                                                                marker[:-1])))
        self.settings.set('%s_marker_amplitude' % marker.lower(), amplitude)
        return amplitude

    def set_marker_offset(self, marker, offset = 0.25):
        """
        Sets the offset of a marker.

        :param marker: String that idenfies the marker \
                (SYNC1, SYNC2, SAMP1, SAMP2)
        :type marker: string
        :param offset: Offset in Volt
        :type offset: float
        """
        marker = marker.upper()
        if marker not in ('SYNC1', 'SYNC2', 'SAMP1', 'SAMP2'):
            print("Marker unkown. Valid markers are: \
                    'SYNC1', 'SYNC2', 'SAMP1', 'SAMP2'")
            return
        channel = int(marker[-1])
        self.write(':MARK%d:%s:VOLT:OFFS %g' % (channel, marker[:-1], offset))
        return self.get_marker_offset(marker)

    def get_marker_offset(self, marker):
        """
        Queries the marker offset.

        :param marker: String that idenfies the marker \
                (SYNC1, SYNC2, SAMP1, SAMP2)
        :type marker: string

        :returns: Offset in Volt
        :rtype: float
        """
        marker = marker.upper()
        if marker not in ('SYNC1', 'SYNC2', 'SAMP1', 'SAMP2'):
            print("Marker unkown. Valid markers are: \
                    'SYNC1', 'SYNC2', 'SAMP1', 'SAMP2'")
            return
        channel = int(marker[-1])
        offset = float(self.query(':MARK%d:%s:VOLT:OFFS?' % (channel,
                                                             marker[:-1])))
        self.settings.set('%s_marker_offset' % marker.lower(), offset)
        return offset

    def force_trigger(self):
        """
        Sends start/begin event in trigger mode to a channel.
        """
        self.write(':TRIG:BEG')

    ###############################################
    # INSTRUMENT Subsystem
    ###############################################
    def switch_coupling(self, state = 'ON'):
        """
        Switch coupling on/off. If coulping is switched on, the fvalues of the channel
        where coupling switched on are taken. 
        """
        self.write(':INST:COUP:STAT %s' % status)

    def query_coupling(self):
        """
        Queries if channels are coupled.
        """
        return self.query(':INST:COUP:STAT?')


    ###############################################
    # File system commands
    ###############################################
    def query_catalog(self):
        """
        Query file system.
        """
        return self.query(':MMEM:CAT?')

    def cdir_default(self, path):
        r"""
        Changes the default directory for a mass memory file system.
        Default is C:\Users\Name\Documents (System.Environment.SpecialFolder.Personal)
        """
        self.write(':MMEM:CDIR "%s"' % path)

    def query_dir(self):
        """
        Queries the default directory.
        """
        return self.query(':MMEM:CDIR?')

    def copy_file(self, source, destination):
        """
        Copies a file.
        """
        self.write(':MMEM:COPY "%s", "%s"' % (source, destination))

    def del_file(self, filename):
        """
        Deletes a file.
        """
        self.write(':MMEM:DEL "%s"' % filename)

    def load_instrument_state(self, filename):
        """
        Current state of instrument is loaded from a file.
        """
        self.write(':MMEM:LOAD:CST "%s"' % filename)

    def store_instrument_state(self, filename):
        """
        Store current state of instrument to a file.
        """
        self.write(':MMEM.STOR:CST "%s" % filename')

    #--------------------------------------------------------------------
    # Methods to manage segments
    #--------------------------------------------------------------------
 
    def get_defined_segments(self, channel = 1):
        """
        The query returns a dictionary with the length of the segments and the segment-ids as keys. 
        :param channel: channel (1/2)
        :type channel: int
        """
        segs = self.query(":TRAC%d:CAT?" % channel).split(',')
        segments = {}
        for pos in xrange(len(segs)//2):
            segments[int(segs[2*pos])] = segs[2 * pos + 1]
        self.settings.set('defined_segments', segments)
        return segments

    def delete_segment(self, segment_id, channel = 1):
        """
        Delete segment.
                
        :param segment_id: Id of the segment 
        :type segment_id: integer
        :param channel: channel whose segment will be deleted.
        :type channel: integer
        """
        self.write(":TRAC%d:DEL %d" % (channel, segment_id))
    
    def define_segment(self, channel, length, seg_id = None, initial_value = 0):
        """
        Define the size of a waveform memory segment. 

        The length of a segment has to be a multiple of memory vector size (AWG_MIN_VECTORSIZE) and at least
        the minimum segment size (AWG_MIN_SEGMENTSIZE). 

        :param length: Length of the segment - Number of samples
        :type length: int
        :param seg_id: segment-Id. 
        :type seg_id: int
        """
        if length < AWG_MIN_SEGMENTSIZE:
            print("Minimum length is %d samples in speed mode. Length set to %d" % (AWG_MIN_SEGMENTSIZE, AWG_MIN_SEGMENTSIZE))
            length = AWG_MIN_SEGMENTSIZE

        if length % AWG_MIN_VECTORSIZE > 0:
            length = length + AWG_MIN_VECTORSIZE - length % AWG_MIN_VECTORSIZE
            print("Length has to be multiple of %d in speed mode. Length increased to %d." % ( AWG_MIN_VECTORSIZE, length))

        if seg_id:
            self.write(":TRAC%d:DEF %d,%d,%d" % (channel, seg_id, length, int(initial_value)))
        else:
            seg_id = self.query(":TRAC%d:DEF:NEW? %d,%d" % (channel, length, int(initial_value)))

        return seg_id

    def get_selected_segment(self):
        """
        Query selected segment.
        returns selected segment
        """
        seg = int(self.query(':TRAC:SEL?'))
        self.settings.set('selected_segment', seg)
        return seg

    def select_segment(self, segment_id):
        """
        Selects a segment.
        """
        self.write(":TRAC:SEL %d" % segment_id)
        return self.get_selected_segment()

    def get_marker_state(self):
        """
        Queries the marker state for the selected segment.
        Returns marker state (1 on, 0 off)
        """
        return self.query(":TRAC:MARK?")

    def set_marker_state(self, enabled = True):
        """
        Sets marker state for the selected segment.
        :param enabled: If marker should be enabled
        :type enabled: Boolean
        """
        if enabled:
           state = 1
        else:
           state = 0
        self.write(":TRAC:MARK %d" % state)
        return self.get_marker_state()

    ###################################################
    # UPLOAD WAVEFORMS
    ###################################################
    def upload_singletone(self, 
                          segment_id, 
                          freq, 
                          freq_lo = None, 
                          pulselength = None, 
                          delaylength = 0.0, 
                          phase = 0.0, 
                          rise_time = 0.0, 
                          fall_time = 0.0, 
                          samplemarker = True, 
                          syncmarker = True):
        """
        Uploads a single tone.

        :param segment_id: Id of the segment where the Singletone is uploaded to"
        :type segment_id: int
        :param freq: Frequency of the single tone in MHz.
        :type freq: float
        :param freq_lo: Frequency of the Local Oscillator (if AWG Signal is upconverted) in MHz.
        :type freq_lo: float
        :param pulselength: Length of the signal in microseconds.
        :type pulselength: float
        :param phase: Initial phase of the signal in Degree.
        :type phase: float
        """
        # Simulate the waveform and obtain i,q - datapoints
        signal = wb.SingleTone(freq, freq_lo = freq_lo, pulselength =
                               pulselength, phase = phase, samplerate =
                               self.samplerate, rise_time = rise_time,
                               fall_time = fall_time, delay = delaylength)
        i, q = signal.calc_iq_waveform()

        # delay will be only defined in the waveform in order to avoid problem
        # of trigger signals from markers that are too short !!
        #delaypoints = int(self.samplerate * delaylength * 1.0e-6)
        delaypoints = 0
        delay_data = np.zeros(delaypoints) 

        # upload waveforms to i and q channel
        self.upload_waveform(1, segment_id, i.data, delaydata = delay_data,
                             offset = 0, samplemarker = samplemarker, syncmarker
                            = syncmarker)
        self.upload_waveform(2, segment_id, q.data, delaydata = delay_data,
                             offset = 0, samplemarker = samplemarker, syncmarker
                            = syncmarker)

    def upload_chirp(self, segment_id, start_freq, stop_freq, 
                     freq_lo = None,
                     pulselength = None, 
                     delaylength = 0.0, 
                     phase = 0.0,
                     amplitude = 1.0,
                     rise_time = 0.0, 
                     fall_time = 0.0, 
                     samplemarker = True,
                     syncmarker = True):
        """
        Generates a chirped pulse and uploads its waveform to the awg.

        :param segment_id: Segment-Id of the uploaded waveform
        :type segment_id: int
        :param start_freq: Start-frequency of the chirped pulse in MHz.
        :type start_freq: float
        :param stop_freq: Stop frequency of the chirped pulse in MHz.
        :type stop_freq: float
        :param freq_lo: Frequency of the Local Oscillator (if AWG Signal is upconverted) in MHz.
        :type freq_lo: float
        :param pulselength: Length of the signal in microseconds.
        :type pulselength: float
        :param delay_length: Length of the initial delay in microseconds.
        :type delay_length: float
        :param phase: Initial phase of the signal in Degree.
        :type phase: float
        :param amplitude: max. rel. amplitude of the signal (0-1)
        :type amplitude: float
        :param rise_time: rise time of the pulse in microseconds.
        :type rise_time: float
        :param fall_time: fall time of the pulse in microseconds.
        :type fall_time: float
        :param samplemarker: Set samplemarker during pulse
        :type samplemarker: boolean
        :param syncmarker: set sync-marker during pulse
        :type syncmarker: boolean
        """
        signal = wb.Chirp(start_freq, stop_freq, 
                          freq_lo = freq_lo, 
                          pulselength = pulselength, 
                          phase = phase, 
                          amplitude = amplitude, 
                          samplerate = self.settings.samplerate, 
                          rise_time = rise_time, 
                          fall_time = fall_time, 
                          delay = delaylength)
        # i, q = signal.calc_iq_waveform()

        # delay will be only defined in the waveform!!
        # delaypoints = int(round(self.settings.samplerate * delaylength *
        #                         1.0e-6))
        delaypoints = 0

        delay_data = np.zeros(delaypoints) 

        samplemarker = [len(signal.i_signal.data)]

        # upload waveforms
        self.upload_waveform(1, segment_id, signal.i_signal.data, delaydata = delay_data,
                             offset = 0, samplemarker = samplemarker, syncmarker
                            = syncmarker)
        self.upload_waveform(2, segment_id, signal.q_signal.data, delaydata = delay_data,
                             offset = 0, samplemarker = samplemarker,
                             syncmarker = syncmarker)

        return signal

    def upload_waveform(self, 
                        channel, 
                        seg_id, 
                        sampledata, 
                        delaydata = [],
                        offset = 0, 
                        samplemarker = True, 
                        syncmarker = True, 
                        mode = 'SPEED'):
        """
        Uploads waveform data into the specified channel and segment.

        Old segments will be deleted. The datapoints will be scaled to full amplitude and are have to be in the interval [-1, 1]

        :param channel: AWG Channel 1/2
        :type channel: int
        :param seg_id: Segment-ID 
        :type seg_id: int
        :param sampledata: sample data [-1,1]
        :type sampledata: list of float
        :param offset: Offset position of the data (used to upload data in multiple chunks).
        :param samplemarker: position of samplemarkers 
        :type samplemarker: list of integer
        """
        if offset % AWG_MIN_VECTORSIZE != 0:
            print("Offset must fulfill the granularity requirement (multiple of AWG_MIN_VECTORSIZE)!")
            return

        if mode == 'SPEED':
            num_data_bits = 12
            bit23 = '00'
            factor = 2047
            shift = 16
        else:
            num_data_bits = 14
            bit23 = ''
            factor = 8188
            shift = 4

        marker = 0
        if syncmarker:
            marker += 2
        if samplemarker:
            marker += 1

        #--------------------------------------------------------------------------------------------------------
        # convert list of sample points into int16 signed integer format as required by the awg
        # and set markers to high for all samplepoints. Data points will be scaled to max. amplitude. 
        # (multiplication by 4/16 shifts the value in binary format two/four digits to the left and 3 adds '11' markers.
        data = np.array([np.round( factor * i) * shift + marker for i in sampledata], dtype = np.int16)
        data_delay = np.array([np.round( factor * i) * shift + marker for i in delaydata], dtype = np.int16)
        print('Len data: %d' % len(data))
        print('Len delay: %d' % len(data_delay))
        data = np.concatenate((data_delay, data), axis = 0)
        print('Len segment: %d' % len(data))
        # swap bytes in order to get little endian for TCPIP
        #        data = data.byteswap()
        #--------------------------------------------------------------------------------------------------------
        # transfer data in blocks of 4800 (multiple of AWG_MIN_VECTORSIZE) samples
        len_data = len(data)

        # make sure that at least the minimum number of samples is transfered
        if len_data < AWG_MIN_SEGMENTSIZE:
            print("Minimum length is %d samples in speed mode. %d zeroes appended to fulfill granularity requirement" % (AWG_MIN_SEGMENTSIZE, AWG_MIN_SEGMENTSIZE-len_data))
            data = np.concatenate((data, [0 for i in xrange(int(AWG_MIN_SEGMENTSIZE - len_data))]), axis = 0)
            len_data = len(data)

        # make sure that number of samples is a multiple of minimum vectorsize 
        print(len_data, len_data % AWG_MIN_VECTORSIZE)
        if len_data % AWG_MIN_VECTORSIZE > 0:
            data = np.concatenate((data, [0 for i in xrange(int(AWG_MIN_VECTORSIZE - len_data % AWG_MIN_VECTORSIZE))]), axis = 0)
            len_data = len(data)
            print(len_data)
            print("Length has to be multiple of %d in speed mode. Length increased to %d by filling zeroes." % ( AWG_MIN_VECTORSIZE, len_data))


        # delete segment if it exists
        if seg_id in self.get_defined_segments(channel = channel).keys():
            self.delete_segment(seg_id, channel = channel)

        # create new segment
        self.define_segment(channel, len_data, seg_id)

        # calculate number of blocks to transfer (VECTORSIZE is transfered per block)
        num_blocks = len_data // 4800 # AWG_MIN_VECTORSIZE
        num_blocks += 0 if (len_data % 4800) == 0 else 1
        # transfer the data
        for i in xrange( num_blocks ):
             # prepare the block with data
             block_data = ','.join(['%d' % d for d in data[i * 4800:(i + 1) * 4800]])
             cmd = ":TRAC%d:DATA %d,%d,%s" % (channel, seg_id, offset + i * 4800, block_data)
             self.write(cmd)
             # check if an error occured
             errors =  self.check_for_error()
             if errors:
                 for err in errors:
                     print(err[1])
                     print('Last command: \n%s' % cmd)
                 break


    ###################################################
    # SEQUENCE GENERATION AND MANIPULATION
    ###################################################
    def define_new_sequence(self, channel = 1, length = 1):
        """
        Defines a new sequence.
        :param channel: Channel 
        :type channel: int
        :param length: Number of segments to be defined for sequence
        :type length: int
        returns sequence_id
        """
        self.write(':SEQ%d:DEF:NEW? %d' % (channel, length))
        return int(self.read())

    def insert_segment_to_sequence(self, 
                                   channel,
                                   sequence_id, 
                                   row, 
                                   segment_id,
                                   loop_count = 1, 
                                   advanced_mode = 0 ,
                                   marker_enable = 1, 
                                   start_addr = 0, 
                                   stop_addr = 4294967295):
        """
        insert a segment into a sequence.
        :param sequence_id: id of the sequence
        :param row: sequence table entry [0-length of the defined sequence -1]
        :param segment_id: segment which will be inserted
        :param loop_count: number of segment loop iterations
        :param advance_mode: Specifies how the generator advances (0: AUTO, 1: CONDitional, 2: REPeat, 3:SINGLe)
        :param marker_enable: Enable markers of the segment (0: disabled, 1: enabled)
        :param start_addr: Address of the first sample within the segment.
        :param stop_addr: Address of the last sample within the segment.
        """
        self.write(":SEQ%d:DATA %d,%d,%d,%d,%d,%d,%d,%d" % (channel,
                                                            sequence_id, 
                                                            row,
                                                            segment_id,
                                                            loop_count,
                                                            advanced_mode,
                                                            marker_enable,
                                                            start_addr, 
                                                            stop_addr) )
        err = self.check_for_error()
        if err:
            print(err)

    def list_sequences(self, channel = 1):
        """
        Lists the defined sequences.
        
        :param channel: Channel for which the sequences are defined.
        :type channel: int

        Returns dictionary of sequences [sequence_id serves as key]
        """
        seq_dict = {}

        seqs = self.query(':SEQ%d:CAT?' % channel).split(',')       
        for i in xrange(len(seqs)//2):
            sequence_id = int(seqs[2*i])
            seq_length = int(seqs[2*i+1])
            seq_dict[sequence_id] = seq_length
        return seq_dict

    def get_sequence_data(self, channel, sequence_id, row = None):
        """
        Query the data of a specific sequence
        
        :param channel: Channel for which the sequence is defined
        :param sequence_id: Sequence - ID
        :type sequence_id: int
        :param row: Specific row in the sequence-table (all rows if None)
        :type row: int

        returns dict
        """
        # Get list with all defined sequences
        seq_list = self.list_sequences(channel = channel)

        # Check if sequence is defined
        if not sequence_id in seq_list.keys():
            return {}
        
        if row > seq_list[sequence_id] - 1:
            return {}

        if not row:
            row = 0
            length = seq_list[sequence_id]
        else:
            length = 1

        data = self.query(':SEQ%d:DATA? %d,%d,%d' % (channel,
                                                   sequence_id, 
                                                   row,
                                                   length)).split(',')
        seq_table = {}
        for i in xrange(length):
            entry = {}
            entry['seqment_id'] = data.pop(0)
            entry['loop_count'] = data.pop(0)
            entry['advance_mode'] = data.pop(0)
            entry['marker_enabled'] = data.pop(0)
            entry['start_sample'] = data.pop(0)
            entry['end_sample'] = data.pop(0)
            seq_table[i] = entry
        return seq_table

    def delete_all_sequences(self):
        """
        Deletes all defined sequences.
        """
        self.write(':SEQ:DEL:ALL')

    def delete_sequence(self, sequence_id):
        """
        Deletes one sequence.
        """
        self.write(':SEQ:DEL %d' % sequence_id)

    ##################################################
    # STABI SUBSYSTEM
    ##################################################
    # awg.query(':STAB:DATA? 0,6;*OPC?')
    # hex(1895825408)
    # 0x71000000
    # instr.tobin(9,4)
    # Out[23]: '1001'
#    awg.write(':STAB:DATA 0,0,1,1,1,0,95999')
#
# In [27]: awg.query(':STAB:DATA? 0,6;*OPC?')
# Out[27]: '0,1,1,1,0,95999;1'

    def select_stabi_sequence(self, sequence_idx, channel = 1):
        """
        Select the sequence (index of the first entry of the sequence)

        :param sequence_idx: Index of the first sequence
        :type sequence_idx: int
        """
        # select the sequence
        self.write(':STAB%d:SEQ:SEL %d' % (channel, sequence_idx))
        # select non-dynamic mode
        self.write(':STAB%d:DYN OFF' % channel)
        # select sequence mode
        self.write(':FUNC:MODE STS')

        err = self.check_for_error()
        if err:
            print(err)


    def get_stabi_selected_sequence(self, channel = 1):
        """
        Returns the index of the first entry of the currently selected sequence.
        """
        idx = int(self.query(':STAB%d:SEQ:SEL?' % channel))
        return idx

    def stabi_reset(self):
        """
        Resets all sequence table entries to default values.
        """
        self.write(':STAB:RES')
        err = self.check_for_error()
        if err:
            print(err)

    def create_stabi_control_parameter(self, **kwds):
        """
        Creates the control parameter for the STABI - SUBSYSTEM

        Accepts the following keywords:
            'command' (DATA|COMMAND)
            'end_marker_sequence' (ON|OFF)
            'end_marker_scenario' (ON|OFF)
            'init_marker_scequence' (ON|OFF)
            'marker_enable' (ON|OFF)
            'advancement_mode_sequence' (AUTO|CONDITIONAL|REPEAT|SINGLE)
            'advancement_mode_seqment' (AUTO|CONDITIONAL|REPEAT|SINGLE)
            'amplitude_table_init' (ON|OFF)
            'amplitude_table_increment' (ON|OFF)
            'frequency_table_init' (ON|OFF)
            'frequency_table_increment' (ON|OFF)

        Returns int
        """

        cmd = 0
        if 'command' in kwds.keys():
            cmd += kwds['command'] * 2**31
        if 'end_marker_sequence' in kwds.keys():
            cmd += kwds['end_marker_sequence'] * 2**30
        if 'end_marker_scenario' in kwds.keys():
            cmd += kwds['end_marker_scenario'] * 2**29
        if 'init_marker_sequence' in kwds.keys():
            cmd += kwds['init_marker_sequence'] * 2**28
        if 'marker_enable' in kwds.keys():
            cmd += kwds['marker_enable'] * 2**24
        if 'advancement_mode_sequence' in kwds.keys():
            cmd += kwds['advancement_mode_sequence'] * 2**20
        if 'advancement_mode_segment' in kwds.keys():
            cmd += kwds['advancement_mode_segment'] * 2**16
        if 'amplitude_table_init' in kwds.keys():
            cmd += kwds['amplitude_table_init'] * 2**15
        if 'amplitude_table_increment' in kwds.keys():
            cmd += kwds['amplitude_table_increment'] *2**14
        if 'frequency_table_init' in kwds.keys():
            cmd += kwds['frequency_table_init'] * 2**13
        if 'frequency_table_increment' in kwds.keys():
            cmd += kwds['frequency_table_increment'] * 2**12

        return cmd

    def parse_stabi_control_parameter(self, control_parameter):
        """
        Parses the control parameter for the STABI - SUBSYSTEM into dictionary.

        Uses the following keywords:
            'command' (DATA|COMMAND)
            'end_marker_sequence' (ON|OFF)
            'end_marker_scenario' (ON|OFF)
            'init_marker_sequence' (ON|OFF)
            'marker_enable' (ON|OFF)
            'advancement_mode_sequence' (AUTO|CONDITIONAL|REPEAT|SINGLE)
            'advancement_mode_seqment' (AUTO|CONDITIONAL|REPEAT|SINGLE)
            'amplitude_table_init' (ON|OFF)
            'amplitude_table_increment' (ON|OFF)
            'frequency_table_init' (ON|OFF)
            'frequency_table_increment' (ON|OFF)

        Returns dict
        """

        cmd = {}
        cmd['command'] = control_parameter / 2**31
        control_parameter -= cmd['command'] * 2**31
        cmd['end_marker_sequence'] = control_parameter / 2**30
        control_parameter -= cmd['end_marker_sequence'] * 2**30
        cmd['end_marker_scenario'] = control_parameter / 2**29
        control_parameter -= cmd['end_marker_scenario'] * 2**29
        cmd['init_marker_sequence'] = control_parameter / 2**28
        control_parameter -= cmd['init_marker_sequence'] * 2**28
        cmd['marker_enable'] = control_parameter / 2**24
        control_parameter -= cmd['marker_enable'] * 2**24
        cmd['advancement_mode_sequence'] = control_parameter / 2**20
        control_parameter -= cmd['advancement_mode_sequence'] * 2**20
        cmd['advancement_mode_segment'] = control_parameter / 2**16
        control_parameter -= cmd['advancement_mode_segment'] * 2**16
        cmd['amplitude_table_init'] = control_parameter / 2**15
        control_parameter -= cmd['amplitude_table_init'] * 2**15
        cmd['amplitude_table_increment'] = control_parameter / 2**14
        control_parameter -= cmd['amplitude_table_increment'] * 2**14
        cmd['frequency_table_init'] = control_parameter / 2**13
        control_parameter -= cmd['frequency_table_init'] * 2**13
        cmd['frequency_table_increment'] = control_parameter / 2**12
        control_parameter -= cmd['frequency_table_increment'] * 2**12

        return cmd


    def create_stabi_table_entry(self, 
                                 sequence_table_idx, 
                                 channel = None,
                                 entry_type = DATA, 
                                 control_parameter = 0,
                                 **kwds):
        """
        Creates a table entry in the STABI subsystem. The entry is inserted for
        both channels if channel is not specified.

        :param sequence_table_idx: index of the table entry
        :type sequence_table_idx: int
        :param channel: Channel for which the entry is generated (Both if \
                not specified)
        :type channel: int
        :param entry_type: Type of the entry (DATA|IDLE_DELAY|CONFIG)
        :type entry_type: int
        :param control_parameter: Control parameter
        :type control_parameter: int
        """
        if entry_type == DATA:
            row = "%d,%d,%d,%d,%d,%d" % (control_parameter,
                                         kwds.get('sequence_loop_count', 1),
                                         kwds.get('segment_loop_count', 1),
                                         kwds.get('segment_id', 0),
                                         kwds.get('segment_start_offset', 0),
                                         kwds.get('segment_end_offset',
                                                  0xffffffff),
                                         )
        elif entry_type == IDLE_DELAY:
            min_delay = 10 * AWG_MIN_VECTORSIZE
            row = "%d,%d,%d,%d,%d,%d" % (control_parameter,
                                         kwds.get('sequence_loop_count', 1),
                                         0,
                                         kwds.get('idle_sample', 0),
                                         kwds.get('idle_delay', min_delay),
                                         0,
                                         )
        elif entry_type == CONFIG: 
            row = "%d,%d,%d,%d,%d,%d" % (control_parameter,
                                         kwds.get('sequence_loop_count', 1),
                                         1,
                                         kwds.get('segment_id', 0),
                                         kwds.get('segment_start_offset', 1),
                                         kwds.get('segment_end_offset',
                                                  0xffffffff),
                                         )
        else:
            row = ''
        
        if channel:
            self.write(':STAB%d:DATA %d, %s' % (channel, sequence_table_idx, row))
        else:
            self.write(':STAB%d:DATA %d, %s' % (1, sequence_table_idx, row))
            self.write(':STAB%d:DATA %d, %s' % (2, sequence_table_idx, row))
 

    def read_stabi_table_entry(self, sequence_table_idx, channel = 1, length = 1):
        """
        Read the STABI table entry at specified index.

        :param sequence_table_idx: Index of the entry
        :type sequence_table_idx: int
        :param channel: channel to be read (default = 1)
        :type channel: int
        :param length: number of entries to be read
        :type length: int
        """
        self.write(':STAB%d:DATA? %d, %d' % (channel, sequence_table_idx,
                                                   6 * length)
                        )
        ret = self.read()
        params = ret.split(',')
        params = [int(p) for p in params]
        table = []
        for i in xrange(len(params) // 6):
            entry = {}
            entry['control_parameter'] = params.pop(0)
            entry['sequence_loop_count'] = params.pop(0)
            if entry['control_parameter'] / 2**31 == DATA:
                entry['type'] = DATA
                entry['segment_loop_count'] = params.pop(0)
                entry['segment_id'] = params.pop(0)
                entry['segment_start_offset'] = params.pop(0)
                entry['segment_end_offset'] = params.pop(0)
            else:
                entry['command_code'] = params.pop(0)
                if entry['command_code'] == 0:
                    entry['entry_type'] = IDLE_DELAY
                    entry['idle_sample'] = params.pop(0)
                    entry['idle_delay'] = params.pop(0)
                    dummy = params.pop(0)
                else:
                    entry['entry_type'] = CONFIG
                    entry['segment_id'] = params.pop(0)
                    entry['segment_start_offset'] = params.pop(0)
                    entry['segment_end_offset'] = params.pop(0)
            table.append(entry)
        return table













    ####################################################################################
    # upload pulses
    #################################################################################### 

    def upload_qpsk_chirp(self, 
                          start_freq, 
                          stop_freq, 
                          pulse_length = 0.2,
                          delay_length = 0.0, 
                          amplitude = 1.0,
                          rise_time = 0.0005,
                          fall_time = 0.0005,
                          segments = [],
                          syncmarker_segment = True
                         ):
        """
        Creates and uploads four chirped pulse waveforms with initial phases of
        0,90,180,270 degree. This is usefull to separate sidebands.

        The first segment is dublicated with syncmarker enabled if the parameter
        'syncmarker_segment' is set to True

        :param start_freq: Start-Frequency of the chirped pulse in MHz.
        :type start_freq: float
        :param stop_freq: Stop-Frequency of the chirped pulse in MHz.
        :type stop_freq: float
        :param pulse_length: Length of the chirped pulse in microseconds.
        :type pulse_length: float
        :param delay_length: Initial delay in microseconds.
        :type delay_legnth: float
        :param amplitude: relative amplitude (0 - 1.0)
        :type amplitude: float
        :param rise_time: Rise-time of the pulse in microseconds.
        :type rise_time: float
        :param fall_time: Fall-time of the pulse in microseconds.
        :type fall_time: float
        :param segments: 4 (5) Segment-Ids to which the waveforms are written.
        :type segments: list
        :param syncmarker_segment: add a segment (0 degree) with syncmarker active.
        :type syncmarker_segment: boolean

        :returns: list of segment ids that have been created
        :rtype: list
        """
        # if segments are not specified then free segments are determined
        if len(segments) == 0:
            segs = self.get_defined_segments()
            i = max(segs)+1
            if syncmarker_segment:
                segments = [0,1,2,3,4]
            else:
                segments = [0,1,2,3]

            for i in xrange(1, max(segs)+2):
                if len(set(segments).intersection(segs)) == 0:
                    break
                else:
                    segments = [s+1 for s in segments]

        # Add a syncmarker segment (e.g. if the syncmarker is needed to assign
        # measured segments to the according signal segment.
        if syncmarker_segment:
            self.upload_chirp(segments[0],
                                      start_freq, 
                                      stop_freq, 
                                      pulselength = pulse_length,
                                      delaylength = delay_length, 
                                      amplitude = amplitude,
                                      rise_time=rise_time, 
                                      fall_time=fall_time,
                                      phase = 0.0, 
                                      samplemarker=True, 
                                      syncmarker=True)

        self.upload_chirp(segments[1], 
                                  start_freq, 
                                  stop_freq, 
                                  pulselength = pulse_length,
                                  delaylength = delay_length, 
                                  amplitude = amplitude,
                                  rise_time=rise_time, 
                                  fall_time=fall_time,
                                  phase = 0.0, 
                                  samplemarker=True, 
                                  syncmarker=False)
        self.upload_chirp(segments[2], 
                                  start_freq, 
                                  stop_freq, 
                                  pulselength = pulse_length,
                                  delaylength = delay_length, 
                                  amplitude = amplitude,
                                  rise_time=rise_time, 
                                  fall_time=fall_time,
                                  phase = 90.0, 
                                  samplemarker=True, 
                                  syncmarker=False)
        self.upload_chirp(segments[3], 
                                  start_freq, 
                                  stop_freq, 
                                  pulselength = pulse_length,
                                  delaylength = delay_length, 
                                  amplitude = amplitude,
                                  rise_time=rise_time, 
                                  fall_time=fall_time,
                                  phase = 180.0, 
                                  samplemarker=True, 
                                  syncmarker=False)
        self.upload_chirp(segments[4], 
                                  start_freq, 
                                  stop_freq, 
                                  pulselength = pulse_length,
                                  delaylength = delay_length, 
                                  amplitude = amplitude,
                                  rise_time=rise_time, 
                                  fall_time=fall_time,
                                  phase = 270.0, 
                                  samplemarker=True, 
                                  syncmarker=False)

        self.check_for_error()
        return segments

    def upload_pump_pulses_width(self, first_segment, frequency, widths,
                                 amplitude = 1.0, 
                                 pulse_length = None,
                                 rise_time = 0.05,
                                 fall_time = 0.05,
                                 phase = 0.0
                                ):
        """
        Upload pump pulses with different pulse widths. A delay will be
        generated if the pulse_length is larger than the width specified in widths.

        :param first_segment: id of the segment to which the first pump pulse is
            uploaded.
        :type first_segment: int
        :param frequency: Frequency in MHz of the pump pulse.
        :type frequency: float
        :param widths: List of pulse widths (in microseconds).
        :type widths: list of float
        :param amplitude: rel. amplitude of the pulse
        :type amplitude: float
        :param pulse_length: Length of the pulses including delay in ms (wo
            rise and fall time.
        :type pulse_length: float

        :returns: list with uploaded segments
        :rtype: list
        """
        if pulse_length is None:
            pulse_length = max(widths)
        
        seg_id = first_segment 
        seg_list = []
        for width in widths:

            delay = pulse_length - width
            if delay < 0.0:
                delay = 0.0

            self.upload_chirp(seg_id, 
                                      start_freq = frequency, 
                                      stop_freq = frequency, 
                                      pulselength = width, 
                                      delaylength = delay, 
                                      rise_time=rise_time, 
                                      amplitude = amplitude,
                                      phase = phase,
                                      fall_time=fall_time, 
                                      samplemarker=False,
                                      syncmarker=False)
            seg_list.append(seg_id)
            seg_id += 1
        return seg_list

    def upload_pump_pulses_width_list(self, 
                                      first_segment, 
                                      frequency_list, 
                                      widths,
                                      amplitude = 1.0, 
                                      pulse_length = None,
                                      rise_time = 0.05,
                                      fall_time = 0.05,
                                      phase = 0.0
                                     ):
        """
        Upload pump pulses with different pulse widths for a list of
        frequnencies. A delay will be generated if the pulse_length is larger
        than the width specified in widths.

        :param first_segment: id of the segment to which the first pump pulse is
                              uploaded.
        :type first_segment: int
        :param frequency_list: List of frequencies in MHz of the pump pulses.
        :type frequency_list: list of float
        :param widths: List of pulse widths (in microseconds).
        :type widths: list of float
        :param amplitude: rel. amplitude of the pulse
        :type amplitude: float
        :param pulse_length: Length of the pulses including delay in ms (wo
                             rise and fall time. 
        :type pulse_length: float

        :returns: list with uploaded segments
        :rtype: list
        """
        seg_id = first_segment
        seg_dict = {}
        for freq in frequency_list:
            segs = self.upload_pump_pulses_width(seg_id,
                                                freq,
                                                widths,
                                                amplitude = amplitude,
                                                pulse_length = pulse_length,
                                                rise_time = rise_time,
                                                fall_time = fall_time,
                                                phase = phase)
            seg_dict[freq] = segs
            seg_id = max(segs) + 1

        return seg_dict

    def upload_qpsk_pulses_different_amplitude(self, 
                                               first_segment, 
                                               frequency,
                                               amplitudes,
                                               delay = 0.0,
                                               width = 1.0,
                                               rise_time = 0.05,
                                               fall_time = 0.05
                                              ):
        """
        Upload qpsk pulses with different pulse amplitude.

        :param first_segment: id of the segment to which the first pump pulse is
            uploaded.
        :type first_segment: int
        :param frequency: Frequency in MHz of the pump pulse.
        :type frequency: float
        :param amplitudes: list of rel. amplitudes
        :type amplitudes: list of float
        :param delay: initial delay of the pulses in microseconds
        :type delay: float
        :param widths: pulse widths in microseconds
        :type widths: float
        """
        
        seg_id = first_segment 
        syncmarker = True
        for amp in amplitudes:
            # 0 deg pulse
            self.upload_chirp(seg_id, 
                                      start_freq = frequency, 
                                      stop_freq = frequency, 
                                      pulselength = width, 
                                      delaylength = delay, 
                                      rise_time=rise_time, 
                                      phase = 0.0,
                                      amplitude = amp,
                                      fall_time=fall_time, 
                                      samplemarker=True,
                                      syncmarker=syncmarker)
            syncmarker = False
            seg_id += 1

            # 90 deg pulse
            self.upload_chirp(seg_id, 
                                      start_freq = frequency, 
                                      stop_freq = frequency, 
                                      pulselength = width, 
                                      delaylength = delay, 
                                      rise_time=rise_time, 
                                      phase = 90.0,
                                      amplitude = amp,
                                      fall_time=fall_time, 
                                      samplemarker=True,
                                      syncmarker=syncmarker)
            seg_id += 1

            # 180 deg pulse
            self.upload_chirp(seg_id, 
                                      start_freq = frequency, 
                                      stop_freq = frequency, 
                                      pulselength = width, 
                                      delaylength = delay, 
                                      rise_time=rise_time, 
                                      phase = 180.0,
                                      amplitude = amp,
                                      fall_time=fall_time, 
                                      samplemarker=True,
                                      syncmarker=syncmarker)
            seg_id += 1

            # 270 deg pulse
            self.upload_chirp(seg_id, 
                              start_freq = frequency, 
                              stop_freq = frequency, 
                              pulselength = width, 
                              delaylength = delay, 
                              rise_time=rise_time, 
                              phase = 270.0,
                              amplitude = amp,
                              fall_time=fall_time, 
                              samplemarker=True,
                              syncmarker=syncmarker)
            seg_id += 1

    def upload_qpsk_pulses_different_width(self, 
                                           first_segment, 
                                           frequency,
                                           widths,
                                           amplitude = 1.0,
                                           delay = 0.0,
                                           rise_time = 0.05,
                                           fall_time = 0.05
                                          ):
        """
        Upload qpsk pulses with different pulse widths.

        :param first_segment: id of the segment to which the first pump pulse is
            uploaded.
        :type first_segment: int
        :param frequency: Frequency in MHz of the pump pulse.
        :type frequency: float
        :param widths: list of pulse widths in microseconds
        :type widths: list of float
        :param amplitude: rel. amplitude (0-1)
        :type amplitude: float
        :param delay: initial delay of the pulses in microseconds
        :type delay: float
        :param widths: list of pulse widths in microseconds
        :type widths: list of float
        """
        
        seg_id = first_segment 
        syncmarker = True
        for width in widths:
            # 0 deg pulse
            self.upload_chirp(seg_id, 
                                      start_freq = frequency, 
                                      stop_freq = frequency, 
                                      pulselength = width, 
                                      delaylength = delay, 
                                      rise_time=rise_time, 
                                      phase = 0.0,
                                      amplitude = amplitude,
                                      fall_time=fall_time, 
                                      samplemarker=True,
                                      syncmarker=syncmarker)
            syncmarker = False
            seg_id += 1

            # 90 deg pulse
            self.upload_chirp(seg_id, 
                                      start_freq = frequency, 
                                      stop_freq = frequency, 
                                      pulselength = width, 
                                      delaylength = delay, 
                                      rise_time=rise_time, 
                                      phase = 90.0,
                                      amplitude = amplitude,
                                      fall_time=fall_time, 
                                      samplemarker=True,
                                      syncmarker=syncmarker)
            seg_id += 1

            # 180 deg pulse
            self.upload_chirp(seg_id, 
                                      start_freq = frequency, 
                                      stop_freq = frequency, 
                                      pulselength = width, 
                                      delaylength = delay, 
                                      rise_time=rise_time, 
                                      phase = 180.0,
                                      amplitude = amplitude,
                                      fall_time=fall_time, 
                                      samplemarker=True,
                                      syncmarker=syncmarker)
            seg_id += 1

            # 270 deg pulse
            self.upload_chirp(seg_id, 
                                      start_freq = frequency, 
                                      stop_freq = frequency, 
                                      pulselength = width, 
                                      delaylength = delay, 
                                      rise_time=rise_time, 
                                      phase = 270.0,
                                      amplitude = amplitude,
                                      fall_time=fall_time, 
                                      samplemarker=True,
                                      syncmarker=syncmarker)
            seg_id += 1






    #####################################################################
    # Set specialized sequences
    #####################################################################

    def create_delay_phasediff_sequence(self, sequence_idx, seg1, seg2,
                                        init_delay, delay):
        """
        Creates a sequence which plays seg1, delay, seg2 and
        has markers on segment 1 and segment 2

        :param seg1: Segment ID, which will be played first
        :type seg1: int
        :param seg2: Segment ID, which will be played after delay
        :type seg2: int
        :param delay: Delay in between segements in microseconds
        :type delay: float
        """

        cp1 = self.create_stabi_control_parameter(command = COMMAND,
                                                  init_marker_sequence = ON,
                                                 )
        cp2 = self.create_stabi_control_parameter(command = DATA,
                                                 marker_enable = ON
                                                 )
        cp3 = self.create_stabi_control_parameter(command = COMMAND,
                                                 )
        cp4 = self.create_stabi_control_parameter(command = DATA,
                                                  marker_enable = ON,
                                                  end_marker_sequence = ON,
                                                 )
        self.create_stabi_table_entry(sequence_idx, 
                                      control_parameter = cp1, 
                                      entry_type = IDLE_DELAY,
                                      idle_delay = self.settings.samplerate * init_delay * 1.0e-6)
        self.create_stabi_table_entry(sequence_idx + 1, 
                                      control_parameter = cp2,
                                      segment_id = seg1)
        self.create_stabi_table_entry(sequence_idx + 2, 
                                      control_parameter = cp3, 
                                      entry_type = IDLE_DELAY,
                                      idle_delay = self.settings.samplerate * delay * 1.0e-6)
        self.create_stabi_table_entry(sequence_idx + 3, 
                                      control_parameter = cp4,
                                      segment_id = seg2)
        err = self.check_for_error()
        if err:
            print(err)
    
          
    def set_multipump_qpsk_delay_sequence(self, 
                                          first_segment, 
                                          qpsk_segments,
                                          pump_segments,
                                          pump_probe_delays,
                                          delays = None,
                                          sequence_loop_count = 1,
                                          stabi_idx = 0
                                         ):
        """
        Usually used to create a sequence that allows to probe the signal as a
        function of pump pulse width and delay time.

        Generates a sequence of pump pulses followed by qpsk-probe pulses in the
        STABI - Table of the AWG. The last pump pulse is repeated for each delay
        specified in pump_probe_delays and probed after the delay time.

        :param first_segment: Id of the first segment (This segment has to
            contain the sync-marker
        :type first_segment: int
        :param qpsk_segments: list of four segment-ids that contain the qpsk - pulses
        :type qpsk_segments: list of int
        :param pump_segments: list of segment-ids that contain the pump pulses
        :type pump_segments: list of int
        :param pump_probe_delays: list of delays that have to be probed 
        :type pump_probe_delays: list of float
        :param delays: Delay before the next pulse [s]
        :type delays: float
        :param sequence_loop_count: Number of iterations of the sequence.
        :type sequence_loop_count: int
        :param stabi_idx: Stabi-Table Id of the first row of the new sequence.
        :type stabi_idx: int
        """
        # ---------------------------------------------
        # test if arguments are valid
        # ---------------------------------------------

        if type(qpsk_segments) != list:
            print("segments is not a list!")
            return

        if len(qpsk_segments) != 4:
            print("Four segments are needed for QPSK (0,90,180,270) deg!")
            return
        
        if type(pump_segments) != list:
            print("Pump segments have to be defined as list!")
            return

        if delays is None:
            delays = []
            # create standard delay set before each segment.
            for i in xrange(4):
                delays.append(self.chirped_pulse_delay)

        # ----------------------------------------------
        # convert delay times into number of samples
        # ----------------------------------------------
        srate = self.get_samplerate()       
        num_samples_delay = [int(round(srate * delay)) for delay in delays] 
        pump_probe_delay_samples = [int(round(srate * delay)) for delay in
                                    pump_probe_delays]

        # initialize some values for loops
        # stabi_idx = 0
        num_pump_loops = len(pump_segments)
        num_delay_loops = len(pump_probe_delays)



        # -----------------------------------------------------
        # CREATE REFERENCE SEQUENCE NO PUMP
        # ----------------------------------------------------#

        # create delay1 - row
        self.create_stabi_table_entry(stabi_idx, 
                                      entry_type= IDLE_DELAY,
                                      control_parameter=2415919104, 
                                      idle_delay = num_samples_delay[0],
                                      sequence_loop_count = sequence_loop_count
                                     )
        stabi_idx += 1
        # create first pulse - row (first probe pulse contains sync-marker!!!)
        self.create_stabi_table_entry(stabi_idx, 
                                      entry_type= DATA,
                                      control_parameter=16777216, 
                                      segment_id = first_segment)
        
        stabi_idx += 1

        for i in xrange(1,4):
            # create 90, 180, and 270 degree pulse with delay
            self.create_stabi_table_entry(stabi_idx, 
                                          entry_type = IDLE_DELAY,
                                          control_parameter=2147483648, 
                                          idle_delay = num_samples_delay[i])

            stabi_idx += 1
            self.create_stabi_table_entry(stabi_idx, 
                                          entry_type=DATA,
                                          control_parameter=16777216, 
                                          segment_id = qpsk_segments[i])
     
            stabi_idx += 1

        # ---------------------------------------------------- 
        # Create Pump-Probe sequences for each pump pulse
        # -----------------------------------------------------
        for j in xrange(num_pump_loops):

            for i in xrange(0,4):
                # create 0, 90, 180, and 270 degree pulse with delay
                self.create_stabi_table_entry(stabi_idx, 
                                              entry_type=IDLE_DELAY,
                                              control_parameter=2147483648, 
                                              idle_delay = num_samples_delay[i])

                stabi_idx += 1

                # pump - segment
                self.create_stabi_table_entry(stabi_idx, 
                                              entry_type=DATA,
                                              control_parameter=0, 
                                              segment_id = pump_segments[j])
         
                stabi_idx += 1

                # check if the next entry is the last one. marker_end_bit has to
                # be set!
                if i == 3 and j == num_pump_loops -1 and num_delay_loops == 0:
                    control_param = 1090519040
                else:
                    control_param = 16777216

                # qpsk - segment
                self.create_stabi_table_entry(stabi_idx, 
                                              entry_type=DATA,
                                              control_parameter=control_param, 
                                              segment_id = qpsk_segments[i])
         

                stabi_idx += 1
        # ------------------------------------------------------ 
        # Create Pump-Probe sequences for each pump pulse delay
        # -------------------------------------------------------
        for j in xrange(num_delay_loops):

            for i in xrange(0,4):
                # create initial delay
                self.create_stabi_table_entry(stabi_idx, 
                                              entry_type=IDLE_DELAY,
                                              control_parameter=2147483648, 
                                              idle_delay = num_samples_delay[i])
                stabi_idx += 1

                # repeat last pump - segment
                self.create_stabi_table_entry(stabi_idx, 
                                              entry_type=DATA,
                                              control_parameter=0, 
                                              segment_id = pump_segments[-1])
                stabi_idx += 1

                # Create delay segment
                self.create_stabi_table_entry(stabi_idx, 
                                              entry_type=IDLE_DELAY,
                                              control_parameter=2147483648, 
                                              idle_delay = pump_probe_delay_samples[j])

                stabi_idx += 1

                # check if the next entry is the last one. marker_end_bit has to
                # be set!
                if i == 3 and j == num_delay_loops -1:
                    control_param = 1090519040
                else:
                    control_param = 16777216

                # create qpsk - probe segment
                self.create_stabi_table_entry(stabi_idx, 
                                              entry_type=DATA,
                                              control_parameter=control_param, 
                                              segment_id = qpsk_segments[i])
         

                stabi_idx += 1

        # Check if an error occured
        self.check_for_error()

        # -------------------------------------------------------------
        # Calculate and print some sequence parameters for information
        # -------------------------------------------------------------

        # calculate length of sequence in ms
        seg_dict = self.get_defined_segments()
        # calculate length of qpsk sequence
        len_qpsk = 0
        len_delay = 0
        len_seq = 0
        for seg in qpsk_segments:
            len_qpsk += int(seg_dict[seg])
                
        for i in xrange(4):
            len_delay += num_samples_delay[i]
            
        for seg in pump_segments:
            len_seq += 4 * int(seg_dict[seg]) + len_qpsk + len_delay

        seq_time = len_seq / self.settings.samplerate

        print(seq_time, len_seq, len_delay, len_qpsk)
        print("Length sequence: %lf ms" % (float(seq_time) * 1000.0))
        print("Max trigger rate: %lf Hz" % (1.0 / seq_time))

        return stabi_idx, seq_time
    
