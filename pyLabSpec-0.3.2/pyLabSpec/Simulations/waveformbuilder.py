#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module defines classes which generate a waveform of the signal,
which can be transfered to the AWG.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import sys
import os

import numpy as np
import pyqtgraph as pg
from pyqtgraph import exporters
from scipy.special import fresnel
from scipy.fftpack import fft, ifft, fftshift

if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Spectrum import spectrum

if sys.version_info[0] == 3:
    xrange = range


DEFAULT_SAMPLERATE = 12.0e9

class Waveform(object):

    """
    This class defines an object which contains the sampled waveform
    """

    def __init__(self, data, samplerate=DEFAULT_SAMPLERATE):
        """
        Initialize a waveform based on the sample points.

        :param data: List or Array with the sample points
        :type data: list or array
        :param samplerate: Sample rate.
        :type samplerate: float
        """
        self.data = data
        self.length = len(data)
        self.samplerate = float(samplerate)
        self.t = self.get_sampled_time()

    def plot(self):
        """
        Plots the waveform.
        """
        self.t = self.get_sampled_time()
        self.p = pg.plot(x=self.t, y=self.data)
        labelStyle = {'color': '#FFF', 'font-size': '14pt'}
        self.p.setLabel('bottom', text='Time', units='s', **labelStyle)
        self.p.setLabel('left', 'Intensity', **labelStyle)

    def get_sampled_time(self):
        """
        Returns an array with sampled time-points according to the samplerate and sample length

        :returns: Array with sampled points
        :rtype: numpy.array
        """
        return np.array(xrange(self.length)) / self.samplerate


class Signal():

    """
    This is a base class which provides general methods used by all waveforms.
    """

    sweeprate = 0.0
    span = 0.0
    freq_lo = None

    # Signal correction, such as phase offsets of the AWG - Channels
    correction = {"phase_offset_i": 0.0,  # phase - offset in Degree (I-Channel)
                  "phase_offset_q": 0.0  # phase - offset in Degree (Q-Channel)
                  }

    def set_initial_phase(self, phase=0.0):
        """
        Sets the initial phase of the chirped pulse (Default = 0 degree)

        :param phase: Initial phase in degree
        :type phase: float
        """
        self.phase = np.pi * phase / 180.0

    def apply_phase_correction(self, offset_i=0.0, offset_q=0.0):
        """
        Apply a correction of the phases of each channel (I and Q).

        The phase correction is used in order to account for transit time differences between I and Q channel
        and to improve the sideband surpression.

        :param offset_i: Phase offset of the I-Channel (Degree).
        :param offset_q: Phase offset of the Q-Channel (Degree).
        """
        self.correction['phase_offset_i'] = offset_i * np.pi / 180.0
        self.correction['phase_offset_q'] = offset_q * np.pi / 180.0

    def plot_iq(self):
        """
        Plots the I and Q signals of the waveform.
        """
        i, q = self.calc_iq_waveform()
        t = np.array(xrange(len(i.data))) / self.samplerate
        self.p = pg.plot(t, i.data, pen='r')
        self.p.plot(t, q.data, pen='b')
        labelStyle = {'color': '#FFF', 'font-size': '14pt'}
        self.p.setLabel('bottom', text='Time', units='s', **labelStyle)
        self.p.setLabel('left', 'Intensity', **labelStyle)

    def plot_upconverted_signal(self, freq_lo=None):
        """
        Plots the upconverted signal.

        :param freq_lo: Frequency of the local oscillator in [MHz] (if None:
            LO-Frequency, which is specified in the instance, is used.
        :type freq_lo: float
        """
        if not freq_lo:
            freq_lo = self.freq_lo
        else:
            freq_lo = float(freq_lo) * 1.0e6
        self.out_signal = self.simulate_upconversion(freq_lo=freq_lo)
        self.out_signal.plot()

    def set_pulselength(self, pulselength):
        """
        Sets the pulse length of the signal
        """
        self.pulselength = pulselength
        self.sweeprate = self.span * 1.0e6 / self.pulselength

    def simulate_upconversion(self, freq_lo=None, samplerate=None):
        """
        Simulates the upconversion via I/Q - Modulator. The samplerate can be specified, but should be
        at least twice the LO-frequency.
        """
        if not freq_lo:
            freq_lo = self.freq_lo

        if not freq_lo:
            print("No LO-frequency specified")
            return

        if not self.pulselength:
            print("No pulselength specified")
            return

        if not samplerate:
            samplerate = freq_lo * 2.5

        if samplerate < 2.0 * freq_lo:
            samplerate = 2.5 * freq_lo
            print('Samplerate should be greater than twice the local oscillator frequency!\nSamplerate set to: %lf' %
                  samplerate)

        # Get the number of samplepoints needed
        samplepoints = int(round(samplerate * self.pulselength * 1.0e-6))

        t = np.array(xrange(samplepoints)) / samplerate
        # sample lo-signal and lo-signal after 90 deg phase shift
        lo = np.sin(2.0 * np.pi * freq_lo * t)
        lo90 = np.cos(2.0 * np.pi * freq_lo * t)

        i, q = self.calc_iq_waveform(samplerate=samplerate)
        return Waveform(lo * i.data + lo90 * q.data, samplerate=samplerate)

class DoublePulse(Signal):

    """
    This class defines two monochromatic pulses with delay in between.

    """
    data = []

    def __init__(self, freq, freq_lo=None, pulselength=1.0,
                 phase=0.0, amplitude = 1.0, samplerate=12.0e9, rise_time = 0.0, fall_time = 0.0,
                 initial_delay = 0.0, delay = 0.0, invert_second = False,
                 vectorsize = 64, min_segment_size = 320, make_granular = True):
        """
        Initializes all paramters that define the chirped pulse signal.

        :param freq: Frequency of the Pulse in MHz
        :type freq_start: float
        :param freq_lo: Frequency of the local oscillator in MHz, which is used for upconversion
        :type freq_lo: float
        :param pulselength: Pulselength in microseconds
        :type pulselength: float
        :param phase: Initial Phase in Degrees
        :type phase: float
        :param amplitude: rel. amplitude (0-1)
        :type amplitude: float
        :param samplerate: Rate at which the signal is sampled [Sa/s].
        :type samplerate: float
        :param initial_delay: Initial delay of the pulse
        :type delay: float
        :param delay: Delay between pulses in microseconds
        :type delay: float
        :param invert_second: Phase of the second pulse ( 180 deg if True)
        :param invert_second: Boolean
        :param make_granular: Insert zeros at the beginning of the waveform to
                              fullfill granularity
        """
        self.samplerate = float(samplerate)
        self.pulselength = float(pulselength)
        self.rise_time = float(rise_time)
        self.fall_time = float(fall_time)
        self.initial_delay = float(initial_delay)
        self.amplitude = float(amplitude)
        self.delay = float(delay)
        self.freq = float(freq) * 1.0e6
        self.invert_second = invert_second
        self.min_segment_size = min_segment_size
        self.vectorsize = vectorsize
        self.make_granular = make_granular

        self.span = 0.0

        if not freq_lo:
            self.freq_lo = 0.0
        else:
            self.freq_lo = float(freq_lo) * 1.0e6

        # direction of the sweep (increasing or decreasing in frequency)
        self.sweepdirection = 'up'

        self.sweeprate = self.span * 1.0e6 / self.pulselength
        self.set_initial_phase(phase)

        # calculates both waveforms (I/Q)
        self.i_signal, self.q_signal = self.calc_iq_waveform()
        if amplitude < 1.0:
            self.i_signal.data = self.i_signal.data * amplitude
            self.q_signal.data = self.q_signal.data * amplitude

    def calc_iq_waveform(self, samplerate = None, length = 0.0):
        """
        Calculates and samples the waveform for the I and Q channels, based on
        Keysights iqtools - algorythm.

        :param samplerate: rate at which the waveform is sampled (might differ for simulation purposes from the initialized value)
        :type samplerate: float
        :param length: length of the waveform to be created [microseconds]
        :type length: float

        :return: Returns the sample points for time, i-channel, q-channel
        :rtype: tuple of type numpy.array
        """
        if samplerate is None:
            samplerate = self.samplerate

        # Calculated the Start-Frequency of the IF-Signal for both channels (I
        # and Q).
        if_freq = self.freq - self.freq_lo
        # Get the number of samplepoints needed
        self.wvform_length = np.max([self.initial_delay + self.delay 
                                     + 2.0 * self.pulselength 
                                     + 2.0 * self.rise_time + 2.0 * self.fall_time, length])
        samplepoints = int(round(samplerate * self.wvform_length * 1.0e-6))
        if self.make_granular:
            # check minimum segment size
            if samplepoints < self.min_segment_size:
                num_points_to_insert = self.min_segment_size - samplepoints
                time_to_add = num_points_to_insert / samplerate
                self.initial_delay += time_to_add * 1.0e6
                self.wvform_length += time_to_add * 1.0e6
                samplepoints = self.min_segment_size
            elif samplepoints % self.vectorsize > 0:
                num_points_to_insert = self.vectorsize - (samplepoints % self.vectorsize)
                time_to_add = num_points_to_insert / samplerate
                self.initial_delay += time_to_add * 1.0e6
                self.wvform_length += time_to_add * 1.0e6
                samplepoints += num_points_to_insert
 
        samplepoints_single_pulse = samplerate * (self.rise_time +
                                                  self.pulselength +
                                                  self.fall_time) * 1.0e-6
        samplepoints_single_pulse = int(round(samplepoints_single_pulse))
        samplepoints_delay = int(round(samplerate * self.delay * 1.0e-6))
        samplepoints_initial_delay = int(round(samplerate * self.initial_delay *
                                               1.0e-6))

        phase = 180.0 * self.phase / np.pi
        offset = if_freq

        if self.invert_second:
            phase_fac = -1.0
        else:
            phase_fac = 1.0

        chirpType = 'increasing'

        print("--------------------------------")
        print("Create Chirp - Pulse")
        print("--------------------------------")
        print("Waveform - Length: %lf" % self.wvform_length)
        print("Samplepoints: %d " % samplepoints)
        print("Samplerate: %d" % samplerate)
        print("")
        print("Offset: %lf" % offset)
        print("Span: %lf" % self.span)
        print("Delay-Length: %lf" % self.delay)
        print("Pulselength: %lf" % self.pulselength)
        print("Rise-time: %lf" % self.rise_time)
        print("Fall-time: %lf" % self.fall_time)
        print("Phase: %lf" % self.phase)
        print("Sweep - direction: %s" % chirpType)
        print("--------------------------------")

        # create one pulse 
        iqdata = iqpulse(samplepoints, samplerate, self.span, 
                         1.0e-6 * (self.wvform_length - self.initial_delay),
                         0.0 * self.rise_time * 1.0e-6, # no rise time here
                         0.0 * self.fall_time * 1.0e-6, # no fall time here
                         self.initial_delay * 1.0e-6, phase, offset, 
                         pulseShape = 'raised cosine', 
                         chirpType =  chirpType, 
                         amplitude = 10.0, 
                         normalize = True)

        # get envelope of the two pulse scheme
        env_single_pulse = calcPulseShape(samplepoints_single_pulse, 0, 0.0,
                                          self.rise_time * 1.0e-6,
                                          self.pulselength * 1.0e-6,
                                          self.fall_time * 1.0e-6, 
                                          samplerate, 'raised cosine', 0.0)
        env_delay = calcPulseShape(samplepoints_delay, 0, 0.0,
                                          0.0e-6,
                                          self.delay * 1.0e-6,
                                          0.0e-6, 
                                          samplerate, 'raised cosine', 0.0)
        env_initial_delay = calcPulseShape(samplepoints_initial_delay, 0, 0.0,
                                          0.0e-6,
                                          self.initial_delay * 1.0e-6,
                                          0.0e-6, 
                                          samplerate, 'raised cosine', 0.0)

        envelope = np.concatenate((env_initial_delay, env_single_pulse,
                                   0.0 * env_delay, phase_fac * env_single_pulse))

        print(len(envelope))
        print(len(env_initial_delay))
        print(len(env_single_pulse))
        print(len(env_delay))

        print(len(iqdata.real))
        return Waveform(iqdata.real * envelope, samplerate = samplerate), \
                Waveform(iqdata.imag * envelope, samplerate = samplerate) 

    def get_phase(self, t):
        """
        Returns the phase at time t
        """
        return 2.0 * np.pi * (self.freq * t + 0.5 * self.sweeprate * t ** 2.0) + self.phase

    def get_signal(self, t):
        """
        Returns the normalized voltage at time t
        """
        return np.cos(self.get_phase(t))

    def get_spectrum(self, f):
        """
        Gets the power spectrum at frequency f of the chirped pulse
        f in MHz
        """
        f = f * 1.0e6
        X1 = 2.0 * np.sqrt(np.pi) * ((self.span / 2.0) + f - self.freq_center) / np.sqrt(
            self.span * 1.0e6 / self.pulselength)
        X2 = 2.0 * np.sqrt(np.pi) * ((self.span / 2.0) - f + self.freq_center) / \
            np.sqrt(self.span * 1.0e6 / self.pulselength)

        S1, C1 = fresnel(X1)
        S2, C2 = fresnel(X2)

        return np.sqrt(np.pi * self.pulselength * 1.0e-6 / (2.0 * np.pi * self.span) * ((C1 + C2) ** 2.0 + (S1 + S2) ** 2.0))

    def calc_power_spectrum(self, numpoints=1000):
        """
        Calculates a power spectrum of the chirp pulse (idealized chirped pulse without any signal corrections).

        :param numpoints: number of data points
        :type numpoints: integer
        :return: Returns the sampled power spectrum.
        :rtype: Spectrum.spectrum.Spectrum

        """

        x = self.freq_start - 0.5 * self.span + \
            np.array(xrange(numpoints)) * 2.0 * self.span / numpoints
        y = self.get_spectrum(1.0e-6 * x)

        s = spectrum.Spectrum(x, y ** 2.0)

        return s


class Chirp(Signal):

    """
    This class defines a linear Chirp.

    """
    data = []

    def __init__(self, freq_start, freq_stop, freq_lo=None, pulselength=1.0,
                 phase=0.0, amplitude = 1.0, samplerate=12.0e9, rise_time = 0.0, fall_time = 0.0,
                 delay = 0.0):
        """
        Initializes all paramters that define the chirped pulse signal.

        :param freq_start: Start-Frequency of the Chirp in MHz
        :type freq_start: float
        :param freq_stop: Stop-Frequency of the Chirp in MHz.
        :type freq_stop: float
        :param freq_lo: Frequency of the local oscillator in MHz, which is used for upconversion
        :type freq_lo: float
        :param pulselength: Pulselength in microseconds
        :type pulselength: float
        :param phase: Initial Phase in Degrees
        :type phase: float
        :param amplitude: rel. amplitude (0-1)
        :type amplitude: float
        :param samplerate: Rate at which the signal is sampled [Sa/s].
        :type samplerate: float
        :param delay: Initial delay of the pulse
        :type delay: float
        """
        self.samplerate = float(samplerate)
        self.pulselength = float(pulselength)
        self.rise_time = float(rise_time)
        self.fall_time = float(fall_time)
        self.delay = float(delay)
        self.amplitude = float(amplitude)

        # convert frequencies to Hz
        self.freq_start = float(freq_start) * 1.0e6
        self.freq_stop = float(freq_stop) * 1.0e6

        self.span = abs(self.freq_stop - self.freq_start)
        self.freq_center = self.freq_start + \
            (self.freq_stop - self.freq_start) / 2.0

        if not freq_lo:
            self.freq_lo = 0.0
        else:
            self.freq_lo = float(freq_lo) * 1.0e6

        # direction of the sweep (increasing or decreasing in frequency)
        if freq_start < freq_stop:
            self.sweepdirection = 'up'
        else:
            self.sweepdirection = 'down'

        self.sweeprate = self.span * 1.0e6 / self.pulselength
        self.set_initial_phase(phase)

        # calculates both waveforms (I/Q)
        self.i_signal, self.q_signal = self.calc_iq_waveform()
        if amplitude < 1.0:
            self.i_signal.data = self.i_signal.data * amplitude
            self.q_signal.data = self.q_signal.data * amplitude

    def function(self):
        # calculate number of points needed
        num_points = self.samplerate * self.pulselength / 1000000.0

        self.t = np.arange(0.0, self.pulselength, 1000000.0 / self.samplerate)
        self.freqlist = self.startfreq + \
            (self.span * self.t / self.pulselength)
        self.si = np.sin(np.pi + 2.0 * np.pi * (
            self.startfreq + (0.5 * self.span * self.t / self.pulselength)) * self.t)
        self.sq = np.sin(0.5 * np.pi + 2.0 * np.pi * (
            self.startfreq + (0.5 * self.span * self.t / self.pulselength)) * self.t)

    def calc_iq_waveform_old(self, samplerate=None):
        """
        Calculates and samples the waveform for the I and Q channels.

        :param samplerate: rate at which the waveform is sampled (might differ for simulation purposes from the initialized value)
        :return: Returns the sample points for time, i-channel, q-channel
        :rtype: tuple of type numpy.array
        """
        if not samplerate:
            samplerate = self.samplerate

        # Calculated the Start-Frequency of the IF-Signal for both channels (I
        # and Q).
        if_freq_start = self.freq_start - self.freq_lo
        # Get the number of samplepoints needed
        samplepoints = int(round(samplerate * self.pulselength * 1.0e-6))

        t = np.array(xrange(samplepoints)) / samplerate
        i = np.cos(2.0 * np.pi * (if_freq_start * t + 0.5 * self.sweeprate * t ** 2.0)
                   + self.phase + self.correction['phase_offset_i'])
        q = np.sin(2.0 * np.pi * (if_freq_start * t + 0.5 * self.sweeprate * t ** 2.0)
                   + self.phase + self.correction['phase_offset_q'])

#        i = np.sin(np.pi + 2.0 * np.pi *
#                   (if_freq_start + (0.5 * self.sweeprate * t)) * t)
#        q = np.sin(0.5 * np.pi + 2.0 * np.pi *
#                   (if_freq_start + (0.5 * self.sweeprate * t)) * t)

# lo = np.sin( 2.0 * np.pi * 2.0e9 * t) # 2 GHz LO signal for test calculations
#        lo90 = np.sin ( 2.0 * np.pi * 2.0e9 * t + np.pi / 2.0)

        env = np.array([(np.cos(np.pi * (tt * 1.0e6/self.rise_time - 1.0)) + \
                           1.0)/2.0 if tt < 1.0e-6 * self.rise_time else (np.cos(np.pi * \
                         (tt - 1.0e-6 * (self.pulselength - self.fall_time))/\
                         (1.0e-6 * self.fall_time))  + 1.0)/2.0 if tt > 1.0e-6 *
                        (self.pulselength - self.fall_time) else 1.0 for tt in t]) 

        i = env * i
        q = env * q


        return Waveform(i, samplerate=samplerate), Waveform(q, samplerate=samplerate)

    def calc_iq_waveform(self, samplerate = None, length = 0.0):
        """
        Calculates and samples the waveform for the I and Q channels, based on
        Keysights iqtools - algorythm.

        :param samplerate: rate at which the waveform is sampled (might differ for simulation purposes from the initialized value)
        :type samplerate: float
        :param length: length of the waveform to be created [microseconds]
        :type length: float

        :return: Returns the sample points for time, i-channel, q-channel
        :rtype: tuple of type numpy.array
        """
        if samplerate is None:
            samplerate = self.samplerate

        # Calculated the Start-Frequency of the IF-Signal for both channels (I
        # and Q).
        if_freq_start = self.freq_center - self.freq_lo
        # Get the number of samplepoints needed
        self.wvform_length = np.max([self.delay + self.pulselength +
                                    self.rise_time + self.fall_time, length])
        samplepoints = int(round(samplerate * self.wvform_length * 1.0e-6))
        phase = 180.0 * self.phase / np.pi
        offset = if_freq_start

        if self.sweepdirection == 'down':
            chirpType = 'decreasing'
        else:
            chirpType = 'increasing'

        print("--------------------------------")
        print("Create Chirp - Pulse")
        print("--------------------------------")
        print("Waveform - Length: %lf" % self.wvform_length)
        print("Samplepoints: %d " % samplepoints)
        print("Samplerate: %d" % samplerate)
        print("")
        print("Offset: %lf" % offset)
        print("Span: %lf" % self.span)
        print("Delay-Length: %lf" % self.delay)
        print("Pulselength: %lf" % self.pulselength)
        print("Rise-time: %lf" % self.rise_time)
        print("Fall-time: %lf" % self.fall_time)
        print("Phase: %lf" % self.phase)
        print("Sweep - direction: %s" % chirpType)
        print("--------------------------------")

        iqdata = iqpulse(samplepoints, samplerate, self.span, 1.0e-6 * self.pulselength,
                         self.rise_time * 1.0e-6, self.fall_time * 1.0e-6,
                         self.delay * 1.0e-6, phase, offset, 
                         pulseShape = 'raised cosine', 
                         chirpType =  chirpType, 
                         amplitude = 10.0, 
                         normalize = True)

        return Waveform(iqdata.real, samplerate = samplerate), \
                Waveform(iqdata.imag, samplerate = samplerate) 

    def get_phase(self, t):
        """
        Returns the phase at time t
        """
        return 2.0 * np.pi * (self.startfreq * t + 0.5 * self.sweeprate * t ** 2.0) + self.phase

    def get_signal(self, t):
        """
        Returns the normalized voltage at time t
        """
        return np.cos(self.get_phase(t))

    def get_spectrum(self, f):
        """
        Gets the power spectrum at frequency f of the chirped pulse
        f in MHz
        """
        f = f * 1.0e6
        X1 = 2.0 * np.sqrt(np.pi) * ((self.span / 2.0) + f - self.freq_center) / np.sqrt(
            self.span * 1.0e6 / self.pulselength)
        X2 = 2.0 * np.sqrt(np.pi) * ((self.span / 2.0) - f + self.freq_center) / \
            np.sqrt(self.span * 1.0e6 / self.pulselength)

        S1, C1 = fresnel(X1)
        S2, C2 = fresnel(X2)

        return np.sqrt(np.pi * self.pulselength * 1.0e-6 / (2.0 * np.pi * self.span) * ((C1 + C2) ** 2.0 + (S1 + S2) ** 2.0))

    def calc_power_spectrum(self, numpoints=1000):
        """
        Calculates a power spectrum of the chirp pulse (idealized chirped pulse without any signal corrections).

        :param numpoints: number of data points
        :type numpoints: integer
        :return: Returns the sampled power spectrum.
        :rtype: Spectrum.spectrum.Spectrum

        """

        x = self.freq_start - 0.5 * self.span + \
            np.array(xrange(numpoints)) * 2.0 * self.span / numpoints
        y = self.get_spectrum(1.0e-6 * x)

        s = spectrum.Spectrum(x, y ** 2.0)

        return s


class SingleTone(Signal):

    """
    This class defines a single monochromatic signal.
    """
    data = []

    def __init__(self, 
                 freq, 
                 freq_lo=None, 
                 pulselength=None, 
                 phase=0.0,
                 amplitude = 1.0, 
                 samplerate=12.0e9, 
                 rise_time = 0.0, 
                 fall_time = 0.0):
        """
        Initializes the single tone.

        :param freq: Frequency of the single tone in MHz.
        :type freq: float
        :param freq_lo: Frequency of the Local Oscillator (if AWG Signal is upconverted) in MHz.
        :type freq_lo: float
        :param pulselength: Length of the signal in microseconds.
        :type pulselength: float
        :param phase: Initial phase of the signal in Degree.
        :type phase: float
        :param amplitude: relative amplitude (0-1)
        :type amplitude: float
        :param samplerate: Rate at which the signal will be sampled in Sample/s.
        :type samplerate: float
        :param rise_time: Time to reach the full amplitude in microseconds
        :type rise_time: float
        :param fall_time: Time to reach zero signal
        :type fall_time: float
        """
        self.samplerate = float(samplerate)
        self.freq = freq * 1.0e6
        self.set_initial_phase(phase)

        # Calculate the IF - Frequency
        if freq_lo:
            self.freq_lo = freq_lo * 1.0e6
            self.freq_if = self.freq - self.freq_lo
        else:
            self.freq_if = self.freq
            self.freq_lo = None

        # set the pulselength to one period if not defined yet
        if not pulselength:
            self.pulselength = 1.0e6 / self.freq_if
        else:
            self.pulselength = pulselength

        # attach rise and fall times to pulse length
        self.rise_time = rise_time
        self.fall_time = fall_time
        self.pulselength += (rise_time + fall_time) 

        # calculates both waveforms (I/Q)
        self.i_signal, self.q_signal = self.calc_iq_waveform()
        if amplitude < 1.0:
            self.i_signal.data = self.i_signal.data * amplitude
            self.q_signal.data = self.q_signal.data * amplitude


    def calc_iq_waveform(self):
        """
        Calculates and samples the waveform for the I and Q channels.
        """

        # Get the number of samplepoints needed
        samplepoints = int(round(self.samplerate * self.pulselength * 1.0e-6))

        t = np.array(xrange(samplepoints)) / float(self.samplerate)
        i = np.cos(2.0 * np.pi * (self.freq_if * t) +
                   self.phase + self.correction['phase_offset_i'])
        q = np.sin(2.0 * np.pi * (self.freq_if * t) +
                   self.phase + self.correction['phase_offset_q'])

        env = np.array([(np.cos(np.pi * (tt * 1.0e6/self.rise_time - 1.0)) + \
                           1.0)/2.0 if tt < 1.0e-6 * self.rise_time else (np.cos(np.pi * \
                         (tt - 1.0e-6 * (self.pulselength - self.fall_time))/\
                         (1.0e-6 * self.fall_time))  + 1.0)/2.0 if tt > 1.0e-6 *
                        (self.pulselength - self.fall_time) else 1.0 for tt in t]) 

        i = env * i
        q = env * q

# lo = np.sin( 2.0 * np.pi * 2.0e9 * t) # 2 GHz LO signal for test calculations
#        lo90 = np.sin ( 2.0 * np.pi * 2.0e9 * t + np.pi / 2.0)

        return Waveform(i, samplerate=self.samplerate), Waveform(q, samplerate=self.samplerate)

    def set_frequency(self, freq):
        self.freq = freq

        # Calculate the IF - Frequency
        if self.freq_lo:
            self.freq_if = self.freq - self.freq_lo
        else:
            self.freq_if = self.freq

    def function(self):
        # calculate number of points needed

        # Get the number of samplepoints needed
        samplepoints = int(round(self.samplerate * self.pulselength * 1.0e-6))
        self.t = np.array(xrange(samplepoints)) / self.samplerate

#        num_points = self.samplerate * self.pulselength / 1000000.0
#
# self.t = np.arange( 0.0, self.pulselength, 1000000.0 / self.samplerate)
        self.data = np.sin((2.0 * np.pi * self.freq) * self.t)


def plot(x, y):

    p = pg.plot(x=x, y=y)

    return p

def gen_sig_f_domain(numSamples, sampleRate, normalize = True):

    """
    Generate the signal in the frequency domain.

    :param numSamples: Number of points to sample
    :type numSamples: int
    :param sampleRate: Sample rate
    :type sampleRate: float
    """
    tone = np.linspace(-250.0e6, 250.0e6, 21)
    tone = np.array([-250.0e6])
    magSignal = np.zeros(numSamples)
    phaseSignal = np.zeros(numSamples)
    freqToPoints = numSamples / sampleRate

    magnitude = 10.0
    phase = 0.0

    # Place tones in frequency domain (with wrap-around)
    tonePtExact = np.mod(tone * freqToPoints + numSamples / 2.0, numSamples) \
            + 0 #- 1;
    # round to next frequency bin
    tonePoint = np.round(tonePtExact)

    # warn about round of frequencies, but allow some floating point inaccuracy
    if (np.max(np.abs(tonePoint - tonePtExact)) > 1.0e-10):
        print('Some tone frequencies were rounded - consider adjusting \
              Start/Stop frequency and number of tones')

    # generate complex frequency domain signal
    fSignal = []
    for tP in tonePoint:
        magSignal[tP] = np.power(10.0, magnitude / 20.0)
        phaseSignal[tP] = phase
    

    fSignal =  magSignal * np.exp(1.0j * phaseSignal)
    fSignal = np.array(fSignal)

    # convert signal into time domain
    iqdata = numSamples * ifft(fftshift(fSignal))

    # apply correction (TBD)

    # normalize
    if normalize:
        scale = np.max([np.max(np.abs(iqdata.real)),
                        np.max(np.abs(iqdata.imag))])
        iqdata = iqdata / scale

    return tone, fSignal, iqdata


def iqpulse(numSamples, sampleRate, span, pulseWidth, riseTime, fallTime, delay, phase, offset,
            pulseShape = 'raised cosine', chirpType = 'increasing', amplitude = 10.0, normalize =
            True):
    """
    """
    fmFormula = None
    pmFormula = None
    correction = None
    envelope = calcPulseShape(numSamples, 0, delay, riseTime, pulseWidth,
                              fallTime, sampleRate, pulseShape, amplitude)
    sig = calcPhase(numSamples, 0, delay, riseTime, pulseWidth, fallTime,
                         sampleRate, phase, span, offset, chirpType, fmFormula,
                         pmFormula, correction)
    iqdata = envelope * np.exp(1.0j * sig)
    #iqdata = power(10.0, mag/20.0 * iqdata)

    # normalize amplitude
    if normalize:
        scale = np.max([np.max(np.abs(iqdata.real)),
                        np.max(np.abs(iqdata.imag))])
        if scale > 1.0:
            iqdata = iqdata / scale

    return iqdata


def calcPulseShape(numSamples, pri, delay, riseTime, pulseWidth, fallTime, sampleRate,
                   pulseShape, amplitude):
    """
    Calculate the pulse shape.

    :param numSamples: Number of samples
    :type numSamples: int
    :param pri: Pulse repetition rate
    :type pri: float
    """
    envelope = np.zeros(int(numSamples))
    # create the envelope for the pulse
    linamp = np.power(10.0, amplitude / 20.0)
    # points in time on the pulse
    idx_delay = int(np.round(delay * sampleRate))
    idx_riseTime = int(np.round((delay + riseTime) * sampleRate))
    idx_pulseWidth = int(np.round((delay + riseTime + pulseWidth) * sampleRate))
    idx_fallTime = int(np.round((delay + riseTime + pulseWidth + fallTime) *
                           sampleRate))

    print(numSamples, idx_delay, idx_riseTime, idx_pulseWidth, idx_fallTime) 
    ridx = np.array(list(range(idx_delay, idx_riseTime)))
    pidx = np.array(list(range(idx_riseTime, idx_pulseWidth)))
    fidx = np.array(list(range(idx_pulseWidth, idx_fallTime)))

    # arguments for rise and falltime, scaled to [0...1] interval
    if (riseTime > 0.0):
        rr = (ridx / sampleRate - delay) / riseTime 
    else:
        rr = np.array([])
    if fallTime > 0.0:
        fr = (fidx / sampleRate - pulseWidth - riseTime - delay) / fallTime
    else:
        fr = np.array([])
    if (pulseShape.lower() == 'raised cosine'):
        rise_wave = (np.cos(np.pi * (rr - 1)) + 1) / 2.0
        fall_wave = (np.cos(np.pi * fr) + 1) / 2.0
    elif (pulseShape.lower() == 'trapezodial'):
        rise_wave = rr
        fall_wave = 1.0 - fr
    elif (pulseShape.lower() == 'zero signal during rise time'):
        rise_wave = np.zeros(len(rr))
        fall_wave = np.zeros(len(fr))
    else:
        raise exceptions.Exception

    for idx in ridx:
        envelope[idx] = linamp * rise_wave[idx - idx_delay]
    for idx in pidx:
        envelope[idx] = linamp
    for idx in fidx:
        envelope[idx] = linamp * fall_wave[idx - idx_pulseWidth]

    return envelope

def calcPhase(numSamples, pri, delay, riseTime, pulseWidth, fallTime,
              sampleRate, phase, span, offset, chirpType, fmFormula, pmFormula,
              correction):
    """
    """
    fm = np.zeros(int(numSamples))
    pm = np.zeros(int(numSamples))

    fmFormula = 'np.cos(np.pi*(x-1))'
    pmFormula = 'np.zeros(len(x))'

    fmFormula = fmFormula.replace('x','%s')
    pmFormula = pmFormula.replace('x','%s')

    # points in time on the pulse
    idx_delay = int(np.round(delay * sampleRate))
    idx_end = int(np.round((delay + riseTime + pulseWidth + fallTime) \
                          * sampleRate))

    pidx = np.array(list(range(idx_delay, idx_end)))
    pr = (pidx / sampleRate - delay) / (riseTime + pulseWidth + fallTime)

    fm_on = np.zeros(len(pr))
    pm_on = np.zeros(len(pr))

    if chirpType is None:
        pass
    elif chirpType.lower() == 'none':
        pass
    elif chirpType.lower() == 'increasing':
        fm_on = 2.0 * pr - 1.0 #-1
    elif chirpType.lower() == 'decreasing':
        fm_on = 1.0 - 2.0 * pr
    elif chirpType.lower() == 'v-shape':
        fm_on = 2.0 * np.abs(2.0 * pr - 1) - 1
    elif chirpType.lower() == 'inverted v':
        fm_on = -2.0 * np.abs(2.0 * pr - 1) - 1
    elif chirpType.lower() == 'barker-11':
        print("Not implemented yet. Nothing done")
    elif chirpType.lower() == 'barker-13':
        print("Not implemented yet. Noting done")
    elif chirpType.lower() == 'fmcw':
        fm_on = -2.0 * np.abs(2.0 * pr - 1.0) + 1.0
    elif chirpType.lower() == 'user defined':
        fm_on = eval(fmFormula % pr)
        pm_on = eval(pmFormula % pr)
    else:
        raise exceptions.Exception

    # scale frequency modulation to +/- span/2 and shift by offset
    fmTmp = (span/2.0 * fm_on) + offset
    # FM should start with 0, so the best might be to insert a zero at the
    # beginning and ignore the last sample
    fmTmp[1:] = fmTmp[:-1]
    fmTmp[0] = 0.0
    # store frequency for amplitude correction
    fm[pidx] = fmTmp
    # convert FM to PM (in units of rad/(2*Pi)
    pmTmp = np.cumsum(fmTmp) / sampleRate
    # initial phase need to reflect the offset of the first sample from the
    # 'ideal' pulse starting point
    dT = pidx[0] / sampleRate - delay
    pOffset = phase / 360.0 - fmTmp[1] + dT
    # add FM, PM and initial phase
    pm[pidx] = 2.0 * np.pi * (pmTmp + pm_on / 360.0 + pOffset)
    # finally, add correction depending on FM
    # TPD

    return pm #, mag


