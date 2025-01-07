#!/usr/bin/env python
# -*- coding: utf8 -*-
#
"""
This module provides classes and methods to control lock-in amplifier
devices.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
import time
# third-party libraries
import numpy as np
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from settings import *
from . import instrument as instr

class sr830(instr.InstSocket):
	"""
	Provides a general socket for the SRS SR830 Lock-In Amplifier
	
	Note that this probably could work directly with the SR810, too..
	"""
	
	time_constant_list = [
		10.0e-6, 30.0e-6, 100.0e-6, 300.0e-6,
		1.0e-3, 3.0e-3, 10.0e-3, 30.0e-3, 100.0e-3, 300.0e-3,
		1.0, 3.0, 10.0, 30.0, 100.0, 300.0,
		1.0e3, 3.0e3, 10.0e3, 30.0e3
	]
	sensitivity_list = [
		2.0e-9, 5.0e-9, 10.0e-9, 20.0e-9, 50.0e-9, 100.0e-9, 200.0e-9, 500.0e-9,
		1.0e-6, 2.0e-6, 5.0e-6, 10.0e-6, 20.0e-6, 50.0e-6, 100.0e-6, 200.0e-6, 500.0e-6,
		1.0e-3, 2.0e-3, 5.0e-3, 10.0e-3, 20.0e-3, 50.0e-3, 100.0e-3, 200.0e-3, 500.0e-3,
		1.0
	]
	param_list = ['', 'x', 'y', 'r', 't']
	
	def __init__(self, host='lia', com='GPIB'):
		instr.InstSocket.__init__(self, host=host, com=com)
		
		# initialize settings
		self.write('OUTX 1')
		
		# initialize statuses
		self.isconnected = True
		self.time_constant = self.get_time_constant()
		self.sensitivity = self.get_sensitivity()
		self.harm = self.get_harm()
		self.phase = self.get_phase()
		self.freq = self.get_freq()
	
	
	def set_phase(self, phase):
		"""
		Set the reference phase.
		
		Note that while the phase should only range between -180 to 180, the
		instrument can wrap within -360 to +729.99 degrees, and this routine
		ensures the desired value stays within this range.
		
		:param phase: reference phase in [degrees]
		:type phase: float
		"""
		if phase < -360:
			phase = phase % -360
		elif phase > 720:
			phase = phase % 720
		self.write('PHAS %2f' % phase)
		self.get_phase()
	def auto_phase(self):
		"""
		Runs the Auto-Phase function.
		"""
		self.write('APHS')
	def get_phase(self):
		"""
		Get the reference phase.
		
		:returns: the reference phase in [degrees]
		:rtype: float
		"""
		self.phase = float(self.query('PHAS?'))
		return self.phase
	
	
	def set_harm(self, harm):
		"""
		Set the detection harmonic.
		
		:param harm: detection harmonic
		:type harm: int
		"""
		if not isinstance(harm, (int)):
			raise InputError("The detection harmonic must be an integer, but you requested: %s" % modtype)
		self.write('HARM %d' % harm)
		self.get_harm()
	def get_harm(self):
		"""
		Get the detection harmonic.
		
		:returns: the detection harmonic
		:rtype: int
		"""
		self.harm = int(self.query('HARM?'))
		return self.harm
	
	
	def set_freq(self, freq):
		"""
		Set the internal reference frequency.
		
		Note that the maximum allowed reference frequency is (102/n kHz), where
		'n' is the harmonic number.
		
		:param freq: reference frequency in [Hz]
		:type freq: float
		"""
		harm = self.get_harm()
		if (float(freq/harm) > 102000):
			raise InputError("You attempted to set an excessive ref freq!")
		self.write('FREQ %lf' % freq)
		self.get_freq()
	def get_freq(self):
		"""
		Get the internal reference frequency.
		
		:returns: the reference frequency
		:rtype: float
		"""
		self.freq = float(self.query('FREQ?'))
		return self.freq
	
	
	def read_data(self, delay_time=None, param='x'):
		"""
		Get the magnitude.
		
		It is possible to specify a delay time. The method will then
		wait for the specified time, before the value is read
		
		:param delay_time: (optional) delay time in [ms]
		:param param: (optional) the type of value to be read (X, Y, R, Phase)
		:type delay_time: float
		:type param: string
		"""
		if delay_time:
			time.sleep(delay_time * 0.001)
		return float(self.query('OUTP? %d' % self.param_list.index(param[0].lower()) ))
	
	
	def set_time_constant(self, int_time):
		"""
		Sets the time constant of the lock-in amplifier.
		
		:param int_time: time constant in [s]
		:type int_time: float
		"""
		# get the time constant closest to an available value
		index = np.abs([i - int_time for i in self.time_constant_list]).argmin()
		self.write('OFLT %d' % index)
		self.get_time_constant()
	def get_time_constant(self):
		"""
		Reads the time constant from the lock-in amplifier.
		
		:returns: the time constant
		:rtype: float
		"""
		time_constant = self.query('OFLT?')
		self.time_constant = self.time_constant_list[int(time_constant)]
		return self.time_constant
	
	
	def set_sensitivity(self, sensitivity):
		"""
		Sets the sensitivity of the lock-in amplifier
		
		:param sensitivity: sensitivity in [V]
		:type sensitivity: float
		"""
		# get the sensitivity closest to an available value
		index = np.abs([i - sensitivity for i in self.sensitivity_list]).argmin()
		self.write('SENS %d' % index)
		self.get_sensitivity()
	def get_sensitivity(self):
		"""
		Reads the sensitivity from the lock-in amplifier.
		
		:returns: the sensitivity
		:rtype: float
		"""
		sensitivity = self.query('SENS?')
		self.sensitivity = self.sensitivity_list[int(sensitivity)]
		return self.sensitivity
	
	def set_storage_trigger_rate(self, rate="trigger"):
		"""
		Sets the method/rate for storing to internal memory
		
		Note that only 'trigger' is allowed for now
		
		:param rate: the rate to use, or simply an external trigger
		:type rate: str
		"""
		if not rate.lower() == "trigger":
			raise SyntaxError("only 'trigger' is supported for now.. buy Jake a beer")
		self.write('SRAT 14')
	
	def get_storage_trigger_mode(self):
		"""
		Returns the state of internal storage
		
		:returns: returns the state as on or off
		:rtype: str
		"""
		mode = self.query('TSTR?')
		trigger_mode = {'0':"off", '1':"on"}
		return trigger_mode[mode]
	def set_storage_trigger_mode(self, mode):
		"""
		Sets the state of using internal storage
		
		:param mode: the state as on or off
		:type mode: str
		"""
		if not mode.lower() in ["on", "off"]:
			raise SyntaxError("only ON|OFF modes are supported")
		trigger_mode = {
			"off":0,
			"on":1}
		mode = trigger_mode[mode.lower()]
		self.write('TSTR %s' % mode)
	
	def send_storage_trigger(self):
		"""
		Sends a trigger to store the current value to internal memory
		"""
		self.write('TRIG')
	
	def reset_storage_buffer(self):
		"""
		Resets the internal storage buffer, essentially clearing the data
		"""
		self.write('REST')
	
	def get_storage_buffer_length(self):
		"""
		Returns the size of the current internal storage
		
		Note that this value changes immediately! Therefore it is probably
		a good idea to turn off the storage before reading this number..
		
		:returns: the number of data points currently stored
		:rtype: int
		"""
		return int(self.query('SPTS?'))
	
	def get_storage_buffer_a(self, channel=1, start=0, end=1):
		"""
		Returns the data stored in the internal memory, using the TRCA
		query. See 5-16 of the programming manual for details..
		
		:param channel: (optional) which channel to retrieve (default: 1)
		:param start: (optional) the first data point to begin at (default: 0)
		:param end: (optional) the last data point to finish with (default: the last one)
		:type channel: int
		:type start: int
		:type end: int
		
		:returns: the stored data from the internal memory
		:rtype: str
		"""
		if not end:
			end = self.get_storage_buffer_length()
		cmd = 'TRCA?%s,%s,%s'%(channel, start, end)
		length = end - start
		num = length * 16
		return self.query(cmd, num=num)
	def get_storage_buffer_b(self, channel=1, length=1):
		"""
		Returns the data stored in the internal memory, using the TRCB
		query. See 5-16 of the programming manual for details..
		
		:param channel: (optional) which channel to retrieve (default: 1)
		:param start: (optional) the first data point to begin at (default: 0)
		:param end: (optional) the last data point to finish with (default: the last one)
		:type channel: int
		:type start: int
		:type end: int
		
		:returns: the stored data from the internal memory
		:rtype: str
		"""
		if not length:
			length = self.get_storage_buffer_length()
		cmd = 'TRCB?%s,0,%s' % (channel, length)
		num = length * 4
		return self.query(cmd, num=num)
	def get_storage_buffer_l(self, channel=1, length=1):
		"""
		Returns the data stored in the internal memory, using the TRCL
		query. See 5-17 of the programming manual for details..
		
		Note that this is not necessarily faster than TRCB, and prior
		tests have shown that this query is prone to communication
		errors. It is therefore recommended to use the TRCB-based
		routine instead.
		
		:param channel: (optional) which channel to retrieve (default: 1)
		:param start: (optional) the first data point to begin at (default: 0)
		:param end: (optional) the last data point to finish with (default: the last one)
		:type channel: int
		:type start: int
		:type end: int
		
		:returns: the stored data from the internal memory
		:rtype: str
		"""
		if not length:
			length = self.get_storage_buffer_length()
		cmd = 'TRCL?%s,0,%s' % (channel, length)
		num = length * 4
		return self.query(cmd, num=num)
	


class mfli(instr.InstSocket):
	"""
	Provides a general socket for the SRS SR830 Lock-In Amplifier
	
	Note that this probably could work directly with the SR810, too..
	"""
	
	time_constant_list = [
		10.0e-6, 15e-6, 20e-6, 25e-6, 30.0e-6, 100.0e-6, 300.0e-6,
		1.0e-3, 3.0e-3, 10.0e-3, 30.0e-3, 100.0e-3, 300.0e-3,
		1.0, 3.0, 10.0, 30.0, 100.0, 300.0,
		1.0e3, 3.0e3, 10.0e3, 30.0e3
	]
	param_list = ['x', 'y', 'r', 'phase']
	log_levels = {
		"trace" : 0,
		"info" : 1,
		"debug" : 2,
		"warning" : 3,
		"error" : 4,
		"fatal" : 5,
		"status" : 6}
	signals = {
		"SigIn1" : 0,
		"CurIn1" : 1,
		"Trigger1" : 2,
		"Trigger2" : 3,
		"AuxOut1" : 4,
		"AuxOut2" : 5,
		"AuxOut3" : 6,
		"AuxOut4" : 7,
		"AuxIn1" : 8,
		"AuxIn2" : 9}
	triggers = {
		"cont" : 0,
		"cont_cont" : 0,
		"1_cont" : 0,
		"2_cont" : 0,
		"both_cont" : 0,
		"1_rise" : 1,
		"1_fall" : 2,
		"1_both" : 3,
		"1_high" : 32,
		"1_low" : 16,
		"2_rise" : 4,
		"2_fall" : 8,
		"2_both" : 12,
		"2_high" : 128,
		"2_low" : 64,
		"both_rise" : 5,
		"both_fall" : 10,
		"both_both" : 15,
		"both_high" : 160,
		"both_low" : 80}
	
	
	def __init__(self, host='dev3367', ip=None, port=None, interface="PCIe", log_level="fatal", useAPIsession=False, api=1):
		import zhinst
		import zhinst.utils
		from zhinst import ziPython
		if useAPIsession:
			try:
				(daq, device, props) = zhinst.utils.create_api_session(
					host, self.log_levels[log_level])
			except RuntimeError as e:
				print("\tERROR: there was a problem connecting to the device!")
				print("\tplease ensure the following:")
				print("\t\t- the has been turned on while unplugged")
				print("\t\t- the USB cable has been plugged into it while it was on")
				print("\t\t- a network connection has been properly established with the device")
				print("\ton the last point, identify the relevant network-interface by matching the MAC")
				print("\taddress from the most recent '>dmesg' entry containing 'RNDIS device, xx:xx:xx:xx:xx:xx'")
				print("\tagainst that which is listed under '>ifconfig -a', and then running something like:")
				print("\t'>sudo ifconfig ethX 192.168.52.157 broadcast 192.168.52.159 netmask 255.255.255.252'")
				print("\tif you run 'dmesg' in the terminal but do not see an entry about 'RNDIS device',")
				print("\ttry running '>sudo modprobe usbnet rndis_host rndis_wlan' and check again!")
				raise
		elif port:
			try:
				daq = ziPython.ziDAQServer(ip, port, api)
				d = ziPython.ziDiscovery()
				device = d.find("%s" % host).lower()
				props = d.get(host.upper())
				props['devicetype'] = "MF"
				props['serveraddress'] = ip
				daq.connectDevice(props['deviceid'], props['interfaces'][0])
				props['connected'] = True
			except RuntimeError as e:
				print("\tERROR: there was a problem connecting to the device!")
				print("\tthis occurred in the new IP:PORT style connection")
				print("\tthis occurred in the new IP:PORT style connection")
				raise
		
		# define device sockets & statuses
		self.version = zhinst.ziPython.__version__
		self.daq = daq
		self.device = device
		self.props = props
		self.tau = [0,0,0,0]
		self.harm = [0,0,0,0]
		self.phase = [0,0,0,0]
		self.freq = [0,0,0,0]
		self.demodInputs = ["", "", "", ""]
		
		# initialize statuses
		self.isconnected = True
		self.trigger = None
		self.identify()
		self.get_statuses()
	
	
	def identify(self):
		"""
		Updates and returns the identifier string of the device. This
		looks like: MODEL-ID (connected:TRUE/FALSE, server:IP)
		"""
		self.identifier = "%s-%s (connected:%s, server:%s)" % (
			self.props["devicetype"], self.props["deviceid"],
			self.props["connected"], self.props["serveraddress"])
		return self.identifier
	
	def get_statuses(self):
		"""
		Runs through various statuses of the demodulators and updates
		their flags/parameters. These statuses can then be checked
		via print_statuses().
		"""
		self.get_sensitivity()
		for i in range(1,5):
			self.get_time_constant(demod=i)
			self.get_harm(demod=i)
			self.get_phase(demod=i)
			self.get_freq(osc=i)
			self.getDemodInput(demod=i)
	
	def print_statuses(self):
		"""
		Prints to the terminal the various statuses of the demodulators.
		They are not kept up-to-date, but rather should be first updated
		via the get_statuses() method.
		"""
		print("sensitivity is %s" % self.sensitivity)
		print("time_constants are %s" % self.tau)
		print("harmonics are %s" % self.harm)
		print("phases are %s" % self.phase)
		print("frequencies are %s" % self.freq)
		print("demod inputs are %s" % self.demodInputs)
	
	def sync(self, useDelay=False, delay=1):
		"""
		Forces the synchronization of the settings between the data/comm
		server and the device itself.
		"""
		self.daq.sync() # sync the settings from the data server
		if useDelay:
			import time
			time.sleep(delay)
	
	def reset(self):
		"""
		Reloads the factory default settings by referencing the read-only
		preset 0.
		"""
		self.loadPreset(0)
	
	def loadPreset(self, preset):
		"""
		Forces the device to reload a specific configuration preset. 0 is
		the default factory preset, and 1-6 are user-configurable. They
		may also be renamed using the HTML interface.
		"""
		if not preset in range(0, 7):
			raise SyntaxError("this device only supports presets 0-6: %g" % preset)
		self.daq.setInt('/%s/system/preset/index' % self.device, preset)
		self.daq.setInt('/%s/system/preset/load' % self.device, 1)
		self.sync(useDelay=True)
	
	def getClockbase(self):
		"""
		Returns the timebase of the internal clock, which is used
		for referencing all other time-related parameters.
		
		:returns: the internal clock's timebase
		:rtype: float
		"""
		return float(self.daq.getInt('/%s/clockbase' % self.device))
	
	def setDemodEnabled(self, state=None, demod=1):
		"""
		Enables/disables a demodulator. Note that the demodulators are
		numbered internally 0-3, but this python module shifts them
		to be 1-4.
		
		:param state: the desired on/off (or 0/1) state
		:type state: str or int
		:param demod: which demodulator to act upon (1-4)
		:type demod: int
		"""
		if not state in ["on", "off", 0, 1]:
			raise SyntaxError("demod states must be 'on' or 'off': %s" % state)
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		if state == "on":
			state = 1
		elif state == "off":
			state = 0
		self.daq.setInt('/%s/demods/%g/enable' % (self.device, demod), state)
	
	def setDemodInput(self, demod=1, signal=""):
		"""
		Switches the input for a demodulator to an alternative signal.
		
		Note that the available signals are something like:
		[Sig,Cur]In1, Trigger[1,2], AuxOut[1-4], AuxIn[1-2]
		
		See setDemodEnabled() about a note about the expected numbering scheme.
		
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		:param signal: the new input signal to use
		:type signal: str
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		if signal not in self.signals:
			raise SyntaxError("signal must be [Sig,Cur]In1, Trigger[1,2], AuxOut[1-4], AuxIn[1-2]: %s" % signal)
		self.daq.setInt('/%s/demods/%g/adcselect' % (self.device, demod), self.signals[signal])
	def getDemodInput(self, demod=1):
		"""
		Returns the active input for a demodulator.
		
		See setDemodEnabled() about a note about the expected numbering scheme.
		
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		:returns: the active input
		:rtype: str
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		self.demodInputs[demod] = self.daq.getInt('/%s/demods/%g/adcselect' % (self.device, demod))
		for k,v in self.signals.items():
			if self.demodInputs[demod] == v:
				self.demodInputs[demod] = k
		return self.demodInputs[demod]
	
	def set_datarate(self, rate, demod=1):
		"""
		Switches the data rate for a specific demodulator. The rate
		should be specified in terms of samples per second.
		
		Note that the total data rate should not exceed something like
		500,000 Sa/s, and this limit may be reduced if/when the HTML
		interface is also active or additional modules are being
		used to process data. The MFLI is no supercomputer.
		
		:param rate: the new rate
		:type rate: float
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		self.daq.setDouble('/%s/demods/%g/rate' % (self.device, demod), rate)
	
	def set_input_range(self, voltage=None, current=None):
		"""
		Switches the input ranges for the current & voltage input.
		
		:param voltage: (optional) the new voltage upper range
		:type voltage: float
		:param current: (optional) the new current upper range
		:type current: float
		"""
		allowedV = [3e-3, 10e-3, 30e-3, 100e-3, 300e-3, 1.0, 3.0]
		allowedI = [10e-9, 1e-6, 100e-6, 10e-3]
		if voltage is not None:
			if voltage > allowedV[-1]:
				msg = "input voltage may not exceed %.1e V" % allowedV[-1]
				msg += " (you requested %.1e V)" % voltage
				raise SyntaxError(msg)
			else:
				self.daq.setDouble('/%s/sigins/0/range' % (self.device), voltage)
		if current is not None:
			if current > allowedI[-1]:
				msg = "input current may not exceed %.1e A" % allowedI[-1]
				msg += " (you requested %.1e A)" % current
				raise SyntaxError(msg)
			else:
				self.daq.setDouble('/%s/currins/0/range' % (self.device), current)
	def set_input_impedance(self, impedance=None):
		"""
		Switches the input impedance to 50 Ω or 10 MΩ.
		
		:param impedance: (optional) the new impedance (50 or 10M)
		:type impedance: int or float
		"""
		allowedZ = [50, 10e6]
		if not impedance in allowedZ:
			msg = "input impedance only be 50 Ω or 10 MΩ"
			msg += ", and you requested %g" % impedance
			raise SyntaxError(msg)
		elif impedance == 50:
			self.daq.setInt('/%s/sigins/0/imp50' % (self.device), 1)
		else:
			self.daq.setInt('/%s/sigins/0/imp50' % (self.device), 0)
	
	def set_filter_slope(self, db, demod=1):
		"""
		Sets the filter slope for a specific demodulator. The slope
		should be specified in terms of dB per octave, which is then
		converted to an integer.
		
		:param db: the new slope
		:type db: float
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		order = int(round(db/6.0))
		self.daq.setInt('/%s/demods/%g/order' % (self.device, demod), order)
	
	
	def set_phase(self, phase, demod=1):
		"""
		Set the reference phase.
		
		Note that while the phase should only range between -180 to 180, the
		instrument can wrap within -360 to +729.99 degrees, and this routine
		ensures the desired value stays within this range.
		
		:param phase: reference phase in [degrees]
		:type phase: float
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		if phase < -360:
			phase = phase % -360
		elif phase > 720:
			phase = phase % 720
		self.daq.setDouble('/%s/demods/%g/phaseshift' % (self.device, demod), phase)
	def auto_phase(self, demod=1):
		"""
		Runs the Auto-Phase function.
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		self.daq.setDouble('/%s/demods/%g/phaseadjust' % (self.device, demod), 1)
	def get_phase(self, demod=1):
		"""
		Get the reference phase.
		
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		:returns: the reference phase in [degrees]
		:rtype: float
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		self.phase[demod] = self.daq.getDouble('/%s/demods/%g/phaseshift' % (self.device, demod))
		return self.phase[demod]
	
	
	def set_harm(self, harm, demod=1):
		"""
		Set the detection harmonic.
		
		:param harm: detection harmonic
		:type harm: int
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		"""
		if not isinstance(harm, (int)):
			raise InputError("The detection harmonic must be an integer, but you requested: %s" % modtype)
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		self.daq.setDouble('/%s/demods/%g/harmonic' % (self.device, demod), harm)
	def get_harm(self, demod=1):
		"""
		Get the detection harmonic.
		
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		:returns: the detection harmonic
		:rtype: int
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		self.harm[demod] = int(self.daq.getDouble('/%s/demods/%g/harmonic' % (self.device, demod)))
		return self.harm[demod]
	
	
	def set_freq(self, freq, osc=1):
		"""
		Set the internal reference frequency.
		
		Note that the maximum allowed reference frequency is (500/n kHz), where
		'n' is the harmonic number.
		
		:param freq: reference frequency in [Hz]
		:type freq: float
		:param osc: the oscillator to act upon (1-4)
		:type osc: int
		"""
		harm = self.get_harm()
		if (freq/float(harm) > 500000):
			raise InputError("You attempted to set an excessive ref freq!")
		if not osc in range(1,5):
			raise SyntaxError("osc must be 1-4: %g" % osc)
		osc -= 1
		self.daq.setDouble('/%s/oscs/%g/freq' % (self.device, osc), freq)
	def get_freq(self, osc=1):
		"""
		Get the internal reference frequency.
		
		:param osc: the oscillator to act upon (1-4)
		:type osc: int
		:returns: the reference frequency
		:rtype: float
		"""
		if not osc in range(1,5):
			raise SyntaxError("osc must be 1-4: %g" % osc)
		osc -= 1
		self.freq[osc] = self.daq.getDouble('/%s/oscs/%g/freq' % (self.device, osc))
		return self.freq[osc]
	
	
	def read_data(self, delay_time=None, param='x', demod=1):
		"""
		Get the magnitude.
		
		It is possible to specify a delay time. The method will then
		wait for the specified time, before the value is read
		
		:param delay_time: (optional) delay time in [ms]
		:param param: (optional) the type of value to be read (X, Y, R, Phase)
		:type delay_time: float
		:type param: string
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		"""
		if delay_time:
			time.sleep(delay_time * 0.001)
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		sample = self.daq.getSample('/%s/demods/%s/sample' % (self.device, demod))
		if param.lower() not in self.param_list:
			raise SyntaxError("you requested param '%s', which is not in %s!" % (param, self.param_list))
		if param.lower() == 'x':
			return float(sample['x'])
		elif param.lower() == 'y':
			return float(sample['y'])
		elif param.lower() == 'r':
			return float(np.abs(sample['x'] + 1j*sample['y']))
		elif param.lower() == 'phase':
			return float(np.angle(sample['x'] + 1j*sample['y']))
	
	
	def set_time_constant(self, int_time, demod=1):
		"""
		Sets the time constant of the lock-in amplifier.
		
		:param int_time: time constant in [s]
		:type int_time: float
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		self.daq.setDouble('/%s/demods/%g/timeconstant' % (self.device, demod), int_time)
	def get_time_constant(self, demod=1):
		"""
		Reads the time constant from the lock-in amplifier.
		
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		:returns: the time constant
		:rtype: float
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		self.tau[demod] = self.daq.getDouble('/%s/demods/%g/timeconstant' % (self.device, demod))
		return self.tau[demod]
	
	
	def set_trigger(self, source=None, mode=None, demod=1):
		"""
		Sets the trigger of the lock-in amplifier.
		
		:param source: source of trigger ('cont', '1', '2', 'both')
		:type source: str
		:param mode: mode for the trigger ('cont', 'rise', 'fall', 'both', 'high', 'low')
		:type mode: str
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		trigger_key = "%s_%s" % (source, mode)
		if not trigger_key in self.triggers.keys():
			raise SyntaxError("you requested a strange trigger setting: %s. options are: %s" % (trigger_key, list(self.triggers.keys())))
		trigger_int = self.triggers[trigger_key]
		self.daq.setInt('/%s/demods/%g/trigger' % (self.device, demod), trigger_int)
	def get_trigger(self, demod=1):
		"""
		Reads the time constant from the lock-in amplifier.
		
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		:returns: the time constant
		:rtype: float
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		trigger_int = self.daq.getInt('/%s/demods/%g/trigger' % (self.device, demod))
		trigger_key = "cont_cont"
		for k in reversed(self.triggers.keys()):
			if trigger_int == self.triggers[k]:
				trigger_key = k
				break
		return trigger_key.split("_")
	
	
	def set_sine_filter(self, state=None, demod=1):
		"""
		Sets the state for the sine filter of the lock-in amplifier.
		
		:param state: state of filter ('on', 'off')
		:type source: str
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		states = {
			"on" : 1,
			"off" : 0}
		if not state.lower() in states.keys():
			raise SyntaxError("you requested a strange state: %s. options are 'on' or 'off'" % trigger_key)
		state_int = states[state.lower()]
		self.daq.setInt('/%s/demods/%g/sinc' % (self.device, demod), state_int)
	def get_sine_filter(self, demod=1):
		"""
		Reads the state for the sine filter of the lock-in amplifier.
		
		:param demod: the demodulator to act upon (1-4)
		:type demod: int
		:returns: the sinc filter state
		:rtype: str
		"""
		if not demod in range(1,5):
			raise SyntaxError("demod must be 1-4: %g" % demod)
		demod -= 1
		states = ['off', 'on']
		state_int = self.daq.getInt('/%s/demods/%g/sinc' % (self.device, demod))
		state = states[state_int]
		return state
	
	
	def set_sensitivity(self, sensitivity):
		"""
		Sets the sensitivity of the lock-in amplifier
		
		:param sensitivity: sensitivity in [V]
		:type sensitivity: float
		"""
		self.daq.setDouble('/%s/sigins/0/range' % self.device, sensitivity)
	def get_sensitivity(self):
		"""
		Reads the sensitivity from the lock-in amplifier.
		
		:returns: the sensitivity
		:rtype: float
		"""
		self.sensitivity = self.daq.getDouble('/%s/sigins/0/range' % self.device)
		return self.sensitivity
	