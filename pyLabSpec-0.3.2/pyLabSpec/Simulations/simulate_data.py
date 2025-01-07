#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module defines classes which generate an ideal chirp pulse and
a plot of the result in both time and frequency domains.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import sys

import numpy as np
from scipy.special import fresnel
import matplotlib.pyplot as plt

if sys.version_info[0] == 3:
    xrange = range

class Chirp():
    """
    Defines all parameters of the chirp
    """
    def __init__(self, startfreq, stopfreq, pulselength, phase = 0.0):
        """
        Defines the chirped pulse signal

        :param startfreq: Start-Frequency of the Chirp in GHz
        :type startfreq: float
        :param stopfreq: Stop-Frequency of the Chirp in GHz
        :param pulselength: Pulselength in ns
        :param phase: Initial Phase in Degrees
        """
        self.startfreq = startfreq * 1.0e9
        self.stopfreq = stopfreq * 1.0e9
        self.pulselength = pulselength * 1.0e-9
        self.bandwidth = abs(self.stopfreq - self.startfreq)
        self.set_initial_phase(phase)
        self.centerfreq = self.startfreq + (self.stopfreq - self.startfreq) / 2.0

        if startfreq < stopfreq:
            self.sweepdirection = 'up'
        else:
            self.sweepdirection = 'down'
        self.sweeprate = self.bandwidth / self.pulselength

    def set_initial_phase(self, phase):
        """
        Sets the initial phase of the chirped pulse

        phase in degree
        """
        self.phase = np.pi * phase / 180.0

    def calc_iq_waveform(self, lo_freq = None, samplerate = 12.0e9, phase_offset_i = 0.0, phase_offset_q = 0.0):
        """
        Calculates and samples the waveform for the I and Q channels.

        Returns the sampled timesteps and the signals I, Q, 2GHz - LO and 2GHz - LO (90°)

        """
        # use center frequency of the chirp as default LO frequency
        if not lo_freq:
            lo_freq = self.centerfreq
        print("Set LO - Frequency to %lf" % lo_freq)
        startfreq = self.startfreq - lo_freq
        samplepoints = int(samplerate * self.pulselength)
        
        t = np.array(xrange(samplepoints)) / samplerate
        i = np.cos(2.0 * np.pi * (startfreq * t + 0.5 * self.sweeprate * t**2.0 ) + self.phase + phase_offset_i * np.pi / 180.0)
        q = np.sin(2.0 * np.pi * (startfreq * t + 0.5 * self.sweeprate * t**2.0 ) + self.phase + phase_offset_q * np.pi / 180.0)
        lo = np.sin( 2.0 * np.pi * 2.0e9 * t) # 2 GHz LO signal for test calculations
        lo90 = np.sin ( 2.0 * np.pi * 2.0e9 * t + np.pi / 2.0)
        return t, i, q, lo, lo90

    def get_phase(self, t):
        """
        Returns the phase at time t 
        """
        return 2.0 * np.pi * (self.startfreq*t + 0.5 * self.sweeprate * t**2.0) + self.phase 

    def get_signal(self, t):
        """
        Returns the normalized voltage at time t 
        """
        return np.cos(self.get_phase(t))

    def get_spectrum(self, f):
        """
        Gets the power spectrum at frequency f of the chirped pulse
        f in GHz
        """
        f = f * 1.0e9
        X1 = 2.0 * np.sqrt(np.pi) * ((self.bandwidth / 2.0) + f - self.centerfreq) / np.sqrt(self.bandwidth / self.pulselength)
        X2 = 2.0 * np.sqrt(np.pi) * ((self.bandwidth / 2.0) - f + self.centerfreq) / np.sqrt(self.bandwidth / self.pulselength)

        S1, C1 = fresnel(X1)
        S2, C2 = fresnel(X2)

        return np.sqrt(np.pi * self.pulselength / (2.0 * np.pi * self.bandwidth) * ( (C1 + C2)**2.0 + (S1 + S2)**2.0 ) )

    def plot_spectrum(self, numpoints = 1000):

        fig = plt.figure()
        ax = fig.add_subplot(111)

        x = self.startfreq - 0.5 * self.bandwidth + np.array(xrange(numpoints)) * 2.0 * self.bandwidth / numpoints
        y = self.get_spectrum(1.0e-9 *  x )

        ax.plot(x,y)
        plt.show()


def plot(x,y):

    fig = plt.figure()
    ax = fig.add_subplot(111)

    ax.plot(x,y)
    plt.show()



