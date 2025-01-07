#!/usr/bin/env python
# -*- coding: utf8 -*-
#
"""
This module provides classes and functions to conduct scripted/automated
measurements and data aquisitions.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import os
import sys
import time

import numpy as np
import matplotlib.pyplot as plt

if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from settings import *
from . import instrument as instr
from . import temperature_reading as tr
from . import pressure_gauges as pr
from Simulations import waveformbuilder as wb

if sys.version_info[0] == 3:
    xrange = range

###################################
# functions to control measurment
###################################

#def init_awg(host = AWG_HOST, port = AWG_PORT, samplerate = AWG_SAMPLERATE):
#    """
#    initializes the AWG.
#    """
#    awg = instr.awg(host = host, port = port)
#    return awg


#class Record():
#   
#    def __init__(self):
#        id = 1
#
#
#
#    def fft():
#      freqlist = np.fft.rfftfreq(len(rec),timeperdiv * 10.0 / len(rec))
#      spectrum = np.fft.rfft(spectrum)



class DataAcquisition():
    """
    This class provides functions to record spectra and aquire data.
    """
    def __init__(self, samplerate, acq_duration, channel = 1, num_averages = 10):
        """
        Initialize data acquisition:
        Sets samplerate, acquisition length

        :param samplerate: Samplerate in Sa/s
        :param acq_duration: Acquisition length in seconds
        """
        # set number of math-averages
        self.num_math_averages = num_averages

        self.scope = instr.Scope()

        self.scope.set_samplerate(samplerate)
        self.scope.wait()
        self.samplerate = self.scope.get_samplerate()
        self.scope.set_horizontal_scale(acq_duration / 10.0)
        self.scope.wait()
        # switch fast frame on
        self.scope.set_fast_frame(True)
        self.scope.wait()
        # select a very large number of frames in order to select max. value
        self.scope.set_num_frames(1000000)
        self.scope.wait()
        self.num_fast_frames = self.scope.get_num_frames()
        # select average (summary) frame mode
        self.scope.set_summary_frame_mode('AVERAGE')
        # apply math functions only on summary frame
        self.scope.set_math_on_summaryframe(True)
        # select last (summary) frame 
        self.scope.select_last_frame()
        last_frame = self.scope.get_selected_frame()
        if last_frame != self.num_fast_frames:
           print("Last frame was not selected. Please check manually!")

        # Define math functions (Average on math1, Spectrum on math2)
        self.scope.define_average(channel, 1, num_averages)
        self.scope.define_spectral_mag('MATH1', 2)

        # Define data transfer
        self.scope.set_encoding('ASCII')
        # transfer all the data of a waveform
        self.scope.set_transfer_range()
        # transfer only last (summary) frame
        self.scope.select_frame_for_transfer()

        # 
        self.tm = tr.TemperatureMonitor(port = '/dev/ttyUSB0')
        self.gauge = pr.Gauge(port = '/dev/ttyUSB1')

    def __del__(self):
        self.scope.close()

    def wait_for_averages(self):
        """
        Wait until the averages have been acquired by the scope.
        """
        init_acq = self.scope.get_num_acquisitions()
        curr_acq = init_acq
        while curr_acq < init_acq + self.num_math_averages * self.num_fast_frames:
           time.sleep(0.05)
           curr_acq = self.scope.get_num_acquisitions()

    def wait_for_temperature(self):
        """
        """
        init_temp = self.tm.getTemperature()
        cur_temp = init_temp
        while int(cur_temp) == int(init_temp):
           time.sleep(0.05)
           cur_temp = self.tm.getTemperature()

    def record(self, source = 'CH1'):
        """
        Get the data from the scope.
        """
        self.data = self.scope.get_curve() #get_next_curve()
        self.temperature = self.tm.getTemperature()
        self.pressure1 = self.gauge.read_pressure(gauge = 1)
        self.pressure2 = self.gauge.read_pressure(gauge = 2)

    def save_data(self, name = None):
        """
        Saves the last data.
        """
        timestamp = str(time.time()).replace('.','_')
        if not name:
           name = 'scope'
        temperature = '%d' % self.temperature
        fname = name + '_' + temperature + '_' + timestamp + '.dat'
        f = open(fname,'w')
        f.write('Temperature = %lf\n' % self.temperature)
        f.write('Pressure Chamber: %lf\n' % self.pressure1)
        f.write('Pressure Line: %lf\n' % self.pressure2)

        for data in self.data:
            f.write('%g\n' % data)
        f.close()
        
    def plot_data(self):
        t = [ x / self.scope.samplerate for x in xrange(len(self.data))]
        spec = pd.Spectrum(t, self.data)
        spec.plot()
