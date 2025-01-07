#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module provides methods of filtering data arrays.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""

def get_fft(x, y, cutoff):
    """
    Performs a FFT filter on a dataset.
    
    :param x: the abscissa
    :param y: the ordinate
    :param cutoff: the fraction of the strongest power spectrum to cutoff
    :type x: list or ndarray
    :type y: list or ndarray
    :type cutoff: int or float
    :returns: the filtered ordinate
    :rtype: list or ndarray
    """
    from scipy.fftpack import rfft, rfftfreq, irfft
    N = len(y)
    dt = x[1]-x[0]
    f = rfftfreq(len(x), d=dt)
    w = rfft(y)
    # harmonics
    spectrum = w**2
    cutoff_idx = spectrum < (spectrum.max()/cutoff)
    # do cutoff & inverse, and return result
    w[cutoff_idx] = 0
    new_y = irfft(w)
    return new_y

def get_lowpass(y, order, rolloff):
    """
    Performs a low-pass Butterworth filter on a dataset.
    
    :param y: the ordinate
    :param order: the order to use for the rolloff
    :param rolloff: the lower frequency at which to begin the rolloff, normalized with respect to the Nyquist frequency (pi radians/sample /2) (see scipy.signal.butter() for details)
    :type y: list or ndarray
    :type order: int
    :type rolloff: float
    :returns: the filtered ordinate
    :rtype: list or ndarray
    """
    from scipy import signal
    b, a = signal.butter(order, rolloff, analog=False)
    new_y = signal.filtfilt(b, a, y)
    return new_y

def get_gauss(y, npts, sig):
    """
    Performs a Gaussian filter on a dataset.
    
    Note that this particular filter simply performs a convolution of the data
    with the created Gaussian.
    
    :param y: the ordinate
    :param npts: the width of the window to use
    :param sig: the standard deviation (i.e. amplitude) of the gaussian
    :type y: list or ndarray
    :type npts: int
    :type sig: int or float
    :returns: the filtered ordinate
    :rtype: list or ndarray
    """
    from scipy.signal import gaussian
    from scipy.ndimage import filters
    g = gaussian(npts, sig)
    new_y = filters.convolve1d(y, g/g.sum())
    return new_y

def get_wiener(y, npts):
    """
    Performs a Wiener filter on a dataset.
    
    :param y: the ordinate
    :param npts: the width of the window to use
    :type y: list or ndarray
    :type npts: int
    :returns: the filtered ordinate
    :rtype: list or ndarray
    """
    from scipy.signal import wiener
    new_y = wiener(y, npts)
    return new_y

def get_sg(y, npts, order=3):
    """
    Performs a Savitzky-Golay filter on a dataset.
    
    :param y: the ordinate
    :param npts: the width of the window to use
    :param order: (optional) the order to use for the shape of the polynomial (default: 3)
    :type y: list or ndarray
    :type npts: int
    :type order: int
    :returns: the filtered ordinate
    :rtype: list or ndarray
    """
    if not npts % 2: # force the value to be odd
        npts += 1
    new_y = savitzky_golay(y, npts, order)
    return new_y

def savitzky_golay(y, window_size, order, deriv=0, rate=1):
    """
    Smooth (and optionally differentiate) data with a Savitzky-Golay filter.
    The Savitzky-Golay filter removes high frequency noise from data.
    It has the advantage of preserving the original shape and
    features of the signal better than other types of filtering
    approaches, such as moving averages techniques.
    
    The Savitzky-Golay is a type of low-pass filter, particularly
    suited for smoothing noisy data. The main idea behind this
    approach is to make for each point a least-square fit with a
    polynomial of high order over a odd-sized window centered at
    the point.
    
    Source: http://scipy.github.io/old-wiki/pages/Cookbook/SavitzkyGolay
    
    Note: finally implemented in scipy >0.14.. this should be replaced by the scipy built-in
    
    :param y: the values of the time history of the signal.
    :param window_size: the length of the window. Must be an odd integer number.
    :param order: the order of the polynomial used in the filtering (note: ust be less then `window_size` - 1)
    :param deriv: the order of the derivative to compute (default = 0 means only smoothing)
    :type y: array_like, shape (N,)
    :type window_size: int
    :type order: int
    :type deriv: int
    :returns: the smoothed signal (or it's n-th derivative)
    :rtype: ndarray, shape (N)
    
    :Example:
    
    >>> t = np.linspace(-4, 4, 500)
    >>> y = np.exp( -t**2 ) + np.random.normal(0, 0.05, t.shape)
    >>> ysg = savitzky_golay(y, window_size=31, order=4)
    >>> import matplotlib.pyplot as plt
    >>> plt.plot(t, y, label='Noisy signal')
    >>> plt.plot(t, np.exp(-t**2), 'k', lw=1.5, label='Original signal')
    >>> plt.plot(t, ysg, 'r', label='Filtered signal')
    >>> plt.legend()
    >>> plt.show()
    """
    import numpy as np
    from math import factorial
    
    if isinstance(y, list):
        y = np.asarray(y)

    try:
        window_size = np.abs(np.int(window_size))
        order = np.abs(np.int(order))
    except ValueError as msg:
        raise ValueError("window_size and order have to be of type int")
    if window_size % 2 != 1 or window_size < 1:
        raise TypeError("window_size size must be a positive odd number")
    if window_size < order + 2:
        raise TypeError("window_size is too small for the polynomials order")
    order_range = list(range(order+1))
    half_window = (window_size-1) / 2
    # precompute coefficients
    b = np.mat([[k**i for i in order_range] for k in range(-half_window, half_window+1)])
    m = np.linalg.pinv(b).A[deriv] * rate**deriv * factorial(deriv)
    # pad the signal at the extremes with
    # values taken from the signal itself
    firstvals = y[0] - np.abs( y[1:half_window+1][::-1] - y[0] )
    lastvals = y[-1] + np.abs(y[-half_window-1:-1][::-1] - y[-1])
    y = np.concatenate((firstvals, y, lastvals))
    return np.convolve( m[::-1], y, mode='valid')