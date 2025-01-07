#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# TODO
# - add effects of digitilization (bit-noise and dynamic range)
# - improve simulation of line shapes (JCL: how exactly?)
#
"""
This package contains classes that are used to simulate spectra using
different kinds of detection techniques.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import sys
import os
import numpy as np

if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Spectrum import spectrum
import Catalog.catalog as cat

if sys.version_info[0] == 3:
    xrange = range

# constants
kB = 1.380310e-23 

XFFTS = {'samplerate': 5.0e9, 'bandwidth': 2.5e9, 'samplepoints':64 * 1024,
         'recordlength': ((64 * 1024) / 5.0e9 )}

class transitions():
    """
    Class that contains functions and methods to calculate and simulate line
    strength and handles parameters needed to calculate these.
    """
    def __init__(self, frequency, logint, p = 1.0, gamma = 1.0e5):
        """
        :param frequency: Transition frequency in MHz
        :type frequency: float
        :param logint: log intensitiy in nm^2 MHz
        :type logint: float
        :param p: pressure in microbar
        :type p: float
        :param gamma: gamma in Hz
        :type gamma: float
        """
        self.set_frequency(frequency * 1.0e6)
        self.set_intensity(logint)
        self.set_pressure(p=p)
        self.set_gamma(gamma = gamma)
        self.set_absorption_length(1.0)

    def set_intensity(self, logint):
        """
        :param logint: log intensitiy in nm^2 MHz
        :type logint: float
        """
        self.logint = logint
        self.intensity = np.power(10.0, logint)

    def set_frequency(self, frequency):
        """
        """
        self.frequency = frequency

    def set_gamma(self, gamma):
        """
        Sets the linewidth parameter
        """
        self.gamma = gamma

    def set_pressure(self, p = 1.0):
        """
        Set the pressure condition.

        :param p: Pressure in microbar
        :type p: float
        """
        self.p = p
        # Number density in 1/m^3
        self.N = p * 2.4 * 10.0**19
        print("Pressure: %lf micro-bar \nNumber density: %lf 1/m^3" % (self.p, self.N))

    def set_absorption_length(self, L):
        """
        Sets the length of the absorption path.

        :param L: length in [m]
        :type L: float
        """
        self.length = L

    def get_absorption_coefficient(self):
        """
        Calculates the absorption coefficient k_alpha
        """
        k_alpha = (3.0 * self.N) / (2.0 * np.pi**2.0 * self.gamma) \
                * self.intensity * 1.0e-12

        return k_alpha

    def get_absorbance(self):

        k_alpha = self.get_absorption_coefficient()
        A = k_alpha * self.length
        return A

    def get_absorptance(self):
        """
        """
        A = self.get_absorbance()
        return 1.0 - np.exp(-A)

    def get_transmission(self):
        """
        """
        A = self.get_absorbance()
        return np.exp(-A)

    def func_absorbtance(self, profile = 'Gaussian'):
        """
        returns a function that simulates the absortance.
        """
        fwhm = 2.0 * self.gamma
        intens = self.get_absorptance()

        def func(x):
            return cat.gaussian(x, self.frequency, intens, fwhm)

        return func

class heterodyne_receiver():
    """
    Class that contains functions and methods to simulate spectra and noise
    obtained with heterodyne receivers.
    """

    def __init__(self, rate = 5.0e9, recolength = 1.0e-4, nf = 10.0):
        """
        """
        self.reference_temperature = 290 # K
        self.set_noise_figure(nf = nf)
        self.set_sampling_rate(rate = rate)
        self.set_record_length(recolength = recolength)

    def set_sampling_rate(self, rate = 5.0e9):
        """
        Sets the sampling rate

        :param rate: sampling rate in Samples/s
        :type rate: float
        """
        self.sampling_rate = rate
        self.nyquist_bandwidth = rate / 2.0
        self.time_step = 1.0/rate
        if hasattr(self, 'record_length'):
            self.set_record_length(self.record_length)
        print("Sample rate: %lf GSa/s" % (self.sampling_rate / 1.0e9))
        print("Nyquist-Bandwidth: %lf GHz" % (self.nyquist_bandwidth / 1.0e9))

    def set_noise_figure(self, nf = 10.0):
        """
        Sets the noise figure.

        :param nf: noise figure in dB
        :type nf: float
        """
        nf = float(nf)
        self.noise_figure_factor = 10.0**(0.1 * nf)
        self.noise_figure = nf
        self.noise_temperature = self.reference_temperature \
                * (10.0**(nf / 10.0) - 1.0)
        print("Noise figure: %lf" % self.noise_figure)
        print("Noise temperature: %lf K" % self.noise_temperature)

    def set_noise_temperature(self, temperature = 290.0):
        temperature = float(temperature)
        self.noise_temperature = temperature
        self.noise_figure = 10.0 * np.log10(temperature /
                                            self.reference_temperature + 1.0)
        self.noise_figure_factor = 10.0**(0.1 * self.noise_figure)

        print("Noise figure: %lf" % self.noise_figure)
        print("Noise temperature: %lf K" % self.noise_temperature)


    def set_record_length(self, recolength = 1.0e-4):
        """
        Sets the record length of the recording.

        :param recolength: Record length in [s]
        :type recolength: float
        """
        self.record_length = recolength
        self.set_channel_bandwidth(1.0/recolength)
        self.num_samples = int(self.record_length / self.time_step)
        self.num_channels = int(self.nyquist_bandwidth / self.channel_bandwidth)
        self.time = np.array([ self.time_step * i for i in
                              xrange(self.num_samples)])
        print("Record length: %lf s" % recolength)
        print("# channels: %lf" % self.num_channels)

    def set_channel_bandwidth(self, bandwidth = 100.0e3):
        """
        Sets the channel bandwidth.
        """
        self.channel_bandwidth = bandwidth
        print("Channel Bandwidth: %lf Hz" % self.channel_bandwidth)

    def get_noise_power_per_channel(self):
        """
        Returns the noise power per channel in [W]
        """
        return kB * self.noise_temperature * self.channel_bandwidth 

    def get_noise_power_total(self):
        """
        Returns the total noise power in [W]
        """
        return kB * self.noise_temperature * self.nyquist_bandwidth

    def get_noise_voltage_time_step(self, impedance = 50.0):
        """
        Returns the noise voltage per time step in [V]
        """
        # factor 4 ignored sqrt(4kBTR), because that defines the
        # noise source not the extracted signal 
        #
        return np.sqrt(self.get_noise_power_total() * impedance) 

    def get_noise_voltage_per_channel(self, impedance = 50.0):
        """
        Returns the noise voltage per channel in [V].
        """
#        if integration_time is None:
#            integration_time = self.record_length

        # factor 4 ignored sqrt(4kBTR), because that defines the
        # noise source not the extracted signal 
        #

        return np.sqrt(self.get_noise_power_per_channel() * impedance)  

    def simulate_timedomain_noise(self, average = False, num_averages = 1):
        """
        Returns a function that models white noise with gaussian distribution.

        :param average: Specifies if spectrum shall be averaged in time domain
        :type average: boolean
        :param num_averages: number of averages in the time domain
        :type num_averages: int
        """
        
        noise = self.get_noise_voltage_time_step() 
        def func_noise(x = None):
            noise_arr = np.random.normal( scale = noise, size = x)
            if average:
                for i in xrange(num_averages - 1):
                    noise_arr += np.random.normal( scale = noise, size = x)
            return noise_arr
        return func_noise   

    def generate_noise_spectrum(self, recolength = 1.0e-4, print_info = True):
        """
        Returns a noise - spectrum.
        """
        self.set_record_length(recolength)
        noise_func = self.simulate_timedomain_noise()
        spec = spectrum.TimeDomainSpectrum(self.time,
                                           noise_func(len(self.time)))
        spec.calc_amplitude_spec(window_function = 'None')
        spec.calc_power_spec(window_function = 'None')

        rms_sig = 0
        rms_pow_sig = 0
        rms_amp_sig = 0
        for i in xrange(len(spec.x)):
            rms_sig += np.power(spec.y[i], 2.0)

        for i in xrange(len(spec.u_spec_win_x)):
            rms_amp_sig += np.power(spec.u_spec_win_y[i], 2.0)
            rms_pow_sig += spec.p_spec_win_y[i]

        rms_amp_sig = np.sqrt(rms_amp_sig / float(len(spec.u_spec_win_x)))
        rms_pow_sig = rms_pow_sig / float(len(spec.u_spec_win_x))
        rms_sig = np.sqrt(rms_sig / float(len(spec.x)))
        noise_temperature = rms_pow_sig / (kB * self.channel_bandwidth)

        if print_info:
            print("-----------------------------------------------------------")
            print("RMS - Noise - Signal: U^eff = U^rms = %g V, U^peak = %g" %
                  (rms_sig, np.sqrt(2)*rms_sig))
            print("RMS - Noise - Amplitude - Spectrum: U^eff = U^rms = %g V" % rms_amp_sig)
            print("Averaged Noise Power per Channel: %g W" % rms_pow_sig)
            print("Noise Temperature: %g K" % noise_temperature)
            print("-----------------------------------------------------------")
 
        return spec

    def generate_noise_power_spectrum(self, recolength = 1.0e-4, num_averages =
                                      1, print_info = True):
        """
        Returns a noise power spectrum averaged in frequency domain.
        """
        self.set_record_length(recolength)
 
        noise_func = self.simulate_timedomain_noise()
        spec = spectrum.TimeDomainSpectrum(self.time,
                                           noise_func(len(self.time)))
        spec.calc_power_spec(window_function = 'None')
        power_spec = spectrum.Spectrum(spec.p_spec_win_x, spec.p_spec_win_y)

        for i in xrange(num_averages - 1):
            noise_func = self.simulate_timedomain_noise()
            spec = spectrum.TimeDomainSpectrum(self.time,
                                               noise_func(len(self.time)))
            spec.calc_power_spec(window_function = 'None')
            power_spec.y += spec.p_spec_win_y

        power_spec.y = power_spec.y / float(num_averages)
        rms_pow_sig = 0

        for i in xrange(len(power_spec.x)):
            rms_pow_sig += power_spec.y[i]

        rms_pow_sig = rms_pow_sig / float(len(power_spec.x))
        noise_temperature = rms_pow_sig / (kB * self.channel_bandwidth)

        if print_info:
            print("-----------------------------------------------------------")
            print("Averaged Noise Power per Channel: %g W" % rms_pow_sig)
            print("Noise Temperature: %g K" % noise_temperature)
            print("-----------------------------------------------------------")
 
        return power_spec


class emission():
    """
    Class that contains functions and methods to simulate spectra obtained with
    an emission spectrometer based on heterodyne detectors.
    """

    def __init__(self,
                 transition,
                 background_temperature = 77.0, 
                 ambient_temperature = 290.0,
                 system_temperature = 100.0,
                 record_length = 1.0e-5,
                ):
        """
        """
        self.transition = transition
        self.receiver = heterodyne_receiver()
        self.set_ambient_temperature(temperature = ambient_temperature)
        self.set_system_temperature(temperature = system_temperature)
        self.set_background_temperature(temperature = background_temperature)
        self.set_record_length(recolength = record_length)

    def set_record_length(self, recolength = 1.0e-5):
        """
        Sets the record length of the recording.

        :param recolength: Record length in [s]
        :type recolength: float
        """
        self.record_length = recolength

    def set_pressure(self, p = 1.0):
        """
        Set the pressure condition.

        :param p: Pressure in microbar
        :type p: float
        """
        self.transition.set_pressure(p = p)

    def set_background_temperature(self, temperature = 77):
        """
        Sets the background temperature

        :param temperature: Temperature of the blackbody background in [K]
        :type temperature: float
        """
        self.background_temperature = temperature

    def set_ambient_temperature(self, temperature = 300.0):
        """
        Sets the temperature of the sample gas (and cell windows)

        :param temperature: Temperature of the blackbody background in [K]
        :type temperature: float
        """
        self.ambient_temperature = temperature

    def set_system_temperature(self, temperature = 100.0):
        """
        Sets the system temperature of the receiver.

        :param temperature: Temperature of the blackbody background in [K]
        :type temperature: float
        """
        self.system_temperature = temperature

    def set_number_of_averges(self, num_averages):
        """
        Sets the number of averages (integration time)
        """
        self.num_averages = num_averages

    def generate_background_spectrum(self):
        """
        Generates a spectrum of the blackbody background (e.g. 77K)
        """
        self.receiver.set_noise_temperature(self.background_temperature)
        self.background_spec = self.receiver.generate_noise_power_spectrum(
            recolength=self.record_length,
            num_averages=self.num_averages)

    def generate_ambient_spectrum(self):
        """
        Generates a spectrum of the blackbody background (e.g. 77K)
        """
        self.receiver.set_noise_temperature(self.ambient_temperature)
        self.ambient_spec = self.receiver.generate_noise_power_spectrum(
            recolength=self.record_length,
            num_averages=self.num_averages)

    def generate_system_spectrum(self):
        """
        Generates a spectrum of the blackbody background (e.g. 77K)
        """
        self.receiver.set_noise_temperature(self.system_temperature)
        self.system_spec = self.receiver.generate_noise_power_spectrum(
            recolength=self.record_length,
            num_averages=self.num_averages)

    def generate_hot_spectrum(self):
        """
        Generates a spectrum of the hot gas vs. cold background.
        """
        self.generate_background_spectrum()
        self.generate_system_spectrum()
        self.generate_ambient_spectrum()
        profile = self.transition.func_absorbtance()

        self.hot_spectrum = spectrum.Spectrum(self.background_spec.x, 
                                              self.system_spec.y +
                                              self.background_spec.y +
                                              self.ambient_spec.y *
                                              profile(self.ambient_spec.x)
                                             )


    def generate_cold_spectrum(self):
        """
        Generates a spectrum of the background only.
        """
        self.generate_background_spectrum()
        self.generate_system_spectrum()
        self.cold_spectrum = spectrum.Spectrum(self.background_spec.x,
                                               self.system_spec.y +
                                               self.background_spec.y)


class chirp():
    """
    Class that contains function and methods to simulate FID's obtained
    with a chirped pulse fourier transform spectrometer.
    """

    def __init__(self, transition):
        self.set_transition(transition)
        self.receiver = heterodyne_receiver()

       
        self.set_sampling_rate()
        self.set_temperature(300.0)
        self.set_record_length()
        self.set_waveguide_config()
        self.set_noise_figure()
        self.set_pressure()
        self.set_attenuation()
        self.set_power()
        self.set_sweep_rate(1.0)

    def set_transition(self, transition):
        """
        Sets a transition.
        """
        self.transition = transition

    def set_power(self, pwr = 1.0):
        """
        Sets the power of the signal source.

        :param pwr: Power in Watt
        :type pwr: float
        """
        self.power = pwr

    def set_attenuation(self, alpha = 0.14):
        """
        Sets the attenuation through the waveguide.

        :param alpha: attenuation in 1/m
        :type alpha: float
        """
        self.alpha = alpha
        print("Attenuation along path alpha: %lf" % self.alpha)
 
    def set_waveguide_config(self, L = 1.0, a = 15.7988, b = 7.8994):
        """
        Set waveguide dimensions.

        :param L: length of the absorbtion path (waveguide) in m
        :type L: float
        :param a: waveguide dimension in mm
        :type a: float
        :param b: waveguide dimension in mm
        :type b: float
        """
        self.a = a
        self.b = b
        self.L = L

    def set_pressure(self, p = 1.0):
        """
        Set the pressure condition.

        :param p: Pressure in microbar
        :type p: float
        """
        self.transition.set_pressure(p = p)

    def set_sampling_rate(self, rate = 5.0e9):
        """
        Sets the sampling rate

        :param rate: sampling rate in Samples/s
        :type rate: float
        """
        self.receiver.set_sampling_rate(rate)

    def set_noise_figure(self, nf = 10.0):
        """
        Sets the noise figure.

        :param nf: noise figure in dB
        :type nf: float
        """
        self.receiver.set_noise_figure(nf)

    def set_temperature(self, temperature = 300.0):
        self.temperature = temperature
        print("Background temperature: %lf" % self.temperature)

    def set_record_length(self, recolength = 10.0e-6):
        """
        Sets the record length of the recording.
        """
        self.receiver.set_record_length(recolength)

    def set_channel_bandwidth(self, bandwidth = 100.0e3):
        """
        Sets the channel bandwidth.
        """
        self.receiver.set_channel_bandwidth(bandwidth)

    def set_sweep_rate(self, alpha_sr):
        """
        Set the sweep rate of the chirp.

        :param alpha_sr: Chirp sweep rate in [GHz/microsec]
        :type alpha_sr: float
        """
        self.sweep_rate = alpha_sr * 1.0e15
        

    def calc_init_signal(self, beta = 1.0):
        """
        Calculates the signal Sab expected from the Chirped-Pulse Spectrometer.

        :param logI: Intensity in log nm^2MHz
        :type logI: float
        :param pwr: Power in [W]
        :type pwr: float
        :param gamma: decay rate Hz
        :type gamma: float
        :param beta: conversion gain of the detector
        :type beta: float
        """
        pwr = self.power
        I = self.transition.intensity
        gamma = self.transition.gamma

        # R = 50 Ohm
        R = 50 
        # group velocity
        cg = 3.0e8
        # 
        tau = 0.0
        y = 0.0
        # position perpendicular to the propagation axis in the waveguide
        x = self.a/2.0
        kc = np.pi / self.a
        term1 = np.sqrt(beta * R / (4.0 * np.pi**3.0)) * self.L * np.exp(-self.alpha * self.L / 2.0)
        term2 = np.sqrt(beta * pwr) * np.exp(-self.alpha * y / 2.0) * np.sin(kc * x)
        term3 = np.sqrt(1.0 / self.sweep_rate) * np.exp( gamma * (tau + self.L / cg))

        return 3.0 * self.transition.N * I * 1.0e-12 * term1 * term2 * term3

    def get_signal_envelope(self, beta = 1.0):

        sab0 = self.calc_init_signal(beta = beta)

        def Sab(t):
            return sab0 * np.exp(-self.transition.gamma * t)

        return Sab

    def get_avg_signal(self, beta = 1.0, time_start = 0.0, time_stop = 100.0e-6):

        sab0 = self.calc_init_signal(beta = beta)
        gamma = self.transition.gamma

        # check factor 0.5
        return -0.5 * sab0 / gamma * (np.exp(-gamma * time_stop) - np.exp(-gamma * time_start) ) / (time_stop - time_start)

    def get_snr(self, beta = 1.0, time_start = 0.0, time_stop = 100.0e-6, num_avg = 1):
        """
        Calculates the Signal to Noise ratio.
        """
        sig = self.get_avg_signal(beta = beta, time_start = time_start, time_stop = time_stop)
        noise = self.get_noise_voltage()
        return np.sqrt(num_avg) * sig / noise

    def fid(self, beta = 1.0):
        """
        Calculates the signal Sab expected from the Chirped-Pulse Spectrometer.

        :param beta: conversion gain of the detector
        :type beta: float
        """
        func = self.get_signal_envelope(beta = beta)
        frequency = self.transition.frequency
        def signal(t):
            return func(t) * np.sin(2.0 * np.pi * frequency * t) 

        return signal

    def generate_noise_spectrum(self, num_averages = 1.0):
         
         self.noise_spec = self.receiver.generate_noise_spectrum(
             recolength=self.receiver.record_length)
         if num_averages > 1:
             self.noise_spec.y = self.noise_spec.y / np.sqrt(num_averages)

#    def noise(self):
#        
#        noise = self.receiver.get_noise_voltage() * self.receiver.num_channels 
#        def func_noise(x = None):
#            return noise * 2.0 * (np.random.random(x) - 0.5)
#
#        return func_noise

    def generate_fid_spectrum(self, beta = 1.0, num_averages = 1.0):

        self.generate_noise_spectrum(num_averages = num_averages)
#        self.time = np.array([i * self.receiver.time_step for i in
#                             xrange(int(self.receiver.num_channels))])

        func = self.fid(beta = beta)
        self.fid_td_spec = spectrum.FID(self.receiver.time, func(self.receiver.time))
        self.fid_td_spec_noise = spectrum.FID(self.receiver.time, self.fid_td_spec.y +
                                           self.noise_spec.y)

        self.fid_td_spec_noise.calc_amplitude_spec()
        self.spectrum_noise = \
                spectrum.Spectrum(self.fid_td_spec_noise.u_spec_win_x,
                                  self.fid_td_spec_noise.u_spec_win_y)


class absorption():
    """
    Class that contains functions and methods to simulate spectra obtained with
    standard absorption spectrometers.
    """

    def __init__(self, 
                 transition,
                 modulation_frequency = 10.0e3,
                 modulation_depth = 100.0e3,
                 time_constant = 20.0e-3,
                ):

        self.set_modulation_frequency(modulation_frequency)
        self.set_modulation_depth(modulation_depth)
        self.set_responsivity() # sets the responsivity of the detector V/W
        self.set_system_nep()
        self.set_lo_power()
        self.set_responsivity()
        self.set_scan_range(-2.0e6, 2.0e6, 10.0e3)
        self.set_transition(transition)
        self.time = np.array([1.0e-6 * i  for i in xrange(10000)])
        self.set_time_constant_lockin(time_constant)

    def set_transition(self, transition):
        self.transition = transition

    def set_pressure(self, p = 1.0):
        self.transition.set_pressure(p = p)

    def set_scan_range(self, start, stop, step):
        self.start_freq = start
        self.stop_freq = stop
        self.step_size = step

        if self.stop_freq <= self.start_freq:
            print("Stop Frequency has to be larger than Start-Frequency.")
            return

        self.freq_list = []
        self.num_points = int( (self.stop_freq - self.start_freq) / self.step_size )

        for i in xrange(self.num_points):
            self.freq_list.append(self.start_freq + i * self.step_size)

    def set_modulation_frequency(self, modulation_frequency):
        self.modulation_frequency = modulation_frequency

    def set_modulation_depth(self, modulation_depth):
        self.modulation_depth = modulation_depth

    def set_time_constant_lockin(self, time_constant = 20.0e-3):
        self.time_constant = time_constant

    def set_system_nep(self, nep = 1.0e-9):
        """
        Sets the NEP of the detector.

        :param nep: NEP in W/sqrt(Hz)
        :type nep: float
        """
        self.system_nep = nep
        self.optical_nep = nep / self.responsivity

    def set_lo_power(self, power = 0.0001):
        """
        Sets power of local oscillator (signal source).

        :param power: power in [W]
        :type power: float
        """
        self.lo_power = power

    def set_responsivity(self, responsivity = 4000.0):
        """
        Sets the repsonsivity of the detector.

        :param responsivity: responsivity in V/W
        :type responsivity: float
        """
        self.responsivity = responsivity

    def get_oscillator(self):
        """
        Generates the oscillator function.
        """

        def func(t):
            return self.modulation_depth * np.sin(2.0 * np.pi * self.modulation_frequency * t)

        return func

    def get_signal(self):
        
        sig_mod = self.get_oscillator()
        profile = self.transition.func_absorbtance()

        spec_1f = []
        spec_2f = []
        idx_f1 = 0
        for freq in self.freq_list:
            tspec = spectrum.TimeDomainSpectrum(self.time, profile(freq + sig_mod(self.time)))
            tspec.calc_amplitude_spec()
            tspec.calc_phase_spec()
            if idx_f1 == 0:
                idx_f1 = np.abs(tspec.u_spec_win_x - self.modulation_frequency).argmin()
                idx_f2 = np.abs(tspec.u_spec_win_x - 2.0 * self.modulation_frequency).argmin()
                print(idx_f1, idx_f2)

            spec_1f.append(tspec.u_spec_win_y[idx_f1] *
                           np.sin(tspec.phase_spec_win_y[idx_f1]))
            spec_2f.append(tspec.u_spec_win_y[idx_f2] *
                           np.cos(tspec.phase_spec_win_y[idx_f2]))

        self.spec_1f = spectrum.Spectrum(self.freq_list, self.lo_power * np.array(spec_1f))
        self.spec_2f = spectrum.Spectrum(self.freq_list, self.lo_power * np.array(spec_2f))
        peak_int_2f = np.max(self.spec_2f.y)
        peak_int_1f = np.max(self.spec_1f.y)
        noise_voltage = self.system_nep / np.sqrt(self.time_constant) / \
                self.responsivity
        print("Peak Intensity 2f: %g V, 1f: %g V, rms_noise: %g V" % (peak_int_2f,
                                                                      peak_int_1f,
                                                                      noise_voltage))
        print("Number of frequency points: %d" % len(self.freq_list))
        print("Total integration time: %g s" % (self.time_constant *
                                              len(self.freq_list)))

    def generate_noise(self, num_points = None):
        """
        Generates noise.
        """
        if num_points is None:
            num_points = max(len(self.freq_list), 1000)

        # use function from class heterodyne receiver to calculate a noise
        # spectrum corresponding to the nep
        det = heterodyne_receiver()
        det.set_sampling_rate(float(num_points) * 1.0e4 * 2.0)
        det.set_record_length(1.0e-4)
        noise_voltage = self.system_nep / np.sqrt(self.time_constant)

        det.set_noise_temperature(self.system_nep**2.0 / \
                                  (50.0 * kB * det.channel_bandwidth))
        nspec = det.generate_noise_spectrum()
        noise_points = nspec.u_spec_win_y 
        self.noise = spectrum.Spectrum(self.freq_list,
                                       noise_points[:len(self.freq_list)] /
                                       self.responsivity)


    def simulate_spectrum(self):
        """
        Simulates the spectrum including noise.
        """
        self.get_signal()
        self.generate_noise()
        self.spec_1f_noise = spectrum.Spectrum(self.spec_1f.x, self.spec_1f.y +
                                               self.noise.y)
        self.spec_2f_noise = spectrum.Spectrum(self.spec_2f.x, self.spec_2f.y +
                                               self.noise.y)
