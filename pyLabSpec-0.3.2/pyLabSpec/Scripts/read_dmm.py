#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# TODO
# - add a checkbox and display for simply showing the current output
#
"""
This program simply connects to a Keithley digital multimeter and
returns its readout.

It also handles a number of more advanced functions, which be accessed
through commandline arguments. Use '--help' as an argument for details.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import sys
import os
import argparse
if sys.version_info[0] == 3:
	import subprocess as commands
else:
	import commands
import time
import datetime
import glob
# third-party
import numpy as np
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import Instruments
from Instruments import multimeter

# flags
debugging = False


def getUSBdevices(include_bus=False):
	cmd_find = "find /sys/bus/usb/devices/usb*/ -name dev"
	cmd_getName = "udevadm info -q name -p %s"
	status, output_find = commands.getstatusoutput(cmd_find)
	devices = []
	for d in output_find.split('\n'):
		devPath = os.path.dirname(d)
		status, output_getName = commands.getstatusoutput(cmd_getName % devPath)
		if (not include_bus) and ("bus/" in output_getName):
			continue
		devices.append(devPath)
	return devices

def findUSBTMC():
	usb_devices = getUSBdevices()
	cmd_getProps = "udevadm info -q property -p %s"
	for d in usb_devices:
		if debugging: print("\nchecking device %s" % d)
		status, output_getProps = commands.getstatusoutput(cmd_getProps % d)
		if debugging:
			print("properties are:")
			for p in output_getProps.split('\n'):
				print("\t%s" % p)
		if "usbtmc" in output_getProps.lower():
			if debugging:
				print("looks like a usbtmc device!")
			props = {}
			for p in output_getProps.split('\n'):
				prop, val = p.split('=')
				props[prop] = val
			return props
	return None


def readDMM(
	dev=None, num=1,
	init_clear=False, init_reset=False,
	wait=0.0, pause=1.0,
	output=None):
	fh = None
	if output:
		try:
			# note the zero nullifies the buffersize and keeps
			# the file up-to-date (as per OS global settings)
			# so that the contents are (approx) realtime
			fh = open(output, 'w', 0)
		except IOError as e:
			print("WARNING: received an error while trying to write out to file (%s)" % e)
			return
	if not dev:
		msg = "WARNING: did not receive a valid device: %s" % dev
		print(msg)
		if fh: fh.write("%s\n" % msg)
		return
	# just get the /dev/* entry
	if isinstance(dev, str):
		dev_str = dev
	else:
		dev_str = "%s (%s)" % (dev.get('ID_SERIAL', "unidentified device"), dev['DEVNAME'])
		dev = dev['DEVNAME']
	# print something useful if debugging
	if debugging:
		msg = "trying to connect to: %s" % dev_str
		print(msg)
		if fh: fh.write("%s\n" % msg)
	# establish connection
	dmm = multimeter.usbtmcdmm(host=dev)
	if init_reset:
		if debugging:
			msg = "resetting the device"
			print(msg)
			if fh: fh.write("%s\n" % msg)
		dmm.reset()
		time.sleep(0.3)
		dmm.clear()
		dmm.display_clear()
		dmm = None
		return
	elif init_clear:
		if debugging:
			msg = "clearing the device first"
			print(msg)
			if fh: fh.write("%s\n" % msg)
		dmm.clear()
	try:
		dmm.identify()
	except OSError as e:
		msg = "received an OSError: %s" % e
		print(msg)
		if fh: fh.write("%s\n" % msg)
	if dmm.identifier:
		msg = "connected: %s" % dmm.identifier
		print(msg)
		if fh: fh.write("%s\n" % msg)
		dmm.display_text("CONNECTED TO PC")
	else:
		return
	time.sleep(wait)
	msg = "current measurement mode: %s" % dmm.get_mode()
	print(msg)
	if fh: fh.write("%s\n" % msg)
	dmm.set_count(1)
	for i in range(num):
		msg = "measurement is: %s (%s)" % (dmm.do_readval(num=1), datetime.datetime.now())
		print(msg)
		if fh: fh.write("%s\n" % msg)
		if num > 1:
			time.sleep(pause)
	if fh:
		fh.write("measurements finished")
		fh.close()


if __name__ == '__main__':
	# parse arguments
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"--debugging",
		action='store_true', default=False,
		help="whether to add extra print messages to the terminal")
	parser.add_argument(
		"-d", "--dev", default=None,
		help="which device to use (e.g. /dev/usbtmc0, default: searches connected devices automatically)")
	parser.add_argument(
		"-n", "--num",
		type=int, default=1,
		help="how many reading to make (default: 1)")
	parser.add_argument(
		"-o", "--output",
		type=str, default=None,
		help="output file for measurements (default: none)")
	parser.add_argument(
		"-p", "--pause",
		type=float, default=1.0,
		help="time between incremental measurements (unit: seconds, default: 1)")
	parser.add_argument(
		"-w", "--wait",
		type=float, default=0.0,
		help="how long to wait before the first measurement (unit: seconds, default: 0)")
	parser.add_argument(
		"--clear",
		action='store_true', default=False,
		help="whether to clear the device (display & error status) upon connection")
	parser.add_argument(
		"--reset",
		action='store_true', default=False,
		help="whether to reset the device upon connection (i.e. as if rebooting) (overrides the clear)")
	# process arguments
	args = parser.parse_args()
	if args.debugging:
		debugging = True
	if not args.dev:
		args.dev = findUSBTMC()
		if args.dev is None: # try the glob method as with the dmm gui
			try:
				args.dev = glob.glob('/dev/usbtmc*')[0]
			except IndexError:
				print("tried to identify a /dev/usbtmc* device file, but nothing was available..")
				args.dev = None
	# do reading
	readDMM(
		dev=args.dev,
		num=args.num, wait=args.wait,
		init_clear=args.clear, init_reset=args.reset,
		pause=args.pause, output=args.output)
