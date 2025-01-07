#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module provides a class for spectral catalogs, both their loading
and saving.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os, sys
if sys.version_info[0] == 3:
    import urllib.request as urllib
else:
    import urllib
import re
# third-party
from scipy import signal
from scipy import optimize
from scipy import interpolate
import numpy as np
import matplotlib.pyplot as plt
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import Spectrum.spectrum as spectrum

if sys.version_info[0] == 3:
    xrange = range


# some constants
wvn2mhz = 29979.2458
mhz2wvn = 1.0 / wvn2mhz

# Defines the gaussian function to be used in the fit routine
gaussian = lambda x, f, i, fwhm: i * np.exp(-(f-x)**2.0/(fwhm*0.600561204393225)**2)
gaussian2f = lambda x, f, i, fwhm: gaussian(x,f,i,fwhm) * ((fwhm*0.600561204393225)**2 - (f-x)**2)/(fwhm*0.600561204393225)**4
lorentzian = lambda x, f, i, fwhm: i * (fwhm/2.0)**2 / ((fwhm/2.0)**2 + (f-x)**2)
catexp = lambda e, t: np.exp(-e/0.695/t)
catescale = lambda f, t, e: (catexp(e,t)-catexp(e+f*mhz2wvn,t)) / (catexp(e,300)-catexp(e+f*mhz2wvn,300))

def parse_calpgm_int(value):
    """
    Converts a pickett integer value, which might contain strings, such as
    'A':10, 'B':11, 'a':-1 into a real integer. This has to be used to convert
    Quantum Numbers and degeneracies provided in the cat-file.

    :param value: spcat-integer 
    :type value: string
    """
    try:
        value = value.replace(' +','+1').replace(' -','-1').replace('  ',' 0') # hack for the parity entries of the CH3OH catalog
        ret_val = int(value)
    except:
        o = ord(value[0])
        rest = int(value[1:])

        if (o > 64 and o < 91):
            ret_val = 10**len(value[1:]) * (o - 55) + rest
        elif (o > 96 and o < 127):
            ret_val = 10**len(value[1:]) * (96 - o) - rest
        else:
            ret_val = None

    return ret_val

class QuantumNumbers(object):
    """
    """
    def __init__(self, qn):
        self.qn = qn
        if isinstance(qn, int):
            self.qn = (self.qn,)
        self.num_qn = len(self.qn)

    def __repr__(self):
        qn_str = ''
        for q in self.qn:
            qn_str += "%3d" % q
        return qn_str

    def __eq__(self, other):
        return self.qn == other.qn

    def __ne__(self, other):
        return not self.__eq__(other)

    def cat_str(self):
        qn_str = ''
        for i in xrange(8):
            if i > self.num_qn - 1:
                qn_str += "  "
            else:
                qn_str += "%2s" % formatqn(self.qn[i])
        return qn_str

    def egy_str(self):
        qn_str = ''
        for i in xrange(8):
            if i > self.num_qn - 1:
                qn_str += "  "
            else:
                qn_str += "%3s" % self.qn[i]
        return qn_str

    def lin_str(self):
        return self.egy_str()

    def match(self, qn):
        for i in xrange(qn.num_qn):
            if qn.qn[i] is None:
                continue
            if qn.qn[i] != self.qn[i]:
                return False
        return True

class Transition(object):
    """
    """
    def __init__(self, **kwds):
        self.update(**kwds)

    def update(self, **kwds):
        for ck in kwds.keys():
            if ck in vars(self).keys():
                self.__dict__.update({ck: kwds[ck]})
            else:
                setattr(self, ck, kwds[ck])

    def __repr__(self):
        return self.cat_str()

    def cat_str(self):
        if self.unit == 'wvn':
            unc = -self.calc_unc
        else:
            unc = self.calc_unc
        return '%13.4lf%8.4lf%8.4lf%2d%10.4lf%3d%7d%4d%12s%12s' % \
     (self.calc_freq, unc, np.log10(self.intensity), 3, self.egy_low,
      self.gup, self.tag, self.qntag, self.qn_up.cat_str(), self.qn_low.cat_str())
 
    def mrg_str(self):
        if self.exp_freq:
            freq = self.exp_freq
            unc = self.exp_unc
            tag = -self.tag
        else:
            freq = self.calc_freq
            unc = self.calc_unc
            tag = self.tag
        return '%13.4lf%8.4lf%8.4lf%2d%10.4lf%3d%7d%4d%12s%12s' % \
                 (freq, unc, np.log10(self.intensity), 3, self.egy_low,
                  self.gup, tag, self.qntag, self.qn_up.cat_str(), self.qn_low.cat_str())
 
    def lin_str(self):
        if not self.exp_freq:
            return ''
        return '%18s%18s%36.6lf%10.6lf%10.6lf     %s' % (self.qn_up.lin_str(), self.qn_low.lin_str(),
                             self.exp_freq, self.exp_unc, self.intensity,
                                                    self.comment)

class Transitions(object):
    def __init__(self):
        self.transitions = []

    def add_transition(self, transition):
        self.transitions.append(transition)

    def convert_unit(self, unit = 'MHz'):
        for t in self.transitions:
            if t.unit == unit:
                pass
            if unit == 'wvn':
                t.calc_freq = mhz2wvn * t.calc_freq
                t.calc_unc = mhz2wvn * t.calc_unc
                try:
                    t.exp_freq = mhz2wvn * t.exp_freq
                    t.exp_unc = mhz2wvn * t.exp_unc
                except:
                    pass
                t.unit = 'wvn'
            else:
                t.calc_freq = wvn2mhz * t.calc_freq
                t.calc_unc = wvn2mhz * t.calc_unc
                try:
                    t.exp_freq = wvn2mhz * t.exp_freq
                    t.exp_unc = wvn2mhz * t.exp_unc
                except:
                    pass
                t.unit = 'MHz'
 
    def __repr__(self):
        ret_str = ''
        for t in self.transitions:
            ret_str += t.__repr__() + '\n'
            #ret_str += '%13.4lf%8.4lf%8.4lf%2d%10.4lf%3d%7d%4d%12s%12s\n' %  (t.calc_freq, t.calc_unc, np.log10(t.intensity), 3, t.egy_low,
            #          t.gup, t.tag, t.qntag, t.qn_up.cat_str(), t.qn_low.cat_str())
 
        return ret_str

    def filter(self, **kwds):
        ret_list = []
        for i in xrange(len(self.transitions)):
            t = self.transitions[i]
            if ('qn_up' in kwds
                and not t.qn_up.match(kwds['qn_up'])):
                continue
            if ('qn_low' in kwds
                and not t.qn_low.match(kwds['qn_low'])):
                continue
            if ('freq_min' in kwds
                and t.calc_freq < kwds['freq_min']):
                continue
            if ('freq_max' in kwds
                and t.calc_freq > kwds['freq_max']):
                continue
            if ('intensity_min' in kwds
                and t.intensity < kwds['intensity_min']):
                continue
            ret_list.append(i)
        return ret_list

    def save(self, fname, fdir = '', ftype = 'cat'):
        """
        Saves list of states to file

        :param ftype: Fileformat (egy - spcat)
        """
        if (fdir and fdir[-1] != "/"):
            fdir = fdir + "/"
        f = open(fdir + fname, 'w')
        if ftype == 'cat':
            for t in self.transitions:
                f.write("%s\n" % t.cat_str())
        elif ftype == 'lin':
            for t in self.transitions:
                line = t.lin_str()
                if len(line)>0:
                    f.write("%s\n" % line)
        elif ftype == 'mrg':
            for t in self.transitions:
                f.write("%s\n" % t.mrg_str())
        else:
            for t in self.transitions:
                f.write("%s\n" % t.__repr__())
        f.close()

    def simulate_spectrum(self, freq_min, freq_max, line_width=1.0,
                          step_size=0.1, func=gaussian):
        """
        Simulates a spectrum for the specified frequency range.

        :param freq_min: Lower frequency limit.
        :type freq_min: float.
        :param freq_max: Upper frequency limit.
        :type freq_max: float.
        :param line_width: Width of the line (FWHM in units specified in
                           transitions).
        :type line_widht: float.
        :returns: list of float, list of float -- the simulated spectrum
        """
        trans = self.filter(freq_min=freq_min, freq_max=freq_max)
        # step_size = fak * line_width
        # generate frequency axis
        x = np.arange(freq_min, freq_max, step_size)
        y = np.zeros(len(x))

        # calculate gaussian
        xg = np.arange(-100.0 * line_width, 100.0 * line_width, step_size)
#        yg = gaussian(xg, 0.0, 1.0, line_width)
        yg = func(xg, 0.0, 1.0, line_width)
        glength = len(xg)
        gcenter = glength / 2

        for idx in trans:
            t = self.transitions[idx]
            f = t.calc_freq
            start_i = int(round((f - freq_min) / step_size) - gcenter)
            stop_i = start_i + glength

            if stop_i > len(y):
                stop_i = len(y)

            if start_i < 0:
                y[0:stop_i] += t.intensity * yg[-start_i:stop_i-start_i]
            else:
                y[start_i:stop_i] += t.intensity * yg[:stop_i-start_i]

        return spectrum.Spectrum(x, y)


class Predictions(Transitions):
    def __init__(self):
        super(Predictions, self).__init__()
        self.f2idx = {}
        self.freq_range = []

    def get_freq_range(self):
        """
        Returns the lower/upper frequency limits of the transitions
        contained herein.

        :returns: a pair of frequencies noting the lower/upper limits
        :rtype: tuple(float, float)
        """
        freq_sorted = sorted(self.transitions, key=lambda x: x.calc_freq)
        return (freq_sorted[0].calc_freq, freq_sorted[-1].calc_freq)

    def get_idx_from_freq(self, freq):
        """
        Returns the index to the transition list, based on the frequency.

        Note that if the reference frequency is input as a string, it must match
        exactly as how the library defined it: the float formatted as '%s'.

        :param freq: frequency that should be referenced
        :type freq: float (preferred) or str
        :returns: the index of the transition
        :rtype: int
        """
        if not isinstance(freq, str):
            freq = "%s" % freq
        if len(self.f2idx.keys()) < len(self.transitions):
            for idx,t in enumerate(self.transitions):
                self.f2idx['%s' % t.calc_freq] = idx
        return self.f2idx[freq]

    def temperature_rescaled_intensities(self, trot=None, freq_min=None, freq_max=None):
        """
        Returns the intensities rescaled for a different temperature,
        based on the partition function and transition energies.

        Note that for now, it only rescales the partition function
        contribution according to the 3/2+1 power law. This should be
        fixed, using a more rigorous partition function calculator!

        :param trot: temperature to be used for the rescaled intensities (in units: K)
        :param freq_min: lower frequency cutoff passed to the filter
        :param freq_max: upper frequency cutoff passed to the filter
        :type trot: int or float
        :type freq_min: float
        :type freq_max: float
        :returns: the list of indices of transitions and the list of rescaled intensities
        :rtype: tuple(list, np.ndarray)
        """
        # check input parameters
        if (not isinstance(trot, (int,float))) or (trot <= 0):
            raise SyntaxError("you did not request a positive value for the temperature: %s" % trot)
        if freq_min is None:
            freq_min = self.get_freq_range()[0]
        if freq_max is None:
            freq_max = self.get_freq_range()[1]
        # check that callable partition function exists, and create one if not
        if (not float(trot) == 300.0) and (not 'callable_partitionfunc' in vars(self).keys()):
            try:
                self.generate_callable_partitionfunc()
            except Exception as e:
                msg = "ERROR!\n"
                msg += "\tit seems there was an issue generating the partition function on the fly..\n"
                msg += "\tthere might be a problem with the quantum numbers; you should report this catalog"
                raise e
        # make copy of arrays
        x, y, e, idx = [], [], [], []
        for i in self.filter(freq_min=freq_min, freq_max=freq_max):
            if self.transitions[i].unit == 'MHz':
                x.append(self.transitions[i].calc_freq)
            else:
                x.append(self.transitions[i].calc_freq*wvn2mhz)
            y.append(self.transitions[i].intensity)
            e.append(self.transitions[i].egy_low)
            idx.append(i)
        x, y, e = np.asarray(x), np.asarray(y), np.asarray(e)
        if not float(trot) == 300.0:
            # rescale the intensities and return the frequencies and intensities
            y *= catescale(x, trot, e) * self.callable_partitionfunc(300)/self.callable_partitionfunc(trot)
        return idx, y
    
    def generate_callable_partitionfunc(self):
        """
        Generates a table of partition function values across a range
        of temperatures, and a callable interpolated spline.
        
        Note that the range in which this works is 1--300 K. Values
        outside this range will default to the value at 300 K, thus
        yielding only reasonable relative intensities but not absolute.
        """
        # generate list of upper states, based on transitions
        self.states = States()
        qn_set = set()
        for idx,trans in enumerate(self.transitions):
            if repr(trans.qn_up) in qn_set: # set speeds up inclusion check by 20-30x
                continue
            if trans.unit == 'MHz':
                egy_up = trans.egy_low + trans.calc_freq*mhz2wvn
            else:
                egy_up = trans.egy_low + trans.calc_freq
            self.states.add_state(State(
                qn=trans.qn_up,
                energy=egy_up,
                degeneracy=trans.gup))
            qn_set.add(repr(trans.qn_up))
        
        # based on those states, generate a table
        self.calc_partitionfunc = ([], [])
        for t in [2.725, 5, 9.375, 18.75, 37.5, 75, 150, 225, 300, 500, 1000]:
            try:
                self.calc_partitionfunc[1].append(self.states.calc_partitionfunc(t))
                self.calc_partitionfunc[0].append(t)
            except:
                pass
        
        # create a callable interpolative spline
        self.callable_partitionfunc = interpolate.interp1d(
            self.calc_partitionfunc[0], self.calc_partitionfunc[1],
            kind='cubic', bounds_error=False, fill_value=self.calc_partitionfunc[1][-1])

def load_predictions(filename, unit='MHz', url=None, tunit=None):
    """
    This method loads predictions from a calpgm cat-file and returns a
    Transitions - object.

    :param filename: name of the cat-file
    :type filename: string
    :param unit: Unit of frequencies (MHz|wvn)
    :type unit: string
    :param url: Use specified url instead of file
    :type url: string
    """
    if url:
        f = urllib.urlopen(url)
    else:
        f = open(filename)
    p = Predictions()
    p.filename = filename
    for line in f:
        calc_freq = float(line[0:13])
        calc_unc = float(line[13:21])
        intensity = np.power(10, float(line[21:29]))
        dof = int(line[29:31])
        egy_low = float(line[31:41])
        gup = parse_calpgm_int(line[41:44])
        tag = int(line[44:51])
        qntag = int(line[51:55])

        qn_str = line[55:79]
        if (len(line[79:]) and
            re.search(r'[0-9]', line[79:]) and
            not re.search(r'[a-zA-Z]', line[79:])):
            qn_str = line[55:]
        qn_up_str = qn_str[:len(qn_str)//2].rstrip()
        qn_low_str = qn_str[len(qn_str)//2:].rstrip()
        
        qn_up = QuantumNumbers(tuple(parse_calpgm_int(qn_up_str[2*i:2*i+2]) for i in
                                      xrange(len(qn_up_str)//2)))
        qn_low = QuantumNumbers(tuple(parse_calpgm_int(qn_low_str[2*i:2*i+2]) for i in
                                      xrange(len(qn_low_str)//2)))

        # Convert unit to what is requested (MHz or wvn)
        if tunit is None:
            tunit = 'wvn' if (calc_unc < 0) else 'MHz'
        if unit != tunit:
            if unit == 'MHz':
                calc_freq = wvn2mhz * calc_freq
                calc_unc = wvn2mhz * calc_freq
            else:
                calc_freq = mhz2wvn * calc_freq
                calc_unc = mhz2wvn * calc_unc

        #self.transitions[qns] = {'freq': freq, 'intensity': intensity, 'unit': tunit, 'flag': 0}
        trans = Transition(qn_up=qn_up, qn_low=qn_low, qn_str=qn_str,
                           calc_freq=calc_freq, calc_unc=np.abs(calc_unc),
                           intensity=intensity, egy_low=egy_low, gup=gup,
                           tag=tag, qntag=qntag, unit=unit)
        p.add_transition(trans)
        p.unit = unit
    f.close()
    return p


def load_predictions_pamc2v(filename, unit='MHz', url=None, tunit=None):
    """
    This method loads predictions from a pamc2v-file and returns a
    Transitions - object.

    :param filename: name of the cat-file
    :type filename: string
    :param unit: Unit of frequencies (MHz|wvn)
    :type unit: string
    :param url: Use specified url instead of file
    :type url: string
    """
    if url:
        f = urllib.urlopen(url)
    else:
        f = open(filename)
    p = Predictions()
    p.filename = filename
    line_counter = 0
    for line in f:
        line_counter += 1
        if line_counter < 10:
            continue
        calc_freq = float(line[55:69])
        calc_unc = float(line[70:78])
        intensity = float(line[42:55])
#        dof = int(line[29:31])
        egy_low = float(line[79:91])
#        gup = parse_calpgm_int(line[41:44])
#        tag = int(line[44:51])
#        qntag = int(line[51:55])

        qn = line[:46].split()
        qn_up = QuantumNumbers( (int(qn[2]), int(qn[3]), int(qn[4]), int(qn[1]),
                                 int(qn[10])))
        qn_low = QuantumNumbers( (int(qn[7]), int(qn[8]), int(qn[9]),
                                  int(qn[6]), int(qn[10])))

        gup = 2.0 * int(qn[2]) + 1
        tag = 99999
        qntag = 99999

 #       if (len(line[79:]) and
 #           re.search(r'[0-9]', line[79:]) and
 #           not re.search(r'[a-zA-Z]', line[79:])):
 #           qn_str = line[55:]
 #       qn_up_str = qn_str[:len(qn_str)//2].rstrip()
 #       qn_low_str = qn_str[len(qn_str)//2:].rstrip()
        

        # Convert unit to what is requested (MHz or wvn)
        if tunit is None:
            tunit = 'wvn' if (calc_unc < 0) else 'MHz'
        if unit != tunit:
            if unit == 'MHz':
                calc_freq = wvn2mhz * calc_freq
                calc_unc = wvn2mhz * calc_freq
            else:
                calc_freq = mhz2wvn * calc_freq
                calc_unc = mhz2wvn * calc_unc

        #self.transitions[qns] = {'freq': freq, 'intensity': intensity, 'unit': tunit, 'flag': 0}
        trans = Transition(qn_up=qn_up, qn_low=qn_low, #qn_str=qn_str,
                           calc_freq=calc_freq, calc_unc=np.abs(calc_unc),
                           intensity=intensity, egy_low=egy_low, gup=gup,
                           tag=tag, qntag=qntag, unit=unit)
        p.add_transition(trans)
        p.unit = unit
    f.close()
    return p
       
def load_predictions_from_cdms(SpeciesID, Freq_From, Freq_To, Temperature =
                               300.0, order_by = 'frequency'):
    if float(Temperature) != 300.0:
        temp_string = 'and+EnvironmentTemperature=150+'
    else:
        temp_string = ''
    url = 'http://cdms.ph1.uni-koeln.de/cdms/tap/sync?REQUEST=doQuery&LANG=VSS2&FORMAT=spcat&QUERY=\
            SELECT+RadiativeTransitions+WHERE+SpeciesID=%d+%sand+RadTransFrequency>%f+\
            and+RadTransFrequency<%f&ORDERBY=%s' % (SpeciesID, temp_string, Freq_From, Freq_To, order_by)
    print(url)
    return load_predictions('dummy', unit = 'MHz', url = url)

class State(object):
    """
    """
    def __init__(self, **kwds):
        self.update(**kwds)

    def update(self, **kwds):
        for ck in kwds.keys():
            if ck in vars(self).keys():
                self.__dict__.update({ck: kwds[ck]})
            else:
                setattr(self, ck, kwds[ck])

    def __repr__(self):
        if hasattr(self, 'blk') and self.blk:
            blk = '%6d' % self.blk
        else:
            blk = '     '
        if hasattr(self, 'idx') and self.idx:
            idx = '%5d' % self.idx
        else:
            idx = '     '
        if hasattr(self, 'acc') and self.acc:
            acc = '%18.6lf' % self.acc
        else:
            acc = '%18s' % ''
        if hasattr(self, 'mix') and self.mix:
            mix = '%11.6lf' % self.mix
        else:
            mix = '%11s' % ''
 
        if hasattr(self, 'degeneracy'):
            deg = '%5d' % self.degeneracy
        else:
            deg = '%5s' % ''
        return '%s%s%18.6lf%s%s%s:%s' % (blk, idx, self.energy, acc, mix,
                                                   deg, self.qn.egy_str())

class States():
    def __init__(self):
        self.states = []
        self.qn_idx = {}

    def add_state(self, state):
        self.states.append(state)

    def __repr__(self):
        ret_str = ''
        for s in self.states:
            ret_str += s.__repr__() + '\n'
        return ret_str

    def filter(self, qn):
        ret_list = []
        for i in xrange(len(self.states)):
            if self.states[i].qn.match(qn):
                ret_list.append(i)
        return ret_list

    def save(self, fname, fdir = '', ftype = 'egy'):
        """
        Saves list of states to file

        :param ftype: Fileformat (egy - spcat)
        """
        if (fdir and fdir[-1] != "/"):
            fdir = fdir + "/"
        f = open(fdir + fname, 'w')
        for s in self.states:
            f.write("%s\n" % s.__repr__())
        f.close()

    def calc_partitionfunc(self, temperature = 300.0):
        pf = 0
        for s in self.states:
            pf += s.degeneracy * np.exp(-1.43878 * s.energy / temperature)
        return pf

def load_egy(filename, unit = 'wvn'):
    """
    Load state information from egy-file (calpgm - suite) and returns a States -
    object.

    :param filename: Name of the egy-file (path has to be included)
    :type filename: str
    :param unit: energy unit
    :type unit: str
    """

    f = open(filename)
    states = States()
    for line in f:
        blk = line[:6].strip()        
        idx = line[6:11].strip()
        energy = float(line[11:29])
        acc    = line[29:47].strip()
        mix    = line[47:58].strip()
        deg = int(line[58:63])
        qns = line[64:].rstrip()

        blk = int(blk) if blk else None
        mix = int(mix) if mix else None
        acc = float(acc) if acc else None

        qn = QuantumNumbers(tuple(int(qns[3*i:3*i+3]) for i in
                                         xrange(len(qns)//3)))
        state = State(qn = qn, energy = energy, acc = acc, mix = mix,
                      degeneracy = deg, blk = blk, idx = idx)
        states.add_state(state)

        states.qn_idx['_'.join(str(i) for i in qn.qn)] = len(states.states)-1
    f.close()
    return states

class Lines():
   """
   This class contains functions to load, filter, and convert experimental lines (lin-file).
   Supported file formats are lin-files.
   """
   transitions = {}

   def __init__(self, filename, unit = 'MHz'):
      """
      Initializes an instance based on the specified lin-file.
      """
      f = open(filename)
      self.transitions = {}
      self.unit = unit

      for line in f:
         qns = line[:36].split()
         rest = line[36:].split()
         freq = float(rest[0])
         unc = float(rest[1])
         if unc < 0:
             tunit = 'wvn' 
             unc = -unc
         else:
             tunit = 'MHz'

         if unit == tunit:
            pass
         elif unit == 'MHz' and tunit == 'wvn':
             freq = freq * wvn2mhz
             unc = unc * wvn2mhz
         elif unit == 'wvn' and tunit == 'MHz':
             freq = freq * mhz2wvn
             unc = unc * mhz2wvn

         qn_count = len(qns)//2
         qn_key = ''
         for i in xrange(qn_count):
             qn_key += '%2d' % int(qns[i])
         for i in xrange(6 - qn_count):
             qn_key += '  '
         for i in xrange(qn_count):
             qn_key += '%2d' % int(qns[i + qn_count])
         for i in xrange(6 - qn_count):
             qn_key += '  '
         self.transitions[qn_key] = {'freq': freq, 'unit': tunit, 'flag': 0, 'unc': unc}

   def convertUnit(self, unit):
       """
       Converts the units from MHz to wavenumber and vice versa

       :param unit: The unit to which the data is converted.
       :type unit: str.
       """

       for qn in self.transitions:
           tunit = self.transitions[qn]['unit']
           if tunit == unit:
              continue
           elif (unit == 'MHz' and tunit == 'wvn'):
              self.transitions[qn]['unit'] = 'MHz'
              self.transitions[qn]['freq'] *= wvn2mhz
           elif (unit == 'wvn' and tunit == 'MHz'):
              self.transitions[qn]['unit'] = 'wvn'
              self.transitions[qn]['freq'] *= mhz2wvn
           else:
              pass

   def filter_transitions(self, qn_up1 = None, qn_up2 = None, qn_up3 = None, qn_up4 = None, qn_up5 = None, qn_up6 = None,
                                qn_low1 = None, qn_low2 = None, qn_low3 = None, qn_low4 = None, qn_low5 = None, qn_low6 = None, freq_min = 0, freq_max = 1.0e30, flag = None):
       """
       Filters the list of transitions using specified kwargs.


       :param qn_up1: first upper quantum number (e.g. J).
       :type qn_up1: integer
       :param qn_up2: second upper quantum number (e.g. Ka).
       :type qn_up1: integer
       :param qn_up3: third upper quantum number (e.g. Kc).
       :type qn_up1: integer
       :param qn_up4: fourth upper quantum number (e.g. state identifier).
       :type qn_up1: integer
       :param qn_up5: fifth upper quantum number.
       :type qn_up1: integer
       :param qn_up6: sixth upper quantum number.
       :type qn_up1: integer
       :param freq_min: lower frequency limit.
       :type freq_min: float
       :param freq_max: upper frequency limit.
       :type freq_max: float
       :param intensity_min: lower intensity limit.
       :type intensity_min: float
       :param flag: flag of a transition (to exclude specific transitions)
       :type flag: int

       :Returns: list of str. The list contains the keys of the predicitions.
       """
       qn_list = []
       for qn in self.transitions.keys():
           if not qn_up1 is None:
              if int(qn[:2]) != qn_up1:
                 continue
           if not qn_up2 is None:
              if int(qn[2:4]) != qn_up2:
                 continue
           if not qn_up3 is None:
              if int(qn[4:6]) != qn_up3:
                 continue
           if not qn_up4 is None:
              if int(qn[6:8]) != qn_up4:
                 continue
           if not qn_up5 is None:
              if int(qn[8:10]) != qn_up5:
                 continue
           if not qn_up6 is None:
              if int(qn[10:12]) != qn_up6:
                 continue
           if not qn_low1 is None:
              if int(qn[12:14]) != qn_low1:
                 continue
           if not qn_low2 is None:
              if int(qn[14:16]) != qn_low2:
                 continue
           if not qn_low3 is None:
              if int(qn[16:18]) != qn_low3:
                 continue
           if not qn_low4 is None:
              if int(qn[18:20]) != qn_low4:
                 continue
           if not qn_low5 is None:
              if int(qn[20:22]) != qn_low5:
                 continue
           if not qn_low6 is None:
              if int(qn[22:24]) != qn_low6:
                 continue
           if (self.transitions[qn]['freq'] < freq_min or self.transitions[qn]['freq'] > freq_max):
                 continue
           if not flag is None:
              if self.transitions[qn]['flag'] != flag:
                 continue
           qn_list.append(qn)
       return qn_list

 
# SHOULD BE REMOVED BY Spectrum.spectrum.py
class SpectrumOLD():
    """
    Defines a spectrum and methods display and analyze it.
    """
    def __init__(self, x, y):
        """
        Initializes a spectrum

        :param x: x-axis datapoints (Frequency)
        :type x: float
        :param y: y-axix datapoints (Intensity)
        :type y: float
        """
        self.x = np.array(x)
        self.y = np.array(y)
        self.step = (x[-1]-x[0]) / float(len(x))
        self.bandwith = x[-1] - x[0]
        self.startfreq = self.x[0]
        self.stopfreq = self.x[-1]

    def find_peaks(self, min_x = None, max_x = None, width = np.arange(10,15), min_snr = 5000):
        """
        Finds the peaks within the spectrum. This method is based on scipy.signal's peakfinder.

        :param min_x: Lower limit of the frequency range in which peaks are to be searched.
        :type min_x: float
        :param max_x: Upper limit of the frequency range in which peaks are to be searched.
        :type max_x: float
        :param width: list of number of points which define the tested linewidth of peaks
        :type width: list of integers
        :param min_snr: minimal signal to noise level of peaks
        :type min_snr: integer
        :returns: list of peaks, list of peak frequencies, list of peak intensities
        """
        if min_x:
            start_x = int(( min_x - self.x[0] ) / self.step)
        else:
            start_x = 0
        if max_x:
            vec = np.array(self.y[start_x: int((max_x - self.x[0]) / self.step)])
        else:
            vec = np.array(self.y[start_x:])

        peakind = list(np.array( signal.find_peaks_cwt( vec , width, min_snr = min_snr) ) + start_x)

        return peakind , list(np.array(self.x)[peakind]), list(np.array(self.y)[peakind])

    def save(self, filename, directory = os.getcwd() ):
        """
        Saves spectrum to file (x, y data separated by space)

        :param filename: name of the file
        :type filename: string
        :param directory: name of the directory where the file is saved to
        :type directory: string
        """
        if directory[-1] != '/':
            directory = directory + "/"

        print("save spectrum %s" % (directory + filename))
        f = open(directory + filename, 'w')
        for i in xrange(len(self.x)):
            f.write('%lf  %g \n' % (self.x[i], self.y[i]) )
        f.close()

    def plot(self, fstart = None, fstop = None, fcenter = None, span = None, foffset = None, yoffset = 0.0):
        """
        Plots the spectrum.

        :param fstart: lower frequency limit of the ploted frequency range
        :type fstart: float
        :param fstop: upper frequency limit of the ploted frequency range
        :type fstop: float
        :param fcenter: center frequency of the ploted frequency range
        :type fcenter: float
        :param span: frequency span of the ploted frequency range
        :type span: float
        :param foffset: offset, which is substracted from the frequency axis
        :type foffset: float
        :param yoffset: offset, which is added to the intensity-axis
        :type yoffset: float
        """

        starti = 0
        stopi = -1
        if fstart:
            starti = np.argmin(abs(self.x - fstart))
            if span:
                stopi = np.argmin(abs(self.x - (fstart + span)))
        if fstop and stopi == -1:
            stopi = np.argmin(abs(self.x - fstop))
            if span and starti == 0:
                starti = np.argmin(abs(self.x - (fstop-span)))
        if fcenter:
            if span:
                starti = np.argmin(abs(self.x - fcenter + 0.5*span))
                stopi = np.argmin(abs(self.x - fcenter - 0.5*span))

        if foffset:
            offseti = np.argmin(abs(self.x - foffset))
            offset = self.x[offseti]
        else:
            offset = 0

        plt.figure(1)
        plt.plot(self.x[starti:stopi]-offset, self.y[starti:stopi]+yoffset)
        plt.show()

    def get_range(self, startx, stopx):
        """
        Returns part of the spectrum

        :param startx: lower frequency limit
        :type startx: float
        :param stopx: upper frequency limit
        :type stopx: float
        :returns: list of frequency points, list of intensity points
        """
        starti = 0
        stopi = -1
        for i in xrange(len(self.x)):
            if (starti == 0 and self.x[i] > startx):
                starti = i
            if (stopi == -1 and self.x[i] > stopx):
                stopi = i-1

        return self.x[starti:stopi], self.y[starti:stopi]

    def fit_line(self, f, startx, stopx, intensity=1.0, fwhm = 1.0e-3, fix_fwhm = True):
        """
        Fits a gaussian line profile to the peak.

        :param f: initial frequency
        :type f: float
        :param startx: lower limit of the frequency range
        :type startx: float
        :param stopx: upper limit of the frequency range
        :type stopx: float
        :param intensity: initial intensity
        :type intensity: float
        :param fwhm: initial line width (in ...)
        :type fwhm: float
        :param fix_fwhm: fix line width during the fit (True: do not include parameter)
        :type fix_fwhm: boolean
        :returns: fit-result as obtained by scipy's leassq - fit
        """
        x, y = self.get_range(startx, stopx)
        frequency = Parameter(f)
        intensity = Parameter(intensity)
        param = [frequency, intensity]
        # width will be fixed if not specified
        if fix_fwhm:
           fwhm = fwhm
           func = lambda x: gaussian(x, frequency(), intensity(), fwhm)
        else:
           fwhm = Parameter(fwhm)
           param.append(fwhm)
           func = lambda x: gaussian(x, frequency(), intensity(), fwhm())

        return fit(func, param, y, x)

# General functions

def parse_qn(qn):
    """
    Parses the quantum numbers string used in the cat-file to a list of quantum numbers

    :param qn: qn-string from spcat-file
    :type qn: string
    :returns: list of quantum numbers
    """
    return [qn[:2], qn[2:4], qn[4:6], qn[6:8], qn[8:10], qn[10:12], qn[12:14], qn[14:16],qn[16:18], qn[18:20], qn[20:22],qn[22:24]]

def catQn2linQn(qn):
    """
    Converts the string of quantum numbers used in spcat to format used in lin-file

    :param qn: qn-string from spcat-file
    :type qn: string
    :returns: quantum numbers string in lin-file format
    """
    qnlist = parse_qn(qn)
    qn = [int(q) if q!= '  ' else None for q in qnlist]
    if qnlist[1] == '  ':
        str_out = '%3d%3d' % (qn[0], qn[6])
    elif qnlist[2] == '  ':
        str_out = '%3d%3d%3d%3d' % (qn[0], qn[1], qn[6], qn[7])
    elif qnlist[3] == '  ':
        str_out = '%3d%3d%3d%3d%3d%3d' % (qn[0], qn[1], qn[2], qn[6], qn[7], qn[8])
    elif qnlist[4] == '  ':
        str_out = '%3d%3d%3d%3d%3d%3d%3d%3d' % (qn[0], qn[1], qn[2], qn[3], qn[6], qn[7], qn[8], qn[9])
    elif qnlist[5] == '  ':
        str_out = '%3d%3d%3d%3d%3d%3d%3d%3d%3d%3d' % (qn[0], qn[1], qn[2], qn[3], qn[4], qn[6], qn[7], qn[8], qn[9], qn[10])
    else:
        str_out = '%3d%3d%3d%3d%3d%3d%3d%3d%3d%3d%3d%3d' % (qn[0], qn[1], qn[2], qn[3], qn[4], qn[5], qn[6], qn[7], qn[8], qn[9], qn[10], qn[11])

    return '%-36s' % str_out

def output_transitions( predictions, qn, offset, linfile = None, dirname = os.getcwd(), unc = 0.001):
    """
    Creates lin-file with transitions which share the same upper energy level based on the determined offset.

    :param predictions: Predictions
    :type predicions: Predictions
    :param qn: list of upper state energy levels
    :type qn: list of integers
    :param offset: offset which is added to the calculated frequency of each transition
    :type offset: float
    :param linfile: output filename
    :type linfile: string
    :param dirname: directory where the file is saved to
    :type dirname: string
    """
    if linfile:
       lf = open(linfile, 'a')
    else:
       lf = open('exptrans_%d_%d_%d_%d.lin' % (qn[0],qn[1],qn[2],qn[3]), 'a' )


    for qnstr in predictions.filter_transitions(qn_up1 = qn[0], qn_up2 = qn[1], qn_up3 = qn[2], qn_up4 = qn[3]):
        qnstr_lin = catQn2linQn(qnstr)
        lf.write('%s%16.6lf %8.6lf              %8.6lf \n' % (qnstr_lin, predictions.transitions[qnstr]['freq'] + offset, unc, offset) )
    lf.close()

def generate_linelists(basename, predictions, dirname = os.getcwd(), scan_range = 2.0, centerfreq = 0.0, overwrite = False, width = np.arange(10,15), min_snr = 5000 ):
    """
    Determines peaks and outputs lin-files for all spectra stored in a common directory following the filename labeling scheme 'basename'_qn1_..._qnX.xxx.

    :param basename: common part of the filename (quantum numbers excluded)
    :type basename: string
    :param predictions: predictions which are used to create the linfile (frequency and quantum number information is used)
    :type predictions: predictions
    :param dirname: directory which is processed
    :type dirname: string
    :param scan_range: frequency span which is scanned for peaks
    :type scan_range: float
    :param centerfreq: center-frequency of the offset frequency range which is scanned for peaks
    :type centerfreq: float
    :param overwrite: Specifies if lin-files are replaced or not
    :type overwrite: boolean
    :param width: list of number of points which might determine peak (used in the peak finder)
    :type width: list of integers
    :param min_snr: minimal signal to noise ratio of the peak (used in the peak finder)
    :type min_snr: integer
    """
    if dirname[-1] != '/':
       dirname = dirname + "/"

    # Loops over all files identified by basename
    for fname in os.listdir(dirname):
       if fname[:len(basename)] == basename:
          qn = fname[len(basename):].split('.')[0].split('_')
          qn = [int(q) for q in qn]
          # Skip analysis if file already exists.
          if (overwrite == False and os.path.exists(dirname + 'exptrans_%d_%d_%d_%d.lin' % (qn[0],qn[1],qn[2],qn[3]) ) ):
              continue
          s = load_spectrum(dirname + fname)
          print("Scan for transitions J: %d Ka: %d Kc: %d, v: %d" % (qn[0], qn[1], qn[2], qn[3]))
          if type(centerfreq) == dict:
              cfreq = centerfreq['%d' % qn[1]]
          else:
              cfreq = centerfreq
          try:
             pl = s.find_peaks(-scan_range + cfreq, scan_range + cfreq, min_snr = min_snr, width = width)
          except:
             print("Error occured. Skip scan.")
             continue
          # print(pl)
          counter = 0 # Try it 5 times with different snr_values
          while (counter < 5):
             if (len(pl[0]) == 1):
                offset = pl[1][0]
                print("Assign offset for J: %d Ka: %d Kc: %d, v: %d  === %lf " % (qn[0], qn[1], qn[2], qn[3], offset))
                output_transitions( predictions, qn, offset)
                counter = 5
             elif (len(pl[0]) > 1):
                print("Multiple peaks found!")
                output_offset_list( pl, qn )
                for offset in pl[1]:
                    output_transitions( predictions, qn, offset, unc = 999.001)
                counter = 5
             else:
                print("No peak found! Try again ...")
                counter += 1
                pl = s.find_peaks(-scan_range + cfreq, scan_range + cfreq, min_snr = min_snr / (counter * 5.0), width = width )

def generate_linelist(fname, basename, predictions, dirname = os.getcwd(), scan_range = 2.0, centerfreq = 0.0, overwrite = False, width = np.arange(10,15), min_snr = 5000 ):
    """
    Determines peaks and outputs lin-files for a cross-correlation spectrum.

    :param fname: filename of the cross-correlation spectrum (format: 'basename'_qn1_..._qnX.xxx).
    :type fname: string
    :param basename: common part of the filename (quantum numbers excluded)
    :type basename: string
    :param predictions: predictions which are used to create the linfile (frequency and quantum number information is used)
    :type predictions: predictions
    :param dirname: directory which is processed
    :type dirname: string
    :param scan_range: frequency span which is scanned for peaks
    :type scan_range: float
    :param centerfreq: center-frequency of the offset frequency range which is scanned for peaks
    :type centerfreq: float
    :param overwrite: Specifies if lin-files are replaced or not
    :type overwrite: boolean
    :param width: list of number of points which might determine peak (used in the peak finder)
    :type width: list of integers
    :param min_snr: minimal signal to noise ratio of the peak (used in the peak finder)
    :type min_snr: integer
    """

    if dirname[-1] != '/':
       dirname = dirname + "/"

    qn = fname[len(basename):].split('.')[0].split('_')
    qn = [int(q) for q in qn]
    # Skip analysis if file already exists.
    if (overwrite == False and os.path.exists(dirname + 'exptrans_%d_%d_%d_%d.lin' % (qn[0],qn[1],qn[2],qn[3]) ) ):
         print("File already exists!")
         return
    s = load_spectrum(dirname + fname)
    print("Scan for transitions J: %d Ka: %d Kc: %d, v: %d" % (qn[0], qn[1], qn[2], qn[3]))
    try:
        pl = s.find_peaks(-scan_range + centerfreq, scan_range + centerfreq, min_snr = min_snr, width = width)
    except:
        print("Error occured. Skip scan.")
        return
    # print(pl)
    counter = 0 # Try it 5 times with different snr_values
    while (counter < 5):
        if (len(pl[0]) == 1):
           offset = pl[1][0]
           print("Assign offset for J: %d Ka: %d Kc: %d, v: %d  === %lf " % (qn[0], qn[1], qn[2], qn[3], offset))
           output_transitions( predictions, qn, offset)
           counter = 5
        elif (len(pl[0]) > 1):
           print("Multiple peaks found!")
           output_offset_list( pl, qn )
           for offset in pl[1]:
               output_transitions( predictions, qn, offset, unc = 999.001)
           counter = 5
        else:
           print("No peak found! Try again ...")
           counter += 1
           pl = s.find_peaks(-scan_range + centerfreq, scan_range + centerfreq, min_snr = min_snr / (counter * 5.0) )


def fit_linelist(spectrum, linfile, outfile):
    """
    Fits transtions in an experimental spectrum.

    :param spectrum: experimental spectrum
    :type spectrum: spectrum
    :param linfile: lin-file which includes transitions and their initial values to be used in the fit
    :type linfile: string
    :param outfile: output filename
    :type outfile: string
    """
    f = open(linfile)
    fo = open(outfile, 'w')

    for line in f:
       l = line.split()
       peakfreq = float(l[8])
       pout, success = spectrum.fit_line(peakfreq, peakfreq- 0.003, peakfreq + 0.003)
       fo.write("%s %12.8lf %d %12.8lf \n" % (line.strip(), pout[0], success, pout[0] - peakfreq))

    f.close()
    fo.close()

def combine_linelists(basename, outfile, dirname = os.getcwd() ):
    """
    Copies the content of all files whose name begin with 'basename'
    into one file

    :param basename: common part of the filename
    :type basename: string
    :param outfile: output filename
    :type outfile: string
    :param dirname: directory where the files are located
    :type dirname: string
    """
    if dirname[-1] != '/':
       dirname = dirname + "/"

    fo = open(dirname + outfile, 'w')

    for fname in os.listdir(dirname):
        if (fname[:len(basename)] == basename and (fname != outfile )):
           f = open(dirname + fname)
           for line in f:
               fo.write(line)
           f.close()
    fo.close()







 
def convertEgy(fname):
    """
    Convert file into pickett format.

    :param fname: Input filename
    """
    s = States()
    f = open(fname)

    for line in f:
        if len(line.strip()) == 0:
            continue

        data = line.split()

        if data[0].strip() not in ('A', 'E'):
            continue
        if data[1].strip() != 'VT':
            continue

        # A VT =   0 N =   1 K =   1 E =   139.3880893768 +   E = 139.4159179687 -
        rotSym = data[0].strip()
        v = int(data[3].strip())
        N = int(data[6].strip())
        K = int(data[9].strip())
        E1 = float(data[12].strip())
        p1 = data[13].strip()
        deg = 2*N+1
        sym1 = int(p1+'1')
        if (K == 0 and rotSym == 'A'):
            E2 = None
            p2 = None
        else:
            E2 = float(data[16].strip())
            p2 = data[17].strip()
            sym2 = int(p2+'1')

        if rotSym == 'A':
            vib1 = v * 3
            vib2 = v * 3
        else:
            vib1 = v * 3 + 1
            vib2 = v * 3 + 2

        # Determine Kc
        if K == 0:
            Kc1 = N
        else:
            if E1 > E2:
                Kc1 = N - K 
                Kc2 = N - K + 1
            else:
                Kc1 = N - K + 1
                Kc2 = N - K 

        qn = QuantumNumbers((N, K, Kc1, vib1, sym1))

        state = State(qn = qn, energy = E1, degeneracy = deg)
        s.add_state(state)
        #print('           %18lf%18s%11s%5d:%3d%3d%3d%3d%3d' % (E1, ' ', ' ', deg, N, K, 0, vib1, sym1))
        if (E2 and K > 0):
            qn = QuantumNumbers((N, K, Kc2, vib2, sym2))
            state = State(qn = qn, energy = E2, degeneracy = deg)
            s.add_state(state)
            #print('           %18lf%18s%11s%5d:%3d%3d%3d%3d%3d' % (E2,' ', ' ', deg, N, K, 0, vib2, sym2))

    f.close()

    # Determine Zero-Point Energy
    qn_origin = QuantumNumbers((0, 0, 0, 0))
    s_origin = s.filter(qn_origin)
    if len(s_origin) == 1:
        s_origin = s.states[s_origin[0]]
        s.zero_point_energy = s_origin.energy
    else:
        print("Could not determine Zero-Point Energy from Dataset")

    return s

def convertTransitions(fname, tag, qntag):
    """
    Convert Li Hong Xu's transitions into pickett format
    
    :param fname: Input filename
    """

    p = Predictions()
    f = open(fname)

    for line in f:
        # upper state quanta
        try:
            vup = int(line[:4])
        except:
            continue
        nup = int(line[4:8])
        kaup = int(line[8:13])
        kcup = int(line[13:17])
        pup = line[17:19].strip()
        
        # lower state quanta
        vlow = int(line[19:23])
        nlow = int(line[23:27])
        kalow = int(line[27:32])
        kclow = int(line[32:36])
        plow = line[36:38].strip()

        if len(pup)>0:
            rotSym = 'A'
            pup = int(pup+'1')
            plow = int(plow+'1')
        else:
            rotSym = 'E'

        if rotSym == 'E':
            pup = np.sign(kaup)
            plow = np.sign(kalow)
            if pup == 0:
                pup = 1
            if plow == 0:
                plow = 1
            kaup = abs(kaup)
            kalow = abs(kalow)

        if rotSym == 'A':
            vibup = 3 * vup 
            viblow = 3 * vlow
        if rotSym == 'E':
            if pup < 0:
                vibup = 3 * vup + 2
            else:
                vibup = 3 * vup + 1
            if plow < 0:
                viblow = 3 * vlow + 2
            else:
                viblow = 3 * vlow + 1

        qn_up = QuantumNumbers((nup, kaup, kcup, vibup, pup))
        qn_low = QuantumNumbers((nlow, kalow, kclow, viblow, plow))

        # get frequencies
        exp_freq, exp_unc, exp_comment = get_frequency(line[38:59])
        calc_freq, calc_unc, calc_comment = get_frequency(line[59:80])

        intensity = float(line[80:92])
        elow = float(line[92:102].strip())
        comment = line[102:].strip()
        gup = 2 * nup + 1

        t = Transition(qn_up = qn_up, qn_low = qn_low, calc_freq = calc_freq,
                       calc_unc = calc_unc, exp_freq = exp_freq, exp_unc =
                       exp_unc, intensity = intensity, egy_low = elow, gup =
                       gup, tag = tag, qntag = qntag, comment = comment)

        p.add_transition(t)
    return p

        #print('%13.4lf%8.4lf%8.4lf%2d%10.4lf%3d%7d%4d%12s%12s'
        #      %  (calc_freq, calc_unc, np.log10(intensity), 3, elow, gup, tag, qntag,
        #       qn_up.cat_str(), qn_low.cat_str()))
             

def formatqn(value):
    """
    Returns the string presentation of a single quantum number for Pickett's
    spcat files. Values greater than 99 will be turned into Ax, Bx, ...
    and values smaller than -9 into ax, bx, ...

    :param value: quantum number value
    :type value: int

    returns string
    """
    if value == None:
        return ''
    elif value > 99 and value < 360:
        return chr(55+value/10)+ "%01d" % ( value % 10)
    elif value < -9 and value > -260:
        return chr(95-(value-1)/10)+ "%01d" % -( value % -10)
    else:
        return str(value)

