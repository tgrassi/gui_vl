#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# TODO
# - add loading of CLASS spectral files?
#   - refs:
#       GILDAS documentation: https://www.iram.fr/IRAMFR/GILDAS/gildasli3.html
#       internal CLASS format: https://www.iram.fr/IRAMFR/GILDAS/doc/html/class-html/node55.html
#       classic data container: https://www.iram-institute.org/medias/uploads/classic-data-container.pdf
#       additional slides about format: http://www.iram.es/IRAMES/events/summerschool2015/presentations/pety-bardeau-gratier-class-tutorial-ss15.pdf#page=93
#       pygildas/pyclass tips: http://www.carsten-koenig.de/tutorials/blog-post/2018/04/03/using-gildasclass-from-python/
#   - also older versions (pre-2014)?
# - add checks for rest of filetypes
#   - open each file to check contents?
#   - CASAC
#   - GESP
#   - Hiden CSV
#   - Batop T3DS
"""
This package contains classes and methods used to load/store/process
experimental data.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
import logging, logging.handlers
logformat = '%(asctime)s - %(name)s:%(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=logformat)
log = logging.getLogger("spectrum-%s" % os.getpid())
logpath = os.path.expanduser("~/.log/pyLabSpec/spectrum.log")
try:   # automatically try to recursively create directories
    os.makedirs(os.path.dirname(logpath))
except:
	pass
try:
    loghandler = logging.handlers.RotatingFileHandler(logpath, maxBytes=5e5, backupCount=10)
    loghandler.setFormatter(logging.Formatter(logformat))
    log.addHandler(loghandler)
except:
    e = sys.exc_info()
    log.info("warning: couldn't set up a log handler at '%s' (e: %s)" % (logpath, e))
import re
import datetime
import warnings
import collections
# thirdy-party
import numpy as np
#from matplotlib import pylab
from scipy import optimize
import matplotlib.pyplot as plt
import pyqtgraph as pg
from pyqtgraph import exporters
from scipy import fftpack, signal
from scipy import interpolate
# local
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import bruker_opus_filereader
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import Fit.fit as fit
from miscfunctions import siEval, datetime2sec

# python 3 compatibility
if sys.version_info[0] == 3:
    xrange = range

# Constants
c = 2.99792458e8
K_to_wvn = 0.69503476
scanindex2opusblock = {1:"AB", 2:"ScSm", 3:"ScRf", 4:"IgSm", 5:"IgRf"}

#----------------------------------------------------------------------
# General classes
#----------------------------------------------------------------------

class Spectrum(object):

    """
    This class defines an object that contains spectral information (spectrum).
    """


    def __init__(self, x, y, dx = None, dy = None, **kwds):
        """
        Initializes the spectrum.

        :param x: x-axis data points
        :param y: y-axis data points
        :param dx: x-axis error data points
        :param dy: y-axis error data points
        """
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy

        # make sure x, y are numpy-arrays
        self.x = np.array(self.x)
        self.y = np.array(self.y)

        # Save a copy of the original data. This data is never modified and
        # allows to restore the original data at any time.
        self.raw_x = x
        self.raw_y = y

        # Push any keywords to attributes of this instance
        self.update(**kwds)

    def update(self, **kwds):
        """
        Update the instance with a dictionary containing its new properties.
        """
        for ck in kwds.keys():
            if ck in vars(self).keys():
                self.__dict__.update({ck: kwds[ck]})
            else:
                setattr(self, ck, kwds[ck])

    def restore(self):
        """
        Restore the orignal data.
        """
        self.x = self.raw_x
        self.y = self.raw_y

    def plot(self, filename=None, xlabel=None, ylabel=None, legend=None,
             with_points = False, with_errors = False, with_fits = False,
             with_residual = False, x_range = None, y_range = None
            ):
        """
        Plots the spectrum (to file or screen).

        :param filename: filename to which the spectrum is saved (if specified).
        :type filename: string
        :param xlabel: Label for the x-axis
        :type xlabel: string
        :param ylabel: Label for the y-axis
        :type ylabel: string
        :param legend: Legend for the plot
        :type legend: string
        :param with_points: Show only points (not connected)
        :type with_points: boolean
        :param with_errors: Show errorbars
        :type with_errors: boolean
        :param with_fits: Add curve (e.g. fit (fit_x, fit_y))
        :type with_fits: boolean
        """
        if 'p' in vars(self).keys():
            # check if window is closed and create a new window if so
            if self.p.closed:
                self.p = pg.plot()
            # show window if it is hidden
            if not self.p.isVisible():
                self.p.parent().setVisible(True)
            self.p.clear()
            self.p.plot(x = self.x, y = self.y, clear = True)
        else:
            self.p = pg.plot()

        if not with_points:
            self.p.plot(x = self.x, y = self.y)
        elif with_errors:
            if not hasattr(self, 'dx'):
                self.dx = 0.0
            if not hasattr(self, 'dy'):
                self.dy = 0.0
            points = pg.ErrorBarItem(x = self.x, y = self.y,
                                     top = self.dy, bottom = self.dy,
                                     left = self.dx, right = self.dx)
            self.p.addItem(points)
        else:
            points = pg.ErrorBarItem(x = self.x, y = self.y)
            self.p.addItem(points)

        if with_fits and hasattr(self, 'fit_x') and hasattr(self, 'fit_y'):
            self.p.plot(self.fit_x, self.fit_y, pen = (1,5))

        if with_residual and hasattr(self, 'fit_x') and hasattr(self, 'fit_y'):
            self.p.plot(self.fit_x, self.y - self.fit_y, pen = (2,5))



        labelStyle = {'color': '#FFF', 'font-size': '14pt'}
        if xlabel: self.p.setLabel('bottom', xlabel, **labelStyle)
        if ylabel: self.p.setLabel('left', ylabel, **labelStyle)
        if hasattr(self, 'unit_x'): self.p.setLabel('bottom', units = self.unit_x)
        if hasattr(self, 'unit_y'): self.p.setLabel('left', units = self.unit_y)
        if x_range is not None:
            self.p.setXRange(x_range[0], x_range[1])
        if y_range is not None:
            self.p.setYRange(y_range[0], y_range[1])
        if filename:
            exporter = exporters.ImageExporter(self.p.plotItem)
            exporter.export(filename)
        return


    def get_maximum(self, xmin=None, xmax=None):
        """
        Returns the maximum value of y within the specified range (xmin, xmax)

        :param xmin: lower limit of the search range
        :type xmin: float
        :param xmax: upper limit of the search range
        :type xmax: float
        :rtype: float
        """
        if not xmin:
            xmin = min(self.x)
        if not xmax:
            xmax = max(self.x)

        return max([self.y[i] for i in xrange(len(self.x)) if self.x[i] >= xmin and self.x[i] <= xmax])

    def get_intensity(self, x):
        """
        Returns the intensity of the bin closest to the specified x-value

        :param x: value on the x axis whose y value will be returned
        :type x: float
        :rtype: float
        """
        idx = abs(self.x - x).argmin()
        return self.y[idx]

    def get_rms_noise(self, xmin=None, xmax=None):
        """
        Returns the maximum value of y within the specified range (xmin, xmax)

        :param xmin: lower limit of the search range
        :type xmin: float
        :param xmax: upper limit of the search range
        :type xmax: float
        :rtype: float
        """
        if not xmin:
            xmin = min(self.x)
        if not xmax:
            xmax = max(self.x)

        idx_start = self.get_xindex(xmin)
        idx_stop = self.get_xindex(xmax)

        rms = 0
        for i in xrange(idx_start, idx_stop):
            rms += np.power(self.y[i], 2)

        return np.sqrt(rms / float(idx_stop - idx_start))

    def get_xindex(self, x):
        """
        Returns the index of the position, whose x-value is closest to the given
        value.

        :param x: x-value
        :type x: float
        """
        return np.abs(self.x  - x).argmin()

    def crop(self, xmin, xmax):
        """
        Crops the spectrum to the given x-range.

        :param xmin: start-value
        :type xmin: float
        :param xmax: stop-value
        :type xmax: float
        """
        idx_min = self.get_xindex(xmin)
        idx_max = self.get_xindex(xmax)
        self.x = self.x[idx_min:idx_max]
        self.y = self.y[idx_min:idx_max]

    def get_maximum_position(self, xmin = None, xmax = None, unit = 'xunit'):
        """
        Returns the position (x-axis) of the maximum (y-axis)

        :param xmin: lower limit of the search range
        :type xmin: float
        :param xmax: upper limit of the search range
        :type xmax: float
        :rtype: float
        """
        if not xmin:
            idxmin = 0
        else:
            idxmin = abs(self.x - xmin).argmin()
        if not xmax:
            idxmax = len(self.x) - 1
        else:
            idxmax = abs(self.x - xmax).argmin()

        if unit == 'xunit':
            return self.x[idxmin + self.y[idxmin:idxmax].argmax()]
        else:
            return idxmin + self.y[idxmin:idxmax].argmax()

    def save(self, filename, ftype = 'xydata', overwrite = True):
        """
        Saves the spectrum to file.

        :param filename: Filename
        :param ftype: data format (xydata: asci (x  y), npy: Numpy binary)
        :type filename: str
        :type ftype: str
        """
        if os.path.exists(filename) and not overwrite:
            print("File already exists")
            return

        if hasattr(self, 'dy') and self.dy is not None:
            error_col = True
        else:
            error_col = False

        if ftype == 'xydata':
            f = open(filename, 'w')
            if error_col:
                for i in xrange(len(self.x)):
                    f.write('%.10g  %.10g  %.10g\n' % (self.x[i],
                                                       self.y[i],
                                                       self.dy[i]))
            else:
                for i in xrange(len(self.x)):
                    f.write('%.10g  %.10g\n' % (self.x[i], self.y[i]))
            f.close()
        elif ftype == 'npy':
            if error_col:
                np.save(filename, (self.x, self.y, self.dy))
            else:
                np.save(filename, (self.x, self.y))
        else:
            print("Unkown file format:\n Known formats are 'xydata', 'npy'")

    def calc_background(self, num_points):
        """
        Calculates a background spectrum by getting the minimum in the vicinity of each frequency point.
        """
        self.backgr = np.zeros(len(self.x))
        for i in xrange(len(self.y)):
            try:
                minval = min(self.y[i-num_points:i+num_points])
                if minval == 0.0:
                    minval = lastval
                self.backgr.put(i, minval)
                lastval = minval
            except:
                print(i)
                self.backgr.put(i, self.y[i])

    def smooth(self, num_points):
        """
        Calculates a background spectrum by getting the minimum in the vicinity of each frequency point.
        """
        num_data_points = len(self.x)
        self.smoothed_spectrum = np.zeros(num_data_points)
        for i in xrange(num_data_points):
            idx_from = max(i - num_points, 0)
            idx_to = min(num_data_points, i + num_points)

            self.smoothed_spectrum.put(i,np.average(self.y[idx_from:idx_to]))

class SpectrumList(object):
    """
    This class contains a list of Spectrum types and methods that are applied to
    the list.
    """
    x = []
    spectra = {}
    N = 0 # number of spectra

    def __init__(self, x, y, **kwds):
        """
        :param x: list of xdata or list of list of xdata
        :type x: list
        :param y: list of y-data points or list of list of y-data points
        :type y: list
        """
        if len(x) == 0:
            pass
        elif len(x) > 0 and type(x[0]) != list:
            self.x = x
            x = [x]
        if len(y) == 1 and type(y[0]) != list:
            y = [y]

        if len(x) == 1 and len(y)>1:
            for i, ydata in enumerate(y):
                self.spectra[i] = Spectrum(x[0], ydata)
        else:
            for i, ydata in enumerate(y):
                self.spectra[i] = Spectrum(x[i], ydata)
        self.N = len(self.spectra)

        # Push any keywords to attributes of this instance
        self.update(**kwds)

    def update(self, **kwds):
        """
        Update the instance with a dictionary containing its new properties.
        """
        for ck in kwds.keys():
            if ck in vars(self).keys():
                self.__dict__.update({ck: kwds[ck]})
            else:
                setattr(self, ck, kwds[ck])

    def addSpectrum(self, spectrum):
        """
        adds a spectrum to the array.

        :param spectrum: spectrum to add
        :type spectrum: Spectrum
        """
        i = max([int(j) for j in self.spectra.keys()]) + 1
        self.spectra[i] = spectrum
        self.N = i + 1

    def average(self, imin = 0, imax = None, check = False):
        """
        averages all spectra.

        :param imin: index to start averaging from
        :type imin: int
        :param imax: index to stop averaging to
        :type imax: int
        :param check: check if x-data is the same for all spectra.
        :type check: Boolean
        """
        if check:
            for i in self.spectra.keys():
                if (spectra[0].x != spectra[i].x).max():
                    print("x-axis contain different data points!")
                    return

        avg_y = np.zeros(len(self.spectra[0].x))

        for i in self.spectra.keys():
            avg_y += self.spectra[i].y

        return Spectrum(self.spectra[0].x, avg_y)/len(spectra)


#----------------------------------------------------------------------
# Format-specific classes
#----------------------------------------------------------------------

class IQSpectrum(SpectrumList):
    """
    """
    def __init__(self, x, y, **kwds):
        super(IQSpectrum, self).__init__(x, y, **kwds)

        self.init_iq()
        self.calc_sample_rate()

    def init_iq(self):
        self.t = self.spectra[0].x
        self.i = self.spectra[0].y
        self.q = self.spectra[1].y

    def restore(self):

        self.init_iq()

    def calc_sample_rate(self):
        """
        Calculates the sample rate based on the assumption of equally spaced sample points
        """
        if len(self.t) > 1:
            self.samplerate = 1.0 / (self.t[1] - self.t[0])

    def calc_amplitude_spec(self, time_start=0.0, time_stop=1.0e9,
                            window_function = 'Hann', zero_filling = False):
        self.h = np.imag(signal.hilbert(self.q))
        self.u = self.i + self.h
        self.l = self.i - self.h

        # calculate fft
        #fft = spectrum.fftpack.fft(spec_i.y + h_q)
        if time_start is None:
            xmin = np.argmax(self.u)
        else:
            xmin = np.min([i for i in xrange(len(self.t)) \
                           if self.t[i] >= time_start])
        if not time_stop:
            xmax = np.argmin(self.u)
        else:
            xmax = np.max([i for i in xrange(len(self.t)) \
                           if self.t[i] <= time_stop])

        self.spec_x_u, self.spec_y_u, self.spec_win_x_u, self.spec_win_y_u = \
                calc_amplitude_spec(self.t[xmin:xmax], self.u[xmin:xmax], \
                                self.samplerate, window_function=
                                window_function, zero_filling = zero_filling)

        self.spec_x_l, self.spec_y_l, self.spec_win_x_l, self.spec_win_y_l = \
                calc_amplitude_spec(self.t[xmin:xmax], self.l[xmin:xmax], \
                                self.samplerate,
                                    window_function=window_function,
                                    zero_filling=zero_filling)

        self.spec_win_x = np.concatenate((-self.spec_win_x_l[::-1],
                                          self.spec_win_x_u))

        self.spec_x = np.concatenate((-self.spec_x_l[::-1],
                                          self.spec_x_u))

        self.spec_win_y = np.concatenate((self.spec_win_y_l[::-1],
                                          self.spec_win_y_u))

        self.spec_y = np.concatenate((self.spec_y_l[::-1],
                                          self.spec_y_u))

        self.amplitude_spec = Spectrum(self.spec_win_x, self.spec_win_y, unit_x =
                                   'Hz', unit_y = 'V')
        self.raw_amplitude_spec = Spectrum(self.spec_x, self.spec_y)


    def plot_amplitude_spec(self, time_start = 0.0, time_stop = 1.0e9,
                            window_function = 'Hann', zero_filling =
                            False):
        """
        """
        self.calc_amplitude_spec(time_start = time_start, time_stop = time_stop,
                                window_function = window_function, zero_filling
                                = zero_filling)
        self.amplitude_spec.plot()

    def calc_power_spec(self, time_start=0.0, time_stop=1.0e9, window_function =
                       'Hann', zero_filling = False):
        self.h = np.imag(signal.hilbert(self.q))
        self.u = self.i + self.h
        self.l = self.i - self.h

        # calculate fft
        #fft = spectrum.fftpack.fft(spec_i.y + h_q)
        if time_start is None:
            xmin = np.argmax(self.u)
        else:
            xmin = np.argmin([np.abs(t - time_start) for t in self.t]) + 1

        if not time_stop:
            xmax = np.argmin(self.u)
        else:
            xmax = np.argmin([np.abs(t - time_stop) for t  in self.t]) - 1

        self.spec_x_u, self.spec_y_u, self.spec_win_x_u, self.spec_win_y_u = \
                calc_power_spec(self.t[xmin:xmax], self.u[xmin:xmax], \
                                self.samplerate, window_function=
                                window_function, zero_filling = zero_filling)

        self.spec_x_l, self.spec_y_l, self.spec_win_x_l, self.spec_win_y_l = \
                calc_power_spec(self.t[xmin:xmax], self.l[xmin:xmax], \
                                self.samplerate,
                                window_function=window_function,
                                zero_filling = zero_filling)

        self.spec_win_x = np.concatenate((-self.spec_win_x_l[::-1],
                                          self.spec_win_x_u))

        self.spec_x = np.concatenate((-self.spec_x_l[::-1],
                                          self.spec_x_u))

        self.spec_win_y = np.concatenate((self.spec_win_y_l[::-1],
                                          self.spec_win_y_u))

        self.spec_y = np.concatenate((self.spec_y_l[::-1],
                                          self.spec_y_u))


        self.power_spec = Spectrum(self.spec_win_x, self.spec_win_y, unit_x =
                                   'Hz', unit_y = 'W')
        self.raw_power_spec = Spectrum(self.spec_x, self.spec_y)


    def plot_power_spec(self, time_start = 0.0, time_stop = 1.0e9,
                        zero_filling = False):
        """
        """
        self.calc_power_spec(time_start = time_start, time_stop = time_stop)
        self.power_spec.plot()

    def save(self, filename, wdir, overwrite = False, ftype = 'xyzdata'):
        """
        Saves the spectrum
        """
        if wdir[-1] != '/':
            wdir += '/'

        if os.path.exists(wdir + filename) and not overwrite:
            print("File already exists")
            return

        if ftype == 'xyzdata':
            f = open(wdir + filename, 'w')
            for i in xrange(len(self.t)):
                f.write('%.10g  %.10g  %.10g \n' % (self.t[i], self.i[i], self.q[i]))
            f.close()
        elif ftype == 'npy':
            np.save(wdir + filename, (self.t, self.i, self.q))
        else:
            print("Unkown file format.\n Known formats are 'xyzdata', 'npy'!")

    def get_envelope(self, method = 'iq', slice_length=0.1, frequency = None):
        """
        Determines the envelope of the spectrum.

        :param method: Determines how the envelope is determined:
                       slices - Time-domain spectrum is sliced and maximum is determined;
                       slices_fft - FFT of small time windows is done and intensity at the frequency is retrieved;
                       iq - sqrt( i**2 + q**2) is calculated.
        :param slice_length: Length of the slice in the time-domain
        :param frequency: Frequency point whose intensity is retrieved
        """
        x = self.t
        y = np.sqrt(self.i**2.0 + self.q**2.0)

        if method == 'slices':
            sl = slice_spectrum(x, y, self.sampling_rate, slice_length=slice_length)

            xx = []
            yy = []

            for slice in sl:
                yy.append(max(slice[1]))
                xx.append(min(slice[0]) + (max(slice[0]) - min(slice[0])) / 2.0)
        elif method == 'slices_fft':
            xx = []
            yy = []
            min_t = np.min(self.t)
            max_t = np.max(self.t)
            for i in range(int(round( (max_t - min_t) / slice_length))):
                self.calc_amplitude_spec(time_start = min_t + i * slice_length,
                                         time_stop = min_t + (i+1) *
                                         slice_length, zero_filling =
                                         zero_filling)
                if frequency is not None:
                    idx = np.abs(self.amplitude_spec.x  - frequency).argmin()
                    xx.append(min_t + (i + 0.5) * slice_length)
                    yy.append(self.amplitude_spec.y[idx])
                else:
                    # return 2d array
                    xx.append(min_t + (i + 0.5) * slice_length)
                    yy.append(self.amplitude_spec.y)
        else:
            xx = x
            yy = y
        self.env_x = xx
        self.env_y = yy

    def fit_envelope(self, method = 'hilbert', slice_length=0.1, time_start=None,
                     time_stop=None, threshold=None, fixedDecay=None):

        # calculate envelope again with specified slice length
        self.get_envelope(method = method, slice_length=slice_length)
        # Just fit the range between max and min in order to skip initial switch on phase
        # and background limited long range
        if time_start is None:
            xmin = np.argmax(self.env_y)
        else:
            xmin = np.argmin([np.abs(t - time_start) for t in self.env_x]) + 1
        if not time_stop:
            xmax = np.argmin(self.env_y)
        else:
            xmax = np.argmin([np.abs(t - time_stop) for t in self.env_x]) - 1

        # check when the threshold is reached and set max point accordingly
        if threshold:
            xmax_t = np.argmin(
                np.abs(self.env_y[xmin:] - threshold * np.ones(len(self.env_x[xmin:]))))
            if xmax_t + xmin < xmax:
                xmax = xmax_t + xmin

        self.logenv = np.array([np.log(y) for y in self.env_y])
        if xmax - xmin < 2:
            print('Curve below threshold! Not enough data points!')
            self.decayrate = None
            self.intensity = None
            return

        init_a = (self.logenv[xmax] - self.logenv[xmin]) / \
                (self.env_x[xmax] - self.env_x[xmin])
        out = fit.fit_linear(
            y = self.logenv[xmin:xmax],
            x = self.env_x[xmin:xmax],
            init_a = init_a,
            init_b = 0.0, output = 'param') #, fixedDecay=fixedDecay)
        if fixedDecay:
            self.decayrate = fixedDecay
        else:
            self.decayrate = -out[0][0]
            self.decayrate_err = out[1][0]
        self.intensity = np.exp(out[0][1])
        self.intensity_err = np.abs(self.intensity * out[1][1])

        return out

    def filter_spectrum(self, flow = 0.0, fhigh = 30.0e9):

        x, self.q = filter_spectrum(self.t, self.q, self.samplerate,
                                    flow=flow, fhigh=fhigh)
        x, self.i = filter_spectrum(self.t, self.i, self.samplerate,
                                    flow=flow, fhigh = fhigh)


class TimeDomainSpectrum(Spectrum):

    """
    This class defines an object that contains a Time domain spectrum.

    It includes various methods and functions which are useful in order to
    analyze the spectrum.
    """

    def __init__(self, x, y, **kwds):
        """
        Initializes an instance of FID.

        :param x: x-axis data points (time) in s
        :type x: list of float
        :param y: y-axis data points (signal) in V
        :type y: list of float
        """
        super(TimeDomainSpectrum, self).__init__(x, y, **kwds)

        # calculates and sets the sample rate
        self.calc_sample_rate()

    def calc_sample_rate(self):
        """
        Calculates the sample rate based on the assumption of equally spaced sample points
        """
        if len(self.x) > 1:
            self.samplerate = 1.0 / (self.x[1] - self.x[0])

    def crop(self, start, stop):
        """
        Crop everything which is not in the specified range

        :param start: lower end of the x-axis
        :type start: float
        :param stop: upper end of the x-axis
        :type stop: float
        """

        self.y = np.array([self.y[i] for i in xrange(len(self.x)) \
                           if self.x[i] > start and self.x[i] < stop])
        self.x = np.array([self.x[i] for i in xrange(len(self.x)) \
                           if self.x[i] > start and self.x[i] < stop])

    def filter(self, flow, fhigh):
        """
        Applies a bandpass filter to the data.

        :param flow: Low pass frequency cut-off
        :type flow: float
        :param fhigh: High pass frequency cut-off
        :type fhigh: float
        """
        if not self.samplerate:
            self.calc_sample_rate()

        self.x, self.y = filter_spectrum(
            self.x, self.y, self.samplerate, flow=flow, fhigh=fhigh)

    def calc_amplitude_spec(self,
                            window_function='Hamming',
                            time_start=None,
                            time_stop=None,
                            zero_filling = False,
                           ):
        """
        Calculates and sets the amplitude spectrum of the FID (FFT).

        :param window_function: Window-function which is used in the FFT.
        :type window_function: string
        :param time_start: Skip data before time_start (also possible: 'min_y'
                           and 'max_y')
        :type time_start: float (or str)
        :param time_stop: Skip data after time_stop (also possible: 'min_y'
                          and 'max_y')
        :type time_stop: float (or str)

        """
        # Just calculated the range between max and min in order to skip initial switch on phase
        # and background limited long range
        if type(time_start) == str:
            if time_start == 'max_y':
                xmin = np.argmax(self.y)
            if time_start == 'min_y':
                xmin = np.argmin(self.y)
        else:
            if time_start is None:
                xmin = 0
            else:
                xmin = np.argmin([np.abs(t - time_start) for t in self.x])
                if self.x[xmin] < time_start:
                    xmin += 1
        if type(time_stop) == str:
            if time_stop == 'max_y':
                xmax = np.argmax(self.y)
            if time_stop == 'min_y':
                xmax = np.argmin(self.y)
        else:
            if time_stop is None:
                xmax = len(self.x)
            else:
                xmax = np.argmin([np.abs(t - time_stop) for t in self.x])
                if self.x[xmax] > time_stop:
                    xmax -= 1

        self.u_spec_x, self.u_spec_y, self.u_spec_win_x, self.u_spec_win_y = \
                calc_amplitude_spec( self.x[xmin:xmax], self.y[xmin:xmax], \
                                    self.samplerate,  window_function=
                                    window_function, zero_filling = zero_filling)

    def plot_amplitude_spec(self, window_function='Hamming', time_start=None,
                            time_stop=None, filename=None, zero_filling = False):
        """
        Plots the amplitude (V) spectrum of the FID (FFT) .

        :param window_function: Window-function which is used in the FFT.
        :type window_function: string
        :param window_function: Window-function which is used in the FFT.
        :type window_function: string
        :param time_start: Skip data before time_start (also possible: 'min_y'
                           and 'max_y')
        :type time_start: float (or str)
        :param time_stop: Skip data after time_stop (also possible: 'min_y'
                          and 'max_y')
        :type time_stop: float (or str)

        """
        self.calc_amplitude_spec(
            window_function=window_function, time_start=time_start,
            time_stop=time_stop, zero_filling = zero_filling)

        plt = pg.plot(self.u_spec_win_x, self.u_spec_win_y, title = "FFT Amplitude Spectrum")
        plt.setLabel('left','Signal', 'V')
        plt.setLabel('bottom', 'Frequency', 'Hz')

        if filename:
            exporter = pg.exporters.ImageExporter(plt.plotItem)
            exporter.export(filename)

        return plt


    def calc_power_spec(self, window_function='Hamming', time_start=None,
                        time_stop=None, zero_filling = False):
        """
        Calculates and sets the power spectrum of the FID (FFT). If time_start is None then
        the time when the signal is maximal will be used as start time.

        :param window_function: Window-function which is used in the FFT.
        :type window_function: string
        :param window_function: Window-function which is used in the FFT.
        :type window_function: string
        :param time_start: Skip data before time_start (also possible: 'min_y'
                           and 'max_y')
        :type time_start: float (or str)
        :param time_stop: Skip data after time_stop (also possible: 'min_y'
                          and 'max_y')
        :type time_stop: float (or str)

        """
        # Just calculated the range between max and min in order to skip initial switch on phase
        # and background limited long range
        if type(time_start) == str:
            if time_start == 'max_y':
                xmin = np.argmax(self.y)
            if time_start == 'min_y':
                xmin = np.argmin(self.y)
        else:
            if time_start is None:
                xmin = 0
            else:
                xmin = np.argmin([np.abs(t - time_start) for t in self.x])
                if self.x[xmin] < time_start:
                    xmin += 1
        if type(time_stop) == str:
            if time_stop == 'max_y':
                xmax = np.argmax(self.y)
            if time_stop == 'min_y':
                xmax = np.argmin(self.y)
        else:
            if time_stop is None:
                xmax = len(self.x)
            else:
                xmax = np.argmin([np.abs(t - time_stop) for t in self.x])
                if self.x[xmax] > time_stop:
                    xmax -= 1

        self.p_spec_x, self.p_spec_y, self.p_spec_win_x, self.p_spec_win_y = calc_power_spec(
            self.x[xmin:xmax], self.y[xmin:xmax], self.samplerate,
            window_function= window_function, zero_filling = zero_filling)

    def plot_power_spec(self, window_function='Hamming', time_start=None,
                        time_stop=None, filename=None, zero_filling = False):
        """
        Plots the power spectrum of the FID (FFT).

        :param window_function: Window-function which is used in the FFT.
        :type window_function: string
        """
        self.calc_power_spec(
            window_function=window_function, time_start=time_start,
            time_stop=time_stop, zero_filling = zero_filling)

        plt = pg.plot(self.p_spec_win_x, self.p_spec_win_y, title = "FFT Power Spectrum")
        plt.setLabel('left','Signal', 'W')
        plt.setLabel('bottom', 'Frequency', 'Hz')

        if filename:
            exporter = pg.exporters.ImageExporter(plt.plotItem)
            exporter.export(filename)

        return plt

    def calc_phase_spec(self, window_function='Hamming', time_start=None,
                            time_stop=None, zero_filling = False):
        """
        Calculates and sets the phase spectrum of the FID (FFT).

        :param window_function: Window-function which is used in the FFT.
        :type window_function: string
        :param time_start: Skip data before time_start (also possible: 'min_y'
                           and 'max_y')
        :type time_start: float (or str)
        :param time_stop: Skip data after time_stop (also possible: 'min_y'
                          and 'max_y')
        :type time_stop: float (or str)

        """
        # Just calculated the range between max and min in order to skip initial switch on phase
        # and background limited long range
        if type(time_start) == str:
            if time_start == 'max_y':
                xmin = np.argmax(self.y)
            if time_start == 'min_y':
                xmin = np.argmin(self.y)
        else:
            if time_start is None:
                xmin = 0
            else:
                xmin = np.argmin([np.abs(t - time_start) for t in self.x])
                if self.x[xmin] < time_start:
                    xmin += 1
        if type(time_stop) == str:
            if time_stop == 'max_y':
                xmax = np.argmax(self.y)
            if time_stop == 'min_y':
                xmax = np.argmin(self.y)
        else:
            if time_stop is None:
                xmax = len(self.x)
            else:
                xmax = np.argmin([np.abs(t - time_stop) for t in self.x])
                if self.x[xmax] > time_stop:
                    xmax -= 1

        self.phase_spec_x, self.phase_spec_y, self.phase_spec_win_x, self.phase_spec_win_y = \
                calc_phase_spec( self.x[xmin:xmax], self.y[xmin:xmax], \
                                    self.samplerate,  window_function=
                                window_function, zero_filling = zero_filling)


    def get_max_amplitude(self, xmin=None, xmax=None, window_function='Hamming',
                      time_start=None, time_stop=None, zero_filling = False):
        """
        Returns the maximum value of y within the specified range (xmin, xmax)

        :param xmin: lower limit of the search range
        :type xmin: float
        :param xmax: upper limit of the search range
        :type xmax: float
        :rtype: float
        """
        self.calc_amplitude_spec(
            window_function=window_function, time_start=time_start,
            time_stop=time_stop, zero_filling = zero_filling)

        if not xmin:
            xmin = min(self.u_spec_win_x)
        if not xmax:
            xmax = max(self.u_spec_win_x)

        return max([self.u_spec_win_y[i] for i in xrange(len(self.u_spec_win_x))
                    if self.u_spec_win_x[i] >= xmin and self.u_spec_win_x[i] <= xmax])


class FID(TimeDomainSpectrum):

    """
    This class defines an object that contains the FID spectrum.

    It includes various methods and functions which are useful in order
    to analyze the FID.
    """

    decayrate = None

    def __init__(self, x, y, **kwds):
        """
        Initializes an instance of FID.

        :param x: x-axis data points (time) in s
        :type x: list of float
        :param y: y-axis data points (signal) in V
        :type y: list of float
        """
        super(FID, self).__init__(x, y, **kwds)

        # calculates and sets the envelope
        # self.get_envelope()

    def filter(self, flow, fhigh):
        """
        Applies a bandpass filter to the data.

        :param flow: Low pass frequency cut-off
        :type flow: float
        :param fhigh: High pass frequency cut-off
        :type fhigh: float
        """
        super(FID, self).filter(flow, fhigh)

        # update the envelope
        self.get_envelope()

    def get_envelope(self, method = 'hilbert', slice_length=0.1):
        """
        Calculates and sets the envelope of the FID (just positive slope).

        The method defines how the envelope is determined. 'hilbert' uses the
        Hilbert - Tranformation and 'slices' devides the Spectrum into slices
        and the maximum of each slice is determined.

        :param method: Defines the method used to determine envelope ('hilbert',
             'slices'
        :type slice_length: float
        """
        x, y = get_envelope(
            self.x, self.y, method, self.samplerate, slice_length=slice_length)
        self.env_x = np.array(x)
        self.env_y = np.array(y)

    def plot_envelope(self, slice_length=0.1, type=None, filename=None):
        """
        Plots only the envelope of the FID.

        :param slice_length: Length of each slice
        :type slice_length: float
        :param type: normal or log - plot (default: normal)
        :type type: string
        :param filename: filename to save the plot to
        :type filename: string
        """
        self.get_envelope(slice_length=slice_length)
        # plt.cla()
        fig = plt.figure()
        ax = fig.add_subplot(111)
        # set labels
        ax.set_xlabel('time [s]')
        if type == 'log':
            ax.plot(self.env_x, np.log(self.env_y))
            ax.set_ylabel('Log(Intensity / V)')
        else:
            ax.plot(self.env_x, self.env_y)
            ax.set_ylabel('Intensity [V]')

        if self.decayrate:
            if type == 'log':
                ax.plot(
                    self.env_x, [np.log(self.intensity) - self.decayrate * x for x in self.env_x])
                # show fit result
                ax.text(0.7, 0.8, 'T = %lf' %
                        self.decayrate, transform=ax.transAxes)
                ax.text(0.7, 0.7, 'I = %g' %
                        self.intensity, transform=ax.transAxes)
            else:
                ax.plot(self.env_x, [self.intensity * np.exp(- self.decayrate * x)
                        for x in self.env_x])

        ax.grid(True)
        if filename:
            fig.savefig(filename)
        else:
            plt.show()

        return fig

    def fit_envelope(self, method = 'hilbert', slice_length=0.1, time_start=None, time_stop=None, threshold=None, fixedDecay=None):
        """
        Fits the envelope (positive slope) of the FID and set the decay rate and the intensity.

        :param slice_length: Length of each slice.
        :type slice_length: float
        :param time_start: Rejects all datapoints recorded earlier than time_start from the fit.
        :type time_start: float
        :param time_stop: Rejects all datapoints recorded later than time_stop from the fit.
        :type time_stop: float
        :param threshold: Rejects all datapoints that are recorded after the threshold is reached.
        :type threshold: float
        """
        # calculate envelope again with specified slice length
        self.get_envelope(method = method, slice_length=slice_length)
        # Just fit the range between max and min in order to skip initial switch on phase
        # and background limited long range
        if time_start is None:
            xmin = np.argmax(self.env_y)
        else:
            xmin = np.argmin([np.abs(t - time_start) for t in self.env_x]) + 1
        if not time_stop:
            xmax = np.argmin(self.env_y)
        else:
            xmax = np.argmin([np.abs(t - time_stop) for t in self.env_x]) - 1

        # check when the threshold is reached and set max point accordingly
        if threshold:
            xmax_t = np.argmin(
                np.abs(self.env_y[xmin:] - threshold * np.ones(len(self.env_x[xmin:]))))
            if xmax_t + xmin < xmax:
                xmax = xmax_t + xmin

        self.logenv = np.array([np.log(y) for y in self.env_y])
        if xmax - xmin < 2:
            print('Curve below threshold! Not enough data points!')
            self.decayrate = None
            self.intensity = None
            return

        init_a = (self.logenv[xmax] - self.logenv[xmin]) / \
                (self.env_x[xmax] - self.env_x[xmin])
        out = fit.fit_linear(
            y = self.logenv[xmin:xmax],
            x = self.env_x[xmin:xmax],
            init_a = init_a,
            init_b = 0.0, output = 'param') #, fixedDecay=fixedDecay)
        if fixedDecay:
            self.decayrate = fixedDecay
        else:
            self.decayrate = -out[0][0]
            self.decayrate_err = out[1][0]
        self.intensity = np.exp(out[0][1])
        self.intensity_err = np.abs(self.intensity * out[1][1])

        return out


#----------------------------------------------------------------------
# General functions
#----------------------------------------------------------------------

def load_file(
    filename, ftype='tekscope-csv', # JCL: would probably be best for ftype to not be optional..
    samplerate=3.125e9,
    skipFirst=False,
    xcol=1, ycol=2,
    delimiter=",",
    scanindex=0,
    unit=None,
    mass=None):
    """
    Loads a measurement-file from the given location and returns list of data

    :param ftype: file format (tekscope-csv, ocf (one column format))
    """
    header = []
    f = open(filename, mode='rU')

    log.info("processing file %s" % f)

    # process data
    x = []  # X-Axis
    y = []  # Y-Axis
    header = collections.OrderedDict()
    if ftype == 'ocf':
        for line in f:
            line = line.replace('=', ':')
            if len(line.split(':')) > 1:
                info = line.split(':')
                header[info[0].strip()] = info[1].strip()
                continue
            y.append(float(line.strip()))
        x = [i / samplerate for i in xrange(len(y))]
        header['samplerate'] = samplerate
    elif ftype == 'xydata':
        x, y, header = loadfile_arbdelim(filename,
            skipFirst = skipFirst, xcol = xcol, ycol = ycol,
            delimiter = r'\s+')
    elif ftype == 'ydata':
        x, y, header = loadfile_ydata(filename,
            skipFirst=skipFirst)
    elif ftype.lower() == 'csv':
        x, y, header = loadfile_arbdelim(filename,
            skipFirst=skipFirst, xcol=xcol, ycol=ycol,
            delimiter=',')
    elif ftype.lower() == 'tsv':
        x, y, header = loadfile_arbdelim(filename,
            skipFirst=skipFirst, xcol=xcol, ycol=ycol,
            delimiter=r'\t+')
    elif ftype.lower() == 'ssv':
        x, y, header = loadfile_arbdelim(filename,
            skipFirst=skipFirst, xcol=xcol, ycol=ycol,
            delimiter=r'\s+')
    elif ftype.lower() == 'arbdelim':
        x, y, header = loadfile_arbdelim(filename,
            skipFirst=skipFirst, xcol=xcol, ycol=ycol,
            delimiter=delimiter)
    elif ftype.lower() == 'fits':
        x, y, header = loadfile_fits(filename, primHDU=scanindex)
    elif ftype.lower() == 'hidencsv':
        x, y, header = loadfile_hidencsv(filename,
            cycle=scanindex, unit=unit, mass=mass)
    elif ftype.lower() == 'brukeropus':
        x, y, header = loadfile_brukeropus(filename, scanindex=scanindex)
    elif ftype.lower() == 'batopt3ds':
        x, y, header = loadfile_batopt3ds(filename)
    elif ftype.lower() == 'gesp':
        x, y, header = loadfile_gesp(filename)
    elif ftype.lower() == 'casac':
        x, y, header = loadfile_casac(filename)
    elif ftype.lower() == 'jpl':
        x, y, header = loadfile_jpl(filename, scanindex=scanindex)
    elif ftype.lower() == 'npy':
        data = np.load(filename)
        x = data[0]
        if len(data[1:]) == 1:
            y = data[1]
        else:
            y = data[1:]
    else:
        for line in f:
            data = line.split(',')
            if data[0:3] != ['', '', '']:
                if data[0]:
                    header[data[0]] = data[1]
            try:
                x.append(float(data[3]))
                y.append(float(data[4].strip()))
            except Exception as e:
                print(e)
    f.close()
    return header, x, y

def loadfile_ydata(filename, skipFirst=True):
    """
    Import an arbitrarily-delimited file.
    """
    try:
        if sys.version_info[0] == 3:
            fileHandle = open(filename, mode='r', encoding='utf-8')
        else:
            fileHandle = open(filename, mode='rU')
    except IOError:
        err_str = "%s: file could not be loaded" % (filename)
        raise IOError(err_str)

    xdata, ydata = [], []
    c = []
    numPoints = 0

    for i,line in enumerate(fileHandle):
        if line[0]=="#":
            c.append(line.strip())
            continue
        else:
            if skipFirst:
                skipFirst=False
                continue
            xdata.append(i)
            try:
                ydata.append(float(line.strip()))
            except ValueError:
                pass
            numPoints += 1

    # Process data
    xdata = np.array(xdata)
    ydata = np.array(ydata)

    # update class data
    header = collections.OrderedDict([
        ('sourcefile', os.path.abspath(filename)),
        ('loadTime', str(datetime.datetime.now())),
        ('xrange', float(xdata.max() - xdata.min())),
        ('yrange', float(ydata.max() - ydata.min())),
        ('numPoints', numPoints)
    ])
    # add keys to built-in pretty-printed header
    h = []
    for k,v in header.items():
        h.append("%s: %s" % (k, v))
    h += c
    header['ppheader'] = h

    fileHandle.close()
    return xdata, ydata, header

def loadfile_arbdelim(filename, delimiter=',', skipFirst=True, xcol=1, ycol=2):
    """
    Import an arbitrarily-delimited file.
    """
    try:
        if sys.version_info[0] == 3:
            fileHandle = open(filename, mode='r', encoding='utf-8')
        else:
            fileHandle = open(filename, mode='rU')
    except IOError:
        err_str = "%s: file could not be loaded" % (filename)
        raise IOError(err_str)

    xdata, ydata = [], []
    c = []
    numPoints = 0

    for i,line in enumerate(fileHandle):
        if line[0]=="#":
            c.append(line.strip())
            continue
        else:
            if skipFirst and i==0:
                skipFirst=False
                continue
            try:
                xdata.append(float(re.split(delimiter,line.strip())[int(xcol-1)])) # new style, using regex
                ydata.append(float(re.split(delimiter,line.strip())[int(ycol-1)]))
            except ValueError:
                msg = "%s: received a non-number at line #%s" % (filename, int(i+1))
                print(msg)
            numPoints += 1

    # Process data
    xdata = np.array(xdata)
    ydata = np.array(ydata)

    # update class data
    header = collections.OrderedDict([
        ('sourcefile', os.path.abspath(filename)),
        ('loadTime', str(datetime.datetime.now())),
        ('xrange', float(xdata.max() - xdata.min())),
        ('yrange', float(ydata.max() - ydata.min())),
        ('numPoints', numPoints),
        ('xunit', None),
        ('yunit', None),
    ])
    # add keys to built-in pretty-printed header
    h = []
    for k,v in header.items():
        h.append("%s: %s" % (k, v))
    h += c
    header['ppheader'] = h

    fileHandle.close()
    return xdata, ydata, header

def loadfile_jpl(filename, scanindex=0):
    """
    Import an arbitrarily-delimited file.
    """
    try:
        if sys.version_info[0] == 3:
            fileHandle = open(filename, mode='r', encoding='utf-8')
        else:
            fileHandle = open(filename, mode='rU')
    except IOError:
        err_str = "%s: file could not be loaded" % (filename)
        raise IOError(err_str)
    if not scanindex:
        raise SyntaxError(
            "You must specify which scanindex to use for the desired "
            "spectrum (1 for first scan, 2 for second, etc...): %s." % scanindex)

    scanLineNums = []
    scanTot = []
    timestamp = 0
    sh = 0
    it = 0
    detAmplitude = 0
    detSamplerate = 0
    modFrequency = 0
    modAmplitude = 0
    title = ""
    freqStart = 0
    freqStep = 0
    numPoints = 0
    numScans = 0
    multFact = 0
    ydata = ""
    xdata = []

    # loop through file, to determine line numbers associated with the beginning of each scan
    lines = fileHandle.readlines()
    for i,line in enumerate(lines):
        if line[:4]=="DATE":
            scanLineNums.append(i)
    scanTot = len(scanLineNums)
    # check against scanindex again
    if scanindex > scanTot:
        msg = "You requested scan index %s" % scanindex
        msg += ", but the file only contains %s scans!" % scanTot
        raise IOError(msg)
    # collect scan data
    lineStart = scanLineNums[scanindex-1]
    lineEnd = scanLineNums[scanindex]
    for i,line in enumerate(lines[lineStart:lineEnd]):
        if i == 0:
            lineTemp = re.split('\s+', line)
            timestamp = "%s %s" % (lineTemp[1], lineTemp[3])
            sh = int(lineTemp[5])
            it = int(lineTemp[7])
            detAmplitude = float(lineTemp[9])
            detSamplerate = float(lineTemp[11])
            modFrequency = float(lineTemp[13])
            modAmplitude = float(lineTemp[15])
        elif i == 1:
            title = "%s" % line.strip() # formatting ensures it is never None, even if blank
        elif i == 2:
            lineTemp = re.split('\s+', line)
            freqStart = float(lineTemp[0])
            freqStep = float(lineTemp[1])
            numPoints = int(lineTemp[2])
            numScans = float(lineTemp[3])
            multFact = float(lineTemp[4])
        else:
            ydata += "%s " % line.strip()
    # process data
    ydata = re.split('\s+', ydata)[:-1]
    ydata = list(map(float, ydata))
    if not len(ydata) == numPoints:
        msg = "data appears incomplete; "
        msg += "there was a mismatch between numPoints (%s) " % numPoints
        msg += "and the actual length (%s)" % len(ydata)
        raise IOError(msg)
    for i in range(numPoints):
        xdata.append(freqStart + i*freqStep)
    xdata = np.array(xdata)
    ydata = np.array(ydata)

    # update class data
    header = collections.OrderedDict([
        ("title", title),
        ('sourcefile', os.path.abspath(filename)),
        ('loadTime', str(datetime.datetime.now())),
        ('scanindex', scanindex),
        ("timestamp", timestamp),
        ('sh', sh),
        ('it', it),
        ("detAmplitude", detAmplitude),
        ("detSamplerate", detSamplerate),
        ("modFrequency", modFrequency),
        ("modAmplitude", modAmplitude),
        ("freqStart", freqStart),
        ("freqStop", float(xdata[-1])),
        ("freqStep", freqStep),
        ("numPoints", numPoints),
        ("numScans", numScans),
        ("multFact", multFact),
        ('xrange', float(xdata.max() - xdata.min())),
        ('yrange', float(ydata.max() - ydata.min())),
        ('xunit', "MHz"),
        ('yunit', "arb"),
    ])
    # add keys to built-in pretty-printed header
    h = []
    for k,v in header.items():
        h.append("%s: %s" % (k, v))
    header['ppheader'] = h

    fileHandle.close()
    return xdata, ydata, header

def loadfile_gesp(filename):
    """ Import a GESP spectrum file. """

    try:
        if sys.version_info[0] == 3:
            fileHandle = open(filename, mode='r', encoding='utf-8')
        else:
            fileHandle = open(filename, mode='rU')
    except:
        err_str = "{}: file not found".format(filename)
        raise NameError(err_str)

    ysp = []
    xsp = []
    timestamp = 0
    title = 0
    detAmplitude = 0
    detSamplerate = 0
    yrange = 0
    freqStart = 0
    freqStop = 0
    freqStep = 0
    numPoints = 0
    multFact = 0
    scanTime = 0
    numScans = 0

    nstep = 0
    for (nl,line) in enumerate(fileHandle):
        # Input first line
        if nl == 0:
            tt = re.split('\,', line)
            dtt = tt[0].replace('"',' ').strip() + " " \
                + tt[1].replace('"',' ').strip()
            tit = tt[2].replace('"',' ').strip()
            timestamp = dtt
            title = tit
            detAmplitude = float(tt[3])
            detSamplerate = float(tt[4])
            yrange = float(tt[5])
            freqStart = float(tt[6])
            freqStop = float(tt[7])
            freqStep = float(tt[8])
            continue

        # Input second line
        if nl == 1:
            tt = re.split('\,', line)
            numPoints = int(tt[0])
            multFact = int(tt[1])
            scanTime = float(tt[2])
            numScans = int(tt[3])
            continue

        # Input y-data
        tt = line.split()
        ysp.append(float(tt[0]))
        nstep += 1

    # Check data consistency
    if nstep != numPoints:
        err_str = "{}: GESP file is incomplete!".format(filename)
        raise NameError(err_str)

    # set the xdata & convert both to numpy array
    for ns in range(numPoints):
        xsp.append(freqStart + freqStep*ns)
    xsp = np.array(xsp)
    ysp = np.array(ysp)

    header = collections.OrderedDict([
        ("title", title),
        ("timestamp", timestamp),
        ('sourcefile', os.path.abspath(filename)),
        ('loadTime', str(datetime.datetime.now())),
        ("freqStart", freqStart),
        ("freqStop", freqStop),
        ("freqStep", freqStep),
        ('xrange', float(xsp.max() - xsp.min())),
        ('yrange', float(ysp.max() - ysp.min())),
        ("numPoints", numPoints),
        ("detAmplitude", detAmplitude),
        ("detSamplerate", detSamplerate),
        ("multFact", multFact),
        ("scanTime", scanTime),
        ("numScans", numScans),
        ('xunit', "MHz"),
        ('yunit', "arb"),
    ])
    # add keys to built-in pretty-printed header
    h = []
    for k,v in header.items():
        h.append("%s: %s" % (k, v))
    header['ppheader'] = h

    fileHandle.close()
    return xsp, ysp, header

def loadfile_fits(filename,
    primHDU=0, unit="MHz"):
    """ Import a FITS file. """

    try:
        fileHandle = open(filename, mode='rU')
    except:
        err_str = "{}: file not found".format(filename)
        raise NameError(err_str)
    fileHandle.close()

    ysp = []
    xsp = []
    title = 0
    yrange = 0
    freqStart = 0
    freqStop = 0
    freqStep = 0
    numPoints = 0
    multFact = 0
    scanTime = 0
    numScans = 0
    xunit = None
    yunit = None

    if primHDU is None: # ensure this is an int
        primHDU = 0
    # use astropy for getting the header
    try:
        import astropy
        from astropy.io import fits
        hdul = fits.open(filename)
        hdu = hdul[primHDU]
        hdu.data = hdu.data # force load before closing the file
    except:
        print("received an unexpected error while retrieving the header using astropy!")
        raise
    # try various methods of loading the data (refs: astropy and pyspeckit)
    try:
        hdr = hdu.header
        data = np.ma.array(hdu.data).squeeze()
        yunit = hdr.get("BUNIT")
        if hdr.get('XTENSION') == 'BINTABLE':
            xsp, ysp = zip(*data)
            xsp = np.asarray(xsp)
            ysp = np.asarray(ysp)
        else:
            ysp = data
            n = np.arange(len(ysp))
            v0 = 0
            dv = 0
            pix = 0
            origin = hdr.get('ORIGIN')
            if origin == 'CLASS-Grenoble':
                if hdr.get('CTYPE1') == "FREQ":
                    dv = hdr.get('CDELT1')
                    if hdr.get('RESTFREQ'):
                        v0 = hdr.get('RESTFREQ') + hdr.get('CRVAL1')
                    elif hdr.get('RESTF'):
                        v0 = hdr.get('RESTF') + hdr.get('CRVAL1')
                    else:
                        warn("CLASS file does not have RESTF or RESTFREQ")
                    pix = hdr.get('CRPIX1')
                    xconv = lambda n, v0, dv, pix: (n-pix+1)*dv + v0
                    xsp = xconv(n, v0, dv, pix) / 1e6
                    xunit = "MHz"
                else:
                    msg = "this FITS file comes from Grenoble is not using a FREQ for AXIS1 and cannot be loaded yet!"
                    msg += "\nthe header follows here:\n%s" % repr(hdr)
                    raise NotImplementedError(msg)
            elif origin == 'CASA Viewer / Spectral Profiler':
                if hdr.get('CTYPE1') == "VRAD":
                    dv = hdr.get('CDELT1')
                    v0 = hdr.get('CRVAL1')
                    pix = hdr.get('CRPIX1')
                    restfreq = hdr.get('RESTFRQ') / 1e6
                    xconv = lambda n, v0, dv, pix: (n-pix+1)*dv + v0
                    xsp = xconv(n, v0, dv, pix) # in velocity...
                    xsp = (1 - xsp/2.99792458e8) * restfreq
                    xunit = "MHz"
                else:
                    msg = "this FITS file comes from CASA is not using VRAD (m/s) for AXIS1 and cannot be loaded yet!"
                    msg += "\nthe header follows here:\n%s" % repr(hdr)
                    raise NotImplementedError(msg)
            else:
                msg = "this FITS file comes from %s and cannot yet be loaded!" % origin
                raise NotImplementedError(msg)
        hdul.close()
    except:
        print("\nThere was a problem while loading the FITS file! Here's the contents of the file:")
        print("\t%s" % hdul.info())
        print("\nNote that you tried loading spectrum No.: %s\n" % primHDU)
        print("Its header contains:\n%s" % repr(hdr))
        hdul.close()
        raise
    ## use pyspeckit for quick and dirty loading of xy data
    #try:
    #    import pyspeckit
    #    sp = pyspeckit.Spectrum(filename)
    #    sp.xarr.convert_to_unit(unit)
    #    inds = np.argsort(sp.xarr)
    #    xsp = sp.xarr.value[inds]
    #    ysp = sp.data[inds]
    #except ImportError:
    #    print("couldn't import 'pyspeckit'.. try running 'sudo pip install pyspeckit'")
    #    raise
    #except:
    #    print("there was an unexpected error loading the fits file '%s'!" % filename)
    #    raise

    header = collections.OrderedDict([
        ("title", title),
        ('sourcefile', os.path.abspath(filename)),
        ('loadTime', str(datetime.datetime.now())),
        ("freqStart", xsp[0]),
        ("freqStop", xsp[-1]),
        ("freqStep", float(xsp[1]-xsp[0])),
        ('xrange', float(xsp.max() - xsp.min())),
        ('yrange', float(ysp.max() - ysp.min())),
        ("numPoints", len(xsp)),
        ('hdu', hdu),
        ('xunit', xunit),
        ('yunit', yunit),
    ])
    # update header with all the FITS header entries
    for h in hdu.header:
        header[h] = hdu.header[h]
    # add keys to built-in pretty-printed header
    h = []
    for k,v in header.items():
        if (k == "hdu") or (not len(k)):
            continue
        h.append("%s: %s" % (k, v))
    header['ppheader'] = h

    return xsp, ysp, header

def loadfile_casac(filename):
    """ Import a CASAC file. """
    try:
        if sys.version_info[0] == 3:
            fileHandle = open(filename, mode='r', encoding='utf-8')
        else:
            fileHandle = open(filename, mode='rU')
    except IOError:
        err_str = "%s: file could not be loaded" % (filename)
        raise IOError(err_str)

    paramsCollected = collections.OrderedDict()
    h = []
    comments = []
    xsp, ysp = [], []
    nstep = 0

    for i,line in enumerate(fileHandle):
        match = re.search(r"^#:(.*): '(.*)'$", line)
        if match:
            k = match.group(1)
            try:
                v = str(match.group(2))
            except:
                v = match.group(2).encode('utf-8')
            if k == "scanComment": # special treatment of the scanComment, which can be plural
                comments.append(v)
            else:
                paramsCollected[k] = v
            h.append(line.strip())
        elif re.search(r"^#.*$", line):
            h.append(line.strip())
        else:
            try:
                xsp.append(float(line.split(',')[0]))
                ysp.append(float(line.split(',')[1]))
                nstep += 1
            except ValueError:
                warnings.warn("couldn't interpret line #%s as two values: %s" % (i, line))

    if "currentScanIndex" in paramsCollected:
        scanIndex = paramsCollected["currentScanIndex"]
        try:
            numPoints = int(scanIndex.split("/")[1])
            if not nstep==numPoints:
                msg = "%s: CASAC file is incomplete!" % filename
                raise IOError
        except IndexError:
            numPoints = nstep   # does not catch errors for older files! (i.e. early-2016)
        except AttributeError:
            numPoints = None

    # hacks for older files (i.e. early-2016)
    if not 'txt_ScanTime' in paramsCollected:
        paramsCollected['txt_ScanTime'] = '00:00:0.00'
    elif paramsCollected['txt_ScanTime'] == '':
        paramsCollected['txt_ScanTime'] = '00:00:0.00'
    if not 'lcd_ScanIterations' in paramsCollected:
        paramsCollected['lcd_ScanIterations'] = '1'

    # Process data
    xsp = np.array(xsp)
    ysp = np.array(ysp)

    # update class data
    header = collections.OrderedDict([
        ('title', paramsCollected["scanTitle"]),
        ('comments', "\n".join(comments)),
        ('timestamp', paramsCollected["timeScanSave"]),
        ('sourcefile', os.path.abspath(filename)),
        ('loadTime', str(datetime.datetime.now())),
        ('freqStart', float(paramsCollected["txt_SynthFreqStart"])),
        ('freqStop', float(paramsCollected["txt_SynthFreqEnd"])),
        ('freqStep', float(paramsCollected["txt_SynthFreqStep"])),
        ('xrange', float(xsp.max() - xsp.min())),
        ('yrange', float(ysp.max() - ysp.min())),
        ('numPoints', numPoints),
        ('detAmplitude', siEval(paramsCollected["combo_LockinSensitivity"])),
        ('detSamplerate', siEval(paramsCollected["combo_LockinTau"])),
        ('multFact',  int(paramsCollected["txt_SynthMultFactor"])),
        ('scanTime',  datetime2sec(paramsCollected["txt_ScanTime"])),
        ('numScans',  int(paramsCollected["lcd_ScanIterations"])),
        ('paramsCollected', paramsCollected), # just in case...
        ('xunit', "MHz"),
        ('yunit', "V"),
    ])
    # add keys to built-in pretty-printed header
    addedh = []
    for k,v in header.items():
        if k == 'paramsCollected':
            continue
        addedh.append("%s: %s" % (k, v))
    header['ppheader'] = addedh + h

    fileHandle.close()
    return xsp, ysp, header

def loadfile_hidencsv(filename,
    cycle=None, unit="ms", mass=None):
    """ Import a CSV file from a Hiden mass-spec. """
    if mass is not None and isinstance(mass, int):
        mass = float(mass)

    try:
        if sys.version_info[0] == 3:
            fileHandle = open(filename, mode='r', encoding='utf-8')
        else:
            fileHandle = open(filename, mode='rU')
    except IOError:
        err_str = "%s: file could not be loaded" % (filename)
        raise IOError(err_str)

    hdr = collections.OrderedDict()
    xsp, ysp = [], []
    comments = []
    cycles = {}
    units = []
    xunit = unit
    yunit = None

    for i,line in enumerate(fileHandle):
        if i==0:
            continue
        if line[0] == '"':
            comments.append(line.strip())
            line = line.replace('"',"").strip()
            k = line.split(',')[0]
            if k == "header":
                continue
            v = " ".join(line.split(',')[1:])
            hdr[k] = v
        else:
            units = comments[-1].replace('"',"").split(',')
            if "Cycle" in units: # should always be the first column..
                this_c = int(line.strip().split(',')[0])
                if not this_c in cycles.keys():
                    cycles[this_c] = {}
                for k,u in enumerate(units[1:]):
                    if not u in cycles[this_c].keys():
                        cycles[this_c][u] = []
                    val = line.split(',')[k+1].strip()
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                    cycles[this_c][u].append(val)
            else:
                this_c = 1
                if not this_c in cycles.keys():
                    cycles[this_c] = {}
                for k,u in enumerate(units[1:]):
                    if not u in cycles[this_c].keys():
                        cycles[this_c][u] = []
                    val = line.split(',')[k+1].strip()
                    try:
                        val = float(val)
                    except ValueError:
                        pass
                    cycles[this_c][u].append(val)

    # Process data
    if not cycle:
        cycle = sorted(cycles.keys())[-1]
        print("you did not specify which cycle to load, so choosing the last entry: %g" % cycle)
    if ((("Cycle" in units) and (not unit == "ms")) or # for normal mass spectrum
        (not ("Cycle" in units) and (unit == "ms"))): # or a "leak test"-like scan
        if cycle == -1:
            yunit = units[units.index(unit)+1]
            xsp = np.asarray(map(float, cycles[1][unit]))
            ymat = []
            for cycle in sorted(cycles.keys()):
                ymat.append(np.asarray(map(float, cycles[cycle][yunit])))
            ymat = np.asarray(ymat)
            ysp = np.mean(ymat, axis=0)
        elif cycle in cycles.keys():
            yunit = units[units.index(unit)+1]
            xsp = np.asarray(map(float, cycles[cycle][unit]))
            ysp = np.asarray(map(float, cycles[cycle][yunit]))
        else:
            raise SyntaxError("you requested cycle #%g but it isn't found in the file" % cycle)
    elif ("Cycle" in units) and (unit == "ms") and (mass is None):
        raise SyntaxError("the file looks like a mass spectrum but you didn't specify a mass!")
    else: # for extracting a single mass from a looped mass spectrum
        if not mass in cycles[1]["mass amu"]:
            masses = cycles[1]["mass amu"]
            msg = "you requested mass %g but it is not in the spectrum: %s" % (mass, masses)
            raise Exception(msg)
        xsp = []
        ysp = []
        for cycle in sorted(cycles.keys()):
            xsp.append(float(cycles[cycle]["ms"][0]))
            yunit = units[units.index("mass amu")+1]
            iamu = cycles[cycle]["mass amu"].index(mass)
            ysp.append(cycles[cycle][yunit][iamu])
        xsp = np.asarray(xsp)
        ysp = np.asarray(ysp)

    # update class data
    header = collections.OrderedDict([
        ('timestamp', "TODO"),
        ('paramsCollected', ["%s: %s" % (k,v) for k,v in hdr.items()]),
        ('sourcefile', os.path.abspath(filename)),
        ('loadTime', str(datetime.datetime.now())),
        ('xrange', float(xsp.max() - xsp.min())),
        ('yrange', float(ysp.max() - ysp.min())),
        ('xunit', xunit),
        ('yunit', yunit),
    ])
    header.update(hdr)
    # add keys to built-in pretty-printed header
    h = []
    for k,v in header.items():
        if k == 'paramsCollected':
            continue
        h.append("%s: %s" % (k, v))
    header['ppheader'] = h

    fileHandle.close()
    return xsp, ysp, header

def loadfile_brukeropus(filename, scanindex=0, do_t2a_conversion=False):
    """ Import a spectrum from a *.0...*.x Bruker Opus file. """
    try:
        if sys.version_info[0] == 3:
            fileHandle = open(filename, mode='r', encoding='utf-8')
        else:
            fileHandle = open(filename, mode='rU')
    except IOError:
        err_str = "%s: file could not be loaded" % (filename)
        raise IOError(err_str)

    hdr = collections.OrderedDict()
    xsp, ysp = [], []
    logging.getLogger('bruker_opus').addHandler(logging.NullHandler())

    # load file
    spectrum = bruker_opus_filereader.OpusReader(filename)
    spectrum.readDataBlocks()
    for k in spectrum.keys():
        hdr[k] = spectrum[k]
    def get_spectrum(block_key):
        try:
            if (block_key == "AB") and do_t2a_conversion and (not "AB" in spectrum):
                log.info("will try to build an absorption spectrum from the transmission")
                xsp_rf = spectrum.wavenumber("ScRf")
                xsp_sm = spectrum.wavenumber("ScSm")
                ysp_rf = spectrum["ScRf"]
                ysp_sm = spectrum["ScSm"]
                if len(xsp_rf) > len(xsp_sm):
                    spline = interpolate.interp1d(
                        xsp_rf, ysp_rf,
                        bounds_error=True, fill_value=0)
                    xsp = xsp_sm
                    ysp = np.log10(spline(xsp_sm)/ysp_sm)
                elif len(xsp_rf) < len(xsp_sm):
                    spline = interpolate.interp1d(
                        xsp_rf, ysp_rf,
                        bounds_error=True, fill_value=0)
                    xsp = xsp_rf
                    ysp = np.log10(ysp_rf/spline(xsp_rf))
                elif not np.isclose(xsp_rf, xsp_sm):
                    raise ValueError("the reference and sample spectra do not cover the same spectral region:\n %s vs %s" % (xsp_rf, xsp_sm))
                else:
                    xsp = xsp_sm
                    ysp = np.log10(ysp_rf/ysp_sm)
                date = spectrum['ScSm Data Parameter']['DAT']
                date = "-".join(reversed(date.split("/"))) # convert to a more standard format
                time = spectrum['ScSm Data Parameter']['TIM']
                timestamp = "%s %s" % (date, time)
            else:
                xsp = spectrum.wavenumber(block_key)
                ysp = spectrum[block_key]
                block_key_pm = '%s Data Parameter' % block_key
                date = spectrum[block_key_pm]['DAT']
                date = "-".join(reversed(date.split("/"))) # convert to a more standard format
                time = spectrum[block_key_pm]['TIM']
                timestamp = "%s %s" % (date, time)
        except KeyError:
            raise NotImplementedError("This Bruker spectrum does not have a data block '%s': %s" % (block_key, spectrum.keys()))
        except:
            e = sys.exc_info()[1]
            raise NotImplementedError("There was an unexpected error during the processing of the data block: %s" % (e,))
        else:
            return xsp, ysp, timestamp
    # collect desired spectrum according to the following values for the scanindex:
    # 0: tries (in order) AB -> ScSm -> ScRf
    # 1: the "AB" block
    # 2: the "ScSm" block
    # 3: the "ScRf" block
    # 4: the "IgSm" block
    # 5: the "IgRf" block
    if scanindex:
        block_key = scanindex2opusblock[scanindex]
        xsp, ysp, timestamp = get_spectrum(block_key)
    else:
        for block_key in ("AB", "ScSm", "ScRf"):
            log.debug("trying block_key %s" % block_key)
            try:
                xsp, ysp, timestamp = get_spectrum(block_key)
            except:
                continue
            else:
                break

    # update class data
    header = collections.OrderedDict([
        ('block_key', block_key),
        ('timestamp', timestamp),
        ('paramsCollected', hdr),
        ('sourcefile', os.path.abspath(filename)),
        ('loadTime', str(datetime.datetime.now())),
        ('xrange', float(xsp.max() - xsp.min())),
        ('yrange', float(ysp.max() - ysp.min())),
        ('xunit', "cm-1"),
        ('yunit', "arb"),
    ])
    header.update(hdr)
    # add keys to built-in pretty-printed header
    h = []
    for k,v in header.items():
        if k == 'paramsCollected':
            continue
        elif isinstance(v, dict) and len(v.items()):
            h.append("### %s" % k)
            for kk,vv in v.items():
                h.append("#:%s: '%s'" % (kk,vv))
        else:
            h.append("%s: %s" % (k, v))
    header['ppheader'] = h

    fileHandle.close()
    return xsp, ysp, header

def loadfile_batopt3ds(filename):
    """
    Import a spectrum from the Batop THz-TDS experiment.
    """
    try:
        if sys.version_info[0] == 3:
            fileHandle = open(filename, mode='r', encoding='ISO-8859-1')
        else:
            fileHandle = open(filename, mode='rU')
    except IOError:
        err_str = "%s: file could not be loaded" % (filename)
        raise IOError(err_str)

    hdr = collections.OrderedDict()
    data = collections.OrderedDict()
    xdata, ydata = [], []

    inHDR = True
    keys = []   # a throwaway during the loading
    for i,line in enumerate(fileHandle):
        if i == 0:
            timestamp = line.split("\t")[0]
            # now convert timestamp to something more standard
            date, time = timestamp.split("/")
            date = date.strip().replace(".","-")
            time = time.strip().replace(".",":")
            if len(time.split(":")) == 2:
                time += ":0"
            timestamp = "%s %s" % (date, time)
        elif inHDR and (":" in line):       # collect the metadata
            k,v = line.replace("\t"," ").split(":")
            hdr[k.strip()] = v.strip()
        elif inHDR and (not ":" in line):   # initialize the data dict
            inHDR = False
            keys = line.strip().split("\t")
            for k in keys:
                data[k] = []
        else:                               # collect the data
            for k,d in enumerate(line.strip().split("\t")):
                key = keys[k]
                d = float(d)
                if (d == 0.0) and len(data[key]): # only a single zero-valued datapoint is useful
                    continue
                else:
                    data[key].append(d)

    # Process data
    for k in keys:
        data[k] = np.array(data[k])
    xdata = data["f [THz]"]
    ydata = data["A_measurement [V/THz]"]
    numPoints = len(xdata)

    # update class data
    header = collections.OrderedDict([
        ('timestamp', timestamp),
        ('paramsCollected', ["%s: %s" % (k,v) for k,v in hdr.items()]),
        ('sourcefile', os.path.abspath(filename)),
        ('loadTime', str(datetime.datetime.now())),
        ('xrange', float(xdata.max() - xdata.min())),
        ('yrange', float(ydata.max() - ydata.min())),
        ('numPoints', numPoints),
        ('xunit', "THz"),
        ('yunit', "V/THz"),
    ])
    header.update(hdr)
    # add keys to built-in pretty-printed header
    h = []
    for k,v in header.items():
        h.append("%s: %s" % (k, v))
    header['ppheader'] = h

    fileHandle.close()
    return xdata, ydata, header

def guess_filetype(filename=None):
    """
    Tries to guess the filetype based on the filename(s).

    The delimited files are easy to parse, as are FITS, JPL, and
    Bruker Opus spectral files. However, XY files tend to either
    be comma- or tab-separated files, and GESP, FID, and Batop's
    T3DS spectral files all end in '.dat'.

    :param filename: the filename(s) to be checked
    :type filename: str or list(str)
    :returns: the guessed filetype
    :rtype: str
    """
    # check input(s)
    if filename is None:
        return None
    elif isinstance(filename, str):
        filename = [filename]
    # check extensions then
    filetype = None
    theseExts = [os.path.splitext(f)[1][1:].lower() for f in filename]
    if all([("fid" in f.lower()) for f in filename]):
        filetype = "fid"
    elif all([(os.path.splitext(f)[1][1:] == "lwa") for f in filename]):
        filetype = "jpl"
    elif all([(ext in list(map(str,range(11)))) for ext in theseExts]):
        filetype = "brukeropus"
    else:
        knownExts = ("ssv", "tsv", "csv", "fits")
        for ext in knownExts:
            log.debug("checking ext %s against %s" % (ext, theseExts))
            if all([bool(e == ext) for e in theseExts]):
                filetype = ext
                break
    return filetype

def create_spectrum(ydata, samplerate, stype='xyspectrum'):
    """
    Creates a spectrum from ydata, based on the samplerate.

    :param ydata: Data points (Signal)
    :type ydata: list of float
    :param samplerate: Samplerate, which will be used to calculate points on time-axis.
    :type samplerate: float
    """
    header = {}
    x = [i / samplerate for i in xrange(len(ydata))]
    header['samplerate'] = samplerate
    if stype == 'FID':
        spec = FID(x, ydata)
    else:
        spec = Spectrum(x, ydata)
    spec.h = header
    return spec

def load_spectrum(filename, ftype='tekscope-csv', **kwds):
    """
    Loads a spectrum from file.

    :param filename: file that contains spectrum (x,y)
    :type filename: str
    :rtype: spectrum.spectrum
    """
    h, x, y = load_file(filename, ftype, **kwds)
    if len(y) == 2:
        dy = y[1]
        y = y[0]
        spec = Spectrum(x, y)
        spec.dy = dy
    else:
        spec = Spectrum(x, y)
    spec.h = h
    spec.update(**h) # JCL: should be the preferred method because takes ANY key/value pair
    return spec

def load_fid(filename, ftype='tekscope-csv', samplerate=3.125e9):
    """
    Loads a fid-spectrum from file.

    :param filename: file that contains spectrum (x,y)
    :type filename: str
    :rtype: spectrum.Spectrum
    """
    h, x, y = load_file(filename, ftype, samplerate)
    fid = FID(x, y)
    fid.header = h
    fid.update(**h)
    return fid

def load_iqspectrum(filename, ftype = 'npy', **kwds):
    """
    Loads an IQ-Spectrum from file.

    :param filename: file that contains iqspectrum (x,y,z)
    :type filename: str
    :rtype: spectrum.IQSpectrum
    """
    h, x, y = load_file(filename, ftype, **kwds)
    # test if file has i,q data
    if len(y) == 2:
        spec = IQSpectrum(x, y)
    else:
        spec = Spectrum(x, y)
    spec.h = h
    spec.update(**h)
    return spec

def plot_data(x, y, filename=None, xlabel=None, ylabel=None, legend=None):

    fig = plt.figure(1)
    ax = fig.add_subplot(111)

    # set labels
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)

    # check if a list of plots is submitted.
    if len(y) > 1 and isinstance(y[0], list):
        for arr in y:
            ax.plot(x, arr)
    else:
        ax.plot(x, y, 'b')

    if legend:
        ax.legend(legend)
    ax.grid(True)

    if filename:
        fig.savefig(filename)
    else:
        plt.show()

    return fig


def convert_units(target=None, from_unit=None, to_unit=None):
    """
    Tries to convert the target (anything compatible with the
    multiplication operator) from one unit to another.

    :param target: the target value or collection of values
    :type target: int, float, or numpy.ndarray
    :param from_unit: the original unit
    :type from_unit: str
    :param to_unit: the new unit
    :type to_unit: str
    :returns: the new value or collection of values
    :rtype: (same as input, hopefully)
    """
    raise NotImplementedError("convert_units() does nothing yet..")


def calc_power_spec(x, y, sampling_rate, window_function='Boxcar', impedance =
                    50.0, zero_filling = False):
    """
    Calculates the power spectrum. A window function, such as Hamming-, Hann- and Blackman
    can be applied.

    :param x: x-data values
    :type x: list of float
    :param y: y-data values
    :type y: list of float
    :param window_function: window function which will be applied ('Hamming', 'Hann', 'Blackman').
    :type window_function: string
    :param impedance: Impedance for the conversion from voltage to power [Ohm]
    :type impedance: float
    """
    xf, yf, xwf, ywf = calc_amplitude_spec(x, y, sampling_rate, window_function
                                           = window_function, zero_filling =
                                           zero_filling)

    return xf, yf**2.0 / impedance, xwf, ywf**2.0 / impedance

def calc_amplitude_spec(x, y,
                        sampling_rate,
                        window_function='Boxcar',
                        zero_filling = False):
    """
    Calculates the amplitude spectrum. A window function, such as Hamming-, Hann- and Blackman
    can be applied.

    :param x: x-data values
    :type x: list of float
    :param y: y-data values
    :type y: list of float
    :param window_function: window function which will be applied ('Hamming', 'Hann', 'Blackman').
    :type window_function: string
    """
    # Number of sampling points
    N = len(x)
    N2 = int(N/2.0)

    # window function
    if window_function == 'Hamming':
        w = signal.hamming(N)
    elif window_function == 'Hann':
        w = signal.hann(N)
    elif window_function == 'Blackman':
        w = signal.blackman(N)
    elif window_function == 'Flattop':
        w = signal.flattop(N)
    elif window_function == 'Blackmanharris':
        w = signal.blackmanharris(N)
    elif window_function == 'Kaiser':
        w = signal.kaiser(N,14)
    elif window_function == 'Triangle':
        w = signal.triang(N)
    elif window_function == 'Tukey':
        w = signal.tukey(N)
    elif window_function == 'Bohman':
        w = signal.bohman(N)
    elif window_function == 'Barthann':
        w = signal.barthann(N)
    elif window_function == 'Barlett':
        w = signal.barlett(N)
    elif window_function == 'Boxcar':
        w = signal.boxcar(N)
    else:
        w = 1.0

    if zero_filling:
        yy = np.zeros(int(2**np.ceil(np.log2(N))))
        yw = np.zeros(int(2**np.ceil(np.log2(N))))
        yy[:N] += y
        yw[:N] += y * w

        N = len(yy)
        N2 = int(N/2.0)
    else:
        yy = y
        yw = y * w

    # Time step
    time_step = 1.0 / sampling_rate

    # Calculate frequency and intensity (x,y) points
    x_fft = fftpack.fftfreq(N, d=time_step)
    x_fft = fftpack.fftshift(x_fft)
    y_fft = fftpack.fft(yy)
    y_fft = fftpack.fftshift(y_fft)

    y_w_fft = fftpack.fft(yw)
    y_w_fft = fftpack.fftshift(y_w_fft)

    # scaling factor is only sqrt(2)/N, because power Ueff = Upeak / sqrt(2)
    return x_fft[N2:], np.sqrt(2.0) / N * np.sqrt(y_fft[N2:].real**2.0 + y_fft[N2:].imag**2.0), \
            x_fft[N2:], np.sqrt(2.0) / N * np.sqrt(y_w_fft[N2:].real**2.0 + y_w_fft[N2:].imag**2.0)

def calc_phase_spec(x, y, sampling_rate, window_function='Boxcar'):
    """
    Calculates the phase spectrum. A window function, such as Hamming-, Hann- and Blackman
    can be applied.

    :param x: x-data values
    :type x: list of float
    :param y: y-data values
    :type y: list of float
    :param window_function: window function which will be applied ('Hamming', 'Hann', 'Blackman').
    :type window_function: string
    """
    # Number of sampling points
    N = len(x)
    N2 = int(N/2.0)

    # Time step
    time_step = 1.0 / sampling_rate
    # window function
    if window_function == 'Hamming':
        w = signal.hamming(N)
    elif window_function == 'Hann':
        w = signal.hann(N)
    elif window_function == 'Blackman':
        w = signal.blackman(N)
    elif window_function == 'Flattop':
        w = signal.flattop(N)
    elif window_function == 'Blackmanharris':
        w = signal.blackmanharris(N)
    elif window_function == 'Kaiser':
        w = signal.kaiser(N,14)
    elif window_function == 'Triangle':
        w = signal.triang(N)
    elif window_function == 'Tukey':
        w = signal.tukey(N)
    elif window_function == 'Bohman':
        w = signal.bohman(N)
    elif window_function == 'Barthann':
        w = signal.barthann(N)
    elif window_function == 'Barlett':
        w = signal.barlett(N)
    elif window_function == 'Boxcar':
        w = signal.boxcar(N)
    else:
        w = 1.0

    if zero_filling:
        yy = np.zeros(int(2**np.ceil(np.log2(N))))
        yw = np.zeros(int(2**np.ceil(np.log2(N))))
        yy[:N] += y
        yw[:N] += y * w

        N = len(yy)
        N2 = int(N/2.0)
    else:
        yy = y
        yw = y * w

    # Calculate frequency and intensity (x,y) points
    x_fft = fftpack.fftfreq(N, d=time_step)
    x_fft = fftpack.fftshift(x_fft)
    y_fft = fftpack.fft(yy)
    y_fft = fftpack.fftshift(y_fft)

    y_w_fft = fftpack.fft(yw)
    y_w_fft = fftpack.fftshift(y_w_fft)

    # scaling factor is only sqrt(2)/N, because power Ueff = Upeak / sqrt(2)
    return x_fft[N2:], np.arctan2(y_fft[N2:].imag, y_fft[N2:].real), \
            x_fft[N2:], np.arctan2(y_w_fft[N2:].imag, y_w_fft[N2:].real)

def calc_complex_power_spec(x, y, sampling_rate, window_function='Hamming',
                            zero_filling = False):
    """
    Calculates the power spectrum. A window function, such as Hamming-, Hann- and Blackman
    can be applied.

    :param x: x-data values
    :type x: list of float
    :param y: y-data values
    :type y: list of float
    :param window_function: window function which will be applied ('Hamming', 'Hann', 'Blackman').
    :type window_function: string
    """
    # Number of sampling points
    N = len(x)
    # Time step
    time_step = 1.0 / sampling_rate
    # window function
    if window_function == 'Hamming':
        w = signal.hamming(N)
    elif window_function == 'Hann':
        w = signal.hann(N)
    elif window_function == 'Blackman':
        w = signal.blackman(N)
    elif window_function == 'Flattop':
        w = signal.flattop(N)
    elif window_function == 'Blackmanharris':
        w = signal.blackmanharris(N)
    elif window_function == 'Kaiser':
        w = signal.kaiser(N,14)
    elif window_function == 'Triangle':
        w = signal.triang(N)
    elif window_function == 'Tukey':
        w = signal.tukey(N)
    elif window_function == 'Bohman':
        w = signal.bohman(N)
    elif window_function == 'Barthann':
        w = signal.barthann(N)
    elif window_function == 'Barlett':
        w = signal.barlett(N)
    elif window_function == 'Boxcar':
        w = signal.boxcar(N)
    else:
        w = 1.0

    if zero_filling:
        yy = np.zeros(int(2**np.ceil(np.log2(N))))
        yw = np.zeros(int(2**np.ceil(np.log2(N))))
        yy[:N] += y
        yw[:N] += y * w

        N = len(yy)
        N2 = int(N/2.0)
    else:
        yy = y
        yw = y * w


    # Calculate frequency and intensity (x,y) points
    x_fft = fftpack.fftfreq(N, d=time_step)
    y_fft = fftpack.fft(yy)

    y_w_fft = fftpack.fft(yw)
    #x_w_fft = np.linspace(-1.0 / (2.0 * time_step), 1.0 / (2.0 * time_step), N )
    x_w_fft = fftpack.fftfreq(N, d=time_step)
    x_w_fft = fftpack.fftshift(x_w_fft)
    y_w_fft = fftpack.fftshift(y_w_fft)

    return x_fft, 2.0 / N * np.abs(y_fft), x_w_fft, 2.0 / N * np.abs(y_w_fft)

def calc_amplitude_spec_win(y, samplerate, window_function = 'Boxcar',
                            zero_filling_n = 0):
    """
    Calculates the complex fft with window function ( Hamming-, Hann- and
    Blackman).

    :param y: y-data values
    :type y: list of float
    :param samplerate: samplerate
    :type samplerate: float
    :param window_function: window function which will be applied ('Hamming', 'Hann', 'Blackman').
    :type window_function: string
    """
    # Number of sampling points
    N = len(y)
    if zero_filling_n < N:
        zero_filling_n = N

    # Time step
    try:
        time_step = 1.0 / samplerate
    except:
        print("Timestep")

    # Calculate frequency and intensity (x,y) points
    x_fft = fftpack.fftfreq(zero_filling_n, d=time_step)
    x_fft = fftpack.fftshift(x_fft)

    # window function
    if window_function == 'Hamming':
        w = signal.hamming(N)
    elif window_function == 'Hann':
        w = signal.hann(N)
    elif window_function == 'Blackman':
        w = signal.blackman(N)
    elif window_function == 'Flattop':
        w = signal.flattop(N)
    elif window_function == 'Blackmanharris':
        w = signal.blackmanharris(N)
    elif window_function == 'Kaiser':
        w = signal.kaiser(N,14)
    elif window_function == 'Triangle':
        w = signal.triang(N)
    elif window_function == 'Tukey':
        w = signal.tukey(N)
    elif window_function == 'Bohman':
        w = signal.bohman(N)
    elif window_function == 'Barthann':
        w = signal.barthann(N)
    elif window_function == 'Barlett':
        w = signal.barlett(N)
    elif window_function == 'Boxcar':
        w = signal.boxcar(N)
    else:
        w = 1.0

    data = np.zeros(zero_filling_n, dtype=type(y[0]))
    data[:N] += y * w
    y_fft = fftpack.fft(data)
    y_fft = fftpack.fftshift(y_fft)

    # scaling factor is only sqrt(2)/N, because power Ueff = Upeak / sqrt(2)
    try:
        specdata = np.sqrt(2)/N * np.abs(y_fft)
    except:
        print("specdata")
    return x_fft, np.sqrt(2)/N * np.abs(y_fft)

def calc_power_spec_win(y, samplerate, window_function = 'Boxcar',
                        zero_filling_n = 0):
    """
    Calculates the complex fft with window function ( Hamming-, Hann- and
    Blackman).

    :param y: y-data values
    :type y: list of float
    :param samplerate: samplerate
    :type samplerate: float
    :param window_function: window function which will be applied ('Hamming', 'Hann', 'Blackman').
    :type window_function: string
    """
    # Number of sampling points
    N = len(y)
    if zero_filling_n < N:
        zero_filling_n = N

    # Time step
    time_step = 1.0 / samplerate

    # Calculate frequency and intensity (x,y) points
    x_fft = fftpack.fftfreq(zero_filling_n, d=time_step)
    x_fft = fftpack.fftshift(x_fft)

    # window function
    if window_function == 'Hamming':
        w = signal.hamming(N)
    elif window_function == 'Hann':
        w = signal.hann(N)
    elif window_function == 'Blackman':
        w = signal.blackman(N)
    elif window_function == 'Flattop':
        w = signal.flattop(N)
    elif window_function == 'Blackmanharris':
        w = signal.blackmanharris(N)
    elif window_function == 'Kaiser':
        w = signal.kaiser(N,14)
    elif window_function == 'Triangle':
        w = signal.triang(N)
    elif window_function == 'Tukey':
        w = signal.tukey(N)
    elif window_function == 'Bohman':
        w = signal.bohman(N)
    elif window_function == 'Barthann':
        w = signal.barthann(N)
    elif window_function == 'Barlett':
        w = signal.barlett(N)
    elif window_function == 'Boxcar':
        w = signal.boxcar(N)
    else:
        w = 1.0

    data = np.zeros(zero_filling_n, dtype=type(y[0]))
    data[:N] += y * w
    y_fft = fftpack.fft(data)
    y_fft = fftpack.fftshift(y_fft)

    # scaling factor is only sqrt(2)/N, because power Ueff = Upeak / sqrt(2)
    return x_fft, 2.0/N * np.abs(y_fft.real**2 + y_fft.imag**2)



def plot_power_spec(x, y, sampling_rate, window_function='Hamming',
                    zero_filling = False):

    # Number of sampling points
    N = len(x)

    x_fft, yfft, x_w_fft, y_w_fft = calc_power_spec(
        x, y, sampling_rate, window_function=window_function,
        zero_filling = zero_filling)
    # Plot spectrum
    plt.figure(1)
    # plt.plot(x_fft[0:N/2], 2.0 / N * np.abs(y_fft[0:N/2]))
    plt.plot(x_w_fft, y_w_fft)

 #   plt.plot(x_fft,abs(y_fft))
    plt.show()


def filter_spectrum(x, y, sampling_rate, flow=0.0, fhigh=30.0e9):

    # Number of sampling points
    N = len(x)
    # Time step
    time_step = 1.0 / sampling_rate

    # Calculate frequency and intensity (x,y) points
    x_fft = fftpack.rfftfreq(N, d=time_step)
    y_fft = fftpack.rfft(y)

    cut_f_signal = y_fft.copy()
    cut_f_signal[(x_fft < flow)] = 0.0
    cut_f_signal[(x_fft > fhigh)] = 0.0

    return x, fftpack.irfft(cut_f_signal)

def bandpass_filter(y, sampling_rate, flow, fhigh, ftype='butter'):
    nyquistfreq = sampling_rate / 2.0
    b, a = signal.butter(
        1, (flow / nyquistfreq, fhigh / nyquistfreq), 'bandpass')

    return signal.filtfilt(b, a, y)


def slice_spectrum(x, y, sampling_rate, slice_length=0.1):
    """
    Returns an array of slices of the time-domain spectrum

    slice_length is in microseconds
    """
    slice_length_samples = int(slice_length * sampling_rate * 1.0e-6)

    num_slices = int(len(x) / slice_length_samples)

    slices = []
    for i in xrange(num_slices):
        slices.append(
            [x[i * slice_length_samples:(i + 1) * slice_length_samples], y[i * slice_length_samples:(i + 1) * slice_length_samples]])

    return slices


def get_envelope(x, y, method = 'hilbert', sampling_rate = 5.0e9, slice_length=0.1):
    """
    Determines the envelope of the spectrum defined by x and y.

    """
    if method == 'slices':
        sl = slice_spectrum(x, y, sampling_rate, slice_length=slice_length)

        xx = []
        yy = []

        for slice in sl:
            yy.append(max(slice[1]))
            xx.append(min(slice[0]) + (max(slice[0]) - min(slice[0])) / 2.0)

    else:
        # use Hilber - transformation to determine the amplitude of the spectrum
        hil = fftpack.hilbert(y)
        xx = x
        yy = np.sqrt(y**2 + hil.real**2)
    return xx, yy

def fit_envelope(x, y, sampling_rate, slice_length=0.1, amplitude=None, decay_rate=None):

    xx, yy = get_envelope(x, y, sampling_rate, slice_length=slice_length)

    if amplitude is None:
        amp = fit.Parameter(max(yy))
    else:
        amp = fit.Parameter(amplitude)

    if decay_rate is None:
        decay = fit.Parameter(1.0)
    else:
        decay = fit.Parameter(decay_rate)

    func = lambda x: amp() * np.exp(-decay() * x)

    return fit.fit(func, [amp, decay], np.array(yy), np.array(xx))

def fit_FID(x, y, frequencies, sampling_rate, slice_length=0.1, width=2.0e5, delays=None):
    """
    applies a bandpass filter to the FID and fits the envelope to derive the decay rate
    """

    result = []
    if not type(frequencies) == list:
        frequencies = [frequencies]

    i = 0
    for f in frequencies:
        xf, yf = filter_spectrum(
            x, y, sampling_rate, flow=f - width, fhigh=f + width)
        param, success = fit_envelope(
            xf, yf, sampling_rate, slice_length=slice_length)
        print(param)
        if delays is not None:
            d = delays[i]
        else:
            d = 0.0
        amp_corr = param[0] * np.exp(-param[1] * d * 1.0e-6)
        result.append([f, param[0], param[1], amp_corr])
        i += 1

    return result

def add_delay(data, step, delay):
    """
    Shifts data points.
    """
    y = data[0]
    new_data = np.zeros(len(data))
    if np.abs(delay) < step:
        if delay > 0.0:
            for i in xrange(len(data)-1):
                new_data[i] = data[i] + (data[i+1] - data[i]) * delay / step
            # no information about intensity after last point
            new_data[-1] = data[-1]
        else:
            # no information about intensity before first point
            new_data[0] = data[0]
            for i in xrange(1,len(data)):
                new_data[i] = data[i] - (data[i-1] - data[i]) * delay / step

    return new_data

def fit_td_fid(spec,
               transitions = None,
               time_start = 0.0,
               time_stop = 1.0,
               init_A = 7000000.0 ,
               init_gamma = 800000.0,
               init_dx = 1.0e-10,
               locked_A = False,
               locked_gamma = False,
               locked_dx = False,
               chirpType = 'increasing',
               pulseWidth = 0.240e-6,
               span = 5000.0,
               offset = 0.0,
               lo = 22000.0,
               fstart = -2500.0,
               ):

    parameters = fit.Parameters(params = [])
    if type(init_A) == float:
        init_A = [init_A]
        locked_A = [locked_A]

    print(len(parameters.params))
    for i in range(len(init_A)):
        parameters.add('A%d' % i, init_A[i], locked = locked_A[i])

    parameters.add('gamma', init_gamma, locked = locked_gamma)

    for i in range(len(init_dx)):
        parameters.add('dx%d' %i, init_dx[i], locked = locked_dx[i])
    # parameters.add('dx', init_dx, locked = locked_dx)


    #trans = fit.Parameter(value = transition)

    idx_start = np.abs(spec.x - time_start).argmin()
    idx_stop = np.abs(spec.x - time_stop).argmin()

    #    func = lambda x: nh3_sim_single(x, A(), gamma(), dx(),
    #                                    transition = transition )

    # func = lambda x: fit.chirp_fid_func(x,
    #                                     [A() for A in parameters.params[:-2]],
    #                                     parameters.params[-2](),
    #                                     parameters.params[-1](),
    #                                     transitions = transitions,
    #                                     chirpType = chirpType,
    #                                     pulseWidth = pulseWidth,
    #                                     span = span,
    #                                     offset = offset,
    #                                     lo = lo,
    #                                     fstart = fstart
    #                                    )
    func = lambda x: fit.chirp_fid_func(x,
                                        [A() for A in
                                         parameters.params[:len(init_A)]],
                                        parameters.params[len(init_A) ](),
                                        [dx() for dx in
                                         parameters.params[len(init_A) +1:]],
                                        transitions = transitions,
                                        chirpType = chirpType,
                                        pulseWidth = pulseWidth,
                                        span = span,
                                        offset = offset,
                                        lo = lo,
                                        fstart = fstart
                                       )


    info = fit.fit(func, parameters.params,
                   spec.y[idx_start:idx_stop], \
                   spec.x[idx_start:idx_stop],
                   output = 'parameter')

    fit_y = func(spec.x)

    return info, fit_y

def fit_td_fids(spec_list,
               transitions = None,
               time_start = 0.0,
               time_stop = 1.0,
               init_A = 7000000.0 ,
               init_gamma = 800000.0,
               init_dx = 1.0e-10,
               locked_A = False,
               locked_gamma = False,
               locked_dx = False,
               chirpType = 'increasing',
               pulseWidth = 0.240e-6,
               span = 5000.0,
               offset = 0.0,
               lo = 22000.0,
               fstart = -2500.0,
               ):

    parameters = fit.Parameters(params = [])
    if type(init_A) == float:
        init_A = [init_A]
        locked_A = [locked_A]

    num_amp_params = len(init_A)
    # add amplitude parameters for every spectrum
    for spec_id in range(len(spec_list)):
        for i in range(num_amp_params):
            parameters.add('A%d_%d' % (i, spec_id), init_A[i], locked = locked_A[i])

    # use same decay and phase for all spectra
    parameters.add('gamma', init_gamma, locked = locked_gamma)
    parameters.add('dx', init_dx, locked = locked_dx)

    #trans = fit.Parameter(value = transition)

    idx_start = np.abs(spec_list[0].x - time_start).argmin()
    idx_stop = np.abs(spec_list[0].x - time_stop).argmin()
    len_spec = len(spec_list[0].x[idx_start:idx_stop])

    #    func = lambda x: nh3_sim_single(x, A(), gamma(), dx(),
    #                                    transition = transition )

    def func(x):
        ret_val = np.zeros(len(spec_list) * len_spec)

        for spec_id in range(len(spec_list)):
            xi = x[spec_id * len_spec:(spec_id+1) * len_spec]
            ret_val[spec_id * len_spec:(spec_id+1) * len_spec] = \
                    fit.chirp_fid_func(xi,
                                       [A() for A in parameters.params[
                                           spec_id * num_amp_params:\
                                           (spec_id+1) * num_amp_params]],
                                       parameters.params[-2](),
                                       parameters.params[-1](),
                                       transitions = transitions,
                                       chirpType = chirpType,
                                       pulseWidth = pulseWidth,
                                       span = span,
                                       offset = offset,
                                       lo = lo,
                                       fstart = fstart
                                       )
        return ret_val

    y = np.concatenate([spec_list[spec_id].y[idx_start:idx_stop] \
                        for spec_id in range(len(spec_list)) ])
    x = np.concatenate([spec_list[spec_id].x[idx_start:idx_stop] \
                        for spec_id in range(len(spec_list)) ])

    info = fit.fit(func, parameters.params,
                   y, \
                   x,
                   output = 'parameter')

    fit_y = func(x)

    return info, [fit_y[spec_id * len_spec:(spec_id+1) * len_spec] \
                  for spec_id in range(len(spec_list))]


def calibrateQPSKPulses(spec, frequency, idx_from = 0, zero_filling =
                        False):

    if len(spec) == 0:
        return

    # calculate frequency spectrum
    iq = []
    intensity = []
    for i in range(len(spec)):
        iq[i] = IQSpectrum(spec[i].x[idx_from:], spec[i].y[idx_from:])
        iq[i].calc_amplitude_spec(zero_filling = zero_filling)

    # determine intensity at frequency
    idx = np.abs(iq[0].spec_win_x-frequency).argmin()

    for i in range(len(spec)):
        intensity[i] = iq[i].spec_win_y[idx]
        int_cal_factor[i] = intensity[0]/intensity[1]
        print("Intensity for spec %d: %6.3g (rel.: %6.3g)" % (i,
                                                              intensity[i],
                                                              int_cal_factor[i]))
        iq[i].y *= int_cal_factor[i]
        ffts[i] = fftpack.fftshift(fftpack.fft(signal.hilbert(iq[i].y)))
        angles[i] = 180.0 * (np.arctan2(ffts[i].imag,ffts[i].real)) / np.pi
        diffangles[i] = angles[i][idx] - angles[0][idx]
        if diffangles[i] < 0:
            diffangles[i] = 360.0 + diffangles[i]

