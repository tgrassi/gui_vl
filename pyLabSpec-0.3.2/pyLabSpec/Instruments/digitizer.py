#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module provides a class for communicating with a Keysight PCIe
digitizer card.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import os
import sys
from ctypes import cdll
import ctypes

import numpy as np
from numpy.ctypeslib import ndpointer
from Spectrum import spectrum

if sys.version_info[0] == 3:
    from .instrument import Settings
else:
    from instrument import Settings

#digi_lib_path = '/home/cendres/Scripts/c/U5310A/tests/SimpleTest/SimpleAcquisition.so'

pychirp_path = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
digi_lib_path = os.path.join(pychirp_path, 'c/Digitizer/Digitizer.so')

if sys.version_info[0] == 3:
    xrange = range

try:
    lib = cdll.LoadLibrary(digi_lib_path)

    getData = lib.getData
    getDataAvg = lib.getDataAvg
    getDataMultiRecord = lib.getDataMultiRecord
    configureAcquisition = lib.configureAcquisition
    configureAvgAcquisition = lib.configureAvgAcquisition
    get_trigger_delay = lib.getTriggerDelay
    configure_external_trigger = lib.configureExternalTrigger
    configure_external_trigger.argtypes = [ctypes.c_int32, ctypes.c_double,
                                           ctypes.c_char_p]

    # Attribute handling
    getAttributeViInt32 = lib.getAttributeViInt32
    getAttributeViInt32.argtypes = [ctypes.c_int32, ctypes.c_int32]
    getAttributeViInt32.restype = ctypes.c_int32

    getAttributeViInt64 = lib.getAttributeViInt64
    getAttributeViInt64.argtypes = [ctypes.c_int32, ctypes.c_int32]
    getAttributeViInt64.restype = ctypes.c_int64

    getAttributeViReal64 = lib.getAttributeViReal64
    getAttributeViReal64.argtypes = [ctypes.c_int32, ctypes.c_int32]
    getAttributeViReal64.restype = ctypes.c_double

    getAttributeViString = lib.getAttributeViString
    getAttributeViString.argtypes = [ctypes.c_int32, ctypes.c_int32]
    getAttributeViString.restype = ctypes.c_char_p

    getAttributeViBoolean = lib.getAttributeViBoolean
    getAttributeViBoolean.argtypes = [ctypes.c_int32, ctypes.c_int32]
    getAttributeViBoolean.restype = ctypes.c_bool

    setAttributeViInt32 = lib.setAttributeViInt32
    setAttributeViInt32.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_int32]
    #setAttributeViInt32.restype = ctypes.c_int32

    setAttributeViInt64 = lib.setAttributeViInt64
    setAttributeViInt64.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_int64]
    #setAttributeViInt64.restype = ctypes.c_int64

    setAttributeViReal64 = lib.setAttributeViReal64
    setAttributeViReal64.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_double]
    #setAttributeViReal64.restype = ctypes.c_double

    setAttributeViString = lib.setAttributeViString
    setAttributeViString.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_char_p]
    #setAttributeViString.restype = ctypes.c_char_p

    setAttributeViBoolean = lib.setAttributeViBoolean
    setAttributeViBoolean.argtypes = [ctypes.c_int32, ctypes.c_int32, ctypes.c_bool]
    #setAttributeViBoolean.restype = ctypes.c_bool


    configureAcquisition.argtypes = [ctypes.c_int32, ctypes.c_char_p, 
                                     ctypes.c_int32, ctypes.c_int32, 
                                     ctypes.c_double, ctypes.c_double]
    configureAvgAcquisition.argtypes = [ctypes.c_int32, ctypes.c_char_p, 
                                     ctypes.c_int32, ctypes.c_int32, 
                                     ctypes.c_double, ctypes.c_double]


    getData.argtypes = [ctypes.c_int32, ctypes.c_char_p, ctypes.c_int32, ctypes.c_size_t, 
                        ndpointer(ctypes.c_double, flags = "C_CONTIGUOUS")]
    getDataAvg.argtypes = [ctypes.c_int32, ctypes.c_char_p, ctypes.c_int32, ctypes.c_size_t, 
                        ndpointer(ctypes.c_double, flags = "C_CONTIGUOUS")]
    getDataMultiRecord.argtypes = [ctypes.c_int32, ctypes.c_char_p, ctypes.c_int64, ctypes.c_int64, ctypes.c_size_t, 
                        ndpointer(ctypes.c_double, flags = "C_CONTIGUOUS")]

    get_trigger_delay.restype = ctypes.c_double

except:
    print("Could not load digitizer - lib")


# ViReal64 Attributes
AGMD2_ATTR_TRIGGER_DELAY = 1250017
GMD2_ATTR_BOARD_TEMPERATURE = 1250100

class Digitizer(object):
    """
    This is a class to communicate and control a Digitizer pcie card.
    """

    session = 0
    settings = Settings()

    #---------------------------------------------------------
    # Session
    #---------------------------------------------------------
    def __init__(self):
        """
        Initialize the digitizer
        """
        try:
            self.session = lib.open_session()
            self.connected = False
        except:
            self.session = 0
            self.connected = False

        print("Initialize")
        self.set_acquisition_mode()
        self.set_samplerate()
        self.set_recordlength()
        self.set_vertical_range()
        self.set_trigger_source('ext')
        self.set_acquisition_mode()
        self.set_num_acquisitions()
        self.calibrate()
        self.get_reference_source()
 
    def info(self):
        """
        Print out info about the digitizer.
        """
        lib.info(self.session)

    def close(self):
        """
        Closes the session with the digitizer.
        """
        lib.close_session(self.session)

    def apply_settings(self, **kwds):

        for ck in kwds.keys():
            if ck == 'settings':
                self.settings.apply_settings(kwds[ck])
            else:
                self.settings.set(ck, kwds[ck])

        if hasattr(self.settings, 'samplerate'):
            self.set_samplerate(self.settings.samplerate)
        if hasattr(self.settings, 'acquisition_mode'):
            self.set_acquisition_mode(
                mode = self.settings.get('acquisition_mode'))
        if hasattr(self.settings, 'num_acquisitions'):
            self.set_num_acquisitions(
                self.settings.get('num_acquisitions')
            )
        if hasattr(self.settings, 'record_length_time'):
            self.set_recordlength(
                self.settings.get('record_length_time')
            )
        if hasattr(self.settings, 'vertical_range'):
            self.set_vertical_range(
                self.settings.get('vertical_range')
            )
        if hasattr(self.settings, 'trigger_source'):
            trigger_source = self.settings.get('trigger_source')
        else:
            trigger_source = 'int'
        if hasattr(self.settings, 'trigger_level'):
            level = self.settings.get('trigger_level')
        else:
            level = 0.5
        if hasattr(self.settings, 'trigger_slope'):
            slope = self.settings.get('trigger_slope')
        else:
            slope = 'negative'
        self.set_trigger_source(trigger_source, level, slope)
        if hasattr(self.settings, 'error_on_overflow'):
            self.set_error_on_overflow(
                self.settings.get('error_on_overflow')
            )
        if hasattr(self.settings, 'reference_source'):
            self.set_reference_source(
                self.settings.get('reference_source')
            )


    def print_settings(self):
        """
        print the settings.
        """
        for ck in sorted(self.settings.__dict__.keys() ):
            print("%s: %s" % (ck, vars(self.settings)[ck]))

    #---------------------------------------------------------
    # Configure settings
    #---------------------------------------------------------
    def set_acquisition_mode(self, mode = 'single'):
        """
        Sets the aquisition mode (single, segmented, avg)

        :param mode: Mode to be set
        :type mode: str
        """
        if not mode in ['single', 'segmented', 'avg']:
            print("Acquistion mode has to be one of 'single', 'segmented', \
                  'avg'")
            return
        self.settings.set('acquisition_mode', mode)
        print("Acquistion mode: %s" % self.settings.get('acquisition_mode'))

    def set_num_acquisitions(self, num_acquisitions = 1):
        """
        Sets the number of acquisitions.
        """
        self.settings.set('num_acquisitions', num_acquisitions)
        print("Num Acquisitions: %d" % self.settings.get('num_acquisitions'))

    def get_num_acquisitions(self):
        """
        Gets the number of records to acquire.

        :returns: Number of records
        :rtype: int
        """
        num_records = getAttributeViInt64(self.session, 1250013)
        self.settings.set('num_acquisitions', num_records)
        return num_records

    def get_num_averages(self):
        """
        Gets the number of records to acquire.

        :returns: Number of records
        :rtype: int
        """
        num_records = getAttributeViInt32(self.session, 1150069)
        self.settings.set('num_averages', num_records)
        return num_records

    def get_num_segments(self):
        """
        Returns the number of segments used in the digitizer.
        """
        return self.get_num_acquisitions()

    def set_samplerate(self, samplerate = 5.0e9):
        """
        Sets the samplerate.
        """
        self.settings.set('samplerate', samplerate)
        print("Samplerate: %g" % self.settings.get('samplerate'))

    def set_recordlength(self, recordlength = 1.0e-5):
        """
        Sets the recordlength.

        :param recordlength: Length in seconds
        :type recodlength: float
        """
        self.settings.set('record_length_time', recordlength)
        print("Record-length: %g s" % self.settings.get('record_length_time'))
        num_samples = int(np.round(recordlength *
                                   self.settings.get('samplerate')))
        self.settings.set('record_size', num_samples)
        print("Record size %d Samples" %
              self.settings.get('record_size'))

    def set_vertical_range(self, vrange = 1.0):
        """
        Sets the vertical range (allowed values are only 1.0 and 0.25)
        """
        if vrange == 1.0 or vrange == 0.25:
            self.settings.set('vertical_range', vrange)
        else:
            print("Value not allowed. Allowed are 1.0 and 0.25")
            self.settings.set('vertical_range', 1.0)
        print("Vertical range: %lf V" % self.settings.get('vertical_range'))

    def set_trigger_source(self, source = 'ext', level = 0.5, slope = 'negative'):
        """
        Sets the trigger source port.

        :param source: Trigger source ('ext', 'int)
        :type source: str
        """
        source = source.lower()
        if source == 'int':
            lib.configureTrigger(self.session)
        elif source == 'ext':
            lib.configureExternalTrigger(self.session, level, slope)
        else:
            print("Trigger source unkown: %s" % source)
            return

        self.settings.set('trigger_source', source)
        self.settings.set('trigger_level', level)
        self.settings.set('trigger_slope', slope)
        print("Trigger source: %s" % self.settings.get('trigger_source'))
    #---------------------------------------------------------
    # Configure settings
    #---------------------------------------------------------
    def get_trigger_delay(self):
        """
        Reads the Trigger delay from Digitizer.
        """
        val = lib.getTriggerDelay(self.session)
        return val

    def set_error_on_overflow(self, enable):
        """
        Tells the instrument to throw an error on overflow if enabled.

        :param enable: Throw error if true otherwise not
        :type enable: Boolean
        """
        self.settings.set('error_on_overflow', enable)
        setAttributeViBoolean(self.session, 1150115, enable)
        return self.get_error_on_overflow()

    def get_error_on_overflow(self):
        """
        Queries if the instrument will throw an error on overflow or not

        :returns: enabled or not
        :rtype: boolean
        """
        enabled = getAttributeViBoolean(self.session, 1150115)
        self.settings.set('error_on_overflow', enabled)
        return enabled

    def get_reference_source(self):
        """
        """
        ref = getAttributeViInt32(self.session, 1250602)
        if ref == 1:
            source = 'EXT'
        elif ref == 0:
            source = 'INT'
        else:
            source = 'UNKOWN'

        self.settings.set('reference_source', source)
        return source

    def set_reference_source(self, source = 'INT'):
        """
        Sets the reference source (internal: 'INT' or external: 'EXT').
        """
        if source.upper == 'EXT':
            ref = 1
        else:
            ref = 0
        setAttributeViInt32(self.session, 1250602, ref)
#        setAttributeViBoolean(self.session, 1250602, ref)
        return self.get_reference_source()

    #---------------------------------------------------------
    # Acquisition
    #---------------------------------------------------------
    def get_calibration_required(self):
        """
        Checks if instrument calibration is required.
        
        :returns: required or not
        :rtype: boolean
        """
        required = getAttributeViBoolean(self.session, 1150067)
        return required

    def configure_acquisition(self, channel = 'Channel1', 
                              offset = 0.0 ):
        """
        Configure an acquisition in normal or segmented mode.

        :param channel: Channel to be configured (or list of channels)
        :type channel: str
        :param offset: Vertical offset (usually 0.0)
        :type offset: float
        """
        mode = self.settings.get('acquisition_mode')
        record_size = self.settings.get('record_size')
        vrange = self.settings.get('vertical_range')

        if mode == 'single':
            num_averages = 1
            num_records = 1
            if type(channel) == list:
                for ch in channel:
                    configureAcquisition(self.session, 
                                             ch, 
                                             num_records,
                                             record_size, 
                                             vrange, 
                                             offset)
            else:
                configureAcquisition(self.session, 
                                         channel, 
                                         num_records,
                                         record_size, 
                                         vrange, 
                                         offset)
        elif mode == 'segmented':
            num_averages = 1
            num_records = self.settings.get('num_acquisitions')
            if type(channel) == list:
                for ch in channel:
                    configureAcquisition(self.session, 
                                             ch, 
                                             num_records,
                                             record_size, 
                                             vrange, 
                                             offset)
            else:
                configureAcquisition(self.session, 
                                         channel, 
                                         num_records,
                                         record_size, 
                                         vrange, 
                                         offset)
        elif mode == 'avg':
            num_records = 1
            num_averages = self.settings.get('num_acquisitions')

            if type(channel) == list:
                for ch in channel:
                    configureAvgAcquisition(self.session, 
                                                channel, 
                                                num_averages,
                                                record_size, 
                                                vrange, 
                                                offset)
            else:
                configureAvgAcquisition(self.session, 
                                            channel, 
                                            num_averages,
                                            record_size, 
                                            vrange, 
                                            offset)

    def acquire_data(self):
        """
        Starts the acquisition and returns after the acquisition is completed.
        """
        lib.acquireData(self.session)

    def initiateAcquisition(self):
        """
        Initiate the acquisition, but do not wait until its finished.
        """
        lib.initiateAcquisition(self.session)

    def abortAcquisition(self):
        """
        Aborts the current acquisition.
        """
        lib.abortAcquisition(self.session)

    def waitForAcquisitionComplete(self, timeout = 5000):
        """
        Waits until the acquisition is finished.

        :param timeout: Timeout in ms
        :type timeout: int
        """
        lib.waitForAcquisitionComplete(self.session, timeout)

    #---------------------------------------------------------
    # Calibration
    #---------------------------------------------------------
    def calibrate(self):
        """
        Initiates a self-calibration of the digitizer.
        """
        lib.calibrate(self.session)

    #---------------------------------------------------------
    # Trigger
    #---------------------------------------------------------
    def configure_trigger(self, source = 'Int'):
        """
        Configures the trigger.

        :param source: Trigger source ('ext', 'int)
        :type source: str
        """
        if source.lower() == 'int':
            lib.configureTrigger(self.session)
        elif source.lower() == 'ext':
            lib.configureExternalTrigger(self.session)
        else:
            print("Trigger source unkown: %s" % source)

    #---------------------------------------------------------
    # Acquisition
    #---------------------------------------------------------
    def get_curve(self, channel = 'Channel1'):
        """
        Retrieves the data recorded in last acquisition.
        """
        mode = self.settings.get('acquisition_mode')
        if mode == 'single':
            return self.get_curve_single(channel = channel)
        elif mode == 'segmented':
            return self.get_curve_multi_record(channel = channel)
        elif mode == 'avg':
            return self.get_curve_avg(channel = channel)
        else:
            return None

    def get_curve_single(self, channel = 'Channel1'):
        """
        Retrieves the data recorded for a single acquisition.
        """
        size = self.settings.get('record_size')
        outdata = np.empty(size)
        status = getData(self.session, channel, size, outdata.size, outdata)
        
        return outdata

    def get_curve_multi_record(self, channel = 'Channel1'):
        """
        Retrieves the data recorded for multi acquisition (segmented).
        """
        num_records = self.settings.get('num_acquisitions')
        record_size = self.settings.get('record_size')
        size = num_records * record_size
        outdata = np.zeros([num_records, record_size])

        status = getDataMultiRecord(self.session, channel, num_records,
                                    record_size, outdata.size, outdata)
        
        return outdata

    def get_curve_avg(self, channel = 'Channel1'):
        """
        Retrieves the data recorded in avg-mode.
        """
        num_records = 1 #self.settings.get('num_acquisitions')
        record_size = self.settings.get('record_size')
        size = num_records * record_size
        outdata = np.empty(size)
        status = getDataAvg(self.session, channel, record_size, outdata.size, outdata)
        
        return outdata

    def get_curve_average_segments(self, channel = 'Channel1', num_segments = 1):
        """
        Retrieves the data recorded for multi acquisition (segmented) and
        averages the segements according to the number of segments specified.
        """
        num_records = self.settings.get('num_acquisitions')
        if num_records % num_segments != 0:
            print("Number of Records has to be multiple of number of segments.")
            return

        record_size = self.settings.get('record_size')
        size = num_records * record_size
        outdata = np.zeros([num_records, record_size])
        segdata = np.zeros([num_segments, record_size])

        status = getDataMultiRecord(self.session, channel, num_records,
                                    record_size, outdata.size, outdata)
        
        for i in xrange(num_records):
            seg = i % num_segments
            segdata[seg] += outdata[i]

        return segdata

    def acquire_avg(self, filename = None, signal_channel = 1):

        xorigin = 0
        xfac = 1.0 / self.settings.get('samplerate')

        data = self.get_curve(channel = 'Channel%d' % signal_channel)

        record_length = len(data)
        x = [xorigin + (i) * xfac for i in xrange(record_length)]

        spec = spectrum.FID(x, data)

        if filename is not None:
            spec.save('%s.npy' % filename,
                      ftype = 'npy')

        return spec


    def acquire_segments_multipulse(self,
                                    filename,
                                    num_segments,
                                    num_pulses,
                                    start = None,
                                    size = None,
                                    signal_channel = 1,
                                    probe_channel = 4,
                                    probe_point = 1500):
        """
        Transfers all the segments from scope to computer
        """
        if np.mod(num_segments, num_pulses) != 0:
            print("Number of segments as to be multiple of num_pulses!")
            return

        probe_spec = {}
        # Make sure all segments will be transfered
#        self.scope.write('WAV:SEGM:ALL 1')

        # Transfer all segments for signal-channel
#        self.scope.set_data_source('CHAN%d' % signal_channel)

#        xorigin, xfac = self.scope.get_time_conversion_factors()
#        yorigin, yfac = self.scope.get_voltage_conversion_factors()

        xorigin = 0
        xfac = 1.0 / self.settings.get('samplerate')

        if start is None:
            start = 0

        if size:
          if not start:
            start = 0
#          data = self.scope.get_curve(start = start, size = size)
          data = self.get_curve(channel = 'Channel%d' % signal_channel)
        elif start:
#          data = self.scope.get_curve(start = start)
          data = self.get_curve(channel = 'Channel%d' % signal_channel)
        else:
          # data = self.scope.get_curve()
          data = self.get_curve(channel = 'Channel%d' % signal_channel)

        record_length = len(data[0])
        x = [xorigin + (start + i) * xfac for i in xrange(record_length)]

        # Create separate spectra for iterating pulses
        for i in xrange(num_pulses):
            probe_spec[i] = spectrum.FID(x, np.zeros(record_length))
            for j in xrange(num_segments / num_pulses):
                probe_spec[i].y += data[num_pulses * j + i]

        # save the spectra if a filename is given
        if filename is not None:
            for i in probe_spec.keys():
                probe_spec[i].save('%s_probe%d' % (filename, i), ftype =
                                   'npy')
        return probe_spec
