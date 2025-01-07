#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module provides an enhanced API for remote access to the Red Pitaya.

The short-term goal is to implement all the current functionality of the
SCPI interface.

A list of supported SCPI commands can be found at the following pages:
https://redpitaya.readthedocs.io/en/latest/appsFeatures/remoteControl/remoteControl.html
https://redpitaya.readthedocs.io/en/latest/developerGuide/scpi/scpi.html

The medium-/long-term goal is to add FPGA functionality and perhaps other
unforeseeables.

FPGA links:
https://red-pitaya-fpga-examples.readthedocs.io/en/latest/index.html

Copyright 2020, Jacob C. Laas
"""

# standard library
import sys
import os
# third-party
# local
if not os.path.dirname(os.path.dirname(os.path.abspath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import redpitaya_scpi as rpscpi

if sys.version_info[0] == 3:
	from importlib import reload
	unicode = str
	xrange = range


class RedPitaya(object):
	"""
	Provides a nicer API to the scpi socket.
	
	Note that this relies solely on its native SCPI python wrapper,
	which itself is simply a front-end for the C-based API. It's a bit
	slow if you want real-time/continuous data acquisition using the
	high-speed inputs. If speed (and still python) is your preference,
	look into PyRPL..
	
	A note about versions: the beta firmware is known to cause some
	strange issues. Use version 0.98-617 if you run into issues.
	
	Another note about versions: if you are also using PyRPL at all
	with the same device, use their version 0.9.3.6 from 2017-Aug-29,
	otherwise PyRPL will lock you out of a functioning SCPI server
	until you reboot the device!
	"""
	
	waveforms = ["sine", "square", "triangle", "sawu", "sawd", "pwm", "arb"]
	
	decimations = (1,8,64,1024,8192,65536)
	
	def __init__(self, host, timeout=None, port=5000, debugging=False):
		"""Initialize object and open IP connection.
		Host IP should be a string in parentheses, like '192.168.1.100'.
		"""
		self.scpi = rpscpi.scpi(host, timeout, port)
		self.debugging = debugging
		self.close = self.scpi.close
		self.clear = self.scpi.cls # does nothing!
		self.reset = self.scpi.rst # does nothing!
		
		self.buffsize = 2**14 # i.e. 16384
		self.samprate = 125e6
		
		self.identifier = self.identify()
	
	def read(self, chunksize=4096, format="txt", timeout=None):
		if self.debugging:
			print("reading")
		if format == "txt":
			return self.scpi.rx_txt(chunksize=chunksize)
		else:
			return self.scpi.rx_arb()
	def write(self, cmd):
		if self.debugging:
			print("writing %s" % cmd)
		return self.scpi.tx_txt(cmd)
	def query(self, cmd, chunksize=4096, format="txt"):
		self.write(cmd)
		return self.read(chunksize=chunksize, format=format)
	
	def identify(self):
		return self.query('*IDN?')
	
	def setLED(self, pin=None, state=None):
		# check arguments
		if ((isinstance(pin, int) and not pin in list(range(8))) or
			(isinstance(pin, str) and not pin.lower() == "all")):
			msg = "you specified a strange pin (%s) instead of 0-7 or 'all'" % pin
			raise IOError(msg)
		if ((isinstance(state, int) and not state in (0,1)) or
			(isinstance(state, str) and not state[:2].lower() in ("on", "of"))):
			msg = "you specified a strange state (%s) instead of 0/1/on/off" % state
			raise IOError(msg)
		# define command string
		basecmd = "DIG:PIN LED%s,%s"
		# parse options
		if isinstance(pin, str) and pin[0].lower() == "a":
			result = []
			for i in range(8):
				cmd = basecmd % (i, state)
				r = self.write(cmd)
				result.append(r)
				return result
		if isinstance(state, str):
			if state[:2].lower() == "on":
				state = 1
			else:
				state = 0
		cmd = basecmd % (pin, state)
		return self.write(cmd)
	
	def setLEDbarGraph(self, percent=None):
		# check arguments
		try:
			float(percent)
		except:
			msg = "percent must be a floating-point value (%s)!" % percent
			raise IOError(msg)
		if percent < 0:
			msg = "percent must be greater than zero (%s)!" % percent
			raise IOError(msg)
		elif percent > 100:
			msg = "percent must be less than 100 (%s)!" % percent
			raise IOError(msg)
		# parse options
		if self.debugging:
			print("setting the LED to a bar graph of %s percent" % percent)
		for i in range(8):
			if percent > (i * 100/8.0):
				self.setLED(i, "on")
			else:
				self.setLED(i, "off")
	
	def readAnalogInput(self, ch=None):
		# check arguments
		if not isinstance(ch, int) or not ch in list(range(4)):
			msg = "you must specify a channel 0-3 (%s)" % ch
			raise IOError(msg)
		# define command string
		basecmd = "ANALOG:PIN? AIN%s"
		# parse options
		cmd = basecmd % (ch)
		return float(self.query(cmd))
	
	def setAnalogOutput(self, ch=None, voltage=None):
		# check arguments
		if ((isinstance(ch, int) and not ch in list(range(4))) or
			(isinstance(ch, str) and not ch.lower() == "all")):
			msg = "you specified a strange channel (%s) instead of 0-3 or 'all'" % ch
			raise IOError(msg)
		try:
			float(voltage)
		except:
			msg = "voltage must be a floating-point value (%s)!" % voltage
			raise IOError(msg)
		if voltage < 0:
			msg = "voltage must be greater than zero (%s)!" % voltage
			raise IOError(msg)
		elif voltage > 1.8:
			msg = "voltage must be less than 1.8 V (%s)!" % voltage
			raise IOError(msg)
		# define command string
		basecmd = "ANALOG:PIN AOUT%s,%s"
		# parse options
		if isinstance(ch, str) and ch[0].lower() == "a":
			result = []
			for i in range(4):
				cmd = basecmd % (i, voltage)
				r = self.write(cmd)
				result.append(r)
			return result
		else:
			cmd = basecmd % (ch, voltage)
			return self.write(cmd)
	
	
	def resetFastOutput(self):
		self.write('GEN:RST')
		self.write('OUTPUT1:STATE OFF')
		self.write('OUTPUT2:STATE OFF')
	
	def setFastOutput(self,
		ch=None,
		waveform=None,
		frequency=None,
		amplitude=1.0,
		offset=None, # None or float
		trigger=None, # None or str:internal,external
		threshold=None, # None or (if trigger is external) float:voltage
		burstcycles=None, # None or (if trigger is not None) int
		):
		### check arguments
		# check channels
		if not isinstance(ch, int) or not ch in (1,2):
			msg = "you specified a strange channel (%s) instead of 1 or 2" % ch
			raise IOError(msg)
		# check waveform
		if (not isinstance(waveform, str) or
			not waveform.lower() in ("sine", "square", "triangle", "sawu", "sawd", "pwm", "arb")):
			msg = "you must specify a waveform sine/square/triangle/sawu/sawd/pwm/arb (%s)" % waveform
			raise IOError(msg)
		if waveform.lower() == "arb":
			# https://redpitaya.readthedocs.io/en/latest/appsFeatures/examples/genRF-exm4.html
			raise NotImplementedError("arbitrary waveforms are not supported yet..")
		# check amplitude and offset
		try:
			float(amplitude)
		except:
			msg = "you must specify a amplitude (%s)!" % amplitude
			raise IOError(msg)
		if offset is not None:
			vlo = offset - amplitude/2.0
			vhi = offset + amplitude/2.0
			if (vlo < -1) or (vhi > 1):
				msg = "the output may not exceed ±1 V (%s-%s)!" % (vlo, vhi)
				raise IOError(msg)
		elif amplitude > 2:
			msg = "the output may not exceed ±1 V (%s)!" % (amplitude/2.0)
			raise IOError(msg)
		# check frequency
		try:
			float(frequency)
		except:
			msg = "you must specify a frequency (%s)!" % frequency
			raise IOError(msg)
		if frequency < 0:
			msg = "frequency must be positive (%s)!" % frequency
			raise IOError(msg)
		elif frequency > 62.5e6:
			msg = "frequency may not exceed 62.5 MHz (%s)!" % frequency
			raise IOError(msg)
		# check trigger
		if trigger is not None:
			# https://redpitaya.readthedocs.io/en/latest/appsFeatures/examples/genRF-exm3.html
			raise NotImplementedError("only a continuous generator is supported so far..")
		# check threshold
		if threshold is not None:
			raise NotImplementedError("external trigger and threshold is not supported yet..")
		# check burstcycles
		if burstcycles is not None:
			# https://redpitaya.readthedocs.io/en/latest/appsFeatures/examples/genRF-exm2.html
			raise NotImplementedError("bursts are not supported yet..")
		# parse option
		self.write('SOUR%s:FUNC %s' % (ch, waveform.upper()))
		self.write('SOUR%s:FREQ:FIX %s' % (ch, frequency))
		self.write('SOUR%s:VOLT %f' % (ch, amplitude))
		if offset is not None:
			self.write('SOUR%s:VOLT:OFFS %s' % (ch, offset))
		self.write('OUTPUT%s:STATE ON' % ch)
	
	
	def set_acq_state(self, state):
		if not isinstance(state, str) or not state.upper() in ("START", "STOP"):
			raise IOError("state must be START or STOP (%s)" % state)
		cmd = "ACQ:%s"
		self.write(cmd % state.upper())
	def reset_acq(self):
		cmd = "ACQ:%s"
		self.write("ACQ.RST")
	
	def get_acq_wpos(self):
		return int(self.query("ACQ:WPOS?"))
	def get_acq_tpos(self):
		return int(self.query("ACQ:TPOS?"))
	
	def get_acq_samprate(self):
		return self.query("ACQ:SRAT?")
	def set_acq_samprate(self, rate):
		return self.write("ACQ:SRAT %s" % rate)
	
	def get_acq_decimation(self):
		return int(self.query("ACQ:DEC?"))
	def set_acq_decimation(self, dec=None):
		if dec is None:
			return
		if (not isinstance(dec, int)) or (dec not in self.decimations):
			raise IOError("you may only use an dec of %s (%s)" % (self.decimations, dec))
		else:
			self.write("ACQ:DEC %s" % dec)
	
	def get_acq_trig_status(self):
		return self.query("ACQ:TRIG:STAT?")
	
	def set_acq_trig_source(self, source=None, edge="pos"):
		if source is not None:
			if not source[:3].upper() in ("DIS", "NOW", "CH1", "CH2", "EXT", "AWG"):
				raise IOError("source must be DISABLED, NOW, CH1, CH2, EXT, or AWG (%s)" % source)
			if source[:3].upper() in ("CH1", "CH2", "EXT", "AWG"):
				if not edge[0].upper() in ("P", "N"):
					raise IOError("edge must be POS or NEG (%s)" % edge)
				source = "%s_%sE" % (source[:3].upper(), edge[0].upper())
		else:
			source = "DISABLED"
		cmd = "ACQ:TRIG %s" % source
		self.write(cmd)
	
	def get_acq_trig_delay(self):
		samples = self.query("ACQ:TRIG:DLY?")
		ns = self.query("ACQ:TRIG:DLY:NS?")
		return "%s (%s ns)" % (samples, ns)
	def set_acq_trig_delay(self, delay=None):
		if delay is not None:
			if isinstance(delay, str):
				if not delay[-1] == "s":
					raise IOError("you may request a delay in ns (e.g. 128ns) but this string looks weird: %s" % delay)
				elif not delay[-2] == "n":
					raise NotImplementedError("delay in anything except ns isn't supported yet..")
				else:
					self.write("ACQ:TRIG:DLY:NS %s" % delay[:-2])
			else:
				try:
					int(delay)
				except:
					raise IOError("a trigger delay in samples must be an integer (%s)" % delay)
				self.write("ACQ:TRIG:DLY %s" % delay)
	
	def set_acq_trig_gain(self, gain="low", ch=1):
		if not ch in (1,2):
			raise IOError("you may only choose channel 1 or 2 (%s)" % ch)
		if not gain[0].upper() in ("L", "H"):
			raise IOError("gain must be LV/HV/LOW/HIGH (looks for first letter): %s" % gain)
		else:
			self.write("ACQ:SOUR%s:GAIN %sV" % (ch, gain[0]))
	
	def get_acq_trig_level(self):
		return self.query("ACQ:TRIG:LEV?")*1e-3
	def set_acq_trig_level(self, level=0.1):
		try:
			float(level)
		except:
			raise IOError("trigger level must be a floating point value (%s)" % level)
		mv = level*1e3
		self.write("ACQ:TRIG:LEV %g mV" % mv)
	
	def set_acq_trig(self, source=None, edge=None, level=None, delay=None, gain=None):
		self.set_acq_trig_source(source=source, edge=edge)
		self.set_acq_trig_level(level=level)
		self.set_acq_trig_delay(delay=delay)
		self.set_acq_trig_gain(gain=gain)
	
	def get_acq_data(
		self,
		source=1, # required!
		start=None, # or int
		end=None, # or int
		length=None, # or int
		pretrigger=None, # or int
		posttrigger=None):
		# check quality of arguments
		if not source in (1,2):
			raise IOError("you may only choose source 1 or 2 (%s)" % source)
		if (start is not None):
			if (not isinstance(start, int)):
				raise IOError("start must be the first index for the data buffer (%s)" % start)
			if (end is None) and (length is None):
				raise IOError("if you want a starting index for the data buffer, you must also choose a length or ending index")
			if (length is not None) and (not isinstance(length, int)):
				raise IOError("length must be the length for the data buffer (%s)" % length)
			if (end is not None) and (not isinstance(end, int)):
				raise IOError("end must be the last index for the data buffer (%s)" % end)
		if isinstance(start, int) and not (-self.buffsize <= start < self.buffsize):
			raise IOError("indices/lengths for the data buffer are limited to %s (%s)" % (self.buffsize, start))
		if isinstance(end, int) and not (-self.buffsize < end <= self.buffsize):
			raise IOError("indices/lengths for the data buffer are limited to %s (%s)" % (self.buffsize, end))
		if isinstance(length, int) and not (-self.buffsize < length < self.buffsize):
			raise IOError("indices/lengths for the data buffer are limited to %s (%s)" % (self.buffsize, length))
		if isinstance(pretrigger, int) and not (-self.buffsize < pretrigger < self.buffsize):
			raise IOError("indices/lengths for the data buffer are limited to %s (%s)" % (self.buffsize, pretrigger))
		if isinstance(posttrigger, int) and not (-self.buffsize < posttrigger < self.buffsize):
			raise IOError("indices/lengths for the data buffer are limited to %s (%s)" % (self.buffsize, posttrigger))
		# process request
		if start is not None:
			if length is not None:
				buff_string = self.query('ACQ:SOUR%s:DATA:STA:N? %s,%s' % (source, start, length))
			elif end is not None:
				buff_string = self.query('ACQ:SOUR%s:DATA:STA:END? %s,%s' % (source, start, length))
		elif pretrigger is not None:
			buff_string = self.query('ACQ:SOUR%s:DATA:LAT:N? %s' % (source, pretrigger))
		elif posttrigger is not None:
			buff_string = self.query('ACQ:SOUR%s:DATA:OLD:N? %s' % (source, posttrigger))
		else:
			buff_string = self.query('ACQ:SOUR%s:DATA? %s' % (source))
		try:
			buff_string = buff_string.strip('ERR!{}\n\r').replace("  ", "").split(',')
			buff = list(map(float, buff_string))
			return buff
		except:
			if self.debugging:
				e = sys.exc_info()[1]
				print("an error occurred during the processing of the buffer data: %s" % e)
			return None
	
	
	
	
	
	
	
	