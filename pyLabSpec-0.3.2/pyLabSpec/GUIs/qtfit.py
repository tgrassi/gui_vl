#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# TODO
# - (loading) add alternative units
#	- copy/paste should use a flag for unit in header
#	- in CV tab, perform conversion from original unit
#	- update other tabs for unit conversion
#	- check other tabs for unit labels
#	- some pre-/post-processes should depend on unit (e.g. vlsr)
# - to LA tab:
#	- load all the other input files
# - to FF tab:
#	- reset individual constants
#	- export contents
#
"""
This module provides a class for a GUI that provides classes and methods to
handle an variety of spectral data, particularly in the analysis/processing
of measured data from the other CAS instruments. It also supports loading all
the file types supported by the Spectrum module, which includes general file
formats used by other laboratories and some astronomical data, and the project
files behind the CALPGM (spfit & spcat) software suite that is popular within
the rotational spectroscopy community.

Note that this module is typically called directly as a standalone program.
When this is done, there are a number of optional commandline arguments
that can be used to enhanced functionality. If this is of interest to you,
try calling the file directly with the `-h` or `--help` argument.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
import logging, logging.handlers
logformat = '%(asctime)s - %(name)s:%(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=logformat)
log = logging.getLogger("qtfit-%s" % os.getpid())
logpath = os.path.expanduser("~/.log/pyLabSpec/qtfit.log")
try:
	os.makedirs(os.path.dirname(logpath))
except:
	pass
try:
	loghandler = logging.handlers.TimedRotatingFileHandler(logpath, when='d', interval=1, backupCount=10)
	loghandler.setFormatter(logging.Formatter(logformat))
	log.addHandler(loghandler)
except:
    e = sys.exc_info()
    log.info("warning: couldn't set up a log handler at '%s' (e: %s)" % (logpath, e))
log.info("**** STARTING A NEW SESSION (PID: %s) ****" % os.getpid())
from sys import platform
import codecs
import re
from functools import partial
import argparse
import datetime, time
import math, random
import subprocess
import tempfile
import shutil
import copy
import webbrowser
import distutils.version
from timeit import default_timer as timer
import linecache
if sys.version_info[0] == 3:
	import urllib.request
	from urllib.request import urlopen, urlretrieve
else:
	from urllib import urlretrieve
	from urllib2 import urlopen # urlopen from urllib2 provides a timeout
import cgi
import ssl
# third-party
import numpy as np
import scipy
from scipy import interpolate
if sys.platform == "win32" and getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):   # i.e. if bundled from pyinstaller
	import PyQt5
	from PyQt5 import QtGui, QtCore
	from PyQt5 import uic
try:
	import pyqtgraph as pg
	from pyqtgraph import siScale
except ImportError as e:
	msg = "Could not import pyqtgraph! This plotting library is absolutely required by QtFit.."
	log.debug("Executable: %s" % sys.executable)
	if ('anaconda' in str(sys.version).lower() or
		"anaconda" in str(sys.executable)):
		msg += "\n\tTry doing something like 'conda install pyqtgraph'\n"
	elif sys.platform == 'darwin':
		msg += "\n\tTry doing something like 'sudo port install py-pyqtgraph'\n"
	else:
		msg += "\n\tTry doing something like 'sudo pip install pyqtgraph'\n"
	log.exception(msg)
	raise
if not (sys.platform == "win32" and getattr(sys, 'frozen', False)):
	from pyqtgraph.Qt import QtGui, QtCore
	from pyqtgraph.Qt import uic
loadUiType = uic.loadUiType
if distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5.6":
	try:
		from PyQt5 import QtWebEngineWidgets    # must be imported now, if ever
	except ImportError:
		if sys.platform == "win32" and getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
			pass
		else:
			log.exception("IMPORTERROR: if you got here, you should probably try 'sudo apt-get install python-pyqt5.qtwebengine'")
	try:
		from OpenGL import GL               # to fix an issue with NVIDIA drivers
	except:
		pass
try:
	import yaml
except ImportError as e:
	msg = "Could not import PyYAML, so saving/loading sessions from the CV tab won't work!"
	if 'anaconda' in str(sys.version).lower():
		msg += "\n\tTry doing something like 'conda install pyyaml'\n"
	elif sys.platform == 'darwin':
		msg += "\n\tTry doing something like 'sudo port install py-yaml'\n"
	else:
		msg += "\n\tTry doing something like 'sudo pip install PyYAML'\n"
	log.exception(msg)
try:
	import requests
except ImportError as e:
	msg = "Could not import the requests module, so one of the methods for"
	msg += " accessing the VAMDC catalogs may fail"
	if sys.platform == 'darwin':
		msg += "\n\tTry doing something like 'sudo port install py-requests'\n"
	else:
		msg += "\n\tTry doing something like 'sudo apt-get install python-requests'\n"
	log.exception(msg)
# local
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	log.info("Adding QtFit's directory to the python path.")
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import Widgets
import Dialogs
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	log.info("Adding pyLabSpec's directory to the python path.")
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Spectrum import spectrum, Filters, plotlib
from Catalog import catalog
from Fit import fit
import miscfunctions

if sys.version_info[0] == 3:
	log.debug("Setting some hacks for py3 (reload to namespace, xrange=range, and unicode=str)")
	from importlib import reload
	xrange = range
	unicode = str


# defines a test function for simulating catalog data (the others have been moved to the Fit module)
simtest = lambda x, f, i, fwhm: gaussian(x,f,i,fwhm*0.89) * ((fwhm*0.89)**2 - (f-x)**2)/(fwhm*0.89)**4 * c*0.0792 # copied from 2f_adj


# determine the correct containing the *.ui files
ui_filename = 'QtFitMainWindow.ui'
ui_path = ""
for p in (os.path.dirname(os.path.realpath(__file__)),
		  os.path.dirname(__file__),
		  os.path.dirname(os.path.realpath(sys.argv[0]))):
	log.info("checking %s for the ui_path" % p)
	if os.path.isfile(os.path.join(p, ui_filename)):
		ui_path = p # should be most reliable, even through symlinks
		log.info("that was it..")
		break
	elif os.path.isfile(os.path.join(p, "resources", ui_filename)):
		ui_path = os.path.join(p, "resources") # should be most reliable, even through symlinks
		log.info("used the resources subdirectory..")
		break
if ui_path == "":
	raise IOError("could not identify the *.ui files")

Ui_MainWindow, QMainWindow = loadUiType(os.path.join(ui_path, ui_filename))
class QtFitGUI(QtGui.QMainWindow, Ui_MainWindow):
	"""
	Defines the main window of the QtFit GUI.
	"""
	def __init__(self):
		super(self.__class__, self).__init__()
		self.setupUi(self)

		### main window properties
		self.programName = "QtFit"
		self.setWindowTitle(self.programName)
		if sys.platform == "win32" and not getattr(sys, "frozen", False):
			self.setWindowIcon(QtGui.QIcon(os.path.join(ui_path, 'linespec.ico')))
		else:
			self.setWindowIcon(QtGui.QIcon(os.path.join(ui_path, 'linespec.svg')))
		self.debugging = False
		self.cwd = os.getcwd()


		### button functionality
		# CV tab
		self.btn_CVloadCatalog.clicked.connect(self.CVloadCatalog)
		self.btn_CVloadVAMDCCatalog.clicked.connect(self.CVbrowseVAMDC)
		self.btn_CVremoveCatalog.clicked.connect(self.CVremoveCatalog)
		self.btn_CVloadExp.clicked.connect(self.CVloadExp)
		self.btn_CVpasteExp.clicked.connect(self.CVpasteExp)
		self.btn_CVloadOther.clicked.connect(self.CVloadOther)
		self.btn_CVremoveExp.clicked.connect(self.CVremoveExp)
		self.btn_CVrecolorCat.clicked.connect(self.CVrecolorCat)
		self.btn_CVrecolorExp.clicked.connect(self.CVrecolorExp)
		self.btn_CVrenameCat.clicked.connect(self.CVrenameCat)
		self.btn_CVrenameExp.clicked.connect(self.CVrenameExp)
		self.btn_CVexpHeader.clicked.connect(self.CVshowHeader)
		self.btn_CVexpTransformations.clicked.connect(self.CVchooseTransformations)
		self.btn_CVsaveSession.clicked.connect(self.CVsaveSession)
		self.btn_CVloadSession.clicked.connect(self.CVloadSession)
		self.btn_CVresetPlotLegend.clicked.connect(self.CVresetPlotLegend)
		self.btn_CVclearPlotLabels.clicked.connect(self.CVclearPlotLabels)
		self.btn_CVviewCatsDisp.clicked.connect(partial(self.CVviewCatEntries, useCutoff=True))
		self.btn_CVviewCatsAll.clicked.connect(self.CVviewCatEntries)
		self.btn_CVupdatePlot.clicked.connect(self.CVupdatePlot)
		self.btn_CVdoSplat.clicked.connect(self.CVdoSplat)
		#self.btn_CVprevPlotView.clicked.connect(self.CVprevPlotView)
		# ES tab
		self.btn_ESloadScan.clicked.connect(self.ESloadScan)
		self.btn_ESpasteScan.clicked.connect(self.ESpasteScan)
		self.btn_ESclearPlot.clicked.connect(self.ESclearPlot)
		self.btn_ESclearPlotLabels.clicked.connect(self.ESclearPlotLabels)
		# BR tab
		self.btn_BRloadScan.clicked.connect(self.BRloadScan)
		self.btn_BRpasteScan.clicked.connect(self.BRpasteScan)
		self.btn_BRclearPlotTop.clicked.connect(self.BRclearPlotTop)
		self.btn_BRshowHeader.clicked.connect(self.BRshowHeader)
		self.btn_BRclearBoxes.clicked.connect(self.BRclearPlotBoxes)
		self.btn_BRclearLines.clicked.connect(self.BRclearPlotLines)
		self.btn_BRupdateBottom.clicked.connect(self.BRupdateBottomPlot)
		self.btn_BRclearBottom.clicked.connect(self.BRclearPlotBottom)
		self.btn_BRfit.clicked.connect(self.BRdoFit)
		self.btn_BRfitPro.clicked.connect(self.BRdoFitPro)
		self.btn_BRsplat.clicked.connect(self.BRdoSplat)
		# LA tab
		self.btn_LAloadCat.clicked.connect(self.LAloadCat)
		self.btn_LAclearCat.clicked.connect(self.LAclearCat)
		self.btn_LAloadExp.clicked.connect(self.LAloadExp)
		self.btn_LApasteExp.clicked.connect(self.LApasteExp)
		self.btn_LAclearExp.clicked.connect(self.LAclearExp)
		self.btn_LAaddSticks.clicked.connect(self.LAaddSticks)
		self.btn_LAclearSticks.clicked.connect(self.LAclearSticks)
		self.btn_LAclearMarkers.clicked.connect(self.LAclearMarkers)
		self.btn_LAgetCursorFreq.clicked.connect(self.LAgetCursorFreq)
		self.btn_LAfitGauss.clicked.connect(self.LAfitGauss)
		self.btn_LAfit2f.clicked.connect(self.LAfit2f)
		self.btn_LAfitPro.clicked.connect(self.LAfitPro)
		self.btn_LAaddEntry.clicked.connect(self.LAaddEntry)
		# FF tab
		self.btn_FFloadFiles.clicked.connect(self.FFloadFiles)
		self.btn_FFreset.clicked.connect(self.FFreset)
		self.btn_FFaddConstant.clicked.connect(self.FFaddConstant)
		self.btn_FFupdate.clicked.connect(self.FFupdate)
		self.btn_FFrecolorCat.clicked.connect(self.FFrecolorCat)
		self.btn_FFrecolorExp.clicked.connect(self.FFrecolorExp)
		self.btn_FFloadExp.clicked.connect(self.FFloadExp)
		self.btn_FFpasteExp.clicked.connect(self.FFpasteExp)
		self.btn_FFremoveExp.clicked.connect(self.FFremoveExp)
		self.btn_FFaddSticks.clicked.connect(self.FFaddSticks)
		self.btn_FFclearSticks.clicked.connect(self.FFclearSticks)
		self.btn_FFclearLabels.clicked.connect(self.FFclearLabels)
		# CA tab
		self.btn_CAloadFiles.clicked.connect(self.CAloadFiles)
		self.btn_CArepQ.clicked.connect(self.CArepQ)
		self.btn_CArepBlah.clicked.connect(self.CArepBlah)
		# main
		self.btn_browseCASData.clicked.connect(self.launchCASBrowser)
		self.btn_test.clicked.connect(self.runTest)
		self.btn_openTmpDir.clicked.connect(self.openTmpDir)
		self.btn_console.clicked.connect(self.showConsole)
		self.btn_quit.clicked.connect(self.exit)

		### GUI element contents/options
		self.colorDialog = QtGui.QColorDialog()
		self.colorDialog.setOption(QtGui.QColorDialog.ShowAlphaChannel, True)
		self.highlightedPenStyle = QtCore.Qt.DashDotLine # or just QtCore.Qt.DashLine?
		self.useVamdcPartFxns = True
		self.vamdcFile = "/tmp/vamdcSpecies.npy"
		self.url_vamdccat = 'https://cdms.astro.uni-koeln.de/cdms/tap/sync?REQUEST=doQuery&LANG=VSS2&FORMAT=mrg&QUERY=SELECT+RadiativeTransitions+WHERE+SpeciesID=%s+&ORDERBY=frequency'
		self.url_cdmscat = 'https://cdms.astro.uni-koeln.de/classic/entries/c%s.cat'
		self.url_jplcat = 'https://spec.jpl.nasa.gov/ftp/pub/catalog/c%s.cat'
		self.url_CASData = "http://cas01int.mpe.mpg.de/"
		self.CVsimShapes = [
			'gaussian',
			#'2f gaussian (adj)',
			'2f gaussian',
			'lorentzian',
			'test']
		for s in self.CVsimShapes:
			self.cb_CVsimShape.addItem(s)
		self.txt_CVsimScale.opts['formatString'] = "%.2e"
		self.txt_CVtemperature.opts['formatString'] = "%g"
		self.txt_CVtemperature.opts['constStep'] = 5
		self.txt_CVtemperature.opts['min'] = 0.0
		self.txt_CVsimLW.opts['formatString'] = "%.1e"
		self.txt_CVsimStep.opts['formatString'] = "%.1e"
		for op in [" ","+","-"]:
			self.cb_CVexpMathOp.addItem(op)
		self.txt_BRlowpassRolloff.opts['formatString'] = "%.1e"
		self.const_watsonA = [
			('A', '10000'), ('B', '20000'), ('C', '30000'),
			('-Delta_K', '2000', u'-Δⱼₖ'), ('-Delta_JK', '1100', u'-Δⱼₖ'), ('-Delta_J', '200', u'-Δⱼ'),
			('-delta_K', '41000', u'-δₖ'), ('-delta_J', '40100', u'-δⱼ'),
			('Phi_K', '3000', u'Φₖ'), ('Phi_KJ', '2100', u'Φₖⱼ'), ('Phi_JK', '1200', u'Φⱼₖ'), ('Phi_J', '300', u'Φⱼ'),
			('phi_K', '42000', u'φₖ'), ('phi_JK', '41100', u'φⱼₖ'), ('phi_J', '40200', u'φⱼ'),
			('L_K', '4000'), ('L_KKJ', '3100'), ('L_JK', '2200'), ('L_JJK', '1300'), ('L_J', '400'),
			('l_K', '43000'), ('l_KJ', '42100'), ('l_JK', '41200'), ('l_J', '40300'),
			('P_K', '5000'), ('P_KKJ', '4100'), ('P_KJ', '3200'), ('P_JK', '2300'), ('P_JJK', '1400'), ('P_J', '500'),
			('p_K', '44000'), ('p_KKJ', '43100'), ('p_JK', '42200'), ('p_JJK', '41300'), ('p_J', '40400'),
			('S_K', '6000'), ('T_K', '7000'),
		]
		self.const_watsonS = [
			('A', '10000'), ('B', '20000'), ('C', '30000'),
			('-D_K', '2000', u'-Dₖ'), ('-D_JK', '1100', u'-Dⱼₖ'), ('-D_J', '200', u'-Dⱼ'),
			('d1', '40100', u'd₁'), ('d2', '50000', u'd₂'),
			('HK', '3000', u'Hₖ'), ('HKJ', '2100', u'Hₖⱼ'), ('HJK', '1200', u'Hⱼₖ'), ('HJ', '300', u'Hⱼ'),
			('h1', '40200', u'h₁'), ('h2', '50100', u'h₂'), ('h3', '60000', u'h₃'),
			('LK', '4000'), ('LKKJ', '3100'), ('LJK', '2200'), ('LJJK', '1300'), ('LJ', '400'),
			('l1', '40300'), ('l2', '50200'), ('l3', '60100'), ('l4', '70000'),
			('PJ', '500'), ('PJJK', '1400'), ('PJK', '2300'), ('PKJ', '3200'), ('PKKJ', '4100'), ('PK', '5000'),
			('p1', '40400'), ('p2', '50300'), ('p3', '60200'), ('p4', '70100'), ('p5', '80000'),
			('S_K', '6000'), ('T_K', '7000'),
		]
		self.const_hyperfine = [
			# spin-orbit
			('-2A zet_t', '200000', u'-2*Aζₜ'), ('et_e zet_t', '200100', u'ηₑζₜ'), ('et_e zet_t', '200100', u'ηₖζₜ'),
			('a zet_e d', '10200000', u'aζₑd'), ('aD zet_e d', '10201000', u'ᵃᴅζₑd'),
			# spin-rotation
			('eps_aa', '10010000', u'ε.aa'), ('eps_bb', '10020000', u'ε.bb'), ('eps_cc', '10030000', u'ε.cc'),
			('eps_1', '10040001', u'ε₁'), ('eps_2a', '990000'),
			('eps(2a+2b)', '10610010', u'½*(ε.ab+ε.ba)'), ('eps(2a-2b)', '100610010', u'½*(ε.ab-ε.ba)'),
			# spin-rotation distortion
			('Del(S)_K', '5001000', u'Δˢₖ'), ('Del(S)_KN', '1001000', u'Δˢₖₙ'), ('Del(S)_NK', '5000100', u'Δˢₙₖ'), ('Del(S)_N', '1000100', u'Δˢₙ'),
			# nuclear quadrupole, spin 1
			('3/2*chi_aa', '110010000', u'³⁄₂*χₐₐ, spin 1'), ('3/2*chi_bb', '110020000', u'³⁄₂*χbb, spin 1'), ('3/2*chi_cc', '110030000', u'³⁄₂*χcc, spin 1'),
			('1/4*chi(b-c)', '110040000', u'¼*(χbb-χcc), spin 1'),
			('chi_ab', '110610000', u'χab, spin 1'), ('chi_bc', '110210000', u'χbc, spin 1'), ('chi_ac', '110410000', u'χac, spin 1'),
			('3/2*chi_K', '110011000', u'³⁄₂*χₖ, spin 1'), ('3/2*chi_J', '110011000', u'³⁄₂*χⱼ, spin 1'),
			# nuclear quadrupole, spin 2
			('3/2*chi_aa', '220010000', u'³⁄₂*χₐₐ, spin 2'), ('3/2*chi_bb', '220020000', u'³⁄₂*χbb, spin 2'), ('3/2*chi_cc', '220030000', u'³⁄₂*χcc, spin 2'),
			# fermi contact
			('a_L', '20200000', u'ᵃʟ'), ('sig0', '120000000', u'ᵃꜰ or σ₀'), ('2*sig+-', '120000010', u'2*σ±'),
			('a_FJ', '120000100', u'ᵃꜰᴊ or Δˢˢₙ'), ('a_FK', '120001000', u'ᵃꜰᴋ or Δˢˢₖₙ'),
			('Del(SS)_K', '120011000', u'Δˢˢₖ or ³⁄₂*Tₐₐᴋ'), ('Del(SS)_NK', '120010100', u'Δˢˢₙₖ or ³⁄₂*Tₐₐᴊ'),
			('del(SS)_1', '120040100', u'δˢˢ₁'), ('del(SS)_2', '120050000', u'δˢˢ₂'),
			# spin-spin
			('3/2*D_aa', '120010000', u'³⁄₂*Tₐₐ or 2*T²₀(C₀)'), ('1/4*D(b-c)', '120040000', u'¼*(Tbb-Tcc)'), ('D_ab', '120610000', u'Tab'),
			('6*T0C+', '120010010', u'6*T²₀(ᶜ±)'), ('T+C0', '120040001', u'T²_±2(C₀)'), ('2*T-C+', '120040010', u'T²_⁻⁄₊2(ᶜ±)'),
		]

		### add tooltips
		# CV tab
		self.tabWidget.setCurrentWidget(self.tabCatalogViewer)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Catalog Viewer</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Rotational line catalogs compatible with the JPL/CDMS databases (i.e. CALPGM) and
				experimental spectral data can be plotted easily. Most things should be self-
				explanatory, except for the integer spinboxes: they are associated with the index
				of the catalogs/spectra and are used for adding/removing/modifying what's been loaded.
				See their hovertext for the current listing of catalogs and their respective indices.
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- simulate catalogs at different temperatures<br/>
				- simulate catalogs at alternative absolute scales<br/>
				- highlight observed/unobserved lines (only for MRG files!)<br/>
				- draw horizontal lines according to the catalog uncertainties<br/>
				- simulate basic line profiles (Gaussian, Lorentzian, 2f)<br/>
				- plot experimental spectra<br/>
				- perform basic arithmetic (addition or subtraction) between two experimental spectra<br/>
				- recolor all plots<br/>
				- provides an interface to browse/load molecular line catalogs from the VAMDC (JPL/CDMS)
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Ctrl+B - Launch a simple web browser to load the CasDataManagement website for browsing/loading spectral data<br/>
				Ctrl+PgDwn / Ctrl+Tab - Next tab<br/>
				Ctrl+PgUp / Ctrl+Shift+Tab - Previous tab<br/>
				Ctrl+T / Ctrl+Shift+T - Run runtest() or runtest2()<br/>
				Escape or Shift+Esc - Exit the GUI (shift skips the confirmation prompt)<br/>
				Alt+C - Switch back to this tab<br/>
				Ctrl+L - Load experimental spectrum<br/>
				Ctrl+V - Paste an experimental spectrum (must be CSV!)<br/>
				Ctrl+R / F5 - Force an update of the plot<br/>
				Ctrl+Z - Remove the last label
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts:</span><br/>
				Control+Hover - View the XY coordinates<br/>
				Shift+Hover - View nearest catalog line (or the XY coordinates)<br/>
				Shift+LeftClick - Add catalog entry label<br/>
				Ctrl+LeftClick - Add XY label<br/>
				LeftClick+Drag - Pan the plot<br/>
				RightClick - View plot menu<br/>
				RightClick+Drag - Zoom the plot<br/>
				Hover+Delete - Delete the plot label under mouse
			</p>
			</body></html>
			""")
		self.btn_CVloadCatalog.setToolTip(
			"Provides a dialog to load SPFIT/SPCAT catalog file."
			"\nPRO TIP: hold the following while clicking to plot in wavenumbers:"
			"\n\tSHIFT: load a wavenumber-based file to wavenumbers"
			"\n\tSHIFT+CTRL: fix the loading of a wavenumber-based file")
		self.btn_CVloadExp.setToolTip("(Ctrl+L)")
		self.btn_CVpasteExp.setToolTip("(Ctrl+V)")
		self.btn_CVrecolorCat.setToolTip(
			"Provides a dialog to change the color of a catalog file."
			"\nPRO TIP: hold SHIFT while clicking, to change ALL the plotted catalogs!")
		self.check_CVsimHighlightObs.setToolTip(
			"If this is checked, only the lines in the selected catalog"
			"\nwhich have been marked as observed will be solid lines."
			"\nAll others will be shown using a discontinuous line style.")
		self.check_CVsimShowUnc.setToolTip(
			"If this is checked, frequency uncertainties will be"
			"\nillustrated using horizontal lines like error bars.")
		self.btn_CVrecolorExp.setToolTip(
			"Provides a dialog to change the color of a spectrum."
			"\nPRO TIP: hold SHIFT while clicking, to change ALL the plotted spectra!")
		self.cb_CVexpMathOp.setToolTip(
			"Allows one to perform math between two experimental spectra."
			"\nNote that interpolation (linear & nearest-neighbors) of"
			"\nthe second spectrum is used to determine what to add to/"
			"\nsubtract from the first spectrum. This means you probably"
			"\nwant the highest-resolution spectrum to be the first one..")
		self.btn_CVexpTransformations.setToolTip(
			"Provides a dialog to perform certain transformations to a"
			"\nloaded spectrum. These changes are only temporary (i.e."
			"\nonly the plot is affected).")
		self.btn_CVsaveSession.setToolTip(
			"Provides a dialog to save the current session (i.e. all the"
			"\nloaded catalogs and spectra, and their settings) to a file"
			"\nfor future loading.")
		self.btn_CVloadSession.setToolTip(
			"Provides a dialog to load an old session. Try saving one first"
			"\nto get an idea of how to create/edit one.")
		self.btn_CVresetPlotLegend.setToolTip(
			"Redraws the legend, fixing a number of bugs that may crop up"
			"\nduring usage (i.e. sometimes it sucks..).")
		self.btn_CVupdatePlot.setToolTip(
			"Refreshes the plot, but is usually automatic. (Ctrl+R or F5)")
		self.btn_CVdoSplat.setToolTip(
			"Queries VAMDC (CDMS and JPL only, until further requested)"
			" for spectral matches against the current plot window.")
		# ES tab
		self.tabWidget.setCurrentWidget(self.tabEasyStats)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Easy Stats</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Allows quick access to basic stats of an experimental spectrum or regions of it.
				For example, it can be useful for checking signal to noise ratios, by adding a
				region to a line-free area to see the std. dev., and then selecting a region at the
				peak of a line to see the intensity.
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- plot experimental spectra<br/>
				- provides two interactive windows to view statistics about specific regions
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Ctrl+B - Launch a simple web browser to load the CasDataManagement website<br/>
				Ctrl+PgDwn / Ctrl+Tab - Next tab<br/>
				Ctrl+PgUp / Ctrl+Shift+Tab - Previous tab<br/>
				Ctrl+T / Ctrl+Shift+T - Run runtest() or runtest2()<br/>
				Escape or Shift+Esc - Exit the GUI (shift skips the confirmation prompt)<br/>
				Alt+S - Switch back to this tab<br/>
				Ctrl+L - Load experimental spectrum<br/>
				Ctrl+C - Copy an experimental spectrum (to CSV format)<br/>
				Ctrl+V - Paste an experimental spectrum (must be CSV!)
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts:</span><br/>
				Shift+Hover - View XY coordinates<br/>
				Shift+LeftClick - Add XY coordinate label<br/>
				Ctrl+LeftClick - Add a resizable ROI to select a region of data<br/>
				LeftClick+Drag - Pan the plot<br/>
				RightClick - View plot menu<br/>
				RightClick+Drag - Zoom the plot
			</p>
			</body></html>
			""")
		self.btn_ESloadScan.setToolTip("(Ctrl+L)")
		self.btn_ESpasteScan.setToolTip("(Ctrl+V)")
		# BR tab
		self.tabWidget.setCurrentWidget(self.tabDebaseline)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Baseline Removal</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Provides tools to flatten a spectral scan, to clean it up (remove spikes), and
				(one day) to fit spectral lines to a region of data. One can load a spectrum to the
				top plot, and either a) directly flatten the baseline with the "De-baseline"
				checkbox and one (or more) of the spectral filters, or b) drawing boxes around
				noise spikes to make a more presentable spectrum for a nice figure.
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- plot an experimental spectrum<br/>
				- filter a spectrum, for smoothing or for baseline subtraction<br/>
				- use interactive lines to set baselines<br/>
				- use interactive boxes to remove data points
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Ctrl+B - Launch a simple web browser to load the CasDataManagement website<br/>
				Ctrl+PgDwn / Ctrl+Tab - Next tab<br/>
				Ctrl+PgUp / Ctrl+Shift+Tab - Previous tab<br/>
				Ctrl+T / Ctrl+Shift+T - Run runtest() or runtest2()<br/>
				Escape or Shift+Esc - Exit the GUI (shift skips the confirmation prompt)<br/>
				Alt+B - Switch back to this tab<br/>
				Ctrl+L - Load experimental spectrum<br/>
				Ctrl+C - Copy an experimental spectrum (from the bottom plot)<br/>
				Ctrl+V - Paste an experimental spectrum (to the top plot)<br/>
				Ctrl+R / F5 - Force an update of the bottom plot
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts (both plots):</span><br/>
				Shift+Hover - View XY coordinates<br/>
				RightClick - View plot menu<br/>
				RightClick+Drag - Zoom the plot<br/>
				LeftClick+Drag - Pan the plot
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts (top plot):</span><br/>
				Shift+Click - Add interactive box to remove contained datapoints<br/>
				Ctrl+Click - Anchor endpoint of line (first click) and then add interactive line (second click)
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts (bottom plot):</span><br/>
				Shift+Click - Add XY coordinate label<br/>
				Ctrl+Click - Add interactive ROI overlay to select range of data (tip: numbers are used with the "Fit" button)
			</p>
			</body></html>
			""")
		self.btn_BRloadScan.setToolTip("(Ctrl+L)")
		self.btn_BRpasteScan.setToolTip("(Ctrl+V)")
		self.btn_BRclearBoxes.setToolTip("Removes all the boxes.")
		self.btn_BRclearLines.setToolTip("Removes all the active straight lines.")
		self.label_BRdataLength.setToolTip(
			"The number of data points found in the top spectrum.")
		self.txt_BRdataLength.setToolTip(
			"The number of data points found in the top spectrum.")
		#self.frame_BRbottomOpt.setToolTip(
		#	"Listed here are all the possible methods for filtering"
		#	"\nand/or flattening the data prior to attempting a fit.")
		self.check_BRfilterLines.setToolTip(
			"Whether to apply all the filters to the lines, instead"
			"\nof using a mask in their place. This is particularly"
			"\nwell-suited for simply fixing a minor baseline offset"
			"\nto the data before finally activating a filter.")
		self.check_BRdebaseline.setToolTip(
			"Whether to use the filters as a rolling reference for"
			"\nbeing directly subtracted from the data.")
		self.label_BRlowpass.setToolTip(
			"Enables the use of a Buttworth filter to provide a low-pass filter"
			"\nof the data.")
		self.cb_BRlowpassOrd.setToolTip(
			"The order to use for the low-pass filter.")
		self.txt_BRlowpassRolloff.setToolTip(
			"The frequency at which to begin the rolloff of the low-pass filter,"
			"\nwhere the frequency is normalized with respect to the Nyquist"
			"\nfrequency (pi rads/sample) and can range from 0 to 1.")
		self.label_BRgauss.setToolTip(
			"Enables the use of a Gaussian filter for convolution"
			"\nwith the data.")
		self.cb_BRgaussWin.setToolTip("The number of points for the filter window.")
		self.cb_BRgaussSig.setToolTip("The amplitude (std. dev.) (default: 10).")
		self.label_BRderivative.setToolTip(
			"Performs a numerical derivative on a B-spline representation of the"
			"\ndata. The B-spline is based on splev and splder of FITPACK.")
		self.label_BRwiener.setToolTip(
			"Enables the use of the Wiener filter, but the version"
			"\nused by SciPy is rather simplistic and essentially"
			"\na simple local-mean filter.")
		self.cb_BRwienerWin.setToolTip("Size of the filter window to use.")
		self.label_BRsg.setToolTip(
			"Enables the use of the famous Savitzky-Golay filter,"
			"\nwhich is a low-pass filter particularly well-suited"
			"\nfor smoothing noisy data while still maintaining the"
			"\noverall form.")
		self.cb_BRsgWin.setToolTip("Defines the window size of the filter.")
		self.cb_BRsgOrder.setToolTip("Defines the order of the polynomial (default: 1).")
		self.btn_BRupdateBottom.setToolTip(
			"Refreshes this bottom plot, but is usually automatic. (Ctrl+R or F5)")
		self.btn_BRclearBottom.setToolTip(
			"Clears all the labels and window-regions that may be defined plot.")
		self.cb_BRwindow.setToolTip(
			"Defines the (optional) region that may be specified"
			"\nfor a fit. A value of zero will simply use the full"
			"\ndataset. The indices are determined at the time of"
			"\ntheir creation, and are shown as hover text with"
			"\nthe mouse.")
		self.btn_BRsplat.setToolTip(
			"Queries VAMDC (CDMS and JPL only, until further requested)"
			" for spectral matches against the plot region or range.")
		self.btn_BRfit.setToolTip("Opens a child window for performing the fit.")
		self.btn_BRfitPro.setToolTip(
			"Similar to the other fit, except uses a more advanced dialog and more line profiles.")
		# LA tab
		self.tabWidget.setCurrentWidget(self.tabLineAssignments)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Line Assignments</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Provide functionality similar to JPL's SMAP software, for assigning rest frequencies
				from experimental data, to a work-in-progress SPFIT project.
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- plot a set of experimental spectra alongside the associated catalog<br/>
				- select an active (or several) catalog entry and add its/their entry in a .lin-formatted style<br/>
				- perform line profile fits to a experimental data, for assignments to catalog entries
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Ctrl+B - Launch a simple web browser to load the CasDataManagement website<br/>
				Ctrl+PgDwn / Ctrl+Tab - Next tab<br/>
				Ctrl+PgUp / Ctrl+Shift+Tab - Previous tab<br/>
				Ctrl+T / Ctrl+Shift+T - Run runtest() or runtest2()<br/>
				Escape or Shift+Esc - Exit the GUI (shift skips the confirmation prompt)<br/>
				Alt+L - Switch back to this tab<br/>
				Ctrl+V - Paste an experimental spectrum
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts:</span><br/>
				Control+Hover - View the XY coordinates<br/>
				Shift+Hover - View nearest catalog line<br/>
				RightClick - View plot menu<br/>
				RightClick+Drag - Zoom the plot<br/>
				LeftClick+Drag - Pan the plot<br/>
				Ctrl+Click - Add a box &amp; window for selecting catalog entries &amp; performing fits (respectively)<br/>
				Shift+Click - Add a marker for the nearest catalog line
			</p>
			</body></html>
			""")
		self.btn_LAloadCat.setToolTip(
			"Provides a dialog to load SPFIT/SPCAT catalog file."
			"\nPRO TIP: hold SHIFT while clicking, to convert MHz to wavenumbers!")
		self.btn_LApasteExp.setToolTip("(Ctrl+V)")
		# FF tab
		self.tabWidget.setCurrentWidget(self.tabFitFidget)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Fit Fidget</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Provides an interface to interact with an SPFIT project, to modify fit constants,
				and immediately visualize this impact on the catalog by overlaying the before-and-after
				stick plots. Load INT+VAR files, and tweak a constant (or add a new one) to
				immediately see the resulting effect.<br/>
				*note* SPCAT must be available in your executable path!
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- plot an ongoing SPFIT project by loading INT+VAR files and plotting the associated catalog<br/>
				- add/remove/modify descriptions/values/uncertainties of fit constants<br/>
				- (NOT YET!) overlay an experimental spectrum
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Ctrl+B - Launch a simple web browser to load the CasDataManagement website<br/>
				Ctrl+PgDwn / Ctrl+Tab - Next tab<br/>
				Ctrl+PgUp / Ctrl+Shift+Tab - Previous tab<br/>
				Ctrl+T / Ctrl+Shift+T - Run runtest() or runtest2()<br/>
				Escape or Shift+Esc - Exit the GUI (shift skips the confirmation prompt)<br/>
				Alt+F - Switch back to this tab<br/>
				Ctrl+L - Load experimental spectrum<br/>
				Ctrl+V - Paste an experimental spectrum<br/>
				Ctrl+R - Reset the constants<br/>
				F5 / Return - Update the new fit
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts:</span><br/>
				RightClick - View plot menu<br/>
				RightClick+Drag - Zoom the plot<br/>
				LeftClick+Drag - Pan the plot<br/>
				Shift+Click - Add label about nearest catalog entry<br/>
				Ctrl+Click - Add XY coordinate label
			</p>
			</body></html>
			""")
		self.btn_FFloadFiles.setToolTip("Load files from a SPFIT/SPCAT project.")
		self.btn_FFreset.setToolTip(
			"Reloads the input files resets the constants to their original values. (Ctrl+R)")
		self.btn_FFaddConstant.setToolTip(
			"PRO TIP: hold down SHIFT to activate a menu containing"
			"\npredefined constants (credit: Kisiel for his nice website).")
		self.btn_FFupdate.setToolTip(
			"Refreshes this bottom plot, but is usually automatic."
			"\n(F5, also Return/Enter from a text field)")
		self.btn_FFloadExp.setToolTip("(Ctrl+L)")
		# CA tab
		self.tabWidget.setCurrentWidget(self.tabCatAnalysis)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Catalog Analysis</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Provides an interface that links to a number of routines for analyzing a
				CALPGM/SPFIT/SPCAT project and provide summaries of various properties that are not
				necessarily apparent from the input/output files.<br/>
				<br/>
				*note* One may load a single input/output file from a project, but the other files
				have the same naming (i.e. just as calpgm expects: foo.cat, foo.par, foo.fit, etc...).
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- partition function vs temperature reports/plots<br/>
				- quick overview of important properties/constants, missing files
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Ctrl+B - Launch a simple web browser to load the CasDataManagement website<br/>
				Ctrl+PgDwn / Ctrl+Tab - Next tab<br/>
				Ctrl+PgUp / Ctrl+Shift+Tab - Previous tab<br/>
				Ctrl+T / Ctrl+Shift+T - Run runtest() or runtest2()<br/>
				Escape or Shift+Esc - Exit the GUI (shift skips the confirmation prompt)<br/>
				Ctrl+L - Load input files
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts:</span><br/>
				None so far..
			</p>
			</body></html>
			""")
		self.btn_CAloadFiles.setToolTip(
			"Load files from a SPFIT/SPCAT project. (Ctrl+L)")
		self.btn_CArepQ.setToolTip(
			"Activates a report about the catalog's partition function."
			"\nPRO TIP: hold the following while clicking to consider wavenumbers:"
			"\n\tSHIFT: load a wavenumber-based file to wavenumbers"
			"\n\tSHIFT+CTRL: fix the loading of a wavenumber-based file")
		# main
		self.btn_browseCASData.setToolTip(
			"Launches a simple web browser to browse the CasDataManagement website,"
			"\nwhich allows you to browse/search/filter spectral data and also even"
			"\nplot them directly to the tabs. (Ctrl+B)")
		self.btn_test.setToolTip(
			"Simply runs one of the test routines runTest() or runTest2(). They are"
			"\nused purely for development/debugging. (Ctrl+T or Ctrl+Shift+T)")
		self.btn_console.setToolTip(
			"Loads a console that provides a direct interface to"
			"\nthe underlying python instance, and pushes the GUI"
			"\ninto the namespace for direct access to all its"
			"\nelements.")
		self.btn_quit.setToolTip("(Escape or Shift+Esc)")
		# reset initial tab
		self.tabWidget.setCurrentIndex(0)

		# keyboard shortcuts
		self.shortcutCtrlB = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+B"), self, self.launchCASBrowser)
		self.shortcutCtrlL = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self, self.keyboardCtrlL)
		self.shortcutCtrlC = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+C"), self, self.keyboardCtrlC)
		self.shortcutCtrlV = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+V"), self, self.keyboardCtrlV)
		self.shortcutCtrlR = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, self.keyboardCtrlR)
		self.shortcutCtrlZ = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, self.keyboardCtrlZ)
		self.shortcutCtrlT = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+T"), self, self.runTest)
		self.shortcutCtrlShiftT = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+T"), self, self.runTest2)
		self.shortcutCtrlPcv = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+P"), self.tabCatalogViewer, partial(self.launchPlotDesigner, tab="cv"))
		self.shortcutDeleteCVplot = QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.CVplotFigure, partial(self.keyboardDelete, target="CVplot"))
		self.shortcutF5 = QtGui.QShortcut(QtGui.QKeySequence("F5"), self, self.keyboardF5)
		self.shortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, partial(self.exit, confirm=True))
		self.shortcutQuitHard = QtGui.QShortcut(QtGui.QKeySequence("Shift+Esc"), self, partial(self.exit, confirm=False))
		# switch tabs
		self.keyShortcutCtrlPgUp = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+PgUp"), self, self.prevTab)
		self.keyShortcutCtrlPgDown = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+PgDown"), self, self.nextTab)
		self.keyShortcutCtrlTab = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Tab"), self, self.nextTab)
		self.keyShortcutCtrlShiftTab = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Tab"), self, self.prevTab)
		# tab specific
		self.keyShortcutFFUpdate = QtGui.QShortcut(QtGui.QKeySequence("Return"), self.frame_FFconstants, self.FFupdate)

		# init instance containers/lists
		self.tmpDir = self.initTmpDir()
		self.sshtunnel = None
		self.defaultLoadSettings = {
			"filetype": None,
			"appendData": False,
			"skipFirst": False,
			"unit": "MHz",
			"scanIndex": 0,
			"delimiter": None,
			"xcol": 0,
			"ycol": 1,
			"xstart": None,
			"xstep": None,
			"fidStart": None,
			"fidStop": None,
			"fidLO": None,
			"fftType": None,
			"fftSideband": None,
			"mass": None,
			"preprocess": None,
			"filenames" : None}
		self.CVcatalogs = []
		self.CVexpSpectra = []
		self.CVdefaultSettings = {
			"scale": 1,
			"temp": 300,
			"lw": 0.3,
			"step": 0.01,
			"hidden": False,
			"color": None,
			"highlightobs": False,
			"showunc": False}
		self.CVcatSettings = []
		self.CVexpSettings = []
		self.CVexpHeaderWindows = []
		self.ESplotData = {"x":[], "y":[]}
		self.ESplotLabels = []
		self.ESplotBoxes = []
		self.BRplotTopData = {"x":[], "y":[], "spec":[]}
		self.BRplotBottomData = {"x":[], "y":[]}
		self.BRplotBoxes = []
		self.BRplotLines = []
		self.BRplotBottomLabels = []
		self.BRplotBottomRegions = []
		self.BRplotFitWindows = []
		self.BRexpHeaderWindows = []
		self.BRplotLineStart = 0
		self.LAexpData = {"x":[], "y":[]}
		self.LAplotCursor = None
		self.LAplotBox = None
		self.LAplotWindow = None
		self.LAsticks = ""
		self.FFfiles = [None, None, None]
		self.FFconstants = []
		self.FFcats = [None, None]
		self.FFsettings = {
			"colorCat": 'b',
			"colorExp": 'g'}
		self.FFsticks = ""
		self.FFexpData = {"x":[], "y":[]}
		self.CAbaseFilename = None

		# init plots
		self.labelStyle = {'color':'#FFF', 'font-size':'16pt'}
		self.tickFont = QtGui.QFont()
		self.tickFont.setPixelSize(16)
		self.CVinitPlot()
		self.ESinitPlot()
		self.BRinitPlotTop()
		self.BRinitPlotBottom()
		self.LAinitPlot()
		self.FFinitPlot()

		### signals
		# CV tab
		self.cb_CVsimIdx.valueChanged.connect(self.CVupdateSimSettings)
		self.txt_CVsimScale.textEdited.connect(self.CVsaveSimSettings)
		self.txt_CVtemperature.textEdited.connect(self.CVsaveSimSettings)
		self.check_CVsimHidden.clicked.connect(self.CVsaveSimSettings)
		self.check_CVsimHighlightObs.clicked.connect(self.CVsaveSimSettings)
		self.check_CVsimShowUnc.clicked.connect(self.CVsaveSimSettings)
		self.check_CVexpHidden.clicked.connect(self.CVsaveExpSettings)
		self.txt_CVsimLW.textEdited.connect(self.CVupdatePlot)
		self.txt_CVsimStep.textEdited.connect(self.CVupdatePlot)
		self.cb_CVexpIdx.valueChanged.connect(self.CVupdateExpSettings)
		# BR tab
		self.check_BRdebaseline.stateChanged.connect(self.BRupdateBottomPlot)
		self.cb_BRlowpassOrd.valueChanged.connect(self.BRupdateBottomPlot)
		self.txt_BRlowpassRolloff.textChanged.connect(self.BRupdateBottomPlot)
		self.cb_BRgaussWin.valueChanged.connect(self.BRupdateBottomPlot)
		self.cb_BRgaussSig.valueChanged.connect(self.BRupdateBottomPlot)
		self.cb_BRderivative.valueChanged.connect(self.BRupdateBottomPlot)
		self.cb_BRwienerWin.valueChanged.connect(self.BRupdateBottomPlot)
		self.cb_BRsgWin.valueChanged.connect(self.BRupdateBottomPlot)
		self.cb_BRsgOrder.valueChanged.connect(self.BRupdateBottomPlot)
		self.check_BRlockFreqRange.stateChanged.connect(self.BRtoggleFreqLock)
		self.check_BRlockFreqRange.setChecked(True)
		# LA tab
		self.txt_LAcatScale.textChanged.connect(self.LAupdateSim)
		self.txt_LAcatTemp.textChanged.connect(self.LAupdateSim)
		## FF tab
		self.check_FFuncForStepsize.stateChanged.connect(self.FFupdateStepSizes)

		### drag/drop event handling
		for CVitemForDragIn in (
				self.btn_CVloadCatalog,
				self.btn_CVloadExp,
				self.CVplotFigure,
				self.CVplotFigure.plotItem.vb
			):
			CVitemForDragIn.setAcceptDrops(True)
			CVitemForDragIn.dragEnterEvent = self.checkForURLmime
			CVitemForDragIn.dropEvent = self.CVdragInFile
		
		### load configuration file if it exists
		conffile = os.environ.get("QTFITCONF")
		if conffile:
			try:
				self.CVloadSession(filename=conffile)
			except:
				log.exception("tried loading QTFITCONF=%s but received an error: %s" % (conffile, sys.exc_info()[1]))


	### keyboard shortcuts
	def keyboardCtrlL(self):
		"""
		Performs all the desired tasks associated with the Ctrl+L keyboard
		shortcut.
		"""
		currentTabText = self.tabWidget.tabText(self.tabWidget.currentIndex())
		if currentTabText == "&Catalog Viewer":
			self.CVloadExp()
		elif currentTabText == "Easy &Stats":
			self.ESloadScan()
		elif currentTabText == "&Baseline Removal":
			self.BRloadScan()
		elif currentTabText == "&Fit Fidget":
			self.FFloadFiles()
	def keyboardCtrlC(self):
		"""
		Performs all the desired tasks associated with the Ctrl+C keyboard
		shortcut.
		"""
		currentTabText = self.tabWidget.tabText(self.tabWidget.currentIndex())
		if currentTabText == "Easy &Stats":
			self.EScopyScan()
		elif currentTabText == "&Baseline Removal":
			self.BRcopyScan()
	def keyboardCtrlV(self):
		"""
		Performs all the desired tasks associated with the Ctrl+V keyboard
		shortcut.
		"""
		currentTabText = self.tabWidget.tabText(self.tabWidget.currentIndex())
		if currentTabText == "&Catalog Viewer":
			self.CVpasteExp()
		elif currentTabText == "Easy &Stats":
			self.ESpasteScan()
		elif currentTabText == "&Baseline Removal":
			self.BRpasteScan()
		elif currentTabText == "&Line Assignments":
			self.LApasteExp()
		elif currentTabText == "&Fit Fidget":
			self.FFpasteExp()
	def keyboardCtrlR(self):
		"""
		Performs all the desired tasks associated with the Ctrl+R keyboard
		shortcut.
		"""
		currentTabText = self.tabWidget.tabText(self.tabWidget.currentIndex())
		if currentTabText == "&Catalog Viewer":
			self.CVupdatePlot()
		elif currentTabText == "&Baseline Removal":
			self.BRupdateBottomPlot()
		elif currentTabText == "&Fit Fidget":
			self.FFreset()
	def keyboardF5(self):
		"""
		Equivalent to the Ctrl+R keyboard shortcut (i.e. refresh).
		"""
		currentTabText = self.tabWidget.tabText(self.tabWidget.currentIndex())
		if currentTabText == "&Fit Fidget":
			self.FFupdate()
		else:
			self.keyboardCtrlR()
	def keyboardCtrlZ(self):
		"""
		Performs all the desired tasks associated with the Ctrl+Z keyboard
		shortcut.
		"""
		currentTabText = self.tabWidget.tabText(self.tabWidget.currentIndex())
		if currentTabText == "&Catalog Viewer":
			self.CVclearPlotLabels(onlyLastOne=True)
	def keyboardDelete(self, target=None):
		"""
		Performs all the desired tasks associated with the Ctrl+Z keyboard
		shortcut.
		"""
		if target is None:
			return
		elif target == "CVplot":
			lastHoverEvent = self.CVplotFigure.plotItem.scene().lastHoverEvent
			viewBox = self.CVplotFigure.plotItem.getViewBox()
			mouseCoord = viewBox.mapSceneToView(lastHoverEvent.scenePos())
			viewrange = viewBox.state['viewRange']
			viewrange = QtCore.QRectF(
				QtCore.QPoint(float(viewrange[0][0]), float(viewrange[1][1])), # top left
				QtCore.QPoint(float(viewrange[0][1]), float(viewrange[1][0]))) # bottom right
			isonplot = viewrange.contains(mouseCoord)
			# walk through the labels and check this coordinate
			for idx,label in enumerate(self.CVplotLabels):
				if isinstance(label, (tuple, list)):
					toDel = False
					for l in label:
						if l.sceneBoundingRect().contains(lastHoverEvent.scenePos()):
							toDel = True
					if toDel:
						self.CVplotFigure.removeItem(label[0])
						self.CVplotFigure.removeItem(label[1])
						del self.CVplotLabels[idx]
				elif label.sceneBoundingRect().contains(lastHoverEvent.scenePos()):
					self.CVplotFigure.removeItem(label)
					del self.CVplotLabels[idx]
					# note: doesn't delete the dot if from a session


	### tab control
	def nextTab(self):
		"""
		Switches to the tab on the right.
		"""
		currentTabIndex = self.tabWidget.currentIndex()
		finalIndex = self.tabWidget.count() - 1
		if currentTabIndex == finalIndex:
			self.tabWidget.setCurrentIndex(0)
		else:
			self.tabWidget.setCurrentIndex(currentTabIndex+1)
	def prevTab(self):
		"""
		Switches to the tab on the left.
		"""
		currentTabIndex = self.tabWidget.currentIndex()
		finalIndex = self.tabWidget.count() - 1
		if currentTabIndex == 0:
			self.tabWidget.setCurrentIndex(finalIndex)
		else:
			self.tabWidget.setCurrentIndex(currentTabIndex-1)


	### CV tab
	def CVinitPlot(self):
		"""
		Initializes the plot for viewing catalogs.
		"""
		pg.setConfigOptions(antialias=True)
		# figure properties
		self.CVplotFigure.setLabel('left', "Intensity", units='V', **self.labelStyle)
		self.CVplotFigure.setLabel('bottom', "Frequency", units='Hz', **self.labelStyle)
		self.CVplotFigure.getAxis('bottom').setScale(scale=1e6)
		self.CVplotFigure.getAxis('left').tickFont = self.tickFont
		self.CVplotFigure.getAxis('bottom').tickFont = self.tickFont
		self.CVplotFigure.getAxis('bottom').setStyle(**{'tickTextOffset':5})
		#self.CVplotLegend = self.CVplotFigure.addLegend() # until the normal pg.LegendItem stops growing in width..
		self.CVplotLegend = Widgets.LegendItem(offset=(30, 30))
		self.CVplotFigure.getPlotItem().legend = self.CVplotLegend
		self.CVplotLegend.setParentItem(self.CVplotFigure.getPlotItem().vb)
		# plots
		self.CVplotSim = self.CVplotFigure.plot(
			name='sim', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.CVplotSim.setPen('w')
		self.CVplotLegend.removeItem(self.CVplotSim.name())
		self.CVplotExpMath = self.CVplotFigure.plot(
			name='exp math', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.CVplotExpMath.setPen('w')
		self.CVplotLegend.removeItem(self.CVplotExpMath.name())
		# containers for catalog and experimental plots
		self.CVplotsCat, self.CVplotsExp = [], []
		self.CVplotLabels = []
		# signals for interacting with the mouse
		self.CVplotMouseLabel = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
		self.CVplotMouseLabel.setZValue(999)
		self.CVplotFigure.addItem(self.CVplotMouseLabel, ignoreBounds=True)
		self.CVplotMouseMoveSignal = pg.SignalProxy(
			self.CVplotFigure.plotItem.scene().sigMouseMoved,
			rateLimit=15,
			slot=self.CVplotMousePosition)
		self.CVplotMouseClickSignal = pg.SignalProxy(
			self.CVplotFigure.plotItem.scene().sigMouseClicked,
			rateLimit=5,
			slot=self.CVplotMouseClicked)
	def CVresetPlotLegend(self):
		"""
		Resets the Legend size, position, and contents.
		"""
		self.CVplotLegend.scene().removeItem(self.CVplotLegend)
		self.CVplotLegend = Widgets.LegendItem(offset=(30, 30))
		self.CVplotLegend.setParentItem(self.CVplotFigure.getPlotItem().vb)
		#self.CVplotLegend.addItem(self.CVplotSim, self.CVplotSim.name())
		#self.CVplotLegend.addItem(self.CVplotExpMath, self.CVplotExpMath.name())
		for i,p in enumerate(self.CVplotsCat):
			self.CVplotLegend.addItem(self.CVplotsCat[i], self.CVplotsCat[i].name())
		for i,p in enumerate(self.CVplotsExp):
			self.CVplotLegend.addItem(self.CVplotsExp[i], self.CVplotsExp[i].name())
	def CVclearPlotLabels(self, onlyLastOne=False):
		"""
		Clears labels added to the plot.

		:param onlyLastOne: (optional) whether to only remove the previously-added label (i.e. undo)
		:type onlyLastOne: bool
		"""
		if onlyLastOne:
			self.CVplotFigure.removeItem(self.CVplotLabels[-1][0])
			self.CVplotFigure.removeItem(self.CVplotLabels[-1][1])
			self.CVplotLabels = self.CVplotLabels[:-1]
		else:
			for label in self.CVplotLabels:
				if isinstance(label, (list, tuple)):
					for l in label:
						self.CVplotFigure.removeItem(l)
				else:
					self.CVplotFigure.removeItem(label)
			self.CVplotLabels = []
	def CVprevPlotView(self):
		"""
		Returns to the previous plot zoom/range.
		"""
		self.CVplotFigure.getViewBox().scaleHistory(-1)

	def CVplotMousePosition(self, mouseEvent):
		"""
		Processes the signal when the mouse is moving above the plot area.

		Note that this signal is active always, so only light processing
		should be done here, and only under appropriate conditions should
		additional routines should be called.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(PyQt4.QtCore.QPointF, None)
		"""
		# process keyboard modifiers and perform appropriate action
		modifier = QtGui.QApplication.keyboardModifiers()
		if modifier == QtCore.Qt.ShiftModifier:
			# convert mouse coordinates to XY wrt the plot
			mousePos = self.CVplotFigure.plotItem.getViewBox().mapSceneToView(mouseEvent[0])
			mouseX, mouseY = mousePos.x(), mousePos.y()
			if not len(self.CVplotsCat) and not len(self.CVexpSpectra):
				self.CVplotMouseLabel.setPos(mouseX, mouseY)
				self.CVplotMouseLabel.setText(" \n%.3f\n%g" % (mouseX,mouseY))
			elif len(self.CVplotsCat):
				HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'><span style='color:green'>cat: %s</span>"
				HTMLCoordinates += "<br>f=%s<br>unc: %s<br>lgint: %.3f<br>qns: <tt>%s</tt></span></div>"
				nearest = []
				for i,p in enumerate(self.CVplotsCat):
					if self.CVcatSettings[i]['hidden']: continue
					idx = np.abs(p.opts.get('x') - mouseX).argmin()
					distance = mouseX - p.opts.get('x')[idx]
					nearest.append((distance, i, idx))
				nearestIdx = np.abs([i[0] for i in nearest]).argmin()
				name = self.CVplotsCat[nearest[nearestIdx][1]].name()
				freq = self.CVplotsCat[nearest[nearestIdx][1]].opts.get('x')[nearest[nearestIdx][2]]
				tIdx = self.CVcatalogs[nearest[nearestIdx][1]].get_idx_from_freq(freq)
				unc = self.CVcatalogs[nearest[nearestIdx][1]].transitions[tIdx].calc_unc
				# qns = self.CVcatalogs[nearest[nearestIdx][1]].transitions[tIdx].qn_str
				# qns_lo = "%s %s %s %s %s %s" % (qns[:2], qns[2:4], qns[4:6], qns[6:8], qns[8:10], qns[10:12])
				# qns_hi = "%s %s %s %s %s %s" % (qns[12:14], qns[14:16], qns[16:18], qns[18:20], qns[20:22], qns[22:24])
				qntag = self.CVcatalogs[nearest[nearestIdx][1]].transitions[tIdx].qntag
				qn_str = self.CVcatalogs[nearest[nearestIdx][1]].transitions[tIdx].qn_str
				qnps = int(str(qntag)[-1])    # number per state
				qns_lo, qns_hi = "", ""
				for i in range(qnps):
					qns_lo += " %s" % (qn_str[2*i:2*i+2],)
					qns_hi += " %s" % (qn_str[len(qn_str)//2:][2*i:2*i+2],)
				qns_full = qns_lo.strip() + " &#8592; " + qns_hi.strip()
				lgint = np.log10(self.CVcatalogs[nearest[nearestIdx][1]].transitions[tIdx].intensity)
				self.CVplotMouseLabel.setPos(freq, mouseY)
				self.CVplotMouseLabel.setHtml(HTMLCoordinates % (name,freq,unc,lgint,qns_full))
			else:
				HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'><span style='color:green'>spec: %s</span>"
				HTMLCoordinates += "<br>x=%s<br>y: %.3f<br>point #%g</span></div>"
				nearest = []
				for i,s in enumerate(self.CVexpSpectra):
					if self.CVexpSettings[i]['hidden']: continue
					if mouseX < s['x'][0] or mouseX > s['x'][-1]:
						continue
					idx = np.abs(s['x'] - mouseX).argmin()
					distance = mouseY - s['y'][idx]
					nearest.append((distance, i, idx))
				if not nearest:
					self.CVplotMouseLabel.setPos(0,0)
					self.CVplotMouseLabel.setText("")
					return
				nearestIdx = np.abs([i[0] for i in nearest]).argmin()
				datapointIdx = nearest[nearestIdx][2]
				name = self.CVplotsExp[nearest[nearestIdx][1]].name()
				x = self.CVexpSpectra[nearest[nearestIdx][1]]['x'][datapointIdx]
				y = self.CVexpSpectra[nearest[nearestIdx][1]]['y'][datapointIdx]
				self.CVplotMouseLabel.setPos(x, y)
				self.CVplotMouseLabel.setHtml(HTMLCoordinates % (name,x,y,datapointIdx+1))
		elif modifier == QtCore.Qt.ControlModifier:
			mousePos = self.CVplotFigure.plotItem.getViewBox().mapSceneToView(mouseEvent[0])
			mouseX, mouseY = mousePos.x(), mousePos.y()
			self.CVplotMouseLabel.setPos(mouseX, mouseY)
			self.CVplotMouseLabel.setText(" \n%.3f\n%g" % (mouseX,mouseY))
		else:
			self.CVplotMouseLabel.setPos(0,0)
			self.CVplotMouseLabel.setText("")
	def CVplotMouseClicked(self, mouseEvent):
		"""
		Processes the signal when the mouse is clicked within the plot.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent, None)
		"""
		# convert mouse coordinates to XY wrt the plot
		screenPos = mouseEvent[0].screenPos()
		mousePos = mouseEvent[0].scenePos()
		viewBox = self.CVplotFigure.plotItem.getViewBox()
		mousePos = viewBox.mapSceneToView(mousePos)
		mousePos = (mousePos.x(), mousePos.y())
		modifier = QtGui.QApplication.keyboardModifiers()
		# if right-mouse button, adds menu for copying plots
		if mouseEvent[0].button() == QtCore.Qt.RightButton:
			items = self.CVplotFigure.sceneObj.items(mouseEvent[0].scenePos())
			removemenu = QtGui.QMenu()
			removemenu.setTitle("remove from plot..")
			copymenu = QtGui.QMenu()
			copymenu.setTitle("copy to clipboard..")
			othermenu = QtGui.QMenu()
			othermenu.setTitle("other actions..")
			self.CVmenus = [removemenu, copymenu, othermenu]
			for idx_cat,cat in enumerate(self.CVplotsCat):
				if cat in items:
					remove = removemenu.addAction("%s" % cat.name())
					remove.triggered.connect(partial(self.CVremoveExp, idx=int(idx_cat+1)))
					copy = copymenu.addAction("%s" % cat.name())
					copy.triggered.connect(cat.copy)
					othermenu.addMenu(cat.getContextMenu())
			for idx_exp,exp in enumerate(self.CVplotsExp):
				if ((exp in items) or
					(("curve" in dir(exp)) and (exp.curve in items))):
					remove = removemenu.addAction("%s" % exp.name())
					remove.triggered.connect(partial(self.CVremoveExp, idx=int(idx_exp+1)))
					copy = copymenu.addAction("%s" % exp.name())
					copy.triggered.connect(exp.copy)
					othermenu.addMenu(exp.getContextMenu())
			self.CVplotFigure.plotItem.getViewBox().menu.addMenu(removemenu)
			self.CVplotFigure.plotItem.getViewBox().menu.addMenu(copymenu)
			self.CVplotFigure.plotItem.getViewBox().menu.addMenu(othermenu)
		# update mouse label if SHIFT
		if modifier == QtCore.Qt.ShiftModifier:
			labelDot = pg.TextItem(text="*",anchor=(0.5,0.5))
			labelDot.html = None
			labelDot.setPos(self.CVplotMouseLabel.pos())
			labelDot.setZValue(999)
			self.CVplotFigure.addItem(labelDot, ignoreBounds=True)
			labelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
			labelText.setPos(self.CVplotMouseLabel.pos())
			html = unicode(self.CVplotMouseLabel.textItem.toHtml())
			labelText.html = html
			labelText.setHtml(html)
			labelText.setZValue(999)
			self.CVplotFigure.addItem(labelText, ignoreBounds=True)
			self.CVplotLabels.append((labelDot,labelText))
		# update mouse label if CONTROL
		elif modifier == QtCore.Qt.ControlModifier:
			HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 13pt'>x=%.3f"
			HTMLCoordinates += "<br>y=%0.2e</span></div>"
			labelDot = pg.TextItem(text="*",anchor=(0.5,0.5))
			labelDot.html = None
			labelDot.setPos(mousePos[0], mousePos[1])
			labelDot.setZValue(999)
			self.CVplotFigure.addItem(labelDot, ignoreBounds=True)
			labelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
			labelText.setPos(mousePos[0], mousePos[1])
			html = HTMLCoordinates % (mousePos[0], mousePos[1])
			labelText.html = html
			labelText.setHtml(html)
			labelText.setZValue(999)
			self.CVplotFigure.addItem(labelText, ignoreBounds=True)
			self.CVplotLabels.append((labelDot,labelText))

	def CVdragInFile(self, inputEvent=None):
		urls = inputEvent.mimeData().urls()
		filenames = [u.toLocalFile() for u in urls]
		catFiles = []
		expFiles = []
		for f in filenames:
			if os.path.splitext(f)[1][1:].lower() in ("cat", "mrg"):
				catFiles.append(f)
			else:
				expFiles.append(f)
		if len(catFiles):
			self.CVloadCatalog(catalogs=catFiles)
		if len(expFiles):
			self.CVloadExp(filenames=expFiles)

	def CVloadCatalog(self, mouseEvent=False,
		catalogs=None, scale=None, temp=None,
		unit="MHz", tunit=None):
		"""
		Loads a catalog file into memory.

		:param mouseEvent: (optional) the mouse event from a click
		:param catalogs: (optional) a list of catalogs to load, bypassing the selection dialog
		:param scale: (optional) a factor to use to immediately rescale the intensities
		:param temp: (optional) a temperature to use to immediately rescale the intensities
		:param unit: (optional) the unit used in the catalog (default: MHz)
		:param tunit: (optional) the preferred unit for plotting the catalog
		:type mouseEvent: QtGui.QMouseEvent
		:type catalogs: list
		:type scale: float
		:type temp: float
		:type unit: str
		:type tunit: str
		"""
		kbmods = QtGui.QApplication.keyboardModifiers()
		if kbmods == QtCore.Qt.ShiftModifier:
			unit = "wvn"
		elif kbmods == (QtCore.Qt.ShiftModifier | QtCore.Qt.ControlModifier):
			unit = "wvn"
			tunit = "wvn"
		# request/process the input file(s)
		if catalogs and (not isinstance(catalogs, list)):
			catalogs = [catalogs]
		elif not catalogs:
			catalogs = []
		if isinstance(catalogs, list) and (len(catalogs) == 0):
			directory = self.cwd
			if self.CVcatalogs:
				directory = os.path.realpath(os.path.dirname(self.CVcatalogs[-1].filename))
			# open file
			files = QtGui.QFileDialog.getOpenFileNames(directory=directory)
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				files = files[0]
			for f in files:
				catalogs.append(str(f))
		if not any([os.path.isfile(f) for f in catalogs]):
			raise UserWarning("could not locate one of the requested input files!")
		self.cwd = os.path.realpath(os.path.dirname(catalogs[-1]))
		# make note of something to do later..
		toSetFreqLimits = False
		if not len(self.CVcatalogs) and not len(self.CVexpSpectra):
			toSetFreqLimits = True
		if ((unit == "wvn" or tunit == "wvn") and
			not len(self.CVcatalogs) and not len(self.CVexpSpectra)):
			self.CVplotFigure.setLabel('bottom', units="cm-1")
			self.CVplotFigure.getPlotItem().vb.invertX(True)
			self.CVplotFigure.getAxis('bottom').setScale(scale=1)
		elif ((unit == "MHz" and tunit is None) and
			(len(self.CVcatalogs) or len(self.CVexpSpectra)) and
			self.CVplotFigure.getAxis('bottom').labelUnits == "cm-1"):
			unit = "wvn"
		else:
			self.CVplotFigure.setLabel('bottom', units="Hz")
			self.CVplotFigure.getPlotItem().vb.invertX(False)
			self.CVplotFigure.getAxis('bottom').setScale(scale=1e6)
		# loop across files
		for icat,catFile in enumerate(catalogs):
			# load using Catalog.catalog.Predictions()
			log.debug("loading catFile=%s in freq.units=%s" % (catFile, unit))
			self.CVcatalogs.append(catalog.load_predictions(filename=catFile, unit=unit, tunit=tunit))
			self.CVcatalogs[-1].filename = catFile
			# update GUI contents
			self.CVcatSettings.append(dict(self.CVdefaultSettings))
			newMaxCatIdx = self.cb_CVplotIdxCatalog.maximum() + 1
			self.cb_CVplotIdxCatalog.setMaximum(newMaxCatIdx)
			self.cb_CVsimIdx.setMaximum(newMaxCatIdx)
			self.cb_CVplotIdxCatalog.setValue(newMaxCatIdx)
			self.cb_CVsimIdx.setValue(newMaxCatIdx)
			name = os.path.split(catFile)[-1]
			# add to plot and update
			self.CVplotsCat.append(Widgets.StickPlot(x=[], height=[], name=name)) # use the line below, if JCL's contributions to pg are available
			#self.CVplotsCat.append(pg.StickPlotItem(x=[], height=[], name=name))
			newColor = pg.mkColor("#%06x" % random.randint(0, 0xFFFFFF))
			hsv = newColor.getHsv()
			newColor.setHsv(hsv[0], hsv[1], 255)
			self.CVcatSettings[-1]["color"] = miscfunctions.qcolorToRGBA(newColor)
			self.CVplotsCat[-1].opts['pen'] = pg.mkPen(self.CVcatSettings[-1]["color"])
			self.CVplotFigure.addItem(self.CVplotsCat[-1])
			self.CVplotLegend.addItem(self.CVplotsCat[-1], self.CVplotsCat[-1].name())
			# if first index, set the view range
			if toSetFreqLimits:
				self.CVplotFigure.getViewBox().setXRange(
					self.CVcatalogs[-1].get_freq_range()[0],
					self.CVcatalogs[-1].get_freq_range()[1],
					padding=0)
			# update the tooltips for the indices
			ttip = "idx - name"
			for i,catPlot in enumerate(self.CVplotsCat):
				ttip += "\n%s - %s" % ((i+1),catPlot.name())
			self.cb_CVplotIdxCatalog.setToolTip(ttip)
			self.cb_CVsimIdx.setToolTip(ttip)
			# update intensity and temperature if appropriate
			if scale is not None:
				if isinstance(scale, (list, tuple)):
					self.CVcatSettings[-1]["scale"] = scale[icat]
				else:
					self.CVcatSettings[-1]["scale"] = scale
			if temp is not None:
				if isinstance(temp, (list, tuple)):
					self.CVcatSettings[-1]["temp"] = temp[icat]
				else:
					self.CVcatSettings[-1]["temp"] = temp
			self.CVcatSettings[-1]["unit"] = unit
			self.CVcatSettings[-1]["tunit"] = tunit
		self.CVupdatePlot()
	def CVremoveCatalog(self):
		"""
		Removes a catalog from the plot and memory.
		"""
		# process the catalog index
		catIdx = self.cb_CVplotIdxCatalog.value()
		if not catIdx:
			return
		# remove the plots
		catIdx -= 1 # to easily account for 0-indexing
		self.CVplotLegend.removeItem(self.CVplotsCat[catIdx].name())
		self.CVplotFigure.removeItem(self.CVplotsCat[catIdx])
		del self.CVcatalogs[catIdx]
		del self.CVcatSettings[catIdx]
		del self.CVplotsCat[catIdx]
		# update the GUI contents
		self.cb_CVplotIdxCatalog.setMaximum(self.cb_CVplotIdxCatalog.maximum() - 1)
		self.cb_CVsimIdx.setMaximum(self.cb_CVsimIdx.maximum() - 1)
		# update the tooltips for the indices
		ttip = "idx - name"
		for i,catPlot in enumerate(self.CVplotsCat):
			ttip += "\n%s - %s" % ((i+1),catPlot.name())
		self.cb_CVplotIdxCatalog.setToolTip(ttip)
		self.cb_CVsimIdx.setToolTip(ttip)
		self.CVupdatePlot()

	def CVbrowseVAMDC(self):
		"""
		Loads a list in a new window, enabling one to select a line
		catalog from the CDMS or JPL spectroscopy databases.
		"""
		reload(Dialogs)
		if not 'vamdcSpecies' in vars(self):
			vamdcSpecies = self.getVAMDCSpeciesList()
			if vamdcSpecies is not None:
				self.vamdcSpecies = vamdcSpecies
			else:
				return
		self.VAMDCbrowser = Dialogs.VAMDCSpeciesBrowser(self.vamdcSpecies, parent=self)
		if not self.VAMDCbrowser.exec_():
			return
		else:
			selection = self.VAMDCbrowser.getModel()
		if not len(selection):
			return
		catalogs = []
		URLs = []
		for molecule in selection:
			log.info("will add the following catalog from the VAMDC: '%s'" % molecule.Comment)
			filename = "%s (VAMDC).cat" % molecule.OrdinaryStructuralFormula
			filename = os.path.join(self.tmpDir, filename)
			fh = open(filename, 'wb')
			try:
				speciesurl = self.url_vamdccat % molecule.SpeciesID.split('-')[1] # standard: using a URL request
				log.debug("trying a request from: %s" % speciesurl)
				r = requests.get(speciesurl, allow_redirects=True, timeout=5)
				r.raise_for_status()
				for chunk in r.iter_content(1024):
					fh.write(chunk)
				fh.close()
			except:
				if not fh.closed:
					fh.close()
				### temporary fix, while https://www.astro.uni-koeln.de suffers from a webserver problem
				tag = molecule.Comment[:6].replace(' ', '0')
				if tag[-3] == "5":
					speciesurl = self.url_cdmscat % tag
				else:
					speciesurl = self.url_jplcat % tag
				log.debug("that didn't work, instead trying the direct URL with urllib: %s" % speciesurl)
				urlretrieve(speciesurl, filename)
			catalogs.append(filename)
			URLs.append(speciesurl)
		oldCatLength = len(self.CVcatalogs)
		# load to plot
		self.CVloadCatalog(catalogs=catalogs)
		for i in range(len(selection)):
			catIdx = oldCatLength + i
			# add URL as a new 'source' entry in the settings
			self.CVcatSettings[catIdx]['sourceURL'] = URLs[i]
			# collect partition functions at multiple temperatures, for debugging
			if self.debugging:
				t = selection[i].PartitionFunction[0].PartitionFunctionT
				print("found partition function for the followig temperatures: %s" % (t))
				myTemps = list(map(float, selection[i].PartitionFunction[0].PartitionFunctionT))
				myParts = list(map(float, selection[i].PartitionFunction[0].PartitionFunctionQ))
				mySpline = interpolate.splrep(myTemps, myParts)
				try:
					self.CVcatalogs[catIdx].generate_callable_partitionfunc() # prob not necessary if already plotted..
					log.debug("the partitions functions for '%s' are determined to be:" % self.CVplotsCat[catIdx].name())
					log.debug("\tTemp (K)  Q (vamdc)  (ratio)     Q (gen'd)   (ratio)")
					q300_vamdc = interpolate.splev(300, mySpline)
					q300_gen = self.CVcatalogs[catIdx].callable_partitionfunc(300)
					for t in [1000, 300, 150, 37.5, 9.375, 5]:
						q_vamdc = interpolate.splev(t, mySpline)
						q_gen = self.CVcatalogs[catIdx].callable_partitionfunc(t)
						log.debug("\t%5.1f     %.3e (%.1e)    %.4e (%.1e)" % (t, q_vamdc, q300_vamdc/q_vamdc, q_gen, q300_gen/q_gen))
				except Exception as e:
					log.exception("the partition function comparison failed for '%s'! (%s)" % (self.CVplotsCat[catIdx].name(), e))
			# update the partition function if so desired
			if self.useVamdcPartFxns:
				myTemps = list(map(float, selection[i].PartitionFunction[0].PartitionFunctionT))
				myParts = list(map(float, selection[i].PartitionFunction[0].PartitionFunctionQ))
				spline = interpolate.splrep(myTemps, myParts)
				def callable_partitionfunc(t):
					return interpolate.splev(t, spline)
				self.CVcatalogs[catIdx].callable_partitionfunc = callable_partitionfunc

	def CVloadExp(self, mouseEvent=False, filenames=[], settings={}):
		"""
		Loads a spectral file into memory.

		:param mouseEvent: (optional) the mouse event from a click
		:param filenames: (optional) a list of files to load, bypassing the selection dialog
		:param settings: (optional) settings to use for loading spectra
		:type mouseEvent: QtGui.QMouseEvent
		:type filenames: list
		:type settings: dict
		"""
		reload(spectrum)
		if not len(filenames):
			# provide dialog
			if not "CVloadDialog" in vars(self):
				self.CVloadDialog = Dialogs.SpecLoadDialog(self)
			if not self.CVloadDialog.exec_():
				return
			else:
				settings = self.CVloadDialog.getValues()
			# get file
			filenames = settings["filenames"]
		if not any([os.path.isfile(f) for f in filenames]):
			raise IOError("could not locate one of the requested input files!")
		self.cwd = os.path.realpath(os.path.dirname(filenames[-1]))
		# if no settings, do some guesswork..
		if settings == {}:
			settings = self.defaultLoadSettings.copy()
		if settings["filetype"] is None:
			settings["filetype"] = spectrum.guess_filetype(filename=filenames)
			log.debug("guessed the filetype(s) should be: %s" % args.filetype)
			if settings["filetype"] is None:
				raise SyntaxError("could not determine the filetype, so you should fix this..")
		# if multiple scan indices of a single file, do something special
		scanindices = []
		if (len(filenames) == 1) and isinstance(settings["scanIndex"], list):
			scanindices = settings["scanIndex"]
			fileIn = filenames[0]
			filenames = [fileIn for _ in scanindices]
		# initialize a decent colormap if plotting multiple files at once
		colormap = None
		if len(filenames) >= 3:
			palettes = ["cielab256", "coloralphabet26", "gilbertson", # misc palettes
						"nipy_spectral", "hsv", "Paired", "rainbow", # matplotlib palettes
						"thermal", "phase"] # cmocean palettes
			palette = random.sample(palettes, k=len(palettes))[0]
			log.debug("using the color palette '%s'" % palette)
			colormap = plotlib.getColormap(
				num=len(filenames)+1,
				palette=palette)
		# loop through files
		x, y, header = [], [], []
		for i,fileIn in enumerate(filenames):
			# initialize empty containers
			if not settings["appendData"]:
				x, y, header = [], [], []
			if len(scanindices):
				settings.update({"scanIndex":scanindices[i]})
			if (settings["appendData"]) and (len(filenames) > 1):
				name = "%s...%s" % (os.path.split(filenames[0])[-1], os.path.split(filenames[-1])[-1])
			else:
				name = os.path.split(fileIn)[-1]
			# load spectra to memory
			if settings["filetype"] in ["ssv", "tsv", "csv", "casac", "gesp", "ydata"]:
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					skipFirst=settings["skipFirst"])
			elif settings["filetype"]=="jpl":
				if not settings["scanIndex"]:
					settings["scanIndex"] = 1
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (#%g)" % settings["scanIndex"]
			elif settings["filetype"]=="fits":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
			elif settings["filetype"]=="arbdc":
				delimiter = settings["delimiter"]
				xcol = settings["xcol"]
				ycol = settings["ycol"]
				expspec = spectrum.load_spectrum(
					fileIn, ftype="arbdelim",
					skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
					delimiter=delimiter)
			elif settings["filetype"]=="arbs":
				raise NotImplementedError
			elif settings["filetype"]=="hidencsv":
				if settings["unit"] == "mass amu":
					settings["histogram"] = True
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"],
					unit=settings["unit"],
					mass=settings["mass"])
				if settings["scanIndex"]:
					if settings["scanIndex"] == -1:
						name += " (cycle: avg)"
					else:
						name += " (cycle: %g)" % settings["scanIndex"]
				if settings["mass"]:
					name += " (mass: %g)" % settings["mass"]
			elif settings["filetype"] == "brukeropus":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (%s)" % expspec.h['block_key']
			elif settings["filetype"] == "batopt3ds":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"])
			elif settings["filetype"]=="fid":
				pass    # works on this AFTER preprocess
			else:
				raise NotImplementedError("not sure what to do with filetype %s" % settings["filetype"])
			# do preprocessing
			if ("preprocess" in settings) and (settings["preprocess"] is not None):
				expspec.xOrig = expspec.x.copy()
				expspec.yOrig = expspec.y.copy()
				if "vlsrShift" in settings["preprocess"]:
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrShift")
					val = float(settings["preprocess"][idxP+1])
					expspec.x *= (1 + val/2.99792458e8)
				if "vlsrFix" in settings["preprocess"]:
					curVal = 0
					if settings["filetype"]=="fits":
						fitsHeader = expspec.hdu.header
						if "VELO-LSR" in fitsHeader:
							curVal = float(fitsHeader["VELO-LSR"])
						elif "VELO" in fitsHeader:
							curVal = float(fitsHeader["VELO"])
						elif "VELREF" in fitsHeader:
							curVal = float(fitsHeader["CRVAL1"])
						elif "VLSR" in fitsHeader:
							curVal = float(fitsHeader["VLSR"])*1e3
						else:
							raise Warning("couldn't find the original reference velocity in the fits header..")
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrFix")
					val = float(settings["preprocess"][idxP+1])
					if not curVal == 0.0:
						log.info("first removing the old vel_lsr: %s" % curVal)
						expspec.x *= (1 - curVal/2.99792458e8) # revert old value
					log.info("applying vel_lsr = %s" % val)
					expspec.x *= (1 + val/2.99792458e8) # apply new value
				if "shiftX" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftX")
					val = float(settings["preprocess"][idxP+1])
					log.info("applying shiftX = %s" % val)
					expspec.x += val
				if "shiftY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y += val
				if "scaleY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("scaleY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y *= val
				if "clipTopY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipTopY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, None, val)
				if "clipBotY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipBotY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, val, None)
				if "clipAbsY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipAbsY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, -val, val)
				if "wienerY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("wienerY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y -= Filters.get_wiener(expspec.y, val)
				if "medfiltY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("medfiltY")
					val = int(settings["preprocess"][idxP+1])
					expspec.y = scipy.signal.medfilt(expspec.y, val)
				if "ffbutterY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("ffbutterY")
					ford = int(settings["preprocess"][idxP+1])
					ffreq = float(settings["preprocess"][idxP+2])
					b, a = scipy.signal.butter(ford, ffreq, btype='low', analog=False, output='ba')
					expspec.y = scipy.signal.filtfilt(b, a, expspec.y, padlen=20)
			if settings["filetype"]=="fid":
				reload(spectrum)
				if len(settings["delimiter"]):
					xcol, ycol = (1,2)
					if settings["xcol"]:
						xcol = settings["xcol"]
					if settings["ycol"]:
						ycol = settings["ycol"]
					log.info(xcol, ycol)
					delimiter = settings["delimiter"]
					fidxy = spectrum.load_spectrum(
						fileIn, ftype="arbdelim",
						skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
						delimiter=delimiter)
				else:
					log.warning("you did not specify a delimiter, so this assumes they are spaces")
					fidxy = spectrum.load_spectrum(fileIn, ftype="xydata")
				fidspec = spectrum.TimeDomainSpectrum(fidxy.x, fidxy.y)
				fidspec.calc_amplitude_spec(
					window_function=settings["fftType"],
					time_start=float(settings["fidStart"]),
					time_stop=float(settings["fidStop"]))
				expspec = spectrum.Spectrum(x=fidspec.u_spec_win_x, y=fidspec.u_spec_win_y)
				expspec.if_x = expspec.x.copy()
				expspec.rest_x =  expspec.if_x.copy() + float(settings["fidLO"])*1e9
				expspec.image_x = -1*expspec.if_x.copy() + float(settings["fidLO"])*1e9
				if settings["fftSideband"] == "upper":
					expspec.x = expspec.rest_x
				elif settings["fftSideband"] == "lower":
					expspec.x = expspec.image_x
				elif settings["fftSideband"] == "both":
					expspec.x = np.asarray(expspec.image_x.tolist() + expspec.rest_x.tolist())
					expspec.y = np.asarray(expspec.y.tolist() + expspec.y.tolist())
				expspec.x /= 1e6
			# work on unit conversion and plot label fixes
			if settings["unit"] == "GHz":
				expspec.x *= 1e3
			elif settings["unit"] == "THz":
				expspec.x *= 1e6
			elif not settings["unit"] == "MHz":
				if not len(self.CVcatalogs) and not len(self.CVexpSpectra): # update the plot label
					self.CVplotFigure.getAxis('bottom').setScale(scale=1)
					if settings["unit"] == "cm-1":
						self.CVplotFigure.setLabel('bottom', "Wavenumber", units=settings["unit"])
						self.CVplotFigure.getPlotItem().vb.invertX(True)
					elif settings["unit"] in ["s","ms"]:
						self.CVplotFigure.setLabel('bottom', "Time", units=settings["unit"][-1])
					elif settings["unit"] == "mass amu":
						self.CVplotFigure.setLabel('bottom', "Mass", units="amu")
					elif settings["unit"][0] == u"μ":
						self.CVplotFigure.setLabel('bottom', "Wavelength", units=settings["unit"][1:])
				if settings["unit"] == "ms":
					expspec.x /= 1e3
				elif settings["unit"][0] == u"μ":
					expspec.x /= 1e6
			elif not len(self.CVcatalogs) and not len(self.CVexpSpectra): # reset plot
				self.CVplotFigure.setLabel('bottom', units="Hz")
				self.CVplotFigure.getPlotItem().vb.invertX(False)
				self.CVplotFigure.getAxis('bottom').setScale(scale=1e6)
			x += expspec.x.tolist()
			y += expspec.y.tolist()
			try:
				header += expspec.ppheader
			except AttributeError:
				header += ["(blank)"]
			if (not settings["appendData"]) or (i == int(len(filenames)-1)):
				# sort by x
				x, y = list(zip(*sorted(zip(x, y))))
				# convert back to ndarray
				x = np.asarray(x)
				y = np.asarray(y)
				# update plot and GUI elements
				self.CVexpSpectra.append({
					'x':x, 'xOrig':x.copy(),
					'y':y, 'yOrig':y.copy(),
					'header':header,
					'filenames':[filenames[i]],
					'spec':expspec})
				self.CVexpSettings.append(dict(self.CVdefaultSettings))
				self.CVexpSettings[-1]["settings"] = settings
				if ("preprocess" in settings) and (settings["preprocess"] is not None):
					self.CVexpSettings[-1]["transformations"] = settings["preprocess"]
				self.CVexpSettings[-1]["settings"] = settings
				newMaxExpIdx = self.cb_CVplotIdxExp.maximum() + 1
				self.cb_CVplotIdxExp.setMaximum(newMaxExpIdx)
				self.cb_CVexpIdx.setMaximum(newMaxExpIdx)
				self.cb_CVplotIdxExp.setValue(newMaxExpIdx)
				self.cb_CVexpIdx.setValue(newMaxExpIdx)
				self.cb_CVexpMath1.setMaximum(newMaxExpIdx)
				self.cb_CVexpMath2.setMaximum(newMaxExpIdx)
				# add to plot and update
				if ("histogram" in settings) and settings["histogram"]:
					self.CVplotsExp.append(Widgets.StickPlot(
						x=[], height=[], name=name))
				else:
					self.CVplotsExp.append(Widgets.SpectralPlot(
						name=name, clipToView=True,
						autoDownsample=True, downsampleMethod='subsample'))
				self.CVplotFigure.addItem(self.CVplotsExp[-1])
				if colormap is not None:
					newColor = pg.mkColor(colormap[i])
				else:
					newColor = pg.mkColor("#%06x" % random.randint(0, 0xFFFFFF))
				hsv = newColor.getHsv()
				newColor.setHsv(hsv[0], hsv[1], 255)
				self.CVexpSettings[-1]["color"] = miscfunctions.qcolorToRGBA(newColor)
				self.CVplotsExp[-1].setPen(pg.mkPen(self.CVexpSettings[-1]["color"]))
				self.CVplotsExp[-1].setData(x=self.CVexpSpectra[-1]['x'], y=self.CVexpSpectra[-1]['y'])
				self.CVplotsExp[-1].update()
				# update the tooltips for the indices
				ttip = "idx - name"
				for i,expPlot in enumerate(self.CVplotsExp):
					ttip += "\n%s - %s" % ((i+1),expPlot.name())
				self.cb_CVplotIdxExp.setToolTip(ttip)
				self.cb_CVexpIdx.setToolTip(ttip)
				self.cb_CVexpMath1.setToolTip(ttip)
				self.cb_CVexpMath2.setToolTip(ttip)
		self.CVupdatePlot()
	def CVloadOther(self, mouseEvent=False):
		"""
		Provides a dialog for loading a variety of alternative online
		sources for quick access.

		:param mouseEvent: (optional) the mouse event from a click
		:param item: (optional) the name of an item (names provided in dialog)
		:type mouseEvent: QtGui.QMouseEvent
		:type item: str
		"""
		reload(Dialogs)
		def addSpectra():
			spectra = self.OnlineDataBrowser.getSpectra()
			if (spectra is None) or (not len(spectra)):
				return
			for spectrum in spectra:
				name = str(spectrum.text(0))
				settings = self.defaultLoadSettings.copy()
				if spectrum.extras is not None:
					settings.update(spectrum.extras)
				if settings["filetype"] is None:
					settings['filetype'] = spectrum.sourceurl.split(".")[-1]
				if settings['filetype'] in ("csv", "casac"):
					filename = "%s.csv" % name.replace(" ", "_")
					filename = os.path.join(self.tmpDir, filename)
					log.info("downloading %s to %s" % (name, filename))
					urlretrieve(spectrum.sourceurl, filename)
					settings.update({
						"filenames" : [filename]})
					self.CVloadExp(filenames=[filename], settings=settings)
					self.CVexpSettings[-1]['sourceURL'] = spectrum.sourceurl
				elif "fits" in (settings['filetype'], spectrum.sourceurl[-4:]):
					filename = "%s.fits" % name.replace(" ", "_")
					filename = os.path.join(self.tmpDir, filename)
					log.info("downloading %s to %s" % (name, filename))
					urlretrieve(spectrum.sourceurl, filename)
					settings = self.defaultLoadSettings.copy()
					settings.update({
						"filetype" : "fits",
						#"delimiter" : ",",
						"filenames" : [filename]})
					self.CVloadExp(filenames=[filename], settings=settings)
					self.CVexpSettings[-1]['sourceURL'] = spectrum.sourceurl
				else:
					msg = "not yet sure what to do with this: %s" % spectrum.sourceurl
					raise NotImplementedError(msg)
		self.OnlineDataBrowser = Dialogs.OnlineDataBrowser(parent=self)
		self.OnlineDataBrowser.accepted.connect(addSpectra)
		self.OnlineDataBrowser.show()
	def CVpasteExp(self):
		"""
		Loads a spectral file into memory.
		"""
		# grab clipboard contents
		clipboard = unicode(QtGui.QApplication.clipboard().text())
		# try to determine data format
		if all(',' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a csv")
			ftype = "csv"
		elif all('\t' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a tsv")
			ftype = "tsv"
		else:
			log.info("pasting what is not csv or tsv, and therefore assuming ssv")
			ftype = "ssv"
		# write out to temporary file
		fname='clipboard (%s).%s' % (time.strftime("%Y-%m-%d %H:%M:%S"), ftype)
		fname = os.path.join(self.tmpDir, fname)
		fd = codecs.open(fname, encoding='utf-8', mode='w+')
		fd.write(clipboard)
		fd.close()
		# now load using the standard function..
		settings = self.defaultLoadSettings.copy()
		settings["filetype"] = ftype
		self.CVloadExp(filenames=[fname], settings=settings)
	def CVremoveExp(self, inputEvent=None, idx=None):
		"""
		Removes a spectral file from the plot and memory.
		"""
		# process the catalog index
		if idx is not None:
			expIdx = idx
		else:
			expIdx = self.cb_CVplotIdxExp.value()
		if not expIdx:
			return
		# remove the plots
		expIdx -= 1 # to easily account for 0-indexing
		self.CVplotLegend.removeItem(self.CVplotsExp[expIdx].name())
		self.CVplotFigure.removeItem(self.CVplotsExp[expIdx])
		del self.CVexpSpectra[expIdx]
		del self.CVexpSettings[expIdx]
		del self.CVplotsExp[expIdx]
		# update the GUI contents
		newMaxExpIdx = self.cb_CVplotIdxExp.maximum() - 1
		self.cb_CVplotIdxExp.setMaximum(newMaxExpIdx)
		self.cb_CVexpIdx.setMaximum(newMaxExpIdx)
		self.cb_CVexpMath1.setMaximum(newMaxExpIdx)
		self.cb_CVexpMath2.setMaximum(newMaxExpIdx)
		# update the tooltips for the indices
		ttip = "idx - name"
		for i,expPlot in enumerate(self.CVplotsExp):
			ttip += "\n%s - %s" % ((i+1),expPlot.name())
		self.cb_CVplotIdxExp.setToolTip(ttip)
		self.cb_CVexpIdx.setToolTip(ttip)
		self.cb_CVexpMath1.setToolTip(ttip)
		self.cb_CVexpMath2.setToolTip(ttip)
		self.CVupdatePlot()

	def CVupdateSimSettings(self):
		"""
		Updates the displayed simulation settings for the given index.
		"""
		simIdx = self.cb_CVsimIdx.value()
		if not simIdx:
			self.txt_CVsimScale.clear()
			self.txt_CVtemperature.clear()
			self.check_CVsimHidden.setChecked(False)
			self.check_CVsimHighlightObs.setChecked(False)
			self.check_CVsimShowUnc.setChecked(False)
		else:
			simIdx -= 1 # to easily account for 0-indexing
			self.txt_CVsimScale.setValue(self.CVcatSettings[simIdx]['scale'])
			self.txt_CVtemperature.setValue(self.CVcatSettings[simIdx]['temp'])
			self.check_CVsimHidden.setChecked(self.CVcatSettings[simIdx]['hidden'])
			self.check_CVsimHighlightObs.setChecked(self.CVcatSettings[simIdx]['highlightobs'])
			self.check_CVsimShowUnc.setChecked(self.CVcatSettings[simIdx]['showunc'])
	def CVsaveSimSettings(self):
		"""
		Saves the changed simulation settings for the given index. This
		is called immediately whenever any of the contents change (so
		long as the index is not ZERO). It also invokes an update of the
		simulation in the end.
		"""
		simIdx = self.cb_CVsimIdx.value()
		if not simIdx:
			self.txt_CVsimScale.clear()
			self.txt_CVtemperature.clear()
			self.check_CVsimHidden.setChecked(False)
			self.check_CVsimHighlightObs.setChecked(False)
			self.check_CVsimShowUnc.setChecked(False)
		else:
			simIdx -= 1 # to easily account for 0-indexing
			self.CVcatSettings[simIdx]['scale'] = self.txt_CVsimScale.value()
			self.CVcatSettings[simIdx]['temp'] = self.txt_CVtemperature.value()
			self.CVcatSettings[simIdx]['hidden'] = self.check_CVsimHidden.isChecked()
			self.CVcatSettings[simIdx]['highlightobs'] = self.check_CVsimHighlightObs.isChecked()
			self.CVcatSettings[simIdx]['showunc'] = self.check_CVsimShowUnc.isChecked()
			self.CVupdatePlot()
	def CVupdateExpSettings(self):
		"""
		See CVsaveSimSettings, except this works for the experimental
		spectra.
		"""
		expIdx = self.cb_CVexpIdx.value()
		if not expIdx:
			self.check_CVexpHidden.setChecked(False)
		else:
			expIdx -= 1 # to easily account for 0-indexing
			self.check_CVexpHidden.setChecked(self.CVexpSettings[expIdx]['hidden'])
	def CVsaveExpSettings(self):
		"""
		See CVsaveSimSettings, except this works for the experimental
		spectra.
		"""
		expIdx = self.cb_CVexpIdx.value()
		if not expIdx:
			self.check_CVexpHidden.setChecked(False)
		else:
			expIdx -= 1 # to easily account for 0-indexing
			self.CVexpSettings[expIdx]['hidden'] = self.check_CVexpHidden.isChecked()
			self.CVupdatePlot()
	def CVchooseTransformations(self, inputEvent=None):
		expIdx = self.cb_CVexpIdx.value()
		if expIdx:
			expIdx -= 1
			transformationDialog = Dialogs.CheckableSettingsWindow(self.tabWidget, self.CVupdateTransformations)
			self.transWindow = transformationDialog
			settings = self.CVexpSettings[expIdx]['settings']
			transformations = []
			if ("transformations" in self.CVexpSettings[expIdx]):
				transformations = self.CVexpSettings[expIdx]['transformations']
			value = 0.0
			checked = False
			if ("vlsrShift" in transformations):
				idxP = transformations.index("vlsrShift")
				value = transformations[idxP+1]
				checked = True
			transformationDialog.addRow(
				"vlsrShift",
				"vlsrShift: Performs a velocity shift (m/s) across the frequency axis",
				checked=checked,
				entries=[{"format":"%.1f", "value":value, "hover":"units: m/s!"}])
			value = 0.0
			checked = False
			if ("vlsrFix" in transformations):
				idxP = transformations.index("vlsrFix")
				value = transformations[idxP+1]
				checked = True
			transformationDialog.addRow(
				"vlsrFix",
				"vlsrFix: Fixes the v_lsr (first removes old value, e.g. via FITS header)",
				checked=checked,
				entries=[{"format":"%.1f", "value":value, "hover":"units: m/s!"}])
			value = 0.0
			checked = False
			if ("shiftX" in transformations):
				idxP = transformations.index("shiftX")
				value = transformations[idxP+1]
				checked = True
			transformationDialog.addRow(
				"shiftX",
				"shiftX: Shifts the x-axis by a fixed value",
				checked=checked,
				entries=[{"format":"%g", "value":value, "hover":"unit: agnostic (i.e. same as original)"}])
			value = 0.0
			checked = False
			if ("shiftY" in transformations):
				idxP = transformations.index("shiftY")
				value = transformations[idxP+1]
				checked = True
			transformationDialog.addRow(
				"shiftY",
				"shiftY: Shifts the y-axis by a fixed value",
				checked=checked,
				entries=[{"format":"%g", "value":value}])
			value = 0.0
			checked = False
			if ("scaleY" in transformations):
				idxP = transformations.index("scaleY")
				value = transformations[idxP+1]
				checked = True
			transformationDialog.addRow(
				"scaleY",
				"scaleY: Scales the y-axis by a fixed value",
				checked=checked,
				entries=[{"format":"%g", "value":value}])
			value = 0.0
			checked = False
			if ("clipTopY" in transformations):
				idxP = transformations.index("clipTopY")
				value = transformations[idxP+1]
				checked = True
			transformationDialog.addRow(
				"clipTopY",
				"clipTopY: Clips all y-values to a maximum value",
				checked=checked,
				entries=[{"format":"%g", "value":value}])
			value = 0.0
			checked = False
			if ("clipBotY" in transformations):
				idxP = transformations.index("clipBotY")
				value = transformations[idxP+1]
				checked = True
			transformationDialog.addRow(
				"clipBotY",
				"clipBotY: Clips all y-values to a minimum value value",
				checked=checked,
				entries=[{"format":"%g", "value":value}])
			value = 0.0
			checked = False
			if ("clipAbsY" in transformations):
				idxP = transformations.index("clipAbsY")
				value = transformations[idxP+1]
				checked = True
			transformationDialog.addRow(
				"clipAbsY",
				"clipAbsY: Clips all y-values to a min. -VAL1 and max. +VAL1",
				checked=checked,
				entries=[{"format":"%g", "value":value}])
			value = 0.0
			checked = False
			if ("wienerY" in transformations):
				idxP = transformations.index("wienerY")
				value = transformations[idxP+1]
				checked = True
			value = 10
			checked = False
			transformationDialog.addRow(
				"wienerY",
				"wienerY: Performs Wiener filter (same as BR tab)",
				checked=checked,
				entries=[{"format":"%d", "value":value, "hover":"the window size"}])
			value = 0.0
			checked = False
			if ("medfiltY" in transformations):
				idxP = transformations.index("medfiltY")
				value = transformations[idxP+1]
				checked = True
			value = 3
			checked = False
			transformationDialog.addRow(
				"medfiltY",
				"medfiltY: Performs a Median filter using a window size",
				checked=checked,
				entries=[{"format":"%d", "value":value, "hover":"the window size"}])
			val1 = 1
			val2 = 5e-3
			checked = False
			if ("ffbutterY" in transformations):
				idxP = transformations.index("ffbutterY")
				val1 = transformations[idxP+1]
				val2 = transformations[idxP+2]
				checked = True
			transformationDialog.addRow(
				"ffbutterY",
				"ffbutterY: Performs a low-pass filter (same as BR tab)",
				checked=checked,
				entries=[{"format":"%d", "value":val1, "hover":"the roll-off order (range: 1 to 8)"},
				{"format":"%.1f", "value":val2, "hover":"the max Nyquist frequency (valid range: 0.0 to 1.0)"}])
			if transformationDialog.exec_():
				pass
	def CVupdateTransformations(self, inputEvent=None, settings=None):
		expIdx = self.cb_CVexpIdx.value() - 1
		self.CVexpSettings[expIdx]['transformations'] = settings
		knownTransformations = [
			("vlsrShift",1), ("vlsrFix",1),
			("shiftX",1), ("shiftY",1), ("scaleY",1),
			("clipTopY",1), ("clipBotY",1), ("clipAbsY",1),
			("wienerY",1), ("medfiltY",1), ("ffbutterY",2)]
		spec = self.CVexpSpectra[expIdx]['spec']
		try:
			self.CVexpSpectra[expIdx]['x'] = spec.xOrig.copy()
			self.CVexpSpectra[expIdx]['y'] = spec.yOrig.copy()
		except AttributeError:
			self.CVexpSpectra[expIdx]['x'] = self.CVexpSpectra[expIdx]['xOrig'].copy()
			self.CVexpSpectra[expIdx]['y'] = self.CVexpSpectra[expIdx]['yOrig'].copy()
		if len(settings):
			# do transformations
			if "vlsrShift" in settings:
				# this assumes vrad shift in m/s for a frequency axis
				idxP = settings.index("vlsrShift")
				val = float(settings[idxP+1])
				self.CVexpSpectra[expIdx]['x'] *= (1 + val/2.99792458e8)
			if "vlsrFix" in settings:
				curVal = 0
				if "VELO-LSR" in spec.h:
					curVal = float(spec.h["VELO-LSR"])
				elif "VELO" in spec.h:
					curVal = float(spec.h["VELO"])
				elif "VELREF" in spec.h:
					curVal = float(spec.h["CRVAL1"])
				elif "VLSR" in spec.h: # is apparently non-standard..
					curVal = float(spec.h["VLSR"])*1e3
				elif "lsr" in spec.h:
					log.info("found something else containing 'lsr' in the header..")
				elif "velo" in spec.h:
					log.info("found something else containing 'vel' in the header..")
				# this assumes vrad shift in m/s for a frequency axis
				idxP = settings.index("vlsrFix")
				val = float(settings[idxP+1])
				if not curVal == 0.0:
					log.info("first removing the old vel_lsr: %s" % curVal)
					self.CVexpSpectra[expIdx]['x'] *= (1 - curVal/2.99792458e8) # revert old value
				log.info("applying vel_lsr = %s" % val)
				self.CVexpSpectra[expIdx]['x'] *= (1 + val/2.99792458e8) # apply new value
			if "shiftX" in settings:
				idxP = settings.index("shiftX")
				val = float(settings[idxP+1])
				log.info("applying shiftX = %s" % val)
				self.CVexpSpectra[expIdx]['x'] += val
			if "shiftY" in settings:
				idxP = settings.index("shiftY")
				val = float(settings[idxP+1])
				self.CVexpSpectra[expIdx]['y'] += val
			if "scaleY" in settings:
				idxP = settings.index("scaleY")
				val = float(settings[idxP+1])
				self.CVexpSpectra[expIdx]['y'] *= val
			if "clipTopY" in settings:
				idxP = settings.index("clipTopY")
				val = float(settings[idxP+1])
				self.CVexpSpectra[expIdx]['y'] = np.clip(self.CVexpSpectra[expIdx]['y'], None, val)
			if "clipBotY" in settings:
				idxP = settings.index("clipBotY")
				val = float(settings[idxP+1])
				self.CVexpSpectra[expIdx]['y'] = np.clip(self.CVexpSpectra[expIdx]['y'], val, None)
			if "clipAbsY" in settings:
				idxP = settings.index("clipAbsY")
				val = float(settings[idxP+1])
				self.CVexpSpectra[expIdx]['y'] = np.clip(self.CVexpSpectra[expIdx]['y'], -val, val)
			if "wienerY" in settings:
				idxP = settings.index("wienerY")
				val = float(settings[idxP+1])
				self.CVexpSpectra[expIdx]['y'] -= Filters.get_wiener(self.CVexpSpectra[expIdx]['y'], val)
			if "medfiltY" in settings:
				idxP = settings.index("medfiltY")
				val = int(settings[idxP+1])
				self.CVexpSpectra[expIdx]['y'] = scipy.signal.medfilt(self.CVexpSpectra[expIdx]['y'], val)
			if "ffbutterY" in settings:
				idxP = settings.index("ffbutterY")
				ford = int(settings[idxP+1])
				ffreq = float(settings[idxP+2])
				b, a = scipy.signal.butter(ford, ffreq, btype='low', analog=False, output='ba')
				self.CVexpSpectra[expIdx]['y'] = scipy.signal.filtfilt(b, a, self.CVexpSpectra[expIdx]['y'], padlen=20)
		self.CVplotsExp[expIdx].setData(x=self.CVexpSpectra[expIdx]['x'], y=self.CVexpSpectra[expIdx]['y'])
	
	def CVsaveSession(self, inputEvent=None, filename=None):
		"""
		Performs the saving of the current session (i.e. loaded files
		and their settings) to a file, which can be loaded via the
		respective load button/routine.
		"""
		if filename is None:
			directory = self.cwd
			filename = QtGui.QFileDialog.getSaveFileName(
				parent=self, caption='Select output file',
				directory=directory, filter='YAML files (*.yml)')
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5.0.0":
				filename = filename[0]
			else:
				filename = str(filename)
		self.cwd = os.path.realpath(os.path.dirname(filename))
		sessionFile = str(filename)
		if not sessionFile:
			return
		if not sessionFile[-4:] == ".yml":
			sessionFile += ".yml"
		try:
			import yaml
		except ImportError:
			log.exception("QtFit depends on PyYAML for the saving/loading of sessions!")
			return
		### collect the current files and their settings
		data = {}
		for catIdx,cat in enumerate(self.CVcatalogs):
			nodename = "catalog%s" % catIdx
			data[nodename] = self.CVcatSettings[catIdx]
			data[nodename]["filename"] = os.path.abspath(cat.filename)
		for expIdx,exp in enumerate(self.CVexpSpectra):
			nodename = "spec%s" % expIdx
			data[nodename] = self.CVexpSettings[expIdx]
			filenames = exp["filenames"]
			if isinstance(filenames, str):
				data[nodename]["filename"] = os.path.abspath(filenames)
			elif len(filenames) == 1:
				data[nodename]["filename"] = os.path.abspath(filenames[0])
			else:
				data[nodename]["filename"] = [os.path.abspath(f) for f in filenames]
		### collect the plot labels
		labelIdx = 0
		for labels in self.CVplotLabels:
			if isinstance(labels, (list, tuple)):
				for label in labels:
					nodename = "label%s" % labelIdx
					data[nodename] = {
						"text": unicode(label.textItem.toPlainText()),
						"html": label.html,
						"anchor": list(label.anchor),
						"pos": list(label.pos()),
						"fill": miscfunctions.qcolorToRGBA(label.fill)}
					labelIdx += 1
			else:
				label = labels
				nodename = "label%s" % labelIdx
				data[nodename] = {
					"text": unicode(label.textItem.toPlainText()),
					"anchor": list(label.anchor),
					"pos": list(label.pos()),
					"fill": miscfunctions.qcolorToRGBA(label.fill)}
				if "html" in dir(label):
					data[nodename]["html"] = label.html
				labelIdx += 1
		### collect the plot settings
		viewrange = self.CVplotFigure.getViewBox().state['viewRange']
		viewrange = [
			[float(viewrange[0][0]), float(viewrange[0][1])],
			[float(viewrange[1][0]), float(viewrange[1][1])]]
		data["viewrange"] = viewrange
		data["xrange"] = list(viewrange[0])
		data["yrange"] = list(viewrange[1])
		data["autorange"] = list(self.CVplotFigure.getViewBox().state['autoRange'])
		data["winsize"] = [self.width(), self.height()]
		data["width"] = self.width()
		data["height"] = self.height()
		data["winpos"] = [self.x(), self.y()]
		log.info("writing the following as the session to '%s'" % sessionFile)
		log.debug(yaml.dump(data))
		### dump the session to file
		log.info("saving the current session to '%s'" % sessionFile)
		fh = open(sessionFile, 'w')
		header = """#
		# DESCRIPTION
		# This is a session for loaded spectra and line catalogs for the CV tab
		# for QtFit. The format is YAML (1), which "may be the most human friendly
		# format for structured data invented so far" (2).
		#
		# REFS
		# 1: https://yaml.org/
		# 2: https://wiki.python.org/moin/YAML
		#
		# EXAMPLE (minimalist, compared to what is saved by qtfit)
		# autorange: false
		# xrange: [330e3, 450e3]
		# yrange: [0, 0.001]
		# catalog0:
		#   color: y
		#   filename: /home/jake/Documents/line catalogs/40-ArH+ (cdms) wavenumbers incorrect.cat
		#   hidden: false
		#   highlightobs: false
		#   scale: 1
		#   showunc: false
		#   temp: 300
		#   tunit: wvn      # used to override incorrect catalogs via missing negative signs
		#   unit: wvn
		# catalog99:
		#   color: [6, 18, 255, 255]
		#   filename: /home/jake/Documents/line catalogs/40-ArH+ (cdms) wavenumbers.cat
		#   unit: wvn
		# catalog1:
		#   filename: "/home/jake/Documents/line catalogs/36-ArH+ (cdms).cat"
		#   temp: 10
		#   scale: 100
		#   color: r
		# catalog2: "/home/jake/Documents/line catalogs/38-ArH+ (cdms).cat"
		# spec1: "/home/jake/Documents/Data/testdata/2016-02-22__13-32-46.98__ethanol_332-333.csv"
		# spec2:
		#   filename: "/home/jake/Documents/Data/testdata/hc3n_long_scan.csv"
		#
		# NOTES
		# - individual plots are simply separate keys, and their settings are nested items
		# - no two keys may have the same name, so you must do something like "spec1 spec2 spec3 etc.."
		# - "color" settings for plots may also be a much simpler, such as the single letter shown above
		#   ‘c’             one of: r,g,b,c,m,y,k,w  for red/green/blue/cyan/magenta/yellow/black/white
		#   [R, G, B, [A]]  integers 0-255, where A is the alpha (i.e. opacity)
		#   (R, G, B, [A])  tuple of integers 0-255
		#   float           greyscale, 0.0-1.0
		#   “RRGGBB”        hexadecimal strings; may begin with ‘#’
		#   “RRGGBBAA”
		# - "fill" for labels may only be a list or tuple [R, G, B, A] of integers
		# - catalogs must always begin with "cat", such as "catblah1"
		# - spectra must always begin with "spec", such as "spectrumblah1"
		# - "position" may be used instead of "winpos"
		# - "xrange" (or the first entry in "viewrange") is relative to the plotted units & scale
		#
		"""
		header = header.replace('\t', '')
		header += "# CREATED: %s\n#\n" % (datetime.datetime.now())
		fh.write(header)
		yaml.dump(data, fh)
		fh.close()
	def CVloadSession(self, inputEvent=None, filename=None):
		"""
		Performs the loading of an old session (i.e. loaded files
		and their settings) from a file.
		"""
		if filename is None:
			directory = self.cwd
			filename = QtGui.QFileDialog.getOpenFileName(
				parent=self, caption='Open session file',
				directory=directory, filter='YAML files (*.yml)')
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5.0.0":
				filename = filename[0]
			else:
				filename = str(filename)
			if not os.path.isfile(filename):
				return
		self.cwd = os.path.realpath(os.path.dirname(filename))
		sessionFile = filename
		try:
			import yaml
		except ImportError:
			log.exception("QtFit depends on PyYAML for the saving/loading of sessions!")
			return
		try:
			session = yaml.full_load(open(sessionFile, 'r'))
		except:
			session = yaml.load(open(sessionFile, 'r'))
		### process the contents
		### process window-specific items
		if "winsize" in session:
			self.resize(*session["winsize"])
		else:
			w, h = self.width(), self.height()
			resize = False
			if "width" in session:
				w = session["width"]
				resize = True
			if "height" in session:
				h = session["height"]
				resize = True
			if resize:
				self.resize(w, h)
		if "position" in session:
			self.move(*session["position"])
		elif "winpos" in session:
			self.move(*session["winpos"])
		### process plot-specific
		for key,val in sorted(session.items()):
			log.debug("processing: %s -> %s" % (key, val))
			try:
				if key[:3] == "cat":
					if isinstance(val, str):
						self.CVloadCatalog(catalogs=val)
					else:
						filename = val["filename"]
						if not os.path.isfile(filename):
							if not "sourceURL" in val:
								msg = "%s could not be loaded " % (filename)
								msg += "from the session file (%s)" % (sessionFile)
								raise Exception(msg)
							else:
								try:
									sourceURL = val["sourceURL"]
									filename = os.path.split(filename)[-1]
									filename = os.path.join(self.tmpDir, filename)
									fh = open(filename, 'wb')
									r = requests.get(sourceURL, allow_redirects=True, timeout=5)
									r.raise_for_status()
									for chunk in r.iter_content(1024):
										fh.write(chunk)
									fh.close()
								except:
									msg = "%s could not be loaded " % (filename)
									msg += "from the session file (%s), " % (sessionFile)
									msg += "including from its URL (%s)" % (sourceURL)
									log.warning(msg)
									if self.debugging:
										raise
						temp, scale = None, None
						unit, tunit = "MHz", None
						if "temp" in val:
							temp = float(val["temp"])
						if "scale" in val:
							scale = float(val["scale"])
						if "unit" in val:
							unit = val["unit"]
						if "tunit" in val:
							tunit = val["tunit"]
						self.CVloadCatalog(
							catalogs=filename,
							temp=temp, scale=scale,
							unit=unit, tunit=tunit)
						self.CVcatSettings[-1].update(val)
						if "color" in val:
							pen = pg.mkPen(val["color"])
							self.CVplotsCat[-1].setPen(pen)
						if "name" in val:
							self.CVrenameCat(newname=val["name"])
				elif key[:4] == "spec":
					settings = self.defaultLoadSettings.copy()
					if isinstance(val, str):
						filename = val
						settings["filetype"] = filename.split(".")[-1]
					else:
						filename = val["filename"]
						if not os.path.isfile(filename):
							if not "sourceURL" in val:
								msg = "%s could not be loaded " % (filename)
								msg += "from the session file (%s)" % (sessionFile)
								raise Exception(msg)
							else:
								try:
									sourceURL = val["sourceURL"]
									filename = os.path.split(filename)[-1]
									filename = os.path.join(self.tmpDir, filename)
									urlretrieve(sourceURL, filename)
								except:
									msg = "%s could not be loaded " % (filename)
									msg += "from the session file (%s), " % (sessionFile)
									msg += "including from its URL (%s)" % (sourceURL)
									log.warning(msg)
									if self.debugging:
										raise
						if "settings" in val:
							settings.update(val["settings"])
						else:
							settings.update(val)
						if settings["filetype"] is None:
							settings["filetype"] = filename.split(".")[-1]
					self.CVloadExp(filenames=[filename], settings=settings)
					if isinstance(val, dict):
						self.CVexpSettings[-1].update(val)
						# fix color...
						if "color" in val:
							pen = pg.mkPen(val["color"])
							self.CVplotsExp[-1].setPen(pen)
						if "name" in val:
							self.CVrenameExp(newname=val["name"])
						# fix transformations...
						if "transformations" in val:
							self.CVupdateTransformations(settings=val["transformations"])
				elif key[:5] == "label":
					label = pg.TextItem(
						text=val.get("text",""),
						color=val.get("color",(200,200,200)),
						anchor=val.get("anchor",(0,0)),
						border=val.get("border",None),
						fill=val.get("fill",None))
					if ("html" in val) and (val["html"] is not None):
						label.html = val["html"]
						label.setHtml(label.html)
					label.setPos(*val["pos"])
					label.setZValue(999)
					self.CVplotFigure.addItem(label, ignoreBounds=True)
					if (len(self.CVplotLabels) and # catch the second item of a pair and group them
						unicode(lastLabel.textItem.toPlainText()) == "*"):
						self.CVplotLabels[-1] = (lastLabel, label)
					else:
						self.CVplotLabels.append(label)
					lastLabel = label
			except Exception as e:
				log.warning("\twarning: there was a problem with a session entry: %s" % e)
				if self.debugging:
					raise
		### process figure-specific items
		if "autorange" in session:
			autorange = session["autorange"]
			if isinstance(autorange, (list, tuple)) and len(autorange)==2:
				self.CVplotFigure.getViewBox().enableAutoRange(
					x=autorange[0], y=autorange[1])
			elif autorange:
				self.CVplotFigure.getViewBox().enableAutoRange()
		if "viewrange" in session:
			self.CVplotFigure.getViewBox().setXRange(*session["viewrange"][0], padding=0.0)
			self.CVplotFigure.getViewBox().setYRange(*session["viewrange"][1], padding=0.0)
		else:
			if "xrange" in session:
				self.CVplotFigure.getViewBox().setXRange(*session["xrange"], padding=0.0)
			if "yrange" in session:
				self.CVplotFigure.getViewBox().setYRange(*session["yrange"], padding=0.0)
		self.CVupdatePlot()
	
	def CVrecolorCat(self):
		"""
		Provides a dialog for choosing a new color for the catalog.
		"""
		actOnAll = False
		if QtGui.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
			actOnAll = True
		simIdx = self.cb_CVsimIdx.value()
		if not simIdx:
			return
		simIdx -= 1 # to easily account for 0-indexing
		self.colorDialog.setCurrentColor(QtGui.QColor(*self.CVcatSettings[simIdx]["color"]))
		if not self.colorDialog.exec_():
			return
		color = self.colorDialog.selectedColor()
		pen = pg.mkPen(color)
		if actOnAll:
			for simIdx,plot in enumerate(self.CVplotsCat):
				plot.opts['pen'] = pen
				self.CVcatSettings[simIdx]["color"] = miscfunctions.qcolorToRGBA(color)
		else:
			self.CVcatSettings[simIdx]["color"] = miscfunctions.qcolorToRGBA(color)
			self.CVplotsCat[simIdx].opts['pen'] = pen
		self.CVupdatePlot()
	def CVrecolorExp(self):
		"""
		Provides a dialog for choosing a new color for the experimental spectrum.
		"""
		actOnAll = False
		if QtGui.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
			actOnAll = True
		expIdx = self.cb_CVexpIdx.value()
		if not expIdx:
			return
		expIdx -= 1 # to easily account for 0-indexing
		self.colorDialog.setCurrentColor(QtGui.QColor(*self.CVexpSettings[expIdx]["color"]))
		if not self.colorDialog.exec_():
			return
		color = self.colorDialog.selectedColor()
		pen = pg.mkPen(color)
		if actOnAll:
			for expIdx,plot in enumerate(self.CVplotsExp):
				plot.setPen(pen)
				self.CVexpSettings[expIdx]["color"] = miscfunctions.qcolorToRGBA(color)
		else:
			self.CVplotsExp[expIdx].setPen(pen)
			self.CVexpSettings[expIdx]["color"] = miscfunctions.qcolorToRGBA(color)
		self.CVupdatePlot()
	
	def CVrenameCat(self, event=None, idx=None, newname=None):
		"""
		Provides a dialog for choosing a new name for the catalog.
		"""
		# get the right index
		if idx is None:
			idx = self.cb_CVsimIdx.value()
			if not idx:
				return
			idx -= 1 # to easily account for 0-indexing
		# get the name and prompt for new one
		name = self.CVplotsCat[idx].name()
		if newname is None:
			self.CVrenameDialog = Dialogs.BasicTextInput(text=name, size=(min(len(name)*10,600),50))
			if not self.CVrenameDialog.exec_():
				return
			newname = str(self.CVrenameDialog.editor.document().toPlainText())
		self.CVcatSettings[idx]["name"] = newname
		self.CVplotsCat[idx].opts["name"] = str(newname).strip()
		# update the tooltips for the indices
		ttip = "idx - name"
		for i,catPlot in enumerate(self.CVplotsCat):
			ttip += "\n%s - %s" % ((i+1),catPlot.name())
		self.cb_CVplotIdxCatalog.setToolTip(ttip)
		self.cb_CVsimIdx.setToolTip(ttip)
		self.CVupdatePlot()
	def CVrenameExp(self, event=None, idx=None, newname=None):
		"""
		Provides a dialog for choosing a new name for the experimental spectrum.
		"""
		# get the right index
		if idx is None:
			idx = self.cb_CVexpIdx.value()
			if not idx:
				return
			idx -= 1 # to easily account for 0-indexing
		# get the name and prompt for new one
		if newname is None:
			name = self.CVplotsExp[idx].name()
			self.CVrenameDialog = Dialogs.BasicTextInput(text=name, size=(min(len(name)*10,600),50))
			if not self.CVrenameDialog.exec_():
				return
			newname = str(self.CVrenameDialog.editor.document().toPlainText())
		self.CVexpSettings[idx]["name"] = newname
		self.CVplotsExp[idx].opts["name"] = str(newname).strip()
		# update the tooltips for the indices
		ttip = "idx - name"
		for i,expPlot in enumerate(self.CVplotsExp):
			ttip += "\n%s - %s" % ((i+1),expPlot.name())
		self.cb_CVplotIdxExp.setToolTip(ttip)
		self.cb_CVexpIdx.setToolTip(ttip)
		self.cb_CVexpMath1.setToolTip(ttip)
		self.cb_CVexpMath2.setToolTip(ttip)
		self.CVupdatePlot()

	def CVshowHeader(self):
		"""
		Opens a window to show the header information for the experimental spectrum.
		"""
		expIdx = self.cb_CVexpIdx.value()
		if not expIdx:
			return
		expIdx -= 1 # to easily account for 0-indexing
		header = self.CVexpSpectra[expIdx]['header']
		if isinstance(header, str):
			header = [header]
		self.CVexpHeaderWindows.append(Widgets.HeaderViewer(self, header))
		self.CVexpHeaderWindows[-1].show()

	def CVviewCatEntries(self, useCutoff=False):
		"""
		Opens a window to show the currently active line entries of the shown catalogs

		:param useCutoff: (optional) whether to use an intensity cutoff for excluding weak lines
		:type useCutoff: bool
		"""
		entries = []
		fMin, fMax = self.CVplotFigure.getViewBox().viewRange()[0]
		yMin, yMax = self.CVplotFigure.getViewBox().viewRange()[1]
		# gather all lines entries
		for catIdx,cat in enumerate(self.CVcatalogs):
			if self.CVcatSettings[catIdx]['hidden']:
				continue
			# get temperature-rescaled intensities
			trot = self.CVcatSettings[catIdx]['temp']
			idx, y = cat.temperature_rescaled_intensities(freq_min=fMin, freq_max=fMax, trot=trot)
			x, err, pens = [], [], []
			for i in idx:
				x.append(cat.transitions[i].calc_freq)
			x, idx = np.asarray(x), np.asarray(idx)
			if len(x)==0:
				continue
			# rescale intensities and mask weak lines (even if ignoring cutoff)
			y *= self.CVcatSettings[catIdx]['scale']
			#mask = y > (y.max()*1e-4) # cutoff is per-catalog basis
			mask = y > (yMax*1e-3) # cutoff is plot-limit basis
			# append to list
			if useCutoff:
				idx = idx[mask]
			for i in idx:
				entry_str = cat.transitions[i].cat_str()
				entry_str += "# %s" % self.CVplotsCat[catIdx].name()
				entries.append(entry_str)
		# sort & convert to a single string
		entries = sorted(entries)
		entries = "\n".join(entries)
		self.CVentryViewer = Dialogs.BasicTextViewer(entries)
	def CVdoSplat(self):
		"""
		Invokes a spectral line query, based on the frequency ranges of
		the displayed plot range.
		"""
		viewrange = self.CVplotFigure.getViewBox().state['viewRange']
		lowerX, upperX = float(viewrange[0][0]), float(viewrange[0][1])
		rangeX = float(upperX-lowerX)
		if rangeX > 100:
			msg = "Are you sure you want to search across %f?" % rangeX
			response = QtGui.QMessageBox.question(self, "Confirmation", msg,
				QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
			if response == QtGui.QMessageBox.No:
				return
		cdmsurl = 'https://cdms.astro.uni-koeln.de/cdms/tap/sync?REQUEST=doQuery&LANG=VSS2&FORMAT=spcat&QUERY=SELECT+RadiativeTransitions+WHERE+RadTransFrequency>%f+and+RadTransFrequency<%f&ORDERBY=frequency'
		queryurl = cdmsurl % (lowerX, upperX)
		try:
			f = urlopen(queryurl)
		except:
			log.warning("the query to CDMS for spectral lines didn't work, trying to bypass SSL certificate verification..")
			f = urlopen(queryurl, context=ssl._create_unverified_context())
		queryresults = f.read()
		if isinstance(queryresults, bytes):
			queryresults = queryresults.decode('utf-8')
		reload(Dialogs)
		self.splatViewer = Dialogs.BasicTextViewer(queryresults, size=(1000,500))

	def CVupdatePlot(self):
		"""
		Updates the plot. This is called either by the "Update" button
		or whenever any of the simulation inputs are changed.
		"""
		fMin, fMax = map(float, self.CVplotFigure.getViewBox().viewRange()[0])
		sim_x, sim_y = [],[]
		for catIdx,cat in enumerate(self.CVcatalogs):
			# get temperature-rescaled intensities
			trot = self.CVcatSettings[catIdx]['temp']
			if trot < 1:
				continue
			try:
				idx, y = cat.temperature_rescaled_intensities(freq_min=fMin, freq_max=fMax, trot=trot)
			except Exception as e:
				msg = "caught an error: %s\n" % e
				msg += "because of the problem rescaling the temperature"
				msg += " for the catalog '%s'" % self.CVplotsCat[catIdx].name()
				msg += ", will skip it and keep it at the previous temperature..."
				log.exception(msg)
				continue
			x, err, pens = [], [], []
			for i in idx:
				x.append(cat.transitions[i].calc_freq)
				err.append(cat.transitions[i].calc_unc)
				if cat.transitions[i].tag < 0:
					p = pg.mkPen(self.CVcatSettings[catIdx]["color"])
				else:
					p = pg.mkPen(self.CVcatSettings[catIdx]["color"], style=self.highlightedPenStyle)
				pens.append(p)
			x, err, pens = np.asarray(x), np.asarray(err), np.asarray(pens)
			if len(x)==0:
				continue
			# rescale intensities and mask weak lines
			y *= self.CVcatSettings[catIdx]['scale']
			mask = y > (y.max()*1e-4)
			# send to plot
			if self.CVcatSettings[catIdx]["highlightobs"]:
				pens = pens[mask]
			else:
				pens = None
			self.CVplotsCat[catIdx].setData(x=x[mask], height=y[mask],
				pen=pg.mkPen(self.CVcatSettings[catIdx]["color"]), pens=pens,
				err=err[mask], showErr=self.CVcatSettings[catIdx]["showunc"])
			self.CVplotsCat[catIdx].update()
			# add to simulation if necessary
			if self.check_CVuseSim.isChecked():
				sim_x += x.tolist()
				sim_y += y.tolist()
		# process the simulation
		self.CVplotLegend.removeItem(self.CVplotSim.name())
		if self.check_CVuseSim.isChecked() and (len(sim_x) > 0):
			sim_x, sim_y = np.asarray(sim_x), np.asarray(sim_y)
			lw = float(str(self.txt_CVsimLW.text()))
			step = float(str(self.txt_CVsimStep.text()))
			sim_x, sim_y = self.sim_spectrum(sim_x, sim_y, lw=lw, step=step, cutoff=1e-4)
			try:
				self.CVplotSim.setData(sim_x, sim_y)
				self.CVplotSim.update()
				self.CVplotLegend.addItem(self.CVplotSim, self.CVplotSim.name())
			except:
				pass
		else:
			self.CVplotSim.clear()
		# update exp plots
		for exp in self.CVplotsExp:
			exp.update()
		# process visibilities
		for catIdx,cat in enumerate(self.CVcatalogs):
			self.CVplotsCat[catIdx].setVisible(not self.CVcatSettings[catIdx]['hidden'])
		for expIdx,exp in enumerate(self.CVexpSpectra):
			self.CVplotsExp[expIdx].setVisible(not self.CVexpSettings[expIdx]['hidden'])
		# force-update the legend
		self.CVresetPlotLegend()
		# process the exp math operations
		expIdx1 = self.cb_CVexpMath1.value()
		expIdx2 = self.cb_CVexpMath2.value()
		expOpIdx = self.cb_CVexpMathOp.currentIndex()
		if expOpIdx == 0:
			pass
		elif (expIdx1 == 0) or (expIdx2 == 0):
			self.CVplotExpMath.clear()
			self.CVplotLegend.removeItem(self.CVplotExpMath.name())
		elif expIdx1 == expIdx2:
			self.CVplotExpMath.clear()
			self.CVplotLegend.removeItem(self.CVplotExpMath.name())
		else:
			if expOpIdx == 1:
				op = "add"
			elif expOpIdx == 2:
				op = "sub"
			math_x, math_y = [], []
			math_x, math_y = self.math_btw_spectra(
				self.CVexpSpectra[expIdx1-1],
				self.CVexpSpectra[expIdx2-1],
				op=op)
			self.CVplotExpMath.setData(math_x, math_y)
			self.CVplotExpMath.update()
			self.CVplotLegend.addItem(self.CVplotExpMath, self.CVplotExpMath.name())

	def sim_spectrum(self, x, y, lw=0.3, step=1e-3, stype='gauss', cutoff=None):
		"""
		Runs a simulation for a given list of rest frequencies (x) and
		their 300K-LOGINT (y).

		Note that this is no longer used for simulating the catalogs, and
		should be checked against the spectrum module to make sure nothing
		special would be lost upon the removal of this qtfit method.

		:param x: list of rest frequencies (unit: MHz)
		:param y: list of JPL-style LOGINT at 300K (unit: complicated)
		:param lw: (optional) desired line width (unit: MHz) (default: 0.3)
		:param step: (optional) stepsize of the simulation (unit: MHz) (default: 0.001)
		:param stype: (optional) type of line profile (default: gaussian)
		:param cutoff: (optional) relative percent intensity for exclusion (default: 0.01%)
		:type x: np.ndarray
		:type y: np.ndarray
		:type lw: float
		:type step: float
		:type stype: str
		:type cutoff: float
		"""
		sim_f = []
		if cutoff:
			mask = y > (y.max()*cutoff)
		else:
			mask = np.ones(len(x))
		# find decimals for rounding
		ndec = int(math.ceil(math.log10(step)*-1))
		roundedFreq = lambda x: np.round([x],decimals=ndec)
		# populate list of frequencies
		for f in x[mask]:
			fr = roundedFreq(f) #  ensures the frequencies are rounded
			sim_f += np.arange(fr-10*lw, fr+10*lw+step, step).tolist()
		if len(sim_f) > 1e5:
			log.warning("you attempted to simulate more than 100,000 points; this is dangerous and will be intentionally avoided for now..")
			return None, None
		sim_f = np.asarray(sorted(set(sim_f)))
		sim_int = np.zeros(len(sim_f))
		# generate lines
		if self.cb_CVsimShape.currentIndex() == 0:
			fn = fit.gaussian_true
			rad = 2*lw # to 1e-6 of peak
		elif self.cb_CVsimShape.currentIndex() == 1:
			fn = fit.gaussian2f_true # for gaussian with lw=0.1 and peak=1, this gives fwhm=0.0337024*2 and peak=277.25887
			rad = 3.62*lw
		elif self.cb_CVsimShape.currentIndex() == 2:
			fn = fit.lorentzian
			rad = 160*lw # 1e-4:50x, 1e-5:160x, 1e-6:500x
		elif self.cb_CVsimShape.currentIndex() == 3:
			fn = simtest
			rad = 10*lw
		for i,f in enumerate(x):
			start_i = np.abs(sim_f - (f-rad)).argmin()
			stop_i = np.abs(sim_f - (f+rad)).argmin()
			sim_int[start_i:stop_i] += fn(sim_f[start_i:stop_i], f, y[i], lw)
		# mask the data based on a cutoff
		if cutoff:
			mask = abs(sim_int) > (sim_int.max()*cutoff)
			sim_f = sim_f[mask]
			sim_int = sim_int[mask]
		return sim_f, sim_int

	def math_btw_spectra(self, spec1, spec2, op=None):
		"""
		Performs simple arithmetic between two spectra.

		Note that the first input spectrum is the primary reference, and
		the returned spectrum's axes are the same size/shape of it. The
		secondary spectrum is simply 'interpolated' with respect to the
		data points from the reference spectrum. This allows for arithmetic
		to be performed between two spectra of difference sizes and those
		which do not perfectly overlap with each other.

		:param spec1: the primary, reference spectrum
		:param spec2: the secondary spectrum
		:param op: the type of spectral arithmetic to perform (add or sub)
		:type spec1: list or ndarray
		:type spec2: list or ndarray
		:type op: str

		:returns: a 1-d spectrum resulting from spectral arithmetic
		:rtype: tuple(ndarray, ndarray)
		"""
		x, y = np.asarray(spec1['x'].copy()), np.asarray(spec1['y'].copy())
		spline = interpolate.interp1d(
			spec2['x'], spec2['y'],
			bounds_error=False, fill_value=0)
		if op == "add":
			y += spline(x)
		elif op == "sub":
			y -= spline(x)
		return x, y


	### ES tab
	def ESinitPlot(self):
		"""
		Simply initializes the plot.
		"""
		# figure properties
		self.ESplotFigure.setLabel('left', "Intensity", units='V', **self.labelStyle)
		self.ESplotFigure.setLabel('bottom', "Frequency", units='Hz', **self.labelStyle)
		self.ESplotFigure.getAxis('bottom').setScale(scale=1e6)
		self.ESplotFigure.getAxis('left').tickFont = self.tickFont
		self.ESplotFigure.getAxis('bottom').tickFont = self.tickFont
		self.ESplotFigure.getAxis('bottom').setStyle(**{'tickTextOffset':5})
		# plots
		self.ESplot = Widgets.SpectralPlot(
			name='exp', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.ESplot.setPen('w')
		self.ESplotFigure.addItem(self.ESplot)
		# signals
		self.ESplotMouseLabel = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
		self.ESplotMouseLabel.setZValue(999)
		self.ESplotFigure.addItem(self.ESplotMouseLabel, ignoreBounds=True)
		self.ESplotMouseMoveSignal = pg.SignalProxy(
			self.ESplot.scene().sigMouseMoved,
			rateLimit=15,
			slot=self.ESplotMousePosition)
		self.ESplotSigMouseClick = pg.SignalProxy(
			self.ESplot.scene().sigMouseClicked,
			rateLimit=10,
			slot=self.ESplotMouseClicked)
		# menu entry for copying to clipboard
		self.ESplot.getViewBox().menu.addSeparator()
		copy = self.ESplot.getViewBox().menu.addAction("copy spectrum")
		copy.triggered.connect(self.ESplot.copy)

	def ESloadScan(self, mouseEvent=False, filenames=[], settings={}):
		"""
		Loads a dataset directly into memory.

		:param mouseEvent: (optional) the mouse event from a click
		:param filenames: (optional) a list of files to load, bypassing the selection dialog
		:param settings: (optional) settings to use for loading spectra
		:type mouseEvent: QtGui.QMouseEvent
		:type filenames: list
		:type settings: dict
		"""
		reload(spectrum)
		if not len(filenames):
			# provide dialog
			if not "ESloadDialog" in vars(self):
				self.ESloadDialog = Dialogs.SpecLoadDialog(self)
			if not self.ESloadDialog.exec_():
				return
			else:
				settings = self.ESloadDialog.getValues()
			# get file
			filenames = settings["filenames"]
		if not any([os.path.isfile(f) for f in filenames]):
			raise IOError("could not locate one of the requested input files!")
		self.cwd = os.path.realpath(os.path.dirname(filenames[-1]))
		# if no settings, do some guesswork..
		if settings == {}:
			settings = self.defaultLoadSettings.copy()
		if settings["filetype"] is None:
			settings["filetype"] = spectrum.guess_filetype(filename=filenames)
			log.debug("guessed the filetype(s) should be: %s" % args.filetype)
			if settings["filetype"] is None:
				raise SyntaxError("could not determine the filetype, so you should fix this..")
		# sanity check about: multiple files but not appending them
		if (not settings["appendData"]) and (len(filenames) > 1):
			raise SyntaxError("you cannot load multiple files without appending them!")
		# reset the plots & data
		if not settings["appendData"]:
			self.ESclearPlot()
			self.ESplotData = {"x":[], "y":[]}
			if settings["unit"]=="arb.":
				self.ESplotFigure.setLabel('bottom', "Frequency", units='arb')
			else:
				self.ESplotFigure.setLabel('bottom', "Frequency", units='Hz')
				self.ESplotFigure.getAxis('bottom').setScale(scale=1e6)
		elif isinstance(self.ESplotData["x"], type(np.array([]))):
			self.ESplotData["x"] = self.ESplotData["x"].copy().tolist()
			self.ESplotData["y"] = self.ESplotData["y"].copy().tolist()
		# loop through it and push to memory
		for fileIn in filenames:
			if settings["filetype"] in ["ssv", "tsv", "csv", "casac", "gesp", "ydata"]:
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					skipFirst=settings["skipFirst"])
			elif settings["filetype"]=="jpl":
				if not settings["scanIndex"]:
					settings["scanIndex"] = 1
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (#%g)" % settings["scanIndex"]
			elif settings["filetype"]=="fits":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
			elif settings["filetype"]=="arbdc":
				delimiter = settings["delimiter"]
				xcol = settings["xcol"]
				ycol = settings["ycol"]
				expspec = spectrum.load_spectrum(
					fileIn, ftype="arbdelim",
					skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
					delimiter=delimiter)
			elif settings["filetype"]=="arbs":
				raise NotImplementedError
			elif settings["filetype"] == "brukeropus":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (%s)" % expspec.h['block_key']
			elif settings["filetype"] == "batopt3ds":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"])
			elif settings["filetype"]=="fid":
				pass    # works on this AFTER preprocess
			else:
				raise NotImplementedError("not sure what to do with filetype %s" % settings["filetype"])
			if ("preprocess" in settings) and (settings["preprocess"] is not None):
				expspec.xOrig = expspec.x.copy()
				expspec.yOrig = expspec.y.copy()
				if "vlsrShift" in settings["preprocess"]:
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrShift")
					val = float(settings["preprocess"][idxP+1])
					expspec.x *= (1 + val/2.99792458e8)
				if "vlsrFix" in settings["preprocess"]:
					curVal = 0
					if settings["filetype"]=="fits":
						fitsHeader = expspec.hdu.header
						if "VELO-LSR" in fitsHeader:
							curVal = float(fitsHeader["VELO-LSR"])
						elif "VELO" in fitsHeader:
							curVal = float(fitsHeader["VELO"])
						elif "VELREF" in fitsHeader:
							curVal = float(fitsHeader["CRVAL1"])
						elif "VLSR" in fitsHeader:
							curVal = float(fitsHeader["VLSR"])*1e3
						else:
							raise Warning("couldn't find the original reference velocity in the fits header..")
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrFix")
					val = float(settings["preprocess"][idxP+1])
					if not curVal == 0.0:
						log.info("first removing the old vel_lsr: %s" % curVal)
						expspec.x *= (1 - curVal/2.99792458e8) # revert old value
					log.info("applying vel_lsr = %s" % val)
					expspec.x *= (1 + val/2.99792458e8) # apply new value
				if "shiftX" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftX")
					val = float(settings["preprocess"][idxP+1])
					log.info("applying shiftX = %s" % val)
					expspec.x += val
				if "shiftY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y += val
				if "scaleY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("scaleY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y *= val
				if "clipTopY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipTopY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, None, val)
				if "clipBotY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipBotY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, val, None)
				if "clipAbsY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipAbsY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, -val, val)
				if "wienerY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("wienerY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y -= Filters.get_wiener(expspec.y, val)
				if "medfiltY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("medfiltY")
					val = int(settings["preprocess"][idxP+1])
					expspec.y = scipy.signal.medfilt(expspec.y, val)
				if "ffbutterY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("ffbutterY")
					ford = int(settings["preprocess"][idxP+1])
					ffreq = float(settings["preprocess"][idxP+2])
					b, a = scipy.signal.butter(ford, ffreq, btype='low', analog=False, output='ba')
					expspec.y = scipy.signal.filtfilt(b, a, expspec.y, padlen=20)
			if settings["filetype"]=="fid":
				reload(spectrum)
				if len(settings["delimiter"]):
					xcol, ycol = (1,2)
					if settings["xcol"]:
						xcol = settings["xcol"]
					if settings["ycol"]:
						ycol = settings["ycol"]
					log.info(xcol, ycol)
					delimiter = settings["delimiter"]
					fidxy = spectrum.load_spectrum(
						fileIn, ftype="arbdelim",
						skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
						delimiter=delimiter)
				else:
					log.warning("you did not specify a delimiter, so this assumes they are spaces")
					fidxy = spectrum.load_spectrum(fileIn, ftype="xydata")
				fidspec = spectrum.TimeDomainSpectrum(fidxy.x, fidxy.y)
				fidspec.calc_amplitude_spec(
					window_function=settings["fftType"],
					time_start=float(settings["fidStart"]),
					time_stop=float(settings["fidStop"]))
				expspec = spectrum.Spectrum(x=fidspec.u_spec_win_x, y=fidspec.u_spec_win_y)
				expspec.if_x = expspec.x.copy()
				expspec.rest_x =  expspec.if_x.copy() + float(settings["fidLO"])*1e9
				expspec.image_x = -1*expspec.if_x.copy() + float(settings["fidLO"])*1e9
				if settings["fftSideband"] == "upper":
					expspec.x = expspec.rest_x
				elif settings["fftSideband"] == "lower":
					expspec.x = expspec.image_x
				elif settings["fftSideband"] == "both":
					expspec.x = np.asarray(expspec.image_x.tolist() + expspec.rest_x.tolist())
					expspec.y = np.asarray(expspec.y.tolist() + expspec.y.tolist())
				expspec.x /= 1e6
			if settings["unit"] == "GHz":
				expspec.x *= 1e3
			elif not settings["unit"] == "MHz":
				self.ESplotFigure.getAxis('bottom').setScale(scale=1)
				if settings["unit"] == "cm-1":
					self.ESplotFigure.setLabel('bottom', "Wavenumber", units=settings["unit"])
					self.ESplotFigure.getPlotItem().vb.invertX(True)
				elif settings["unit"] in ["s","ms"]:
					self.ESplotFigure.setLabel('bottom', "Time", units=settings["unit"][-1])
				elif settings["unit"] == "mass amu":
					self.ESplotFigure.setLabel('bottom', "Mass", units="amu")
				elif settings["unit"][0] == u"μ":
					self.ESplotFigure.setLabel('bottom', "Wavelength", units=settings["unit"][1:])
				if settings["unit"] == "ms":
					expspec.x /= 1e3
				elif settings["unit"][0] == u"μ":
					expspec.x /= 1e6
			self.ESplotData["x"] += expspec.x.tolist()
			self.ESplotData["y"] += expspec.y.tolist()
		# sort by x
		self.ESplotData["x"], self.ESplotData["y"] = list(zip(*sorted(zip(self.ESplotData["x"], self.ESplotData["y"]))))
		# back to ndarray if necessary
		if not any([isinstance(self.ESplotData[data], type(np.array([]))) for data in ["x","y"]]):
			self.ESplotData["x"] = np.asarray(self.ESplotData["x"])
			self.ESplotData["y"] = np.asarray(self.ESplotData["y"])
		# update plot and GUI elements
		self.ESplot.setData(self.ESplotData["x"],self.ESplotData["y"])
		self.ESplot.update()
		self.ESupdateStatsAll()
	def EScopyScan(self):
		"""
		Copies the dataset to the clipboard.
		"""
		self.ESplot.copy()
	def ESpasteScan(self):
		"""
		Pastes a dataset directly from the clipboard.
		"""
		# grab clipboard contents
		clipboard = unicode(QtGui.QApplication.clipboard().text())
		# try to determine data format
		if all(',' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a csv")
			ftype = "csv"
		elif all('\t' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a tsv")
			ftype = "tsv"
		else:
			log.info("pasting what is not csv or tsv, and therefore assuming ssv")
			ftype = "ssv"
		# write out to temporary file
		fname='clipboard (%s).%s' % (time.strftime("%Y-%m-%d %H:%M:%S"), ftype)
		fname = os.path.join(self.tmpDir, fname)
		fd = codecs.open(fname, encoding='utf-8', mode='w+')
		fd.write(clipboard)
		fd.close()
		# now load using the standard function..
		settings = self.defaultLoadSettings.copy()
		settings["filetype"] = ftype
		self.ESloadScan(filenames=[fname], settings=settings)
		# update plot and GUI elements
		self.ESplot.setData(self.ESplotData["x"],self.ESplotData["y"])
		self.ESplot.update()
		self.ESupdateStatsAll()
		
	def ESclearPlot(self):
		"""
		Clears the data from memory, and completely clears the plot.
		"""
		self.ESplot.clear()
		self.ESplotData = {"x":[], "y":[]}
		self.ESclearPlotLabels()
	def ESclearPlotLabels(self):
		"""
		Clears all the rectangular ROIs that may be created via SHIFT+CLICK.
		"""
		# mouse labels
		if len(self.ESplotLabels):
			for label in self.ESplotLabels:
				self.ESplotFigure.removeItem(label[0])
				self.ESplotFigure.removeItem(label[1])
		self.ESplotLabels = []
		# boxes
		if len(self.ESplotBoxes):
			for box in self.ESplotBoxes:
				self.ESplotFigure.removeItem(box)
		self.ESplotBoxes = []
		# update stats, based on new (disappeared) labels
		self.ESupdateStatsAll()

	def ESupdateStatsAll(self):
		"""
		Updates all the stats for the various windows, by calling their
		respective routines in one-by-one.
		"""
		self.ESupdateStatsData()
		self.ESupdateStatsWin1()
		self.ESupdateStatsWin2()
	def ESupdateStatsData(self):
		"""
		Updates the general stats about the loaded data
		"""
		if (not len(self.ESplotData["x"])) or (not self.ESplotData["x"].size):
			self.txt_ESlengthData.clear()
			self.txt_ESxminData.clear()
			self.txt_ESxmaxData.clear()
			self.txt_ESyminData.clear()
			self.txt_ESymaxData.clear()
			return
		length = self.ESplotData["x"].size
		xmin = np.nanmin(self.ESplotData["x"])
		xmax = np.nanmax(self.ESplotData["x"])
		ymin = np.nanmin(self.ESplotData["y"])
		ymax = np.nanmax(self.ESplotData["y"])
		self.txt_ESlengthData.setText("%g3" % length)
		self.txt_ESxminData.setText("%.3f" % xmin)
		self.txt_ESxmaxData.setText("%.3f" % xmax)
		self.txt_ESyminData.setText("%.3f" % ymin)
		self.txt_ESymaxData.setText("%.3f" % ymax)

	def ESupdateStatsWin1(self):
		"""
		Updates the stats for the data within window1
		"""
		if (not len(self.ESplotBoxes)) or (not len(self.ESplotData["x"])) or (not self.ESplotData["x"].size):
			self.txt_ESlength1.clear()
			self.txt_ESxmin1.clear()
			self.txt_ESxmax1.clear()
			self.txt_ESymin1.clear()
			self.txt_ESymax1.clear()
			self.txt_ESyavg1.clear()
			self.txt_ESysigma1.clear()
			return
		lowerX, upperX = self.ESplotBoxes[0].getRegion()
		lowerIdx = np.abs(self.ESplotData["x"] - lowerX).argmin()
		upperIdx = np.abs(self.ESplotData["x"] - upperX).argmin()
		length = self.ESplotData["x"][lowerIdx:upperIdx].size
		xmin = np.nanmin(self.ESplotData["x"][lowerIdx:upperIdx])
		xmax = np.nanmax(self.ESplotData["x"][lowerIdx:upperIdx])
		ymin = np.nanmin(self.ESplotData["y"][lowerIdx:upperIdx])
		ymax = np.nanmax(self.ESplotData["y"][lowerIdx:upperIdx])
		yavg = np.nanmean(self.ESplotData["y"][lowerIdx:upperIdx])
		ysigma = np.nanstd(self.ESplotData["y"][lowerIdx:upperIdx])
		self.txt_ESlength1.setText("%g3" % length)
		self.txt_ESxmin1.setText("%.3f" % xmin)
		self.txt_ESxmax1.setText("%.3f" % xmax)
		self.txt_ESymin1.setText("%.3f" % ymin)
		self.txt_ESymax1.setText("%.3f" % ymax)
		self.txt_ESyavg1.setText("%.6e" % yavg)
		self.txt_ESysigma1.setText("%.4e" % ysigma)
	def ESupdateStatsWin2(self):
		"""
		Updates the stats for the data within window2
		"""
		if (not (len(self.ESplotBoxes) == 2)) or (not len(self.ESplotData["x"])) or (not self.ESplotData["x"].size):
			self.txt_ESlength2.clear()
			self.txt_ESxmin2.clear()
			self.txt_ESxmax2.clear()
			self.txt_ESymin2.clear()
			self.txt_ESymax2.clear()
			self.txt_ESyavg2.clear()
			self.txt_ESysigma2.clear()
			return
		lowerX, upperX = self.ESplotBoxes[1].getRegion()
		lowerIdx = np.abs(self.ESplotData["x"] - lowerX).argmin()
		upperIdx = np.abs(self.ESplotData["x"] - upperX).argmin()
		length = self.ESplotData["x"][lowerIdx:upperIdx].size
		xmin = np.nanmin(self.ESplotData["x"][lowerIdx:upperIdx])
		xmax = np.nanmax(self.ESplotData["x"][lowerIdx:upperIdx])
		ymin = np.nanmin(self.ESplotData["y"][lowerIdx:upperIdx])
		ymax = np.nanmax(self.ESplotData["y"][lowerIdx:upperIdx])
		yavg = np.nanmean(self.ESplotData["y"][lowerIdx:upperIdx])
		ysigma = np.nanstd(self.ESplotData["y"][lowerIdx:upperIdx])
		self.txt_ESlength2.setText("%g3" % length)
		self.txt_ESxmin2.setText("%.3f" % xmin)
		self.txt_ESxmax2.setText("%.3f" % xmax)
		self.txt_ESymin2.setText("%.3f" % ymin)
		self.txt_ESymax2.setText("%.3f" % ymax)
		self.txt_ESyavg2.setText("%.6e" % yavg)
		self.txt_ESysigma2.setText("%.4e" % ysigma)

	def ESplotMousePosition(self, mouseEvent):
		"""
		This is the function that is called each time the mouse cursor
		moves above the plot.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(PyQt4.QtCore.QPointF, None)
		"""
		# process keyboard modifiers and perform appropriate action
		modifier = QtGui.QApplication.keyboardModifiers()
		if modifier == QtCore.Qt.ShiftModifier:
			# convert mouse coordinates to XY wrt the plot
			mousePos = self.ESplot.getViewBox().mapSceneToView(mouseEvent[0])
			mouseX, mouseY = mousePos.x(), mousePos.y()
			if len(self.ESplotData["x"]) > 0:
				HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'>x=%.3f"
				HTMLCoordinates += "<br>y=%g</span></div>"
				idx = np.abs(self.ESplotData["x"] - mouseX).argmin()
				m_freq = self.ESplotData["x"][idx]
				m_int = self.ESplotData["y"][idx]
				self.ESplotMouseLabel.setPos(mouseX, mouseY)
				self.ESplotMouseLabel.setHtml(HTMLCoordinates % (m_freq, m_int))
			else:
				self.ESplotMouseLabel.setPos(mouseX, mouseY)
				self.ESplotMouseLabel.setText("\n%.3f\n%g" % (mouseX,mouseY))
		else:
			self.ESplotMouseLabel.setPos(0,0)
			self.ESplotMouseLabel.setText("")
	def ESplotMouseClicked(self, mouseEvent):
		"""
		This is the function that is called each time the mouse button
		is clicked on the plot.

		It first processes the coordinates of the click, and some bounding
		ranges around these coordinates. Then it checks what modifying
		buttons may be active (i.e. CTRL, ALT or SHIFT), and possibly
		performs additional things.

		:param mouseEvent: the mouse event that is sent by the PlotWidget signal
		:type mouseEvent: tuple(pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent, None)
		"""
		# convert mouse coordinates to XY wrt the plot
		mousePos = mouseEvent[0].scenePos()
		viewBox = self.ESplot.getViewBox()
		mousePos = viewBox.mapSceneToView(mousePos)
		mousePos = (mousePos.x(), mousePos.y())
		modifier = QtGui.QApplication.keyboardModifiers()
		# add a label if SHIFT
		if modifier == QtCore.Qt.ShiftModifier:
			HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 13pt'>x=%.3f"
			HTMLCoordinates += "<br>y=%0.2e</span></div>"
			labelDot = pg.TextItem(text="*",anchor=(0.5,0.5))
			labelDot.setPos(mousePos[0], mousePos[1])
			labelDot.setZValue(999)
			self.ESplotFigure.addItem(labelDot, ignoreBounds=True)
			labelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
			labelText.setPos(mousePos[0], mousePos[1])
			labelText.setHtml(HTMLCoordinates % (mousePos[0], mousePos[1]))
			labelText.setZValue(999)
			self.ESplotFigure.addItem(labelText, ignoreBounds=True)
			self.ESplotLabels.append((labelDot,labelText))
		# add a region if CTRL
		elif modifier == QtCore.Qt.ControlModifier:
			# define bounds that are +/- some range around the cursor
			xRange = viewBox.viewRange()[0][1] - viewBox.viewRange()[0][0]
			lowerX = mousePos[0] - 0.025*xRange
			upperX = mousePos[0] + 0.025*xRange
			yRange = viewBox.viewRange()[1][1] - viewBox.viewRange()[1][0]
			lowerY = mousePos[1] - 0.1*yRange
			upperY = mousePos[1] + 0.1*yRange
			if len(self.ESplotBoxes) == 2:
				self.ESplotFigure.removeItem(self.ESplotBoxes[1])
				self.ESplotBoxes = [self.ESplotBoxes[0]]
			self.ESplotBoxes.append(pg.LinearRegionItem())
			self.ESplotBoxes[-1].setRegion((lowerX, upperX))
			self.ESplotFigure.addItem(self.ESplotBoxes[-1], ignoreBounds=True)
			if len(self.ESplotBoxes) == 1:
				self.ESplotBoxes[-1].sigRegionChanged.connect(self.ESupdateStatsWin1)
			elif len(self.ESplotBoxes) == 2:
				self.ESplotBoxes[-1].sigRegionChanged.connect(self.ESupdateStatsWin2)


	### BR tab
	# top plot functionality
	def BRinitPlotTop(self):
		"""
		Initializes the top plot, which is used for loading a dataset and
		(optionally) defining regions that force straight-lined baseline
		corrections.
		"""
		# figure properties
		self.BRplotTopFigure.setLabel('left', "Intensity", units='V', **self.labelStyle)
		self.BRplotTopFigure.setLabel('bottom', "Frequency", units='Hz', **self.labelStyle)
		self.BRplotTopFigure.getAxis('bottom').setScale(scale=1e6)
		self.BRplotTopFigure.getAxis('left').tickFont = self.tickFont
		self.BRplotTopFigure.getAxis('bottom').tickFont = self.tickFont
		self.BRplotTopFigure.getAxis('bottom').setStyle(**{'tickTextOffset':5})
		# plot
		self.BRplotTopPlot = Widgets.SpectralPlot(
			name='top', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.BRplotTopFigure.addItem(self.BRplotTopPlot)
		# signals
		self.BRplotTopMouseLabel = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
		self.BRplotTopMouseLabel.setZValue(999)
		self.BRplotTopFigure.addItem(self.BRplotTopMouseLabel, ignoreBounds=True)
		self.BRplotTopMouseMoveSignal = pg.SignalProxy(
			self.BRplotTopPlot.scene().sigMouseMoved,
			rateLimit=15,
			slot=self.BRplotTopMousePosition)
		self.BRplotTopSigMouseClick = pg.SignalProxy(
			self.BRplotTopPlot.scene().sigMouseClicked,
			rateLimit=10,
			slot=self.BRplotTopMouseClicked)
		# menu entry for copying to clipboard
		self.BRplotTopPlot.getViewBox().menu.addSeparator()
		copy = self.BRplotTopPlot.getViewBox().menu.addAction("copy spectrum")
		copy.triggered.connect(self.BRplotTopPlot.copy)

	def BRloadScan(self, mouseEvent=False, filenames=[], settings={}):
		"""
		Loads a dataset directly into memory.

		:param mouseEvent: (optional) the mouse event from a click
		:param filenames: (optional) a list of files to load, bypassing the selection dialog
		:param settings: (optional) settings to use for loading spectra
		:type mouseEvent: QtGui.QMouseEvent
		:type filenames: list
		:type settings: dict
		"""
		reload(spectrum)
		if not len(filenames):
			# provide dialog
			if not "BRloadDialog" in vars(self):
				self.BRloadDialog = Dialogs.SpecLoadDialog(self)
			if not self.BRloadDialog.exec_():
				return
			else:
				settings = self.BRloadDialog.getValues()
			# get file
			filenames = settings["filenames"]
		if not any([os.path.isfile(f) for f in filenames]):
			raise IOError("could not locate one of the requested input files!")
		self.cwd = os.path.realpath(os.path.dirname(filenames[-1]))
		# if no settings, do some guesswork..
		if settings == {}:
			settings = self.defaultLoadSettings.copy()
		if settings["filetype"] is None:
			settings["filetype"] = spectrum.guess_filetype(filename=filenames)
			log.debug("guessed the filetype(s) should be: %s" % args.filetype)
			if settings["filetype"] is None:
				raise SyntaxError("could not determine the filetype, so you should fix this..")
		# sanity check about: multiple files but not appending them
		if (not settings["appendData"]) and (len(filenames) > 1):
			raise SyntaxError("you cannot load multiple files without appending them!")
		# reset the plots & data
		if not settings["appendData"]:
			self.BRclearPlotTop()
			self.BRclearPlotBoxes()
			self.BRclearPlotLines()
			self.BRclearPlotBottom()
			self.BRplotTopData = {"x":[], "y":[], "spec":[]}
			if settings["unit"]=="arb.":
				self.BRplotTopFigure.setLabel('bottom', "Frequency", units='arb')
				self.BRplotBottomFigure.setLabel('bottom', "Frequency", units='arb')
				self.BRplotTopFigure.getAxis('bottom').setScale(scale=1)
				self.BRplotBottomFigure.getAxis('bottom').setScale(scale=1)
			else:
				self.BRplotTopFigure.setLabel('bottom', "Frequency", units='Hz')
				self.BRplotBottomFigure.setLabel('bottom', "Frequency", units='Hz')
				self.BRplotTopFigure.getAxis('bottom').setScale(scale=1e6)
				self.BRplotBottomFigure.getAxis('bottom').setScale(scale=1e6)
		elif isinstance(self.BRplotTopData["x"], type(np.array([]))):
			self.BRplotTopData["x"] = self.BRplotTopData["x"].copy().tolist()
			self.BRplotTopData["y"] = self.BRplotTopData["y"].copy().tolist()
		# loop through it and push to memory
		for fileIn in filenames:
			if settings["filetype"] in ["ssv", "tsv", "csv", "casac", "gesp", "ydata"]:
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					skipFirst=settings["skipFirst"])
			elif settings["filetype"]=="jpl":
				if not settings["scanIndex"]:
					settings["scanIndex"] = 1
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (#%g)" % settings["scanIndex"]
			elif settings["filetype"]=="fits":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
			elif settings["filetype"]=="arbdc":
				delimiter = settings["delimiter"]
				xcol = settings["xcol"]
				ycol = settings["ycol"]
				expspec = spectrum.load_spectrum(
					fileIn, ftype="arbdelim",
					skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
					delimiter=delimiter)
			elif settings["filetype"]=="arbs":
				raise NotImplementedError
			elif settings["filetype"] == "brukeropus":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (%s)" % expspec.h['block_key']
			elif settings["filetype"] == "batopt3ds":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"])
			elif settings["filetype"]=="fid":
				pass    # works on this AFTER preprocess
			else:
				raise NotImplementedError("not sure what to do with filetype %s" % settings["filetype"])
			if ("preprocess" in settings) and (settings["preprocess"] is not None):
				expspec.xOrig = expspec.x.copy()
				expspec.yOrig = expspec.y.copy()
				if "vlsrShift" in settings["preprocess"]:
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrShift")
					val = float(settings["preprocess"][idxP+1])
					expspec.x *= (1 + val/2.99792458e8)
				if "vlsrFix" in settings["preprocess"]:
					curVal = 0
					if settings["filetype"]=="fits":
						fitsHeader = expspec.hdu.header
						if "VELO-LSR" in fitsHeader:
							curVal = float(fitsHeader["VELO-LSR"])
						elif "VELO" in fitsHeader:
							curVal = float(fitsHeader["VELO"])
						elif "VELREF" in fitsHeader:
							curVal = float(fitsHeader["CRVAL1"])
						elif "VLSR" in fitsHeader:
							curVal = float(fitsHeader["VLSR"])*1e3
						else:
							raise Warning("couldn't find the original reference velocity in the fits header..")
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrFix")
					val = float(settings["preprocess"][idxP+1])
					if not curVal == 0.0:
						log.info("first removing the old vel_lsr: %s" % curVal)
						expspec.x *= (1 - curVal/2.99792458e8) # revert old value
					log.info("applying vel_lsr = %s" % val)
					expspec.x *= (1 + val/2.99792458e8) # apply new value
				if "shiftX" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftX")
					val = float(settings["preprocess"][idxP+1])
					log.info("applying shiftX = %s" % val)
					expspec.x += val
				if "shiftY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y += val
				if "scaleY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("scaleY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y *= val
				if "clipTopY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipTopY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, None, val)
				if "clipBotY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipBotY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, val, None)
				if "clipAbsY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipAbsY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, -val, val)
				if "wienerY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("wienerY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y -= Filters.get_wiener(expspec.y, val)
				if "medfiltY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("medfiltY")
					val = int(settings["preprocess"][idxP+1])
					expspec.y = scipy.signal.medfilt(expspec.y, val)
				if "ffbutterY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("ffbutterY")
					ford = int(settings["preprocess"][idxP+1])
					ffreq = float(settings["preprocess"][idxP+2])
					b, a = scipy.signal.butter(ford, ffreq, btype='low', analog=False, output='ba')
					expspec.y = scipy.signal.filtfilt(b, a, expspec.y, padlen=20)
			if settings["filetype"]=="fid":
				reload(spectrum)
				if len(settings["delimiter"]):
					xcol, ycol = (1,2)
					if settings["xcol"]:
						xcol = settings["xcol"]
					if settings["ycol"]:
						ycol = settings["ycol"]
					log.info(xcol, ycol)
					delimiter = settings["delimiter"]
					fidxy = spectrum.load_spectrum(
						fileIn, ftype="arbdelim",
						skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
						delimiter=delimiter)
				else:
					log.warning("you did not specify a delimiter, so this assumes they are spaces")
					fidxy = spectrum.load_spectrum(fileIn, ftype="xydata")
				fidspec = spectrum.TimeDomainSpectrum(fidxy.x, fidxy.y)
				fidspec.calc_amplitude_spec(
					window_function=settings["fftType"],
					time_start=float(settings["fidStart"]),
					time_stop=float(settings["fidStop"]))
				expspec = spectrum.Spectrum(x=fidspec.u_spec_win_x, y=fidspec.u_spec_win_y)
				expspec.if_x = expspec.x.copy()
				expspec.rest_x =  expspec.if_x.copy() + float(settings["fidLO"])*1e9
				expspec.image_x = -1*expspec.if_x.copy() + float(settings["fidLO"])*1e9
				if settings["fftSideband"] == "upper":
					expspec.x = expspec.rest_x
				elif settings["fftSideband"] == "lower":
					expspec.x = expspec.image_x
				elif settings["fftSideband"] == "both":
					expspec.x = np.asarray(expspec.image_x.tolist() + expspec.rest_x.tolist())
					expspec.y = np.asarray(expspec.y.tolist() + expspec.y.tolist())
				expspec.x /= 1e6
			if settings["unit"] == "GHz":
				expspec.x *= 1e3
			elif not settings["unit"] == "MHz":
				self.BRplotTopFigure.getAxis('bottom').setScale(scale=1)
				self.BRplotBottomFigure.getAxis('bottom').setScale(scale=1)
				if settings["unit"] == "cm-1":
					self.BRplotTopFigure.setLabel('bottom', "Wavenumber", units=settings["unit"])
					self.BRplotTopFigure.getPlotItem().vb.invertX(True)
					self.BRplotBottomFigure.setLabel('bottom', "Wavenumber", units=settings["unit"])
					self.BRplotBottomFigure.getPlotItem().vb.invertX(True)
				elif settings["unit"] in ["s","ms"]:
					self.BRplotTopFigure.setLabel('bottom', "Time", units=settings["unit"][-1])
					self.BRplotBottomFigure.setLabel('bottom', "Time", units=settings["unit"][-1])
				elif settings["unit"] == "mass amu":
					self.BRplotTopFigure.setLabel('bottom', "Mass", units="amu")
					self.BRplotBottomFigure.setLabel('bottom', "Mass", units="amu")
				elif settings["unit"][0] == u"μ":
					self.BRplotTopFigure.setLabel('bottom', "Wavelength", units=settings["unit"][1:])
					self.BRplotBottomFigure.setLabel('bottom', "Wavelength", units=settings["unit"][1:])
				if settings["unit"] == "ms":
					expspec.x /= 1e3
				elif settings["unit"][0] == u"μ":
					expspec.x /= 1e6
			self.BRplotTopData["x"] += expspec.x.tolist()
			self.BRplotTopData["y"] += expspec.y.tolist()
			self.BRplotTopData["spec"].append(expspec)
		# sort by x
		self.BRplotTopData["x"], self.BRplotTopData["y"] = list(zip(*sorted(zip(self.BRplotTopData["x"], self.BRplotTopData["y"]))))
		# back to ndarray if necessary
		if not any([isinstance(self.BRplotTopData[data], type(np.array([]))) for data in ["x","y"]]):
			self.BRplotTopData["x"] = np.asarray(self.BRplotTopData["x"])
			self.BRplotTopData["y"] = np.asarray(self.BRplotTopData["y"])
		# update plot and GUI elements
		self.BRplotTopPlot.setData(self.BRplotTopData["x"],self.BRplotTopData["y"])
		self.BRplotTopPlot.update()
		self.txt_BRminX.setText("%.3e" % min(self.BRplotTopData["x"]))
		self.txt_BRmaxX.setText("%.3e" % max(self.BRplotTopData["x"]))
		self.txt_BRminY.setText("%.3e" % min(self.BRplotTopData["y"]))
		self.txt_BRmaxY.setText("%.3e" % max(self.BRplotTopData["y"]))
		self.txt_BRdataLength.setText("%s" % len(self.BRplotTopData["x"]))
		self.cb_BRgaussWin.setMaximum(len(self.BRplotTopData["x"]))
		self.cb_BRwienerWin.setMaximum(len(self.BRplotTopData["x"]))
		self.cb_BRsgWin.setMaximum(len(self.BRplotTopData["x"]))
		self.BRupdateBottomPlot()
		self.BRplotTopFigure.getPlotItem().enableAutoRange()
		self.BRplotBottomFigure.getPlotItem().enableAutoRange()
	def BRpasteScan(self):
		"""
		Pastes a dataset directly from the clipboard.
		"""
		self.BRclearPlotTop()
		self.BRclearPlotBoxes()
		# grab clipboard contents
		clipboard = unicode(QtGui.QApplication.clipboard().text())
		# try to determine data format
		if all(',' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a csv")
			ftype = "csv"
		elif all('\t' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a tsv")
			ftype = "tsv"
		else:
			log.info("pasting what is not csv or tsv, and therefore assuming ssv")
			ftype = "ssv"
		# write out to temporary file
		fname='clipboard (%s).%s' % (time.strftime("%Y-%m-%d %H:%M:%S"), ftype)
		fname = os.path.join(self.tmpDir, fname)
		fd = codecs.open(fname, encoding='utf-8', mode='w+')
		fd.write(clipboard)
		fd.close()
		# now load using the standard function..
		settings = self.defaultLoadSettings.copy()
		settings["filetype"] = ftype
		self.BRloadScan(filenames=[fname], settings=settings)
		# update plot and GUI elements
		self.BRplotTopFigure.setLabel('bottom', "Frequency", units='Hz')
		self.BRplotBottomFigure.setLabel('bottom', "Frequency", units='Hz')
		self.BRplotTopFigure.getAxis('bottom').setScale(scale=1e6)
		self.BRplotBottomFigure.getAxis('bottom').setScale(scale=1e6)
		self.BRplotTopPlot.setData(self.BRplotTopData["x"],self.BRplotTopData["y"])
		self.BRplotTopPlot.update()
		self.txt_BRminX.setText("%.3e" % min(self.BRplotTopData["x"]))
		self.txt_BRmaxX.setText("%.3e" % max(self.BRplotTopData["x"]))
		self.txt_BRminY.setText("%.3e" % min(self.BRplotTopData["y"]))
		self.txt_BRmaxY.setText("%.3e" % max(self.BRplotTopData["y"]))
		self.txt_BRdataLength.setText("%s" % len(self.BRplotTopData["x"]))
		#self.cb_BRlowpassRolloff.setSingleStep(float(len(self.BRplotTopData["x"])/2.0*1e-8))
		self.cb_BRgaussWin.setMaximum(len(self.BRplotTopData["x"]))
		self.cb_BRwienerWin.setMaximum(len(self.BRplotTopData["x"]))
		self.cb_BRsgWin.setMaximum(len(self.BRplotTopData["x"]))
		self.BRupdateBottomPlot()
		self.BRplotTopFigure.getPlotItem().enableAutoRange()
		self.BRplotBottomFigure.getPlotItem().enableAutoRange()

	def BRclearPlotTop(self):
		"""
		Clears the data from memory, and completely clears the plot.
		"""
		self.BRplotTopPlot.clear()
		self.BRplotTopData = {"x":[], "y":[], "spec":[]}
	def BRclearPlotBoxes(self):
		"""
		Clears all the rectangular ROIs that may be created via SHIFT+CLICK.
		"""
		if len(self.BRplotBoxes):
			for box in self.BRplotBoxes:
				self.BRplotTopFigure.removeItem(box)
		self.BRplotBoxes = []
	def BRclearPlotLines(self):
		"""
		Clears all the straight lines that may be created via CTRL+CLICK
		and dragged with the mouse.
		"""
		if len(self.BRplotLines):
			for line in self.BRplotLines:
				self.BRplotTopFigure.removeItem(line)
		self.BRplotLines = []

	def BRshowHeader(self):
		"""
		Opens a window to show the header information for the experimental spectrum.
		"""
		if not self.BRplotTopData["spec"]:
			return
		header = []
		for s in self.BRplotTopData["spec"]:
			try:
				header += s.ppheader
			except AttributeError:
				header += ["(blank)"]
		self.BRexpHeaderWindows.append(Widgets.HeaderViewer(self, header))
		self.BRexpHeaderWindows[-1].show()

	def BRplotTopMousePosition(self, mouseEvent):
		"""
		This is the function that is called each time the mouse cursor
		moves above the top plot.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(PyQt4.QtCore.QPointF, None)
		"""
		# process keyboard modifiers and perform appropriate action
		modifier = QtGui.QApplication.keyboardModifiers()
		if modifier in (QtCore.Qt.ShiftModifier, QtCore.Qt.ControlModifier):
			# convert mouse coordinates to XY wrt the plot
			mousePos = self.BRplotTopPlot.getViewBox().mapSceneToView(mouseEvent[0])
			mouseX, mouseY = mousePos.x(), mousePos.y()
			if len(self.BRplotTopData["x"]) > 0:
				HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'>x=%.3f"
				HTMLCoordinates += "<br>y=%g</span></div>"
				idx = np.abs(self.BRplotTopData["x"] - mouseX).argmin()
				m_freq = self.BRplotTopData["x"][idx]
				m_int = self.BRplotTopData["y"][idx]
				self.BRplotTopMouseLabel.setPos(mouseX, mouseY)
				self.BRplotTopMouseLabel.setHtml(HTMLCoordinates % (m_freq, m_int))
			else:
				self.BRplotTopMouseLabel.setPos(mouseX, mouseY)
				self.BRplotTopMouseLabel.setText("%.3f\n%g" % (mouseX,mouseY))
		else:
			self.BRplotTopMouseLabel.setPos(0,0)
			self.BRplotTopMouseLabel.setText("")
	def BRplotTopMouseClicked(self, mouseEvent):
		"""
		This is the function that is called each time the mouse button
		is clicked on the top plot.

		It first processes the coordinates of the click, and some bounding
		ranges around these coordinates. Then it checks what modifying
		buttons may be active (i.e. CTRL, ALT or SHIFT), and possibly
		performs additional things.

		:param mouseEvent: the mouse event that is sent by the PlotWidget signal
		:type mouseEvent: tuple(pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent, None)
		"""
		# convert mouse coordinates to XY wrt the plot
		mousePos = mouseEvent[0].scenePos()
		viewBox = self.BRplotTopPlot.getViewBox()
		mousePos = viewBox.mapSceneToView(mousePos)
		mousePos = (mousePos.x(), mousePos.y())
		modifier = QtGui.QApplication.keyboardModifiers()
		# add a region if SHIFT
		if modifier == QtCore.Qt.ShiftModifier:
			# define bounds that are +/- some range around the cursor
			xRange = viewBox.viewRange()[0][1] - viewBox.viewRange()[0][0]
			lowerX = mousePos[0] - 0.025*xRange
			upperX = mousePos[0] + 0.025*xRange
			yRange = viewBox.viewRange()[1][1] - viewBox.viewRange()[1][0]
			lowerY = mousePos[1] - 0.1*yRange
			upperY = mousePos[1] + 0.1*yRange
			#### windowed region
			#self.plotBoxes.append(pg.LinearRegionItem())
			#self.plotBoxes[-1].setRegion((lowerX, upperX))
			#self.plotTopFigure.addItem(self.plotBoxes[-1], ignoreBounds=True)
			### rectangular ROI
			self.BRplotBoxes.append(pg.RectROI(
				[lowerX,lowerY],
				[xRange*0.05,yRange*0.2],
				pen=(0,9)))
			self.BRplotTopFigure.addItem(self.BRplotBoxes[-1], ignoreBounds=True)
		# add a line if CTRL
		elif modifier == QtCore.Qt.ControlModifier:
			### add linear ROI
			#self.plotLineStart
			#y = mousePos[1]
			#self.plotLines.append(pg.LineSegmentROI(
			#	[[lowerX,y], [upperX,y]],
			#	pen='r'))
			#self.plotTopFigure.addItem(self.plotLines[-1], ignoreBounds=True)
			### add handles ONEbyONE! (based on the data that is loaded)
			x,y = mousePos
			if len(self.BRplotTopData['x']): # prevents an exception
				idx = np.abs(x - self.BRplotTopData['x']).argmin()
				x = self.BRplotTopData['x'][idx]
				y = self.BRplotTopData['y'][idx]
			if self.BRplotLineStart:
				self.BRplotLines.append(pg.LineSegmentROI(
					[self.BRplotLineStart, [x,y]],
					pen='r'))
				self.BRplotTopFigure.addItem(self.BRplotLines[-1], ignoreBounds=True)
				self.BRplotLineStart = 0
			else:
				self.BRplotLineStart = [x,y]

	# bottom plot functionality
	def BRinitPlotBottom(self):
		"""
		Initializes the bottom plot, which is used for viewing the data
		after filtering/baseline-corrections, (optionally) defining
		window(s) for choosing a subset of the data, and finally invoking
		child windows that may be used for fitting spectral lines.
		"""
		# figure properties
		self.BRplotBottomFigure.setLabel('left', "Intensity", units='V', **self.labelStyle)
		self.BRplotBottomFigure.setLabel('bottom', "Frequency", units='Hz', **self.labelStyle)
		self.BRplotBottomFigure.getAxis('bottom').setScale(scale=1e6)
		self.BRplotBottomFigure.getAxis('left').tickFont = self.tickFont
		self.BRplotBottomFigure.getAxis('bottom').tickFont = self.tickFont
		self.BRplotBottomFigure.getAxis('bottom').setStyle(**{'tickTextOffset':5})
		# plot
		self.BRplotBottomPlot = Widgets.SpectralPlot(
			name='bottom', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.BRplotBottomFigure.addItem(self.BRplotBottomPlot)
		# signals
		self.BRplotBottomSigMouseMove = pg.SignalProxy(
			self.BRplotBottomPlot.scene().sigMouseMoved,
			rateLimit=30,
			slot=self.BRplotBottomMousePosition)
		self.BRplotBottomSigMouseClick = pg.SignalProxy(
			self.BRplotBottomPlot.scene().sigMouseClicked,
			rateLimit=10,
			slot=self.BRplotBottomMouseClicked)
		# misc
		self.cb_BRwindow.setMaximum(0)
		self.BRplotBottomMouseLabelXY = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
		self.BRplotBottomMouseLabelXY.setZValue(999)
		self.BRplotBottomFigure.addItem(self.BRplotBottomMouseLabelXY, ignoreBounds=True)
		self.BRplotBottomMouseLabelWindow = pg.TextItem(text="",anchor=(0.5,1))
		self.BRplotBottomMouseLabelWindow.setZValue(999)
		self.BRplotBottomFigure.addItem(self.BRplotBottomMouseLabelWindow, ignoreBounds=True)
		# menu entry for copying to clipboard
		self.BRplotBottomPlot.getViewBox().menu.addSeparator()
		copy = self.BRplotBottomPlot.getViewBox().menu.addAction("copy spectrum")
		copy.triggered.connect(self.BRcopyScan)
	def BRupdateBottomPlot(self):
		"""
		Updates the bottom plot, based on any filters/baseline-corrections
		that may be active.

		Note that this is called directly whenever any of the elements
		are activated on the righthand-side of the bottom plot.
		"""
		if not len(self.BRplotTopData["x"]):
			return
		# copy data to new lists
		self.BRplotBottomData["x"] = self.BRplotTopData["x"].copy()
		self.BRplotBottomData["y"]  = self.BRplotTopData["y"].copy()
		# remove all data points within the boxes
		if len(self.BRplotBoxes):
			self.BRplotBottomData["x"] = self.BRplotTopData["x"].tolist()
			self.BRplotBottomData["y"]  = self.BRplotTopData["y"].tolist()
			for roi in self.BRplotBoxes:
				# get bounds of box
				lowerX = roi.pos().x()
				lowerY = roi.pos().y()
				upperX = roi.pos().x() + roi.size().x()
				upperY = roi.pos().y() + roi.size().y()
				# find list of indexes within the box
				xVals = np.asarray(self.BRplotBottomData["x"]) # ensures the indexing is updated for each box
				idxWithin = np.where((xVals >= lowerX) & (xVals <= upperX))[0].tolist()
				# loop (REVERSED!) through each index and remove it from the list
				for idx in reversed(idxWithin):
					yVal = self.BRplotBottomData["y"][idx]
					if (yVal >= lowerY) and (yVal <= upperY):
						del self.BRplotBottomData["x"][idx]
						del self.BRplotBottomData["y"][idx]
			self.BRplotBottomData["x"] = np.asarray(self.BRplotBottomData["x"])
			self.BRplotBottomData["y"]  = np.asarray(self.BRplotBottomData["y"])
		# for each line, create list for masking, and make fast-callable bounds
		lineRegions = []
		lineHandles = []
		if len(self.BRplotLines):
			for lineROI in self.BRplotLines:
				lineRegions.append({'idx':[], 'newY':[]})
				lineHandles.append([0,0])
			# set the correct direction of all the lines
			viewBox = self.BRplotTopPlot.getViewBox()
			for k,lineROI in enumerate(self.BRplotLines):
				handleFirst = viewBox.mapSceneToView(lineROI.getSceneHandlePositions()[0][1])
				handleSecond = viewBox.mapSceneToView(lineROI.getSceneHandlePositions()[1][1])
				if handleFirst.x() > handleSecond.x():
					self.BRplotLines[k].rotate(180)
					lineHandles[k][0] = handleSecond
					lineHandles[k][1] = handleFirst
				else:
					lineHandles[k][0] = handleFirst
					lineHandles[k][1] = handleSecond
		# add line masks
		if len(self.BRplotLines):
			for k,lineROI in enumerate(self.BRplotLines):
				lowerX,lowerY = (lineHandles[k][0].x(),lineHandles[k][0].y())
				upperX,upperY = (lineHandles[k][1].x(),lineHandles[k][1].y())
				lineInterp = interpolate.interp1d([lowerX,upperX],[lowerY,upperY])
				# get indices from data
				lowerIdx = np.abs(self.BRplotBottomData["x"] - lowerX).argmin()
				upperIdx = np.abs(self.BRplotBottomData["x"] - upperX).argmin()
				if self.BRplotBottomData["x"][lowerIdx] < lowerX: lowerIdx += 1
				if self.BRplotBottomData["x"][upperIdx] > upperX: upperIdx -= 1
				for idx in range(lowerIdx,upperIdx+1):
					x = self.BRplotBottomData["x"][idx]
					# find line & new y-values
					linearY = lineInterp(x)
					newY = self.BRplotBottomData["y"][idx] - linearY
					# back-up new y-value & add mask
					lineRegions[k]['idx'].append(idx)
					lineRegions[k]['newY'].append(newY)
					if self.check_BRfilterLines.isChecked():
						linearY = newY
					self.BRplotBottomData["y"][idx] = linearY
		# get filter result
		yFilter = self.BRplotBottomData["y"]
		if (self.cb_BRlowpassOrd.value() > 0) and (self.txt_BRlowpassRolloff.value() > 0):
			yFilter = Filters.get_lowpass(yFilter, self.cb_BRlowpassOrd.value(), self.txt_BRlowpassRolloff.value())
		if self.cb_BRgaussWin.value() > 0:
			sig = 10
			if not self.cb_BRgaussSig.value() == 0:
				sig = self.cb_BRgaussSig.value()
			yFilter = Filters.get_gauss(yFilter, self.cb_BRgaussWin.value(), sig)
		if self.cb_BRderivative.value() > 0:
			splrep = interpolate.splrep(self.BRplotBottomData["x"], yFilter)
			yFilter = interpolate.splev(self.BRplotBottomData["x"], splrep, der=self.cb_BRderivative.value())
		if self.cb_BRwienerWin.value() > 0:
			# http://www.nehalemlabs.net/prototype/blog/2013/04/09/an-introduction-to-smoothing-time-series-in-python-part-ii-wiener-filter-and-smoothing-splines/
			yFilter = Filters.get_wiener(yFilter, self.cb_BRwienerWin.value())
		if self.cb_BRsgWin.value() > 0:
			order = 1
			if not self.cb_BRsgOrder.value() == 0:
				order = self.cb_BRsgOrder.value()
			yFilter = Filters.get_sg(yFilter, self.cb_BRsgWin.value(), order)
		# apply de-baselining if appropriate
		if self.check_BRdebaseline.isChecked() and len(yFilter):
			self.BRplotBottomData["y"] -= yFilter
		elif len(yFilter):
			self.BRplotBottomData["y"] = yFilter
		# return unmasked data
		if len(self.BRplotLines) and (not self.check_BRfilterLines.isChecked()):
			for lineRegion in lineRegions:
				for i,idx in enumerate(lineRegion['idx']):
					self.BRplotBottomData["y"][idx] = lineRegion['newY'][i]
		# update stat box (if there's a window)
		if len(self.BRplotBottomRegions):
			lowerX, upperX = self.BRplotBottomRegions[0].getRegion()
			lowerIdx = np.abs([i-lowerX for i in self.BRplotBottomData["x"]]).argmin()
			upperIdx = np.abs([i-upperX for i in self.BRplotBottomData["x"]]).argmin()
			ysigma = np.nanstd(self.BRplotBottomData["y"][lowerIdx:upperIdx])
			self.txt_BRbottomSig.setText("%.4e" % ysigma)
		# update plot
		self.BRplotBottomPlot.setData(self.BRplotBottomData["x"], self.BRplotBottomData["y"])
		self.BRplotBottomPlot.update()
	def BRclearPlotBottom(self):
		"""
		Clears all the regions that may be defined by CTRL+CLICK.
		"""
		if len(self.BRplotBottomLabels):
			for label in self.BRplotBottomLabels:
				self.BRplotBottomFigure.removeItem(label[0])
				self.BRplotBottomFigure.removeItem(label[1])
		self.BRplotBottomLabels = []
		if len(self.BRplotBottomRegions):
			for window in self.BRplotBottomRegions:
				self.BRplotBottomFigure.removeItem(window)
		self.BRplotBottomRegions = []
		self.BRplotFitWindows = []
		self.cb_BRwindow.setMaximum(0)

	def BRdoFit(self):
		"""
		Invokes a child window for running a fit on the bottom plot or a
		subset of data therein.
		"""
		if not len(self.BRplotBottomData["x"]):
			self.showError("you have no spectra loaded yet!", e=RuntimeError)

		windowIdx = self.cb_BRwindow.value()
		x, y = [], []
		if windowIdx == 0:
			x, y = self.BRplotBottomData["x"], self.BRplotBottomData["y"]
		else:
			lowerX, upperX = self.BRplotBottomRegions[windowIdx-1].getRegion()
			x, y = self.BRplotBottomData["x"], self.BRplotBottomData["y"]
			lowerIdx = np.abs([i-lowerX for i in x]).argmin()
			upperIdx = np.abs([i-upperX for i in x]).argmin()
			x = x[lowerIdx:upperIdx]
			y = y[lowerIdx:upperIdx]
		reload(Dialogs)
		self.BRplotFitWindows = Dialogs.QtBasicLineFitter(x=x, y=y)
		self.BRplotFitWindows.show()
	def BRdoFitPro(self):
		"""
		Invokes a child window for running a fit on the bottom plot or a
		subset of data therein.

		Note that this is simply a duplicate of the previous function, but
		references the PRO fitter instead..
		"""
		if not len(self.BRplotBottomData["x"]):
			self.showError("you have no spectra loaded yet!", e=RuntimeError)

		windowIdx = self.cb_BRwindow.value()
		x, y, cursorxy = [], [], ()
		if windowIdx == 0:
			x, y = self.BRplotBottomData["x"], self.BRplotBottomData["y"]
			if len(self.BRplotBottomLabels):
				cursorxy = self.BRplotBottomLabels[-1][0]
				cursorxy = (cursorxy.pos().x(), cursorxy.pos().y())
		else:
			lowerX, upperX = self.BRplotBottomRegions[windowIdx-1].getRegion()
			x, y = self.BRplotBottomData["x"], self.BRplotBottomData["y"]
			lowerIdx = np.abs([i-lowerX for i in x]).argmin()
			upperIdx = np.abs([i-upperX for i in x]).argmin()
			x = x[lowerIdx:upperIdx]
			y = y[lowerIdx:upperIdx]
			if len(self.BRplotBottomLabels):
				for labelPair in self.BRplotBottomLabels:
					if lowerX <= labelPair[0].pos().x() <= upperX:
						cursorxy = (labelPair[0].pos().x(), labelPair[0].pos().y())
		if len(self.BRplotTopData["spec"]) == 1:
			fitSpec = copy.deepcopy(self.BRplotTopData["spec"][0])
			fitSpec.x = x.copy()
			fitSpec.y = y.copy()
		else:
			fitSpec = spectrum.Spectrum(x.copy(), y.copy())
		reload(Dialogs)
		self.BRplotFitWindows = Dialogs.QtProLineFitter(parent=self, spec=fitSpec, cursorxy=cursorxy)
		self.BRplotFitWindows.show()
	def BRdoSplat(self):
		"""
		Invokes a spectral line query, based on the frequency ranges of
		an active region, or the displayed plot range.
		"""
		windowIdx = self.cb_BRwindow.value()
		x, y = [], []
		if windowIdx == 0:
			lowerX, upperX = self.BRplotBottomData["x"][0], self.BRplotBottomData["x"][-1]
		else:
			lowerX, upperX = self.BRplotBottomRegions[windowIdx-1].getRegion()
		cdmsurl = 'https://cdms.astro.uni-koeln.de/cdms/tap/sync?REQUEST=doQuery&LANG=VSS2&FORMAT=spcat&QUERY=SELECT+RadiativeTransitions+WHERE+RadTransFrequency>%f+and+RadTransFrequency<%f&ORDERBY=frequency'
		queryurl = cdmsurl % (lowerX, upperX)
		try:
			f = urlopen(queryurl)
		except:
			log.warning("the query to CDMS for spectral lines didn't work, trying to bypass SSL certificate verification..")
			f = urlopen(queryurl, context=ssl._create_unverified_context())
		queryresults = f.read()
		if isinstance(queryresults, bytes):
			queryresults = queryresults.decode('utf-8')
		reload(Dialogs)
		self.splatViewer = Dialogs.BasicTextViewer(queryresults, size=(1000,500))

	def BRplotBottomMousePosition(self, mouseEvent):
		"""
		Called whenever the mouse is found hovering above the bottom plot.
		It checks if there any regions exist, and adds a hover text with
		that region's index if the mouse is above one.

		:param mouseEvent: the mouse event that is sent by the PlotWidget signal
		:type mouseEvent: tuple(PyQt4.QtCore.QPointF, None)
		"""
		mousePos = self.BRplotBottomPlot.getViewBox().mapSceneToView(mouseEvent[0])
		mouseX, mouseY = mousePos.x(), mousePos.y()
		# process keyboard modifiers and perform appropriate action
		modifier = QtGui.QApplication.keyboardModifiers()
		if modifier == QtCore.Qt.ShiftModifier:
			# convert mouse coordinates to XY wrt the plot
			if len(self.BRplotBottomData["x"]) > 0:
				HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'>x=%f"
				HTMLCoordinates += "<br>y=%g</span></div>"
				idx = np.abs(self.BRplotBottomData["x"] - mouseX).argmin()
				m_freq = self.BRplotBottomData["x"][idx]
				m_int = self.BRplotBottomData["y"][idx]
				self.BRplotBottomMouseLabelXY.setPos(mouseX, mouseY)
				self.BRplotBottomMouseLabelXY.setHtml(HTMLCoordinates % (m_freq, m_int))
			else:
				self.BRplotBottomMouseLabelXY.setPos(mouseX, mouseY)
				self.BRplotBottomMouseLabelXY.setText("%.3f\n%g" % (mouseX,mouseY))
		else:
			self.BRplotBottomMouseLabelXY.setPos(0,0)
			self.BRplotBottomMouseLabelXY.setText("")
		# also update window index for hover
		if len(self.BRplotBottomRegions):
			# convert mouse coordinates to XY wrt the plot
			# check location against regions' bounds
			for win in self.BRplotBottomRegions:
				if (mouseX > win.getRegion()[0]) and (mouseX < win.getRegion()[1]):
					self.BRplotBottomMouseLabelWindow.setPos(mouseX, mouseY)
					winIndex = self.BRplotBottomRegions.index(win) + 1
					self.BRplotBottomMouseLabelWindow.setText(str(winIndex))
					return
				else:
					self.BRplotBottomMouseLabelWindow.setText("")
		else:
			self.BRplotBottomMouseLabelWindow.setText("")
	def BRplotBottomMouseClicked(self, mouseEvent):
		"""
		Called whenever the mouse is clicked in the bottom plot. If the
		SHIFT or CTRL keys are being held, it adds a region to the plot
		that may be used to select a subset of data for running a fit.

		:param mouseEvent: the mouse event that is sent by the PlotWidget signal
		:type mouseEvent: tuple(pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent, None)
		"""
		# convert mouse coordinates to XY wrt the plot
		mousePos = mouseEvent[0].scenePos()
		viewBox = self.BRplotBottomPlot.getViewBox()
		mousePos = viewBox.mapSceneToView(mousePos)
		mouseX, mouseY = mousePos.x(), mousePos.y()
		modifier = QtGui.QApplication.keyboardModifiers()
		# add a region if CTRL
		if modifier == QtCore.Qt.ControlModifier:
			# define bounds that are +/- 10% of the view around the cursor
			xRange = viewBox.viewRange()[0][1] - viewBox.viewRange()[0][0]
			lowerX = mouseX - 0.5 # 0.1*xRange
			upperX = mouseX + 0.5 # 0.1*xRange
			#yRange = viewBox.viewRange()[1][1] - viewBox.viewRange()[1][0]
			#lowerY = mouseY - 0.1*yRange
			#upperY = mouseY + 0.1*yRange
			# define the region
			self.BRplotBottomRegions.append(pg.LinearRegionItem())
			self.BRplotBottomRegions[-1].setRegion((lowerX, upperX))
			# add the region to the plot and update the combobox
			self.BRplotBottomFigure.addItem(self.BRplotBottomRegions[-1], ignoreBounds=True)
			self.cb_BRwindow.setMaximum(len(self.BRplotBottomRegions))
			self.cb_BRwindow.setValue(len(self.BRplotBottomRegions))
		# add/move the XY label if SHIFT
		elif (modifier == QtCore.Qt.ShiftModifier) and len(self.BRplotBottomData["x"]):
			HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'>x=%.3f"
			HTMLCoordinates += "<br>y=%g</span></div>"
			idx = np.abs(self.BRplotBottomData["x"] - mouseX).argmin()
			m_freq = self.BRplotBottomData["x"][idx]
			m_int = self.BRplotBottomData["y"][idx]
			labelDot = pg.TextItem(text="*",anchor=(0.5,0.5))
			labelDot.setPos(mouseX, mouseY)
			labelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
			labelText.setPos(mouseX, mouseY)
			labelText.setHtml(HTMLCoordinates % (m_freq, m_int))
			self.BRplotBottomLabels.append((labelDot, labelText))
			self.BRplotBottomFigure.addItem(self.BRplotBottomLabels[-1][0], ignoreBounds=True)
			self.BRplotBottomFigure.addItem(self.BRplotBottomLabels[-1][1], ignoreBounds=True)
			self.BRplotBottomMouseLabelXY.setPos(0,0)
			self.BRplotBottomMouseLabelXY.setText("")

	def BRtoggleFreqLock(self):
		"""
		Invoked when the checkbox is toggled about locking the frequency
		range of the two plots.
		"""
		if self.check_BRlockFreqRange.isChecked():
			self.BRplotTopFigure.setXLink(self.BRplotBottomFigure)
			self.BRplotBottomFigure.setXLink(self.BRplotTopFigure)
		else:
			self.BRplotTopFigure.setXLink(None)
			self.BRplotBottomFigure.setXLink(None)

	def BRcopyScan(self):
		"""
		Copies the dataset to the clipboard.
		"""
		# get spectral data
		specClipboard = self.BRplotBottomPlot.copy()
		# generate header from top plot's spectrum(a)
		header = []
		for s in self.BRplotTopData["spec"]:
			try:
				header += s.ppheader
			except AttributeError:
				header += ["(blank)"]
		tempHeader = "\n".join(header)
		header = ""
		for line in tempHeader.split("\n"):
			if not line[0] == "#":
				line = "#%s" % line
			header += "%s\n" % line
		# set new clipboard
		clipboard = QtGui.QApplication.clipboard()
		clipboard.setText(header + specClipboard)


	### LA tab
	def LAinitPlot(self):
		"""
		Initializes the LA plot for viewing a catalog & assigning lines
		from experimental spectra.
		"""
		# force the relative sizes to be more reasonable
		self.splitter_LA.setStretchFactor(0, 7)
		self.splitter_LA.setStretchFactor(1, 1)
		# figure properties
		self.LAplotFigure.setLabel('left', "Intensity", units='arb', **self.labelStyle)
		self.LAplotFigure.setLabel('bottom', "Frequency", units='Hz', **self.labelStyle)
		self.LAplotFigure.getAxis('bottom').setScale(scale=1e6)
		self.LAplotFigure.getAxis('left').tickFont = self.tickFont
		self.LAplotFigure.getAxis('bottom').tickFont = self.tickFont
		self.LAplotFigure.getAxis('bottom').setStyle(**{'tickTextOffset':5})
		self.LAplotLegend = Widgets.LegendItem(offset=(30, 30))
		self.LAplotLegend.setParentItem(self.LAplotFigure.getPlotItem().vb)
		# add plot for orig
		self.LAplotCat = Widgets.StickPlot(x=[], height=[], name="catalog")
		self.LAplotCat.opts['pen']=pg.mkPen('g')
		self.LAplotFigure.addItem(self.LAplotCat)
		#self.LAplotLegend.addItem(self.LAplotCat, self.LAplotCat.name())
		# add plot for experimental spectra
		self.LAplotExp = Widgets.SpectralPlot(
			name='exp', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.LAplotExp.setPen(pg.mkPen('w'))
		self.LAplotFigure.addItem(self.LAplotExp)
		# add plots for fits/residuals
		self.LAplotFit = Widgets.SpectralPlot(
			name='fit', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.LAplotFit.setPen(pg.mkPen('y'))
		self.LAplotFigure.addItem(self.LAplotFit)
		#self.LAplotLegend.addItem(self.LAplotFit, self.LAplotFit.name())
		self.LAplotRes = Widgets.SpectralPlot(
			name='residual', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.LAplotRes.setPen(pg.mkPen('r'))
		self.LAplotFigure.addItem(self.LAplotRes)
		#self.LAplotLegend.addItem(self.LAplotRes, self.LAplotRes.name())
		# add plot for arb sticks
		self.LAplotSticks = Widgets.StickPlot(x=[], height=[], name="sticks")
		self.LAplotSticks.opts['pen']=pg.mkPen(color="w")
		self.LAplotFigure.addItem(self.LAplotSticks)
		# containers for catalog and experimental plot labels
		self.LAplotLabels = []
		self.LAplotMouseLabel = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
		self.LAplotMouseLabel.setZValue(999)
		self.LAplotFigure.addItem(self.LAplotMouseLabel, ignoreBounds=True)
		# signals for interacting with the mouse
		self.LAplotMouseMoveSignal = pg.SignalProxy(
			self.LAplotFigure.plotItem.scene().sigMouseMoved,
			rateLimit=15,
			slot=self.LAplotMousePosition)
		self.LAplotMouseClickSignal = pg.SignalProxy(
			self.LAplotFigure.plotItem.scene().sigMouseClicked,
			rateLimit=5,
			slot=self.LAplotMouseClicked)

	def LAplotMousePosition(self, mouseEvent):
		"""
		Processes the signal when the mouse is moving above the plot area.

		Note that this signal is active always, so only light processing
		should be done here, and only under appropriate conditions should
		additional routines should be called.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(PyQt4.QtCore.QPointF, None)
		"""
		# process keyboard modifiers and perform appropriate action
		modifier = QtGui.QApplication.keyboardModifiers()
		if modifier == QtCore.Qt.ShiftModifier:
			# convert mouse coordinates to XY wrt the plot
			mousePos = self.LAplotFigure.plotItem.getViewBox().mapSceneToView(mouseEvent[0])
			mouseX, mouseY = mousePos.x(), mousePos.y()
			try:
				# show a marker at the nearest catalog entry
				HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'><span style='color:green'>cat: %s</span>"
				HTMLCoordinates += "<br>f=%s<br>unc: %s<br>lgint: %.3f<br>qns: <tt>%s</tt></span></div>"
				idx = np.abs(self.LAplotCat.opts.get('x') - mouseX).argmin()
				f = self.LAplotCat.opts.get('x')[idx]
				filename = self.LAcatalog.filename
				tIdx = self.LAcatalog.get_idx_from_freq(f)
				unc = self.LAcatalog.transitions[tIdx].calc_unc
				qns = self.LAcatalog.transitions[tIdx].qn_str
				lgint = np.log10(self.LAcatalog.transitions[tIdx].intensity)
				qns_lo = "%s %s %s %s %s %s" % (qns[:2], qns[2:4], qns[4:6], qns[6:8], qns[8:10], qns[10:12])
				qns_hi = "%s %s %s %s %s %s" % (qns[12:14], qns[14:16], qns[16:18], qns[18:20], qns[20:22], qns[22:24])
				qns_full = qns_lo.rstrip() + "&#8592;" + qns_hi.rstrip()
				self.LAplotMouseLabel.setPos(f, mouseY)
				self.LAplotMouseLabel.setHtml(HTMLCoordinates % (filename,f,unc,lgint,qns_full))
			except TypeError:
				log.warning("warning: you have no catalog loaded..")
		elif modifier == QtCore.Qt.ControlModifier:
			mousePos = self.LAplotFigure.plotItem.getViewBox().mapSceneToView(mouseEvent[0])
			mouseX, mouseY = mousePos.x(), mousePos.y()
			self.LAplotMouseLabel.setPos(mouseX, mouseY)
			self.LAplotMouseLabel.setText(" \n%.3f\n%g" % (mouseX,mouseY))
		else:
			self.LAplotMouseLabel.setPos(0,0)
			self.LAplotMouseLabel.setText("")
	def LAplotMouseClicked(self, mouseEvent):
		"""
		Processes the signal when the mouse is clicked within the plot.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent, None)
		"""
		# convert mouse coordinates to XY wrt the plot
		viewBox = self.LAplotFigure.getPlotItem().vb
		mousePos = viewBox.mapSceneToView(mouseEvent[0].scenePos())
		mousePos = (mousePos.x(), mousePos.y())
		modifier = QtGui.QApplication.keyboardModifiers()
		# add a region if SHIFT
		if modifier == QtCore.Qt.ShiftModifier:
			# add a marker for nearest catalog entry
			labelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
			labelText.setPos(self.LAplotMouseLabel.pos())
			labelText.setHtml(self.LAplotMouseLabel.textItem.toHtml())
			labelText.setZValue(999)
			self.LAplotFigure.addItem(labelText, ignoreBounds=True)
			self.LAplotLabels.append(labelText)
		if modifier == QtCore.Qt.ControlModifier:
			self.LAclearMarkers(ignoreExtras=True) # only removes the tagging-related labels
			# define bounds that are +/- some range around the cursor
			xRange = viewBox.viewRange()[0][1] - viewBox.viewRange()[0][0]
			lowerX = mousePos[0] - 0.025*xRange
			upperX = mousePos[0] + 0.025*xRange
			yRange = viewBox.viewRange()[1][1] - viewBox.viewRange()[1][0]
			lowerY = mousePos[1] - 0.1*yRange
			upperY = mousePos[1] + 0.1*yRange
			# add a cursor
			self.LAplotCursor = pg.TextItem(text="*", anchor=(0.5,0.5), fill=(0,0,0,100))
			self.LAplotCursor.setZValue(999)
			self.LAplotCursor.setPos(mousePos[0], mousePos[1])
			self.LAplotFigure.addItem(self.LAplotCursor, ignoreBounds=True)
			# add a rectangular ROI
			self.LAplotBox = pg.RectROI(
				[lowerX,lowerY],
				[xRange*0.05,yRange*0.2],
				pen=(0,9))
			self.LAplotFigure.addItem(self.LAplotBox, ignoreBounds=True)
			# add an window along the x-axis
			self.LAplotWindow = pg.LinearRegionItem()
			self.LAplotWindow.setRegion((lowerX, upperX))
			self.LAplotFigure.addItem(self.LAplotWindow, ignoreBounds=True)
			self.LAgetCursorFreq()

	def LAloadCat(self, mouseEvent=False, catFile=None):
		"""
		Loads a catalog file into the LA tab.

		:param mouseEvent: (optional) the mouse event from a click
		:param catFile: (optional) the name of a catalog file to load, bypassing the selection dialog
		:type mouseEvent: QtGui.QMouseEvent
		:type catFile: str
		"""
		useWavenumber = QtGui.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier
		if isinstance(catFile, list):
			if len(catFile) > 1:
				raise IOError("multiple catalogs are not supported in the LA tab!")
			else:
				catFile = catFile[0]
		if not catFile:
			directory = self.cwd
			catFile = QtGui.QFileDialog.getOpenFileName(directory=directory)
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				catFile = catFile[0]
			else:
				catFile = str(catFile)
			if not os.path.isfile(catFile):
				return
		if not os.path.isfile(catFile):
			raise IOError("could not locate the requested input catalog!")
		self.cwd = os.path.realpath(os.path.dirname(catFile))
		unit = "MHz"
		if useWavenumber:
			unit = "wvn"
			if not len(self.LAexpData["x"]):
				self.LAplotFigure.setLabel('bottom', units="cm-1", **self.labelStyle)
				self.LAplotFigure.getPlotItem().vb.invertX(True)
				self.LAplotFigure.getAxis('bottom').setScale(scale=1)
		log.info("loading catFile=%s in freq.units=%s" % (catFile, unit))
		self.LAcatalog = catalog.load_predictions(filename=catFile, unit=unit)
		self.LAupdateSim()
		self.LAtextEdit.insertPlainText("%s" % catFile)
	def LAclearCat(self):
		"""
		Clears/removes the catalog from the LA tab.
		"""
		self.LAcatalog = None
		self.LAupdateSim()
	def LAupdateSim(self):
		"""
		Updates the stick spectrum based on the temperature and intensity
		scaling for the loaded catalog.
		"""
		if not self.LAcatalog:
			self.LAplotCat.setData(x=[], height=[])
			self.LAplotCat.update()
			return
		idx, y = self.LAcatalog.temperature_rescaled_intensities(trot=float(self.txt_LAcatTemp.text()))
		try:
			y *= float(self.txt_LAcatScale.text())
		except ValueError:
			pass
		x = np.asarray([self.LAcatalog.transitions[i].calc_freq for i in idx])
		self.LAplotCat.setData(x=x, height=y, pen=pg.mkPen('g', width=1.5))
		self.LAplotCat.update()

	def LAloadExp(self, mouseEvent=False, filenames=[], settings={}):
		"""
		Loads an experimental spectrum to the LA plot.

		:param mouseEvent: (optional) the mouse event from a click
		:param filenames: (optional) a list of files to load, bypassing the selection dialog
		:param settings: (optional) settings to use for loading spectra
		:type mouseEvent: QtGui.QMouseEvent
		:type filenames: list
		:type settings: dict
		"""
		reload(spectrum)
		if not len(filenames):
			# provide dialog
			if not "LAloadDialog" in vars(self):
				self.LAloadDialog = Dialogs.SpecLoadDialog(self)
			if not self.LAloadDialog.exec_():
				return
			else:
				settings = self.LAloadDialog.getValues()
			# get file
			filenames = settings["filenames"]
		if not any([os.path.isfile(f) for f in filenames]):
			raise IOError("could not locate one of the requested input files!")
		self.cwd = os.path.realpath(os.path.dirname(filenames[-1]))
		# if no settings, do some guesswork..
		if settings == {}:
			settings = self.defaultLoadSettings.copy()
		if settings["filetype"] is None:
			settings["filetype"] = spectrum.guess_filetype(filename=filenames)
			log.debug("guessed the filetype(s) should be: %s" % args.filetype)
			if settings["filetype"] is None:
				raise SyntaxError("could not determine the filetype, so you should fix this..")
		# sanity check about: multiple files but not appending them
		if (not settings["appendData"]) and (len(filenames) > 1):
			raise SyntaxError("you cannot load multiple files without appending them!")
		# reset the plots & data
		if not settings["appendData"]:
			self.LAexpData = {"x":[], "y":[]}
		elif isinstance(self.FFexpData["x"], type(np.array([]))):
			self.LAexpData["x"] = self.LAexpData["x"].copy().tolist()
			self.LAexpData["y"] = self.LAexpData["y"].copy().tolist()
		# loop through it and push to memory
		for fileIn in filenames:
			if settings["filetype"] in ["ssv", "tsv", "csv", "casac", "gesp", "ydata"]:
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					skipFirst=settings["skipFirst"])
			elif settings["filetype"]=="jpl":
				if not settings["scanIndex"]:
					settings["scanIndex"] = 1
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (#%g)" % settings["scanIndex"]
			elif settings["filetype"]=="fits":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
			elif settings["filetype"]=="arbdc":
				delimiter = settings["delimiter"]
				xcol = settings["xcol"]
				ycol = settings["ycol"]
				expspec = spectrum.load_spectrum(
					fileIn, ftype="arbdelim",
					skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
					delimiter=delimiter)
			elif settings["filetype"]=="arbs":
				raise NotImplementedError
			elif settings["filetype"] == "brukeropus":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (%s)" % expspec.h['block_key']
			elif settings["filetype"] == "batopt3ds":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"])
			elif settings["filetype"]=="fid":
				pass    # works on this AFTER preprocess
			else:
				raise NotImplementedError("not sure what to do with filetype %s" % settings["filetype"])
			if ("preprocess" in settings) and (settings["preprocess"] is not None):
				expspec.xOrig = expspec.x.copy()
				expspec.yOrig = expspec.y.copy()
				if "vlsrShift" in settings["preprocess"]:
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrShift")
					val = float(settings["preprocess"][idxP+1])
					expspec.x *= (1 + val/2.99792458e8)
				if "vlsrFix" in settings["preprocess"]:
					curVal = 0
					if settings["filetype"]=="fits":
						fitsHeader = expspec.hdu.header
						if "VELO-LSR" in fitsHeader:
							curVal = float(fitsHeader["VELO-LSR"])
						elif "VELO" in fitsHeader:
							curVal = float(fitsHeader["VELO"])
						elif "VELREF" in fitsHeader:
							curVal = float(fitsHeader["CRVAL1"])
						elif "VLSR" in fitsHeader:
							curVal = float(fitsHeader["VLSR"])*1e3
						else:
							raise Warning("couldn't find the original reference velocity in the fits header..")
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrFix")
					val = float(settings["preprocess"][idxP+1])
					if not curVal == 0.0:
						log.info("first removing the old vel_lsr: %s" % curVal)
						expspec.x *= (1 - curVal/2.99792458e8) # revert old value
					log.info("applying vel_lsr = %s" % val)
					expspec.x *= (1 + val/2.99792458e8) # apply new value
				if "shiftX" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftX")
					val = float(settings["preprocess"][idxP+1])
					log.info("applying shiftX = %s" % val)
					expspec.x += val
				if "shiftY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y += val
				if "scaleY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("scaleY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y *= val
				if "clipTopY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipTopY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, None, val)
				if "clipBotY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipBotY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, val, None)
				if "clipAbsY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipAbsY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, -val, val)
				if "wienerY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("wienerY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y -= Filters.get_wiener(expspec.y, val)
				if "medfiltY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("medfiltY")
					val = int(settings["preprocess"][idxP+1])
					expspec.y = scipy.signal.medfilt(expspec.y, val)
				if "ffbutterY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("ffbutterY")
					ford = int(settings["preprocess"][idxP+1])
					ffreq = float(settings["preprocess"][idxP+2])
					b, a = scipy.signal.butter(ford, ffreq, btype='low', analog=False, output='ba')
					expspec.y = scipy.signal.filtfilt(b, a, expspec.y, padlen=20)
			if settings["filetype"]=="fid":
				reload(spectrum)
				if len(settings["delimiter"]):
					xcol, ycol = (1,2)
					if settings["xcol"]:
						xcol = settings["xcol"]
					if settings["ycol"]:
						ycol = settings["ycol"]
					log.info(xcol, ycol)
					delimiter = settings["delimiter"]
					fidxy = spectrum.load_spectrum(
						fileIn, ftype="arbdelim",
						skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
						delimiter=delimiter)
				else:
					log.warning("you did not specify a delimiter, so this assumes they are spaces")
					fidxy = spectrum.load_spectrum(fileIn, ftype="xydata")
				fidspec = spectrum.TimeDomainSpectrum(fidxy.x, fidxy.y)
				fidspec.calc_amplitude_spec(
					window_function=settings["fftType"],
					time_start=float(settings["fidStart"]),
					time_stop=float(settings["fidStop"]))
				expspec = spectrum.Spectrum(x=fidspec.u_spec_win_x, y=fidspec.u_spec_win_y)
				expspec.if_x = expspec.x.copy()
				expspec.rest_x =  expspec.if_x.copy() + float(settings["fidLO"])*1e9
				expspec.image_x = -1*expspec.if_x.copy() + float(settings["fidLO"])*1e9
				if settings["fftSideband"] == "upper":
					expspec.x = expspec.rest_x
				elif settings["fftSideband"] == "lower":
					expspec.x = expspec.image_x
				elif settings["fftSideband"] == "both":
					expspec.x = np.asarray(expspec.image_x.tolist() + expspec.rest_x.tolist())
					expspec.y = np.asarray(expspec.y.tolist() + expspec.y.tolist())
				expspec.x /= 1e6
			if settings["unit"] == "GHz":
				expspec.x *= 1e3
			elif not settings["unit"] == "MHz":
				self.LAplotFigure.getAxis('bottom').setScale(scale=1)
				if settings["unit"] == "cm-1":
					self.LAplotFigure.setLabel('bottom', "Wavenumber", units=settings["unit"])
					self.LAplotFigure.getPlotItem().vb.invertX(True)
				elif settings["unit"] in ["s","ms"]:
					self.LAplotFigure.setLabel('bottom', "Time", units=settings["unit"][-1])
				elif settings["unit"] == "mass amu":
					self.LAplotFigure.setLabel('bottom', "Mass", units="amu")
				elif settings["unit"][0] == u"μ":
					self.LAplotFigure.setLabel('bottom', "Wavelength", units=settings["unit"][1:])
				if settings["unit"] == "ms":
					expspec.x /= 1e3
				elif settings["unit"][0] == u"μ":
					expspec.x /= 1e6
					self.LAplotFigure.setLabel('bottom', units=settings["unit"][1:])
			self.LAexpData["x"] += expspec.x.tolist()
			self.LAexpData["y"] += expspec.y.tolist()
		# sort by x
		self.LAexpData["x"], self.LAexpData["y"] = list(zip(*sorted(zip(self.LAexpData["x"], self.LAexpData["y"]))))
		# back to ndarray if necessary
		if not any([isinstance(self.LAexpData[data], type(np.array([]))) for data in ["x","y"]]):
			self.LAexpData["x"] = np.asarray(self.LAexpData["x"])
			self.LAexpData["y"] = np.asarray(self.LAexpData["y"])
		# update plot and GUI elements
		self.LAplotExp.setData(self.LAexpData["x"], self.LAexpData["y"])
		self.LAplotExp.update()
	def LApasteExp(self):
		"""
		Pastes comma-separated values of experimental spectra from
		the clipboard onto the plot.
		"""
		# grab clipboard contents
		clipboard = unicode(QtGui.QApplication.clipboard().text())
		# try to determine data format
		if all(',' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a csv")
			ftype = "csv"
		elif all('\t' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a tsv")
			ftype = "tsv"
		else:
			log.info("pasting what is not csv or tsv, and therefore assuming ssv")
			ftype = "ssv"
		# write out to temporary file
		fname='clipboard (%s).%s' % (time.strftime("%Y-%m-%d %H:%M:%S"), ftype)
		fname = os.path.join(self.tmpDir, fname)
		fd = codecs.open(fname, encoding='utf-8', mode='w+')
		fd.write(clipboard)
		fd.close()
		# now open file (note: uses custom method rather than that of other tabs, for possibly appending)
		x, y, header = [], [], []
		expspec = spectrum.load_spectrum(fname, ftype=ftype)
		if self.check_LAappendExp.isChecked():
			try:
				self.LAexpData["x"] = self.LAexpData["x"].copy().tolist()
				self.LAexpData["y"] = self.LAexpData["y"].copy().tolist()
			except AttributeError:
				self.LAexpData["x"] = []
				self.LAexpData["y"] = []
			self.LAexpData["x"] += expspec.x.tolist()
			self.LAexpData["y"] += expspec.y.tolist()
			self.LAexpData["x"], self.LAexpData["y"] = list(zip(*sorted(zip(self.LAexpData["x"], self.LAexpData["y"]))))
		else:
			self.LAexpData["x"] = expspec.x
			self.LAexpData["y"] = expspec.y
		# back to ndarray if necessary
		if not any([isinstance(self.LAexpData[data], type(np.array([]))) for data in ["x","y"]]):
			self.LAexpData["x"] = np.asarray(self.LAexpData["x"])
			self.LAexpData["y"] = np.asarray(self.LAexpData["y"])
		self.LAplotExp.setData(self.LAexpData["x"], self.LAexpData["y"])
		self.LAplotExp.update()
	def LAclearExp(self):
		"""
		Clears the experimental spectra from the LA plot.
		"""
		self.LAexpData = {"x":[], "y":[]}
		self.LAplotExp.setData(self.LAexpData["x"], self.LAexpData["y"])
		self.LAplotExp.update()
	
	def LAaddSticks(self):
		"""
		Provides a dialog to manually add 'stick' lines at specific rest
		frequencies.
		"""
		reload(Dialogs)
		self.LAstickDialog = Dialogs.BasicTextInput(text=self.LAsticks, size=(80,300))
		if not self.LAstickDialog.exec_():
			return
		self.LAsticks = self.LAstickDialog.editor.document().toPlainText()
		sticks = []
		for l in self.LAsticks.split("\n"):
			l = str(l)
			if (l == ""): continue
			if (l[0] == "#"): continue
			try:
				sticks.append(float(l.strip()))
			except ValueError:
				pass
		self.LAplotSticks.setData(x=sticks, height=1,
			pen=pg.mkPen(color="w", width=1.5, style=QtCore.Qt.DashLine))
		self.LAplotSticks.update()
	def LAclearSticks(self):
		"""
		Removes the manually-added 'stick' lines.
		"""
		self.LAsticks = ""
		self.LAplotSticks.setData(x=[], height=1, pen=pg.mkPen(color="w", width=1.5))
		self.LAplotSticks.update()

	def LAclearMarkers(self, mouseEvent=None, ignoreExtras=False):
		"""
		Removes all the cursors/boxes/windows from the LA plot.
		"""
		if (not ignoreExtras) and len(self.LAplotLabels):
			for exM in self.LAplotLabels:
				self.LAplotFigure.removeItem(exM)
			self.LAplotLabels = []
		if self.LAplotCursor:
			self.LAplotFigure.removeItem(self.LAplotCursor)
			self.LAplotCursor = None
		if self.LAplotBox:
			self.LAplotFigure.removeItem(self.LAplotBox)
			self.LAplotBox = None
		if self.LAplotWindow:
			self.LAplotFigure.removeItem(self.LAplotWindow)
			self.LAplotWindow = None

	def LAgetCursorFreq(self):
		"""
		Pulls the rest frequency from the last-added mouse label.
		"""
		if not self.LAplotCursor:
			return
		freqCenter = self.LAplotCursor.pos().x()
		self.txt_LAcenterFreq.setText("%.3f" % freqCenter)

	def LAfitGauss(self):
		"""
		Attempts the fitting of a Gaussian line to the center of the
		active x-axis window of the LA plot.
		"""
		raise NotImplementedError("the gaussian fits are not working yet for the LA tab!")
	def LAfit2f(self):
		"""
		Attempts the fitting of a 2f lineshape to the center of the
		active x-axis window of the LA plot.
		"""
		if not self.LAplotWindow:
			return
		# import necessary libraries
		from scipy.odr import odrpack as odr
		from scipy.odr import models
		# get bounds of window
		windowLowerX, windowUpperX = self.LAplotWindow.getRegion()
		windowCenter = windowLowerX + (windowUpperX-windowLowerX)/2.0
		freqCenter = self.LAplotCursor.pos().x()
		# populate data arrays
		mask = np.ma.masked_inside(self.LAexpData["x"], windowLowerX, windowUpperX).mask
		new_y = self.LAexpData["y"][mask].copy()
		fit_y = np.zeros_like(new_y)
		res_y = new_y - fit_y
		x2 = self.LAexpData["x"][mask] - freqCenter
		# define fit and run it
		beta0 = [0, 0.3, np.max(fit_y)]
		gauss = odr.Model(fit.gauss2f_func)
		mydata = odr.Data(x2, res_y)
		myodr = odr.ODR(mydata, gauss, beta0=beta0, maxit=1000)
		myodr.set_job(fit_type=0)
		self.LAfit = myodr.run()
		self.LAfit.beta[0] += freqCenter
		self.txt_LAfitStatus.setText(self.LAfit.stopreason[0])
		self.txt_LAcenterFreq.setText("%.3f %.3f" % (self.LAfit.beta[0], self.LAfit.sd_beta[0]))
		# update plots
		new_fit = fit.gauss2f_func(self.LAfit.beta, self.LAexpData["x"][mask])
		new_y -= new_fit
		fit_y += new_fit
		res_y -= new_fit
		self.LAplotFit.setData(self.LAexpData["x"][mask], fit_y)
		self.LAplotFit.update()
		self.LAplotRes.setData(self.LAexpData["x"][mask], res_y)
		self.LAplotRes.update()
	def LAfitPro(self):
		"""
		Loads the QtProLineFitter dialog for running more sophisticated
		line profile fits.
		"""
		def processResults(results):
			self.txt_LAfitStatus.setText("QtProLineFitter finished")
			self.txt_LAcenterFreq.setText("%.3f %.3f" % (results["frequency"]["value"], results["frequency"]["unc"]))
			fit_x = results["fit"][0]
			fit_y = results["fit"][1]
			res_y = results["res"][1]
			self.LAplotFit.setData(fit_x, fit_y)
			self.LAplotFit.update()
			self.LAplotRes.setData(fit_x, res_y)
			self.LAplotRes.update()

		if not self.LAplotWindow:
			return
		# get bounds of window
		windowLowerX, windowUpperX = self.LAplotWindow.getRegion()
		windowCenter = windowLowerX + (windowUpperX-windowLowerX)/2.0
		freqCenter = self.LAplotCursor.pos().x()
		# populate data arrays
		mask = np.ma.masked_inside(self.LAexpData["x"], windowLowerX, windowUpperX).mask
		new_x = self.LAexpData["x"][mask].copy()
		new_y = self.LAexpData["y"][mask].copy()
		# load window
		reload(Dialogs)
		cursorxy = (self.LAplotCursor.pos().x(), self.LAplotCursor.pos().y())
		self.LAproFitter = Dialogs.QtProLineFitter(parent=self, x=new_x, y=new_y, cursorxy=cursorxy)
		self.LAproFitter.newFitSignal.connect(processResults)
		self.LAproFitter.show()

	def LAaddEntry(self):
		"""
		Adds a new line entry(ies) to the text box for each catalog
		entry that overlaps with the rectangular box on the plot, and
		using the frequency (and optional uncertainty) from the text
		line entry that was updated with the latest fit or mouse cursor.
		"""
		if not self.LAplotBox:
			return
		# get bounds of box
		boxLowerX = self.LAplotBox.pos().x()
		boxLowerY = self.LAplotBox.pos().y()
		boxUpperX = self.LAplotBox.pos().x() + self.LAplotBox.size().x()
		boxUpperY = self.LAplotBox.pos().y() + self.LAplotBox.size().y()
		# find the catalog entries within the bounds of the box
		idx, y = self.LAcatalog.temperature_rescaled_intensities(
			freq_min=boxLowerX,
			freq_max=boxUpperX,
			trot=float(self.txt_LAcatTemp.text()))
		try:
			y *= float(self.txt_LAcatScale.text())
		except ValueError:
			pass
		x = np.asarray([self.LAcatalog.transitions[i].calc_freq for i in idx])
		# update the text box
		line = "\n"
		for num,i in enumerate(idx):
			if y[num] > boxLowerY:
				#entry_str = self.LAcatalog.transitions[i].cat_str()
				entry_str = self.LAcatalog.transitions[i].qn_up.__repr__()
				entry_str += self.LAcatalog.transitions[i].qn_low.__repr__()
				entry_str = "%-40s" % entry_str
				entry_str += "%s" % self.txt_LAcenterFreq.text()
				line += entry_str + "\n"
		cursor = self.LAtextEdit.textCursor()
		cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor)
		self.LAtextEdit.setTextCursor(cursor)
		self.LAtextEdit.insertPlainText(line.rstrip())


	### FF tab
	def FFinitPlot(self):
		"""
		Initializes the plot for viewing catalogs.
		"""
		# force the relative sizes to be more reasonable
		self.splitter_FFcontents.setStretchFactor(0, 1)
		self.splitter_FFcontents.setStretchFactor(1, 7)
		# figure properties
		self.FFplotFigure.setLabel('left', "Intensity", units='arb', **self.labelStyle)
		self.FFplotFigure.setLabel('bottom', "Frequency", units='Hz', **self.labelStyle)
		self.FFplotFigure.getAxis('bottom').setScale(scale=1e6)
		self.FFplotFigure.getAxis('left').tickFont = self.tickFont
		self.FFplotFigure.getAxis('bottom').tickFont = self.tickFont
		self.FFplotFigure.getAxis('bottom').setStyle(**{'tickTextOffset':5})
		self.FFplotLegend = Widgets.LegendItem(offset=(30, 30))
		self.FFplotLegend.setParentItem(self.FFplotFigure.getPlotItem().vb)
		# add plot for orig
		self.FFplotOrig = Widgets.StickPlot(x=[], height=[], name="orig")
		self.FFplotOrig.opts['pen']=pg.mkPen('w')
		self.FFplotFigure.addItem(self.FFplotOrig)
		self.FFplotLegend.addItem(self.FFplotOrig, self.FFplotOrig.name())
		# add plot for new
		self.FFplotNew = Widgets.StickPlot(x=[], height=[], name="new")
		self.FFplotNew.opts['pen']=pg.mkPen('b')
		self.FFplotFigure.addItem(self.FFplotNew)
		self.FFplotLegend.addItem(self.FFplotNew, self.FFplotNew.name())
		# add plot for arb sticks
		self.FFplotSticks = Widgets.StickPlot(x=[], height=[], name="sticks")
		self.FFplotSticks.opts['pen']=pg.mkPen('g')
		self.FFplotFigure.addItem(self.FFplotSticks)
		#self.FFplotLegend.addItem(self.FFplotSticks, self.FFplotSticks.name())
		# add plot for experimental spectra
		self.FFplotExp = Widgets.SpectralPlot(
			name='exp', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.FFplotExp.setPen(pg.mkPen('g'))
		self.FFplotFigure.addItem(self.FFplotExp)
		#self.FFplotLegend.addItem(self.FFplotSticks, self.FFplotSticks.name())
		# containers for catalog and experimental plots
		self.FFplotLabels = []
		# signals for interacting with the mouse
		self.FFplotMouseLabel = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
		self.FFplotMouseLabel.setZValue(999)
		self.FFplotFigure.addItem(self.FFplotMouseLabel, ignoreBounds=True)
		self.FFplotMouseMoveSignal = pg.SignalProxy(
			self.FFplotFigure.plotItem.scene().sigMouseMoved,
			rateLimit=15,
			slot=self.FFplotMousePosition)
		self.FFplotMouseClickSignal = pg.SignalProxy(
			self.FFplotFigure.plotItem.scene().sigMouseClicked,
			rateLimit=5,
			slot=self.FFplotMouseClicked)

	def FFloadFiles(self, inputFile=None):
		"""
		Used by the 'Load Files' button to load the int/var/cat files
		that are to be processed by spcat.

		It initiates a file selection dialog to choose one of the input
		files, and uses this selection to the load the complementary
		ones. It finishes with a call to self.FFreset(), so see that
		for additional details.

		Note that if the cat file does not exist, it calls spcat to
		generate it.

		:param inputFile: (optional) the name of the int/var/cat file to load, thus bypassing the selection dialog
		:type inputFile: str
		"""
		if not inputFile:
			directory = self.cwd
			if self.FFfiles[0] and os.path.isdir(os.path.dirname(self.FFfiles[0])):
				directory = os.path.realpath(os.path.dirname(self.FFfiles[0]))
			title = "Select an input file.."
			filters = "Input files (*.int *.var)" # to help with the file search...
			inputFile = QtGui.QFileDialog.getOpenFileName(
				parent=self,
				caption=title,
				directory=directory,
				filter=filters)
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				inputFile = inputFile[0]
			else:
				inputFile = str(inputFile)
			if not os.path.isfile(inputFile):
				return
		self.cwd = os.path.realpath(os.path.dirname(inputFile))
		# identify the brother/sister files
		intFile, varFile, catFile = None, None, None
		if inputFile[-4:] == ".int":
			intFile = inputFile
			varFile = inputFile[:-4] + ".var"
			catFile = inputFile[:-4] + ".cat"
		elif inputFile[-4:] == ".var":
			varFile = inputFile
			intFile = inputFile[:-4] + ".int"
			catFile = inputFile[:-4] + ".cat"
		elif inputFile[-4:] == ".cat":
			catFile = inputFile
			intFile = inputFile[:-4] + ".int"
			varFile = inputFile[:-4] + ".var"
		else:
			msg = "Somehow you managed to select an unknown input file:"
			msg += "\n%s" % inputFile
			QtGui.QMessageBox.warning(self, "Input Error!", msg, QtGui.QMessageBox.Ok)
			return
		# throw an error if the INT and VAR files do not exist
		if (not os.path.isfile(intFile)) or (not os.path.isfile(varFile)):
			msg = "Missing either the INT or VAR file, based on your selection:"
			msg += "\n%s" % inputFile
			QtGui.QMessageBox.warning(self, "Input Error!", msg, QtGui.QMessageBox.Ok)
			return
		# extract base filename and working directory
		cwd = os.path.dirname(intFile)
		if cwd:
			basename = intFile[len(cwd)+1:-4] # note the "+1" accounts for the final directory character
		else:
			cwd = "."
			basename = intFile[:-4]
		# if the catFile doesn't exist, invoke SPCAT
		#if not os.path.isfile(catFile):
		if not None:
			log.info("the catalog doesn't appear to exist.. will invoke SPCAT now")
			try:
				output = subprocess.check_output(["spcat", basename], cwd=cwd)
			except OSError as e:
				msg = "There was an error invoking SPCAT and creating the CAT file."
				msg += "\n%s" % e
				QtGui.QMessageBox.warning(self, "Input Error!", msg, QtGui.QMessageBox.Ok)
				return
			# check again
			if not os.path.isfile(catFile):
				msg = "There was an error invoking SPCAT and creating the CAT file."
				msg += "\noutput was: %s" % output
				QtGui.QMessageBox.warning(self, "Input Error!", msg, QtGui.QMessageBox.Ok)
				return
		# finally, define the list of files and reset the FF tab
		self.FFfiles = [intFile, varFile, catFile]
		self.FFreset()
	def FFreset(self):
		"""
		Removes all the constants from the interface, as well as the
		stick plots. It then reloads the input files. Note that this
		is also what is used for first loading the files.
		"""
		# remove everything in the layout
		for row in self.FFconstants:
			for col in row:
				self.layout_FFconstants.removeWidget(col)
				col.deleteLater()
				del col
		self.FFconstants = []
		# load the files into memory
		with open(self.FFfiles[1], 'r+') as f:
			lineno = 0
			npar, nvib, nparLoaded = 0, 0, 0
			for line in f:
				lineno += 1
				if lineno == 1:
					continue
				elif lineno == 2:
					npar = int(line.strip().split()[0])
				elif lineno == 3:
					nvib = int(line.strip().split()[2])
				elif (lineno > 3) and (lineno <= 2+nvib):
					continue
				elif (lineno > 2+nvib) and (lineno <= 2+nvib+npar) and (nparLoaded < npar):
					#if not '/' in line: line += '/' # ensures all parameters have a comment
					try:
						par, comment = line.strip().split('/')
					except ValueError:
						par = line
						comment = ''
					par = par.strip().split()
					values = [comment, par[0], par[1], par[2]]
					self.FFaddConstant(values=values)
					nparLoaded += 1
				else:
					break
		# update the plot with the line catalog
		cat = catalog.load_predictions(filename=self.FFfiles[2], unit='MHz')
		del self.FFcats[1]
		self.FFcats = [cat, None]
		idx, y = cat.temperature_rescaled_intensities(trot=300)
		x = np.asarray([cat.transitions[i].calc_freq for i in idx])
		self.FFplotOrig.setData(x=x, height=y, pen=pg.mkPen('w', width=1.5))
		self.FFplotOrig.update()
		self.FFplotNew.setData(x=[], height=[], pen=pg.mkPen('b'))
		self.FFplotNew.update()
	def FFupdate(self):
		"""
		Generates a new catalog, based directly on the values of the
		parameters contained in the interface.

		It does this by directly copying the int file to the active
		temporary directory
		"""
		# define a set of temporary files
		fd, basename = tempfile.mkstemp(dir=self.tmpDir)
		os.close(fd)
		os.remove(basename)
		log.info("using %s.[int,var,cat] for the modified FF project files" % basename)
		# copy int to temporary file
		shutil.copyfile(self.FFfiles[0], "%s.int" % basename)
		# populate new var file
		varFile = "%s.var" % basename
		varFD = open(varFile, 'w')
		# first the top lines of the old var file
		with open(self.FFfiles[1], 'r+') as f:
			lineno = 0
			npar, nvib = 0, 0
			for line in f:
				lineno += 1
				if lineno == 1:
					varFD.write(line)
				elif lineno == 2:
					#varFD.write("%s\n" % int(len(self.FFconstants)+1))
					newline = line.strip().split()
					newline[0] = str(len(self.FFconstants))
					varFD.write("%s\n" % " ".join(newline))
				elif lineno == 3:
					nvib = int(line.strip().split()[2])
					varFD.write(line)
				elif (lineno > 3) and (lineno <= 2+nvib):
					varFD.write(line)
				else:
					break
		# then the contents of the FF tab
		for row in self.FFconstants:
			name = row[0].text()
			code = row[1].text()
			#val = row[2].value()
			val = "%.16E" % row[2].value()
			unc = "%.8E" % row[3].value()
			line = "%13s%24s%15s /%s\n" % (code, val, unc, name)
			varFD.write(line)
		varFD.close()
		# invoke spcat
		try:
			output = subprocess.check_output(["spcat", basename], cwd=self.tmpDir)
		except OSError as e:
			msg = "There was an error invoking SPCAT and creating the CAT file."
			msg += "\n%s" % e
			QtGui.QMessageBox.warning(self, "Input Error!", msg, QtGui.QMessageBox.Ok)
			return
		# make sure the catfile exists
		if not os.path.isfile("%s.cat" % basename):
			msg = "There was an error invoking SPCAT and creating the CAT file."
			msg += "\noutput was: %s" % output
			QtGui.QMessageBox.warning(self, "Input Error!", msg, QtGui.QMessageBox.Ok)
			return
		# update plot
		catFile = "%s.cat" % basename
		cat = catalog.load_predictions(filename=catFile, unit='MHz')
		self.FFcats[1] = cat
		idx, y = cat.temperature_rescaled_intensities(trot=300)
		y *= 0.8
		x = np.asarray([cat.transitions[i].calc_freq for i in idx])
		self.FFplotNew.setData(x=x, height=y, pen=pg.mkPen(self.FFsettings['colorCat'], width=1.5))
		self.FFplotNew.update()

	def FFaddConstant(self, event=None, values=None):
		"""
		Adds a new empty row to the table of constants.

		It is typically called under two possible conditions: either
		directly during the loading of a set of input files, or one-by-one
		by the user to add new constants to an already-loaded set. In
		the former case, the input argument can be used to define the
		initial values.

		:param values: (optional) the name/code/val/uncertainty of a constant
		:type values: list(str, str, float, float)
		"""
		kbmods = QtGui.QApplication.keyboardModifiers()
		targetWidget = self.layout_FFconstants
		numrow = len(self.FFconstants)
		newRow = []
		numrow += 1
		if not values:
			values = [
				"new par %s" % numrow,
				"code",
				1e-37,
				1e37]
		name = QtGui.QLineEdit()
		name.setText(values[0])
		newRow.append(name)
		code = QtGui.QLineEdit()
		code.setText(values[1])
		newRow.append(code)
		val = Widgets.ScrollableText(self, **{'relStep':1, "formatString":"%s"})
		val.setValue(values[2])
		newRow.append(val)
		unc = Widgets.ScrollableText(self, **{"formatString":"%.2e"})
		unc.setValue(values[3])
		if self.check_FFuncForStepsize.isChecked():
			val.setStepSize(const=unc.value())
			unc.textChanged.connect(self.FFupdateStepSizes)
		newRow.append(unc)
		delete = QtGui.QPushButton("del")
		delete.setMaximumWidth(40) # otherwise prefers 100
		delete.clicked.connect(partial(self.FFremoveConstant, btn=delete))
		newRow.append(delete)
		moveup = QtGui.QPushButton("up")
		moveup.setMaximumWidth(40)
		moveup.clicked.connect(partial(self.FFmoveupConstant, btn=moveup))
		newRow.append(moveup)
		movedown = QtGui.QPushButton("dwn")
		movedown.setMaximumWidth(40)
		movedown.clicked.connect(partial(self.FFmovedownConstant, btn=movedown))
		newRow.append(movedown)
		for col,item in enumerate(newRow):
			targetWidget.addWidget(item, numrow+1, col)
		self.FFconstants.append(newRow)
		# fix tab order
		for irow,row in enumerate(self.FFconstants):
			for icol,item in enumerate(row):
				try:
					self.frame_FFconstants.setTabOrder(self.FFconstants[irow][icol], self.FFconstants[irow][icol+1])
				except IndexError:
					pass
		# fix the column widths to be more reasonable
		targetWidget.setColumnStretch(0, 2)
		targetWidget.setColumnStretch(1, 3)
		targetWidget.setColumnStretch(2, 3)
		targetWidget.setColumnStretch(3, 2)
		
		# provide a pop-up menu that optionally selects a predefined constant
		if kbmods == QtCore.Qt.ShiftModifier:
			cursor = QtGui.QCursor()
			self.constantMenu = self.FFgetMenuOfConstants()
			self.constantMenu.popup(cursor.pos())
	def FFgetMenuOfConstants(self):
		self.constantMenu = QtGui.QMenu()
		self.constantMenu.setTitle("add a predefined constant")
		self.watsonAmenu = QtGui.QMenu()
		self.watsonAmenu.setTitle("watson-A")
		for constant in self.const_watsonA:
			label = "%s" % constant[0]
			try:
				label += " (%s)" % constant[2]
			except:
				pass
			action = self.watsonAmenu.addAction(label)
			action.triggered.connect(partial(self.FFinsertConstant, ctype="a", cname=constant[0]))
		self.constantMenu.addMenu(self.watsonAmenu)
		self.watsonSmenu = QtGui.QMenu()
		self.watsonSmenu.setTitle("watson-S")
		for constant in self.const_watsonS:
			label = "%s" % constant[0]
			try:
				label += " (%s)" % constant[2]
			except:
				pass
			action = self.watsonSmenu.addAction(label)
			action.triggered.connect(partial(self.FFinsertConstant, ctype="s", cname=constant[0]))
		self.constantMenu.addMenu(self.watsonSmenu)
		self.hfmenu = QtGui.QMenu()
		self.hfmenu.setTitle("hyperfine")
		for constant in self.const_hyperfine:
			label = "%s" % constant[0]
			try:
				label += " (%s)" % constant[2]
			except:
				pass
			action = self.hfmenu.addAction(label)
			action.triggered.connect(partial(self.FFinsertConstant, ctype="hf", cname=constant[0]))
		self.constantMenu.addMenu(self.hfmenu)
		launchCribSheet = self.constantMenu.addAction("launch Kisiel's crib sheet")
		launchCribSheet.triggered.connect(partial(webbrowser.open,
			url="http://www.ifpan.edu.pl/~kisiel/asym/pickett/crib.htm"))
		launchNovickNotes = self.constantMenu.addAction("launch Stewart Novick's notes")
		launchNovickNotes.triggered.connect(partial(webbrowser.open,
			url="https://wesfiles.wesleyan.edu/home/snovick/Pickett%20Handout/SPCAT-SPFIT/Herb%20%26%20my%20Notes%204a.pdf"))
		launchGuide1 = self.constantMenu.addAction("launch Novick's guide (JMS)")
		launchGuide1.triggered.connect(partial(webbrowser.open,
			url="http://dx.doi.org/10.1016/j.jms.2016.08.015"))
		launchGuide2 = self.constantMenu.addAction("launch Drouin's guide (JMS)")
		launchGuide2.triggered.connect(partial(webbrowser.open,
			url="http://dx.doi.org/10.1016/j.jms.2017.07.009"))
		return self.constantMenu
	def FFinsertConstant(self, ctype=None, cname=None):
		"""
		Replaces the name and code of the last constant in the table with
		one of the predefined Watson A or S constants.
		"""
		dictOfConstants = {
			'a': self.const_watsonA,
			's': self.const_watsonS,
			'hf': self.const_hyperfine,
		}
		if cname is None:
			return
		for constant in dictOfConstants.get(ctype):
			if cname == constant[0]:
				self.FFconstants[-1][0].setText(constant[0])
				self.FFconstants[-1][1].setText(constant[1])
				break
	def FFupdateStepSizes(self, event):
		"""
		Loops through the table of constants and sets the scrollable
		step sizes of the values according to the related check box.
		
		Note that this is called each time one of the uncertainties
		is changed.
		"""
		for row in self.FFconstants:
			val = row[2]
			unc = row[3]
			if self.check_FFuncForStepsize.isChecked():
				val.setStepSize(const=unc.value())
			else:
				val.setStepSize(rel=1)
	def FFremoveConstant(self, btn):
		"""
		Removes a row describing a constant.

		The input argument must be a reference to the remove button
		associated with a particular constant, so that it is clear which
		row is to be removed.

		:param btn: the remove button calling this routine
		:type btn: QtGui.QPushButton
		"""
		rowToDelete = 0
		for nrow,row in enumerate(self.FFconstants):
			if row[4] == btn:
				rowToDelete = nrow
				break
		for col in reversed(self.FFconstants[rowToDelete]):
			self.layout_FFconstants.removeWidget(col)
			col.deleteLater()
			del col
		del self.FFconstants[rowToDelete]
	def FFmoveupConstant(self, btn):
		"""
		Moves a constant up.

		The input argument must be a reference to the move-up button
		associated with a particular constant, so that it is clear which
		row is to be moved.

		:param btn: the move-up button calling this routine
		:type btn: QtGui.QPushButton
		"""
		rowToMove = 0
		totRows = len(self.FFconstants)
		# determine row to move
		for nrow,row in enumerate(self.FFconstants):
			if row[5] == btn:
				rowToMove = nrow
				break
		# forget about it, if it's already at the edge
		if rowToMove == 0:
			return
		# clear the layout
		for row in self.FFconstants:
			for col in row:
				self.layout_FFconstants.removeWidget(col)
		# do the moving
		row = self.FFconstants[rowToMove]
		self.FFconstants.remove(row)
		self.FFconstants.insert(rowToMove-1, row)
		for nrow,row in enumerate(self.FFconstants):
			for ncol,item in enumerate(row):
				self.layout_FFconstants.addWidget(item, nrow+1, ncol)
		# fix tab order
		for irow,row in enumerate(self.FFconstants):
			for icol,item in enumerate(row):
				try:
					self.frame_FFconstants.setTabOrder(self.FFconstants[irow][icol], self.FFconstants[irow][icol+1])
				except IndexError:
					pass
			try:
				self.frame_FFconstants.setTabOrder(self.FFconstants[irow][-1], self.FFconstants[irow+1][0])
			except IndexError:
				pass
	def FFmovedownConstant(self, btn):
		"""
		Moves a constant up.

		The input argument must be a reference to the move-down button
		associated with a particular constant, so that it is clear which
		row is to be moved.

		:param btn: the move-down button calling this routine
		:type btn: QtGui.QPushButton
		"""
		rowToMove = 0
		totRows = len(self.FFconstants)
		# determine row to move
		for nrow,row in enumerate(self.FFconstants):
			if row[6] == btn:
				rowToMove = nrow
				break
		# forget about it, if it's already at the edge
		if rowToMove == totRows:
			return
		# clear the layout
		for row in self.FFconstants:
			for col in row:
				self.layout_FFconstants.removeWidget(col)
		# do the moving
		row = self.FFconstants[rowToMove]
		self.FFconstants.remove(row)
		self.FFconstants.insert(rowToMove+1, row)
		for nrow,row in enumerate(self.FFconstants):
			for ncol,item in enumerate(row):
				self.layout_FFconstants.addWidget(item, nrow+1, ncol)
		# fix tab order
		for irow,row in enumerate(self.FFconstants):
			for icol,item in enumerate(row):
				try:
					self.frame_FFconstants.setTabOrder(self.FFconstants[irow][icol], self.FFconstants[irow][icol+1])
				except IndexError:
					pass
			try:
				self.frame_FFconstants.setTabOrder(self.FFconstants[irow][-1], self.FFconstants[irow+1][0])
			except IndexError:
				pass

	def FFrecolorCat(self):
		"""
		Chooses a new random color for the catalog.
		"""
		if not self.colorDialog.exec_():
			return
		self.FFsettings['colorCat'] = str(self.colorDialog.selectedColor().name()).upper()
		self.FFupdate()
	def FFrecolorExp(self):
		"""
		Chooses a new random color for the experimental spectrum.
		"""
		if not self.colorDialog.exec_():
			return
		self.FFsettings['colorExp'] = str(self.colorDialog.selectedColor().name()).upper()
		self.FFplotSticks.opts['pen'] = pg.mkPen(self.FFsettings['colorExp'], width=1.5)
		self.FFplotSticks.drawPicture()
		self.FFplotExp.setPen(pg.mkPen(self.FFsettings['colorExp']))

	def FFloadExp(self, mouseEvent=False, filenames=[], settings={}):
		"""
		Loads an experimental spectrum to the FF plot.

		:param mouseEvent: (optional) the mouse event from a click
		:param filenames: (optional) a list of files to load, bypassing the selection dialog
		:param settings: (optional) settings to use for loading spectra
		:type mouseEvent: QtGui.QMouseEvent
		:type filenames: list
		:type settings: dict
		"""
		reload(spectrum)
		if not len(filenames):
			# provide dialog
			if not "FFloadDialog" in vars(self):
				self.FFloadDialog = Dialogs.SpecLoadDialog(self)
			if not self.FFloadDialog.exec_():
				return
			else:
				settings = self.FFloadDialog.getValues()
			# get file
			filenames = settings["filenames"]
		if not any([os.path.isfile(f) for f in filenames]):
			raise IOError("could not locate one of the requested input files!")
		self.cwd = os.path.realpath(os.path.dirname(filenames[-1]))
		# if no settings, do some guesswork..
		if settings == {}:
			settings = self.defaultLoadSettings.copy()
		if settings["filetype"] is None:
			settings["filetype"] = spectrum.guess_filetype(filename=filenames)
			log.debug("guessed the filetype(s) should be: %s" % args.filetype)
			if settings["filetype"] is None:
				raise SyntaxError("could not determine the filetype, so you should fix this..")
		# sanity check about: multiple files but not appending them
		if (not settings["appendData"]) and (len(filenames) > 1):
			raise SyntaxError("you cannot load multiple files without appending them!")
		# reset the plots & data
		if not settings["appendData"]:
			self.FFexpData = {"x":[], "y":[]}
		elif isinstance(self.FFexpData["x"], type(np.array([]))):
			self.FFexpData["x"] = self.FFexpData["x"].copy().tolist()
			self.FFexpData["y"] = self.FFexpData["y"].copy().tolist()
		# loop through it and push to memory
		for fileIn in filenames:
			if settings["filetype"] in ["ssv", "tsv", "csv", "casac", "gesp", "ydata"]:
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					skipFirst=settings["skipFirst"])
			elif settings["filetype"]=="jpl":
				if not settings["scanIndex"]:
					settings["scanIndex"] = 1
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (#%g)" % settings["scanIndex"]
			elif settings["filetype"]=="fits":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
			elif settings["filetype"]=="arbdc":
				delimiter = settings["delimiter"]
				xcol = settings["xcol"]
				ycol = settings["ycol"]
				expspec = spectrum.load_spectrum(
					fileIn, ftype="arbdelim",
					skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
					delimiter=delimiter)
			elif settings["filetype"]=="arbs":
				raise NotImplementedError
			elif settings["filetype"] == "brukeropus":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					scanindex=settings["scanIndex"])
				name += " (%s)" % expspec.h['block_key']
			elif settings["filetype"] == "batopt3ds":
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"])
			elif settings["filetype"]=="fid":
				pass    # works on this AFTER preprocess
			else:
				raise NotImplementedError("not sure what to do with filetype %s" % settings["filetype"])
			if ("preprocess" in settings) and (settings["preprocess"] is not None):
				expspec.xOrig = expspec.x.copy()
				expspec.yOrig = expspec.y.copy()
				if "vlsrShift" in settings["preprocess"]:
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrShift")
					val = float(settings["preprocess"][idxP+1])
					expspec.x *= (1 + val/2.99792458e8)
				if "vlsrFix" in settings["preprocess"]:
					curVal = 0
					if settings["filetype"]=="fits":
						fitsHeader = expspec.hdu.header
						if "VELO-LSR" in fitsHeader:
							curVal = float(fitsHeader["VELO-LSR"])
						elif "VELO" in fitsHeader:
							curVal = float(fitsHeader["VELO"])
						elif "VELREF" in fitsHeader:
							curVal = float(fitsHeader["CRVAL1"])
						elif "VLSR" in fitsHeader:
							curVal = float(fitsHeader["VLSR"])*1e3
						else:
							raise Warning("couldn't find the original reference velocity in the fits header..")
					# this assumes vrad shift in m/s for a frequency axis
					idxP = settings["preprocess"].index("vlsrFix")
					val = float(settings["preprocess"][idxP+1])
					if not curVal == 0.0:
						log.info("first removing the old vel_lsr: %s" % curVal)
						expspec.x *= (1 - curVal/2.99792458e8) # revert old value
					log.info("applying vel_lsr = %s" % val)
					expspec.x *= (1 + val/2.99792458e8) # apply new value
				if "shiftX" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftX")
					val = float(settings["preprocess"][idxP+1])
					log.info("applying shiftX = %s" % val)
					expspec.x += val
				if "shiftY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("shiftY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y += val
				if "scaleY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("scaleY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y *= val
				if "clipTopY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipTopY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, None, val)
				if "clipBotY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipBotY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, val, None)
				if "clipAbsY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("clipAbsY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y = np.clip(expspec.y, -val, val)
				if "wienerY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("wienerY")
					val = float(settings["preprocess"][idxP+1])
					expspec.y -= Filters.get_wiener(expspec.y, val)
				if "medfiltY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("medfiltY")
					val = int(settings["preprocess"][idxP+1])
					expspec.y = scipy.signal.medfilt(expspec.y, val)
				if "ffbutterY" in settings["preprocess"]:
					idxP = settings["preprocess"].index("ffbutterY")
					ford = int(settings["preprocess"][idxP+1])
					ffreq = float(settings["preprocess"][idxP+2])
					b, a = scipy.signal.butter(ford, ffreq, btype='low', analog=False, output='ba')
					expspec.y = scipy.signal.filtfilt(b, a, expspec.y, padlen=20)
			if settings["filetype"]=="fid":
				reload(spectrum)
				if len(settings["delimiter"]):
					xcol, ycol = (1,2)
					if settings["xcol"]:
						xcol = settings["xcol"]
					if settings["ycol"]:
						ycol = settings["ycol"]
					log.info(xcol, ycol)
					delimiter = settings["delimiter"]
					fidxy = spectrum.load_spectrum(
						fileIn, ftype="arbdelim",
						skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
						delimiter=delimiter)
				else:
					log.warning("you did not specify a delimiter, so this assumes they are spaces")
				fidxy = spectrum.load_spectrum(fileIn, ftype="xydata")
				fidspec = spectrum.TimeDomainSpectrum(fidxy.x, fidxy.y)
				fidspec.calc_amplitude_spec(
					window_function=settings["fftType"],
					time_start=float(settings["fidStart"]),
					time_stop=float(settings["fidStop"]))
				expspec = spectrum.Spectrum(x=fidspec.u_spec_win_x, y=fidspec.u_spec_win_y)
				expspec.if_x = expspec.x.copy()
				expspec.rest_x =  expspec.if_x.copy() + float(settings["fidLO"])*1e9
				expspec.image_x = -1*expspec.if_x.copy() + float(settings["fidLO"])*1e9
				if settings["fftSideband"] == "upper":
					expspec.x = expspec.rest_x
				elif settings["fftSideband"] == "lower":
					expspec.x = expspec.image_x
				elif settings["fftSideband"] == "both":
					expspec.x = np.asarray(expspec.image_x.tolist() + expspec.rest_x.tolist())
					expspec.y = np.asarray(expspec.y.tolist() + expspec.y.tolist())
				expspec.x /= 1e6
			if settings["unit"] == "GHz":
				expspec.x *= 1e3
			elif not settings["unit"] == "MHz":
				self.FFplotFigure.getAxis('bottom').setScale(scale=1)
				if settings["unit"] == "cm-1":
					self.FFplotFigure.setLabel('bottom', "Wavenumber", units=settings["unit"])
					self.FFplotFigure.getPlotItem().vb.invertX(True)
				elif settings["unit"] in ["s","ms"]:
					self.FFplotFigure.setLabel('bottom', "Time", units=settings["unit"][-1])
				elif settings["unit"] == "mass amu":
					self.FFplotFigure.setLabel('bottom', "Mass", units="amu")
				elif settings["unit"][0] == u"μ":
					self.FFplotFigure.setLabel('bottom', "Wavelength", units=settings["unit"][1:])
				if settings["unit"] == "ms":
					expspec.x /= 1e3
				elif settings["unit"][0] == u"μ":
					expspec.x /= 1e6
					self.FFplotFigure.setLabel('bottom', units=settings["unit"][1:])
			self.FFexpData["x"] += expspec.x.tolist()
			self.FFexpData["y"] += expspec.y.tolist()
		# sort by x
		self.FFexpData["x"], self.FFexpData["y"] = list(zip(*sorted(zip(self.FFexpData["x"], self.FFexpData["y"]))))
		# back to ndarray if necessary
		if not any([isinstance(self.FFexpData[data], type(np.array([]))) for data in ["x","y"]]):
			self.FFexpData["x"] = np.asarray(self.FFexpData["x"])
			self.FFexpData["y"] = np.asarray(self.FFexpData["y"])
		# update plot and GUI elements
		self.FFplotExp.setData(self.FFexpData["x"], self.FFexpData["y"])
		self.FFplotExp.update()
	def FFpasteExp(self):
		"""
		Pastes CSV data from the clipboard.
		"""
		# grab clipboard contents
		clipboard = unicode(QtGui.QApplication.clipboard().text())
		# try to determine data format
		if all(',' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a csv")
			ftype = "csv"
		elif all('\t' in l for l in clipboard.split('\n') if len(l) and (not l[0]=="#")):
			log.info("pasting what looks like a tsv")
			ftype = "tsv"
		else:
			log.info("pasting what is not csv or tsv, and therefore assuming ssv")
			ftype = "ssv"
		# write out to temporary file
		fname='clipboard (%s).%s' % (time.strftime("%Y-%m-%d %H:%M:%S"), ftype)
		fname = os.path.join(self.tmpDir, fname)
		fd = codecs.open(fname, encoding='utf-8', mode='w+')
		fd.write(clipboard)
		fd.close()
		# now open file (note: uses custom method rather than that of other tabs, for possibly appending)
		x, y, header = [], [], []
		expspec = spectrum.load_spectrum(fname, ftype=ftype)
		if self.check_FFappendExp.isChecked():
			try:
				self.FFexpData["x"] = self.FFexpData["x"].copy().tolist()
				self.FFexpData["y"] = self.FFexpData["y"].copy().tolist()
			except AttributeError:
				self.FFexpData["x"] = []
				self.FFexpData["y"] = []
			self.FFexpData["x"] += expspec.x.tolist()
			self.FFexpData["y"] += expspec.y.tolist()
			self.FFexpData["x"], self.FFexpData["y"] = list(zip(*sorted(zip(self.FFexpData["x"], self.FFexpData["y"]))))
		else:
			self.FFexpData["x"] = expspec.x
			self.FFexpData["y"] = expspec.y
		# back to ndarray if necessary
		if not any([isinstance(self.FFexpData[data], type(np.array([]))) for data in ["x","y"]]):
			self.FFexpData["x"] = np.asarray(self.FFexpData["x"])
			self.FFexpData["y"] = np.asarray(self.FFexpData["y"])
		self.FFplotExp.setData(self.FFexpData["x"], self.FFexpData["y"])
		self.FFplotExp.update()
	def FFremoveExp(self):
		"""
		Removes the loaded experimental spectrum from the FF plot.
		"""
		self.FFexpData = {"x":[], "y":[]}
		self.FFplotExp.setData(self.FFexpData["x"], self.FFexpData["y"])
		self.FFplotExp.update()

	def FFaddSticks(self):
		"""
		Provides a dialog to manually add 'stick' lines at specific rest
		frequencies.
		"""
		reload(Dialogs)
		self.FFstickDialog = Dialogs.BasicTextInput(text=self.FFsticks, size=(80,300))
		if not self.FFstickDialog.exec_():
			return
		self.FFsticks = self.FFstickDialog.editor.document().toPlainText()
		sticks = []
		for l in self.FFsticks.split("\n"):
			l = str(l)
			if (l == ""): continue
			if (l[0] == "#"): continue
			try:
				sticks.append(float(l.strip()))
			except ValueError:
				pass
		self.FFplotSticks.setData(x=sticks, height=1,
			pen=pg.mkPen(self.FFsettings['colorExp'], width=1.5, style=QtCore.Qt.DashLine))
		self.FFplotSticks.update()
	def FFclearSticks(self):
		"""
		Removes the manually-added 'stick' lines.
		"""
		self.FFsticks = ""
		self.FFplotSticks.setData(x=self.FFsticks, height=1, pen=pg.mkPen(self.FFsettings['colorExp'], width=1.5))
		self.FFplotSticks.update()

	def FFplotMousePosition(self, mouseEvent):
		"""
		Processes the signal when the mouse is moving above the plot area.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(PyQt4.QtCore.QPointF, None)
		"""
		# process keyboard modifiers and perform appropriate action
		modifier = QtGui.QApplication.keyboardModifiers()
		if modifier == QtCore.Qt.ShiftModifier:
			# convert mouse coordinates to XY wrt the plot
			mousePos = self.FFplotFigure.plotItem.getViewBox().mapSceneToView(mouseEvent[0])
			mouseX, mouseY = mousePos.x(), mousePos.y()
			# define a HTML-formatted text string
			HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'><span style='color:green'>cat: %s</span>"
			HTMLCoordinates += "<br>f=%s<br>unc: %s<br>lgint: %.3f<br>qns: <tt>%s</tt></span></div>"
			nearest = []
			cats = [self.FFplotOrig]
			try:
				if len(self.FFplotNew.opts.get('x')):
					cats.append(self.FFplotNew)
			except TypeError:
				pass
			for i,p in enumerate(cats):
				idx = np.abs(p.opts.get('x') - mouseX).argmin()
				distance = mouseX - p.opts.get('x')[idx]
				nearest.append((distance, i, idx))
			nearestIdx = np.abs([i[0] for i in nearest]).argmin()
			name = [self.FFplotOrig, self.FFplotNew][nearest[nearestIdx][1]].name()
			f = [self.FFplotOrig, self.FFplotNew][nearest[nearestIdx][1]].opts.get('x')[nearest[nearestIdx][2]]
			tIdx = self.FFcats[nearest[nearestIdx][1]].get_idx_from_freq("%g"%f)
			unc = self.FFcats[nearest[nearestIdx][1]].transitions[tIdx].calc_unc
			qns = self.FFcats[nearest[nearestIdx][1]].transitions[tIdx].qn_str
			lgint = np.log10(self.FFcats[nearest[nearestIdx][1]].transitions[tIdx].intensity)
			qns_lo = "%s %s %s %s %s %s" % (qns[:2], qns[2:4], qns[4:6], qns[6:8], qns[8:10], qns[10:12])
			qns_hi = "%s %s %s %s %s %s" % (qns[12:14], qns[14:16], qns[16:18], qns[18:20], qns[20:22], qns[22:24])
			qns_full = qns_lo.rstrip() + "&#8592;" + qns_hi.rstrip()
			self.FFplotMouseLabel.setPos(mouseX, mouseY)
			self.FFplotMouseLabel.setHtml(HTMLCoordinates % (name,f,unc,lgint,qns_full))
		elif modifier == QtCore.Qt.ControlModifier:
			pass
		else:
			self.FFplotMouseLabel.setPos(0,0)
			self.FFplotMouseLabel.setText("")
	def FFplotMouseClicked(self, mouseEvent):
		"""
		Processes the signal when the mouse is clicked within the plot.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent, None)
		"""
		# convert mouse coordinates to XY wrt the plot
		screenPos = mouseEvent[0].screenPos()
		mousePos = mouseEvent[0].scenePos()
		viewBox = self.FFplotFigure.plotItem.getViewBox()
		mousePos = viewBox.mapSceneToView(mousePos)
		mousePos = (mousePos.x(), mousePos.y())
		modifier = QtGui.QApplication.keyboardModifiers()
		# update mouse label if SHIFT
		if modifier == QtCore.Qt.ShiftModifier:
			labelDot = pg.TextItem(text="*",anchor=(0.5,0.5))
			labelDot.setPos(self.CVplotMouseLabel.pos())
			labelDot.setZValue(999)
			self.FFplotFigure.addItem(labelDot, ignoreBounds=True)
			labelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
			labelText.setPos(self.FFplotMouseLabel.pos())
			labelText.setHtml(self.FFplotMouseLabel.textItem.toHtml())
			labelText.setZValue(999)
			self.FFplotFigure.addItem(labelText, ignoreBounds=True)
			self.FFplotLabels.append((labelDot,labelText))
		# update mouse label if CONTROL
		elif modifier == QtCore.Qt.ControlModifier:
			HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 13pt'>x=%.3f"
			HTMLCoordinates += "<br>y=%0.2e</span></div>"
			labelDot = pg.TextItem(text="*",anchor=(0.5,0.5))
			labelDot.setPos(mousePos[0], mousePos[1])
			labelDot.setZValue(999)
			self.FFplotFigure.addItem(labelDot, ignoreBounds=True)
			labelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
			labelText.setPos(mousePos[0], mousePos[1])
			labelText.setHtml(HTMLCoordinates % (mousePos[0], mousePos[1]))
			labelText.setZValue(999)
			self.FFplotFigure.addItem(labelText, ignoreBounds=True)
			self.FFplotLabels.append((labelDot,labelText))
	def FFclearLabels(self):
		"""
		Clears all the labels that may have been added to the plot.
		"""
		for label in self.FFplotLabels:
			self.FFplotFigure.removeItem(label[0])
			self.FFplotFigure.removeItem(label[1])
		self.FFplotLabels = []


	### CA tab
	def CAloadFiles(self, ev=None, inputFile=None):
		"""
		Loads an input/output file from a CALPGM (i.e. SPFIT/SPCAT)
		project and updates various GUI elements with the appropriate
		values/properties.
		
		Note that there is generally a specific order/priority of files
		that are checked when filling out the form:
		mrg -> cat -> par -> var -> int -> lin -> str -> egy
		
		Warning: still a work in progress! Both str and egy files are
		totally ignored, though it's likely that any equivalent data
		should be already be found in the other files.
		"""
		# load file
		self.CAbaseFilename = None
		if inputFile is None:
			directory = self.cwd
			title = "Select an input file.."
			filters = "calpgm files (*.mrg *.cat *.par *.var *.int *.lin *.str *.egy)"
			inputFile = QtGui.QFileDialog.getOpenFileName(
				parent=self,
				caption=title,
				directory=directory,
				filter=filters)
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5.0.0":
				inputFile = inputFile[0]
			else:
				inputFile = str(inputFile)
			if not os.path.isfile(inputFile):
				return
		elif isinstance(inputFile, (list, tuple)):
			inputFile = inputFile[0]
		self.cwd = os.path.realpath(os.path.dirname(inputFile))
		self.CAbaseFilename = os.path.join(self.cwd, os.path.splitext(inputFile)[0])
		# check mrg/cat files
		self.led_CAfoundMrg.toggle(state=os.path.isfile("%s.mrg" % self.CAbaseFilename))
		self.led_CAfoundCat.toggle(state=os.path.isfile("%s.cat" % self.CAbaseFilename))
		catFile, mrgFile = None, None
		if os.path.isfile("%s.cat" % self.CAbaseFilename):
			catFile = "%s.cat" % self.CAbaseFilename
		if os.path.isfile("%s.mrg" % self.CAbaseFilename):
			mrgFile = "%s.mrg" % self.CAbaseFilename
		if (catFile is None):
			catFile = mrgFile
		elif (mrgFile is not None) and (os.path.getmtime(mrgFile) > os.path.getmtime(catFile)):
			catFile = mrgFile # use the merge file only if it exists and is newer
		self.led_CAfoundPar.toggle(state=os.path.isfile("%s.par" % self.CAbaseFilename))
		self.led_CAfoundVar.toggle(state=os.path.isfile("%s.var" % self.CAbaseFilename))
		# check par/var files
		parFile, varFile = None, None
		if os.path.isfile("%s.par" % self.CAbaseFilename):
			parFile = "%s.par" % self.CAbaseFilename
		if os.path.isfile("%s.var" % self.CAbaseFilename):
			varFile = "%s.var" % self.CAbaseFilename
		# check int file
		self.led_CAfoundInt.toggle(state=os.path.isfile("%s.int" % self.CAbaseFilename))
		intFile = None
		if os.path.isfile("%s.int" % self.CAbaseFilename):
			intFile = "%s.int" % self.CAbaseFilename
		# check lin file
		self.led_CAfoundLin.toggle(state=os.path.isfile("%s.lin" % self.CAbaseFilename))
		linFile = None
		if os.path.isfile("%s.lin" % self.CAbaseFilename):
			linFile = "%s.lin" % self.CAbaseFilename
		# not sure whether to care much about str/egy files
		self.led_CAfoundStr.toggle(state=os.path.isfile("%s.str" % self.CAbaseFilename))
		self.led_CAfoundEgy.toggle(state=os.path.isfile("%s.egy" % self.CAbaseFilename))
		# update foo
			# get from catFile
			# get from parFile
			# get from varFile
			# get from intFile
			# get from linFile
			# get from strFile
			# get from egyFile
		### update name
		name = ""
		if parFile is not None: # get from parFile: first 20 chars
			try:
				name = linecache.getline(parFile, 1)[:20].rstrip()
			except:
				raise
		elif (name == "") and (varFile is not None): # get from varFile: first XX chars
			try:
				name = linecache.getline(varFile, 1)[:20].rstrip()
			except:
				raise
		elif (name == "") and (intFile is not None): # get from intFile: first line
			try:
				name = linecache.getline(intFile, 1).rstrip()
			except:
				raise
		# get from strFile
		# get from egyFile
		self.txt_CAname.setText(name)
		### update tag
		tag = ""
		if catFile is not None: # get catFile: specific range of chars
			try:
				tag = linecache.getline(catFile, 1)[44:51].strip()
			except:
				raise
		elif (tag == "") and (intFile is not None): # get from intFile: 2nd entry of 2nd line
			try:
				tag = linecache.getline(intFile, 2).split()[1]
			except:
				raise
		# get from strFile
		# get from egyFile
		self.txt_CAtag.setText(tag)
		### update # lines
		lineCount = ""
		if mrgFile is not None: # get mrgFile: count the negative tags
			lineCount = 0
			fh = open(mrgFile, "r")
			for line in fh:
				if int(line[44:51].strip()) < 0:
					lineCount += 1
			lineCount = "%s" % lineCount
		elif (lineCount == "") and (parFile is not None): # get from parFile: 2nd entry on 2nd line
			try:
				lineCount = linecache.getline(parFile, 2).split()[1]
			except:
				raise
		elif (lineCount == "") and (varFile is not None): # get from varFile: 2nd entry on 2nd line
			try:
				lineCount = linecache.getline(varFile, 2).split()[1]
			except:
				raise
		elif (lineCount == "") and (linFile is not None): # get from intFile: count first set of non-empty lines
			lineCount = 0
			fh = open(linFile, "r")
			for line in fh:
				if len(line.strip()):
					lineCount += 1
				else:
					break
			lineCount = "%s" % lineCount
		# get from strFile
		# get from egyFile
		self.txt_CAlineCount.setText(lineCount)
		### update max freq
		maxFreq = ""
		if catFile is not None: # get catFile: find the highest freq
			maxFreq = 0
			fh = open(catFile, "r")
			for line in fh:
				try:
					maxFreq = max(maxFreq, float(line[:13])/1e3)
				except:
					pass
			maxFreq = "%s" % maxFreq
		elif (maxFreq == "") and (intFile is not None): # get from intFile: 2nd-to-last entry on 2nd line
			try:
				maxFreq = linecache.getline(intFile, 2).split()[-2]
			except:
				raise
		# get from strFile
		# get from egyFile
		self.txt_CAmaxFreq.setText(maxFreq)
		### update max J/F/N
		maxJ = ""
		if catFile is not None: # get catFile: find the highest QN'/QN''[0]
			maxJ = 0
			fh = open(catFile, "r")
			for line in fh:
				try:
					maxJ = max(maxJ, int(line[55:57]), int(line[67:69]))
				except:
					pass
			maxJ = "%s" % maxJ
		elif (maxJ == "") and (intFile is not None): # get from intFile: 5th entry of 2nd line
			try:
				maxJ = linecache.getline(intFile, 2).split()[4]
			except:
				raise
		# get from strFile
		# get from egyFile
		self.txt_CAmaxJ.setText(maxJ)
		### update logstr
		logstr0,logstr1 = "",""
		if intFile is not None: # get from intFile: 6th & 7th entries on 2nd line
			try:
				logstr0,logstr1 = linecache.getline(intFile, 2).split()[5:7]
			except:
				raise
		# get from strFile
		# get from egyFile
		self.txt_CAlogstr0.setText(logstr0)
		self.txt_CAlogstr1.setText(logstr1)
		### update egy
		egy = ""
		if catFile is not None: # get catFile: find lowest egy
			egy = 1e6 # something large..
			fh = open(catFile, "r")
			for line in fh:
				try:
					egy = min(egy, float(line[31:42]))
				except:
					pass
			egy = "%s" % egy
		# get from parFile: not sure about this..
		# get from varFile: not sure about this..
		# get from strFile
		# get from egyFile
		self.txt_CAegy.setText(egy)
		### update dipoles
		constMua,constMub,constMuc = "","",""
		# get from intFile
		### update primary constants
		constA,constB,constC = "","",""
		# get from parFile
		# get from varFile
		# get from intFile
		# get from linFile
		# get from strFile
		# get from egyFile
	def CArepQ(self):
		"""
		For now, this simply prints out some values to the terminal..
		
		Note that holding down "SHIFT" and/or "CTRL+SHIFT" while pressing
		the button in the GUI will activate wavenumber units in the same
		fashion as the "Load Catalog" button of the CV tab..
		"""
		# just in case wavenumbers are preferred...
		kbmods = QtGui.QApplication.keyboardModifiers()
		unit = "MHz"
		tunit = None
		if kbmods == QtCore.Qt.ShiftModifier:
			unit = "wvn"
		elif kbmods == (QtCore.Qt.ShiftModifier | QtCore.Qt.ControlModifier):
			unit = "wvn"
			tunit = "wvn"
		# check/load files
		catFile, mrgFile = None, None
		if os.path.isfile("%s.cat" % self.CAbaseFilename):
			catFile = "%s.cat" % self.CAbaseFilename
		if os.path.isfile("%s.mrg" % self.CAbaseFilename):
			mrgFile = "%s.mrg" % self.CAbaseFilename
		if (catFile is None):
			catFile = mrgFile
		elif (mrgFile is not None) and (os.path.getmtime(mrgFile) > os.path.getmtime(catFile)):
			catFile = mrgFile # use the merge file only if it exists and is newer
		if catFile is None:
			msg = "warning: you don't seem to have a set of files loaded!"
			raise UserWarning(msg)
		# load catalog
		cat = catalog.load_predictions(filename=catFile, unit=unit, tunit=tunit)
		cat.generate_callable_partitionfunc()
		msg = "\ntemp (K)     Partition Function\n"
		msg += "-------------------------------\n"
		for it,t in enumerate(cat.calc_partitionfunc[0]):
			q = cat.calc_partitionfunc[1][it]
			msg += "%-10s   %.4f\n" % (t,q)
		log.info(msg)
	def CArepBlah(self):
		pass
	
	
	### errors/warnings
	def showError(self, msg, e=Exception):
		"""
		Pops up a warning dialog, and raises an Exception.

		:param msg: the descriptive message to print as the main text
		:type msg: str
		"""
		QtGui.QMessageBox.warning(self, "Error! (%s)" % (e,), msg, QtGui.QMessageBox.Ok)
		raise e(msg)
	def showWarning(self,
		msg,
		msgFinal="",
		msgDetails="",
		msgAbort="",
		title="User Warning!"):
		"""
		Provides a general routine that invokes a dialog box with a warning
		message, and allows the user to either ignore the issue or abort.
		Aborting raises a UserWarning, which indeed will stop further
		execution.

		:param msg: the main message to be shown
		:param msgFinal: (optional) an final question
		:param msgDetails: (optional) a body of text that can be shown via a toggle
		:param msgAbort: (optional) a brief summary of what was aborted, instead of the full msg
		:param title: (optional) the title of the pop-up box
		:type msg: str
		:type msgFinal: str
		:type msgDetails: str
		:type msgAbort: str
		:type title: str
		"""
		msgBox = Dialogs.WarningBox()
		msgBox.setWindowTitle(title)
		# add messages
		msgBox.setText(miscfunctions.cleanText(msg))
		if msgFinal:
			msgBox.setInformativeText(miscfunctions.cleanText(msgFinal))
		if msgDetails:
			msgBox.setDetailedText(msgDetails)
		# add buttons
		msgBox.setStandardButtons(QtGui.QMessageBox.Ignore | QtGui.QMessageBox.Abort)
		msgBox.setDefaultButton(QtGui.QMessageBox.Ignore)
		# finally, execute the dialog and abort if needed
		msgResponse = msgBox.exec_()
		if msgResponse == QtGui.QMessageBox.Abort:
			if msgAbort:
				abort = msgAbort
			else:
				abort = msg
			raise UserWarning("Aborted by user: '%s'" % abort)


	### misc
	def initTmpDir(self):
		"""
		Creates a temporary directory, and returns the name. This is
		always done at startup, and it is always removed when the
		interface is closed using the Quit button.

		The parent directory is platform-specific, and the name of the
		directory is random, but prepended with 'qtfit-[USER]-' for
		easy identification. Refer to the tempfile module and its
		mkdtemp() method for more details.
		"""
		import getpass
		user = getpass.getuser()
		prefix = 'qtfit-%s-' % user
		tmpDir = tempfile.mkdtemp(prefix=prefix)
		return tmpDir
	def openTmpDir(self):
		"""
		Loads the current temporary directory, using xdg-open.
		"""
		webbrowser.open(self.tmpDir)
		#try:
		#	subprocess.call(['xdg-open', self.tmpDir])
		#except OSError:
		#	msg = "ERROR: cannot access 'xdg-open' for loading the link!"
		#	msg += " install it via the 'xdg-utils' package..."
		#	msg += "\n\t-> debian/ubuntu: sudo apt-get install xdg-utils"
		#	msg += "\n\t-> macports: sudo port install xdg-utils"
		#	print(msg)

	def runTest(self, inputEvent=None):
		"""
		Invoked when the 'test' button is clicked. It is used only for
		running any temporary tests that might be useful when debugging.
		"""
		log.debug("qtfit.runTest() received the following event: %s" % inputEvent)
		self.lastTestEvent = inputEvent
		testBool = True
		testInt = 457
		testFloat = 3.14152
		testString = "Hello, world!"
		testUnicode = u"Γειά Kóσμε!"
		log.info("qtfit.runTest() does nothing at the moment...")
	def runTest2(self, inputEvent=None):
		"""
		Provides a second routine for tests.. e.g. helpful from console.
		"""
		log.debug("qtfit.runTest2() received the following event: %s" % inputEvent)
		self.lastTestEvent = inputEvent
		testBool = True
		testInt = 457
		testFloat = 3.14152
		testString = "Hello, world!"
		testUnicode = u"Γειά Kóσμε!"
		log.info("qtfit.runTest2() does nothing at the moment...")
	
	def checkForURLmime(self, inputEvent=None):
		if hasattr(inputEvent, "mimeData") and inputEvent.mimeData().hasUrls:
			inputEvent.accept()
		else:
			inputEvent.ignore()

	def launchCASBrowser(self, event=None, usetunnel=False):
		"""
		Launches a browser to the CAS DataManagement server.
		
		The URL to the remote server is (for now) hard-coded. The GUI
		will first try to make a request to the remote server. If that
		fails, it will provide a prompt for the username to SSH to the
		login server.
		"""
		kbmods = QtGui.QApplication.keyboardModifiers()
		reload(Widgets)
		### define URL options
		# if current tunnel, check its status
		if usetunnel and (self.sshtunnel is not None):
			if self.sshtunnel.poll() is None: # process has not yet terminated
				usetunnel = False
			else:
				self.sshtunnel = None # release the old one
		# if no tunnel and the remote server is reachable, force the tunnel anyway
		if not usetunnel:
			try:
				log.info("testing the direct connection to the CAS data server (i.e. via intranet/vpn)..")
				code = urlopen(self.url_CASData, timeout=5).getcode() # timeout is important in this case!
				if not code == 200:
					raise Exception # just raise+catch instead of duplicating code
			except:
				log.info("okay, using an SSH tunnel..")
				usetunnel = True
		### define the URL to use (possibly also setting up the SSH tunnel)
		if usetunnel:
			user, okPressed = QtGui.QInputDialog.getText(self,
				"Enter a username",
				"Username @ login.mpe.mpg.de:\n(use the terminal for passwords)",
				QtGui.QLineEdit.Normal, "")
			if distutils.version.LooseVersion(pg.Qt.QtVersion) < "5":
				user = str(user)
			if okPressed and user != '':
				sshcmd = [
					'ssh',
					#'-N', # no terminal.. will persist if not closed manually!
					'-o', 'ExitOnForwardFailure=yes',
					'%s@login.mpe.mpg.de' % user,
					'-L', '8001:%s' % self.url_CASData.replace("http://","").replace("/",":80"),
					'sleep', '3600', # ensures the tunnel will terminate after 1hr
				]
				### use pexpect to run in background (password prompt -> passed from memory)
				#import pexpect
				#self.sshtunnel = pexpect.spawn(" ".join(sshcmd))
				#self.sshtunnel.expect(['password: '])
				#sshpassword = "thisisatest"
				#self.sshtunnel.sendline(sshpassword)
				### use subprocess.Popen to run in background (password prompt -> terminal)
				self.sshtunnel = subprocess.Popen(
					sshcmd, shell=False,
					#" ".join(cmd), shell=True, # cmd must be string if shell=True
					stdout=subprocess.PIPE,
					stderr=subprocess.PIPE)
				log.info("a SSH tunnel is running under PID %s" % self.sshtunnel.pid)
				url = "http://127.0.0.1:8001/"
			else:
				cmd = "ssh USERNAME@login.mpe.mpg.de -L 8001:cas01int.mpe.mpg.de:80"
				log.info("SSH proxy was canceled.. you could also do it yourself: '%s'" % cmd)
				return
		else:
			url = self.url_CASData
			if kbmods == QtCore.Qt.ShiftModifier:
				# url = "http://127.0.0.1:8000/"
				url = "http://cas-ws02.mpe.mpg.de:8000/"
		### launch the internal browser
		try:
			if distutils.version.LooseVersion(pg.Qt.QtVersion) < "5.6":
				self.showWarning(
					"You have an outdated version of Qt and the CASDataBrowser won't work well.."
					" you're probably better off just using a normal browser instead :(\n"
					"<a href='%s'>%s</a>" % (url, url))
			log.info("will try to launch %s" % url)
			self.CASbrowser = Widgets.CASDataBrowser(self, url, scale=0.8)
			# add hooks so that spectra may be "downloaded" directly into the plots
			if distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5.6":
				self.CASbrowser.page().profile().downloadRequested.connect(self.loadCASspec)
				self.CASbrowser.connectedSignals.append(self.CASbrowser.page().profile().downloadRequested)
			else:
				self.CASbrowser.page().setForwardUnsupportedContent(True)
				self.CASbrowser.page().unsupportedContent.connect(self.loadCASspec)
				self.CASbrowser.connectedSignals.append(self.CASbrowser.page().unsupportedContent)
				self.CASbrowser.page().downloadRequested.connect(self.loadCASspec)
				self.CASbrowser.connectedSignals.append(self.CASbrowser.page().downloadRequested)
			self.CASbrowser.show()
		except:
			log.info("couldn't load the CASData url (%s)" % url)
			if "code" in locals():
				log.info("\tcode was: %s" % code)
			log.info("\terror was: %s" % (sys.exc_info(),))
	def loadCASspec(self, download=None):
		"""
		Provides a method for downloading and plotting spectra directly
		from the CAS data browser.
		"""
		if download is None:
			return
		# download the file
		url = str(download.url().toString())
		r = requests.get(url, allow_redirects=True, timeout=5)
		try:
			r.raise_for_status()
		except:
			log.exception("couldn't access the download item (%s)" % r)
		if (('Content-Disposition' in r.headers) and
			('filename' in r.headers['Content-Disposition'])):
			value, params = cgi.parse_header(r.headers['Content-Disposition'])
			filename = params['filename']
			filename = filename.replace(" ", "_").replace('"', '').replace(os.path.sep, ' ')
			filename = os.path.join(self.tmpDir, filename)
			fh = open(filename, 'wb')
		else:
			fh, filename = tempfile.mkstemp(dir=self.tmpDir)
		for chunk in r.iter_content(1024):
			fh.write(chunk)
		fh.close()
		# load to all the tabs..
		settings = self.defaultLoadSettings.copy()
		settings.update({"filenames": [filename]})
		ext = os.path.splitext(filename)[-1]
		if ext == ".csv":
			settings.update({"filetype": "casac"})
		else:
			raise NotImplementedError("not sure about the filetype: %s" % ext)
		self.CVloadExp(filenames=[filename], settings=settings)
		self.CVexpSettings[-1]['sourceURL'] = url
		self.ESloadScan(filenames=[filename], settings=settings)
		self.BRloadScan(filenames=[filename], settings=settings)
		self.LAloadExp(filenames=[filename], settings=settings)
		self.FFloadExp(filenames=[filename], settings=settings)
	
	def showHelpHTML(self, mouseEvent=False):
		"""
		Calls the HTML documentation via the built-in QWebView widget.
		The documentation is located under `./doc/full/_build/` and
		must be built manually (relative to the main package directory).

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		gui_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
		help_dir = os.path.join(gui_dir, '../doc/full')
		html_path = os.path.realpath(os.path.join(help_dir, '_build/html/GUIs.html'))
		url = "file://%s#module-GUIs.qtfit" % html_path
		log.info("will try to load %s" % url)
		if os.path.isfile(html_path):
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				log.info("\ttip: if you see a black screen and are using PyQt5, try installing PyOpenGL")
				from PyQt5 import QtWebEngineWidgets
				self.helpViewer = QtWebEngineWidgets.QWebEngineView()
			else:
				from PyQt4 import QtWebKit
				self.helpViewer = QtWebKit.QWebView()
			self.helpViewer.setUrl(QtCore.QUrl(url))
			self.helpViewer.show()
		else:
			msg = "the html docs are not available!"
			msg += "try running 'make html' from within '%s'" % help_dir
			QtGui.QMessageBox.warning(self, "Error!", msg, QtGui.QMessageBox.Ok)
			raise UserWarning("Missing documentation: '%s'" % msg)

	def getVAMDCSpeciesList(self, vamdcFile=None, ignoreFileAge=False):
		"""
		Loads the external VAMDC library, and populates an internal
		list of available species.
		"""
		modifier = QtGui.QApplication.keyboardModifiers()
		if (vamdcFile is not None) and os.path.isfile(vamdcFile):
			self.vamdcFile = vamdcFile
		if modifier == QtCore.Qt.ShiftModifier:
			ignoreFileAge = True
			directory = self.cwd
			if os.path.isfile(self.vamdcFile):
				directory = os.path.dirname(self.vamdcFile)
			vamdcFile = QtGui.QFileDialog.getOpenFileName(
				parent=self,
				caption="Choose a saved VAMDC species file (e.g. vamdcSpecies.npy)",
				directory=directory,
				filter="numpy output file (*.npy)")
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				vamdcFile = vamdcFile[0]
			vamdcFile = str(vamdcFile)
			if os.path.isfile(vamdcFile):
				self.vamdcFile = vamdcFile
			else:
				return
		if os.path.isfile(self.vamdcFile) and (ignoreFileAge or
			miscfunctions.getFileAge(self.vamdcFile, unit="days") < 7):
			log.info("attempting to load the vamdc list from %s" % self.vamdcFile)
			vamdcresults = np.load(self.vamdcFile, allow_pickle=False)
			# create new "models" based on the loaded xml
			import vamdclib.results
			time.sleep(1)
			cdmsresults = vamdclib.results.Result(xml=vamdcresults[0])
			jplresults = vamdclib.results.Result(xml=vamdcresults[1])
			cdmsresults.populate_model()
			jplresults.populate_model()
			# generate the internal list
			tmpList = []
			tmpList += [cdmsresults.data['Molecules'][i] for i in cdmsresults.data['Molecules']]
			tmpList += [jplresults.data['Molecules'][i] for i in jplresults.data['Molecules']]
			self.vamdcSpecies = sorted(tmpList, key=lambda i: i.Comment)
			return self.vamdcSpecies
		else:
			try:
				import vamdclib
				from vamdclib import nodes, request
			except ImportError as e:
				msg = "Could not load the external VAMDC library! You must install"
				msg += " it as a separate package.. Open a terminal and run something"
				msg += " like:"
				msg += "\n>pip install git+https://github.com/notlaast/vamdclib.git"
				log.exception(msg)
				self.showError(msg, e=ImportError)
			# initialize query
			tmpList = []
			req = request.Request(verifyhttps=False)
			req.setquery("Select Species")
			nl = nodes.Nodelist()
			self.req = req
			try:
				# query CDMS
				cdms = nl.findnode('CDMS')
				req.setnode(cdms)
				result = req.dorequest()
				if result is None:
					raise UserWarning("There was trouble accessing the VAMDC node 'cdms'..")
				cdmsxml = result.Xml
				tmpList += [result.data['Molecules'][i] for i in result.data['Molecules']]
				# query JPL
				jpl = nl.findnode('JPL')
				req.setnode(jpl)
				result = req.dorequest()
				if result is None:
					raise UserWarning("There was trouble accessing the VAMDC node 'jpl'..")
				jplxml = result.Xml
				tmpList += [result.data['Molecules'][i] for i in result.data['Molecules']]
				# finally, just sort the list
				self.vamdcSpecies = sorted(tmpList, key=lambda i: i.Comment)
			except (KeyboardInterrupt, SystemExit):
				raise
			except:
				msg = "\nThere was a problem performing a request to the VAMDC database!"
				msg += "\n\nYou could try to hold SHIFT while clicking the vamdc button, to"
				msg += "\nmanually choose a VAMDC species list saved from a previous session."
				msg += "\nOr perhaps there was a timeout? You could just try again.."
				msg += "\n\tor.. (for the ambitious)"
				msg += "\nThe VAMDC request can be accessed from the GUI as self.req as."
				msg += "\nan instance variable. If you would like to perform debugging,"
				msg += "\ntry using the console. (remember to replace 'self' with 'gui'..)"
				log.exception(msg)
				log.exception("\nThe Error was:\n\t%s" % sys.exc_info()[1])
				return
			# finally save this list to an offline file
			log.info("saving the vamdc list to %s" % self.vamdcFile)
			if (os.path.isfile(self.vamdcFile)):
				log.debug("but will first delete the old (> 7 days) file at %s.." % self.vamdcFile)
				os.remove(self.vamdcFile)
			try:
				np.save(self.vamdcFile, [cdmsxml, jplxml], allow_pickle=False)
			except:
				log.warning("received an error during the dumping of the VAMDC query!")
			return self.vamdcSpecies
	
	def launchPlotDesigner(self, tab=None):
		reload(Dialogs)
		def merged_dict(d1, d2):
			d3 = d1.copy()
			d3.update(d2)
			return d3
		if tab == "cv":
			flatten = lambda l: [item for sublist in l for item in sublist]
			viewrange = flatten(self.CVplotFigure.getViewBox().state['viewRange'])
			spectra = []
			for sidx,s in enumerate(self.CVexpSpectra):
				settings = self.CVexpSettings[sidx].copy()
				settings.pop('lw') # because qtfit uses *very* small linewidths
				spectra.append(merged_dict({
					'spec' : s['spec'],
					'x' : self.CVexpSpectra[sidx]['x'],
					'y' : self.CVexpSpectra[sidx]['y'],
					'name' : self.CVplotsExp[sidx].name()},
					settings))
			catalogs = [merged_dict({
				'cat' : c,
				'trot' : self.CVcatSettings[cidx]['temp'],
				'scale' : self.CVcatSettings[cidx]['scale'],
				'name' : self.CVplotsCat[cidx].name()},
				self.CVcatSettings[cidx]) for cidx,c in enumerate(self.CVcatalogs)]
			labels = []
			for label in self.CVplotLabels:
				if isinstance(label, (list, tuple)):
					if not label[0].textItem.toPlainText() == "*":
						label = label[0]
					else:
						label = label[1]
					labels.append({
						"text": unicode(label.textItem.toPlainText()),
						"html": label.html,
						"anchor": list(label.anchor),
						"pos": list(label.pos()),
						"fill": miscfunctions.qcolorToRGBA(label.fill)
					})
				else:
					labels.append({
						"text": unicode(label.textItem.toPlainText()),
						"anchor": list(label.anchor),
						"pos": list(label.pos()),
						"fill": miscfunctions.qcolorToRGBA(label.fill)
					})
					if "html" in dir(label):
						labels[-1]["html"] = label.html
			self.PlotDesigner = Dialogs.PlotDesigner(
				spectra=spectra,
				catalogs=catalogs,
				viewrange=viewrange,
				labels=labels)
			self.PlotDesigner.show()
		else:
			raise NotImplementedError("buy Jake a beer..")

	def showConsole(self):
		"""
		Invoked when the 'Console' button is clicked. It provides a new
		window containing an interactive console that provides a direct
		interface to the current python instance, and adds the gui to
		that namespace for direct interactions.
		"""
		namespace = {'self': self}
		msg = "This is an active python console, where 'self' is the gui"
		msg += " object, whereby all its internal items/routines can thus"
		msg += " be made available for direct access."
		msg += "\n\nIf you want to enable additional print messages, run:"
		msg += "\n>self.debugging = True"
		msg += "\n\nEnjoy!"
		self.console = pg.dbg(namespace=namespace, text=msg)
		self.console.ui.catchAllExceptionsBtn.toggle()
		self.console.ui.onlyUncaughtCheck.setChecked(False)
		self.console.ui.runSelectedFrameCheck.setChecked(False)
		self.console.ui.exceptionBtn.toggle()

	def exit(self, confirm=False):
		"""
		Provides the routine that quits the GUI.

		It performs two things upon exit: the temp directory that was
		generated upon startup is deleted, and the Qt application is
		closed in a way that ensures all objects are cleanly destroyed.
		It is thus the cleanest way to exit the application.

		:param confirm: (optional) whether to first use a confirmation dialog
		:type confirm: bool
		"""
		# first invoke the confirmation dialog if necessary
		if confirm:
			msg = "Are you sure you want to exit the program?"
			response = QtGui.QMessageBox.question(self, "Confirmation", msg,
				QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
			if response == QtGui.QMessageBox.No:
				return
		
		# stop ssh tunnel if it exists..
		if ('sshtunnel' in dir(self)) and (self.sshtunnel is not None):
			try:
				self.sshtunnel.kill()
				self.sshtunnel = None
			except:
				pass
		
		# clean up the tmp dir
		if not self.debugging:
			log.debug("cleaning up the tmp dir %s" % self.tmpDir)
			shutil.rmtree(self.tmpDir)
		
		# finally quit
		log.info("**** CLOSING THE APP ****")
		QtCore.QCoreApplication.instance().quit()




if __name__ == '__main__':
	### monkey-patch the system exception hook so that it doesn't totally crash
	log.info("monkey-patching the system exception hook..")
	sys._excepthook = sys.excepthook
	def exception_hook(exctype, value, traceback):
		sys._excepthook(exctype, value, traceback)
	sys.excepthook = exception_hook

	### set up input argument parser
	# define input arguments
	parser = argparse.ArgumentParser()
	from __about__ import __version__
	parser.add_argument('--version', action='version', version=__version__)
	parser.add_argument(
		"-d", "--debug", action='store_true',
		help="whether to add extra print messages to the terminal")
	parser.add_argument(
		"--runtest", action='store_true',
		help="(development only) launches mainGUI.runTest() immediately after setup")
	parser.add_argument(
		"--profile", action='store_true',
		help="whether to collect profiling data while running the GUI")
	parser.add_argument("--geometry", type=str, help="geometry (size) of the window (only takes WxH)")
	parser.add_argument("--timegui", action='store_true', help="whether to time the creation/exit of the GUI")
	parser.add_argument("--timeload", action='store_true', help="whether to time the loading of the files")
	parser.add_argument("-cvsession", "--cvsession", type=str, help="loads a session file (CV tab only)")
	# catalog file
	parser.add_argument("-c", "--catalog", metavar='CATFILE', type=str, nargs='+',
		help="specify a catalog file to load")
	parser.add_argument("--temperature", type=int,
		help="(CV tab only) the temperature in Kelvin to use for loaded catalogs")
	parser.add_argument("--scale", type=float,
		help="(CV tab only) the scale at which to multiply the intensities")
	# spectral files (+ options)
	parser.add_argument("file", type=str, nargs='*',
		help="specify file(s) to load, to several tabs, assuming certain things about the filetypes/filenames")
	parser.add_argument("-s", "--spectra", metavar='SPECFILE', type=str, nargs='+',
		help="specify a spectral file to load")
	parser.add_argument("--filetype", type=str, help="what kind of filetype",
		choices=["ssv", "tsv", "csv", "casac", "jpl", "gesp", "arbdc", "arbs", "ydata", "hidencsv", "fits", "brukeropus", "batopt3ds"])
	parser.add_argument("--append", action='store_true', help="whether to load files as one (vs individually)")
	parser.add_argument("--skipfirst", action='store_true', help="whether to skip the first line in the file")
	parser.add_argument("--unit", type=str, default="MHz",
		choices=["arb","arb.", "cm-1", "um", "Hz", "MHz", "GHz", "THz", "ms", "s", "mass","amu"],
		help="the type of unit for the x-axis")
	parser.add_argument("--scanindex", type=str, help="(certain filetypes only) which scan-index to load")
	parser.add_argument("--delimiter", type=str, help="(arbdc filetype only) what string to use to delimit the text, including Perl-style regular expressions if desired")
	parser.add_argument("--xcol", type=int, help="(arbdc filetype only) column number containing the x-axis")
	parser.add_argument("--ycol", type=int, help="(arbdc filetype only) column number containing the y-axis")
	parser.add_argument("--xstart", type=str, help="(arbs filetype only) with which x-value the first y-value begins")
	parser.add_argument("--xstep", type=str, help="(arbs filetype only) at what step to use for the subsequent y-values")
	parser.add_argument("--preprocess", nargs='+', help="performs some sort of optional preprocessing of the data (try '--preprocess help' for more info)")
	parser.add_argument("--mass", type=float, help="(mass spectra only) which mass to select from a mass spectrum")
	# tab options
	parser.add_argument("-cv", "--viewer", action='store_true', help="use the catalog-viewer tab")
	parser.add_argument("-es", "--stats", action='store_true', help="use the easy-stats tab")
	parser.add_argument("-br", "--debaseline", action='store_true', help="use the baseline-removal tab")
	parser.add_argument("-la", "--assign", action='store_true', help="use the line-assignment tab")
	parser.add_argument("-ff", "--fit", action='store_true', help="use the fit-fidget tab")
	parser.add_argument("-ca", "--catan", action='store_true', help="use the catalog-analysis tab")
	# parse arguments and check for command-specific help requests!
	log.info("parsing input arguments")
	args = parser.parse_args()
	if args.preprocess == ["help"]:
		print("Here's the general help information:\n")
		parser.print_help()
		print("\n-------------------------------------\n")
		print("Here's specific information for preprocessing data during loading:\n")
		msg = "As shown above, you would invoke preprocess directives via:\n"
		msg += "\t--preprocess PREPROCESS1 [PREPROCESS2 ...]\n"
		msg += "and each PREPROCESS option typically requires at least two arguments,\n"
		msg += "first the function and then some values as function-specific arguments, e.g.:\n"
		msg += "\t--preprocess FUNC FUNCARG1 [FUNCARG2 ...]\n\n"
		msg += "But wait---there's more! You can apply more than one function, e.g.:\n"
		msg += "\t--preprocess FUNC1 VAL1 FUNC2 VAL1 VAL2\n\n"
		msg += "The following actions are available:\n"
		msg += "ACTION        DESCRIPTION\n"
		msg += "vlsrShift     Performs a velocity shift VAL1 (m/s) across the frequency axis \n"
		msg += "vlsrFix       Fixes the v_lsr to VAL1 (first removes old value, e.g. via FITS header)\n"
		msg += "shiftX        Shifts the x-axis by a fixed value VAL1\n"
		msg += "shiftY        Shifts the y-axis by a fixed value VAL1\n"
		msg += "scaleY        Scales the y-axis by a fixed value VAL1\n"
		msg += "clipTopY      Clips all y-values to a maximum value VAL1\n"
		msg += "clipBotY      Clips all y-values to a minimum value VAL1\n"
		msg += "clipAbsY      Clips all y-values to a min. -VAL1 and max. +VAL1\n"
		msg += "wienerY       Performs Wiener filter using a window size VAL1 (same as BR tab)\n"
		msg += "medfiltY      Performs a Median filter using a window size VAL1\n"
		msg += "ffbutterY     Performs a low-pass filter using order VAL1 and max Nyquist freq VAL2 (same as BR tab)\n\n"
		msg += "A few warnings:\n"
		msg += "\t- These actions are performed during the loading of every spectrum\n"
		msg += "\t- These actions are only applied to the first tab (catalog viewer)\n"
		msg += "\t- If nothing is loading, you may be calling all the files last, in which\n"
		msg += "\t  case the files themselves are being interpreated as preprocessing\n"
		msg += "\t  options, and you should therefore specify the files using '-s'\n"
		parser.exit(message=msg)

	### define GUI elements
	qApp = QtGui.QApplication(sys.argv)
	icon = QtGui.QIcon(os.path.join(ui_path, 'linespec.svg'))
	qApp.setWindowIcon(icon)
	mainGUI = QtFitGUI()

	### set up a system tray icon and functionalities
	tray = QtGui.QSystemTrayIcon()
	tray.setIcon(icon)
	tray.setVisible(True)
	# define some functionality
	def toggleGUI():
		if mainGUI.isVisible():
			mainGUI.hide()
		else:
			mainGUI.show()
	def trayHide():
		tray.hide()
	def trayActivated(reason=None):
		if reason == tray.Unknown:
			pass
		elif reason == tray.Context:
			pass
		elif reason == tray.DoubleClick:
			mainGUI.hide()
			mainGUI.show()
		elif reason == tray.Trigger:
			pass
		elif reason == tray.MiddleClick:
			toggleGUI()
		else:
			pass
	# create a context menu and set functionalities
	trayMenu = QtGui.QMenu()
	trayActionToggleVis = trayMenu.addAction("toggle visibility", toggleGUI)
	trayActionHide = trayMenu.addAction("hide tray icon", trayHide)
	trayActionExit = trayMenu.addAction("exit", mainGUI.exit)
	tray.setContextMenu(trayMenu)
	trayToolTip = "QtFit system tray usage:\n"
	trayToolTip += "\tright-click: context menu\n"
	trayToolTip += "\tmiddle-click: toggle QtFit visibility\n"
	trayToolTip += "\tdouble-click: bring to top"
	tray.setToolTip(trayToolTip)
	tray.activated.connect(trayActivated)
	mainGUI.tray = tray

	### continue with argument parsing
	if args.debug:
		log.info("activating debugging mode")
		mainGUI.debugging = True
		log.setLevel(logging.DEBUG)
		Dialogs.log.setLevel(logging.DEBUG)
		Widgets.log.setLevel(logging.DEBUG)
		spectrum.log.setLevel(logging.DEBUG)

		log.debug("sys.argv is: %s" % (sys.argv,))
		log.debug("CLI args were: %s" % (args,))
	if args.timegui:
		timegui_start = timer()
	if args.timeload:
		timeload_start = timer()
	if args.cvsession:
		log.info("loading the session file: %s" % args.cvsession)
		mainGUI.CVloadSession(filename=args.cvsession)
	if args.geometry and len(args.geometry.split("x")) == 2:
		try:
			w,h = list(map(int, args.geometry.split("x")))
			mainGUI.resize(w,h)
		except:
			log.warning("there was an error parsing the desired geometry")
	if args.unit == "um":
		args.unit = u"μm" # because argparser apparently can't unicode..
	elif args.unit == "arb":
		args.unit = "arb." # because argparser apparently can't unicode..
	elif args.unit in ["amu", "mass"]:
		args.unit = "mass amu" # CLI shouldn't doesn't like spaces
	if args.scanindex:
		scanindex = []
		for section in args.scanindex.split(","):
			if "-" in section[1:]:
				start = int(section.split("-")[0])
				end = int(section.split("-")[1])
				section = list(range(start,end+1))
				scanindex += section
			else:
				scanindex.append(int(section))
		if len(scanindex) == 1:
			scanindex = scanindex[0]
		args.scanindex = scanindex
	if (len(args.file) and all(os.path.isfile(f) for f in args.file)):
		log.info("trying to automatically guess how to load the file(s)...")
		catFiles = ["cat", "mrg"]
		allAreCatFiles = all(f[-3:] in catFiles for f in args.file)
		if (not args.catalog) and allAreCatFiles :
			log.info("looks like catalog files; will load them into the Catalog Viewer tab...")
			args.catalog = args.file
			#args.viewer = True
		spfitFiles = [
			"mrg", "cat",
			"par", "var",
			"int", "lin",
			"str", "egy",]
		allAreSpfitFiles = all(f[-3:] in spfitFiles for f in args.file)
		hasIntAndVar = any(f[-3:] == "int" for f in args.file) and any(f[-3:] == "var" for f in args.file)
		if ((not args.catalog) and (hasIntAndVar or allAreSpfitFiles) and
			(not any(t for t in [args.viewer, args.assign, args.fit, args.catan]))):
			args.catalog = args.file
			args.fit = True
			args.catan = True
		if (not args.catalog) and (not args.spectra):
			log.info("assuming spectral files...")
			args.spectra = args.file
		if not args.filetype:
			args.filetype = spectrum.guess_filetype(filename=args.spectra)
			log.debug("guessed the filetype(s) should be: %s" % args.filetype)
		if args.spectra and (not any(t for t in [args.viewer, args.stats, args.debaseline, args.assign, args.fit])):
			log.info("no tabs were specified; will try to load into all the tabs that accept spectral files...")
			args.viewer = True
			args.stats = True
			args.debaseline = True
			args.assign = True
			args.fit = True
	if (args.spectra or args.catalog) and not any(t for t in [args.viewer, args.stats, args.debaseline, args.assign, args.fit, args.catan]):
		parser.print_help()
		msg = "\nwarning: You didn't specify which tab you want\n"
		msg += "\nto work with! Defaulting simply to the CV tab.."
		log.info(msg)
		args.viewer = True
	if args.spectra and all(os.path.isfile(f) for f in args.spectra):
		if not args.filetype:
			args.filetype = spectrum.guess_filetype(filename=args.spectra)
			log.debug("guessed the filetype(s) should be: %s" % args.filetype)
		settings = mainGUI.defaultLoadSettings.copy()
		settings.update({
			"filetype" : args.filetype,
			"appendData" : args.append,
			"skipFirst" : args.skipfirst,
			"unit" : args.unit,
			"scanIndex" : args.scanindex,
			"delimiter" : args.delimiter,
			"xcol" : args.xcol,
			"ycol" : args.ycol,
			"xstart" : args.xstart,
			"xstep" : args.xstep,
			"preprocess": args.preprocess,
			"mass": args.mass,
			"filenames" : args.spectra})
		if args.viewer:
			mainGUI.CVloadExp(filenames=settings['filenames'], settings=settings)
			mainGUI.tabWidget.setCurrentWidget(mainGUI.tabCatalogViewer)
		if args.stats:
			settings['appendData'] = True
			log.info("the easy-stats tab doesn't support multiple files; will append them as one...")
			mainGUI.ESloadScan(filenames=settings['filenames'], settings=settings)
			mainGUI.tabWidget.setCurrentWidget(mainGUI.tabEasyStats)
		if args.debaseline:
			settings['appendData'] = True
			log.info("the baseline-removal tab doesn't support multiple files; will append them as one...")
			mainGUI.BRloadScan(filenames=settings['filenames'], settings=settings)
			mainGUI.tabWidget.setCurrentWidget(mainGUI.tabDebaseline)
		if args.assign:
			log.info(settings['filenames'])
			settings['appendData'] = True
			log.info("the line-assignment tab doesn't support multiple files; will append them as one...")
			mainGUI.LAloadExp(filenames=settings['filenames'], settings=settings)
			mainGUI.tabWidget.setCurrentWidget(mainGUI.tabLineAssignments)
		if args.fit:
			settings['appendData'] = True
			log.info("the fit-fidget tab doesn't support multiple files; will append them as one...")
			mainGUI.FFloadExp(filenames=settings['filenames'], settings=settings)
			mainGUI.tabWidget.setCurrentWidget(mainGUI.tabFitFidget)
	if args.catalog and all(os.path.isfile(f) for f in args.catalog):
		if args.viewer:
			mainGUI.CVloadCatalog(catalogs=args.catalog)
			if args.temperature:
				for catIdx,cat in enumerate(mainGUI.CVcatalogs):
					mainGUI.CVcatSettings[catIdx]['temp'] = args.temperature
			if args.scale:
				for catIdx,cat in enumerate(mainGUI.CVcatalogs):
					mainGUI.CVcatSettings[catIdx]['scale'] = args.scale
			mainGUI.CVupdateSimSettings()
			mainGUI.CVupdatePlot()
			mainGUI.tabWidget.setCurrentWidget(mainGUI.tabCatalogViewer)
		if args.assign:
			mainGUI.LAloadCat(catFile=args.catalog)
			mainGUI.tabWidget.setCurrentWidget(mainGUI.tabLineAssignments)
		if args.fit:
			for f in args.catalog:
				if f[-3:] == "int":
					mainGUI.FFloadFiles(inputFile=f)
					mainGUI.tabWidget.setCurrentWidget(mainGUI.tabFitFidget)
					break
		if args.catan:
			mainGUI.CAloadFiles(inputFile=args.catalog[0])
			mainGUI.tabWidget.setCurrentWidget(mainGUI.tabCatAnalysis)
	if args.timeload:
		timeload_stop = timer()
		log.info("time to load the files took %s s" % (timeload_stop - timeload_start))
	if args.runtest:
		mainGUI.runTest()

	### start GUI
	mainGUI.show()
	if args.profile:
		miscfunctions.runsnake(command="qApp.exec_()", globals=globals(), locals=locals())
	else:
		qApp.exec_()
	qApp.deleteLater()
	if args.timegui:
		timegui_stop = timer()
		log.info("time to start/exit GUI took %s s" % (timegui_stop - timegui_start))
	sys.exit()
