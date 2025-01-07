#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
Provides a dialog window that for performing fits to a variety
of line profiles, including the speed-dependent profiles discussed
by Luca Dore in his 2003 manuscript (Dore, L., J. Mol. Spec., 2003).

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
import logging, logging.handlers
logformat = '%(asctime)s - %(name)s:%(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=logformat)
log = logging.getLogger("QtProLineFitter-%s" % os.getpid())
logpath = os.path.expanduser("~/.log/pyLabSpec-QtProLineFitter.log")
try:
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
log.info("starting a new session (PID: %s)" % os.getpid())
import argparse
# third-party
try:
	import pyqtgraph as pg
except ImportError as e:
	msg = "Could not import pyqtgraph!"
	if 'anaconda' in str(sys.version).lower():
		msg += "\n\tTry doing something like 'conda install pyqtgraph'\n"
	elif sys.platform == 'darwin':
		msg += "\n\tTry doing something like 'sudo port install py-pyqtgraph'\n"
	else:
		msg += "\n\tTry doing something like 'sudo pip install pyqtgraph'\n"
	raise ImportError(msg)
from pyqtgraph.Qt import QtGui, QtCore
# local
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import Dialogs


if __name__ == '__main__':
	# monkey-patch the system exception hook so that it doesn't totally crash
	sys._excepthook = sys.excepthook
	def exception_hook(exctype, value, traceback):
		sys._excepthook(exctype, value, traceback)
	sys.excepthook = exception_hook
	
	# define GUI elements
	qApp = QtGui.QApplication(sys.argv)
	mainGUI = Dialogs.QtProLineFitter()
	
	# parse arguments
	parser = argparse.ArgumentParser()
	parser.add_argument("-d", "--debug", action='store_true', help="whether to activate additional debugging messages")
	parser.add_argument("--conf", type=str, help="a configuration file to use when loading the fitting interface")
	parser.add_argument("file", type=str, nargs='*',
		help="specify file to load")
	parser.add_argument("--filetype", type=str, help="what kind of filetype",
		choices=["ssv", "tsv", "csv", "casac", "jpl", "gesp", "arbdc", "arbs", "ydata"])
	parser.add_argument("--append", action='store_true', help="whether to load files as one (vs individually)")
	parser.add_argument("--skipfirst", action='store_true', help="whether to skip the first line in the file")
	parser.add_argument("--unit", type=str, default="MHz", choices=["MHz", "Hz"], help="the type of unit for the x-axis")
	parser.add_argument("--scanindex", type=int, help="(jpl filetype only) which scan-index to load")
	parser.add_argument("--delimiter", type=str, help="(arbdc filetype only) what string to use to delimit the text, including Perl-style regular expressions if desired")
	parser.add_argument("--xcol", type=int, help="(arbdc filetype only) column number containing the x-axis")
	parser.add_argument("--ycol", type=int, help="(arbdc filetype only) column number containing the y-axis")
	parser.add_argument("--xstart", type=str, help="(arbs filetype only) with which x-value the first y-value begins")
	parser.add_argument("--xstep", type=str, help="(arbs filetype only) at what step to use for the subsequent y-values")
	parser.add_argument("--windowsize", type=str, help="the window size string")
	parser.add_argument("--fitfunc", type=str, help="the fit function")
	parser.add_argument("--moddepth", type=str, help="the mod depth string")
	parser.add_argument("--phase", type=str, help="the phase detuning")
	parser.add_argument("--poly", type=str, help="the polynomial string (use '--poly help' for more info)")

	### parse arguments
	args = parser.parse_args()
	# activate debugging
	if args.debug:
		print("enabling debugging..")
		mainGUI.debug = True
	if args.conf and os.path.exists(args.conf):
		mainGUI.loadConf(filename=args.conf)
	if (args.poly is not None) and (args.poly.lower() == "help"):
		print("Here's the general help information:\n")
		parser.print_help()
		print("\n-------------------------------------\n")
		print("Examples of the poly string are:\n")
		msg = "only a y-offset would look like: 'a' or -0.0004 or 3.4e5\n"
		msg += "a linear baseline would look like: 'ab' or 'a,b' or 'a+b*x'\n"
		msg += "a parabola would look like: 'c'\n"
		msg += "a full polynomial to 3rd order could be:\n"
		msg += "\t'a + b*x + c*x^2 + d*x^3' or '135e-6 + 8.2e-7*x + -7e-7*x^2 + d'"
		print(msg)
		sys.exit()
	# load spectrum
	if len(args.file): args.file = args.file[0] # simply only chooses the first spectrum
	if args.file and os.path.isfile(args.file):
		if (not args.filetype) and args.file[-3:]=="ssv": args.filetype = "ssv"
		elif (not args.filetype) and args.file[-3:]=="tsv": args.filetype = "tsv"
		elif (not args.filetype) and args.file[-3:]=="csv": args.filetype = "csv"
		elif (not args.filetype) and args.file[-2:]=="xy": args.filetype = "csv"
		elif (not args.filetype) and args.file[-3:]=="dat": args.filetype = "gesp"
		settings = {
			"filetype" : args.filetype,
			"appendData" : args.append,
			"skipFirst" : args.skipfirst,
			"unit" : args.unit,
			"scanIndex" : args.unit,
			"delimiter" : args.delimiter,
			"xcol" : args.xcol,
			"ycol" : args.ycol,
			"xstart" : args.xstart,
			"xstep" : args.xstep,
			"filenames" : args.file}
		mainGUI.loadSpec(settings=settings)
	# update GUI elements
	if args.windowsize:
		mainGUI.txt_windowSize.setText(args.windowsize)
	if args.fitfunc:
		fit_types = Dialogs.QtProLineFitter.fit_types
		if args.fitfunc in fit_types:
			mainGUI.combo_fitFunction.setCurrentIndex(fit_types.index(args.fitfunc))
		else:
			print("warning: couldn't parse the fit function correctly!")
	if args.moddepth:
		mainGUI.txt_modDepth.setText(args.moddepth)
	if args.phase:
		mainGUI.txt_phi.setText(args.phase)
		mainGUI.check_phiUse.setChecked(True)
	if args.poly:
		mainGUI.txt_polynom.setText(args.poly)

	# start GUI
	mainGUI.show()
	qApp.exec_()
	qApp.deleteLater()
	sys.exit()
