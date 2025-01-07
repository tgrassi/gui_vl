#!/usr/bin/env python
# -*- coding: utf8 -*-
#
"""
This module provides classes and methods to control synthesizers.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import sys, os
import time

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

class Synthesizer():
    """
    General class to connect and control synthesizers.
    """
    
    connected = False
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
            self.socket = InstSocket(com, host = host, port = port)
            connected = True
        except:
            raise RuntimeError("Could not connect to synthesizer.")
        self.identifier = self.identify()
    
    def close(self):
        """
        Closes the socket.
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
        return self.socket.query(string)
    
    def write(self, string):
        """
        Sends a command to the device.
        
        :param string: the command string to send
        :type string: str
        """
        self.socket.write(string)
    
    def read(self):
        """
        Returns a reading from the socket.

        :returns: a socket reading
        :rtype: str
        """
        return self.socket.read()
    
    def identify(self):
        """
        Returns the identification string of the device.
        
        :returns: the identification string
        :rtype: str
        """
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
    
    def reset(self):
        """
        The Reset (RST) command resets most signal generator functions to a
        factory-defined state.
        """
        self.write('*RST')
   
    def get_opc(self):
        """
        Operation Complete (O PC) query
        """
        self.query('*OPC?')

    def switch_rf_power(self, state='On'):
        """
        Switches RF power on and off.
        
        :param state: state as 'ON' or 'OFF'
        :type state: str
        """
        raise MethodNotAvailableError
    
    def get_rf_power_state(self):
        """
        Queries if RF power is on or off.
        """
        raise MethodNotAvailableError
    
    def set_frequency(self, frequency):
        """
        Sets the RF frequency (in CW mode).
        
        :param frequency: Frequency to be set in [MHz]
        :type frequency: float
        """
        raise MethodNotAvailableError
    
    def set_power_level(self, rf_power):
        """
        Sets the output power level in dB.
        
        :param rf_power: power level in [dB]
        :type rf_power: float
        """
        raise MethodNotAvailableError
    
    def switch_modulation_state(self, state='OFF'):
        """
        Switches modulation on or off
        
        :param state: state as 'ON' or 'OFF', default is OFF
        :type state: str
        """
        raise MethodNotAvailableError

class PSG_signal_generator(Synthesizer):
    """
    A subclass of Synthesizer specifically for the PSG signal generator.
    """
    def __init__(self, host, port=None, com=None):
        """
        See the documentation for the parent class about the input arguments.
        """
        Synthesizer.__init__(self, host, port=port, com=com)
    
    def print_options(self):
        """
        Returns the options installed on the synthesizer.
        """
        if not "options" in dir(self):
            self.options = self.query(':DIAG:INFO:OPT?')
        return self.options
    
    def get_min_frequency(self, unit="Hz"):
        """
        Returns the min. frequency rated for RF output from the device.
        
        :param unit: (optional) The unit used for the rrequency (Hz)
        :type unit: str
        :returns: the min. frequency
        :rtype: float
        """
        # error-check desired unit
        if not unit in ["Hz","kHz","MHz","GHz"]:
            raise SyntaxError("Only [Hz,kHz,MHz,GHz] are allowed units: %s" % unit)
        # get available/installed options
        options = self.print_options()
        # interpret relevant option
        if "521" in options:
            minFreq = 10e6
        else:
            minFreq = 100e3 # tunable here, but spec'd to 250 kHz
        # apply unit scaling
        if unit == "GHz":
            minFreq /= 1e9
        elif unit == "MHz":
            minFreq /= 1e6
        elif unit == "kHz":
            minFreq /= 1e3
        # return rating
        return minFreq
    
    def get_max_frequency(self, unit="Hz"):
        """
        Returns the max. frequency rated for RF output from the device.
        
        :param unit: (optional) The unit used for the rrequency (Hz)
        :type unit: str
        :returns: the max. frequency
        :rtype: float
        """
        # error-check desired unit
        if not unit in ["Hz","kHz","MHz","GHz"]:
            raise SyntaxError("Only [Hz,kHz,MHz,GHz] are allowed units: %s" % unit)
        # get available/installed options
        options = self.print_options()
        # interpret relevant option
        if "567" in options:
            maxFreq = 70e9 # tunable here, but spec'd to 67 GHz
        elif "550" in options:
            maxFreq = 50e9
        elif "540" in options:
            maxFreq = 40e9
        elif "532" in options:
            maxFreq = 31.8e9
        else:
            maxFreq = 20e9
        # apply unit scaling
        if unit == "GHz":
            maxFreq /= 1e9
        elif unit == "MHz":
            maxFreq /= 1e6
        elif unit == "kHz":
            maxFreq /= 1e3
        # return rating
        return maxFreq

    def check_for_error(self):
        """
        Checks and reads errors from the instruments error
        queue.

        Returns all errors (up to 30 are stored) from
        the queue as a list.
        """
        errors = []
        while 1:
            error = self.query(':SYST:ERR?').split(',')
            if int(error[0]):
                errors.append(error)
            else:
                break
        return errors
       
    def switch_rf_power(self, state='OFF'):
        """
        Switches RF power on and off.
         
        :param state: state as 'ON' or 'OFF'
        :type state: str
        """
        if not state.upper() in ('ON', 'OFF'):
            print("State has to be 'OFF' or 'ON'")
            return
        
        self.write(':OUTP:STATe %s' % state.upper())
    def get_rf_power_state(self):
        """
        Queries the RF output state as on (1) or off (0).
        
        :returns: the state of the RF output
        :rtype: int
        """
        return int(self.query(':OUTPUT:STATE?'))
    
    
    def set_frequency(self, frequency, unit='MHz'):
        """
        Sets the RF frequency (in CW mode).
        
        :param frequency: Frequency to be set in [default: MHz]
        :type frequency: float
        :param unit: unit to use ('GHz', 'MHz', or 'Hz')
        :type unit: str
        """
        if not isinstance(frequency, (int, long, float)):
            raise NotANumberError
        
        self.write(':FREQ %lf%s' % (frequency, unit))
    def get_frequency(self):
        """
        Queries the (CW) RF frequency.
        
        :returns: the RF frequency
        :rtype: float
        """
        return float(self.query(':FREQ?'))
    
    
    def get_trigger_mode(self):
        """
        Returns the active triggering mode.

        :returns: the current triggering mode
        :rtype: str
        """
        mode = self.query(':INIT:CONT?')
        if mode == "ON":
            mode = "CONT"
        return mode
    def set_trigger_mode(self, mode):
        """
        Sets the triggering mode.

        :param mode: the triggering mode (CONT or OFF)
        :type mode: str
        """
        mode = mode.upper()
        if not mode in ["CONT", "OFF"]:
            raise SyntaxError("trigger mode option is CONT or OFF, and %s isn't one of them!" % mode)
        if mode == "CONT":
            mode = "ON"
        self.write(':INIT:CONT %s' % mode)
    
    def send_trigger(self):
        """
        Sends a software trigger.
        """
        self.write(':INIT:IMM')
    
    
    def get_frequency_mode(self):
        """
        Returns the active frequency mode.

        :returns: the active frequency mode
        :rtype: str
        """
        return float(self.query(':FREQ:MODE?'))
    def set_frequency_mode(self, mode):
        """
        Sets the frequency mode.

        :param mode: the frequency mode (FIXED, CW, SWEEP, or LIST)
        :type mode: str
        """
        if mode.lower()[:3] == "fix":
            mode = "FIX"
        elif mode.lower() == "cw":
            mode = "CW"
        elif mode.lower()[:3] == "swe":
            mode = "SWE"
        elif mode.lower() == "list":
            mode = "LIST"
        else:
            raise SyntaxError("frequency mode options were [fixed, cw, sweep, list] and you missed it!")
        
        self.write(':FREQ:MODE %s' % mode)
    
    
    def set_power_level(self, rf_power):
        """
        Sets the output power level in dBm.
        
        :param rf_power: power level in [dBm]
        :type rf_power: int/long/float
        """
        if not isinstance(rf_power, (int, long, float)):
            raise NotANumberError
        
        self.write(':POW %lfDBM' % rf_power)
    def get_power_level(self):
        """
        Queries the output power level in dBm.
        
        :returns: the RF power level
        :rtype: float
        """
        return float(self.query(':POW?'))
    
    
    def switch_lf_state(self, state='OFF'):
        """
        Switches low-frequency (LF) output on or off
        
        :param state: Determines wether to switch LF output on ('ON') or off ('OFF')
        :type state: str
        """
        if not state.upper() in ('ON', 'OFF'):
            print("State has to be 'OFF' or 'ON'")
            return
        
        self.write(':LFO:STAT %s' % state.upper())
    def set_lf_amplitude(self, amplitude=1):
        """
        Switches low-frequency (LF) output on or off
        
        :param amplitude: Sets the output voltage of the LF to the desired value
        :type amplitude: float
        """
        if amplitude < 0:
            print("voltage must be positive: %s" % amplitude)
        elif amplitude > 3.5:
            print("maximum voltage allowed is 3.5V: %s" % amplitude)
        
        self.write(':LFO:AMPL %.1fVP' % amplitude)
    def get_lf_state(self):
        """
        Queries the low-frequency (LF) output as on (1) or off (0)
        
        :returns: the state of the LF output
        :rtype: int
        """
        return int(self.query(':LFO:STAT?'))
    
    def switch_pulse_modulation_state(self, state='OFF'):
        """
        Switches pulse-modulation on or off.

        :param state: whether to switch modulation on ('ON') or off ('OFF')
        :type state: str
        """
        if not state.upper() in ('ON', 'OFF'):
            print("State has to be 'OFF' or 'ON'")
            return
        self.write(':PULM:STAT %s' % state.upper())

    def get_pulse_modulation_state(self):
        """
        Queries the pulse modulation as on (1) or off (1)

        :returns: the state of the pulse - modulation
        :rtype: int
        """
        return int(self.query(':PULM:STAT?'))

    def switch_modulation_state(self, state='OFF'):
        """
        Switches modulation on or off
        
        :param state: whether to switch modulation on ('ON') or off ('OFF')
        :type state: str
        """
        if not state.upper() in ('ON', 'OFF'):
            print("State has to be 'OFF' or 'ON'")
            return
        
        self.write('OUTPUT:MOD %s' % state.upper())

    def get_modulation_state(self):
        """
        Queries the modulation as on (1) or off (0)
        
        :returns: the state of the modulation
        :rtype: int
        """
        return int(self.query('OUTPUT:MOD?'))
    
    def set_modulation_type(self, modtype):
        """
        Sets the modulation type as 'NONE', 'AM', 'FM', or 'PHASE'.
        
        Note that this method treats each modulation type mutually exclusive,
        and thus disables alternative forms. It also only deals with Path 1 of
        the instrument.
        
        :param modtype: the type of modulation to use ('NONE', 'AM', 'FM', or 'PHASE')
        :type modtype: str
        """
        if modtype.upper() == "NONE":
            self.write(':AM:STAT OFF')
            self.write(':FM:STAT OFF')
            self.write(':PM:STAT OFF')
        elif modtype.upper() == "AM":
            self.write(':FM:STAT OFF')
            self.write(':PM:STAT OFF')
            self.write(':AM1:STAT ON')
        elif modtype.upper() == "FM":
            self.write(':AM:STAT OFF')
            self.write(':PM:STAT OFF')
            self.write(':FM1:STAT ON')
        elif modtype.upper() == "PHASE":
            self.write(':AM:STAT OFF')
            self.write(':FM:STAT OFF')
            self.write(':PM1:STAT ON')
        else:
            raise SyntaxError("Could not interpret the requested modulation type: %s" % modtype)
    def get_modulation_type(self):
        """
        Queries the modulation type as 'NONE', 'AM', 'FM', or 'PHASE'
        
        :returns: the type of modulation being used
        :rtype: str
        """
        modtype = ""
        if int(self.query(':AM:STAT?')):
            modtype += "AM "
        if int(self.query(':FM:STAT?')):
            modtype += "FM "
        if int(self.query(':PM:STAT?')):
            modtype += "PHASE "
        if modtype == "":
            modtype = "NONE"
        return modtype.strip()
    
    
    def set_modulation_freq(self, freq, modtype=""):
        """
        Sets the modulation frequency.
        
        :param freq: the frequency to use in [Hz]
        :param modtype: the type of modulation to use ('AM', 'FM', or 'PHASE')
        :type freq: float
        :type modtype: str
        """
        if modtype.upper() == "AM":
            self.write(':AM1:INT1:FREQ %f' % freq)
        elif modtype.upper() == "FM":
            self.write(':FM1:INT1:FREQ %f' % freq)
        elif modtype.upper() == "PHASE":
            self.write(':PM1:INT1:FREQ %f' % freq)
        else:
            raise SyntaxError("Could not interpret the requested modulation type: %s" % modtype)
    def get_modulation_freq(self, modtype=""):
        """
        Queries the modulation frequency.
        
        :param modtype: the type of modulation to use ('AM', 'FM', or 'PHASE')
        :type modtype: str
        :returns: the modulation frequency in [Hz]
        :rtype: float
        """
        if modtype.upper() == "AM":
            return float(self.query(':AM1:INT1:FREQ?'))
        elif modtype.upper() == "FM":
            return float(self.query(':FM1:INT1:FREQ?'))
        elif modtype.upper() == "PHASE":
            return float(self.query(':PM1:INT1:FREQ?'))
        else:
            raise SyntaxError("Could not interpret the requested modulation type: %s" % modtype)
    
    
    def set_modulation_dev(self, deviation, modtype=""):
        """
        Sets the modulation deviation.
        
        :param deviation: the deviation to use (in [percent] for AM, [Hz] for FM, or [radians] for PM)
        :param modtype: the type of modulation to use ('AM', 'FM', or 'PHASE')
        :type deviation: float
        :type modtype: str
        """
        if modtype.upper() == "AM":
            self.write(':AM1 %f' % deviation)
        elif modtype.upper() == "FM":
            self.write(':FM1 %fHZ' % deviation)
        elif modtype.upper() == "PHASE":
            self.write(':PM1 %fRAD' % deviation)
        else:
            raise SyntaxError("Could not interpret the requested modulation type: %s" % modtype)
    def get_modulation_dev(self, modtype=""):
        """
        Queries the modulation deviation.
        
        If AM, the deviation is [percent];
        if FM, the deviation is [Hz];
        if PM, the deviation returns as [radians].
        
        :param modtype: the type of modulation to use ('AM', 'FM', or 'PHASE')
        :type modtype: str
        :returns: the amount of deviation to be used for modulation
        :rtype: float
        """
        if modtype.upper() == "AM":
            return float(self.query(':AM1?'))
        elif modtype.upper() == "FM":
            return float(self.query(':FM1?'))
        elif modtype.upper() == "PHASE":
            return float(self.query(':PM1?'))
        else:
            raise SyntaxError("Could not interpret the requested modulation type: %s" % modtype)
    
    
    def set_modulation_shape(self, shape, modtype=""):
        """
        Sets the functional shape of the modulation.
        
        :param depth: the shape of the function to use ('SINE', 'TRI', or 'SQUARE')
        :param modtype: the type of modulation to use ('AM', 'FM', or 'PHASE')
        :type depth: float
        :type modtype: str
        """
        if not shape.upper() in ["SINE", "TRI", "SQU"]:
            raise SyntaxError("You requested an unavailable shape: %s" % shape)
        
        if modtype.upper() == "AM":
            self.write(':AM1:INT1:FUNC:SHAP %s' % shape)
        elif modtype.upper() == "FM":
            self.write(':FM1:INT1:FUNC:SHAP %s' % shape)
        elif modtype.upper() == "PHASE":
            self.write(':PM1:INT1:FUNC:SHAP %s' % shape)
        else:
            raise SyntaxError("Could not interpret the requested modulation type: %s" % modtype)
    def get_modulation_shape(self, modtype=""):
        """
        Queries the functional shape of the modulation.
        
        :param modtype: the type of modulation to use ('AM', 'FM', or 'PHASE')
        :type modtype: str
        :returns: the shape of the modulation being used
        :rtype: str
        """
        if modtype.upper() == "AM":
            return self.query(':AM1:INT1:FUNC:SHAP?')
        elif modtype.upper() == "FM":
            return self.query(':FM1:INT1:FUNC:SHAP?')
        elif modtype.upper() == "PHASE":
            return self.query(':PM1:INT1:FUNC:SHAP?')
        else:
            raise SyntaxError("Could not interpret the requested modulation type: %s" % modtype)

    def get_pulse_delay(self):
        """
        Queries the pulse delay.
        """
        return float(self.query(':PULM:INT:DEL?'))

    def set_pulse_delay(self, delay):
        """
        Sets the pulse delay.

        :param delay: Delay in seconds
        :type delay: float
        """
        self.write(':PULM:INT:DEL %g' % delay)
        delay = self.get_pulse_delay()
        print("Pulse delay set to %g s" % delay)

    def get_pulse_rate(self):
        """
        Queries the pulse rate. The pulse rate is only used for the internal
        square wave signal (not used in free-run mode).
        """
        return float(self.query(':PULM:INT:FREQ?'))

    def set_pulse_rate(self, rate):
        """
        Sets the pulse rate. The pulse rate is only used for the internal square
        wave signal (not used in free-run mode).

        :param rate: pulse rate in s
        :type rate: float
        """
        self.write(':PULM:INT:FREQ %g' % rate)

    def set_pulse_period(self, period):
        """
        Sets the pulse period.
        
        :param period: period in s
        :type period: float
        """
        self.write(':PULM:INT:PERIOD %g' % period)
        period = self.get_pulse_period()
        print("Pulse period set to %g s" % period)

    def get_pulse_period(self):
        """
        Queries the pulse period.

        Returns period in s.
        """
        period = float(self.query(':PULM:INT:PERIOD?'))
        return period

    def get_pulse_width(self):
        """
        Queries the pulse width.
        """
        return float(self.query(':PULM:INT:PWID?'))

    def set_pulse_width(self, width):
        """
        Sets the pulse width.

        :param width: pulse width in s
        :type width: float
        """
        self.write(':PULM:INT:PWID %g' % width)
        width = self.get_pulse_width()
        print("Pulse width set to %g s" % width)
    
    def get_freq_list_type(self):
        """
        Queries the type ('list' or 'step') of the current frequency list.
        
        :returns: the list type
        :rtype: str
        """
        return self.query(':LIST:TYPE?')
    def set_freq_list_type(self, mode):
        """
        Sets the type for the current frequency list.
        
        :param mode: the type (LIST or STEP)
        :type mode: str
        """
        mode = mode.upper()
        if not mode in ["LIST", "STEP"]:
            raise SyntaxError("list type must be LIST|STEP!")
        self.write(':LIST:TYPE %s' % mode)
    
    def get_freq_list_direction(self):
        """
        Queries the direction (up or down) for the current frequency list.
        
        :returns: the direction of the frequency list
        :rtype: str
        """
        return self.query(':LIST:DIR?')
    def set_freq_list_direction(self, direction):
        """
        Sets the direction (UP or DOWN) for the current frequency list.
        
        :param direction: the direction (UP or DOWN)
        :type direction: str
        """
        if isinstance(direction, bool):
            if direction: direction="UP"
            else: direction="DOWN"
        direction = direction.upper()
        if not direction in ["UP", "DOWN"]:
            raise SyntaxError("list direction must be UP|DOWN!")
        self.write(':LIST:DIR %s' % direction)
    
    def get_freq_list_dwell(self):
        """
        Queries the time (seconds) spent at each frequency point in the list.
        
        :returns: the time spent at each frequency point in the list
        :rtype: float
        """
        return float(self.query(':LIST:DWEL?'))
    def set_freq_list_dwell(self, dwell):
        """
        Sets the time (seconds) spent at each frequency point in the list.
        
        :param dwell: the time to spend
        :type dwell: float
        """
        try:
            float(dwell)
        except ValueError:
            raise SyntaxError("your requested dwell time did not look like a number!")
        self.write(':LIST:DWEL %.3f' % dwell)
    
    def get_freq_list_amplitude(self):
        """
        Queries the amplitude (dBm) used for each frequency point in the list.
        
        :returns: the amplitude in units (dBm)
        :rtype: float
        """
        return self.query(':LIST:POW?')
    def set_freq_list_amplitude(self, amplitude):
        """
        Sets the amplitude to use for each frequency point in the list.
        
        Note that the device accepts either one value (constant) or a list,
        but right now only a constant value is accepted.
        
        :param amplitude: the amplitude in units (dBm)
        :type amplitude: float
        """
        try:
            float(amplitude)
        except ValueError:
            raise SyntaxError("your requested amplitude did not look like a number!")
        self.write(':LIST:POW %f' % amplitude)
    
    def get_freq_list_points(self):
        """
        Queries the list of frequency points.
        
        :returns: the list of frequencies
        :rtype: list(float)
        """
        return self.query(':LIST:FREQ?')
    def set_freq_list_points(self, points=[], unit="MHz"):
        """
        Sets the amplitude to use for each frequency point in the list.
        
        Note that the device accepts either one value (constant) or a list,
        but right now only a constant value is accepted.
        
        :param points: the list of frequencies
        :type points: list(float)
        """
        for i,val in enumerate(points):
            points[i] = "%s%s" % (val, unit)
        points = ",".join(points)
        self.write(':LIST:FREQ %s' % points)
    
    def get_freq_list_length(self):
        """
        Queries the amplitude (dBm) used for each frequency point in the list.
        
        :returns: the amplitude in units (dBm)
        :rtype: float
        """
        return self.query(':LIST:FREQ:POIN?')
    
    



