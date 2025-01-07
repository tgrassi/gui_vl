#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# TODO
#
#	(HIGH priority)
#
#	(MED priority)
# - add 'ghost' window to show when next pulse cycle picks up
#
#	(LOW priority)
# - fix remaining MFCRead() issues
# - consider removing all "temperature"-related things
# - consider removing frequency sweep things
# - make separate doc for GUI (see CASAC)
#
"""
This module provides a class for the GUI that controls the communication
to the instruments for the CAS jet experiment.

Note that this module is typically called directly as a standalone program.
When this is done, there are a number of optional commandline arguments
that can be used to enhanced functionality. If this is of interest to you,
try calling the file directly with the `-h` or `--help` argument.

Also, see the hover text that appears above each tab, for both generalized
operation, as well as keyboard shortcuts.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
from __future__ import print_function
# standard library
import os
import sys
import logging, logging.handlers
logformat = '%(asctime)s - %(name)s:%(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=logformat)
log = logging.getLogger("jetgui-%s" % os.getpid())
logpath = os.path.expanduser("~/.log/pyLabSpec/jet_gui.log")
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
import time
import datetime
import subprocess
import tempfile
import codecs
import re
from functools import partial
import math
import argparse
import struct
import distutils.version
from timeit import default_timer as timer
import socket
# third-party
import numpy as np
try:
	import pyqtgraph as pg
	from pyqtgraph import siScale
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
from pyqtgraph.Qt import uic
loadUiType = uic.loadUiType
if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
	from PyQt5 import QtWebEngineWidgets    # must be imported now, if ever
	try:
		from OpenGL import GL               # to fix an issue with NVIDIA drivers
	except:
		pass
# local
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import Dialogs
from Dialogs import *
import Widgets
from Widgets import *
import DateAxisItem
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import Instruments
from miscfunctions import *

if sys.version_info[0] == 3:
	from importlib import reload
	log.warning("the transition to python 3 is a work in progress!")




class genericThread(QtCore.QThread):
	"""
	Provides a generic class for the process of spawning a daughter thread
	that runs a specific function. See below for usage.

	From within the parent GUI class, one can do the following (note the
	arguments, which could be removed!):

	:Example:

	>>> self.newThread = genericThread(self.someFunctionToCall, arg1, arg2)
	>>> self.newThread.start()
	>>> def someFunctionToCall(self, arg1, arg2):
	>>> 	doSomeWorkHere..
	"""
	def __init__(self, function, *args, **kwargs):
		"""
		Initializes the thread.

		:param function: the function to call from the thread
		:param args: arguments to pass to the function
		:param kwargs: keywords to pass to the function
		:type function: callable method
		:type args: tuple
		:type kwargs: dict
		"""
		QtCore.QThread.__init__(self)
		self.function = function
		self.args = args
		self.kwargs = kwargs
	@QtCore.pyqtSlot()
	def run(self):
		"""
		Method that is called when the thread is started. It simply makes
		the call to the external function.
		"""
		self.function(*self.args, **self.kwargs)

class genericThreadContinuous(QtCore.QThread):
	"""
	First see the documentation for genericThread, then read the notes
	about the difference that this provides.

	This generic class will continuously run the function, until the stop()
	function is called. Ideally, this stop() would be connected	to a button
	in the GUI, or be referenced under some particular case within the
	function itself.

	For example the first case, via a stop button:

	:Example:

	>>> self.newThread = genericThreadContinuous(self.someFunctionToCall)
	>>> self.newThread.start()
	>>> self.stopButton.clicked.connect(self.newThread.stop)
	>>> def someFunctionToCall(self):
	>>> 	doSomeWorkHere..

	For the second case, via some internal logic checks:

	:Example:

	>>> self.newThread = genericThreadContinuous(self.someFunctionToCall, self.waitTime)
	>>> self.newThread.start()
	>>> def someFunctionToCall(self):
	>>> 	while somethingIsTrue:
	>>> 		doSomeWorkHere
	>>> 		if someTest:
	>>> 			somethingIsTrue = False
	>>> 	self.newThread.stop()
	"""
	def __init__(self, function, waittime=10, *args, **kwargs):
		"""
		See the documentation for genericThread.
		"""
		QtCore.QThread.__init__(self)#, parent=qApp)
		self.function = function
		self.waittime = waittime
		self.args = args
		self.kwargs = kwargs
		self.stopped = 0
		if not isinstance(waittime, int):
			self.waittime = int(round(self.waittime))
			msg = "WARNING! you tried to use a non-int for the waittime (%s for the thread connected to %s)" % (waittime, function)
			log.warning(msg)
	@QtCore.pyqtSlot()
	def run(self):
		"""
		See the documentation for genericThread.
		"""
		while not self.stopped:
			self.function(*self.args,**self.kwargs)
			self.msleep(self.waittime)
	@QtCore.pyqtSlot()
	def start(self, *args, **kwargs):
		"""
		Hijacked start() method, which allows it to also restart.
		"""
		self.stopped = 0
		super(self.__class__, self).start(*args, **kwargs)
	@QtCore.pyqtSlot()
	def stop(self):
		"""
		Stops the continuous thread.
		"""
		self.stopped = 1
		self.terminate()









# determine the correct containing the *.ui files
ui_filename = "JetMainWindow.ui"
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
class SpecGUI(QMainWindow, Ui_MainWindow):
	"""
	Defines the main window of the GUI.
	"""
	signalShowMessage = QtCore.pyqtSignal(str, list)
	signalDisableInstrument = QtCore.pyqtSignal(str)
	signalPressuresUpdateGUI = QtCore.pyqtSignal(str, str, str)
	signalMFCUpdateGUI = QtCore.pyqtSignal(list)
	signalScanUpdateIterLCD = QtCore.pyqtSignal(int)
	signalScanStart = QtCore.pyqtSignal(int, str, str)
	signalScanStop = QtCore.pyqtSignal(bool, bool)
	signalScanSave = QtCore.pyqtSignal(str, str)
	signalScanAlarmRaised = QtCore.pyqtSignal(str)
	signalScanUpdateInfo = QtCore.pyqtSignal()
	signalScanUpdatePlot = QtCore.pyqtSignal()
	signalSWTrigUpdated = QtCore.pyqtSignal()
	signalMonUpdatePlot = QtCore.pyqtSignal()
	def __init__(self):
		"""
		All the functionality of the main buttons should be defined here,
		as well as additional initializations (e.g. the plot window) and
		looping timers.
		"""
		# super is basically mandatory; see
		# http://stackoverflow.com/questions/23981625/why-is-super-used-so-much-in-pyside-pyqt
		# for more info
		super(self.__class__, self).__init__()
		self.setupUi(self)	# was defined in a skeleton automatically
		self.timeGUIStart = datetime.datetime.now()
		self.programName = "Jet Experiment GUI"
		self.programGitHash = miscfunctions.get_git_hash()
		self.setWindowIcon(QtGui.QIcon(os.path.join(ui_path, 'jet_icon.svg')))
		self.debugging = False

		### misc parameters
		self.sensorSaveFile = ""
		# to btn_AdvSettingsFilesInstruments
		self.defaultSaveFile = "~/.jet_gui.conf"
		self.saveperiodSensorData = 30000 # [ms]
		self.updateperiodCheckTab = 500 # [ms]
		self.updateperiodCheckInstruments = 200 # [ms]
		self.updateperiodCheckAlarmLimits = 500 # [ms]
		self.updateperiodPressureUpdate = 500 # [ms]
		self.updateperiodTemperatureUpdate = 500 # [ms]
		self.updateperiodMFCUpdate = 500 # [ms]
		# to btn_AdvSettingsMFC
		self.serialPortMFC = "172.16.27.72"
		# to btn_AdvSettingsDG
		self.ethernetIPDG = "172.16.27.40"
		self.ethernetPortDG = 5024
		# to btn_AdvSettingsSynth
		self.reasonableMaxFreqPoints = 100000
		self.reasonableMaxScanTime = 30 # scan time in [min]
		self.synthFreqResolution = 3 # number of decimals points in [Hz]
		self.maxRFInputStd = 10.0 # [dBm]
		self.maxRFInputHi = 0.0 # [dBm]
		self.RFstepPow = 0.1 # [dBm]
		self.RFstepTime = 0.05 # [s]
		# to btn_AdvSettingsLockin
		self.ethernetIPLockin = "172.16.27.30"
		self.waitForAutoPhase = 0.05 # [s] NOT USED
		self.maxLockinFreq = 500e3 # [Hz] NOT USEFUL
		self.lockinDataRateFull = 100e3 # [Hz]
		self.lockinDataRateThrottled = 10e3 # [Hz]
		self.lockinIntegrationTrigSource = 'TrigIn1'
		self.lockinIntegrationTrigDelay = -4e-3 # [s]
		self.lockinIntegrationRecordTime = 14e-3 # [s]
		# to btn_AdvSettingsPlot
		self.waitBeforeScanRestart = 0.05 # [s]
		self.updateperiodScanUpdateSlow = 500 # [ms]
		self.updateperiodPlotUpdateFast = 50 # [ms]
		self.updateperiodPlotUpdateSlow = 200 # [ms]
		self.spikeFilterThreshold = 10 # int

		### real-time statuses
		self.hasConnectedPressure1 = False
		self.hasConnectedPressure2 = False
		self.hasConnectedTemperature = False
		self.hasConnectedMFC = False
		self.hasConnectedDG = False
		self.hasConnectedSynth = False
		self.hasConnectedLockin = False
		self.isMFCTab = False
		self.isScanTab = False
		self.isMonTab = False
		self.isScanning = False
		self.isPaused = False
		self.isBatchRunning = False
		self.isBatchReadyForNext = False
		self.isScanDirectionUp = True
		self.currentScanIndex = 0
		self.hasPermissionHigherRF = False
		self.scanFinished = False

		### misc items
		self.guiParamsAll = []
		self.guiParamsCollected = []
		self.pressureData = []
		self.temperatureData = []
		self.MFCData = []
		self.sensorSaveFileFH = 0
		self.freqList = []
		self.freqDelay = 0
		self.synthEZFreqCenterHistory = []
		self.scanYvalsAvg = []
		self.swTrig = {}
		self.timeScanStart = 0
		self.timeScanStop = 0
		self.timeScanSave = 0
		self.timeScanPaused = datetime.timedelta(seconds=0)
		self.freqFormattedPrecision = "%f"
		self.scanPlotLabels = []
		self.scanPlotRegion = None
		self.swTrigViewerThread = None
		self.tickFont = QtGui.QFont()
		self.tickFont.setPixelSize(16)

		### define sockets to instruments
		self.socketPressure1 = None
		self.socketPressure2 = None
		self.socketTemperature = None
		self.socketMFC = None
		self.socketDG = None
		self.socketSynth = None
		self.socketLockin = None

		### button functionalities
		# main buttons
		self.btn_Test.clicked.connect(self.runTest)
		self.btn_CheckInputs.clicked.connect(self.checkInputs)
		self.btn_Console.clicked.connect(self.showConsole)
		self.btn_Help.clicked.connect(self.showHelpHTML)
		self.btn_Quit.clicked.connect(self.exit)
		self.btn_Quit.setToolTip("Escape")
		# file buttons
		self.btn_AdvSettingsFilesInstruments.clicked.connect(self.chooseAdvSettingsFilesInstruments)
		self.btn_BrowseSpecOut.clicked.connect(self.browseSpecOut)
		self.btn_SettingsFileBrowseIn.clicked.connect(self.browseSettingsIn)
		self.btn_SettingsFileBrowseOut.clicked.connect(self.browseSettingsOut)
		self.btn_SettingsFileLoad.clicked.connect(self.settingsLoad)
		self.btn_SettingsFileLoad.setToolTip("Ctrl+L")
		self.btn_SettingsFileSave.clicked.connect(self.settingsSave)
		self.btn_SettingsFileSave.setToolTip("Ctrl+S")
		self.btn_SettingsFileSaveAs.clicked.connect(partial(self.settingsSave, prompt=True))
		self.btn_SettingsFileSaveAs.setToolTip("Ctrl+Shift+S")
		# instrument buttons
		self.btn_MFCConnect.clicked.connect(self.connectMFC)
		self.btn_DGConnect.clicked.connect(self.connectDG)
		self.btn_SynthConnect.clicked.connect(self.connectSynth)
		self.btn_LockinConnect.clicked.connect(self.connectLockin)
		self.btn_MFCDisconnect.clicked.connect(self.disconnectMFC)
		self.btn_DGDisconnect.clicked.connect(self.disconnectDG)
		self.btn_SynthDisconnect.clicked.connect(self.disconnectSynth)
		self.btn_LockinDisconnect.clicked.connect(self.disconnectLockin)
		self.btn_ConnectAll.clicked.connect(self.connectAll)
		self.btn_DisconnectAll.clicked.connect(self.disconnectAll)
		# pressure buttons
		self.btn_PGauge1Connect.clicked.connect(partial(self.connectPressure, readout=1))
		self.btn_PGauge1Disconnect.clicked.connect(partial(self.disconnectPressure, readout=1))
		self.btn_PGauge2Connect.clicked.connect(partial(self.connectPressure, readout=2))
		self.btn_PGauge2Disconnect.clicked.connect(partial(self.disconnectPressure, readout=2))
		self.btn_AdvSettingsPressure.clicked.connect(self.chooseAdvSettingsPressure)
		# mfc buttons
		self.slider_MFC1Flow.valueChangedSlow.connect(partial(self.MFCFlowSlider, channel=1))
		self.btn_MFC1Set.clicked.connect(partial(self.MFCSet, channel=1))
		self.btn_MFC1Read.clicked.connect(partial(self.MFCRead, channel=1))
		self.btn_MFC1Open.clicked.connect(partial(self.MFCOpen, channel=1))
		self.btn_MFC1Close.clicked.connect(partial(self.MFCClose, channel=1))
		self.slider_MFC2Flow.valueChangedSlow.connect(partial(self.MFCFlowSlider, channel=2))
		self.btn_MFC2Set.clicked.connect(partial(self.MFCSet, channel=2))
		self.btn_MFC2Read.clicked.connect(partial(self.MFCRead, channel=2))
		self.btn_MFC2Open.clicked.connect(partial(self.MFCOpen, channel=2))
		self.btn_MFC2Close.clicked.connect(partial(self.MFCClose, channel=2))
		self.slider_MFC3Flow.valueChangedSlow.connect(partial(self.MFCFlowSlider, channel=3))
		self.btn_MFC3Set.clicked.connect(partial(self.MFCSet, channel=3))
		self.btn_MFC3Read.clicked.connect(partial(self.MFCRead, channel=3))
		self.btn_MFC3Open.clicked.connect(partial(self.MFCOpen, channel=3))
		self.btn_MFC3Close.clicked.connect(partial(self.MFCClose, channel=3))
		self.slider_MFC4Flow.valueChangedSlow.connect(partial(self.MFCFlowSlider, channel=4))
		self.btn_MFC4Set.clicked.connect(partial(self.MFCSet, channel=4))
		self.btn_MFC4Read.clicked.connect(partial(self.MFCRead, channel=4))
		self.btn_MFC4Open.clicked.connect(partial(self.MFCOpen, channel=4))
		self.btn_MFC4Close.clicked.connect(partial(self.MFCClose, channel=4))
		self.btn_MFCSetRatio.clicked.connect(self.MFCSetRatio)
		self.btn_MFCStopRatio.clicked.connect(self.MFCStopRatio)
		self.btn_MFCSetAll.clicked.connect(self.MFCSetAll)
		self.btn_MFCReadAll.clicked.connect(self.MFCReadAll)
		self.btn_MFCOpenAll.clicked.connect(self.MFCOpen)
		self.btn_MFCCloseAll.clicked.connect(self.MFCClose)
		self.btn_MFCClear.clicked.connect(self.MFCClear)
		self.btn_AdvSettingsMFC.clicked.connect(self.chooseAdvSettingsMFC)
		# dg buttons
		self.check_LockPulsePlotAxes.stateChanged.connect(self.DGUpdatePlotAxisLocks)
		self.btn_DGSetValues.clicked.connect(self.DGSetValues)
		self.btn_DGReadValues.clicked.connect(self.DGReadValues)
		self.btn_AdvSettingsDG.clicked.connect(self.chooseAdvSettingsDG)
		# synth buttons
		self.btn_ActivateBatchScanMode.clicked.connect(self.tabBatchOn)
		self.btn_DisableBatchScanMode_2.clicked.connect(self.tabBatchOff)
		self.btn_SynthEZFreqCenterUseLabel.clicked.connect(self.SynthEZFreqCenterUseLabel)
		self.btn_SynthEZFreqCenterApply.clicked.connect(self.SynthEZFreqCenterSet)
		self.btn_SynthEZFreqShiftDown.clicked.connect(self.SynthEZFreqShiftDown)
		self.btn_SynthEZFreqShiftUp.clicked.connect(self.SynthEZFreqShiftUp)
		self.btn_SynthEZFreqCursorsApply.clicked.connect(self.SynthEZFreqCursorsSet)
		self.btn_GetMultFactor.clicked.connect(self.setMultFactor)
		self.btn_GetFrequencies.clicked.connect(self.setFrequencies)
		self.btn_SynthSetValues.clicked.connect(self.SynthSetValues)
		self.btn_SynthSetValues.setToolTip("Ctrl+S")
		self.btn_SynthReadValues.clicked.connect(self.SynthReadValues)
		self.btn_SynthReadValues.setToolTip("Ctrl+R")
		self.btn_AdvSettingsSynth.clicked.connect(self.chooseAdvSettingsSynth)
		# lia buttons
		self.btn_LockinPhaseAuto.clicked.connect(self.LockinPhaseAuto)
		self.btn_LockinSWTrigSet.clicked.connect(self.LockinSWTrigSet)
		self.btn_LockinSWTrigClear.clicked.connect(self.LockinSWTrigClear)
		self.btn_LockinDetInputHEB.clicked.connect(self.LockinSetInputsHEB)
		self.btn_LockinDetInputZBD.clicked.connect(self.LockinSetInputsZBD)
		self.btn_LockinSetValues.clicked.connect(self.LockinSetValues)
		self.btn_LockinSetValues.setToolTip("Ctrl+S")
		self.btn_LockinReadValues.clicked.connect(self.LockinReadValues)
		self.btn_LockinReadValues.setToolTip("Ctrl+R")
		self.slider_LockinPhase.valueChanged.connect(self.LockinUpdatePhaseText)
		self.btn_AdvSettingsLockin.clicked.connect(self.chooseAdvSettingsLockin)
		# batch buttons
		self.btn_BatchAddEntry.clicked.connect(self.batchAddEntry)
		self.btn_BatchClear.clicked.connect(self.batchClearTable)
		self.btn_BatchStart.clicked.connect(self.batchStart)
		self.btn_BatchStop.clicked.connect(self.batchStop)
		self.btn_DisableBatchScanMode.clicked.connect(self.tabBatchOff)
		# scan buttons
		self.btn_ScanStart.clicked.connect(self.scanStart)
		self.btn_ScanStart.setToolTip("Return")
		self.btn_ScanStop.clicked.connect(self.scanStop)
		self.btn_ScanStop.setToolTip("Return")
		self.btn_ScanPause.clicked.connect(self.scanPause)
		self.btn_ScanPause.setToolTip("Space")
		self.btn_ScanContinue.clicked.connect(self.scanContinue)
		self.btn_ScanContinue.setToolTip("Space")
		self.btn_ScanClearScans.clicked.connect(self.scanPlotClearScans)
		self.btn_ScanClearScans.setToolTip("Shift+Delete")
		self.btn_ScanClearLabels.clicked.connect(self.scanPlotClearLabels)
		self.btn_ScanClearLabels.setToolTip("Delete")
		self.btn_ScanSave.clicked.connect(self.scanSave)
		self.btn_ScanLoad1.clicked.connect(self.scanLoad)
		self.btn_ScanLoad1.setToolTip("Ctrl+L")
		self.btn_ScanLoad2.clicked.connect(partial(self.scanLoad,toSecond=True))
		self.btn_ScanClear1.clicked.connect(self.scanClearExtra)
		self.btn_ScanClear2.clicked.connect(partial(self.scanClearExtra,toSecond=True))
		self.btn_OpenSensorViewer.clicked.connect(self.showSensorViewer)
		self.btn_OpenSWTrigViewer.clicked.connect(self.showSWTrigViewer)
		self.btn_AdvSettingsScan.clicked.connect(self.chooseAdvSettingsScan)
		# monitor buttons
		self.btn_MonFreqFromLabel.clicked.connect(self.monFreqFromLabel)
		self.btn_MonStart.clicked.connect(self.monStart)
		self.btn_MonStart.setToolTip("Return")
		self.btn_MonStop.clicked.connect(self.monStop)
		self.btn_MonStop.setToolTip("Return")

		### modify/redefine certain GUI elements
		self.txt_MFC1FSabs.opts['formatString'] = "%.2f"
		self.txt_MFC2FSabs.opts['formatString'] = "%.2f"
		self.txt_MFC3FSabs.opts['formatString'] = "%.2f"
		self.txt_MFC4FSabs.opts['formatString'] = "%.2f"
		self.txt_MFC1FSabs.opts['constStep'] = 1
		self.txt_MFC2FSabs.opts['constStep'] = 1
		self.txt_MFC3FSabs.opts['constStep'] = 1
		self.txt_MFC4FSabs.opts['constStep'] = 1
		self.txt_SynthFreqStart.opts['formatString'] = "%.3f"
		self.txt_SynthFreqStart.opts['constStep'] = 1
		self.txt_SynthFreqEnd.opts['formatString'] = "%.3f"
		self.txt_SynthFreqEnd.opts['constStep'] = 1
		self.txt_SynthFreqStep.opts['formatString'] = "%.4f"
		self.txt_SynthFreqStep.opts['relStep'] = 50
		self.txt_SynthDelay.opts['formatString'] = "%d"
		self.txt_SynthDelay.opts['constStep'] = 1
		self.txt_SynthEZFreqCenter.opts['formatString'] = "%.3f"
		self.txt_SynthEZFreqCenter.opts['constStep'] = 1
		self.txt_SynthEZFreqSpan.opts['formatString'] = "%.1f"
		self.txt_SynthEZFreqSpan.opts['constStep'] = 1
		self.txt_SynthSkipCenterFreq.opts['formatString'] = "%.1f"
		self.txt_SynthSkipCenterFreq.opts['constStep'] = 0.1
		self.txt_SynthAMFreq.opts['formatString'] = "%.1f"
		self.txt_SynthAMFreq.opts['constStep'] = 5
		self.txt_SynthFMFreq.opts['formatString'] = "%.1f"
		self.txt_SynthFMFreq.opts['constStep'] = 0.5
		self.txt_SynthFMWidth.opts['formatString'] = "%d"
		self.txt_SynthFMWidth.opts['constStep'] = 50
		self.txt_LockinPhase.opts['formatString'] = "%.1f"
		self.txt_LockinPhase.opts['constStep'] = 1
		self.txt_MonFreq.opts['formatString'] = "%.3f"
		self.txt_MonFreq.opts['constStep'] = 1

		### define the contents of various comboboxes
		self.serialPorts = [
			"/dev/ttyS0",
			"172.16.27.12",
			"172.16.27.72"]
		# pressure ports/channels
		for p in self.serialPorts:
			self.combo_PGauge1Port.addItem(p)
			self.combo_PGauge2Port.addItem(p)
		self.combo_PGauge1Port.setCurrentIndex(self.serialPorts.index("/dev/ttyS0"))
		self.combo_PGauge2Port.setCurrentIndex(self.serialPorts.index("172.16.27.72"))
		# MFCs
		try:
			from Instruments import massflowcontroller
		except ImportError as e:
			log.exception(e)
			log.exception("Could not load the pyLapSpec library for the mass flow controller!")
			self.combo_MFC1Range.addItem("(no MFC lib)")
			self.combo_MFC1Gas.addItem("(no MFC lib)")
			self.combo_MFC2Range.addItem("(no MFC lib)")
			self.combo_MFC2Gas.addItem("(no MFC lib)")
			self.combo_MFC3Range.addItem("(no MFC lib)")
			self.combo_MFC3Gas.addItem("(no MFC lib)")
			self.combo_MFC4Range.addItem("(no MFC lib)")
			self.combo_MFC4Gas.addItem("(no MFC lib)")
		else:
			# MFC gas types
			self.MFCgasproperties = massflowcontroller.MassFlowController.gas_properties
			self.MFCgastypes = sorted(
				list(self.MFCgasproperties.keys()),
				key=lambda x: re.sub(r'^[\d,\-]*','',x))
			for ig,g in enumerate(self.MFCgastypes):
				ttip = ""
				for p in sorted(list(self.MFCgasproperties[g].keys())):
					pval = "%s" % self.MFCgasproperties[g][p]
					if not len(pval):
						pval = "n/a"
					ttip += "%s: %s\n" % (p, pval)
				ttip = ttip[:-1]
				self.combo_MFC1Gas.addItem(g)
				self.combo_MFC2Gas.addItem(g)
				self.combo_MFC3Gas.addItem(g)
				self.combo_MFC4Gas.addItem(g)
				self.combo_MFC1Gas.setItemData(ig, ttip, QtCore.Qt.ToolTipRole)
				self.combo_MFC2Gas.setItemData(ig, ttip, QtCore.Qt.ToolTipRole)
				self.combo_MFC3Gas.setItemData(ig, ttip, QtCore.Qt.ToolTipRole)
				self.combo_MFC4Gas.setItemData(ig, ttip, QtCore.Qt.ToolTipRole)
			self.combo_MFC1Gas.setCurrentIndex(self.MFCgastypes.index("Air"))
			self.combo_MFC2Gas.setCurrentIndex(self.MFCgastypes.index("Air"))
			self.combo_MFC3Gas.setCurrentIndex(self.MFCgastypes.index("Air"))
			self.combo_MFC4Gas.setCurrentIndex(self.MFCgastypes.index("Air"))
			# MFC ranges
			unitorder = ["SCCM"]
			self.MFCranges = sorted(
				massflowcontroller.MKS_946.range_units,
				key=lambda x: (
					unitorder.index(x.split(' ')[1]),
					int(x.split(' ')[0])))
			for r in self.MFCranges:
				self.combo_MFC1Range.addItem(r)
				self.combo_MFC2Range.addItem(r)
				self.combo_MFC3Range.addItem(r)
				self.combo_MFC4Range.addItem(r)
			self.combo_MFC1Range.setCurrentIndex(self.MFCranges.index("100 SCCM"))
			self.combo_MFC2Range.setCurrentIndex(self.MFCranges.index("20 SCCM"))
			self.combo_MFC3Range.setCurrentIndex(self.MFCranges.index("20 SCCM"))
			self.combo_MFC4Range.setCurrentIndex(self.MFCranges.index("20 SCCM"))
			# MFC pressure units
			self.MFCpressures = massflowcontroller.MKS_946.pressure_units
			for p in self.MFCpressures:
				self.combo_MFCPUnit.addItem(p)
			self.combo_MFCPUnit.setCurrentIndex(self.MFCpressures.index("MBAR"))
		# double sliders
		self.slider_MFC1Flow.setRange(maxInt=1000, sigRate=2)
		self.slider_MFC2Flow.setRange(maxInt=1000, sigRate=2)
		self.slider_MFC3Flow.setRange(maxInt=1000, sigRate=2)
		self.slider_MFC4Flow.setRange(maxInt=1000, sigRate=2)
		# modulation shapes
		self.modShapes = [
			('Sine', 'SINE'),
			('Square', 'SQU'),
			('Triangle', 'TRI')
		]
		for shapeHuman,shapeMachine in self.modShapes:
			self.combo_SynthAMShape.addItem(shapeHuman)
			self.combo_SynthFMShape.addItem(shapeHuman)
		self.combo_SynthAMShape.setCurrentIndex(1)
		# lockin sensitivity and time constant
		try:
			from Instruments import lockin
		except ImportError:
			log.exception("Could not load the pyLapSpec library for the lockin!")
			self.combo_LockinSensitivity.addItem("(no LIA lib)")
			self.combo_LockinTau.addItem("(no LIA lib)")
		else:
			self.lockinSensitivityList = sorted(list(lockin.sr830.sensitivity_list))
			self.lockinSensitivityList.reverse() # so that the larger values are higher
			for val in self.lockinSensitivityList:
				self.combo_LockinSensitivity.addItem(pg.siFormat(val, suffix="V"))
			self.lockinTimeConstantList = sorted(list(lockin.mfli.time_constant_list))
			self.lockinTimeConstantList.reverse()
			for val in self.lockinTimeConstantList:
				self.combo_LockinTau.addItem(pg.siFormat(val, suffix="s"))
			threemsIndex = np.abs([i - 30e-6 for i in self.lockinTimeConstantList]).argmin()
			self.combo_LockinTau.setCurrentIndex(threemsIndex)
		# lockin phase slider
		self.slider_LockinPhase.setRange(maxInt=3600, minFloat=-180.0, maxFloat=180.0)
		# lockin trigger
		self.lockinTriggerSources = ('cont', '1', '2', 'both')
		self.lockinTriggerModes = ('cont', 'rise', 'fall', 'both', 'high', 'low')
		for s in self.lockinTriggerSources:
			self.combo_LockinTriggerSrc.addItem(s)
		for s in self.lockinTriggerModes:
			self.combo_LockinTriggerMode.addItem(s)
		# multiplier bands
		self.AMCBandSpecs = {
			"9.0": {"Standard":9, "High":3, "Range":(82,125)},
			"6.5": {"Standard":3, "High":np.nan, "Range":(110,170)},
			"4.3": {"Standard":18, "High":6, "Range":(170,260)},
			"2.8": {"Standard":27, "High":9, "Range":(260,390)},
			"2.2": {"Standard":36, "High":12, "Range":(325,500)},
			"1.5": {"Standard":54, "High":18, "Range":(500,750)},
			"1.0": {"Standard":81, "High":27, "Range":(750,1100)},
			"0.65, AMC 680": {"Standard":96, "High":np.nan, "Range":(1100,1200)},
			"0.65, AMC 684": {"Standard":108, "High":np.nan, "Range":(1190,1410)},
			"0.65, AMC 685": {"Standard":108, "High":np.nan, "Range":(1410,1580)}
		}
		for b in ["(manual)"]+sorted(list(self.AMCBandSpecs.keys()), reverse=True):
			self.combo_AMCband.addItem(b)
		for m in ["(manual)", "Standard", "High"]:
			self.combo_AMCmode.addItem(m)

		### Initialize special widgets
		self.temperatureDiagramInit()
		self.batchClearTable()
		self.tabBatchOff()
		self.pulsePlotInit()
		self.scanPlotInit()
		self.monPlotInit()

		### Background Threads
		# check the active tab
		self.timerCheckTab = genericThreadContinuous(self.checkCurrentTab, self.updateperiodCheckTab)
		self.timerCheckTab.start()
		# check the instrument connections
		self.timerCheckInstruments = genericThreadContinuous(self.checkInstruments, self.updateperiodCheckInstruments)
		self.timerCheckInstruments.start()
		# save the sensor readings
		self.timerSensorSaveCont = genericThreadContinuous(self.saveSensorData, self.saveperiodSensorData)
		self.timerSensorSaveCont.start()
		# update the pressures
		self.timerPressureUpdateCont = genericThreadContinuous(self.pressureUpdate, self.updateperiodPressureUpdate)
		self.timerPressureUpdateCont.start()
		# update the temperatures
		self.timerTemperatureUpdate = genericThreadContinuous(self.temperatureUpdate, self.updateperiodTemperatureUpdate)
		#self.timerTemperatureUpdate.start()
		# update the mass flow controllers
		self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
		self.timerMFCUpdate.start()
		# update the scan info, and initialize plot-updaters
		# note: the plot updaters are (re-)started only by their respective start buttons
		self.timerScanUpdateInfo = genericThreadContinuous(self.scanUpdateSlow, self.updateperiodScanUpdateSlow)
		self.timerScanUpdateInfo.start()
		self.timerScanUpdatePlot = genericThreadContinuous(self.scanPlotUpdate, self.updateperiodPlotUpdateFast)
		self.timerMonUpdatePlot = genericThreadContinuous(self.monPlotUpdate, self.updateperiodPlotUpdateFast)
		self.timerCheckAlarmLimits = genericThreadContinuous(self.alarmCheckLimits, self.updateperiodCheckAlarmLimits)
		self.timerCheckAlarmLimits.start()


		### Connect scan-related signals/slots
		self.signalShowMessage.connect(self.showMsgByThread)
		self.signalDisableInstrument.connect(self.disableInstrument)
		self.signalPressuresUpdateGUI.connect(self.pressureUpdateGUI)
		self.signalMFCUpdateGUI.connect(self.MFCUpdateGUI)
		self.signalScanUpdateIterLCD.connect(self.scanUpdateIterLCD)
		self.signalScanStart.connect(self.scanStartByScanThread)
		self.signalScanStop.connect(self.scanStopByScanThread)
		self.signalScanSave.connect(self.scanSaveByScanThread)
		self.signalScanAlarmRaised.connect(self.alarmRaised)
		self.signalScanUpdateInfo.connect(self.scanUpdateInfoByThread)
		self.signalScanUpdatePlot.connect(self.scanUpdatePlotByThread)
		self.signalMonUpdatePlot.connect(self.monUpdatePlotByThread)

		### add keyboard shortcuts
		self.keyShortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, partial(self.exit, confirm=True))
		# switch tabs
		self.keyShortcutCtrlPgUp = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+PgUp"), self, self.prevTab)
		self.keyShortcutCtrlPgDown = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+PgDown"), self, self.nextTab)
		self.keyShortcutCtrlTab = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Tab"), self, self.nextTab)
		self.keyShortcutCtrlShiftTab = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Tab"), self, self.prevTab)
		# ctrl+a -> autoscale the new scan
		self.keyShortcutCtrlA = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+A"), self, self.keyboardCtrlA)
		# ctrl+c -> copy average spectrum
		self.keyShortcutCtrlC = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+C"), self, self.scanPlotCopy)
		# ctrl+l -> load settings or (not yet) load scan
		self.keyShortcutCtrlL = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self, self.keyboardCtrlL)
		# ctrl+r -> read values
		self.keyShortcutCtrlL = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+R"), self, self.keyboardCtrlR)
		# ctrl+s -> save settings, set values, or save scan
		self.keyShortcutCtrlS = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+S"), self, self.keyboardCtrlS)
		# ctrl+shift+s -> save copy of settings
		self.keyShortcutCtrlShiftS = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+S"), self, self.keyboardCtrlShiftS)
		# ctrl+z -> delete last label
		self.keyShortcutCtrlZ = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, self.keyboardCtrlZ)
		# ctrl+o -> ?
		self.keyShortcutCtrlShiftO = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+O"), self, self.keyboardCtrlO)
		# synth tab: return -> apply EZ freq center
		self.keyShortcutEZFreqCenterApply = QtGui.QShortcut(QtGui.QKeySequence("Return"), self.frame_EZFreqCenter, self.SynthEZFreqCenterSet)
		# scan tab: return -> start/stop, space -> pause/continue, delete -> clear
		self.keyShortcutScanStart = QtGui.QShortcut(QtGui.QKeySequence("Return"), self.frame_ScanPlotArea, self.scanToggleStartStop)
		self.keyShortcutScanPauseToggle = QtGui.QShortcut(QtGui.QKeySequence("Space"), self.frame_ScanPlotArea, self.scanPauseToggle)
		self.keyShortcutScanClearLabels = QtGui.QShortcut(QtGui.QKeySequence("Delete"), self.frame_ScanPlotArea, self.scanPlotClearLabels)
		self.keyShortcutScanClear = QtGui.QShortcut(QtGui.QKeySequence("Shift+Delete"), self.frame_ScanPlotArea, self.scanPlotClearScans)
		# monitor tab: return -> start/stop, space -> pause/continue
		self.keyShortcutMonStart = QtGui.QShortcut(QtGui.QKeySequence("Return"), self.frame_MonitorPlotArea, self.monToggleStartStop)




	### misc
	def runTest(self, mouseEvent=False):
		"""
		Just a dummy routine for quick access via the 'Test' button.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		log.debug("jet_gui.test() does nothing at the moment...")

	def showHelpHTML(self, mouseEvent=False):
		"""
		Calls the HTML documentation via the built-in QWebView widget.
		The documentation is located under `./doc/full/_build/` and
		must be built manually.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		gui_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
		help_dir = os.path.join(gui_dir, '../../doc/full')
		html_path = os.path.realpath(os.path.join(help_dir, '_build/html/GUIs.html'))
		url = "file://%s#module-GUIs.jet_gui" % html_path
		log.info("will try to load %s" % url)
		if os.path.isfile(html_path):
			if distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5.6":
				log.info("tip: if you see a black screen and are using PyQt5, try installing PyOpenGL")
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

	def saveSensorData(self, mouseEvent=False):
		"""
		Is periodically called for saving the various sensor readings.
		This routine checks that a save file is defined, and if not,
		defines it. It then walks through each type of sensor, collects
		the reading, and then writes to file.

		Note that the format of the datetime string will always be:
		YYYY-MM-DD hh:mm:ss,
		where the seconds are only in integer form.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# immediately exit is none of the sensors are to be saved
		saveChecks = [
			self.check_SavePressures,
			self.check_SaveTemps,
			self.check_SaveMFCs]
		if not any([i.isChecked() for i in saveChecks]):
			return
		# define the save file
		dt = datetime.datetime.now()
		if self.sensorSaveFile == "":
			saveDir = str(self.txt_SpecOut.text())
			saveDir += "/" + str(datetime.date(dt.year, dt.month, dt.day))
			saveDir = os.path.expanduser(saveDir)
			if not os.path.exists(saveDir):
				os.makedirs(saveDir)
			self.sensorSaveFile = saveDir + "/" + str(self.timeGUIStart)[:-4]
			self.sensorSaveFile = self.sensorSaveFile.replace(':', '-').replace(' ', '__')
			self.sensorSaveFile += "__sensor_data.csv"
		# set the file handle and write the header
		if not self.sensorSaveFileFH:
			try:
				self.sensorSaveFileFH = codecs.open(self.sensorSaveFile, 'w', encoding='utf-8')
				self.sensorSaveFileFH.write('time')
				self.sensorSaveFileFH.write(',pressure1,pressure2a,pressure2b')
				self.sensorSaveFileFH.write(',temperature1,temperature2,temperature3,temperature4,temperature5')
				self.sensorSaveFileFH.write(',mfc1,mfc2,mfc3,mfc4')
				self.sensorSaveFileFH.write('\n')
			except IOError:
				return
		# initialize readings
		readingTime = ""
		readingPressure1,readingPressure2a,readingPressure2b = "","",""
		readingTemperature1,readingTemperature2,readingTemperature3,readingTemperature4,readingTemperature5 = "","","","",""
		readingMFC1,readingMFC2,readingMFC3,readingMFC4 = "","","",""
		# perform readings
		readingTime = datetime.datetime.now() # will this always be the same format?
		if self.check_SavePressures.isChecked():
			readingPressure1 = self.txt_PGauge1Reading.text()
			readingPressure2a = self.txt_PGauge2aReading.text()
			readingPressure2b = self.txt_PGauge2bReading.text()
		if self.check_SaveTemps.isChecked():
			readingTemperature1 = self.lcd_TempLeft.value()
		if self.check_SaveMFCs.isChecked():
			readingMFC1 = self.txt_MFC1CurrentFlow.text()
			readingMFC2 = self.txt_MFC2CurrentFlow.text()
			readingMFC3 = self.txt_MFC3CurrentFlow.text()
			readingMFC4 = self.txt_MFC4CurrentFlow.text()
		# write readings
		self.sensorSaveFileFH.write('%s' % (readingTime))
		self.sensorSaveFileFH.write(',%s,%s,%s' % (readingPressure1,readingPressure2a,readingPressure2b))
		self.sensorSaveFileFH.write(',%s,%s,%s,%s,%s' % (readingTemperature1,readingTemperature2,readingTemperature3,readingTemperature4,readingTemperature5))
		self.sensorSaveFileFH.write(',%s,%s,%s,%s' % (readingMFC1,readingMFC2,readingMFC3,readingMFC4))
		self.sensorSaveFileFH.write('\n')
		self.sensorSaveFileFH.flush() # force the output of the buffer

	def showSensorViewer(self, mouseEvent=False):
		"""
		Loads the sensor viewer in a separate window.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		filename = None
		contFileUpdate = False
		if not self.sensorSaveFile == "":
			filename = self.sensorSaveFile
			contFileUpdate = True
		self.sensorViewerThread = CASACSensorViewer(
			gui=self, filename=filename, contFileUpdate=contFileUpdate)
		self.sensorViewerThread.show()
	
	def showSWTrigViewer(self, mouseEvent=False):
		"""
		Loads a separate window for viewing the full data set
		extracted from the lockin's SW Trigger.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		reload(Dialogs)
		if "swTrigViewerThread" in dir(self) and self.swTrigViewerThread is not None:
			self.swTrigViewerThread = None
		self.swTrigViewerThread = Dialogs.JetMFLISWTriggerViewer(parent=self)
		self.swTrigViewerThread.show()
	
	def doSWTrigFilter(self, sample):
		"""
		Performs a numerical filter on the current sample data, based on the
		widgets set in the SWTrig viewer.
		
		:param sample: the data read and processed from the MFLI during SpecGUI.scanRunFreqLoop()
		:type sample: dict
		"""
		sample['xBackup'] = sample['x'].copy() # just in case things go bad
		filtMethod = self.swTrigViewerThread.combo_useFilter2.currentIndex()
		filtType = self.swTrigViewerThread.combo_filterType.currentIndex()
		filtCoeff1 = self.swTrigViewerThread.txt_filterCoeff1.value()
		filtCoeff2 = self.swTrigViewerThread.txt_filterCoeff2.value()
		try:
			if filtType == 0:
				log.warning("you haven't selected a filter to perform!")
				return
			elif filtType == 1:
				if filtCoeff1 == 0.0:
					log.warning("you must set an absolute cutoff for the clipAbsY filter!")
					return
				sample['x'] = np.clip(sample['x'], -filtCoeff1, filtCoeff1)
			elif filtType == 2:
				if filtCoeff1 == 0.0:
					log.warning("you must set a window size for the wienerY filter!")
					return
				sample['x'] -= Filters.get_wiener(sample['x'], int(filtCoeff1))
			elif filtType == 3:
				if filtCoeff1 == 0.0:
					log.warning("you must set a window size for the medfiltY filter!")
					return
				sample['x'] = scipy.signal.medfilt(sample['x'], int(filtCoeff1))
			elif filtType == 4:
				ford = int(filtCoeff1)
				ffreq = filtCoeff2
				if ford == 0.0:
					log.warning("you must set a window size for the ffbutterY filter!")
					return
				if (ffreq < 0) or (ffreq > 1):
					log.warning("you must set a Nyquist-normalized frequency (0.0 to 0.99) for the ffbutterY filter!")
					return
				b, a = scipy.signal.butter(ford, ffreq, btype='low', analog=False, output='ba')
				sample['x'] = scipy.signal.filtfilt(b, a, sample['x'], padlen=20)
			return sample
		except:
			log.exception("received an exception: %s" % sys.exc_info()[1])
			return




	### tab control
	def checkCurrentTab(self):
		"""
		Provides a simple routine that checks to see which tab is active.

		An appropriate internal flag is set here. The intention is that
		this is called via a slow timer that minimizes required
		computational load and prevents duplicate code. So far, only the
		scan tab is checked, but it will probably be used for other tabs
		that require graphics-/computationally-expensive tasks.
		"""
		currentTabText = self.TabWidget.tabText(self.TabWidget.currentIndex())
		self.isPressureTab = (currentTabText == "Pressures")
		self.isMFCTab = (currentTabText == "Flow Controllers")
		self.isScanTab = (currentTabText == "Freq. Scan")
		self.isMonTab = (currentTabText == "Monitor")

	def nextTab(self):
		"""
		Switches to the tab on the right.
		"""
		currentTabIndex = self.TabWidget.currentIndex()
		finalIndex = self.TabWidget.count() - 1
		if currentTabIndex == finalIndex:
			self.TabWidget.setCurrentIndex(0)
		else:
			self.TabWidget.setCurrentIndex(currentTabIndex+1)
	def prevTab(self):
		"""
		Switches to the tab on the left.
		"""
		currentTabIndex = self.TabWidget.currentIndex()
		finalIndex = self.TabWidget.count() - 1
		if currentTabIndex == 0:
			self.TabWidget.setCurrentIndex(finalIndex)
		else:
			self.TabWidget.setCurrentIndex(currentTabIndex-1)

	def tabBatchOn(self):
		"""
		Activates the tab for batch scanning.
		"""
		self.tab_Batch.setEnabled(True)
		if not self.led_BatchMode.isEnabled:
			self.led_BatchMode.toggle()
		try:
			self.TabWidget.setCurrentWidget(self.tab_Batch)
		except:
			pass
	def tabBatchOff(self):
		"""
		Disables the tab for batch scanning.
		"""
		self.tab_Batch.setEnabled(False)
		if self.led_BatchMode.isEnabled:
			self.led_BatchMode.toggle()


	### keyboard shortcuts
	def keyboardCtrlA(self):
		"""
		Performs all the desired tasks associated with the Ctrl+L keyboard
		shortcut.
		"""
		currentTabText = self.TabWidget.tabText(self.TabWidget.currentIndex())
		if (currentTabText == "Freq. Scan"):
			self.ScanPlotFigure.getPlotItem().enableAutoRange()
	def keyboardCtrlL(self):
		"""
		Performs all the desired tasks associated with the Ctrl+L keyboard
		shortcut.
		"""
		currentTabText = self.TabWidget.tabText(self.TabWidget.currentIndex())
		if currentTabText == "Files / Instruments":
			self.settingsLoad()
		elif (currentTabText == "Freq. Scan"):
			self.scanLoad()
	def keyboardCtrlO(self):
		"""
		Performs all the desired tasks associated with the Ctrl+O keyboard
		shortcut.
		"""
		currentTabText = self.TabWidget.tabText(self.TabWidget.currentIndex())
		if (currentTabText == "Files / Instruments"):
			self.settingsLoad(prompt=True)
	def keyboardCtrlR(self):
		"""
		Performs all the desired tasks associated with the Ctrl+R keyboard
		shortcut.
		"""
		currentTabText = self.TabWidget.tabText(self.TabWidget.currentIndex())
		if currentTabText == "Synthesizer":
			self.SynthReadValues()
		elif currentTabText == "Lock-In Amp":
			self.LockinReadValues()
	def keyboardCtrlS(self):
		"""
		Performs all the desired tasks associated with the Ctrl+S keyboard
		shortcut.
		"""
		currentTabText = self.TabWidget.tabText(self.TabWidget.currentIndex())
		if (currentTabText == "Files / Instruments"):
			self.settingsSave()
		elif currentTabText == "Pulse Control":
			self.DGSetValues()
		elif currentTabText == "Synthesizer":
			self.SynthSetValues()
		elif currentTabText == "Lock-In Amp":
			self.LockinSetValues()
		elif (currentTabText == "Freq. Scan"):
			self.scanSave()
	def keyboardCtrlShiftS(self):
		"""
		Performs all the desired tasks associated with the Ctrl++Shift+S
		keyboard shortcut.
		"""
		currentTabText = self.TabWidget.tabText(self.TabWidget.currentIndex())
		if (currentTabText == "Files / Instruments"):
			self.settingsSave(prompt=True)
	def keyboardCtrlZ(self):
		"""
		Performs all the desired tasks associated with the Ctrl+S keyboard
		shortcut.
		"""
		currentTabText = self.TabWidget.tabText(self.TabWidget.currentIndex())
		if currentTabText == "Freq. Scan":
			self.scanPlotClearLabels(onlyLastOne=True)



	### errors/warnings
	def showInformation(self, title, msg):
		"""
		Pops up a warning dialog, and raises a SyntaxError.

		:param msg: the descriptive message to print as the main text
		:type msg: str
		"""
		log.info("showInformation: %s - %s" % (title,msg))
		self.msgBox = QtGui.QMessageBox.information(self, title, msg)
	def showInputError(self, msg):
		"""
		Pops up a warning dialog, and raises a SyntaxError.

		:param msg: the descriptive message to print as the main text
		:type msg: str
		"""
		log.error("showInputError: %s" % (msg,))
		QtGui.QMessageBox.warning(self, "Input Error!", msg, QtGui.QMessageBox.Ok)
		raise SyntaxError(msg)
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
		msgBox.setText(cleanText(msg))
		if msgFinal:
			msgBox.setInformativeText(cleanText(msgFinal))
		if msgDetails:
			msgBox.setDetailedText(msgDetails)
		# add buttons
		msgBox.setStandardButtons(QtGui.QMessageBox.Ignore | QtGui.QMessageBox.Abort)
		msgBox.setDefaultButton(QtGui.QMessageBox.Ignore)
		# finally, execute the dialog and abort if needed
		msgResponse = msgBox.exec_()
		log.warning("showWarning: %s (%s? %s)" % (msg,msgFinal,msgResponse))
		if msgResponse == QtGui.QMessageBox.Abort:
			if msgAbort:
				abort = msgAbort
			else:
				abort = msg
			raise UserWarning("Aborted by user: '%s'" % abort)
	@QtCore.pyqtSlot(str, list)
	def showMsgByThread(self, msgType, contents):
		"""
		Provides functionality tied to the signal slot 'self.signalShowMessage',
		so that a thread-independent message can be shown. To-date, its only use
		is to show a pop-up message at the end of a batch job.
		"""
		if msgType == "info":
			self.showInformation(contents[0], contents[1])
		elif msgType == "error":
			self.showInputError(contents[0])
		elif msgType == "warning":
			self.showWarning([contents[i] for i in range(5)])



	### dialogs to choose files/directories
	def browseSpecOut(self, mouseEvent=False):
		"""
		Provides a dialog to choose a directory.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		self.txt_SpecOut.setText(QtGui.QFileDialog.getExistingDirectory())
	def browseSettingsIn(self, mouseEvent=False):
		"""
		Provides a dialog to choose an input filename for the settings file.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		path = QtGui.QFileDialog.getOpenFileName()
		if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
			path = path[0]
		self.txt_SettingsFile.setText(path)
	def browseSettingsOut(self, mouseEvent=False):
		"""
		Provides a dialog to choose an output filename for the settings file.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		self.txt_SettingsFile.setText(QtGui.QFileDialog.getSaveFileName())

	def chooseAdvSettingsFilesInstruments(self, mouseEvent=False):
		"""
		Loads the current 'Advanced Settings' for the Files/Instruments
		tab into a ScrollableSettingsWindow

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		advSettingsWindow = ScrollableSettingsWindow(self, self.updateAdvSettingsFilesInstruments)
		advSettingsWindow.addRow(
			"debugging", "Whether to show various debugging info.",
			self.debugging, "(bool)")
		advSettingsWindow.addRow(
			"defaultSaveFile", "Default configuration file",
			self.defaultSaveFile, "(none)")
		advSettingsWindow.addRow(
			"saveperiodSensorData", "Save Period for the Sensor Data",
			self.saveperiodSensorData, "ms")
		advSettingsWindow.addRow(
			"updateperiodCheckTab", "Update Period for Active Tab",
			self.updateperiodCheckTab, "ms")
		advSettingsWindow.addRow(
			"updateperiodCheckInstruments", "Update Period for Instrument Connection",
			self.updateperiodCheckInstruments, "ms")
		advSettingsWindow.addRow(
			"updateperiodPressureUpdate", "Update Period for Pressure Readings",
			self.updateperiodPressureUpdate, "ms")
		advSettingsWindow.addRow(
			"updateperiodTemperatureUpdate", "Update Period for Temperature Readings",
			self.updateperiodTemperatureUpdate, "ms")
		advSettingsWindow.addRow(
			"updateperiodMFCUpdate", "Update Period for MFC Readings",
			self.updateperiodMFCUpdate, "ms")
		if advSettingsWindow.exec_():
			pass
	def updateAdvSettingsFilesInstruments(self, advsettings):
		"""
		Updates 'Advanced Settings' for the Files/Instruments tab from the
		ScrollableSettingsWindow

		:param advsettings: the dictionary containing all the new parameters from the ScrollableSettingsWindow
		:type advsettings: dict
		"""
		if str(advsettings["debugging"].text()).lower()[0] in ['y', 't']:
			self.debugging = True
		else:
			self.debugging = False
		self.defaultSaveFile = advsettings["defaultSaveFile"].text()
		self.saveperiodSensorData = qlineedit_to_int(advsettings["saveperiodSensorData"])
		self.timerSensorSaveCont.stop()
		self.timerSensorSaveCont = genericThreadContinuous(self.saveSensorData, self.saveperiodSensorData)
		self.timerSensorSaveCont.start()
		self.updateperiodCheckTab = qlineedit_to_int(advsettings["updateperiodCheckTab"])
		self.timerCheckTab.stop()
		self.timerCheckTab = genericThreadContinuous(self.checkCurrentTab, self.updateperiodCheckTab)
		self.timerCheckTab.start()
		self.updateperiodCheckInstruments = qlineedit_to_int(advsettings["updateperiodCheckInstruments"])
		self.timerCheckInstruments.stop()
		self.timerCheckInstruments = genericThreadContinuous(self.checkInstruments, self.updateperiodCheckInstruments)
		self.timerCheckInstruments.start()
		self.updateperiodPressureUpdate = qlineedit_to_int(advsettings["updateperiodPressureUpdate"])
		self.timerPressureUpdateCont.stop()
		self.timerPressureUpdateCont = genericThreadContinuous(self.pressureUpdate, self.updateperiodPressureUpdate)
		self.timerPressureUpdateCont.start()
		self.updateperiodTemperatureUpdate = qlineedit_to_int(advsettings["updateperiodTemperatureUpdate"])
		self.timerTemperatureUpdate.stop()
		self.timerTemperatureUpdate = genericThreadContinuous(self.temperatureUpdate, self.updateperiodTemperatureUpdate)
		self.timerTemperatureUpdate.start()
		self.updateperiodMFCUpdate = qlineedit_to_int(advsettings["updateperiodMFCUpdate"])
		self.timerMFCUpdate.stop()
		self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
		self.timerMFCUpdate.start()




	### settings processing
	def settingsLoad(self, mouseEvent=False, prompt=False, filename=""):
		"""
		Performs the process of loading the settings from a file.

		:param mouseEvent: (optional) the mouse event from a click
		:param prompt: (optional) whether to provide a dialog for file selection
		:param filename: (optional) name of the file to load
		:type mouseEvent: QtGui.QMouseEvent
		:type prompt: bool
		:type filename: str
		"""
		# define the filename to use
		if prompt and filename:
			msg = "You cannot request a file dialog AND specify a filename!"
			self.showInputError(msg)
		elif prompt:
			fileIn = QtGui.QFileDialog.getOpenFileName()
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				fileIn = fileIn[0]
		elif filename:
			fileIn = os.path.expanduser(str(filename))
		else:
			fileIn = os.path.expanduser(str(self.txt_SettingsFile.text()))
			if not fileIn:
				fileIn = self.defaultSaveFile
		# quick sanity check to make sure the file exists..
		if not os.path.isfile(fileIn):
			log.info("You tried to load a non-file!")
			return
		# define parameters to ignore when loaded
		ignoredParams = [
			"blah","msgBox",
			"numSMPs",
			"updateperiodPlotUpdate",
			"saveFilename","txt_PressureOut","txt_TempOut",
			"scanTitle","scanComment",
			"isScanTab","isMonTab","isMFCTab","isPressureTab",
			"isScanning","isPaused"
			"isBatchRunning","isBatchReadyForNext","scanFinished",
			"currentScanIndex",
			"isScanDirectionUp", "check_LockinTolerateHysteresis",
			"timeScanStart","timeScanStop","timeScanSave","timeScanPaused",
			"txt_ScanStatus","txt_ScanTime","lcd_ScanIterations",
			"scanComment","scanTitle",
			"hasConnectedPressure",
			"txt_PGauge1Reading","txt_PGauge2aReading","txt_PGauge2bReading",
			"txt_PGauge3aReading","txt_PGauge3bReading","txt_PGauge4Reading",
			"txt_MFCPressureReadingPtab", "txt_MFCPressureReadingMtab",
			"abortSynthPowerStepping","check_ignoreSpikes",
			"txt_Pulse01start", "txt_Pulse02start", "txt_Pulse03start", "txt_Pulse04start",
			"txt_Pulse01end",   "txt_Pulse02end",   "txt_Pulse03end",   "txt_Pulse04end",
			"slider_alarmActivity"
		]
		self.guiParamsCollected = {}
		with codecs.open(fileIn, 'r', encoding='utf-8') as f:
			for line in f:
				match = re.search(r".*:(.*): '(.*)'.*", line)
				if match:
					k = match.group(1)
					try:
						v = match.group(2).encode(sys.getdefaultencoding())
					except UnicodeEncodeError:
						v = match.group(2)
					self.guiParamsCollected[k] = v
		unknownParams = []
		for k in self.guiParamsCollected.keys():
			knownKeys = list(vars(self).keys()) + ignoredParams
			if k not in knownKeys:
				unknownParams.append(k)
		if len(unknownParams):
			msg = """Found at least one parameter in the file that was
			loaded just now, which could not be matched with any attribute
			of the current GUI. This could happen if there have been
			significant changes to the GUI since this file was saved.
			\nDetails can be found below."""
			details = "filename: %s\n" % fileIn
			details += "\n<parameterName> -> <parameterValue>\n"
			for k in unknownParams:
				details += "%s -> %s\n" % (k, self.guiParamsCollected[k])
			title = "Unknown parameter(s) identified!"
			abort = "Identified unknown parameter(s) during loading"
			self.showWarning(msg, msgDetails=details, msgAbort=abort, title=title)
		self.setCurrentSettings()
	def setCurrentSettings(self):
		"""
		This routine sets all the parameters defined in the internal
		dictionary, which is itself populated by the settings loader. It
		will invoke a warning message if it finds a parameter that was
		loaded but does not match exactly with a current one.

		VERY IMPORTANT:
		Each and every parameter that is loaded by the settings loader
		should be processed here in one way or another. Parameters of
		'normal' datatypes can probably be set directly by converting
		the string to the appropriate datatype, but some exceptions may
		occur, for example:
		- a helper function ``str_to_bool()`` exists for interpreting
		True/False strings;	and
		- timer rates must also involve the stop(),
		blah=genericThreadContinuous(fxn, updatePeriod), and start()
		methods of any timers that are start()-ed in the GUI's
		``__init__`` routine above.
		Furthermore, all the new values of any Qt Input Widgets must be
		loaded very cleverly, and only by manual programming effort that
		depends exactly on the conversion of the. All I can say about this
		is 'good luck, and have some patience'.
		"""
		### define any/all helper functions here
		couldNotBeLoaded = []
		def canBeLoaded(s):
			"""
			A helper function to check that a parameter name exists in the
			current GUI. If it does not, its name gets appended to a list
			that is reported to the user afterwards.

			:param s: the name of the parameter to check
			:type s: str
			:returns: whether the parameter exists in the current GUI
			:rtype: bool
			"""
			if s in self.guiParamsCollected.keys():
				return True
			else:
				couldNotBeLoaded.append(s)
		### now push all the new parameters
		# misc
		if canBeLoaded("debugging"): self.debugging = self.guiParamsCollected["debugging"]
		# files
		if canBeLoaded("defaultSaveFile"): self.defaultSaveFile = self.guiParamsCollected["defaultSaveFile"]
		if canBeLoaded("txt_SpecOut"): self.txt_SpecOut.setText(self.guiParamsCollected["txt_SpecOut"])
		if canBeLoaded("txt_SettingsFile"): self.txt_SettingsFile.setText(self.guiParamsCollected["txt_SettingsFile"])
		if canBeLoaded("check_SavePressures"): self.check_SavePressures.setChecked(str_to_bool(self.guiParamsCollected["check_SavePressures"]))
		if canBeLoaded("check_SaveTemps"): self.check_SaveTemps.setChecked(str_to_bool(self.guiParamsCollected["check_SaveTemps"]))
		# timers
		try:
			if canBeLoaded("saveperiodSensorData"):
				self.saveperiodSensorData = str_to_int(self.guiParamsCollected["saveperiodSensorData"])
				self.timerSensorSaveCont.stop()
				self.timerSensorSaveCont = genericThreadContinuous(self.saveSensorData, self.saveperiodSensorData)
				self.timerSensorSaveCont.start()
		except:
			log.warning("there was a problem updating the timer timerSensorSaveCont")
		try:
			if canBeLoaded("updateperiodCheckTab"):
				self.updateperiodCheckTab = str_to_int(self.guiParamsCollected["updateperiodCheckTab"])
				self.timerCheckTab.stop()
				self.timerCheckTab = genericThreadContinuous(self.checkCurrentTab, self.updateperiodCheckTab)
				self.timerCheckTab.start()
		except:
			log.warning("there was a problem updating the timer timerCheckTab")
		try:
			if canBeLoaded("updateperiodCheckInstruments"):
				self.updateperiodCheckInstruments = str_to_int(self.guiParamsCollected["updateperiodCheckInstruments"])
				self.timerCheckInstruments.stop()
				self.timerCheckInstruments = genericThreadContinuous(self.checkInstruments, self.updateperiodCheckInstruments)
				self.timerCheckInstruments.start()
		except:
			log.warning("there was a problem updating the timer timerCheckInstruments")
		try:
			if canBeLoaded("updateperiodCheckAlarmLimits"):
				self.updateperiodCheckAlarmLimits = str_to_int(self.guiParamsCollected["updateperiodCheckAlarmLimits"])
				self.timerCheckAlarmLimits.stop()
				self.timerCheckAlarmLimits = genericThreadContinuous(self.alarmCheckLimits, self.updateperiodCheckAlarmLimits)
				self.timerCheckAlarmLimits.start()
		except:
			log.warning("there was a problem updating the timer timerCheckAlarmLimits")
		try:
			if canBeLoaded("updateperiodPressureUpdate"):
				self.updateperiodPressureUpdate = str_to_int(self.guiParamsCollected["updateperiodPressureUpdate"])
				self.timerPressureUpdateCont.stop()
				self.timerPressureUpdateCont = genericThreadContinuous(self.pressureUpdate, self.updateperiodPressureUpdate)
				self.timerPressureUpdateCont.start()
		except:
			log.warning("there was a problem updating the timer timerPressureUpdateCont")
		try:
			if canBeLoaded("updateperiodTemperatureUpdate"):
				self.updateperiodTemperatureUpdate = str_to_int(self.guiParamsCollected["updateperiodTemperatureUpdate"])
				self.timerTemperatureUpdate.stop()
				self.timerTemperatureUpdate = genericThreadContinuous(self.temperatureUpdate, self.updateperiodTemperatureUpdate)
				self.timerTemperatureUpdate.start()
		except:
			log.warning("there was a problem updating the timer timerTemperatureUpdate")
		try:
			if canBeLoaded("updateperiodMFCUpdate"):
				self.updateperiodMFCUpdate = str_to_int(self.guiParamsCollected["updateperiodMFCUpdate"])
				self.timerMFCUpdate.stop()
				self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
				self.timerMFCUpdate.start()
		except:
			log.warning("there was a problem updating the timer timerMFCUpdate")
		# intrument connections
		if canBeLoaded("combo_PGauge1Port"): self.combo_PGauge1Port.setCurrentIndex(self.serialPorts.index(self.guiParamsCollected["combo_PGauge1Port"]))
		if canBeLoaded("combo_PGauge2Port"): self.combo_PGauge2Port.setCurrentIndex(self.serialPorts.index(self.guiParamsCollected["combo_PGauge2Port"]))
		if canBeLoaded("serialPortMFC"): self.serialPortMFC = self.guiParamsCollected["serialPortMFC"]
		if canBeLoaded("ethernetIPDG"): self.ethernetIPDG = self.guiParamsCollected["ethernetIPDG"]
		if canBeLoaded("ethernetPortDG"): self.ethernetPortDG = str_to_int(self.guiParamsCollected["ethernetPortDG"])
		if canBeLoaded("ethernetIPLockin"): self.ethernetIPLockin = self.guiParamsCollected["ethernetIPLockin"]
		if canBeLoaded("hasConnectedPressure1") and (self.guiParamsCollected["hasConnectedPressure1"] == "True"):
			try:
				self.connectPressure(readout=1)
			except:
				log.warning("there was an error while trying to connect 'Pressure Gauge 1' from a settings file!")
		if canBeLoaded("hasConnectedPressure2") and (self.guiParamsCollected["hasConnectedPressure2"] == "True"):
			try:
				self.connectPressure(readout=2)
			except:
				log.warning("there was an error while trying to connect 'Pressure Gauge 2' from a settings file!")
		if canBeLoaded("hasConnectedTemperature") and (self.guiParamsCollected["hasConnectedTemperature"] == "True"):
			try:
				self.connectTemperature()
			except:
				log.warning("there was an error while trying to connect 'Temperatures' from a settings file!")
		if canBeLoaded("hasConnectedMFC") and (self.guiParamsCollected["hasConnectedMFC"] == "True"):
			try:
				self.connectMFC()
			except:
				log.warning("there was an error while trying to connect 'MFCs' from a settings file!")
		if canBeLoaded("hasConnectedDG") and (self.guiParamsCollected["hasConnectedDG"] == "True"):
			try:
				self.connectDG()
			except:
				log.warning("there was an error while trying to connect 'Delay Generator' from a settings file!")
		if canBeLoaded("hasConnectedSynth") and (self.guiParamsCollected["hasConnectedSynth"] == "True"):
			try:
				self.connectSynth()
			except:
				log.warning("there was an error while trying to connect 'Synthesizer' from a settings file!")
		if canBeLoaded("hasConnectedLockin") and (self.guiParamsCollected["hasConnectedLockin"] == "True"):
			try:
				self.connectLockin()
			except:
				log.warning("there was an error while trying to connect 'LIA' from a settings file!")
		if canBeLoaded("check_UseMFC"): self.check_UseMFC.setChecked(str_to_bool(self.guiParamsCollected["check_UseMFC"]))
		if canBeLoaded("check_UseDG"): self.check_UseDG.setChecked(str_to_bool(self.guiParamsCollected["check_UseDG"]))
		if canBeLoaded("check_UseSynth"): self.check_UseSynth.setChecked(str_to_bool(self.guiParamsCollected["check_UseSynth"]))
		if canBeLoaded("check_UseLockin"): self.check_UseLockin.setChecked(str_to_bool(self.guiParamsCollected["check_UseLockin"]))
		# pressures
		# temperatures
		# mass flow controllers
		if canBeLoaded("check_MFC1Active"): self.check_MFC1Active.setChecked(str_to_bool(self.guiParamsCollected["check_MFC1Active"]))
		if canBeLoaded("check_MFC2Active"): self.check_MFC2Active.setChecked(str_to_bool(self.guiParamsCollected["check_MFC2Active"]))
		if canBeLoaded("check_MFC3Active"): self.check_MFC3Active.setChecked(str_to_bool(self.guiParamsCollected["check_MFC3Active"]))
		if canBeLoaded("check_MFC4Active"): self.check_MFC4Active.setChecked(str_to_bool(self.guiParamsCollected["check_MFC4Active"]))
		if canBeLoaded("combo_MFC1Gas"): self.combo_MFC1Gas.setCurrentIndex(self.MFCgastypes.index(self.guiParamsCollected["combo_MFC1Gas"]))
		if canBeLoaded("combo_MFC2Gas"): self.combo_MFC2Gas.setCurrentIndex(self.MFCgastypes.index(self.guiParamsCollected["combo_MFC2Gas"]))
		if canBeLoaded("combo_MFC3Gas"): self.combo_MFC3Gas.setCurrentIndex(self.MFCgastypes.index(self.guiParamsCollected["combo_MFC3Gas"]))
		if canBeLoaded("combo_MFC4Gas"): self.combo_MFC4Gas.setCurrentIndex(self.MFCgastypes.index(self.guiParamsCollected["combo_MFC4Gas"]))
		if canBeLoaded("combo_MFC1Range"): self.combo_MFC1Range.setCurrentIndex(self.MFCranges.index(self.guiParamsCollected["combo_MFC1Range"]))
		if canBeLoaded("combo_MFC2Range"): self.combo_MFC2Range.setCurrentIndex(self.MFCranges.index(self.guiParamsCollected["combo_MFC2Range"]))
		if canBeLoaded("combo_MFC3Range"): self.combo_MFC3Range.setCurrentIndex(self.MFCranges.index(self.guiParamsCollected["combo_MFC3Range"]))
		if canBeLoaded("combo_MFC4Range"): self.combo_MFC4Range.setCurrentIndex(self.MFCranges.index(self.guiParamsCollected["combo_MFC4Range"]))
		if canBeLoaded("txt_MFC1FSabs"): self.txt_MFC1FSabs.setText(self.guiParamsCollected["txt_MFC1FSabs"])
		if canBeLoaded("txt_MFC2FSabs"): self.txt_MFC2FSabs.setText(self.guiParamsCollected["txt_MFC2FSabs"])
		if canBeLoaded("txt_MFC3FSabs"): self.txt_MFC3FSabs.setText(self.guiParamsCollected["txt_MFC3FSabs"])
		if canBeLoaded("txt_MFC4FSabs"): self.txt_MFC4FSabs.setText(self.guiParamsCollected["txt_MFC4FSabs"])
		if canBeLoaded("txt_MFCPressureTarget"): self.txt_MFCPressureTarget.setText(self.guiParamsCollected["txt_MFCPressureTarget"])
		if canBeLoaded("combo_MFCPUnit"): self.combo_MFCPUnit.setCurrentIndex(self.MFCpressures.index(self.guiParamsCollected["combo_MFCPUnit"]))
		# pulses
		for i in ["Valve", "LockinSingle", "LockinInt", "LockinBase", "HV", "DG4"]:
			if canBeLoaded("txt_Pulse%s_start" % i) and canBeLoaded("txt_Pulse%s_end" % i):
				start = float(self.guiParamsCollected["txt_Pulse%s_start" % i])
				end = float(self.guiParamsCollected["txt_Pulse%s_end" % i])
				vars(self)["pulsePlotRegion_%s" % i].setRegion([start, end])
		if canBeLoaded("check_LockPulsePlotAxes"): self.check_LockPulsePlotAxes.setChecked(str_to_bool(self.guiParamsCollected["check_LockPulsePlotAxes"]))
		if canBeLoaded("txt_DGTriggerRate"): self.txt_DGTriggerRate.setText(self.guiParamsCollected["txt_DGTriggerRate"])
		if canBeLoaded("check_DGAutoTrig"):
			self.check_DGAutoTrig.setChecked(str_to_bool(self.guiParamsCollected["check_DGAutoTrig"]))
		# synthesizer
		if canBeLoaded("reasonableMaxFreqPoints"): self.reasonableMaxFreqPoints = str_to_int(self.guiParamsCollected["reasonableMaxFreqPoints"])
		if canBeLoaded("reasonableMaxScanTime"): self.reasonableMaxScanTime = str_to_int(self.guiParamsCollected["reasonableMaxScanTime"])
		if canBeLoaded("synthFreqResolution"): self.synthFreqResolution = str_to_int(self.guiParamsCollected["synthFreqResolution"])
		if canBeLoaded("maxRFInputStd"): self.maxRFInputStd = float(self.guiParamsCollected["maxRFInputStd"])
		if canBeLoaded("maxRFInputHi"): self.maxRFInputHi = float(self.guiParamsCollected["maxRFInputHi"])
		#if canBeLoaded("hasPermissionHigherRF"): self.hasPermissionHigherRF = bool(self.guiParamsCollected["hasPermissionHigherRF"])
		if canBeLoaded("RFstepPow"): self.RFstepPow = float(self.guiParamsCollected["RFstepPow"])
		if canBeLoaded("RFstepTime"): self.RFstepTime = float(self.guiParamsCollected["RFstepTime"])
		if canBeLoaded("txt_SynthMultFactor"): self.txt_SynthMultFactor.setText(self.guiParamsCollected["txt_SynthMultFactor"])
		if canBeLoaded("txt_SynthFreqStart"): self.txt_SynthFreqStart.setText(self.guiParamsCollected["txt_SynthFreqStart"])
		if canBeLoaded("txt_SynthFreqEnd"): self.txt_SynthFreqEnd.setText(self.guiParamsCollected["txt_SynthFreqEnd"])
		if canBeLoaded("txt_SynthFreqStep"): self.txt_SynthFreqStep.setText(self.guiParamsCollected["txt_SynthFreqStep"])
		if canBeLoaded("txt_SynthDelay"): self.txt_SynthDelay.setText(self.guiParamsCollected["txt_SynthDelay"])
		AMCBands = ["(manual)"]+sorted(list(self.AMCBandSpecs.keys()),reverse=True)
		if canBeLoaded("txt_SpecOut"): self.combo_AMCband.setCurrentIndex(AMCBands.index(self.guiParamsCollected["combo_AMCband"]))
		AMCModes = ["(manual)", "Standard", "High"]
		if canBeLoaded("combo_AMCmode"): self.combo_AMCmode.setCurrentIndex(AMCModes.index(self.guiParamsCollected["combo_AMCmode"]))
		if canBeLoaded("synthEZFreqCenterHistory"):
			try:
				ezhistory = self.guiParamsCollected["synthEZFreqCenterHistory"].lstrip('[').rstrip(']').split(',')
				self.synthEZFreqCenterHistory = map(float, ezhistory)
				try:
					self.combo_SynthFreqCenterHistory.currentIndexChanged.disconnect()
				except TypeError:
					pass
				self.combo_SynthFreqCenterHistory.clear()
				self.combo_SynthFreqCenterHistory.addItem("Recent Center Frequencies")
				for f in reversed(self.synthEZFreqCenterHistory):
					self.combo_SynthFreqCenterHistory.addItem("%s" % f)
				self.combo_SynthFreqCenterHistory.setCurrentIndex(0)
				self.combo_SynthFreqCenterHistory.currentIndexChanged.connect(self.getSynthEZFreqCenterHistory)
			except:
				pass
		if canBeLoaded("combo_SynthPower"): self.combo_SynthPower.setValue(float(self.guiParamsCollected["combo_SynthPower"]))
		if canBeLoaded("check_SynthRF"): self.check_SynthRF.setChecked(str_to_bool(self.guiParamsCollected["check_SynthRF"]))
		if canBeLoaded("txt_SynthAMFreq"): self.txt_SynthAMFreq.setText(self.guiParamsCollected["txt_SynthAMFreq"])
		ModShapes = [t[0] for t in self.modShapes]
		if canBeLoaded("combo_SynthAMDepth"): self.combo_SynthAMDepth.setValue(int(self.guiParamsCollected["combo_SynthAMDepth"]))
		if canBeLoaded("combo_SynthAMShape"): self.combo_SynthAMShape.setCurrentIndex(ModShapes.index(self.guiParamsCollected["combo_SynthAMShape"]))
		if canBeLoaded("slider_SynthMod"): self.slider_SynthMod.setValue(int(self.guiParamsCollected["slider_SynthMod"]))
		if canBeLoaded("txt_SynthFMFreq"): self.txt_SynthFMFreq.setText(self.guiParamsCollected["txt_SynthFMFreq"])
		if canBeLoaded("txt_SynthFMWidth"): self.txt_SynthFMWidth.setText(self.guiParamsCollected["txt_SynthFMWidth"])
		if canBeLoaded("combo_SynthFMShape"): self.combo_SynthFMShape.setCurrentIndex(ModShapes.index(self.guiParamsCollected["combo_SynthFMShape"]))
		if canBeLoaded("check_useSynthMod"): self.check_useSynthMod.setChecked(str_to_bool(self.guiParamsCollected["check_useSynthMod"]))
		# lockin
		if canBeLoaded("waitForAutoPhase"): self.waitForAutoPhase = float(self.guiParamsCollected["waitForAutoPhase"])
		if canBeLoaded("maxLockinFreq"): self.maxLockinFreq = str_to_int(self.guiParamsCollected["maxLockinFreq"])
		if canBeLoaded("lockinDataRateFull"): self.lockinDataRateFull = float(self.guiParamsCollected["lockinDataRateFull"])
		if canBeLoaded("lockinDataRateThrottled"): self.lockinDataRateThrottled = float(self.guiParamsCollected["lockinDataRateThrottled"])
		if canBeLoaded("check_LockinUseSWTrigInt"): self.check_LockinUseSWTrigInt.setChecked(str_to_bool(self.guiParamsCollected["check_LockinUseSWTrigInt"]))
		if canBeLoaded("lockinIntegrationTrigSource"): self.lockinIntegrationTrigSource = self.guiParamsCollected["lockinIntegrationTrigSource"]
		if canBeLoaded("lockinIntegrationTrigDelay"): self.lockinIntegrationTrigDelay = float(self.guiParamsCollected["lockinIntegrationTrigDelay"])
		if canBeLoaded("lockinIntegrationRecordTime"): self.lockinIntegrationRecordTime = float(self.guiParamsCollected["lockinIntegrationRecordTime"])
		if canBeLoaded("combo_LockinSensitivity"):
			sens = pg.siEval(self.guiParamsCollected["combo_LockinSensitivity"])
			sensIndex = np.abs([i - sens for i in self.lockinSensitivityList]).argmin()
			self.combo_LockinSensitivity.setCurrentIndex(sensIndex)
		if canBeLoaded("combo_LockinTau"):
			tau = pg.siEval(self.guiParamsCollected["combo_LockinTau"])
			tauIndex = np.abs([i - tau for i in self.lockinTimeConstantList]).argmin()
			self.combo_LockinTau.setCurrentIndex(tauIndex)
		if canBeLoaded("check_LockinSineFilter"): self.check_LockinSineFilter.setChecked(str_to_bool(self.guiParamsCollected["check_LockinSineFilter"]))
		if canBeLoaded("combo_LockinHarmonic"): self.combo_LockinHarmonic.setValue(int(self.guiParamsCollected["combo_LockinHarmonic"]))
		if canBeLoaded("txt_LockinPhase"): self.txt_LockinPhase.setText(self.guiParamsCollected["txt_LockinPhase"])
		if canBeLoaded("combo_LockinTriggerSrc"):
			source = self.guiParamsCollected["combo_LockinTriggerSrc"]
			source_index = self.lockinTriggerSources.index(source)
			self.combo_LockinTriggerSrc.setCurrentIndex(source_index)
		if canBeLoaded("combo_LockinTriggerMode"):
			mode = self.guiParamsCollected["combo_LockinTriggerMode"]
			mode_index = self.lockinTriggerModes.index(mode)
			self.combo_LockinTriggerMode.setCurrentIndex(mode_index)
		if canBeLoaded("check_LockinUseUnidirectionScan"): self.check_LockinUseUnidirectionScan.setChecked(str_to_bool(self.guiParamsCollected["check_LockinUseUnidirectionScan"]))
		# scan
		if canBeLoaded("waitBeforeScanRestart"): self.waitBeforeScanRestart = float(self.guiParamsCollected["waitBeforeScanRestart"])
		if canBeLoaded("updateperiodScanUpdateSlow"):
			self.updateperiodScanUpdateSlow = float(self.guiParamsCollected["updateperiodScanUpdateSlow"])
			self.timerScanUpdateInfo.stop()
			self.timerScanUpdateInfo = genericThreadContinuous(self.scanUpdateSlow, self.updateperiodScanUpdateSlow)
			self.timerScanUpdateInfo.start()
		if canBeLoaded("updateperiodPlotUpdateFast"): self.updateperiodPlotUpdateFast = float(self.guiParamsCollected["updateperiodPlotUpdateFast"])
		if canBeLoaded("updateperiodPlotUpdateSlow"): self.updateperiodPlotUpdateSlow = float(self.guiParamsCollected["updateperiodPlotUpdateSlow"])
		if canBeLoaded("spikeFilterThreshold"): self.spikeFilterThreshold = str_to_int(self.guiParamsCollected["spikeFilterThreshold"])
		if canBeLoaded("check_ignoreSpikes"): self.check_ignoreSpikes.setChecked(str_to_bool(self.guiParamsCollected["check_ignoreSpikes"]))
		if canBeLoaded("freqFormattedPrecision"): self.freqFormattedPrecision = self.guiParamsCollected["freqFormattedPrecision"]
		# monitor
		if canBeLoaded("txt_MonTimestep"): self.txt_MonTimestep.setText(self.guiParamsCollected["txt_MonTimestep"])
		if canBeLoaded("txt_MonTimespan"): self.txt_MonTimespan.setText(self.guiParamsCollected["txt_MonTimespan"])
		if canBeLoaded("check_useMonTimespan"): self.check_useMonTimespan.setChecked(str_to_bool(self.guiParamsCollected["check_useMonTimespan"]))
		# alarms
		if canBeLoaded("check_alarmTurnOffAfterTrigger"): self.check_alarmTurnOffAfterTrigger.setChecked(str_to_bool(self.guiParamsCollected["check_alarmTurnOffAfterTrigger"]))
		if canBeLoaded("check_alarmEmail"): self.check_alarmEmail.setChecked(str_to_bool(self.guiParamsCollected["check_alarmEmail"]))
		if canBeLoaded("txt_alarmEmail"): self.txt_MonTimestep.setText(self.guiParamsCollected["txt_alarmEmail"])
		if canBeLoaded("check_alarmPauseScan"): self.check_alarmPauseScan.setChecked(str_to_bool(self.guiParamsCollected["check_alarmPauseScan"]))
		if canBeLoaded("check_alarmCloseMFCs"): self.check_alarmCloseMFCs.setChecked(str_to_bool(self.guiParamsCollected["check_alarmCloseMFCs"]))
		if canBeLoaded("txt_alarmPgauge2amin"): self.txt_alarmPgauge2amin.setText(self.guiParamsCollected["txt_alarmPgauge2amin"])
		if canBeLoaded("txt_alarmPgauge2amax"): self.txt_alarmPgauge2amax.setText(self.guiParamsCollected["txt_alarmPgauge2amax"])
		if canBeLoaded("txt_alarmPgauge2bmin"): self.txt_alarmPgauge2bmin.setText(self.guiParamsCollected["txt_alarmPgauge2bmin"])
		if canBeLoaded("txt_alarmPgauge2bmax"): self.txt_alarmPgauge2bmax.setText(self.guiParamsCollected["txt_alarmPgauge2bmax"])
		if canBeLoaded("txt_alarmMFC1min"): self.txt_alarmMFC1min.setText(self.guiParamsCollected["txt_alarmMFC1min"])
		if canBeLoaded("txt_alarmMFC1max"): self.txt_alarmMFC1max.setText(self.guiParamsCollected["txt_alarmMFC1max"])
		if canBeLoaded("txt_alarmMFC2min"): self.txt_alarmMFC2min.setText(self.guiParamsCollected["txt_alarmMFC2min"])
		if canBeLoaded("txt_alarmMFC2max"): self.txt_alarmMFC2max.setText(self.guiParamsCollected["txt_alarmMFC2max"])
		if canBeLoaded("txt_alarmMFC3min"): self.txt_alarmMFC3min.setText(self.guiParamsCollected["txt_alarmMFC3min"])
		if canBeLoaded("txt_alarmMFC3max"): self.txt_alarmMFC3max.setText(self.guiParamsCollected["txt_alarmMFC3max"])
		if canBeLoaded("txt_alarmMFC4min"): self.txt_alarmMFC4min.setText(self.guiParamsCollected["txt_alarmMFC4min"])
		if canBeLoaded("txt_alarmMFC4max"): self.txt_alarmMFC4max.setText(self.guiParamsCollected["txt_alarmMFC4max"])
		if canBeLoaded("txt_alarmMFCpressuremin"): self.txt_alarmMFCpressuremin.setText(self.guiParamsCollected["txt_alarmMFCpressuremin"])
		if canBeLoaded("txt_alarmMFCpressuremax"): self.txt_alarmMFCpressuremax.setText(self.guiParamsCollected["txt_alarmMFCpressuremax"])
		# finally, check what was/wasn't loaded
		if len(couldNotBeLoaded) > 0:
			msg = """You appeared to try to set a parameter that was not
			present in the file that was loaded."""
			details = ""
			for paramName in couldNotBeLoaded:
				details += "%s\n" % paramName
			abort = "Tried to set a nonexistent parameter"
			self.showWarning(msg, msgDetails=details, msgAbort=abort)

	def settingsSave(self, mouseEvent=False, prompt=False, filename=""):
		"""
		Performs the process of saving the current settings to a file.

		:param mouseEvent: (optional) the mouse event from a click
		:param prompt: (optional) whether to provide a dialog for file selection
		:param filename: (optional) name of the file to save
		:type mouseEvent: QtGui.QMouseEvent
		:type prompt: bool
		:type filename: str
		"""
		if prompt and filename:
			msg = "You cannot request a file dialog AND specify a filename!"
			self.showInputError(msg)
		elif prompt:
			fileOut = str(QtGui.QFileDialog.getSaveFileName())
		elif filename:
			fileOut = os.path.expanduser(str(filename))
		else:
			fileOut = os.path.expanduser(str(self.txt_SettingsFile.text()))
		if not fileOut:
			log.info("You tried to save to a non-file!")
			return
		if self.debugging:
			log.info("saving settings to %s" % fileOut)
		fileHandle = codecs.open(fileOut, 'w', encoding='utf-8')
		for entry in self.getCurrentSettings():
			fileHandle.write('%s\n' % entry)
		fileHandle.close()
	def paramStringOut(self, param, limit=None, reverse=False):
		"""
		This routine takes a parameter name as input, and returns the active
		value of it in a format useful for the saving of the settings. The
		parameter name can be that of an internal string or number, or even
		that of a Qt input widget. It will raise a warning if it receives
		a parameter that was not automatically identified previously.

		VERY IMPORTANT:
		Please do note that this routine first collects the names of ALL
		attributes of 'normal' datatypes (str, unicode, int, float, bool),
		as well as those of ALL the standard Qt Input Widgets. This
		collection is then used to check against all the parameters from
		the settings collector. If one adds a new datatype by subclassing
		an existing one, it should also be appended to the tuples at the
		top of this routine; otherwise, there is a high probability for
		an important parameter to be missed in the settings collector
		``self.getCurrentSettings()`` and/or the loader
		``self.self.getCurrentSettings()``.

		:param param: name of an internal attribute
		:type param: str

		:returns: a formatted string of the current flag/parameter
		:rtype: str
		"""
		# define interesting attribute types
		normalTypes = (str, unicode, int, float, bool)
		guiTypes = (QtGui.QComboBox, QtGui.QFontComboBox) # all text-based comboboxes
		guiTypes += (QtGui.QSpinBox, QtGui.QDoubleSpinBox) # all number-based comboboxes
		guiTypes += (QtGui.QTimeEdit, QtGui.QDateEdit, QtGui.QDateTimeEdit) # all time-based comboboxes
		guiTypes += (QtGui.QLineEdit, QtGui.QTextEdit, QtGui.QPlainTextEdit, QtGui.QLCDNumber, Widgets.ScrollableText) # general text
		guiTypes += (QtGui.QCheckBox, QtGui.QDial) # checkbox/dials/sliders
		guiTypes += (QtGui.QSlider, DoubleSlider) # sliders
		# collect all the current attribute names if not already
		if not len(self.guiParamsAll):
			ignoredParams = []
			guiAttributes = vars(self)
			for k,v in guiAttributes.items():
				if isinstance(v, normalTypes+guiTypes):
					self.guiParamsAll.append(k)
		# update the list of collected parameters with this new one
		self.guiParamsCollected.append(param)
		# convert the parameter to a nice string format
		settingsFormat = ":%s: '%s'"
		v = vars(self)[param]
		if isinstance(v, list) and (limit is not None) and (len(v) > limit):
			if reverse:
				v = list(v[-limit:])
			else:
				v = list(v[:limit])
		if isinstance(v, normalTypes):
			return settingsFormat % (param, v)
		elif isinstance(v, guiTypes):
			if isinstance(v, QtGui.QLineEdit):
				return settingsFormat % (param, v.text())
			elif isinstance(v, QtGui.QCheckBox):
				return settingsFormat % (param, str(v.isChecked()))
			elif isinstance(v, QtGui.QComboBox):
				return settingsFormat % (param, v.currentText())
			elif isinstance(v, (QtGui.QSpinBox, QtGui.QDoubleSpinBox, QtGui.QLCDNumber)):
				return settingsFormat % (param, v.value())
			elif isinstance(v, (QtGui.QSlider, DoubleSlider)):
				return settingsFormat % (param, v.value())
			else:
				msg = "You missed a GUI element type: %s" % type(v)
				self.showWarning(msg)
		else:
			return settingsFormat % (param, v)
	def getCurrentSettings(self):
		"""
		This routine collects all the internally-defined parameters and
		statuses of the GUI session, and returns this as a list of
		strings, where each entry looks like:
		``:thisIsTheInstanceVariableName: 'thisIsItsValue'``

		VERY IMPORTANT:
		Note that each and every 'instance variable' of the GUI must be
		categorized so be either: a) added to one of the groups of parameters
		to be saved, or b) added to the list of names to be ignored.
		Case A must be processed in one of the groups of parameters below via
		``settingsInfo.append(self.paramStringOut("nameOfNewParameter"))``.
		Case B requires the name of the parameter to be explicitly added
		to the list ``ignoredParams``.

		:returns: a list of all the current internal flags/parameters
		:rtype: list(str)
		"""
		### force the refresh of the paramters
		self.guiParamsAll = []
		self.guiParamsCollected = []
		ignoredParams = [ # define names of parameters to ignore when saving
			"blah","msgBox",
			"numSMPs",
			"sensorSaveFileFH",
			"updateperiodPlotUpdate",
			"txt_MFC1status","txt_MFC2status","txt_MFC3status","txt_MFC4status",
			"txt_MFC1CurrentFlow","txt_MFC2CurrentFlow","txt_MFC3CurrentFlow","txt_MFC4CurrentFlow",
			"slider_MFC1Flow","slider_MFC2Flow","slider_MFC3Flow","slider_MFC4Flow",
			"slider_LockinPhase",
			"freqDelay",
			"check_SynthSkipCenterFreq", "txt_SynthSkipCenterFreq",
			"isScanTab","isMonTab","isMFCTab","isPressureTab",
			"isScanning","isPaused",
			"isBatchRunning","isBatchReadyForNext","scanFinished",
			"currentScanIndex",
			"isScanDirectionUp", "check_LockinTolerateHysteresis",
			"timeScanStart","timeScanStop","timeScanSave","timeScanPaused",
			"txt_ScanStatus","txt_ScanTime",
			"lcd_ScanFreqPnts","lcd_ScanIterations",
			"txt_ScanDelta","txt_ScanCenter","txt_ScanMin","txt_ScanMax","txt_ScanAvg","txt_ScanDev",
			"scanTitle","scanComment",
			"txt_MonFreq",
			"monTimestep","monTimespan",
			"txt_SynthEZFreqCenter","txt_SynthEZFreqShift","txt_SynthEZFreqSpan","combo_SynthFreqCenterHistory",
			"abortSynthPowerStepping",
			"slider_alarmActivity"
		]
		### initialize list of strings and do the collection
		settingsInfo = []
		# general program information
		settingsInfo.append(self.paramStringOut("programName"))
		settingsInfo.append(self.paramStringOut("programGitHash"))
		settingsInfo.append(self.paramStringOut("debugging"))
		# files/instruments
		settingsInfo.append("### files/instruments")
		settingsInfo.append(self.paramStringOut("defaultSaveFile"))
		settingsInfo.append(self.paramStringOut("saveperiodSensorData"))
		settingsInfo.append(self.paramStringOut("updateperiodCheckTab"))
		settingsInfo.append(self.paramStringOut("updateperiodCheckInstruments"))
		settingsInfo.append(self.paramStringOut("updateperiodCheckAlarmLimits"))
		settingsInfo.append(self.paramStringOut("updateperiodPressureUpdate"))
		settingsInfo.append(self.paramStringOut("updateperiodTemperatureUpdate"))
		settingsInfo.append(self.paramStringOut("updateperiodMFCUpdate"))
		settingsInfo.append(self.paramStringOut("txt_SpecOut"))
		settingsInfo.append(self.paramStringOut("txt_SettingsFile"))
		settingsInfo.append(self.paramStringOut("sensorSaveFile"))
		settingsInfo.append(self.paramStringOut("check_SavePressures"))
		settingsInfo.append(self.paramStringOut("check_SaveTemps"))
		settingsInfo.append(self.paramStringOut("check_SaveMFCs"))
		settingsInfo.append(self.paramStringOut("check_UseMFC"))
		settingsInfo.append(self.paramStringOut("check_UseDG"))
		settingsInfo.append(self.paramStringOut("check_UseSynth"))
		settingsInfo.append(self.paramStringOut("check_UseLockin"))
		settingsInfo.append(self.paramStringOut("hasConnectedPressure1"))
		settingsInfo.append(self.paramStringOut("hasConnectedPressure2"))
		settingsInfo.append(self.paramStringOut("hasConnectedTemperature"))
		settingsInfo.append(self.paramStringOut("hasConnectedMFC"))
		settingsInfo.append(self.paramStringOut("hasConnectedDG"))
		settingsInfo.append(self.paramStringOut("hasConnectedSynth"))
		settingsInfo.append(self.paramStringOut("hasConnectedLockin"))
		# pressures
		settingsInfo.append("### pressures")
		settingsInfo.append(self.paramStringOut("combo_PGauge1Port"))
		settingsInfo.append(self.paramStringOut("combo_PGauge2Port"))
		settingsInfo.append(self.paramStringOut("txt_PGauge1Reading"))
		settingsInfo.append(self.paramStringOut("txt_PGauge2aReading"))
		settingsInfo.append(self.paramStringOut("txt_PGauge2bReading"))
		# temperatures
		settingsInfo.append("### temperatures")
		settingsInfo.append(self.paramStringOut("lcd_TempLeft"))
		settingsInfo.append(self.paramStringOut("lcd_TempMidLeft"))
		settingsInfo.append(self.paramStringOut("lcd_TempMiddle"))
		settingsInfo.append(self.paramStringOut("lcd_TempMidRight"))
		settingsInfo.append(self.paramStringOut("lcd_TempRight"))
		# mass flow controllers
		settingsInfo.append("### mass flow controllers")
		settingsInfo.append(self.paramStringOut("serialPortMFC"))
		settingsInfo.append(self.paramStringOut("check_MFC1Active"))
		settingsInfo.append(self.paramStringOut("combo_MFC1Gas"))
		settingsInfo.append(self.paramStringOut("combo_MFC1Range"))
		settingsInfo.append(self.paramStringOut("txt_MFC1FSabs"))
		settingsInfo.append(self.paramStringOut("check_MFC2Active"))
		settingsInfo.append(self.paramStringOut("combo_MFC2Gas"))
		settingsInfo.append(self.paramStringOut("combo_MFC2Range"))
		settingsInfo.append(self.paramStringOut("txt_MFC2FSabs"))
		settingsInfo.append(self.paramStringOut("check_MFC3Active"))
		settingsInfo.append(self.paramStringOut("combo_MFC3Gas"))
		settingsInfo.append(self.paramStringOut("combo_MFC3Range"))
		settingsInfo.append(self.paramStringOut("txt_MFC3FSabs"))
		settingsInfo.append(self.paramStringOut("check_MFC4Active"))
		settingsInfo.append(self.paramStringOut("combo_MFC4Gas"))
		settingsInfo.append(self.paramStringOut("combo_MFC4Range"))
		settingsInfo.append(self.paramStringOut("txt_MFC4FSabs"))
		settingsInfo.append(self.paramStringOut("txt_MFCPressureReadingMtab"))
		settingsInfo.append(self.paramStringOut("txt_MFCPressureTarget"))
		settingsInfo.append(self.paramStringOut("combo_MFCPUnit"))
		# pulses
		settingsInfo.append("### pulses")
		settingsInfo.append(self.paramStringOut("txt_PulseValve_start"))
		settingsInfo.append(self.paramStringOut("txt_PulseValve_end"))
		settingsInfo.append(self.paramStringOut("txt_PulseLockinSingle_start"))
		settingsInfo.append(self.paramStringOut("txt_PulseLockinSingle_end"))
		settingsInfo.append(self.paramStringOut("txt_PulseLockinInt_start"))
		settingsInfo.append(self.paramStringOut("txt_PulseLockinInt_end"))
		settingsInfo.append(self.paramStringOut("txt_PulseLockinBase_start"))
		settingsInfo.append(self.paramStringOut("txt_PulseLockinBase_end"))
		settingsInfo.append(self.paramStringOut("txt_PulseHV_start"))
		settingsInfo.append(self.paramStringOut("txt_PulseHV_end"))
		settingsInfo.append(self.paramStringOut("txt_PulseDG4_start"))
		settingsInfo.append(self.paramStringOut("txt_PulseDG4_end"))
		settingsInfo.append(self.paramStringOut("check_LockPulsePlotAxes"))
		settingsInfo.append(self.paramStringOut("ethernetIPDG"))
		settingsInfo.append(self.paramStringOut("ethernetPortDG"))
		settingsInfo.append(self.paramStringOut("txt_DGTriggerRate"))
		settingsInfo.append(self.paramStringOut("check_DGAutoTrig"))
		# synthesizer
		settingsInfo.append("### synthesizer")
		settingsInfo.append(self.paramStringOut("reasonableMaxFreqPoints"))
		settingsInfo.append(self.paramStringOut("reasonableMaxScanTime"))
		settingsInfo.append(self.paramStringOut("synthFreqResolution"))
		settingsInfo.append(self.paramStringOut("maxRFInputStd"))
		settingsInfo.append(self.paramStringOut("maxRFInputHi"))
		settingsInfo.append(self.paramStringOut("hasPermissionHigherRF"))
		settingsInfo.append(self.paramStringOut("RFstepPow"))
		settingsInfo.append(self.paramStringOut("RFstepTime"))
		settingsInfo.append(self.paramStringOut("txt_SynthMultFactor"))
		settingsInfo.append(self.paramStringOut("txt_SynthFreqStart"))
		settingsInfo.append(self.paramStringOut("txt_SynthFreqEnd"))
		settingsInfo.append(self.paramStringOut("txt_SynthFreqStep"))
		settingsInfo.append(self.paramStringOut("txt_SynthDelay"))
		settingsInfo.append(self.paramStringOut("combo_AMCband"))
		settingsInfo.append(self.paramStringOut("combo_AMCmode"))
		settingsInfo.append(self.paramStringOut("synthEZFreqCenterHistory", limit=10, reverse=True))
		settingsInfo.append(self.paramStringOut("combo_SynthPower"))
		settingsInfo.append(self.paramStringOut("check_SynthRF"))
		settingsInfo.append(self.paramStringOut("txt_SynthAMFreq"))
		settingsInfo.append(self.paramStringOut("combo_SynthAMDepth"))
		settingsInfo.append(self.paramStringOut("combo_SynthAMShape"))
		settingsInfo.append(self.paramStringOut("slider_SynthMod"))
		settingsInfo.append(self.paramStringOut("txt_SynthFMFreq"))
		settingsInfo.append(self.paramStringOut("txt_SynthFMWidth"))
		settingsInfo.append(self.paramStringOut("combo_SynthFMShape"))
		settingsInfo.append(self.paramStringOut("check_useSynthMod"))
		# lockin
		settingsInfo.append("### lock-in amplifier")
		settingsInfo.append(self.paramStringOut("ethernetIPLockin"))
		settingsInfo.append(self.paramStringOut("waitForAutoPhase"))
		settingsInfo.append(self.paramStringOut("maxLockinFreq"))
		settingsInfo.append(self.paramStringOut("lockinDataRateFull"))
		settingsInfo.append(self.paramStringOut("lockinDataRateThrottled"))
		settingsInfo.append(self.paramStringOut("check_LockinUseSWTrigInt"))
		settingsInfo.append(self.paramStringOut("lockinIntegrationTrigSource"))
		settingsInfo.append(self.paramStringOut("lockinIntegrationTrigDelay"))
		settingsInfo.append(self.paramStringOut("lockinIntegrationRecordTime"))
		settingsInfo.append(self.paramStringOut("combo_LockinSensitivity"))
		settingsInfo.append(self.paramStringOut("combo_LockinTau"))
		settingsInfo.append(self.paramStringOut("check_LockinSineFilter"))
		settingsInfo.append(self.paramStringOut("combo_LockinHarmonic"))
		settingsInfo.append(self.paramStringOut("txt_LockinPhase"))
		settingsInfo.append(self.paramStringOut("combo_LockinTriggerSrc"))
		settingsInfo.append(self.paramStringOut("combo_LockinTriggerMode"))
		settingsInfo.append(self.paramStringOut("check_LockinUseUnidirectionScan"))
		# scan
		settingsInfo.append("### scan")
		settingsInfo.append(self.paramStringOut("waitBeforeScanRestart"))
		settingsInfo.append(self.paramStringOut("updateperiodScanUpdateSlow"))
		settingsInfo.append(self.paramStringOut("updateperiodPlotUpdateFast"))
		settingsInfo.append(self.paramStringOut("updateperiodPlotUpdateSlow"))
		settingsInfo.append(self.paramStringOut("check_ignoreSpikes"))
		settingsInfo.append(self.paramStringOut("spikeFilterThreshold"))
		settingsInfo.append(self.paramStringOut("freqFormattedPrecision"))
		# monitor
		settingsInfo.append("### monitor")
		settingsInfo.append(self.paramStringOut("txt_MonTimestep"))
		settingsInfo.append(self.paramStringOut("txt_MonTimespan"))
		settingsInfo.append(self.paramStringOut("check_useMonTimespan"))
		# alarms
		settingsInfo.append("### alarms")
		settingsInfo.append(self.paramStringOut("check_alarmTurnOffAfterTrigger"))
		settingsInfo.append(self.paramStringOut("check_alarmEmail"))
		settingsInfo.append(self.paramStringOut("txt_alarmEmail"))
		settingsInfo.append(self.paramStringOut("check_alarmPauseScan"))
		settingsInfo.append(self.paramStringOut("check_alarmCloseMFCs"))
		settingsInfo.append(self.paramStringOut("txt_alarmPgauge2amin"))
		settingsInfo.append(self.paramStringOut("txt_alarmPgauge2amax"))
		settingsInfo.append(self.paramStringOut("txt_alarmPgauge2bmin"))
		settingsInfo.append(self.paramStringOut("txt_alarmPgauge2bmax"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFC1min"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFC1max"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFC2min"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFC2max"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFC3min"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFC3max"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFC4min"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFC4max"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFCpressuremin"))
		settingsInfo.append(self.paramStringOut("txt_alarmMFCpressuremax"))

		# check for mutually-exclusive parameter names, in case this
		# routine has not been updated since significant changes to the GUI
		differenceList = list(set(self.guiParamsAll)-set(self.guiParamsCollected))
		differenceList = list(set(differenceList)-set(ignoredParams))
		if len(differenceList):
			msg = """
			It looks like you missed an/some internal attribute(s)! Somebody
			has probably made significant changes to the GUI without having
			updated the settings collector. Both routines titled
			'getCurrentSettings' and 'setCurrentSettings' must be updated.
			"""
			msgFinal = "A list of the name(s) of the missing attributes can"
			msgFinal += " be found in the details below."
			details = ""
			for name in sorted(differenceList):
				details += "%s\n" % name
			title = "Missing settings collected!"
			abort = "Found some missing settings during collection"
			self.showWarning(msg, msgFinal=msgFinal, msgDetails=details, msgAbort=abort, title=title)

		return settingsInfo



	#### instrument connections
	def showConnectionWarning(self, msg, msgFinal="", msgDetails=""):
		"""
		Invokes a warning box about an instrument connection.

		:param msg: the message explaining which instrument is troubled
		:param msgFinal: (optional) the message that would go below the main message
		:param msgDetails: (optional) the message found after clicking "Show Details"
		:type msg: str
		:type msgFinal: str
		:type msgDetails: str
		"""
		self.showWarning(
			msg=msg, title="Connection Warning!",
			msgFinal=msgFinal, msgDetails=msgDetails)
	def checkInstruments(self):
		"""
		Checks the status of the instrument checkboxes, and their
		associated instrument connections.
		"""
		# pressure
		if not self.socketPressure1:
			self.hasConnectedPressure1 = False
		if not self.socketPressure2:
			self.hasConnectedPressure2 = False
		# temperature
		if not self.socketTemperature:
			self.hasConnectedTemperature = False
		# MFCs
		if not self.socketMFC:
			self.hasConnectedMFC = False
		if self.check_UseMFC.isChecked() and (not self.hasConnectedMFC):
			self.signalDisableInstrument.emit("MFC")
		# DGs
		if not self.socketDG:
			self.hasConnectedDG = False
		if self.check_UseDG.isChecked() and (not self.hasConnectedDG):
			self.signalDisableInstrument.emit("DG")
		# synthesizer
		if not self.socketSynth:
			self.hasConnectedSynth = False
		if self.check_UseSynth.isChecked() and (not self.hasConnectedSynth):
			self.signalDisableInstrument.emit("Synth")
		# lock-in amplifier
		if not self.socketLockin:
			self.hasConnectedLockin = False
		if self.check_UseLockin.isChecked() and (not self.hasConnectedLockin):
			self.signalDisableInstrument.emit("LIA")
	@QtCore.pyqtSlot(str)
	def disableInstrument(self, instrument=""):
		"""
		Provides functionality to the signal emitted from self.checkInstruments()
		in case an instrument is no longer connected and its check box in the
		GUI should be modified.
		
		This is intended to be thread-safe, because the GUI thread is constantly
		running and therefore most likely to cause instability when modified
		by a daughter thread. In this case, the daughter thread is of local class
		genericThreadContinuous, initiated during __init__().
		"""
		if instrument=="":
			return
		elif instrument=="MFC":
			self.check_UseMFC.setChecked(False)
		elif instrument=="DG":
			self.check_UseDG.setChecked(False)
		elif instrument=="Synth":
			self.check_UseSynth.setChecked(False)
		elif instrument=="LIA":
			self.check_UseLockin.setChecked(False)

	def connectPressure(self, mouseEvent=False, readout=0):
		"""
		Would set the connection for the pressure.

		:param mouseEvent: (optional) the mouse event from a click
		:param readout: which serial slot to use for the connection
		:type mouseEvent: QtGui.QMouseEvent
		:type readout: int
		"""
		if not readout in [1,2]:
			return
		self.timerPressureUpdateCont.stop()
		time.sleep(0.5)
		# define elements
		hasconnected = {
			1: self.hasConnectedPressure1,
			2: self.hasConnectedPressure2}
		pb = getattr(self, "pb_PGauge%sConnection" % readout)
		# just reload the module and reconnect if already connected
		if hasconnected[readout]:
			self.disconnectPressure(readout=readout)
			self.connectPressure(readout=readout)
			return
		# try the connection
		pb.setValue(50)
		try:
			from Instruments import pressure_gauges
			import serial
			port = str(getattr(self, "combo_PGauge%sPort" % readout).currentText())
			if readout==1:
				self.socketPressure1 = pressure_gauges.PfeifferDualGauge(
					com='COM',
					port=port,
					baudrate=9600,
					parity=serial.PARITY_NONE,
					bytesize=serial.EIGHTBITS,
					stopbits=serial.STOPBITS_ONE,
					timeout=0.1,
					xonxoff=True,
					rtscts=False)
			else:
				if not "." in port:
					msg = "this GUI for the jet experiment only supports the ethernet-"
					msg += "based pressure gauges at the moment! buy Jake a beer, if "
					msg += "you want to change this..."
					log.warning(msg)
					self.socketPressure2 = None
					b.setValue(0)
					self.showInputError(msg)
				elif port == "172.16.27.12":
					self.socketPressure2 = pressure_gauges.PfeifferDualGauge(
						com='TCPIP',
						host=port,
						port=8000,
						timeout=1.0)
				elif port == "172.16.27.72":
					self.socketPressure2 = pressure_gauges.PfeifferDualGauge(
						com='TCPIP',
						host=port,
						port=4001,
						__TERM='\r')
					#self.socketPressure2.socket._sock.set_termination_char('\r')
		except ImportError:
			pb.setValue(0)
			raise ImportError("Could not import the pyLapSpec library for the pressure gauges!")
		except RuntimeError as e:
			if readout==1:
				self.socketPressure1 = None
			else:
				self.socketPressure2 = None
			pb.setValue(0)
			self.showConnectionWarning("Could not connect to the pressure readout! Try to disconnect/reconnect at least once.")
		else:
			if readout==1:
				self.hasConnectedPressure1 = True
				socket = self.socketPressure1
				log.info("Connected to pressure gauge %s: %s" % (readout, socket.identifier))
			else:
				self.hasConnectedPressure2 = True
				socket = self.socketPressure2
				log.info("Connected to pressure gauge %s: %s" % (readout, socket.identifier))
			pb.setValue(100)
		self.timerPressureUpdateCont = genericThreadContinuous(self.pressureUpdate, self.updateperiodPressureUpdate)
		self.timerPressureUpdateCont.start()
	def disconnectPressure(self, mouseEvent=False, readout=0):
		"""
		Disconnects the socket for the pressure.

		:param mouseEvent: (optional) the mouse event from a click
		:param readout: which serial slot to use for the connection
		:type mouseEvent: QtGui.QMouseEvent
		:type readout: int
		"""
		if not readout in [1,2]:
			return
		if readout==1:
			if not self.hasConnectedPressure1:
				return
			self.socketPressure1 = None
			self.hasConnectedPressure1 = False
		else:
			if not self.hasConnectedPressure2:
				return
			if self.socketPressure2.socket.port == 8000:
				self.socketPressure2.close()
			self.socketPressure2 = None
			self.hasConnectedPressure2 = False
		pb = getattr(self, "pb_PGauge%sConnection" % readout)
		pb.setValue(0)

	def connectTemperature(self, mouseEvent=False):
		"""
		Would set the connection for the temperature.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if self.hasConnectedTemperature:
			return
		self.pb_TemperatureConnection.setValue(50)
		raise NotImplementedError()
		self.hasConnectedTemperature = True
		self.pb_TemperatureConnection.setValue(100)
	def disconnectTemperature(self, mouseEvent=False):
		"""
		Disconnects the socket for the temperature.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if not self.hasConnectedTemperature:
			return
		self.hasConnectedTemperature = False
		self.socketTemperature = None
		self.pb_TemperatureConnection.setValue(0)

	def connectMFC(self, mouseEvent=False):
		"""
		Sets the connection for the mass flow controllers.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if self.hasConnectedMFC:
			self.disconnectMFC()
			reload(sys.modules['Instruments'])
			self.connectMFC()
			return
		# possibly run commands via 'stty' and 'setserial'
		self.pb_MFCConnection.setValue(50)
		if self.serialPortMFC == "172.16.27.72":
			try:
				self.socketMFC = Instruments.massflowcontroller.MKS_946(
					com='TCPIP',
					host=self.serialPortMFC,
					port=4002,
					address=253,
					terminator='\r',
					eol=";FF",
					enforceTermination=False)
				try:
					self.timerMFCUpdate.stop()
					time.sleep(0.2)
					self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
					self.timerMFCUpdate.start()
				except:
					pass
			except ImportError:
				self.pb_MFCConnection.setValue(0)
				raise ImportError("Could not import the massflowcontroller library!")
			except RuntimeError as e:
				self.socketMFC = None
				self.pb_MFCConnection.setValue(0)
				self.showConnectionWarning("Could not connect to the mass flow controller! Try to disconnect/reconnect at least once.")
			else:
				self.hasConnectedMFC = True
				log.info("Connected to mass flow controller %s" % self.socketMFC.identifier)
				self.pb_MFCConnection.setValue(100)
				self.initMFC()
		else:
			raise NotImplementedError("the CASAC-style direct serial connection is not supported for the jet yet!")
	def disconnectMFC(self, mouseEvent=False):
		"""
		Disconnects the socket for the mass flow controllers.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if not self.hasConnectedMFC:
			return
		self.hasConnectedMFC = False
		self.socketMFC = None
		self.pb_MFCConnection.setValue(0)

	def connectDG(self, mouseEvent=False):
		"""
		Sets the connection for the delay generator.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if self.hasConnectedDG:
			self.disconnectDG()
			reload(sys.modules['delay_generator'])
			self.connectDG()
			return
		# possibly run commands via 'stty' and 'setserial'
		self.pb_DGConnection.setValue(50)
		try:
			from Instruments import delay_generator
			self.socketDG = delay_generator.SRS_Delay_Generator(
				host=self.ethernetIPDG, port=self.ethernetPortDG)
		except ImportError:
			self.pb_DGConnection.setValue(0)
			raise ImportError("Could not import the delay_generator library!")
		except RuntimeError as e:
			self.socketDG = None
			self.pb_DGConnection.setValue(0)
			self.showConnectionWarning("Could not connect to the delay generator! Try to disconnect/reconnect at least once.")
		else:
			self.hasConnectedDG = True
			log.info("Connected to delay generator %s" % self.socketDG.identifier)
			self.pb_DGConnection.setValue(100)
			self.initDG()
	def disconnectDG(self, mouseEvent=False):
		"""
		Disconnects the socket for the delay generator.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if not self.hasConnectedDG:
			return
		self.hasConnectedDG = False
		self.socketDG = None
		self.pb_DGConnection.setValue(0)

	def connectSynth(self, mouseEvent=False):
		"""
		Sets the connection to the synthesizer.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if self.hasConnectedSynth:
			self.disconnectSynth()
			self.connectSynth()
			return
		self.pb_SynthConnection.setValue(50)
		try:
			from Instruments import synthesizer
			self.socketSynth = synthesizer.PSG_signal_generator( # for ethernet via the "cas-jet" subnet
				host="172.16.27.31", port=5025, com="TCPIP")
		except ImportError:
			self.pb_SynthConnection.setValue(0)
			raise ImportError("Could not import the pyLabSpec.Instruments.synthesizer module!")
		except TypeError:
			self.pb_SynthConnection.setValue(0)
			raise
		except RuntimeError:
			self.pb_SynthConnection.setValue(0)
			raise
		else:
			self.hasConnectedSynth = True
			log.info("Connected to synthesizer %s" % self.socketSynth.identifier)
			self.pb_SynthConnection.setValue(100)
			self.initSynth()
	def disconnectSynth(self, mouseEvent=False):
		"""
		Removes the connection to the synthesizer.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if not self.hasConnectedSynth:
			return
		self.hasConnectedSynth = False
		self.socketSynth = None
		self.pb_SynthConnection.setValue(0)

	def connectLockin(self, mouseEvent=False):
		"""
		Sets the connection to the lock-in amplifier.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if self.hasConnectedLockin:
			self.disconnectLockin()
			reload(sys.modules['lockin'])
			self.connectLockin()
			return
		self.pb_LockinConnection.setValue(50)
		try:
			from Instruments import lockin
			### NOTE: change connection, depending on software version
			import zhinst
			from zhinst import ziPython
			ziv = zhinst.ziPython.__version__
			if ziv[:2] == "16":
				self.socketLockin = lockin.mfli(ip=self.ethernetIPLockin, port=8004, api=5) # for ethernet via "cas-jet" subnet
			elif ziv[:2] == "19": # follow new examples
				self.socketLockin = lockin.mfli(ip=self.ethernetIPLockin, port=8004, api=6, useAPIsession=False, log_level='status')
			else:
				raise NotImplemented("Currently the only reasonable version of the MFLI are v16.12 (stable) and v19.05 (testing) but you have %s" % ziv)
			self.socketLockin.loadPreset(4)
		except ImportError:
			self.pb_LockinConnection.setValue(0)
			raise ImportError("Could not import the pyLabSpec.Instruments.lockin module!")
		except RuntimeError:
			self.pb_LockinConnection.setValue(0)
			self.socketLockin = None
			msg = "Could not connect to the lock-in amplifier!"
			msgFinal = "Check that you can ping %s. If not, see the details" % self.ethernetIPLockin
			msgFinal += " for a possible solution."
			msgFinal += ", that the device is on, and that you can"
			msgFinal += " see ."
			msgDetails = "Firstly, ensure the lockin is connected to the HP switch (ports 1-12)"
			msgDetails += ", and that the device is on. Or..\n\n"
			msgDetails += "Access the web interface and ensure the ethernet configuration"
			msgDetails += " (via the Device tab) is set to the following settings:"
			msgDetails += "\nIPv4 Address - %s" % self.ethernetIPLockin
			msgDetails += "\nIPv4 Mask - 255.255.255.0"
			msgDetails += "\nGateway - 172.16.27.1"
			self.showConnectionWarning(msg, msgFinal=msgFinal, msgDetails=msgDetails)
		else:
			self.hasConnectedLockin = True
			self.socketLockin.identify()
			log.info("Connected to lock-in amplifier %s" % self.socketLockin.identifier)
			self.pb_LockinConnection.setValue(100)
			self.initLockin()
	def disconnectLockin(self, mouseEvent=False):
		"""
		Removes the connection to the lock-in amplifier.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if not self.hasConnectedLockin:
			return
		if self.socketLockin.trigger is not None:
			self.LockinSWTrigClear()
		self.hasConnectedLockin = False
		self.socketLockin = None
		self.pb_LockinConnection.setValue(0)
	
	def connectAll(self, mouseEvent=False):
		"""
		Being lazy... shame.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		instruments = ["MFC", "DG", "Synth", "Lockin"]
		for i in instruments:
			try:
				funcName = "connect%s" % i
				getattr(self, funcName)()
				time.sleep(0.3)
				checkName = "check_Use%s" % i
				getattr(self, checkName).setChecked(True)
				time.sleep(0.1)
			except:
				log.exception("couldn't connect to %s" % i)
		try:
			self.connectPressure(readout=2)
		except:
			log.exception("couldn't connect to the pressure readout!")
	def disconnectAll(self, mouseEvent=False):
		"""
		Being lazy... shame.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		instruments = ["MFC", "DG", "Synth", "Lockin"]
		for i in instruments:
			try:
				checkName = "check_Use%s" % i
				getattr(self, checkName).setChecked(False)
				time.sleep(0.1)
				funcName = "disconnect%s" % i
				getattr(self, funcName)()
				time.sleep(0.3)
			except:
				log.exception("couldn't disconnect to %s" % i)
		try:
			self.disconnectPressure(readout=2)
		except:
			log.exception("couldn't connect to the pressure readout!")



	### pressure-related things
	def pressureUpdate(self):
		"""
		Triggers the update of the pressure data. This is constantly being
		invoked from a daughter thread (of class genericThreadContinuous).
		"""
		PString1 = ""
		PString2a = ""
		PString2b = ""
		if self.hasConnectedPressure1:
			try:
				reading = self.socketPressure1.get_pressure(channel=1)
			except AttributeError:
				pass
			else:
				PString1 = str(reading[1]) + " torr"
		if self.hasConnectedPressure2:
			try:
				# get the readings
				reading = self.socketPressure2.get_pressure()
				if "off" in reading[0]:
					self.socketPressure2.set_gauge_state(channel=1, state="on")
				elif "off" in reading[2]:
					self.socketPressure2.set_gauge_state(channel=2, state="on")
			except AttributeError:
				pass
			except RuntimeError:
				log.debug("skipping this reading for now")
			else:
				# update CH 1
				r1 = reading[1]
				if "sensor" in reading[0].lower():
					r1 = reading[0].lower()
				elif r1 < 1e-8:
					r1 = "low (< 10 nanotorr)"
				elif r1 > 1000:
					r1 = "HIGH (> 1000 torr)"
				else:
					r1 = "%.2e torr" % r1
				PString2a = str(r1)
				# update CH 2
				r2 = reading[3]
				if "sensor" in reading[2].lower():
					r2 = reading[2].lower()
				elif r2 < 1e-8:
					r2 = "low (< 10 nanotorr)"
				elif r2 > 1000:
					r2 = "HIGH (> 1000 torr)"
				else:
					r2 = "%.2e torr" % r2
				PString2b = str(r2)
		self.signalPressuresUpdateGUI.emit(PString1, PString2a, PString2b)
	@QtCore.pyqtSlot(str, str, str)
	def pressureUpdateGUI(self, p1, p2a, p2b):
		"""
		Performs the query of a pressure gauge. This should be done
		within the main thread, thereby being TRIGGERED only by a
		daughter thread or timer. This ensures that only a single
		query is ever performed at a time.
		"""
		self.txt_PGauge1Reading.setText(p1)
		self.txt_PGauge2aReading.setText(p2a)
		self.txt_PGauge2bReading.setText(p2b)

	def chooseAdvSettingsPressure(self, mouseEvent=False):
		"""
		Loads the current 'Advanced Settings' for the pressure gauges
		into a ScrollableSettingsWindow

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		advSettingsWindow = ScrollableSettingsWindow(self, self.updateAdvSettingsPressure)
		if advSettingsWindow.exec_():
			pass
	def updateAdvSettingsPressure(self, advsettings):
		"""
		Updates 'Advanced Settings' for the pressure gauges from the
		ScrollableSettingsWindow

		:param advsettings: the dictionary containing all the new parameters from the ScrollableSettingsWindow
		:type advsettings: dict
		"""
		pass



	### temperature-related things
	def temperatureDiagramInit(self):
		"""
		Would initialize the schematic diagram for the temperature.
		
		The original plan was to draw something in the background of the
		appropriate frame containing all the QLCDNumber's, to make it
		clear which numbers match which location along the cell or
		experimental setup.
		"""
		# add here the initialization of a nice diagram
		pass
	def temperatureUpdate(self):
		"""
		Would update/process the temperature data.
		
		Should be modeled after the framework related to pressureUpdate and
		relevant signal/slot combo.
		"""
		if self.hasConnectedTemperature:
			# add here the update to the temperatures
			raise NotImplementedError()



	### MFC-related things
	def initMFC(self):
		"""
		Would send various desirable initialization commands to the MKS
		mass flow controller upon initial connection (but probably the
		module's __init__ method is probably a better place for universal
		settings).
		"""
		pass
	def MFCUpdate(self):
		"""
		Triggers the update of the MFCs.
		"""
		if self.timerMFCUpdate.stopped:
			return
		statuses = []
		# update MFCs
		for channel in range(1,5):
			if self.timerMFCUpdate.stopped:
				return
			#if not self.isMFCTab: break
			MFCflow = ""
			MFCstatus = ""
			# read from the socket
			if self.MFCisReady(channel):
				try:
					MFCflow = self.socketMFC.get_actual_flow(channel)
					MFCstatus = self.socketMFC.get_valve_mode(channel)
				except:
					pass
			statuses.append(("FC", channel, MFCflow, MFCstatus))
		# update pressure sensor
		if self.MFCisReady(5):
			if self.timerMFCUpdate.stopped:
				return
			pType = self.socketMFC.get_sensor_type(5)
			pVal = self.socketMFC.get_pressure(5)
			pUnit = self.socketMFC.get_pressure_unit()
			statuses.append((pType, pVal, pUnit))
		# emit update signal
		if self.timerMFCUpdate.stopped:
			return
		self.signalMFCUpdateGUI.emit(statuses)
	@QtCore.pyqtSlot(list)
	def MFCUpdateGUI(self, statuses=[]):
		"""
		Refreshes the statuses of the mass flow controllers.
		
		:param statuses: the list of statuses for each MFC channel
		:type statuses: list(tuple(int, float, string))
		"""
		try:
			for s in statuses:
				sensorType = s[0]
				if sensorType == "FC":
					#if not self.isMFCTab:
					#	continue
					channel = s[1]
					MFCflow = s[2]
					MFCstatus = s[3]
					if not self.MFCisReady(channel):
						getattr(self, "txt_MFC%sCurrentFlow" % channel).setText("")
						getattr(self, "txt_MFC%sstatus" % channel).setText("inactive")
						continue
					# note the gas correction factor
					gas = str(getattr(self, "combo_MFC%sGas" % channel).currentText())
					gascf = self.MFCgasproperties[gas]["CF"]
					# update the GUI elements
					MFCrange = float(getattr(self, "combo_MFC%sRange" % channel).currentText().split(' ')[0])
					# update status
					getattr(self, "txt_MFC%sCurrentFlow" % channel).setText(str(MFCflow))
					getattr(self, "txt_MFC%sstatus" % channel).setText(MFCstatus)
				elif sensorType in Instruments.massflowcontroller.MKS_946.pressure_sensors:
					pVal = s[1]
					pUnit = s[2]
					#if (pUnit == "mBAR") and (pVal > 1000):
					#	try:
					#		pVal /= 1000.0
					#		pUnit = pUnit.replace("m", "")
					#	except:
					#		pass
					self.txt_MFCPressureReadingMtab.setText("%s %s" % (pVal, pUnit))
		except IndexError:
			log.exception("received an IndexError in MFCUpdateGUI()!")
			log.exception("statuses were: %s" % statuses)
	def MFCisReady(self, channel=0):
		"""
		Checks the MFC connection and state of the device, before applying
		additional methods.

		Note that this method primarily just serves to reduce a lot of
		would-be duplicate code that would precede all the MFC functionalities.
		In most cases of said functionality, this can found

		:param channel: (optional) which channel to use
		:type channel: int

		:returns: whether the MFC controller/channel is ready for activity
		:rtype: bool
		"""
		# check the general status of the main control unit
		if (not self.hasConnectedMFC) and (not self.check_UseMFC.isChecked()):
			return False
		# check the specific flow controller
		if channel==1 and (not self.check_MFC1Active.isChecked()):
			return False
		elif channel==2 and (not self.check_MFC2Active.isChecked()):
			return False
		elif channel==3 and (not self.check_MFC3Active.isChecked()):
			return False
		elif channel==4 and (not self.check_MFC4Active.isChecked()):
			return False
		else:
			return True
	def MFCFlowSlider(self, channel=0):
		"""
		Directly updates the MFC channel with the new value of the flow
		rate from the GUI slider.

		:param channel: (optional) which channel to use
		:type channel: int
		"""
		if not self.MFCisReady(channel):
			return
		self.timerMFCUpdate.stop()
		# define the proper GUI elements for the channel
		slider = getattr(self, "slider_MFC%sFlow" % channel)
		# make note of the gas correction factor
		gas = str(getattr(self, "combo_MFC%sGas" % channel).currentText())
		gascf = self.MFCgasproperties[gas]["CF"]
		# convert the percentage to the full scale value
		pct = slider.value()
		log.debug("MFC (%s): updating mfc%s to %s\%" % (time.time(), channel, pct))
		self.socketMFC.set_setpoint(channel, pct)
		pct /= 100.0
		MFCrange = float(getattr(self, "combo_MFC%sRange" % channel).currentText().split(' ')[0])
		absFlow = pct * MFCrange * gascf
		getattr(self, "txt_MFC%sFSabs" % channel).setText(str(absFlow))
		if not slider.isChanging:
			self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
			self.timerMFCUpdate.start()
	def MFCSetAll(self, mouseEvent=False):
		"""
		Sets the active parameters for each MFC channel.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		self.MFCSet(channel=1)
		self.MFCSet(channel=2)
		self.MFCSet(channel=3)
		self.MFCSet(channel=4)
	def MFCReadAll(self, mouseEvent=False):
		"""
		Reads the active parameters for each MFC channel.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		self.MFCRead(channel=1)
		self.MFCRead(channel=2)
		self.MFCRead(channel=3)
		self.MFCRead(channel=4)
	def MFCSet(self, mouseEvent=False, channel=0):
		"""
		Sets the active parameters for the MFC channel.

		:param mouseEvent: (optional) the mouse event from a click
		:param channel: which channel to use
		:type mouseEvent: QtGui.QMouseEvent
		:type channel: int
		"""
		self.checkInputsMFC()
		if (not channel) or (not self.MFCisReady(channel)):
			return
		self.timerMFCUpdate.stop()
		time.sleep(0.1)
		# get range
		MFCrange = getattr(self, "combo_MFC%sRange" % channel).currentText()
		# get gas
		gas = str(getattr(self, "combo_MFC%sGas" % channel).currentText())
		gascf = self.MFCgasproperties[gas]["CF"]
		# get setpoint
		txt = str(getattr(self, "txt_MFC%sFSabs" % channel).text())
		if txt:
			pct = float(txt)*100
			pct /= float(MFCrange.split(' ')[0]) * gascf
			getattr(self, "slider_MFC%sFlow" % channel).setValue(pct)
		self.socketMFC.set_range_unit(channel, MFCrange)
		self.socketMFC.set_correction_factor(channel, gascf)
		if txt:
			self.socketMFC.set_setpoint(channel, pct)
		self.socketMFC.reset_soft()
		time.sleep(0.2)
		self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
		self.timerMFCUpdate.start()
	def MFCRead(self, mouseEvent=False, channel=0):
		"""
		Reads the active parameters for the MFC channel.

		:param mouseEvent: (optional) the mouse event from a click
		:param channel: which channel to use
		:type mouseEvent: QtGui.QMouseEvent
		:type channel: int
		"""
		if (not channel) or (not self.MFCisReady(channel)):
			return
		self.timerMFCUpdate.stop()
		time.sleep(0.1)
		self.socketMFC.reset_soft()
		# update range
		MFCrange = self.socketMFC.get_range_unit(channel)
		log.info("read MFCrange: %s" % MFCrange)
		cb = getattr(self, "combo_MFC%sRange" % channel)
		# TODO: set the correct index
		# update gas type
		# TODO: read gas
		cb =  getattr(self, "combo_MFC%sGas" % channel)
		# TODO: set the index or create a message with the gas correction if it differs
		# update set point
		MFCsetpoint = self.socketMFC.get_setpoint(channel)
		log.info("read MFCsetpoint: %s" % MFCsetpoint)
		getattr(self, "txt_MFC%sFSabs" % channel).setText(str(MFCsetpoint))
		# update flow
		MFCflow = self.socketMFC.get_actual_flow(channel)
		log.info("read MFCflow: %s" % MFCflow)
		getattr(self, "txt_MFC%sCurrentFlow" % channel).setText(str(MFCflow))
		# update status
		MFCstatus = self.socketMFC.get_valve_mode(channel)
		getattr(self, "txt_MFC%sstatus" % channel).setText(MFCstatus)
		# other things not for the GUI...
		log.info("last response: %s" % self.socketMFC.get_status(channel))
		log.info("module type: %s" % self.socketMFC.get_module_type(channel))
		log.info("cf: %s" % self.socketMFC.get_correction_factor(channel))
		self.socketMFC.reset_soft()
		self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
		self.timerMFCUpdate.start()
	def MFCOpen(self, mouseEvent=False, channel=0):
		"""
		Opens the MFC channel(s).

		:param mouseEvent: (optional) the mouse event from a click
		:param channel: (optional) which channel to use
		:type mouseEvent: QtGui.QMouseEvent
		:type channel: int
		"""
		if not self.MFCisReady(channel):
			return
		self.timerMFCUpdate.stop()
		time.sleep(0.1)
		self.socketMFC.reset_soft()
		self.socketMFC.open_valve(int(channel))
		self.socketMFC.reset_soft()
		self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
		self.timerMFCUpdate.start()
	def MFCClose(self, mouseEvent=False, channel=0):
		"""
		Closes the MFC channel(s).

		:param mouseEvent: (optional) the mouse event from a click
		:param channel: (optional) which channel to use
		:type mouseEvent: QtGui.QMouseEvent
		:type channel: int
		"""
		if not self.MFCisReady(channel):
			return
		self.timerMFCUpdate.stop()
		time.sleep(0.1)
		self.socketMFC.reset_soft()
		self.socketMFC.close_valve(int(channel))
		self.socketMFC.reset_soft()
		self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
		self.timerMFCUpdate.start()
	
	def MFCSetRatio(self, mouseEvent=False):
		"""
		Sets up a recipe for PID control. See Section 6.7.3.2 of the user
		manual for more details!
		
		Note that MANY paramters are hardcoded here, which have been
		found to work best under test conditions. It may be required to
		edit these values below, if experimental conditions so demand.
		
		Note also that the default recipe indices are 1.. therefore the
		ratio recipe RR1 is always modified here, as well as the PID
		control recipe R1.
		"""
		try:
			pSP = float(str(self.txt_MFCPressureTarget.text()))
		except:
			self.txt_MFCPressureTarget.setText("fix me..")
			raise Exception("you have a queer target pressure!!")
		self.timerMFCUpdate.stop()
		### Ratio setup
		recipeNum = 1
		if self.check_MFC1Active.isChecked():
			mfc1 = self.txt_MFC1FSabs.value()
		else:
			mfc1 = None
		if self.check_MFC2Active.isChecked():
			mfc2 = self.txt_MFC2FSabs.value()
		else:
			mfc2 = None
		if self.check_MFC3Active.isChecked():
			mfc3 = self.txt_MFC3FSabs.value()
		else:
			mfc3 = None
		if self.check_MFC4Active.isChecked():
			mfc4 = self.txt_MFC4FSabs.value()
		else:
			mfc4 = None
		self.socketMFC.set_ratio(recipeNum=recipeNum, mfc1=mfc1,
		                         mfc2=mfc2, mfc3=mfc3, mfc4=mfc4)
		## PID setup
		pidCh = "Rat"
		pidPSensor = 5
		kp = 1.0
		ti = 1.0
		td = 0.0
		direction = "downstream"
		ramp = 5
		start = 5.0
		end = 30.0
		base = 0.0
		ceiling = 100.0
		preset = 0.0
		band = 0
		gain = 1
		self.socketMFC.set_pid(
			recipeNum=1, pidChannel=pidCh,
			pidPSensor=pidPSensor, pSP=pSP,
			kp=kp, ti=ti, td=td,
			ramp=5, start=start, end=end, preset=preset,
			base=base, ceiling=ceiling,
			band=band, gain=gain)
		# activate the recipe and the status-updating loop
		self.socketMFC.set_active_recipe("pid")
		self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
		self.timerMFCUpdate.start()
	def MFCStopRatio(self, mouseEvent=False):
		"""
		Terminates PID control of the MFCs.
		"""
		self.socketMFC.set_active_recipe("off")
	
	def MFCClear(self, mouseEvent=False):
		"""
		Performs a soft reset (clear).

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if (not self.hasConnectedMFC) and (not self.check_UseMFC.isChecked()):
			log.warning("you can't clear an instrument connection that doesn't exist..")
			return
		self.timerMFCUpdate.stop()
		self.socketMFC.reset_soft(n=3)
		self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
		self.timerMFCUpdate.start()

	def chooseAdvSettingsMFC(self, mouseEvent=False):
		"""
		Loads the current 'Advanced Settings' for the MFCs into a
		ScrollableSettingsWindow

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		advSettingsWindow = ScrollableSettingsWindow(self, self.updateAdvSettingsMFC)
		advSettingsWindow.addRow(
			"serialPortMFC", "Default serial port for the MFC",
			self.serialPortMFC, "(none)")
		if advSettingsWindow.exec_():
			pass
	def updateAdvSettingsMFC(self, advsettings):
		"""
		Updates 'Advanced Settings' for the MFCs from the
		ScrollableSettingsWindow

		:param advsettings: the dictionary containing all the new parameters from the ScrollableSettingsWindow
		:type advsettings: dict
		"""
		self.timerMFCUpdate.stop()
		self.serialPortMFC = qlineedit_to_str(advsettings["serialPortMFC"])
		self.timerMFCUpdate = genericThreadContinuous(self.MFCUpdate, self.updateperiodMFCUpdate)
		self.timerMFCUpdate.start()


	### DG-related things
	def initDG(self):
		"""
		Would send various desirable initialization commands to the MKS
		mass flow controller upon initial connection (but probably the
		module's __init__ method is probably a better place for universal
		settings).
		"""
		pass
	def DGSetValues(self, mouseEvent=False):
		"""
		Sets all the timings for the TTL pulses onto the delay degenerator,
		as well as the trigger rate. The trigger rate also possibly defines
		a new frequency step delay, in case one is measuring only one
		instantaneous reading from the lockin at each frequency step.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# check the general status of the main control unit
		if (not self.hasConnectedDG) and (not self.check_UseDG.isChecked()):
			return False
		self.socketDG.set_trigger_source(0)
		trig_rate = float(self.txt_DGTriggerRate.text())
		self.socketDG.set_trigger_rate(trig_rate)
		if not self.check_LockinUseSWTrigInt.isChecked():
			#self.txt_SynthDelay.setText("%g" % float(1/trig_rate*1000.0))
			self.txt_MonTimestep.setText("%g" % float(1/trig_rate*1000.0))
		self.socketDG.set_delay(channel="A", ref_channel="T0", delay=float(self.txt_PulseValve_start.text()))
		self.socketDG.set_delay(channel="B", ref_channel="T0", delay=float(self.txt_PulseValve_end.text()))
		self.socketDG.set_delay(channel="C", ref_channel="T0", delay=float(self.txt_PulseLockinSingle_start.text()))
		self.socketDG.set_delay(channel="D", ref_channel="T0", delay=float(self.txt_PulseLockinSingle_end.text()))
		self.socketDG.set_delay(channel="E", ref_channel="T0", delay=float(self.txt_PulseHV_start.text()))
		self.socketDG.set_delay(channel="F", ref_channel="T0", delay=float(self.txt_PulseHV_end.text()))
		self.socketDG.set_delay(channel="G", ref_channel="T0", delay=float(self.txt_PulseDG4_start.text()))
		self.socketDG.set_delay(channel="H", ref_channel="T0", delay=float(self.txt_PulseDG4_end.text()))
	def DGReadValues(self, mouseEvent=False):
		"""
		Loops through all the triggers on the delay generator, and reads
		their edges in based on the current state of the instrument.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# check the general status of the main control unit
		if (not self.hasConnectedDG) and (not self.check_UseDG.isChecked()):
			return False
		trig_rate = self.socketDG.get_trigger_rate()
		self.txt_DGTriggerRate.setText("%f" % trig_rate)
		if not self.check_LockinUseSWTrigInt.isChecked():
			self.txt_SynthDelay.setText("%g" % float(1/trig_rate*1000.0))
			self.txt_MonTimestep.setText("%g" % float(1/trig_rate*1000.0))
		self.txt_PulseValve_start.setText("%f" % self.socketDG.get_delay('A')[1])
		self.txt_PulseValve_end.setText("%f" % self.socketDG.get_delay('B')[1])
		self.txt_PulseLockinSingle_start.setText("%f" % self.socketDG.get_delay('C')[1])
		self.txt_PulseLockinSingle_end.setText("%f" % self.socketDG.get_delay('D')[1])
		self.txt_PulseHV_start.setText("%f" % self.socketDG.get_delay('E')[1])
		self.txt_PulseHV_end.setText("%f" % self.socketDG.get_delay('F')[1])
		self.txt_PulseDG4_start.setText("%f" % self.socketDG.get_delay('G')[1])
		self.txt_PulseDG4_end.setText("%f" % self.socketDG.get_delay('H')[1])
	def pulsePlotInit(self):
		"""
		Initializes the plots containing the pulse windows.
		"""
		brushes = { # default: rgba=(0, 0, 255, 50)
			"Valve": QtGui.QBrush(QtGui.QColor(200, 200, 200, 75)),
			"LockinSingle": QtGui.QBrush(QtGui.QColor(0, 0, 255, 50)),
			"LockinInt": QtGui.QBrush(QtGui.QColor(0, 255, 255, 75)),
			"LockinBase": QtGui.QBrush(QtGui.QColor(112, 166, 255, 50)),
			"HV": QtGui.QBrush(QtGui.QColor(255, 120, 0, 75)),
			"DG4": QtGui.QBrush(QtGui.QColor(0, 0, 255, 50))}
		# defines plot regions for each individual pulse
		self.pulsePlotRegion_Valve =        pg.LinearRegionItem(values=[0,     1e-3], bounds=[0,None], brush=brushes["Valve"])
		self.pulsePlotRegion_LockinSingle = pg.LinearRegionItem(values=[0,     0.5e-3], bounds=[0,None], brush=brushes["LockinSingle"])
		self.pulsePlotRegion_LockinInt =    pg.LinearRegionItem(values=[0.7e-3,1.5e-3], bounds=[0,None], brush=brushes["LockinInt"])
		self.pulsePlotRegion_LockinBase =   pg.LinearRegionItem(values=[5.5e-3,8.5e-3], bounds=[None,None], brush=brushes["LockinBase"])
		self.pulsePlotRegion_HV =           pg.LinearRegionItem(values=[0,     1.5e-3], bounds=[0,None], brush=brushes["HV"])
		self.pulsePlotRegion_DG4 =          pg.LinearRegionItem(values=[0,     1e-3], bounds=[0,None], brush=brushes["DG4"])
		for i in ["Valve", "LockinSingle", "LockinInt", "LockinBase", "HV", "DG4"]:
			vars(self)["pulsePlotRegion_%s" % i].sigRegionChanged.connect(self.updatePulseFields)
			vars(self)["txt_Pulse%s_start" % i].editingFinished.connect(self.updatePulseWindows)
			vars(self)["txt_Pulse%s_end" % i].editingFinished.connect(self.updatePulseWindows)
			signal = pg.SignalProxy(
				vars(self)["pulsePlotRegion_%s" % i].sigRegionChanged,
				rateLimit=5,
				slot=self.DGSetValues)
			setattr(self, "pulsePlotRegion_%s_changedSignal" % i, signal)
		self.updatePulseFields()
		# sets up the GraphicsLayoutWidget
		self.pulsePlot_Valve = self.PulsePlotWidget.addPlot()
		self.PulsePlotWidget.nextRow()
		self.pulsePlot_LockinSingle = self.PulsePlotWidget.addPlot()
		self.PulsePlotWidget.nextRow()
		self.pulsePlot_LockinInt = self.PulsePlotWidget.addPlot()
		self.PulsePlotWidget.nextRow()
		self.pulsePlot_HV = self.PulsePlotWidget.addPlot()
		self.PulsePlotWidget.nextRow()
		self.pulsePlot_DG4 = self.PulsePlotWidget.addPlot()
		self.PulsePlotWidget.nextRow()
		self.pulsePlot_Valve.setLabel('bottom', "DG Chan 1 -> Valve", units='s')
		self.pulsePlot_LockinSingle.setLabel('bottom', "DG Chan 2 -> Lockin Gate (single shot)", units='s')
		self.pulsePlot_LockinInt.setLabel('bottom', "Lockin Gate (integration and baseline)", units='s')
		self.pulsePlot_HV.setLabel('bottom', "DG Chan 3 -> HV Gate", units='s')
		self.pulsePlot_DG4.setLabel('bottom', "DG Chan 4", units='s')
		# update axes and disable buttons/menus
		for i in ["Valve", "LockinSingle", "LockinInt", "HV", "DG4"]:
			vars(self)["pulsePlot_%s" % i].getAxis('left').setStyle(showValues=False)
			vars(self)["pulsePlot_%s" % i].getViewBox().state["enableMenu"] = False
			vars(self)["pulsePlot_%s" % i].hideButtons()
		# add regions and update view
		for i in ["Valve", "LockinSingle", "LockinInt", "HV", "DG4"]:
			vars(self)["pulsePlot_%s" % i].addItem(
				vars(self)["pulsePlotRegion_%s" % i],
				ignoreBounds=True)
		self.pulsePlot_LockinInt.addItem(self.pulsePlotRegion_LockinBase, ignoreBounds=True)
		self.check_LockPulsePlotAxes.setChecked(True)
		self.pulsePlot_Valve.getViewBox().setXRange(-40e-6, 130e-6)
	def updatePulseFields(self):
		"""
		This is triggered when the user has moved one of the pulse
		windows, thereby causing the text fields to be updated
		properly.
		"""
		for i in ["Valve", "LockinSingle", "LockinInt", "LockinBase", "HV", "DG4"]:
			region = vars(self)["pulsePlotRegion_%s" % i]
			txtStart = vars(self)["txt_Pulse%s_start" % i]
			txtEnd = vars(self)["txt_Pulse%s_end" % i]
			try:
				txtStart.setText("%.2e" % region.getRegion()[0])
				txtEnd.setText("%.2e" % region.getRegion()[1])
			except ValueError:
				pass
	def updatePulseWindows(self):
		"""
		This is triggered when the user has modified one of the text
		fields for the pulse windows, thereby forcing the plot windows
		to update.
		"""
		for i in ["Valve", "LockinSingle", "LockinInt", "LockinBase", "HV", "DG4"]:
			region = vars(self)["pulsePlotRegion_%s" % i]
			txtStart = vars(self)["txt_Pulse%s_start" % i]
			txtEnd = vars(self)["txt_Pulse%s_end" % i]
			try:
				region.setRegion([float(txtStart.text()), float(txtEnd.text())])
			except ValueError:
				pass
	def DGUpdatePlotAxisLocks(self, eventSignal=None):
		"""
		This is triggered when the user changes the checkbox specifying
		whether the four pulse window plots should all be aligned with
		each other.
		"""
		if self.check_LockPulsePlotAxes.isChecked():
			self.pulsePlot_Valve.setXLink(self.pulsePlot_LockinSingle)
			self.pulsePlot_LockinSingle.setXLink(self.pulsePlot_Valve)
			self.pulsePlot_LockinInt.setXLink(self.pulsePlot_Valve)
			self.pulsePlot_HV.setXLink(self.pulsePlot_Valve)
			self.pulsePlot_DG4.setXLink(self.pulsePlot_Valve)
		else:
			self.pulsePlot_Valve.setXLink(None)
			self.pulsePlot_LockinSingle.setXLink(None)
			self.pulsePlot_LockinInt.setXLink(None)
			self.pulsePlot_HV.setXLink(None)
			self.pulsePlot_DG4.setXLink(None)
	def chooseAdvSettingsDG(self, mouseEvent=False):
		"""
		Loads the current 'Advanced Settings' for the delay generator
		into a ScrollableSettingsWindow

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		advSettingsWindow = ScrollableSettingsWindow(self, self.updateAdvSettingsDG)
		advSettingsWindow.addRow(
			"ethernetIPDG", "Default ethernet IP for the delay generator",
			self.ethernetIPDG, "(none)")
		advSettingsWindow.addRow(
			"ethernetPortDG", "Default ethernet port for the delay generator",
			self.ethernetPortDG, "(none)")
		if advSettingsWindow.exec_():
			pass
	def updateAdvSettingsDG(self, advsettings):
		"""
		Updates 'Advanced Settings' for the delay generator from the
		ScrollableSettingsWindow

		:param advsettings: the dictionary containing all the new parameters from the ScrollableSettingsWindow
		:type advsettings: dict
		"""
		self.ethernetIPDG = qlineedit_to_str(advsettings["ethernetIPDG"])
		self.ethernetPortDG = qlineedit_to_int(advsettings["ethernetPortDG"].text())


	### synthesizer-related things
	def initSynth(self):
		"""
		Would sends various desirable initialization commands to the
		Synthesizer upon initial connection.

		In practice, this may be the only way to ensure the instrument
		is in an appropriate state for the scanning routine to operate.
		However, this method will only be set up and remain without any
		consequences for the time being.
		
		Similar to the CASAC GUI, this routine has proven unncessary,
		so long as the synthesizer boots into factory default settings.
		"""
		pass
	def SynthEZFreqCenterUseLabel(self, mouseEvent=False):
		"""
		Uses the first plot label to fill in the value for the center

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if not len(self.scanPlotLabels):
			msg = "You do not have a label on the plot!"
			self.showWarning(msg)
			return
		freqCenter = self.scanPlotLabels[-1][1].x()
		self.txt_SynthEZFreqCenter.setText("%.3f" % freqCenter)
	def SynthEZFreqCenterSet(self, mouseEvent=False):
		"""
		Sets the lower/upper frequencies based on the center-frequency
		+/- the desired scan radius.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# make note of frequency center/span
		freqCenter = self.txt_SynthEZFreqCenter.text()
		freqSpan = self.txt_SynthEZFreqSpan.text()
		if (not freqCenter) or (not freqSpan):
			return
		# determine range
		freqLower = float(freqCenter) - float(freqSpan)/2.0
		freqUpper = float(freqCenter) + float(freqSpan)/2.0
		# send to the start/stop entries
		self.txt_SynthFreqStart.setText(str(freqLower))
		self.txt_SynthFreqEnd.setText(str(freqUpper))
		# update the history list & combobox
		self.synthEZFreqCenterHistory.append(float(freqCenter))
		try:
			self.combo_SynthFreqCenterHistory.currentIndexChanged.disconnect()
		except TypeError:
			pass
		self.combo_SynthFreqCenterHistory.clear()
		self.combo_SynthFreqCenterHistory.addItem("Recent Center Frequencies")
		for f in reversed(self.synthEZFreqCenterHistory):
			self.combo_SynthFreqCenterHistory.addItem("%s" % f)
		self.combo_SynthFreqCenterHistory.setCurrentIndex(0)
		self.combo_SynthFreqCenterHistory.currentIndexChanged.connect(self.getSynthEZFreqCenterHistory)
	def SynthEZFreqShiftDown(self, mouseEvent=False):
		"""
		Shifts the synthesizer frequencies down in value, based on the
		desired amount in the EZ Freq. Window box.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		frequencyEntries = [
			self.txt_SynthFreqStart,
			self.txt_SynthFreqEnd,
			self.txt_SynthEZFreqShift]
		if any(x.text() == "" for x in frequencyEntries):
			msg = "Found at least one blank entry for the synthesizer frequency."
			msg += " Check the start/end frequencies, as well as the value of the"
			msg += " desired shift."
			title = "Found blank entry!"
			self.showInputError(msg)
		toShift = float(self.txt_SynthEZFreqShift.text())
		newStart = float(self.txt_SynthFreqStart.text()) - toShift
		newEnd = float(self.txt_SynthFreqEnd.text()) - toShift
		self.txt_SynthFreqStart.setText(str(newStart))
		self.txt_SynthFreqEnd.setText(str(newEnd))
	def SynthEZFreqShiftUp(self, mouseEvent=False):
		"""
		Shifts the synthesizer frequencies up in value, based on the
		desired amount in the EZ Freq. Window box.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		frequencyEntries = [
			self.txt_SynthFreqStart,
			self.txt_SynthFreqEnd,
			self.txt_SynthEZFreqShift]
		if any(x.text() == "" for x in frequencyEntries):
			msg = "Found at least one blank entry for the synthesizer frequency."
			msg += " Check the start/end frequencies, as well as the value of the"
			msg += " desired shift."
			title = "Found blank entry!"
			self.showInputError(msg)
		toShift = float(self.txt_SynthEZFreqShift.text())
		newStart = float(self.txt_SynthFreqStart.text()) + toShift
		newEnd = float(self.txt_SynthFreqEnd.text()) + toShift
		self.txt_SynthFreqStart.setText(str(newStart))
		self.txt_SynthFreqEnd.setText(str(newEnd))
	def SynthEZFreqCursorsSet(self, mouseEvent=False):
		"""
		Sets the lower/upper frequencies based on the last two labels
		added to the scan plot.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if not len(self.scanPlotLabels) >= 2:
			msg = "You do not have at least two labels on the plot!"
			self.showWarning(msg)
			return
		plotLabels = sorted(self.scanPlotLabels[-2:], key=lambda x: x[1].x())
		freqLower = plotLabels[0][1].x()
		freqUpper = plotLabels[-1][1].x()
		self.txt_SynthFreqStart.setText(str(freqLower))
		self.txt_SynthFreqEnd.setText(str(freqUpper))
	def getSynthEZFreqCenterHistory(self):
		"""
		Pushes the history item to the EZ Freq. Center and resets the history
		index to zero.
		"""
		idx = self.combo_SynthFreqCenterHistory.currentIndex()
		if not idx == 0:
			self.combo_SynthFreqCenterHistory.currentIndexChanged.disconnect()
			self.txt_SynthEZFreqCenter.setText(self.combo_SynthFreqCenterHistory.currentText())
			self.combo_SynthFreqCenterHistory.setCurrentIndex(0)
			self.combo_SynthFreqCenterHistory.currentIndexChanged.connect(self.getSynthEZFreqCenterHistory)
	def setMultFactor(self, mouseEvent=False):
		"""
		Updates the entry for the multiplication factor, based on the
		currently-selected multiplier band/mode.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		isManualMultiplierBand = self.combo_AMCband.currentText() == "(manual)"
		isManualMultiplierMode = self.combo_AMCmode.currentText() == "(manual)"
		if isManualMultiplierBand or isManualMultiplierMode:
			msg = "Cannot set the multiplication factor if you have not"
			msg += " chosen both a band and its input mode!"
			self.showInputError(msg)
		currentBand = str(self.combo_AMCband.currentText())
		currentMode = str(self.combo_AMCmode.currentText())
		self.txt_SynthMultFactor.setText(str(self.AMCBandSpecs[currentBand][currentMode]))
	def setFrequencies(self, mouseEvent=False):
		"""
		Updates the entry for the start/stop frequencies, based on the
		currently-selected multiplier band.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		isManualMultiplierBand = self.combo_AMCband.currentText() == "(manual)"
		if isManualMultiplierBand:
			msg = "Cannot set the frequency limits if you have not chosen a band!"
			self.showInputError(msg)
		currentBand = str(self.combo_AMCband.currentText())
		lowerFreq = self.AMCBandSpecs[currentBand]["Range"][0] * 1e3
		upperFreq = self.AMCBandSpecs[currentBand]["Range"][1] * 1e3
		self.txt_SynthFreqStart.setText(str(lowerFreq))
		self.txt_SynthFreqEnd.setText(str(upperFreq))

	def stepSynthPower(self, newPow):
		"""
		Provides the routine for stepping across intermediate RF power
		levels to the final value.

		:param newPow: the new RF power level to be set
		:type newPow: float
		"""
		currentPower = self.socketSynth.get_power_level()
		if currentPower < -20.0:
			log.info("the current power was below -20.0 dBm; will first set it to -20.0 (which should be safe)..")
			self.socketSynth.set_power_level(-20.0)
			currentPower = -20.0
			time.sleep(0.05)
		isWithinRFLimits = (currentPower <= self.maxRFInputHi) and (newPow > self.maxRFInputHi)
		if (not self.hasPermissionHigherRF) and isWithinRFLimits:
			title = "Just a precaution.."
			msg = """You are about to cross the threshold for the RF
			power level (0.0 dBm) that could damage the multiplier chain's
			'High' input. If you are using the 'Standard' input, there is
			no need to worry."""
			final = "How would you like to proceed?"
			self.showWarning(msg, msgFinal=final, title=title)
			self.hasPermissionHigherRF = True
		if ((newPow <= self.maxRFInputHi) or self.hasPermissionHigherRF) and (newPow <= self.maxRFInputStd):
			if abs(newPow - currentPower) > 0.3:
				sign = np.sign(newPow - currentPower)
				startPow = currentPower + sign*self.RFstepPow
				endPow = newPow + sign*self.RFstepPow
				if startPow < endPow:
					intermediatePowerLevels = list(np.arange(startPow, endPow, self.RFstepPow))
				else:
					intermediatePowerLevels = reversed(list(np.arange(endPow+self.RFstepPow, startPow, self.RFstepPow)))
				for intermediatePow in intermediatePowerLevels:
					self.socketSynth.set_power_level(intermediatePow)
					self.combo_SynthPower.setValue(intermediatePow)
					time.sleep(self.RFstepTime)
			else:
				self.socketSynth.set_power_level(newPow)

	def SynthSetValues(self, mouseEvent=False):
		"""
		Loops through all the inputs to the synthesizer, and sets their
		states within the instrument.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# check desired usage, its connection, and its inputs
		self.checkInputsSynth()
		if (not self.check_UseSynth.isChecked()) or (not self.hasConnectedSynth):
			return
		self.tab_FreqScan.setEnabled(False) # disable the frequency tab to prevent conflicting commands
		# ensure that the scan is not active
		toPauseThenContinue = False
		if self.isScanning and not self.isPaused:
			toPauseThenContinue = True
			self.scanPause()
			time.sleep(self.waitBeforeScanRestart*5)
		# set frequency to the "start"
		if self.txt_SynthFreqStart.text():
			freqStart = float(self.txt_SynthFreqStart.text())
			synthMultFactor = int(self.txt_SynthMultFactor.text())
			synthFreqStart = freqStart/float(synthMultFactor)
			self.socketSynth.set_frequency(synthFreqStart, unit='MHz')
		# set RF output
		newRFPower = self.combo_SynthPower.value()
		#curRFPower = self.socketSynth.get_power_level()
		#self.combo_SynthPower.setValue(curRFPower)
		self.abortSynthPowerStepping = False
		if self.check_SynthRF.isChecked():
			# if not yet on: set to -20, turn on, then step to power
			if not self.socketSynth.get_rf_power_state():
				self.socketSynth.set_power_level(-20.0)
				self.socketSynth.switch_rf_power(state="ON")
			self.stepSynthPower(newRFPower)
		else:
			self.stepSynthPower(newRFPower) # or should it default to -20.0 ?
			self.socketSynth.switch_rf_power(state="OFF")
		# set modulation
		modtype = self.slider_SynthMod.value()
		if self.check_useSynthMod.isChecked() and modtype:
			if modtype == -1: # AM
				self.socketSynth.set_modulation_type(modtype="AM")
				# set AM freq
				freq = float(self.txt_SynthAMFreq.text())
				self.socketSynth.set_modulation_freq(freq, modtype="AM")
				# set AM depth
				deviation = float(self.combo_SynthAMDepth.value())
				self.socketSynth.set_modulation_dev(deviation, modtype="AM")
				# set AM shape
				shape = self.combo_SynthAMShape.currentText()
				for t in self.modShapes:
					shapeHuman,shapeMachine = t
					if shape == shapeHuman:
						shape = shapeMachine
						break
				self.socketSynth.set_modulation_shape(shape, modtype="AM")
			elif modtype == 1: # FM
				self.socketSynth.set_modulation_type(modtype="FM")
				# set FM freq
				freq = float(self.txt_SynthFMFreq.text())*1e3
				self.socketSynth.set_modulation_freq(freq, modtype="FM")
				# set FM width
				deviation = float(self.txt_SynthFMWidth.text())*1e3
				deviation /= float(self.txt_SynthMultFactor.text())
				self.socketSynth.set_modulation_dev(deviation, modtype="FM")
				# set FM shape
				shape = self.combo_SynthFMShape.currentText()
				for t in self.modShapes:
					shapeHuman,shapeMachine = t
					if shape == shapeHuman:
						shape = shapeMachine
						break
				self.socketSynth.set_modulation_shape(shape, modtype="FM")
			# then turn modulation and LF on
			self.socketSynth.switch_modulation_state(state="ON")
			self.socketSynth.switch_lf_state(state="ON")
			self.socketSynth.set_lf_amplitude(amplitude=1.0)
		else:
			# then just turn modulation and LF off
			self.socketSynth.switch_modulation_state(state="OFF")
			self.socketSynth.switch_lf_state(state="OFF")
		if toPauseThenContinue:
			self.scanContinue()
		self.tab_FreqScan.setEnabled(True)

	def SynthReadValues(self, mouseEvent=False):
		"""
		Loops through all the inputs to the synthesizer, and sets their
		values based on the current state of the instrument.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if (not self.check_UseSynth.isChecked()) or (not self.hasConnectedSynth):
			return
		# ensure that the scan is not active
		toPauseThenContinue = False
		if self.isScanning and not self.isPaused:
			toPauseThenContinue = True
			self.scanPause()
			time.sleep(self.waitBeforeScanRestart*5)
		# read multiplication factor, and use this to set the start frequency
		synthMultFactor = self.txt_SynthMultFactor.text()
		if synthMultFactor:
			freqStart = self.socketSynth.get_frequency()/1.0e6 * int(synthMultFactor)
			self.txt_SynthFreqStart.setText(str(freqStart))
		# read RF power level
		powLevel = self.socketSynth.get_power_level()
		self.combo_SynthPower.setValue(powLevel)
		# read RF output state
		rfoutput = self.socketSynth.get_rf_power_state()
		if rfoutput:
			self.check_SynthRF.setChecked(True)
		else:
			self.check_SynthRF.setChecked(False)
		# read modulation type
		modtype = self.socketSynth.get_modulation_type()
		if len(modtype.split(' ')) > 1:
			pass
		elif modtype == "AM":
			# set slider to -1
			self.slider_SynthMod.setValue(-1)
			# read freq
			freq = self.socketSynth.get_modulation_freq(modtype="AM")
			self.txt_SynthAMFreq.setText("%f" % freq)
			# read depth/width
			deviation = self.socketSynth.get_modulation_dev(modtype="AM")
			self.combo_SynthAMDepth.setValue(deviation)
			# read shape
			shape = self.socketSynth.get_modulation_shape(modtype="AM")
			shapeIndex = 0
			for i,t in enumerate(self.modShapes):
				shapeHuman,shapeMachine = t
				if shape == shapeMachine:
					shapeIndex = i
					break
			self.combo_SynthAMShape.setCurrentIndex(shapeIndex)
		elif modtype == "FM":
			# set slider to 1
			self.slider_SynthMod.setValue(1)
			# read freq
			freq = self.socketSynth.get_modulation_freq(modtype="FM")/1e3
			self.txt_SynthFMFreq.setText("%f" % freq)
			# read depth/width
			deviation = self.socketSynth.get_modulation_dev(modtype="FM")/1e3
			deviation *= int(self.txt_SynthMultFactor.text())
			self.txt_SynthFMWidth.setText("%f" % deviation)
			# read shape
			shape = self.socketSynth.get_modulation_shape(modtype="FM")
			shapeIndex = 0
			for i,t in enumerate(self.modShapes):
				shapeHuman,shapeMachine = t
				if shape == shapeMachine:
					shapeIndex = i
					break
			self.combo_SynthFMShape.setCurrentIndex(shapeIndex)
		else:
			# set slider to middle
			self.slider_SynthMod.setValue(0)
		# read modulation state
		usemod = self.socketSynth.get_modulation_state()
		if usemod:
			self.check_useSynthMod.setChecked(True)
		else:
			self.check_useSynthMod.setChecked(False)
		# finally, continue the scan if necessary
		if toPauseThenContinue:
			self.scanContinue()

	def chooseAdvSettingsSynth(self, mouseEvent=False):
		"""
		Loads the current 'Advanced Settings' for the Synthesizer into a
		ScrollableSettingsWindow

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		advSettingsWindow = ScrollableSettingsWindow(self, self.updateAdvSettingsSynth)
		hover = "This is the number that, for example, kicks in a user warning\n"
		hover += "and slows down the plot updates."
		advSettingsWindow.addRow(
			"reasonableMaxFreqPoints", "Number of points deemed 'large'",
			self.reasonableMaxFreqPoints, "(none)", hover=hover)
		advSettingsWindow.addRow(
			"reasonableMaxScanTime", "Time for a scan deemed 'long'",
			self.reasonableMaxScanTime, "min", hover=hover)
		advSettingsWindow.addRow(
			"synthFreqResolution", "How many decimal places for the Synth frequency",
			self.synthFreqResolution, "Hz")
		advSettingsWindow.addRow(
			"maxRFInputStd", "Max RF power for the 'Standard' AMC input",
			self.maxRFInputStd, "dBm", hover="Paola is watching you..")
		advSettingsWindow.addRow(
			"maxRFInputHi", "Max RF power for the 'High' AMC input",
			self.maxRFInputHi, "dBm", hover="RTFM, mate")
		advSettingsWindow.addRow(
			"RFstepPow", "Size of the intermediate RF power steps",
			self.RFstepPow, "dBm")
		advSettingsWindow.addRow(
			"RFstepTime", "Delay between the intermediate RF steps",
			self.RFstepTime, "s")
		if advSettingsWindow.exec_():
			pass
	def updateAdvSettingsSynth(self, advsettings):
		"""
		Updates 'Advanced Settings' for the Synthesizer from the
		ScrollableSettingsWindow

		:param advsettings: the dictionary containing all the new parameters from the ScrollableSettingsWindow
		:type advsettings: dict
		"""
		self.reasonableMaxFreqPoints = qlineedit_to_int(advsettings["reasonableMaxFreqPoints"])
		self.reasonableMaxScanTime = qlineedit_to_int(advsettings["reasonableMaxScanTime"])
		self.synthFreqResolution = qlineedit_to_int(advsettings["synthFreqResolution"])
		self.maxRFInputStd = qlineedit_to_float(advsettings["maxRFInputStd"])
		self.maxRFInputHi = qlineedit_to_float(advsettings["maxRFInputHi"])
		self.RFstepPow = qlineedit_to_float(advsettings["RFstepPow"])
		self.RFstepTime = qlineedit_to_float(advsettings["RFstepTime"])



	### lockin-related things
	def initLockin(self):
		"""
		Would sends various desirable initialization commands to the
		Lockin-In Amplifier upon initial connection.
		"""
		pass
	def LockinPhaseAuto(self, mouseEvent=False):
		"""
		Runs the auto-phase function on the lockin.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if (not self.check_UseLockin.isChecked()) or (not self.hasConnectedLockin):
			return
		# ensure that the scan is not active
		toPauseThenContinue = False
		if self.isScanning and not self.isPaused:
			toPauseThenContinue = True
			self.scanPause()
			time.sleep(self.waitBeforeScanRestart*5)
		curSetPhase = float(self.txt_LockinPhase.text())
		curActPhase = self.socketLockin.read_data(param='phase') * 180.0/3.14159
		newPhase = curSetPhase + curActPhase
		self.txt_LockinPhase.setText("%.2f" % newPhase)
		self.socketLockin.set_phase(float(self.txt_LockinPhase.text()), demod=1)
		self.socketLockin.set_phase(float(self.txt_LockinPhase.text()), demod=3)
		# finally, continue the scan if necessary
		if toPauseThenContinue:
			self.scanContinue()
	def LockinUpdatePhaseText(self):
		"""
		Updates the phase of the lockin, and the entry in the input field,
		based on the location of the slider.

		Note that unlike set/read buttons, the scan is stopped and not
		continued.
		"""
		if self.isScanning and not self.isPaused:
			self.scanPause()
			time.sleep(self.waitBeforeScanRestart*5)
		self.txt_LockinPhase.setText(str(self.slider_LockinPhase.value()))
		if self.check_UseLockin.isChecked() and self.hasConnectedLockin:
			self.socketLockin.set_phase(self.slider_LockinPhase.value(), demod=1)
			self.socketLockin.set_phase(self.slider_LockinPhase.value(), demod=3)
	
	def LockinSWTrigSet(self, mouseEvent=False):
		"""
		Initializes the SW Trigger of the MFLI.
		
		Note that many of the parameters are hard-coded here, but some can be
		tuned using the Lockin's 'advanced settings' dialog.
		"""
		if not self.hasConnectedLockin:
			log.warning("the lockin is not yet connected! connect to it and try again..")
			return
		if not self.check_LockinUseSWTrigInt.isChecked():
			log.warning("you have 'integrateLockinTrigger' disabled!")
			return
		# swap the data rates
		self.socketLockin.set_datarate(rate=self.lockinDataRateFull, demod=3)
		self.socketLockin.set_datarate(rate=self.lockinDataRateThrottled, demod=1)
		self.socketLockin.sync()
		# initiate the trigger
		if self.socketLockin.version[:2] == "19":
			trigger = self.socketLockin.daq.dataAcquisitionModule()
			trigger.set('device', self.socketLockin.device)
			# set trigger properties
			log.info("setting a SW trigger via %s" % self.lockinIntegrationTrigSource)
			triggernode = '/%s/demods/2/sample.%s' % (
				self.socketLockin.device,
				self.lockinIntegrationTrigSource)
			trigger.set('triggernode', triggernode)
			trigger.set('type', 6) # 6 = hardware trigger
			trigger.set('edge', 1) # 1 = rising
			trigger.set('count', 1) # how many triggers to save
			trigger.set('grid/mode', 4) # exact == no resampling of data.. 0 or none is no longer supported!
			# trigger.set('grid/repetitions', 1)
			trigger.set('bandwidth', 0.0) # low-pass filter (in Hz) applied to trigger
			# trigger.set('hysteresis', 0.01) # 
			# trigger.set('level', 0.1) # voltage level to throw the trigger
			trigger.set('refreshrate', 60) # note: this assumes ~20 Hz is upper limit of experiment
			trigger.set('holdoff/time', self.lockinIntegrationRecordTime*1.5) # time to sleep before next trigger (should exceed the duration)
			trigger.set('holdoff/count', 0) # number of triggers to skip
			trigger.set('preview', 1) # whether to allow reading incomplete triggers
			trigger.set('delay', self.lockinIntegrationTrigDelay) # delay time wrt trigger (can be negative)
			# trigger.set('duration', self.lockinIntegrationRecordTime) # length of time to record data
			demod_rate = self.socketLockin.daq.getDouble('/%s/demods/2/rate' % self.socketLockin.device)
			sample_count = int(demod_rate * self.lockinIntegrationRecordTime)
			trigger.set('grid/cols', sample_count)
			trigger.set('grid/rows', 1) # number of trigger events
			trigger.set('grid/overwrite', 1) # whether to overwrite the grid or make a new one
			trigger.set('historylength', 1) # number of entries kept in history
			if (self.check_DGAutoTrig.isChecked() and
				not self.check_LockinUseUnidirectionScan.isChecked()):
				trigger.set('endless', 0) # whether to enable endless triggering
			else:
				# trigger.set('clearhistory', 0) # whether to clear the running buffer/data history
				trigger.set('endless', 1)
			# start trigger and add to socket
			trigger.subscribe('/%s/demods/2/sample.x' % self.socketLockin.device)
		elif self.socketLockin.version[:2] == "18": # WARNING: daq module cannot keep up with rates above 6 Hz for v18.05 & v18.12
			trigger = self.socketLockin.daq.dataAcquisitionModule()
			#trigger.set('dataAcquisitionModule/enable', True)
			trigger.set('dataAcquisitionModule/device', self.socketLockin.device)
			# set trigger properties
			log.info("setting a SW trigger via %s" % self.lockinIntegrationTrigSource)
			triggernode = '/%s/demods/2/sample.%s' % (
				self.socketLockin.device,
				self.lockinIntegrationTrigSource)
			trigger.set('dataAcquisitionModule/triggernode', triggernode)
			trigger.set('dataAcquisitionModule/type', 6) # 6 = hardware trigger
			trigger.set('dataAcquisitionModule/edge', 1) # 1 = rising
			trigger.set('dataAcquisitionModule/count', 1) # how many triggers to save
			trigger.set('dataAcquisitionModule/grid/mode', 0)
			trigger.set('dataAcquisitionModule/grid/repetitions', 1)
			trigger.set('dataAcquisitionModule/bandwidth', 0.0)
			trigger.set('dataAcquisitionModule/hysteresis', 0.01)
			trigger.set('dataAcquisitionModule/level', 0.1) # voltage level to throw the trigger
			trigger.set('dataAcquisitionModule/refreshrate', 60) # note: this assumes ~20 Hz is upper limit of experiment
			trigger.set('dataAcquisitionModule/holdoff/time', self.lockinIntegrationRecordTime*1.5) # time to sleep before next trigger (should exceed the duration)
			trigger.set('dataAcquisitionModule/holdoff/count', 0) # number of triggers to skip
			trigger.set('dataAcquisitionModule/preview', 1) # whether to allow reading incomplete triggers
			trigger.set('dataAcquisitionModule/delay', self.lockinIntegrationTrigDelay) # delay time wrt trigger (can be negative)
			trigger.set('dataAcquisitionModule/duration', self.lockinIntegrationRecordTime) # length of time to record data
			demod_rate = self.socketLockin.daq.getDouble('/%s/demods/2/rate' % self.socketLockin.device)
			sample_count = int(demod_rate * self.lockinIntegrationRecordTime)
			trigger.set('dataAcquisitionModule/grid/cols', sample_count)
			trigger.set('dataAcquisitionModule/grid/rows', 1)
			trigger.set('dataAcquisitionModule/grid/overwrite', 1) # whether to overwrite the grid or make a new one
			trigger.set('dataAcquisitionModule/historylength', 1) # number of entries kept in history
			#trigger.set('dataAcquisitionModule/clearhistory', 1) # whether to clear the running buffer/data history
			if (self.check_DGAutoTrig.isChecked() and
				not self.check_LockinUseUnidirectionScan.isChecked()):
				trigger.set('dataAcquisitionModule/endless', 0) # whether to enable endless triggering
			else:
				trigger.set('dataAcquisitionModule/clearhistory', 0) # whether to clear the running buffer/data history
				trigger.set('dataAcquisitionModule/endless', 1)
			# start trigger and add to socket
			trigger.subscribe('/%s/demods/2/sample.x' % self.socketLockin.device)
		else: # v16.12: works at full rate EXCEPT when waiting for external trigger
			trigger = self.socketLockin.daq.record()
			trigger.set('trigger/device', self.socketLockin.device)
			# set trigger properties
			log.info("setting a SW trigger via %s" % self.lockinIntegrationTrigSource)
			triggernode = '/%s/demods/2/sample.%s' % (
				self.socketLockin.device,
				self.lockinIntegrationTrigSource)
			trigger.set('trigger/0/triggernode', triggernode)
			trigger.subscribe('/%s/demods/2/sample' % self.socketLockin.device)
			trigger.set('trigger/0/type', 6) # 6 = hardware trigger
			trigger.set('trigger/0/edge', 1) # 1 = rising
			trigger.set('trigger/0/count', 1) # how many triggers to save
			trigger.set('trigger/0/level', 0.5) # voltage level to throw the trigger
			### new
			trigger.set('trigger/0/grid/mode', 0) # off
			### finished with new grid tests
			trig_rate = float(self.txt_DGTriggerRate.text())
			trigger.set('trigger/0/holdoff/time', self.lockinIntegrationRecordTime*1.5) # time to sleep before next trigger (should exceed the duration)
			trigger.set('trigger/0/holdoff/count', 0) # number of triggers to skip
			trigger.set('trigger/0/delay', self.lockinIntegrationTrigDelay) # delay time wrt trigger (can be negative)
			trigger.set('trigger/0/duration', self.lockinIntegrationRecordTime) # length of time to record data
			trigger.set('trigger/0/retrigger', 0) # whether to re-arm trigger and append to same event
			trigger.set('trigger/buffersize', 2*self.lockinIntegrationRecordTime) # length of time allocated for the buffer
			trigger.set('trigger/historylength', 1) # number of entries kept in history
			if (self.check_DGAutoTrig.isChecked() and
				not self.check_LockinUseUnidirectionScan.isChecked()):
				trigger.set('trigger/endless', 0) # whether to enable endless triggering
			else:
				trigger.set('trigger/clearhistory', 0) # whether to clear the running buffer/data history
				trigger.set('trigger/endless', 1)
		self.socketLockin.sync(useDelay=True)
		# start trigger and add to socket
		trigger.execute()
		if not self.check_DGAutoTrig.isChecked() and self.check_UseDG.isChecked():
			self.socketDG.send_trigger() # prevents a problem later by initializing grid now
		self.socketLockin.trigger = trigger
		
		##########
		### run test measurement
		##########
		
		### NOTE: for v18.05
		#time.sleep(1.0)
		#finished = trigger.finished()
		#print("finished? %s" % finished)
		#if not finished:
		#	print("finished now? %s" % trigger.finished())
		#data = trigger.read(True)
		#target_path = '/dev3367/demods/2/sample.x'
		#print("data:")
		#for k,v in data.items():
		#	if not k == target_path:
		#		print("\t%s -> %s" % (k,v))
		#clockbase = self.socketLockin.getClockbase()
		#samples = data[target_path]
		#self.testsample = samples[-1]
		#print("\nthe most recent sample looks like:")
		#for k,v in self.testsample.items():
		#	print("\t%s -> %s" % (k,v))
		#print("\n"*5)
		#print("# samples: %s" % len(samples))
		#tot_seconds = (self.testsample['timestamp'][0][-1] - self.testsample['timestamp'][0][0])/clockbase
		#print("tot_seconds: %s" % tot_seconds)
		#print("the data contains samples with %s datapoints" % len(self.testsample['value'][0]))
		
		### NOTE: for v17.05 or v16.12
		#time.sleep(0.25)
		#finished = trigger.finished()
		#print "finished? %s" % finished
		#data = trigger.read(True)
		#target_path = '/dev3367/demods/2/sample'
		#print "data:"
		#for k,v in data.items():
		#	if not k == target_path:
		#		print "\t%s -> %s" % (k,v)
		#clockbase = self.socketLockin.getClockbase()
		#samples = data[target_path]
		#self.testsample = samples[-1]
		#print "\n"*5
		#print "# samples: %s" % len(samples)
		#tot_seconds = (samples[0]['timestamp'][-1] - samples[0]['timestamp'][0])/clockbase
		#print "the data contains samples with %s datapoints" % len(samples[0]['x'])
	
	def LockinSWTrigClear(self, mouseEvent=False):
		"""
		Clears/disables the SW Trigger of the MFLI.
		"""
		if not self.hasConnectedLockin:
			log.warning("the lockin is not yet connected! connect to it and try again..")
			return
		if self.socketLockin.trigger is None:
			log.warning("there is no lockin SW trigger!")
			return
		# stop trigger module thread and clear it
		self.socketLockin.trigger.clear()
		self.socketLockin.trigger = None
		# swap the data rates
		self.socketLockin.set_datarate(rate=self.lockinDataRateFull, demod=1)
		self.socketLockin.set_datarate(rate=self.lockinDataRateThrottled, demod=3)
	
	def LockinSetInputsHEB(self, mouseEvent=False):
		"""
		Sets up the signal input (Voltage Input 1) so that it is appropriate to
		the QMC bolometers:
		- Range: 3.0 V (i.e. its max)
		- Impedance: 50 Ω (i.e. scales the input down so it doesn't overload)
		"""
		self.socketLockin.set_input_range(voltage=3.0)
		self.socketLockin.set_input_impedance(impedance=50)
		self.socketLockin.sync()
	def LockinSetInputsZBD(self, mouseEvent=False):
		"""
		Sets up the signal input (Voltage Input 1) so that it is appropriate to
		the VDI ZBDs:
		- Range: 3.0 V (i.e. its max)
		- Impedance: 10 MΩ (i.e. the default)
		"""
		self.socketLockin.set_input_range(voltage=3.0)
		self.socketLockin.set_input_impedance(impedance=10e6)
		self.socketLockin.sync()

	def LockinSetValues(self, mouseEvent=False):
		"""
		Loops through all the inputs to the lockin, and sets their states
		within the instrument.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# check desired usage, its connection, and its inputs
		self.checkInputsLockin()
		if (not self.check_UseLockin.isChecked()) or (not self.hasConnectedLockin):
			return
		# ensure that the scan is not active
		toPauseThenContinue = False
		if self.isScanning and not self.isPaused:
			toPauseThenContinue = True
			self.scanPause()
			time.sleep(self.waitBeforeScanRestart*5)
		## set sensitivity
		#sens = self.lockinSensitivityList[self.combo_LockinSensitivity.currentIndex()]
		#self.socketLockin.set_sensitivity(sens)
		# set time constant
		tau = self.lockinTimeConstantList[self.combo_LockinTau.currentIndex()]
		self.socketLockin.set_time_constant(tau, demod=1)
		self.socketLockin.set_time_constant(tau, demod=3)
		sine_state = "off"
		if self.check_LockinSineFilter.isChecked(): sine_state = "on"
		self.socketLockin.set_sine_filter(sine_state, demod=1)
		self.socketLockin.set_sine_filter(sine_state, demod=3)
		# set harmonic
		self.socketLockin.set_harm(self.combo_LockinHarmonic.value(), demod=1)
		self.socketLockin.set_harm(self.combo_LockinHarmonic.value(), demod=3)
		# set phase
		if self.txt_LockinPhase.text():
			self.socketLockin.set_phase(float(self.txt_LockinPhase.text()), demod=1)
			self.socketLockin.set_phase(float(self.txt_LockinPhase.text()), demod=3)
		# set trigger
		source = str(self.combo_LockinTriggerSrc.currentText())
		mode = str(self.combo_LockinTriggerMode.currentText())
		self.socketLockin.set_trigger(source=source, mode=mode, demod=1)
		# sync settings
		self.socketLockin.sync(useDelay=True)
		# finally, continue the scan if necessary
		if toPauseThenContinue:
			self.scanContinue()

	def LockinReadValues(self, mouseEvent=False):
		"""
		Loops through all the inputs to the lockin, and reads their values
		in based on the current state of the instrument.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if (not self.check_UseLockin.isChecked()) or (not self.hasConnectedLockin):
			return
		# ensure that the scan is not active
		toPauseThenContinue = False
		if self.isScanning and not self.isPaused:
			toPauseThenContinue = True
			self.scanPause()
			time.sleep(self.waitBeforeScanRestart*5)
		## set sensitivity
		#sens = self.socketLockin.get_sensitivity()
		#sens_index = self.lockinSensitivityList.index(sens)
		#self.combo_LockinSensitivity.setCurrentIndex(sens_index)
		# set time constant
		tau = self.socketLockin.get_time_constant()
		log.info(tau)
		#tau_index = self.lockinTimeConstantList.index(tau)
		sine_state = self.socketLockin.get_sine_filter()
		sine_states = {"on":True, "off":False}
		self.check_LockinSineFilter.setChecked(sine_states[sine_state])
		#self.combo_LockinTau.setCurrentIndex(tau_index)
		# set harmonic
		self.combo_LockinHarmonic.setValue(self.socketLockin.get_harm())
		# set phase
		self.txt_LockinPhase.setText("%.2f" % self.socketLockin.get_phase())
		# set trigger
		source, mode = self.socketLockin.get_trigger()
		self.combo_LockinTriggerSrc.setCurrentIndex(self.lockinTriggerSources.index(source))
		self.combo_LockinTriggerMode.setCurrentIndex(self.lockinTriggerModes.index(mode))
		# finally, continue the scan if necessary
		if toPauseThenContinue:
			self.scanContinue()

	def chooseAdvSettingsLockin(self, mouseEvent=False):
		"""
		Loads the current 'Advanced Settings' for the Lockin-In Amplifier
		into a ScrollableSettingsWindow

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		advSettingsWindow = ScrollableSettingsWindow(self, self.updateAdvSettingsLockin)
		advSettingsWindow.addRow(
			"ethernetIPLockin", "Default ethernet IP for the lockin",
			self.ethernetIPLockin, "(none)")
		hover = "I don't think this is used with the MFLI lockin.."
		advSettingsWindow.addRow(
			"waitForAutoPhase", "Time to allow the LIA to Auto-Phase",
			self.waitForAutoPhase, "s", hover=hover)
		advSettingsWindow.addRow(
			"maxLockinFreq", "Highest reference frequency allowed for harm=1",
			self.maxLockinFreq, "Hz")
		advSettingsWindow.addRow(
			"lockinDataRateFull", "Full speed to use for the active demodulator.",
			self.lockinDataRateFull, "Hz")
		advSettingsWindow.addRow(
			"lockinDataRateThrottled", "Throttled speed to use for the inactive demodulator.",
			self.lockinDataRateThrottled, "Hz")
		hover = "Options are 'TrigIn1' or 'TrigIn2' (default: TrigIn2)."
		advSettingsWindow.addRow(
			"lockinIntegrationTrigSource", "TTL signal that triggers the gated integration.",
			self.lockinIntegrationTrigSource, "(none)", hover=hover)
		advSettingsWindow.addRow(
			"lockinIntegrationTrigDelay", "Delay before/after TTL that throws the SW trigger.",
			self.lockinIntegrationTrigDelay, "s", hover="The delay can also be negative..")
		hover = "This is controls how much of the continuous demodulated signal\n"
		hover += "that is recorded. The gated integration window must fall within\n"
		hover += "this time frame (i.e. you would integrate the signal after the\n"
		hover += "and before the total time runs out)."
		advSettingsWindow.addRow(
			"lockinIntegrationRecordTime", "Total recording time for the SW trigger signal.",
			self.lockinIntegrationRecordTime, "s", hover=hover)
		if advSettingsWindow.exec_():
			pass
	def updateAdvSettingsLockin(self, advsettings):
		"""
		Updates 'Advanced Settings' for the Lockin-In Amplifier from the
		ScrollableSettingsWindow

		:param advsettings: the dictionary containing all the new parameters from the ScrollableSettingsWindow
		:type advsettings: dict
		"""
		self.ethernetIPLockin = qlineedit_to_str(advsettings["ethernetIPLockin"])
		self.waitForAutoPhase = qlineedit_to_float(advsettings["waitForAutoPhase"])
		self.maxLockinFreq = qlineedit_to_float(advsettings["maxLockinFreq"])
		self.lockinDataRateFull = qlineedit_to_float(advsettings["lockinDataRateFull"])
		self.lockinDataRateThrottled = qlineedit_to_float(advsettings["lockinDataRateThrottled"])
		self.lockinIntegrationTrigSource = qlineedit_to_str(advsettings["lockinIntegrationTrigSource"])
		self.lockinIntegrationTrigDelay = qlineedit_to_float(advsettings["lockinIntegrationTrigDelay"])
		self.lockinIntegrationRecordTime = qlineedit_to_float(advsettings["lockinIntegrationRecordTime"])




	### batch mode
	def batchAddEntry(self, mouseEvent=False):
		"""
		Adds an empty row for inputting new parameters for a batch scan.

		Note that this makes use of the table widget, but probably it is
		preferable to switch to the technique implemented in the FF tab
		of QtFit.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		lastEntry = self.batchGetLastEntry()
		currentRowCount = self.table_Batch.rowCount()
		self.table_Batch.insertRow(currentRowCount)
		for c in range(0, self.table_Batch.columnCount()-1): # -1 to skip the delete button
			if lastEntry[c]:
				newItem = QtGui.QTableWidgetItem(lastEntry[c])
				self.table_Batch.setItem(currentRowCount, c, newItem)
		btn = QtGui.QPushButton(self.table_Batch)
		btn.setText("remove")
		btn.clicked.connect(partial(self.batchRemoveRow, widget=btn))
		self.table_Batch.setCellWidget(currentRowCount, self.table_Batch.columnCount()-1, btn)
	def batchGetEntries(self):
		"""
		Processes the contents of the table of batch parameters.
		"""
		tableData = []
		for r in range(0, self.table_Batch.rowCount()):
			row = []
			for c in range(0, self.table_Batch.columnCount()):
				entry = self.table_Batch.item(r,c)
				if entry:
					entry = str(entry.text())
				else:
					entry = ""
				row.append(entry)
			tableData.append(row)
		return tableData
	def batchGetEntry(self, r):
		"""
		Processes the contents of the table of batch parameters.

		:param r: which row number to process
		:type r: int

		:returns: the contents of the row of interest
		:rtype: list
		"""
		if r > self.table_Batch.rowCount()-1:
			return None
		row = []
		for c in range(0, self.table_Batch.columnCount()):
			entry = self.table_Batch.item(r,c)
			if entry:
				entry = str(entry.text())
			else:
				entry = ""
			row.append(entry)
		return row
	def batchGetLastEntry(self):
		"""
		Processes the contents of the table of batch parameters.
		"""
		r = self.table_Batch.rowCount()-1
		return self.batchGetEntry(r)
	def batchHighlightEntry(self, r, color="green"):
		"""
		Highlights a row with the color green, which designates that
		this batch entry has been finished

		:param r: which row number to highlight
		:type r: int
		"""
		if r > self.table_Batch.rowCount()-1:
			return
		for c in range(0, self.table_Batch.columnCount()):
			try:
				if not 'setBackgroundColor' in dir(self.table_Batch.item(r,c)):
					self.table_Batch.item(r,c).setBackgroundColor = self.table_Batch.item(r,c).setBackground
				self.table_Batch.item(r,c).setBackgroundColor(QtGui.QColor(color))
			except AttributeError:
				newItem = QtGui.QTableWidgetItem("")
				if not 'setBackgroundColor' in dir(newItem):
					newItem.setBackgroundColor = newItem.setBackground
				newItem.setBackgroundColor(QtGui.QColor(color))
				self.table_Batch.setItem(r, c, newItem)
	def batchClearHighlights(self):
		"""
		Highlights a row with the color green, which designates that
		this batch entry has been finished

		:param r: which row number to highlight
		:type r: int
		"""
		for r in range(self.table_Batch.rowCount()):
			for c in range(0, self.table_Batch.columnCount()):
				try:
					if not 'setBackgroundColor' in dir(self.table_Batch.item(r,c)):
						self.table_Batch.item(r,c).setBackgroundColor = self.table_Batch.item(r,c).setBackground
					self.table_Batch.item(r,c).setBackgroundColor(QtGui.QColor("white"))
				except AttributeError:
					newItem = QtGui.QTableWidgetItem("")
					if not 'setBackgroundColor' in dir(newItem):
						newItem.setBackgroundColor = newItem.setBackground
					newItem.setBackgroundColor(QtGui.QColor("white"))
					self.table_Batch.setItem(r, c, newItem)
	def batchClearTable(self, mouseEvent=False):
		"""
		Clears the table of batch parameters.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		self.batchStop() # stop the current batch
		self.table_Batch.clear()
		self.table_Batch.setRowCount(1)
		self.table_Batch.setColumnCount(7)
		headerLabels = ["Freq. Center", "Freq. Span", "Freq. Step", "Rf Pow.", "FM Width", "# of Iterations", "Comment", ""]
		self.table_Batch.setHorizontalHeaderLabels(headerLabels)
	def batchRemoveRow(self, inputEvent=False, widget=None):
		"""
		Simply removes a row from the table.
		
		:param widget: the widget that called this function (typically a QtGui.QPushButton)
		:type widget: QtGui.QWidget
		"""
		if (not inputEvent) and (not widget):
			return
		for r in range(0, self.table_Batch.rowCount()):
			if self.table_Batch.cellWidget(r, self.table_Batch.columnCount()-1) == widget:
				self.table_Batch.removeRow(r)
				break

	def batchStart(self, mouseEvent=False):
		"""
		Begins a batch scan, which involves predefining certain internal
		variables, and finally invoking a new thread that loops through
		each entry of the table and starting the scan.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		log.info("beginning batch scans")
		self.batchClearHighlights()
		# prompt for title/comment for the whole job
		dt = datetime.datetime.now()
		saveDialog = TitleCommentDialog(self)
		if not saveDialog.exec_():
			return
		else:
			saveResponse = saveDialog.getValues()
			batchTitle = saveResponse["title"].replace(' ', '_')
			batchComment = saveResponse["comment"]
		if batchTitle=="":
			batchTitle = "%s" % str(dt)[:-4].replace(':', '-').replace(' ', '_')
		# do mock loop through settings to check their inputs
		currentBatchScan = 0
		for r in range(0, self.table_Batch.rowCount()):
			# reset things
			currentBatchScan = r + 1
			newScan = self.batchGetEntry(r)
			if not newScan:
				break
			log.info("checking batch scan #%s (%s)" % (currentBatchScan, newScan))
			self.txt_SynthEZFreqCenter.setText(newScan[0]) # <- may not be thread-safe
			self.txt_SynthEZFreqSpan.setText(newScan[1]) # <- may not be thread-safe
			self.SynthEZFreqCenterSet() # <- may not be thread-safe
			self.txt_SynthFreqStep.setText(newScan[2]) # <- may not be thread-safe
			self.combo_SynthPower.setValue(float(newScan[3])) # <- may not be thread-safe
			self.txt_SynthFMWidth.setText(newScan[4]) # <- may not be thread-safe
			try:
				self.checkInputs()
			except:
				self.batchHighlightEntry(r, "red") # <- may not be thread-safe
				log.exception("there was a problem with a batch entry...")
				raise
		# save the job's comment to file
		saveDir = "%s/%s" % (
			str(self.txt_SpecOut.text()),
			str(datetime.date(dt.year, dt.month, dt.day)))
		saveDir = os.path.expanduser(saveDir)
		if not os.path.exists(saveDir): os.makedirs(saveDir)
		descriptionFilename = "%s/BATCH_%s_DESCRIPTION.txt" % (saveDir, batchTitle)
		fileHandle = codecs.open(descriptionFilename, 'w', encoding='utf-8')
		fileHandle.write('%s' % batchComment)
		fileHandle.close()
		# initialize batch loop
		self.TabWidget.setCurrentWidget(self.tab_FreqScan)
		self.isBatchRunning = True
		self.batchLoopThread = genericThread(partial(self.batchRunLoop, batchTitle=batchTitle, batchComment=batchComment))
		self.batchLoopThread.start()
	def batchStop(self, mouseEvent=False):
		"""
		Stops a batch scan by setting the flag self.isBatchRunning, which
		is continuously checked by the daughter thread

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		self.isBatchRunning = False

	def batchRunLoop(self, batchTitle="", batchComment=""):
		"""
		Provides the continuous loop for running a batch scan, which
		basically consists of a list of parameters to use for a series
		of predefined scans.

		:param batchTitle: (optional) the title of the batch scan
		:param batchComment: (optional) a comment that precedes all the invidual comments
		:type batchTitle: str
		:type batchComment: str
		"""
		currentBatchScan = 0
		while self.isBatchRunning:
			# reset things
			currentBatchScan += 1
			self.isBatchReadyForNext = False
			# process new batch entry
			newScan = self.batchGetEntry(currentBatchScan-1)
			if not newScan:
				break
			log.info("beginning batch scan #%s (%s)" % (currentBatchScan, newScan))
			self.txt_SynthEZFreqCenter.setText(newScan[0]) # <- may not be thread-safe
			self.txt_SynthEZFreqSpan.setText(newScan[1]) # <- may not be thread-safe
			self.SynthEZFreqCenterSet() # <- may not be thread-safe
			self.txt_SynthFreqStep.setText(newScan[2]) # <- may not be thread-safe
			if self.check_UseSynth.isChecked():
				self.stepSynthPower(float(newScan[3])) # <- may not be thread-safe
			self.txt_SynthFMWidth.setText(newScan[4]) # <- may not be thread-safe
			iterLimit = int(newScan[5])
			scanTitle = "BATCH_%s_scan%03d" % (batchTitle, currentBatchScan)
			scanComment = "%s\n%s" % (batchComment, newScan[6])
			self.signalScanStart.emit(iterLimit, scanTitle, scanComment)
			# waiting for the next one
			while not self.isBatchReadyForNext and self.isBatchRunning:
				time.sleep(0.5)
			if self.scanFinished:
				self.batchHighlightEntry(currentBatchScan-1) # <- may not be thread-safe
			else:
				self.batchHighlightEntry(currentBatchScan-1, "red") # <- may not be thread-safe
		msg = "batch scans finished/stopped"
		log.info(msg)
		self.signalShowMessage.emit("info", ["Batch Scan", msg])
		self.isBatchRunning = False # <- may not be thread-safe


	### input checks
	def checkInputs(self, mouseEvent=False):
		"""
		Provides a wrapper to call the individual sanity checks for
		each instrument.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		self.checkInputsDG()
		self.checkInputsMFC()
		self.checkInputsSynth()
		self.checkInputsLockin()
	def checkInputsDG(self):
		"""
		Defines the sanity checks for the pulse/delay generator inputs.
		"""
		# check that the last (slowest) edge is not overlapping with a new pulse train
		trig_rate = float(self.txt_DGTriggerRate.text())
		trig_period = 1/trig_rate
		lastEdge = 0.0
		for i in ["Valve", "LockinSingle", "LockinInt", "LockinBase", "HV", "DG4"]:
			plotRegion = vars(self)["pulsePlotRegion_%s" % i]
			lastEdge = max(lastEdge, plotRegion.getRegion()[-1])
		if lastEdge > trig_period:
			msg = "You have one of the pulse windows overlapping with"
			msg += " the next train of pulses! Either reduce the trigger"
			msg += " rate, or adjust the pulse windows."
			self.showInputError(msg)
	def checkInputsMFC(self):
		"""
		Defines the sanity checks for the MFC inputs.
		"""
		for i in range(1,5):
			channel = i
			if self.MFCisReady(channel=channel):
				cb_range = getattr(self, "combo_MFC%sRange" % channel)
				txt_FS = getattr(self, "txt_MFC%sFSabs" % channel)
				MFCrange = float(cb_range.currentText().split(' ')[0])
				flowEntry = txt_FS.text()
				cb_cf = getattr(self, "combo_MFC%sGas" % channel)
				gas = str(cb_cf.currentText())
				gascf = self.MFCgasproperties[gas]["CF"]
				# check that it can be interpreted as a floating point
				if flowEntry:
					try:
						float(flowEntry)
					except ValueError:
						msg = "Could not interpret the flow rate for MFC channel %s." % channel
						self.showInputError(msg)
				# check against lower/upper bounds
				if flowEntry and (float(flowEntry) < 0):
					msg = "You appear to be requesting a negative flow rate for MFC channel %s." % channel
					self.showInputError(msg)
				elif flowEntry and (float(flowEntry) > MFCrange*gascf):
					msg = "You appear to be requesting an excessive flow rate for MFC channel %s." % channel
					self.showInputError(msg)
	def checkInputsSynth(self):
		"""
		Defines the sanity checks for the synthesizer inputs.
		"""
		freqStart = self.txt_SynthFreqStart.text()
		freqEnd = self.txt_SynthFreqEnd.text()
		freqStep = self.txt_SynthFreqStep.text()
		freqDelay = self.txt_SynthDelay.text()
		synthMultFactor = self.txt_SynthMultFactor.text()
		modtype = self.slider_SynthMod.value()
		amFreq = self.txt_SynthAMFreq.text()
		fmFreq = self.txt_SynthFMFreq.text()
		fmWidth = self.txt_SynthFMWidth.text()
		# check the validity of the multiplication factor
		if not synthMultFactor:
			msg = "You are missing an entry for multiplication factor."
			self.showInputError(msg)
		try:
			int(synthMultFactor)
		except ValueError:
			msg = "The multiplication factor could not be interpreted as an integer."
			self.showInputError(msg)
		else:
			synthMultFactor = int(synthMultFactor)
		# check the validity of the frequency range
		if freqStart and freqEnd and freqStep:
			# first make sure they look like floats
			try:
				float(freqStart)
				float(freqEnd)
				float(freqStep)
			except ValueError:
				msg = "One of the inputs for the frequencies does not look like a valid number."
				self.showInputError(msg)
			else:
				freqStart = float(freqStart)
				freqEnd = float(freqEnd)
				freqStep = float(freqStep)
			# check that freqStart < freqEnd
			if (freqStart >= freqEnd):
				msg = "The starting frequency must be smaller than the ending frequency."
				self.showInputError(msg)
			# make sure the step is not too large
			freqRange = freqEnd - freqStart
			if freqStep > freqRange:
				msg = "You are requesting an excessively large frequency step wrt the range."
				self.showInputError(msg)
			freqList = list(np.arange(freqStart, freqEnd+freqStep, freqStep))
			# check the resolution against the multiplication factor
			synthFreqList = []
			actualFreqList = []
			effectiveFreqList = []
			showFreqResPrompt = False
			for gui_f in freqList[:10]:
				synth_f = gui_f/float(synthMultFactor) * 1e6
				synth_f = '%.{0}f'.format(self.synthFreqResolution) % synth_f
				fin_f = float(synth_f)*synthMultFactor
				fin_f = '%.{0}f'.format(self.synthFreqResolution) % fin_f
				eff_f = '%.{0}f'.format(self.synthFreqResolution) % float(fin_f)
				eff_f = float(eff_f)
				synthFreqList.append(synth_f)
				actualFreqList.append(fin_f)
				effectiveFreqList.append(eff_f)
				freqsMatch = ('%.0f' % float(gui_f*1e6)) == ('%.0f' % eff_f)
				if (not freqsMatch) and (not showFreqResPrompt):
					showFreqResPrompt = True
			if showFreqResPrompt and not self.isBatchRunning:
				msg = """It looks like you are inputing an extreme
				combination of multiplication and frequency resolution.
				The synthesizer can work with a resolution of 0.001 Hz,
				but the currently combination of multiplication
				factor and frequency step result in an inexact match
				between the expected frequency and the actual frequency
				used with the synthesizer."""
				final = """If you like, you can view the first 10
				entries of the various rest frequencies."""
				details = "   requested:    synth freq   ->     final freq   ->   effective\n"
				for i,gui_f in enumerate(freqList[:10]):
					details += ("%.0f: %s -> %s -> %.0f\n" % (gui_f*1e6, synthFreqList[i], actualFreqList[i], effectiveFreqList[i]))
				abort = "Ridiculous frequency resolution."
				self.showWarning(msg, msgFinal=final, msgDetails=details, msgAbort=abort)
			# check against the tunable range of the device
			if self.check_UseSynth.isChecked():
				minFreq = self.socketSynth.get_min_frequency(unit="MHz")
				maxFreq = self.socketSynth.get_max_frequency(unit="MHz")
				if freqStart/float(synthMultFactor) < minFreq:
					msg = "You are trying to tune the synth to a frequency "
					msg += "below its tunable range (%s < %s MHz)" % (
						freqStart/float(synthMultFactor), minFreq)
					self.showInputError(msg)
				if freqEnd/float(synthMultFactor) > maxFreq:
					msg = "You are trying to tune the synth to a frequency "
					msg += "above its tunable range (%s > %s MHz)" % (
						freqEnd/float(synthMultFactor), maxFreq)
					self.showInputError(msg)
		# frequency vs band specs
		isManualMultiplierBand = self.combo_AMCband.currentText() == "(manual)"
		isManualMultiplierMode = self.combo_AMCmode.currentText() == "(manual)"
		if (not isManualMultiplierBand) and (not isManualMultiplierMode):
			currentBand = str(self.combo_AMCband.currentText())
			currentMode = str(self.combo_AMCmode.currentText())
			lowerlimit = self.AMCBandSpecs[currentBand]["Range"][0]
			upperlimit = self.AMCBandSpecs[currentBand]["Range"][1]
			# check that multiplication factor matches self.AMCBandSpecs[band][mode]
			if self.txt_SynthMultFactor.text():
				multFactor = int(self.txt_SynthMultFactor.text())
			else:
				multFactor = 0
			if (not multFactor == self.AMCBandSpecs[currentBand][currentMode]):
				msg = "The multiplication you have selected does not match"
				msg += " with the selected multiplier chain."
				msg += "\n\nThe multiplier should be "
				msg += str(self.AMCBandSpecs[currentBand][currentMode])
				self.showInputError(msg)
			# check that the lower frequency limit > self.AMCBandSpecs[band]["Range"][0]
			if (float(self.txt_SynthFreqStart.text())/1e3 < lowerlimit) and not self.isBatchRunning:
				msg = "The starting frequency you have selected does not match"
				msg += " the range of the selected multiplier chain."
				msg += "\n\nThe range should be " + str(lowerlimit) + " to " + str(upperlimit) + " GHz"
				self.showWarning(msg)
			# check that the upper frequency limit < self.AMCBandSpecs[band]["Range"][1]
			if (float(self.txt_SynthFreqEnd.text())/1e3 > upperlimit) and not self.isBatchRunning:
				msg = "The ending frequency you have selected does not match"
				msg += " the range of the selected multiplier chain."
				msg += "\n\nThe range should be " + str(lowerlimit) + " to " + str(upperlimit) + " GHz"
				self.showWarning(msg)
		# check the validity of the step delay
		if not freqDelay:
			msg = "You are missing an entry for the step delay."
			self.showInputError(msg)
		try:
			float(freqDelay)
		except ValueError:
			msg = "The step delay could not be interpreted as a number."
			self.showInputError(msg)
		else:
			freqDelay = float(freqDelay)
		# check the length of the scan (datapoints + memory + time)
		numDataPoints = int((freqEnd-freqStart)/float(freqStep))
		if (numDataPoints > self.reasonableMaxFreqPoints) and not self.isBatchRunning:
			from sys import getsizeof
			memSize = getsizeof(freqStart)*5*numDataPoints
			memSizeSI = siScale(memSize, minVal=1e-25, allowUnicode=True)
			memSize = '%s %sB' % (memSize*memSizeSI[0], memSizeSI[1])
			diskSpace = getsizeof("123456.7890 +12345.67\n")*numDataPoints
			diskSpaceSI = siScale(diskSpace, minVal=1e-25, allowUnicode=True)
			diskSpace = '%s %sB' % (diskSpace*diskSpaceSI[0], diskSpaceSI[1])
			msg = "You are requesting %g frequency point spacings! " % numDataPoints
			msg += "This scan would take up approximately %s of memory" % memSize
			msg += ", and at least %s of disk space!" % diskSpace
			prompt = "Are you sure you want to do this?"
			self.showWarning(msg, msgFinal=prompt)
		if self.check_LockinUseSWTrigInt.isChecked():
			scanTime = numDataPoints / float(str(self.txt_DGTriggerRate.text()))
		else:
			scanTime = numDataPoints * freqDelay/1000.0/60.0
			scanTime += numDataPoints*0.5/1000.0/60.0 # account for a 1/2 ms delay per step
		if (scanTime > self.reasonableMaxScanTime) and not self.isBatchRunning:
			msg = "You are requesting a scan that takes approx. %.0f" % float(scanTime)
			msg += " minutes per sweep! This is longer than the 'reasonable'"
			msg += " length in time of %s minutes." % (self.reasonableMaxScanTime)
			prompt = "Are you sure you want to do this?"
			self.showWarning(msg, msgFinal=prompt)
		# RF power
		if self.combo_AMCmode.currentText() == "High":
			maxRFInput = self.maxRFInputHi
		elif str(self.combo_AMCband.currentText()) == "6.5":
			maxRFInput = 15.0 # TODO: eventually update with actual limit
		else:
			maxRFInput = self.maxRFInputStd
		if self.combo_SynthPower.value() > maxRFInput:
			msg = "Are you nuts?!"
			msg += "\n\nThe current hardware does not accept input above %g dBm!"
			self.showInputError(msg % maxRFInput)
		# modulation
		if modtype:
			if modtype == -1: # check that the AM frequency exists and is a number
				if not amFreq:
					self.showInputError("You have a blank entry for the AM frequency setting.")
				try:
					float(amFreq)
				except ValueError:
					self.showInputError("The AM frequency does not look like a number.")
			elif modtype == 1: # check that the FM settings exist and are numbers
				if (not fmFreq) or (not fmWidth):
					self.showInputError("You have a blank entry among the FM settings.")
				try:
					float(fmFreq)
					float(fmWidth)
				except ValueError:
					self.showInputError("One of FM settings does not look like a number.")
	def checkInputsLockin(self):
		"""
		Defines the sanity checks for the lock-in amplifier inputs.
		"""
		# ensure that the scan is not active
		toPauseThenContinue = False
		if self.isScanning and not self.isPaused: # because it reads the current reference frequency..
			toPauseThenContinue = True
			self.scanPause()
			time.sleep(self.waitBeforeScanRestart*5)
		# check the harmonic against the reference frequency
		harm = int(self.combo_LockinHarmonic.value())
		hasGoodLockinStatus = self.check_UseLockin.isChecked() and self.hasConnectedLockin
		if harm and hasGoodLockinStatus:
			refFreq = self.socketLockin.get_freq()
			if float(refFreq*harm) > self.maxLockinFreq:
				msg = "You cannot use this detection harmonic at this"
				msg += " given reference frequency! The maximum allowed"
				msg += " ref. freq. is (102/n kHz), where n is the harmonic."
				self.showInputError(msg)
		if self.check_LockinUseSWTrigInt.isChecked():
			# check that the lockin trigger is properly set up
			if not self.check_UseLockin.isChecked():
				hasTrigger = False
				self.check_LockinUseSWTrigInt.setChecked(False)
			else:
				hasTrigger = 'trigger' in vars(self.socketLockin)
				if (((not hasTrigger) or (hasTrigger and self.socketLockin.trigger is None)) and
					not self.isBatchRunning):
					msg = """You have the checkbox set to use the SW Trigger to
					integrate the signal from the MFLI over a period of time, but
					the trigger doesn't seem to be set up yet. You choose to ignore
					the checkbox and only make a single measurement per pulse, or
					you can abort the current scan and go back to the lockin tab
					to set the trigger."""
					final = "How would you like to proceed?"
					self.showWarning(msg, msgFinal=final)
					self.check_LockinUseSWTrigInt.setChecked(False)
			# warn if the scan will probably cause hysteresis in the frequency axis
			if ((not self.check_LockinUseUnidirectionScan.isChecked() and
				float(self.txt_DGTriggerRate.text()) > 5) and not self.isBatchRunning):
				msg = """You have the checkbox set to use the SW Trigger and
				to sweep both up and down across the frequency axis, but the
				stepping frequency is above ~5 Hz, and this will result in
				hysteresis across the frequency axis (i.e. the spectrum will
				be delayed). Your lines will be broadened and possibly even
				totally messed up if they are narrow enough and you are scanning
				too quickly."""
				final = "How would you like to proceed?"
				self.showWarning(msg, msgFinal=final)
		# finally, continue the scan if necessary
		if toPauseThenContinue:
			self.scanContinue()




	### scan-related things
	def scanStart(self, mouseEvent=False, iterLimit=0, scanTitle="", scanComment=""):
		"""
		Defines the frequencies to loop through during the scan, and
		initiates the scanning itself.

		Note that the current inputs for the synthesizer and lockin are
		explicitly set here, regardless of whether you had already done so!

		Also, the optional arguments are all used to automatically stop/save
		the scan after a defined number of sweeps, thus enabling all the
		functionality involved with a batch scan. If these arguments are
		not set, then the scan continues indefinitely, until it is manually
		stopped through the interface.

		:param mouseEvent: (optional) the mouse event from a click
		:param iterLimit: (optional) the number of iterations to scan, before stopping/saving
		:param scanTitle: (optional) the title of the scan to use
		:param scanComment: (optional) a series of comments describing the scan
		:type mouseEvent: QtGui.QMouseEvent
		:type iterLimit: int
		:type scanTitle: str
		:type scanComment: str
		"""
		# firstly, don't begin a simultaneous scans (yes, this was possible)
		if self.isScanning or self.isPaused:
			return
		self.scanFinished = False

		# check the instrument connections and set the values
		self.checkInstruments()
		self.DGSetValues()
		self.SynthSetValues()
		self.LockinSetValues()
		if self.check_UseDG.isChecked() and not self.check_DGAutoTrig.isChecked():
			self.socketDG.set_trigger_source(5)

		# define the frequency loops
		hasBlankMult = not self.txt_SynthMultFactor.text()
		hasBlankFreq = (not self.txt_SynthFreqStart.text()) or (not self.txt_SynthFreqEnd.text())
		hasBlankStep = not self.txt_SynthFreqStep.text()
		if hasBlankMult or hasBlankFreq or hasBlankStep:
			self.showInputError("You have a blank entry among the frequency settings!")
		freqStart = self.txt_SynthFreqStart.value()
		freqEnd = self.txt_SynthFreqEnd.value()
		freqStep = self.txt_SynthFreqStep.value()
		self.freqList = list(np.arange(freqStart, freqEnd+freqStep, freqStep))
		if self.check_SynthSkipCenterFreq.isChecked():
			centerFreqWidth = self.txt_SynthSkipCenterFreq.value()
			if centerFreqWidth > (freqEnd-freqStart):
				self.showInputError("The central frequency window to skip is larger than the scan!")
			centerFreq = np.mean(self.freqList)
			self.freqList = np.array(self.freqList)
			lowerIdx = self.freqList < (centerFreq - centerFreqWidth/2.0)
			upperIdx = self.freqList > (centerFreq + centerFreqWidth/2.0)
			self.freqList = list(self.freqList[lowerIdx]) + list(self.freqList[upperIdx])
			# get rid of dangling decimals
			precision = getStringPrecision(freqStep)
			for i,f in enumerate(self.freqList):
				self.freqList[i] = float(precision.format(f))
		synthMultFactor = int(self.txt_SynthMultFactor.text())
		self.synthFreqList = []
		for gui_f in self.freqList:
			synth_f = gui_f/float(synthMultFactor)*1e6
			synth_f = '%.{0}f'.format(self.synthFreqResolution) % synth_f
			self.synthFreqList.append(synth_f)
		self.freqDelay = float(self.txt_SynthDelay.text())/1000.0
		try:
			self.socketSynth.set_frequency(float(self.synthFreqList[0]), unit='Hz')
			time.sleep(self.freqDelay)
		except AttributeError:
			pass

		# initialize the active lists of y-values
		self.scanYvalsCur = []
		self.scanYvalsAvg = []
		self.scanYvalsIters = []
		for f in self.freqList:
			self.scanYvalsCur.append(0)
			self.scanYvalsAvg.append(0)
			self.scanYvalsIters.append(0)

		# set/reset the scan info
		self.txt_ScanStatus.setText("Scanning")
		self.lcd_ScanIterations.display(0)
		self.lcd_ScanFreqPnts.display(len(self.freqList))
		self.txt_ScanTime.setText("")
		self.timeScanStart = datetime.datetime.now()
		self.timeScanStop = 0
		self.timeScanPaused = datetime.timedelta(seconds=0)

		# redefine the precision-limited frequency format
		freqStep = float(self.txt_SynthFreqStep.text())
		freqStep = str(freqStep).rstrip('.0')
		if ('.' in freqStep):
			freqPrecision = len(freqStep.split('.')[1])
		else:
			freqPrecision = 0
		self.freqFormattedPrecision = '%.{0}f'.format(freqPrecision)

		# update the scanning status
		self.isScanning = True

		# connect the frequency looper to a daughter thread & start it
		self.scanThread = genericThread(partial(self.scanRunFreqLoop, iterLimit=iterLimit, scanTitle=scanTitle, scanComment=scanComment))
		self.scanThread.start()

		# star the timer to update the plot
		if len(self.freqList) < self.reasonableMaxFreqPoints:
			#self.timerScanPlotUpdate.start(self.updateperiodPlotUpdateFast)
			self.timerScanUpdatePlot = genericThreadContinuous(self.scanPlotUpdate, self.updateperiodPlotUpdateFast)
			self.timerScanUpdatePlot.start()
		elif len(self.freqList) > 10*self.reasonableMaxFreqPoints:
			#self.timerScanPlotUpdate.start(self.updateperiodPlotUpdateSlow*10)
			self.timerScanUpdatePlot = genericThreadContinuous(self.scanPlotUpdate, self.updateperiodPlotUpdateSlow*10)
			self.timerScanUpdatePlot.start()
		else:
			#self.timerScanPlotUpdate.start(self.updateperiodPlotUpdateSlow)
			self.timerScanUpdatePlot = genericThreadContinuous(self.scanPlotUpdate, self.updateperiodPlotUpdateSlow)
			self.timerScanUpdatePlot.start()
	@QtCore.pyqtSlot(int, str, str)
	def scanStartByScanThread(self, iterLimit, scanTitle, scanComment):
		"""
		Provides functionality to the signal that is emitted to begin the
		scan.
		
		Note that this is meant to be called internally from scanStart()
		
		:param iterLimit: (optional) the number of scan sweeps to stop at
		:param scanTitle: (optional) the title of the scan (prompts if non-existent)
		:param scanComment: (optional) the title of the scan (prompts if non-existent)
		:type iterLimit: int
		:type scanTitle: str
		:type scanComment: str
		"""
		self.scanStart(iterLimit=iterLimit, scanTitle=scanTitle, scanComment=scanComment)
	def scanRunFreqLoop(self, iterLimit=0, scanTitle="", scanComment=""):
		"""
		Defines a normal scan loop, and pushes the newly-read values to
		the scanUpdateData function.

		:param mouseEvent: (optional) the mouse event from a click
		:param iterLimit: (optional) the number of iterations to scan, before stopping/saving
		:param scanTitle: (optional) the title of the scan to use
		:param scanComment: (optional) a series of comments describing the scan
		:type mouseEvent: QtGui.QMouseEvent
		:type iterLimit: int
		:type scanTitle: str
		:type scanComment: str
		"""
		# define a list that contains a pair of values: (freqIndex,freqValue)
		freqIndex = []
		for i,f in enumerate(self.synthFreqList):
			freqIndex.append(i)
		freqIdxFreqpair = list(zip(freqIndex, self.synthFreqList))
		self.isScanDirectionUp = True
		loopIteration = 0
		lastTime = timer()
		# the scan loop repeats so long as the gui's scanning flag is set
		while self.isScanning:
			loopIteration += 1
			self.signalScanUpdateIterLCD.emit(loopIteration)
			# a copy ensures the original list remains intact
			loopList = list(freqIdxFreqpair)
			if (not self.isScanDirectionUp and
				not self.check_LockinUseUnidirectionScan.isChecked()):
				loopList.reverse()
			# finally enters the loop across the frequency list
			for i,f in loopList:
				self.currentScanIndex = i
				stepStart = timer()
				while self.isPaused and self.isScanning:
					time.sleep(max(self.freqDelay,0.1))
				if (not self.isScanning):
					return
				# set frequency here, and wait for the synth & lockin to settle
				if self.check_UseSynth.isChecked():
					self.socketSynth.set_frequency(float(f), unit='Hz')
				time.sleep(self.freqDelay)
				if not self.check_DGAutoTrig.isChecked() and self.check_UseDG.isChecked():
					self.socketDG.send_trigger()
				# todo: read lia x number of desired times
				if self.check_UseLockin.isChecked():
					if self.check_LockinUseSWTrigInt.isChecked():
						if (self.check_DGAutoTrig.isChecked() and
							not self.check_LockinUseUnidirectionScan.isChecked()):
							self.socketLockin.trigger.execute()
							while not self.socketLockin.trigger.finished():
								time.sleep(0.001)
						if self.socketLockin.version[:2] == "19":
							target_path = '/%s/demods/2/sample.x' % self.socketLockin.device
							sample = None
							while sample is None:
								trigdata = self.socketLockin.trigger.read(True)
								if target_path in trigdata and len(trigdata[target_path]):
									sample = trigdata[target_path][-1]
								time.sleep(0.01)
							clockbase = self.socketLockin.getClockbase()
							# get signal via sum over gate
							t = (sample['timestamp'][0] - sample['timestamp'][0][0])/clockbase
							t += sample['header']['gridcoloffset']
							dt = float(t[1] - t[0])
							sig_start = float(self.txt_PulseLockinInt_start.text())
							sig_end = float(self.txt_PulseLockinInt_end.text())
							idx_start = int(round((sig_start-t[0])/dt))
							idx_end = int(round((sig_end-t[0])/dt))
							sig_length = idx_end - idx_start
							if (self.swTrigViewerThread is not None and
								self.swTrigViewerThread.check_useFilter1.isChecked() and
								self.swTrigViewerThread.combo_useFilter2.currentIndex() > 1):
								result = self.doSWTrigFilter(sample)
								if result is not None:
									sample = result
							sample['x'] = sample['value'][0]
							sig_val = np.sum(sample['x'][idx_start:idx_end])
							# determine baseline
							baseline_start = float(self.txt_PulseLockinBase_start.text())
							baseline_end = float(self.txt_PulseLockinBase_end.text())
							idx_start = int(round((baseline_start-t[0])/dt))
							idx_end = int(round((baseline_end-t[0])/dt))
							baseline = np.mean(sample['x'][idx_start:idx_end])*sig_length
							# subtract baseline
							yval = sig_val - baseline
							# update internal copy of trigger data
							self.swTrig['x'] = np.asarray(sample['x'])
						elif self.socketLockin.version[:2] == "18":
							target_path = '/%s/demods/2/sample.x' % self.socketLockin.device
							sample = None
							while sample is None:
								trigdata = self.socketLockin.trigger.read(True)
								if target_path in trigdata and len(trigdata[target_path]):
									sample = trigdata[target_path][-1]
								time.sleep(0.01)
							clockbase = self.socketLockin.getClockbase()
							# get signal via sum over gate
							t = (sample['timestamp'][0] - sample['timestamp'][0][0])/clockbase
							t += sample['header']['gridcoloffset']
							dt = float(t[1] - t[0])
							sig_start = float(self.txt_PulseLockinInt_start.text())
							sig_end = float(self.txt_PulseLockinInt_end.text())
							idx_start = int(round((sig_start-t[0])/dt))
							idx_end = int(round((sig_end-t[0])/dt))
							sig_length = idx_end - idx_start
							if (self.swTrigViewerThread is not None and
								self.swTrigViewerThread.check_useFilter1.isChecked() and
								self.swTrigViewerThread.combo_useFilter2.currentIndex() > 1):
								result = self.doSWTrigFilter(sample)
								if result is not None:
									sample = result
							sample['x'] = sample['value'][0]
							sig_val = np.sum(sample['x'][idx_start:idx_end])
							# determine baseline
							baseline_start = float(self.txt_PulseLockinBase_start.text())
							baseline_end = float(self.txt_PulseLockinBase_end.text())
							idx_start = int(round((baseline_start-t[0])/dt))
							idx_end = int(round((baseline_end-t[0])/dt))
							baseline = np.mean(sample['x'][idx_start:idx_end])*sig_length
							# subtract baseline
							yval = sig_val - baseline
							# update internal copy of trigger data
							self.swTrig['x'] = np.asarray(sample['x'])
						else:
							if not self.check_LockinUseUnidirectionScan.isChecked():
								time.sleep(0.8/float(self.txt_DGTriggerRate.text()))
							target_path = '/%s/demods/2/sample' % self.socketLockin.device
							sample = None
							while sample is None:
								trigdata = self.socketLockin.trigger.read(True)
								if target_path in trigdata and len(trigdata[target_path]):
									sample = trigdata[target_path][-1]
								time.sleep(0.01)
							#try:
							#	sample = self.socketLockin.trigger.read(True)
							#except:
							#	print("there was a problem reading the trigger")
							#	if self.check_UseDG.isChecked():
							#		self.socketDG.set_trigger_source(0)
							#	self.scanStop()
							#	raise
							#try:
							#	print("there were %g samples" % len(sample))
							#	sample = sample[target_path]
							#except:
							#	print("there was a problem retrieving the desired target")
							#	if self.check_UseDG.isChecked():
							#		self.socketDG.set_trigger_source(0)
							#	self.scanStop()
							#	raise
							#try:
							#	sample = sample[-1]
							#except:
							#	print("the sample didn't look like a list..")
							#	try:
							#		if not self.check_DGAutoTrig.isChecked() and self.check_UseDG.isChecked():
							#			time.sleep(float(self.txt_DGTriggerRate.text())**(-1))
							#			self.socketDG.send_trigger()
							#			self.socketLockin.trigger.set('trigger/forcetrigger', 1)
							#			time.sleep(0.05)
							#		sample = self.socketLockin.trigger.read(True)
							#		if self.debugging:
							#			print(sample)
							#		sample = sample[target_path][-1]
							#	except:
							#		self.scanStop()
							#		raise
							clockbase = self.socketLockin.getClockbase()
							# get signal via sum over gate
							t = (sample['timestamp'] - float(sample['time']['trigger']))/clockbase
							dt = float(t[1] - t[0])
							sig_start = float(self.txt_PulseLockinInt_start.text())
							sig_end = float(self.txt_PulseLockinInt_end.text())
							idx_start = int(round((sig_start-t[0])/dt))
							idx_end = int(round((sig_end-t[0])/dt))
							sig_length = idx_end - idx_start
							if (self.swTrigViewerThread is not None and
								self.swTrigViewerThread.check_useFilter1.isChecked() and
								self.swTrigViewerThread.combo_useFilter2.currentIndex() > 1):
								result = self.doSWTrigFilter(sample)
								if result is not None:
									sample = result
							sig_val = np.sum(sample['x'][idx_start:idx_end])
							# determine baseline
							baseline_start = float(self.txt_PulseLockinBase_start.text())
							baseline_end = float(self.txt_PulseLockinBase_end.text())
							idx_start = int(round((baseline_start-t[0])/dt))
							idx_end = int(round((baseline_end-t[0])/dt))
							baseline = np.mean(sample['x'][idx_start:idx_end])*sig_length
							# subtract baseline
							yval = sig_val - baseline
							# update internal copy of trigger data
							self.swTrig = sample
						self.swTrig['t'] = t
						self.signalSWTrigUpdated.emit()
					else:
						try:
							yval = self.socketLockin.read_data()
						except RuntimeError as e:
							log.exception("caught a RuntimeError: %s" % e)
							yval = 0
				else:
					yval = np.random.random(1)[0]
				remainingTime = float(self.txt_DGTriggerRate.text())**-1 - (timer()-lastTime)
				time.sleep(max(0.0, remainingTime*0.98))
				log.debug("remTime was %s," % (remainingTime,))
				while self.isPaused and self.isScanning:
					time.sleep(max(self.freqDelay,0.1))
				if self.isScanning:
					self.scanUpdateData((i,yval)) # <- may not be thread-safe
				now = timer()
				if self.debugging:
					dt = now - lastTime
					fps = dt**-1
					msg = "step dt was: %.2e  (i.e. %.1f steps/s)" % (dt, fps)
					log.debug(msg)
				lastTime = now
			# flip the direction of the scan
			if self.isScanDirectionUp:
				self.isScanDirectionUp = False
			else:
				self.isScanDirectionUp = True
			# if the iteration limit has been reached, save
			if iterLimit and loopIteration==iterLimit:
				self.scanFinished = True
				self.isBatchReadyForNext = True
				self.signalScanStop.emit(True, True)
				self.signalScanSave.emit(scanTitle, scanComment)
				break
	def scanUpdateData(self, data):
		"""
		Is called by the scan loop, and pushes the newly-read values to
		the internal active lists.

		:param data: the tuple containing the current data's index and the y-value
		:type data: tuple(int, float)
		"""
		if not self.isScanning:
			return
		idx,curY = data
		self.scanYvalsCur[idx] = curY
		# check against sudden spikes, if desired
		curFreq = self.freqList[idx]
		if self.check_ignoreSpikes.isChecked():
			try:
				if self.isScanDirectionUp:
					if abs(curY - self.scanYvalsCur[idx-1]) > self.spikeFilterThreshold*float(np.std(self.scanYvalsCur[idx-5:idx])):
						log.debug("%s looked like a spike!" % curFreq)
						return
				else:
					if abs(curY - self.scanYvalsCur[idx+1]) > self.spikeFilterThreshold*float(np.std(self.scanYvalsCur[idx+1:idx+6])):
						log.debug("%s looked like a spike!" % curFreq)
						return
			except IndexError:
				pass
		if self.scanYvalsIters[idx] > 0:
			avg = self.scanYvalsAvg[idx]
			it = self.scanYvalsIters[idx]
			self.scanYvalsAvg[idx] = (avg*it + curY) / (it+1)
		else:
			self.scanYvalsAvg[idx] = curY
		self.scanYvalsIters[idx] += 1
	@QtCore.pyqtSlot(int)
	def scanUpdateIterLCD(self, loopIteration):
		"""
		Provides functionality to the thread-safe signal that is emitted
		update the iteration counter during a scan.
		
		:param loopIteration: the new value of the current scan sweep
		:type loopIteration: int
		"""
		self.lcd_ScanIterations.display(loopIteration)

	def scanStartSweep(self, mouseEvent=False):
		"""
		Duplicated from self.scanStart(), except that the thread calls
		self.scanRunFreqSweep() instead of self.scanRunFreqLoop().

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		raise NotImplementedError("the jet experiment doesn't support the fast frequency sweep mode!")
		# firstly, don't begin a simultaneous scans (yes, this was possible)
		if self.isScanning or self.isPaused:
			return

		# check the instrument connections and set the values
		self.checkInstruments()
		self.SynthSetValues()
		#self.LockinSetValues()

		# if batch mode is enabled, throw a fit
		if self.led_BatchMode.isEnabled:
			msg = "You have the batch mode enabled! But this is experimental!"
			title = "Experimental Feature!"
			self.showWarning(msg,title=title)

		# define the frequency loops
		hasBlankMult = not self.txt_SynthMultFactor.text()
		hasBlankFreq = (not self.txt_SynthFreqStart.text()) or (not self.txt_SynthFreqEnd.text())
		hasBlankStep = not self.txt_SynthFreqStep.text()
		if hasBlankMult or hasBlankFreq or hasBlankStep:
			self.showInputError("You have a blank entry among the frequency settings!")
		if self.check_SynthSkipCenterFreq.isChecked():
			msg = """You've requested to skip some central frequency window within
			the scan, but this is not supported by the fast frequency sweep mode!"""
			final = "How would you like to proceed?"
			self.showWarning(msg, msgFinal=final)
		freqStart = float(self.txt_SynthFreqStart.text())
		freqEnd = float(self.txt_SynthFreqEnd.text())
		freqStep = float(self.txt_SynthFreqStep.text())
		self.freqList = list(np.arange(freqStart, freqEnd+freqStep, freqStep))
		synthMultFactor = int(self.txt_SynthMultFactor.text())
		self.synthFreqList = []
		for gui_f in self.freqList:
			synth_f = gui_f/float(synthMultFactor)
			synth_f = '%.{0}f'.format(self.synthFreqResolution) % synth_f
			self.synthFreqList.append(synth_f)
		self.freqDelay = float(self.txt_SynthDelay.text())/1000.0

		# initialize the active lists of y-values
		self.scanYvalsCur = []
		self.scanYvalsAvg = []
		self.scanYvalsIters = []
		for f in self.freqList:
			self.scanYvalsCur.append(0)
			self.scanYvalsAvg.append(0)
			self.scanYvalsIters.append(0)

		# set/reset the scan info
		self.txt_ScanStatus.setText("Scanning")
		self.lcd_ScanIterations.display(0)
		self.lcd_ScanFreqPnts.display(len(self.freqList))
		self.txt_ScanTime.setText("")
		self.timeScanStart = datetime.datetime.now()
		self.timeScanStop = 0
		self.timeScanPaused = datetime.timedelta(seconds=0)

		# redefine the precision-limited frequency format
		freqStep = float(self.txt_SynthFreqStep.text())
		freqStep = str(freqStep).rstrip('.0')
		if ('.' in freqStep):
			freqPrecision = len(freqStep.split('.')[1])
		else:
			freqPrecision = 0
		self.freqFormattedPrecision = '%.{0}f'.format(freqPrecision)

		# update the scanning status
		self.isScanning = True

		# connect the frequency looper to a daughter thread & start it
		self.scanThread = genericThread(self.scanRunFreqSweep)
		self.scanThread.start()
	def scanRunFreqSweep(self):
		"""
		Duplicated from self.scanRunFreqLoop, except that it sets up
		the scan loop to run directly on the synthesizer, and instructs
		the LIA to save each sweep into its internal memory.
		
		The way it works is to program into the synthesizer all the
		frequency points that define the fast sweep mode. Then it
		instructs the lockin to store a value during each trigger, which
		should happen after the synthesizer has settled to each new
		frequency point. The intention of this routine instead of the
		PC-controlled frequency step is to speed up the time one can
		sweep through the scan. This could be achieved by the combination
		of removing the overhead of the manual frequency loop via PC, but
		also to reduce the time it takes for the synthesizer to reach
		the new frequency. This latter point was theorized because of
		the conservative specifications from the synth's documentation,
		but it the fast sweep mode is hardly faster than instructing
		the synthesizer to switch to a new, discreet output frequency,
		at least for the conditions involved here..
		
		More details for the curious: it turns out that this only saves
		about 10% of the time needed for a single sweep, and this is
		hardly beneficial compared to the fact that you cannot watch
		the scan in real-time (i.e. only after each sweep is finished).
		"""
		if len(self.synthFreqList) > 3201: # check that the list of frequencies is not too long (ouch!)
			msg = "ERROR: the fast sweep mode does not support a scan length "
			msg += "exceeding 3201 data points, simply because that is the "
			msg += "limit of the Keysight Synthesizer. Buy Jake THREE "
			msg += "beers to somehow bypass this limit through intermediate "
			msg += "data transfers."
			log.exception(msg)
			self.scanStop()
			return
		if len(self.synthFreqList) > 16383: # check that the list of frequencies is not too long (ouch!)
			msg = "ERROR: the fast sweep mode does not support a scan length "
			msg += "exceeding 16383 data points, simply because that is the "
			msg += "limit of the SRS SR830 LIA internal storage. Shorten "
			msg += "the scan length, buy a better lockin, or buy Jake THREE "
			msg += "beers to somehow bypass this limit through intermediate "
			msg += "data transfers."
			log.exception(msg)
			self.scanStop()
			return
		self.socketLockin.set_storage_trigger_mode(mode="on") # switch lockin to single trigger
		log.info("lockin trigger mode is %s" % self.socketLockin.get_storage_trigger_mode())
		self.socketLockin.set_storage_trigger_rate(rate="trigger") # switch lockin to trigger mode
		self.socketSynth.set_freq_list_amplitude(self.combo_SynthPower.value())# set the step delay for the synth
		self.socketSynth.set_freq_list_dwell(self.freqDelay)# set the step delay for the synth
		self.socketSynth.set_freq_list_type(mode="list") # switch synth to list type
		self.socketSynth.set_frequency_mode(mode="list") # switch synth to sweep mode
		self.socketSynth.set_trigger_mode(mode="off") # switch synth to single sweep
		log.info("sending %s frequency points to the synth.." % len(self.synthFreqList))
		self.socketSynth.set_freq_list_points(self.synthFreqList, unit="MHz") # instruct synth about the frequencies
		self.isScanDirectionUp = True
		while self.isScanning:
			self.socketSynth.set_freq_list_direction(self.isScanDirectionUp) ## define the direction for the synth to sweep
			self.socketLockin.reset_storage_buffer() ## reset the lockin trigger
			time.sleep(0.5) # to give time for the storage buffer to clear..
			log.info("sending synth trigger now")
			self.socketSynth.send_trigger() ## send the trigger to the synthesizer
			lockinBufferFilled = False
			log.info("emulating the time to sweep in frequency..")
			time.sleep(0.25)
			for i in self.synthFreqList:
				time.sleep(self.freqDelay+0.001)
			log.info("back awake!")
			lockinBufferSize = self.socketLockin.get_storage_buffer_length() ## query lockin buffer length
			if lockinBufferSize == len(self.synthFreqList): lockinBufferFilled = True
			while not lockinBufferFilled: ## while not yet the proper length, sleep & then re-query
				time.sleep(0.1)
				lockinBufferSize = self.socketLockin.get_storage_buffer_length()
				log.info(lockinBufferSize)
				if lockinBufferSize == len(self.synthFreqList): lockinBufferFilled = True
			log.info("sweep should be finished...")
			lockinBufferSize = self.socketLockin.get_storage_buffer_length()
			log.info("final buffer size is %s" % lockinBufferSize)

			## using TRCA
			#num_idx = 0
			#end = 0
			#lockinBufferDataA = ""
			#while end < (lockinBufferSize-1):
			#	start = num_idx*300
			#	end = start + 299
			#	num_idx += 1
			#	if end > (lockinBufferSize-1):
			#		end = lockinBufferSize-1
			#	print("pulling data from %s to %s" % (start, end))
			#	try:
			#		lockinBufferDataA += self.socketLockin.get_storage_buffer_a(start=start, end=end) ## read buffer
			#	except Gpib.gpib.GpibError:
			#		pass
			## convert to floating point numbers
			#print(lockinBufferDataA)
			#lockinBufferDataNew = [float(val) for val in lockinBufferDataA.split(',')[:-1]]
			#print("converted data yielded: %s" % lockinBufferDataNew)

			## using TRCB
			#time_preTRC = time.clock()
			#lockinBufferDataB = self.socketLockin.get_storage_buffer_b(length=lockinBufferSize) ## read buffer
			#time_postTRC = time.clock()
			#print("reading took %s" % float(time_postTRC-time_preTRC))
			#print("and yielded: %s" % lockinBufferDataB)
			## convert to floating point numbers
			#lockinBufferDataNew = []
			#for i in range(lockinBufferSize):
			#	lockinBufferDataNew.append(float(struct.unpack('f', lockinBufferDataB[i*4:(i+1)*4])[0]))
			#print("converted data yielded: %s" % lockinBufferDataNew)

			# using TRCL
			time_preTRC = time.clock()
			lockinBufferDataL = self.socketLockin.get_storage_buffer_l(length=lockinBufferSize) ## read buffer
			time_postTRC = time.clock()
			log.info("reading took %s" % float(time_postTRC-time_preTRC))
			log.info("and yielded: %s" % lockinBufferDataL)
			# convert to floating point numbers
			lockinBufferDataNew = []
			for i in range(lockinBufferSize):
				start = i*4
				m = int(struct.unpack('h', lockinBufferDataL[start:start+2])[0])
				exp = int(struct.unpack('b', lockinBufferDataL[start+2:start+3])[0])
				val = m * math.exp(exp-124) * 1e3
				lockinBufferDataNew.append(val)
			log.info("converted data yielded: %s" % lockinBufferDataNew)

			## push buffer & flip direction
			# flip the direction of the scan
			if self.isScanDirectionUp:
				self.isScanDirectionUp = False
			else:
				lockinBufferDataNew = reversed(lockinBufferDataNew)
				self.isScanDirectionUp = True

			self.scanUpdateDataSweep(lockinBufferDataNew)
		### after not scanning:
		self.socketLockin.set_storage_trigger_mode(mode="off") # switch lockin to single trigger
		self.socketSynth.set_frequency_mode(mode="cw") ### disable sweep mode on synth
		self.socketLockin.reset_storage_buffer() ### reset the lockin trigger
		self.scanStop()

	def scanUpdateDataSweep(self, data):
		"""
		Duplicated from self.scanUpdateData() except that it processes
		an entire scan sweep, rather than individual points.

		:param data: the tuple containing the current data's index and the y-value
		:type data: tuple(int, float)
		"""
		# TODO: update completely
		if not self.isScanning:
			return
		for idx,curY in enumerate(data):
			self.scanYvalsCur[idx] = curY
			if self.scanYvalsIters[idx] > 0:
				avg = self.scanYvalsAvg[idx]
				it = self.scanYvalsIters[idx]
				self.scanYvalsAvg[idx] = (avg*it + curY) / float(it+1)
			else:
				self.scanYvalsAvg[idx] = curY
			self.scanYvalsIters[idx] += 1
		self.signalScanUpdatePlot.emit()

	def scanUpdateSlow(self):
		"""
		Updates various (semi-real-time) statuses shown in the scan tab.

		Note that this is a slow timer (2 Hz) by default, hence the name
		of the function.
		"""
		self.signalScanUpdateInfo.emit()
	@QtCore.pyqtSlot()
	def scanUpdateInfoByThread(self):
		"""
		Provides the functionality related to the signal that is
		emitted from scanUpdateSlow, and is intended to move all the
		thread-unsafe GUI changes to prevent fatal crashes.
		"""
		if not self.isScanTab:
			return
		if self.isScanning:
			# update the iteration count (sometimes buggy with the batch)
			self.lcd_ScanIterations.update()
			# update the scan time
			deltaTime = datetime.datetime.now() - self.timeScanStart
			timePaused = self.timeScanPaused
			if self.isPaused:
				timePaused += datetime.datetime.now() - self.timeScanPauseStarted
			deltaTime -= timePaused # account for total time paused
			self.txt_ScanTime.setText(str(deltaTime)[:-4])
		if self.scanPlotRegion:
			lowerX, upperX = self.scanPlotRegion.getRegion()
			dataDelta = upperX - lowerX
			dataCenter = lowerX + dataDelta/2.0
			self.txt_ScanDelta.setText("%.2e" % dataDelta)
			self.txt_ScanCenter.setText("%.8e" % dataCenter)
			if len(self.scanYvalsAvg) > 0:
				lowerIdx = np.abs([i - lowerX for i in self.freqList]).argmin()
				upperIdx = np.abs([i - upperX for i in self.freqList]).argmin()
				dataMin = np.amin(self.scanYvalsAvg[lowerIdx:upperIdx])
				dataMax = np.amax(self.scanYvalsAvg[lowerIdx:upperIdx])
				dataAvg = np.mean(self.scanYvalsAvg[lowerIdx:upperIdx])
				dataDev = np.std(self.scanYvalsAvg[lowerIdx:upperIdx])
				self.txt_ScanMin.setText("%.2e" % dataMin)
				self.txt_ScanMax.setText("%.2e" % dataMax)
				self.txt_ScanAvg.setText("%.2e" % dataAvg)
				self.txt_ScanDev.setText("%.2e" % dataDev)
			elif len(self.extra1Int) > 0:
				lowerIdx = np.abs([i - lowerX for i in self.extra1Freq]).argmin()
				upperIdx = np.abs([i - upperX for i in self.extra1Freq]).argmin()
				dataMin = np.amin(self.extra1Int[lowerIdx:upperIdx])
				dataMax = np.amax(self.extra1Int[lowerIdx:upperIdx])
				dataAvg = np.mean(self.extra1Int[lowerIdx:upperIdx])
				dataDev = np.std(self.extra1Int[lowerIdx:upperIdx])
				self.txt_ScanMin.setText("%.2e" % dataMin)
				self.txt_ScanMax.setText("%.2e" % dataMax)
				self.txt_ScanAvg.setText("%.2e" % dataAvg)
				self.txt_ScanDev.setText("%.2e" % dataDev)
		else:
			self.txt_ScanDelta.clear()
			self.txt_ScanMin.clear()
			self.txt_ScanMax.clear()
			self.txt_ScanAvg.clear()
			self.txt_ScanDev.clear()

	def scanToggleStartStop(self):
		"""
		Toggles the start/stop of the scan.
		"""
		if self.isScanning:
			self.scanStop()
		else:
			self.scanStart()
	def scanStop(self, mouseEvent=False, ignorePrompts=False, contBatch=False):
		"""
		Stops the scan indefinitely.

		:param mouseEvent: (optional) the mouse event from a click
		:param ignorePrompts: (optional) whether to ignore prompts and just force a stop
		:param contBatch: (optional) whether to continue the batch scan and moving on to the next one listed
		:type mouseEvent: QtGui.QMouseEvent
		:type ignorePrompts: bool
		:type contBatch: bool
		"""
		if self.check_UseDG.isChecked():
			self.socketDG.set_trigger_source(0)
		self.isScanning = False
		self.isPaused = False
		self.timerScanUpdatePlot.stop()
		self.timerMonUpdatePlot.stop()
		self.txt_ScanStatus.setText("Stopped")
		self.timeScanStop = datetime.datetime.now()
		if ignorePrompts:
			if self.isBatchRunning and not contBatch: self.isBatchRunning = False
		else:
			if self.isBatchRunning:
				msg = "A batch scan is still running! Do you want to stop that as well?"
				response = QtGui.QMessageBox.question(self, "Confirmation", msg,
					QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
				if response == QtGui.QMessageBox.Yes:
					self.isBatchRunning = False
				else:
					self.isBatchReadyForNext = True
	@QtCore.pyqtSlot(bool, bool)
	def scanStopByScanThread(self, ignorePrompts, contBatch):
		"""
		Provides functionality to stop the scan, and is intended to be
		called from a daughter thread. In practice, this is called
		internally, from the thread controlling a batch scan.
		"""
		self.scanStop(ignorePrompts=ignorePrompts, contBatch=contBatch)
	def scanPause(self, mouseEvent=False):
		"""
		Pauses the scan.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if self.isScanning and not self.isPaused:
			self.isPaused = True
			self.txt_ScanStatus.setText("Paused")
			self.timeScanPauseStarted = datetime.datetime.now()
			# switch delay generator back to auto-triggering
			if self.check_UseDG.isChecked() and not self.check_DGAutoTrig.isChecked():
				self.socketDG.set_trigger_source(0)
	def scanContinue(self, mouseEvent=False):
		"""
		Continues the scan from a pause.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		if self.isScanning and self.isPaused:
			# stop delay generator auto-triggering
			if self.check_UseDG.isChecked() and not self.check_DGAutoTrig.isChecked():
				self.socketDG.set_trigger_source(5)
			self.isPaused = False
			self.txt_ScanStatus.setText("Scanning")
			self.timeScanPaused += datetime.datetime.now() - self.timeScanPauseStarted
			del self.timeScanPauseStarted
	def scanPauseToggle(self):
		"""
		Toggles a pause.
		"""
		if self.isScanning and self.isPaused:
			self.scanContinue()
		elif self.isScanning and not self.isPaused:
			self.scanPause()

	def scanSave(self, mouseEvent=False, scanTitle="", scanComment=""):
		"""
		Saves the scan to a new output file.

		:param mouseEvent: (optional) the mouse event from a click
		:param scanTitle: (optional) the title of the scan to use
		:param scanComment: (optional) a series of comments describing the scan
		:type mouseEvent: QtGui.QMouseEvent
		:type scanTitle: str
		:type scanComment: str
		"""
		dt = datetime.datetime.now()
		timeScanSave = dt
		# check the save directory and process it
		saveDir = str(self.txt_SpecOut.text())
		if not saveDir:
			msg = "You have a blank entry for the save directory!"
			msg += "\n\nPlease fix this first.."
			self.showInputError(msg)
		saveDir += "/" + str(datetime.date(dt.year, dt.month, dt.day))
		saveDir = os.path.expanduser(saveDir)
		if not os.path.exists(saveDir):
			os.makedirs(saveDir)

		# capture all the data to save simultaneously
		timeGUIStart = self.timeGUIStart
		timeScanStart = self.timeScanStart
		timeScanStop = self.timeScanStop
		timeScanPaused = self.timeScanPaused
		txt_ScanTime = self.txt_ScanTime.text()
		isScanning = self.isScanning
		isPaused = self.isPaused
		isBatchRunning = self.isBatchRunning
		lcd_ScanIterations = self.lcd_ScanIterations.intValue()
		isScanDirectionUp = self.isScanDirectionUp
		currentScanIndex = self.currentScanIndex
		lcd_ScanFreqPnts = self.lcd_ScanFreqPnts.intValue()
		freqStep = float(self.txt_SynthFreqStep.text())
		freqList = self.freqList
		scanYvalsAvg = self.scanYvalsAvg
		currentSettings = self.getCurrentSettings()

		# get the scan title/comment, if not already specified
		if scanTitle=="" and scanComment=="":
			saveDialog = Dialogs.TitleCommentDialog(self)
			if not saveDialog.exec_():
				return
			else:
				saveResponse = saveDialog.getValues()
				scanTitle = saveResponse["title"]
				scanComment = saveResponse["comment"]

		# populate a list that holds all the header lines
		scanInfo = []
		scanInfo.append("### times")
		scanInfo.append(":timeGUIStart: '%s'" % timeGUIStart)
		scanInfo.append(":timeScanStart: '%s'" % timeScanStart)
		scanInfo.append(":timeScanStop: '%s'" % timeScanStop)
		scanInfo.append(":timeScanSave: '%s'" % timeScanSave)
		scanInfo.append(":timeScanPaused: '%s'" % timeScanPaused)
		scanInfo.append(":txt_ScanTime: '%s'" % txt_ScanTime)
		scanInfo.append("### scan statuses")
		scanInfo.append(":isScanning: '%s'" % isScanning)
		scanInfo.append(":isPaused: '%s'" % isPaused)
		scanInfo.append(":isBatchRunning: '%s'" % isBatchRunning)
		scanInfo.append(":lcd_ScanIterations: '%s'" % lcd_ScanIterations)
		scanInfo.append(":isScanDirectionUp: '%s'" % isScanDirectionUp)
		scanInfo.append(":currentScanIndex: '%s/%s'" % (currentScanIndex, lcd_ScanFreqPnts))
		scanInfo.append("### save settings")
		scanInfo.append(":scanTitle: '%s'" % scanTitle)
		for commentLine in scanComment.split('\n'):
			scanInfo.append(":scanComment: '%s'" % commentLine)

		# set filename via timestamp + title
		scanFilename = saveDir + "/"
		#scanFilename += str(datetime.datetime.now())[:-4].replace(':', '-').replace(' ', '__')
		scanFilename += ("%s" % scanTitle.replace(' ', '_'))
		scanFilename += '.csv'
		if os.path.isfile(scanFilename):
			scanFilename = scanFilename[:-4] + "_(%s).csv" % str(datetime.datetime.now())[:-4].replace(':', '-').replace(' ', '_')
		scanInfo.append(":saveFilename: '%s'" % scanFilename)

		# append current settings from the helper routine
		scanInfo.append("###### GUI SETTINGS")
		scanInfo += currentSettings

		fileHandle = codecs.open(scanFilename, 'w', encoding='utf-8')
		# loop through scanInfo
		for headerEntry in scanInfo:
			fileHandle.write('#%s\n' % headerEntry)

		# determine precision to write out
		freqStep = str(freqStep).rstrip('.0')
		if ('.' in freqStep):
			freqPrecision = len(freqStep.split('.')[1])
		else:
			freqPrecision = 0

		# loop through data to save
		fileHandle.write('#freq,intensity\n')
		for i,f in enumerate(freqList):
			f = freqList[i] # convert to MHz
			f = self.freqFormattedPrecision % f
			fileHandle.write('%s,%.6e\n' % (f, scanYvalsAvg[i]))

		fileHandle.close()
		log.debug("saved to %s" % scanFilename)
	@QtCore.pyqtSlot(str, str)
	def scanSaveByScanThread(self, scanTitle, scanComment):
		"""
		Provides functionality to save the scan, and is intended to be
		called from a daughter thread. In practice, this is called
		internally, from the thread controlling a batch scan.
		"""
		self.scanSave(scanTitle=scanTitle, scanComment=scanComment)
	def scanLoad(self, mouseEvent=False, filename="", toSecond=False):
		"""
		Loads an old scan to the plot.

		:param mouseEvent: (optional) the mouse event from a click
		:param filename: (optional) the filename to load directly
		:param toSecond: (optional) whether to use the "second" slot for the plot
		:type mouseEvent: QtGui.QMouseEvent
		:type filename: str
		:type toSecond: bool
		"""
		# define file
		if filename and os.path.isfile(filename):
			fileIn = filename
		else:
			fileIn = QtGui.QFileDialog.getOpenFileName()
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				fileIn = fileIn[0]
			if not os.path.isfile(fileIn):
				return
		# reset current memory
		if not toSecond:
			if 'scanPlotExtra1' in dir(self):
				self.scanPlotExtra1.clear()
				self.scanPlotLegend.removeItem(self.scanPlotExtra1.name())
				self.ScanPlotFigure.removeItem(self.scanPlotExtra1)
				del self.scanPlotExtra1
			self.extra1Freq = []
			self.extra1Int = []
		else:
			if 'scanPlotExtra2' in dir(self):
				self.scanPlotExtra2.clear()
				self.scanPlotLegend.removeItem(self.scanPlotExtra2.name())
				self.ScanPlotFigure.removeItem(self.scanPlotExtra2)
				del self.scanPlotExtra2
			self.extra2Freq = []
			self.extra2Int = []
		# load file
		fileHandle = codecs.open(fileIn, 'r', encoding='utf-8')
		for line in fileHandle:
			if line[0] == "#":
				continue
			match = re.search(r"^(.*)\,(.*)$", line.strip())
			if match:
				f = match.group(1)
				i = match.group(2)
				try:
					if not toSecond:
						self.extra1Freq.append(float(f))
						self.extra1Int.append(float(i))
					else:
						self.extra2Freq.append(float(f))
						self.extra2Int.append(float(i))
				except ValueError:
					pass
		# add new data to plot
		if not toSecond:
			name = fileIn.split('__')[-1].split('.')[0]
			self.scanPlotExtra1 = self.ScanPlotFigure.plot(
				name=name, clipToView=True,
				autoDownsample=True, downsampleMethod='subsample')
			self.scanPlotExtra1.setPen('y')
			self.scanPlotExtra1.setData(self.extra1Freq, self.extra1Int)
			self.scanPlotExtra1.update()
		else:
			name = fileIn.split('__')[-1].split('.')[0]
			self.scanPlotExtra2 = self.ScanPlotFigure.plot(
				name=name, clipToView=True,
				autoDownsample=True, downsampleMethod='subsample')
			self.scanPlotExtra2.setPen('r')
			self.scanPlotExtra2.setData(self.extra2Freq, self.extra2Int)
			self.scanPlotExtra2.update()

	def scanPlotClearLabels(self, mouseEvent=False, onlyLastOne=False):
		"""
		Clears the plot window of any markups/labels.

		:param mouseEvent: (optional) the mouse event from a click
		:param onlyLastOne: (optional) whether to delete only the last label (i.e. an undo)
		:type mouseEvent: QtGui.QMouseEvent
		:type onlyLastOne: bool
		"""
		if onlyLastOne:
			self.ScanPlotFigure.removeItem(self.scanPlotLabels[-1][0])
			self.ScanPlotFigure.removeItem(self.scanPlotLabels[-1][1])
			self.scanPlotLabels = self.scanPlotLabels[:-1]
		else:
			# clear the click-labels if necessary
			if len(self.scanPlotLabels):
				for label in self.scanPlotLabels:
					self.ScanPlotFigure.removeItem(label[0])
					self.ScanPlotFigure.removeItem(label[1])
				self.scanPlotLabels = []
			# clear the plot region if necessary
			if self.scanPlotRegion:
				self.ScanPlotFigure.removeItem(self.scanPlotRegion)
				self.scanPlotRegion = None
	def scanPlotClearScans(self, mouseEvent=False):
		"""
		Clears the current scan. If a scan is running, it will also
		restart a scan with the same settings.

		Note that a finite delay time is necessary for the plot and spectral
		data to fully reset.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# keep track whether to restart the scan
		toRestart = False
		if self.isScanning:
			toRestart = True
			self.scanStop()
			time.sleep(self.waitBeforeScanRestart)
		# clear the main data
		self.scanYvalsCur = []
		self.scanYvalsAvg = []
		self.scanYvalsIters = []
		self.scanPlotCurrent.clear()
		self.scanPlotAverage.clear()
		# finally, restart the scan if necessary
		if toRestart:
			self.scanStart()
	def scanClearExtra(self, mouseEvent=False, toSecond=False):
		"""
		Clear an extra scan.

		:param mouseEvent: (optional) the mouse event from a click
		:param toSecond: (optional) whether to use the "second" slot for the plot
		:type mouseEvent: QtGui.QMouseEvent
		:type toSecond: bool
		"""
		if not toSecond:
			if 'scanPlotExtra1' in dir(self):
				self.scanPlotExtra1.clear()
				self.scanPlotLegend.removeItem(self.scanPlotExtra1.name())
				self.ScanPlotFigure.removeItem(self.scanPlotExtra1)
				del self.scanPlotExtra1
			self.extra1Freq = []
			self.extra1Int = []
		else:
			if 'scanPlotExtra2' in dir(self):
				self.scanPlotExtra2.clear()
				self.scanPlotLegend.removeItem(self.scanPlotExtra2.name())
				self.ScanPlotFigure.removeItem(self.scanPlotExtra2)
				del self.scanPlotExtra2
			self.extra2Freq = []
			self.extra2Int = []

	def chooseAdvSettingsScan(self, mouseEvent=False):
		"""
		Loads the current 'Advanced Settings' for the scan into a
		ScrollableSettingsWindow

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		advSettingsWindow = ScrollableSettingsWindow(self, self.updateAdvSettingsScan)
		hover = "Note that this value is also used (but x5) for determining\n"
		hover += "the time to wait before sending/reading to the instruments\n"
		hover += "from the other tabs."
		advSettingsWindow.addRow(
			"waitBeforeScanRestart", "Time to allow the memory and plot to reset",
			self.waitBeforeScanRestart, "s", hover=hover)
		advSettingsWindow.addRow(
			"updateperiodScanUpdateSlow", "Update period for the misc. scan info",
			self.updateperiodScanUpdateSlow, "ms")
		hover = "Note: this is only applied after starting a new scan"
		advSettingsWindow.addRow(
			"updateperiodPlotUpdateFast", "Update period for a normal scan",
			self.updateperiodPlotUpdateFast, "ms", hover=hover)
		advSettingsWindow.addRow(
			"updateperiodPlotUpdateSlow", "Update period for a scan with a 'large' number of points",
			self.updateperiodPlotUpdateSlow, "ms", hover=hover)
		advSettingsWindow.addRow(
			"spikeFilterThreshold", "How many multiples of the recent noise level to use for filtering out spikes",
			self.spikeFilterThreshold, "", hover=hover)
		if advSettingsWindow.exec_():
			pass
	def updateAdvSettingsScan(self, advsettings):
		"""
		Updates 'Advanced Settings' for the Synthesizer from the
		ScrollableSettingsWindow

		:param advsettings: the dictionary containing all the new parameters from the ScrollableSettingsWindow
		:type advsettings: dict
		"""
		self.waitBeforeScanRestart = qlineedit_to_float(advsettings["waitBeforeScanRestart"])
		self.updateperiodScanUpdateSlow = qlineedit_to_int(advsettings["updateperiodScanUpdateSlow"])
		self.timerScanUpdateInfo.stop()
		self.timerScanUpdateInfo = genericThreadContinuous(self.scanUpdateSlow, self.updateperiodScanUpdateSlow)
		self.timerScanUpdateInfo.start()
		self.updateperiodPlotUpdateFast = qlineedit_to_int(advsettings["updateperiodPlotUpdateFast"])
		self.updateperiodPlotUpdateSlow = qlineedit_to_int(advsettings["updateperiodPlotUpdateSlow"])
		self.spikeFilterThreshold = qlineedit_to_int(advsettings["spikeFilterThreshold"])

	def scanPlotInit(self):
		"""
		Initializes the plot via the PlotWidget named 'ScanPlotFigure'.
		"""
		# labels
		labelStyle = {'color':'#FFF', 'font-size':'16pt'}
		self.ScanPlotFigure.setLabel('left', "Intensity", units='V', **labelStyle)
		self.ScanPlotFigure.setLabel('bottom', "Frequency", units='Hz', **labelStyle)
		self.ScanPlotFigure.getAxis('bottom').setScale(scale=1e6)
		self.ScanPlotFigure.getAxis('left').tickFont = self.tickFont
		self.ScanPlotFigure.getAxis('bottom').tickFont = self.tickFont
		self.ScanPlotFigure.getAxis('bottom').setStyle(**{'tickTextOffset':5})
		#self.scanPlotLegend = self.ScanPlotFigure.addLegend() # until the pg.LegendItem stops growing in width!
		self.scanPlotLegend = LegendItem(offset=(30, 30))
		self.ScanPlotFigure.getPlotItem().legend = self.scanPlotLegend
		self.scanPlotLegend.setParentItem(self.ScanPlotFigure.getPlotItem().vb)
		# add plots
		self.scanPlotCurrent = SpectralPlot( # self.ScanPlotFigure.plot -> SpectralPlot
			name='current', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.scanPlotAverage = SpectralPlot(
			name='average', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.scanPlotCurrent.setPen('g')
		self.scanPlotAverage.setPen('w')
		self.ScanPlotFigure.addItem(self.scanPlotCurrent)
		self.ScanPlotFigure.addItem(self.scanPlotAverage)
		# add label that tracks the mouse
		self.scanPlotMouseLabel = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
		self.scanPlotMouseLabel.setZValue(999)
		self.ScanPlotFigure.addItem(self.scanPlotMouseLabel, ignoreBounds=True)
		self.scanPlotMouseMoveSignal = pg.SignalProxy(
			self.scanPlotCurrent.scene().sigMouseMoved,
			rateLimit=30,
			slot=self.scanPlotMousePosition)
		self.scanPlotMouseClickSignal = pg.SignalProxy(
			self.scanPlotCurrent.scene().sigMouseClicked,
			rateLimit=10,
			slot=self.scanPlotMouseClicked)
		# add arrow that tracks the location
		self.scanPlotCurFreqMarker = pg.TextItem(text="*",anchor=(0.5,0.5))
		self.scanPlotCurFreqMarker.setZValue(999)
		self.ScanPlotFigure.addItem(self.scanPlotCurFreqMarker, ignoreBounds=True)
		# menu entries for copying to clipboard
		menu = self.ScanPlotFigure.plotItem.getViewBox().menu
		menu.addSeparator()
		copyCur = menu.addAction("copy current scan")
		copyCur.triggered.connect(partial(self.scanPlotCopy, plot="current"))
		copyAvg = menu.addAction("copy average scan")
		copyAvg.triggered.connect(partial(self.scanPlotCopy, plot="average"))
	def scanPlotUpdate(self):
		"""
		Refreshes the plot area, by calling the appropriate functions below.

		Note that the plot itself is not refreshed if the scan tab is not
		active! This prevent a tiny bit of CPU usage on a fast PC..
		"""
		# note: the PyQtGraph business appears to be thread-safe, because the GUI itself is not modified
		if self.isScanning and self.isScanTab:
			self.scanPlotUpdateData()
			self.scanPlotUpdateFreqCursor()
			self.signalScanUpdatePlot.emit()
	@QtCore.pyqtSlot()
	def scanUpdatePlotByThread(self):
		"""
		The intention of this function is simply to force the update of
		the plot, thereby fixing a bug that was observed, whereby the
		plot window was not being updated during a scan, likely caused
		by a newer version of either pyqtgraph or pyqt.
		"""
		self.ScanPlotFigure.viewport().update()
	def scanPlotUpdateData(self):
		"""
		Updates the plot data by pointing each pen to the updated data.
		"""
		self.scanPlotCurrent.setData(self.freqList, self.scanYvalsCur)
		self.scanPlotAverage.setData(self.freqList, self.scanYvalsAvg)
	def scanPlotUpdateFreqCursor(self):
		"""
		Updates the marker that sits below the current frequency point.
		"""
		yPos = min(self.scanYvalsCur)
		self.scanPlotCurFreqMarker.setPos(self.freqList[self.currentScanIndex], yPos)
	def scanPlotMousePosition(self, mouseEvent):
		"""
		Processes the signal when the mouse is moving above the plot area.
		At the moment, it only defines the mouse position, and sends this
		position to update the coordinate label if SHIFT is being pressed.

		Note that this signal is active always, so only light processing
		should be done here, and only under appropriate conditions should
		additional routines should be called. If this is found to cause
		too much CPU lag and slow the computer down, one might consider
		changing the slot to a pyqtgraph slot and a finite (slow) rate.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(PyQt4.QtCore.QPointF, None)
		"""
		if not self.isScanning:
			return
		# convert mouse coordinates to XY wrt the plot
		mousePos = mouseEvent[0]
		viewBox = self.scanPlotCurrent.getViewBox()
		mousePos = viewBox.mapSceneToView(mousePos)
		mousePos = (mousePos.x(), mousePos.y())
		# update mouse label if SHIFT
		if QtGui.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
			self.scanPlotShowCrosshairs(mousePos)
		else:
			self.scanPlotMouseLabel.setPos(0,0)
			self.scanPlotMouseLabel.setText("")
		#if modifiers == QtCore.Qt.ControlModifier:
		#	pass
		#elif modifiers == (QtCore.Qt.ControlModifier | QtCore.Qt.ShiftModifier):
		#	pass
		#else:
		#	pass
	def scanPlotShowCrosshairs(self, mousePos):
		"""
		Updates the tracking label containing the XY-coordinates under the
		mouse, based on an HTML-formatted string.

		:param mousePos: the XY coordinates of the plot figure
		:type mousePos: tuple(float, float)
		"""
		mouseX = mousePos[0]
		mouseY = mousePos[1]
		# define a HTML-formatted text string
		HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'>x=%s"
		HTMLCoordinates += "<br><span style='color:green'>cur=%0.2e</span>"
		HTMLCoordinates += "<br><b>avg=%0.2e</b></span></div>"
		if (mouseX > self.freqList[0]) and (mouseX < self.freqList[-1]):
			idx = np.abs([i - mouseX for i in self.freqList]).argmin()
			m_freq = self.freqFormattedPrecision % (self.freqList[idx])
			yCur = self.scanYvalsCur[idx]
			yAvg = self.scanYvalsAvg[idx]
			self.scanPlotMouseLabel.setPos(mouseX, mouseY)
			self.scanPlotMouseLabel.setHtml(HTMLCoordinates % (m_freq, yCur, yAvg))
		else:
			self.scanPlotMouseLabel.setPos(0,0)
			self.scanPlotMouseLabel.setText("")
	def scanPlotMouseClicked(self, mouseEvent):
		"""
		Processes the signal when the mouse is clicked within the plot.

		:param mouseEvent: the signal from the event of the mouse motion
		:type mouseEvent: tuple(PyQt4.QtCore.QPointF, None)
		"""
		# convert mouse coordinates to XY wrt the plot
		mousePos = mouseEvent[0].scenePos()
		viewBox = self.scanPlotCurrent.getViewBox()
		mousePos = viewBox.mapSceneToView(mousePos)
		mousePos = (mousePos.x(), mousePos.y())
		modifier = QtGui.QApplication.keyboardModifiers()
		# update mouse label if SHIFT
		if modifier == QtCore.Qt.ShiftModifier:
			HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 13pt'>x=%s"
			HTMLCoordinates += "<br>y=%0.2e</span></div>"
			labelDot = pg.TextItem(text="*",anchor=(0.5,0.5))
			labelDot.setPos(mousePos[0], mousePos[1])
			labelDot.setZValue(999)
			self.ScanPlotFigure.addItem(labelDot, ignoreBounds=True)
			labelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
			labelText.setPos(mousePos[0], mousePos[1])
			freq = self.freqFormattedPrecision % (mousePos[0])
			labelText.setHtml(HTMLCoordinates % (freq, mousePos[1]))
			labelText.setZValue(999)
			self.ScanPlotFigure.addItem(labelText, ignoreBounds=True)
			self.scanPlotLabels.append((labelDot,labelText))
		elif (modifier == QtCore.Qt.ControlModifier) and (not self.scanPlotRegion):
			self.scanPlotRegion = pg.LinearRegionItem()
			xRange = viewBox.viewRange()[0][1] - viewBox.viewRange()[0][0]
			lowerX = mousePos[0] - 0.1*xRange
			upperX = mousePos[0] + 0.1*xRange
			self.scanPlotRegion.setRegion((lowerX, upperX))
			self.ScanPlotFigure.addItem(self.scanPlotRegion, ignoreBounds=True)
	def scanPlotCopy(self, plot="average"):
		"""
		Copies the average scan (& header) to the clipboard.

		:param plot: (optional) the name of the plot to copy (default: average)
		:type plot: str
		"""
		# initialize some things..
		fullText = ""
		clipboard = QtGui.QApplication.clipboard()
		# get header info (basically duplicated from self.scanSave)
		scanInfo = []
		scanInfo.append("### times")
		scanInfo.append(":timeGUIStart: '%s'" % self.timeGUIStart)
		scanInfo.append(":timeScanStart: '%s'" % self.timeScanStart)
		scanInfo.append(":timeScanStop: '%s'" % self.timeScanStop)
		scanInfo.append(":timeScanSave: '%s'" % datetime.datetime.now())
		scanInfo.append(":timeScanPaused: '%s'" % self.timeScanPaused)
		scanInfo.append(":txt_ScanTime: '%s'" % self.txt_ScanTime.text())
		scanInfo.append("### scan statuses")
		scanInfo.append(":isScanning: '%s'" % self.isScanning)
		scanInfo.append(":isPaused: '%s'" % self.isPaused)
		scanInfo.append(":isBatchRunning: '%s'" % self.isBatchRunning)
		scanInfo.append(":lcd_ScanIterations: '%s'" % self.lcd_ScanIterations.intValue())
		scanInfo.append(":isScanDirectionUp: '%s'" % self.isScanDirectionUp)
		scanInfo.append(":currentScanIndex: '%s/%s'" % (self.currentScanIndex, self.lcd_ScanFreqPnts.intValue()))
		scanInfo.append("### save settings")
		scanInfo.append(":scanTitle: 'clipboard'")
		scanInfo.append(":scanComment: 'clipboard'")
		scanFilename = ("clipboard_(%s).csv" % str(datetime.datetime.now())[:-4].replace(':', '-').replace(' ', '_'))
		scanInfo.append(":saveFilename: '%s'" % scanFilename)
		scanInfo.append("###### GUI SETTINGS")
		scanInfo += self.getCurrentSettings()
		for headerEntry in scanInfo:
			fullText += '#%s\n' % headerEntry
		fullText += '#freq,intensity\n'
		# get plot data
		plotText = ""
		if plot=="average" and self.scanPlotAverage.xData is not None:
			for i in zip(self.scanPlotAverage.xData, self.scanPlotAverage.yData):
				plotText += "%s,%s\n" % (i[0], i[1])
		else:
			for i in zip(self.scanPlotCurrent.xData, self.scanPlotCurrent.yData):
				plotText += "%s,%s\n" % (i[0], i[1])
		# combine data
		fullText += plotText
		clipboard.setText(fullText)




	### monitor-related
	def monPlotInit(self):
		"""
		Initializes the plot via the PlotWidget named 'MonitorPlotFigure'.
		"""
		# labels
		self.MonitorPlotFigure.setLabel('left', "Intensity", units='V', **{'color':'#FFF', 'font-size':'24pt'})
		self.MonitorPlotFigure.setLabel('bottom', "Time")
		self.MonitorPlotFigure.getAxis('left').tickFont = QtGui.QFont()
		self.MonitorPlotFigure.getAxis('left').tickFont.setPixelSize(48)
		self.MonitorPlotFigure.getAxis('left').fixedWidth = 200
		self.MonitorPlotFigure.getAxis('left').setStyle(**{'autoExpandTextSpace':True})
		# add plots
		timeAxis = DateAxisItem.DateAxisItem(orientation='bottom')
		self.monPlot = self.MonitorPlotFigure.plot(
			name='monitor', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.monPlot.setPen('w')
	def monStart(self, mouseEvent=False):
		"""
		Begins the monitor scan.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# firstly, don't begin a simultaneous scans (yes, this was possible)
		if self.isScanning:
			return
		# switch the delay generator to be manually triggered
		if self.check_UseDG.isChecked() and not self.check_DGAutoTrig.isChecked():
			self.socketDG.set_trigger_source(5)
		# set the frequency
		multFactor = self.txt_SynthMultFactor.text()
		freq = str(self.txt_MonFreq.text())
		if multFactor and freq and self.check_UseSynth.isChecked():
			freq = float(freq) / float(multFactor)
			self.socketSynth.set_frequency(freq, unit='MHz')
		time.sleep(0.1) # to give the synthesizer time to get there..
		# initialize/clear the data
		self.monTime = []
		self.monInt = []
		# define the window
		self.monTimespan = float(self.txt_MonTimespan.text())
		# define monitor loop and get it started
		self.monThread = genericThread(self.monRunLoop)
		self.monThread.start()
		# define the timer to update the monitor plot
		self.monTimestep = float(self.txt_MonTimestep.text())
		updateperiod = int(round(self.monTimestep/2.5))
		self.timerMonUpdatePlot = genericThreadContinuous(self.monPlotUpdate, updateperiod)
		self.timerMonUpdatePlot.start()
		# set the new status
		self.isScanning = True
		self.isPaused = False
	def monRunLoop(self):
		"""
		Defines a monitor loop.
		"""
		while self.isScanning:
			while self.isPaused and self.isScanning:
				time.sleep(max(self.freqDelay,0.1))
			timeDelta = (datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds()
			timeDelta += time.timezone
			if not self.check_DGAutoTrig.isChecked() and self.check_UseDG.isChecked():
				self.socketDG.send_trigger()
			if self.check_UseLockin.isChecked():
				if not self.check_LockinUseSWTrigInt.isChecked():
					try:
						intensity = self.socketLockin.read_data()
					except RuntimeError as e:
						log.exception("caught a RuntimeError: %s" % e)
						continue
				else:
					if self.socketLockin.version[:2] == "18":
						target_path = '/%s/demods/2/sample.x' % self.socketLockin.device
						if self.check_DGAutoTrig.isChecked():
							self.socketLockin.trigger.execute()
							while not self.socketLockin.trigger.finished():
								time.sleep(0.001)
						try:
							trigdata = self.socketLockin.trigger.read(True)
							sample = trigdata[target_path]
							sample = sample[-1]
						except:
							log.exception("there was a problem reading the trigger")
							log.exception(trigdata)
							log.exception(sample)
							raise
						clockbase = self.socketLockin.getClockbase()
						# get signal via sum over gate
						t = (sample['timestamp'][0] - sample['timestamp'][0][0])/clockbase
						t += sample['header']['gridcoloffset']
						dt = float(t[1] - t[0])
						sig_start = float(self.txt_PulseLockinInt_start.text())
						sig_end = float(self.txt_PulseLockinInt_end.text())
						idx_start = int(round((sig_start-t[0])/dt))
						idx_end = int(round((sig_end-t[0])/dt))
						sig_length = idx_end - idx_start
						sample['x'] = sample['value'][0]
						sig_val = np.sum(sample['x'][idx_start:idx_end])
						# determine baseline
						baseline_start = float(self.txt_PulseLockinBase_start.text())
						baseline_end = float(self.txt_PulseLockinBase_end.text())
						idx_start = int(round((baseline_start-t[0])/dt))
						idx_end = int(round((baseline_end-t[0])/dt))
						baseline = np.mean(sample['x'][idx_start:idx_end])*sig_length
						# subtract baseline
						yval = sig_val - baseline
						intensity = yval
						# update internal copy of trigger data
						self.swTrig['x'] = np.asarray(sample['x'])
					else:
						if not self.check_LockinUseUnidirectionScan.isChecked():
							time.sleep(0.8/float(self.txt_DGTriggerRate.text()))
						target_path = '/%s/demods/2/sample' % self.socketLockin.device
						sample = None
						while sample is None:
							trigdata = self.socketLockin.trigger.read(True)
							if target_path in trigdata and len(trigdata[target_path]):
								sample = trigdata[target_path][-1]
							time.sleep(0.01)
						clockbase = self.socketLockin.getClockbase()
						# get signal via sum over gate
						t = (sample['timestamp'] - float(sample['time']['trigger']))/clockbase
						dt = float(t[1] - t[0])
						sig_start = float(self.txt_PulseLockinInt_start.text())
						sig_end = float(self.txt_PulseLockinInt_end.text())
						idx_start = int(round((sig_start-t[0])/dt))
						idx_end = int(round((sig_end-t[0])/dt))
						sig_length = idx_end - idx_start
						if (self.swTrigViewerThread is not None and
							self.swTrigViewerThread.check_useFilter1.isChecked() and
							self.swTrigViewerThread.combo_useFilter2.currentIndex() > 1):
							result = self.doSWTrigFilter(sample)
							if result is not None:
								sample = result
						sig_val = np.sum(sample['x'][idx_start:idx_end])
						# determine baseline
						baseline_start = float(self.txt_PulseLockinBase_start.text())
						baseline_end = float(self.txt_PulseLockinBase_end.text())
						idx_start = int(round((baseline_start-t[0])/dt))
						idx_end = int(round((baseline_end-t[0])/dt))
						baseline = np.mean(sample['x'][idx_start:idx_end])*sig_length
						# subtract baseline
						yval = sig_val - baseline
						intensity = yval
						# update internal copy of trigger data
						self.swTrig = sample
					self.swTrig['t'] = t
					self.signalSWTrigUpdated.emit()
			else:
				intensity = float(np.random.random(1)[0])
			self.monTime.append(timeDelta)
			self.monInt.append(intensity)
			time.sleep(self.monTimestep/1000.0)
	def monPlotUpdate(self):
		"""
		Refreshes the plot area.
		"""
		# note: the PyQtGraph business appears to be thread-safe, because the GUI itself is not modified
		if self.isScanning and self.isMonTab:
			if len(self.monTime) and self.check_useMonTimespan.isChecked():
				vb = self.monPlot.getViewBox()
				# get the x range, based on the time
				upperX = (datetime.datetime.now() - datetime.datetime(1970, 1, 1)).total_seconds()
				upperX += time.timezone
				lowerX = upperX - float(self.txt_MonTimespan.text())
				lowerX = max(lowerX, 0)
				vb.setXRange(lowerX, upperX, padding=0.1)
				# get the y range, based on list methods
				lowerIndex = np.abs([i - lowerX for i in self.monTime]).argmin()
				vb.setYRange(
					min(self.monInt[lowerIndex:]),
					max(self.monInt[lowerIndex:]),
					padding=0.1)
			self.monPlot.setData(self.monTime, self.monInt)
			self.signalMonUpdatePlot.emit()
	@QtCore.pyqtSlot()
	def monUpdatePlotByThread(self):
		"""
		Basically the same as scanUpdatePlotByThread(). See it for details.
		"""
		self.MonitorPlotFigure.viewport().update()

	def monStop(self, mouseEvent=False):
		"""
		Stops the monitor scan.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		self.isScanning = False
		self.isPaused = False
		self.timerScanUpdatePlot.stop()
		self.timerMonUpdatePlot.stop()
	def monToggleStartStop(self):
		"""
		Toggles the start/stop of the monitor.
		"""
		if self.isScanning:
			self.monStop()
		else:
			self.monStart()
	def monPause(self):
		"""
		Pauses the scan.
		"""
		if self.isScanning and not self.isPaused:
			self.isPaused = True
	def monContinue(self):
		"""
		Continues the scan from a pause.
		"""
		if self.isScanning and self.isPaused:
			self.isPaused = False
	def monPauseToggle(self):
		"""
		Toggles pause.
		"""
		if self.isScanning and self.isPaused:
			self.monContinue()
		elif self.isScanning and not self.isPaused:
			self.monPause()
	def monFreqFromLabel(self, mouseEvent=False):
		"""
		Sets the frequency for the monitor scan, based on the first cursor
		added to the scan plot.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# immediately return if there are no labels..
		if not len(self.scanPlotLabels) > 0:
			return
		freq = self.scanPlotLabels[-1][1].x()
		self.txt_MonFreq.setText("%.3f" % freq)




	### alarms
	def alarmCheckLimits(self, ev=None):
		"""
		Checks a variety of set limits against the current readouts, and
		emits an alarm signal if one of them is exceeded.
		
		Note that this function is constantly re-ran from a
		genericThreadContinuous() that is started immediately upon GUI
		initialization.
		"""
		triggered = False
		cause = ""
		if ((self.slider_alarmActivity.value() == 1 and self.isScanning and not self.isPaused) or
			self.slider_alarmActivity.value() == 2):
			# check pressure readout
			try:
				pgauge2a = str(self.txt_PGauge2aReading.text())
				if pgauge2a[:3].lower() == "low":
					pgauge2a = 1e-8
				elif pgauge2a[:4].lower() == "high":
					pgauge2a = 1e3
				else:
					pgauge2a = siEval(pgauge2a)
				try:
					if not self.txt_alarmPgauge2amin.editingFinishedBool:
						raise ValueError
					pgauge2a_min = float(str(self.txt_alarmPgauge2amin.text()))
					if pgauge2a < pgauge2a_min:
						triggered = True
						cause += "pgauge2a is too low, "
				except ValueError:
					pass
				try:
					if not self.txt_alarmPgauge2amax.editingFinishedBool:
						raise ValueError
					pgauge2a_max = float(str(self.txt_alarmPgauge2amax.text()))
					if pgauge2a > pgauge2a_max:
						triggered = True
						cause += "pgauge2a is too high, "
				except ValueError:
					pass
			except:
				log.warning("warning: had trouble checking the alarm limits for pgauge2a: %s" % sys.exc_info()[1])
				pass
			try:
				pgauge2b = str(self.txt_PGauge2bReading.text())
				if pgauge2b[:3].lower() == "low":
					pgauge2b = 1e-8
				elif pgauge2b[:4].lower() == "high":
					pgauge2b = 1e3
				else:
					pgauge2b = siEval(pgauge2b)
				try:
					if not self.txt_alarmPgauge2bmin.editingFinishedBool:
						raise ValueError
					pgauge2b_min = float(str(self.txt_alarmPgauge2bmin.text()))
					if pgauge2b < pgauge2b_min:
						triggered = True
						cause += "pgauge2b is too low, "
				except ValueError:
					pass
				try:
					if not self.txt_alarmPgauge2bmax.editingFinishedBool:
						raise ValueError
					pgauge2b_max = float(str(self.txt_alarmPgauge2bmax.text()))
					if pgauge2b > pgauge2b_max:
						triggered = True
						cause += "pgauge2b is too high, "
				except ValueError:
					pass
			except:
				pass
			# check MFC readings
			if self.check_MFC1Active.isChecked():
				try:
					mfc1 = float(str(self.txt_MFC1CurrentFlow.text()))
					try:
						if not self.txt_alarmMFC1min.editingFinishedBool:
							raise ValueError
						mfc1_min = float(str(self.txt_alarmMFC1min.text()))
						if mfc1 < mfc1_min:
							triggered = True
							cause += "mfc1 is too low, "
					except ValueError:
						pass
					try:
						if not self.txt_alarmMFC1max.editingFinishedBool:
							raise ValueError
						mfc1_max = float(str(self.txt_alarmMFC1max.text()))
						if mfc1 > mfc1_max:
							triggered = True
							cause += "mfc1 is too high, "
					except ValueError:
						pass
				except:
					log.warning("warning: had trouble checking the alarm limits for mfc1: %s" % sys.exc_info()[1])
					pass
			if self.check_MFC2Active.isChecked():
				try:
					mfc2 = float(str(self.txt_MFC2CurrentFlow.text()))
					try:
						if not self.txt_alarmMFC2min.editingFinishedBool:
							raise ValueError
						mfc2_min = float(str(self.txt_alarmMFC2min.text()))
						if mfc2 < mfc2_min:
							triggered = True
							cause += "mfc2 is too low, "
					except ValueError:
						pass
					try:
						if not self.txt_alarmMFC2max.editingFinishedBool:
							raise ValueError
						mfc2_max = float(str(self.txt_alarmMFC2max.text()))
						if mfc2 > mfc2_max:
							triggered = True
							cause += "mfc2 is too high, "
					except ValueError:
						pass
				except:
					pass
			if self.check_MFC3Active.isChecked():
				try:
					mfc3 = float(str(self.txt_MFC3CurrentFlow.text()))
					try:
						if not self.txt_alarmMFC3min.editingFinishedBool:
							raise ValueError
						mfc3_min = float(str(self.txt_alarmMFC3min.text()))
						if mfc3 < mfc3_min:
							triggered = True
							cause += "mfc3 is too low, "
					except ValueError:
						pass
					try:
						if not self.txt_alarmMFC3max.editingFinishedBool:
							raise ValueError
						mfc3_max = float(str(self.txt_alarmMFC3max.text()))
						if mfc3 > mfc3_max:
							triggered = True
							cause += "mfc3 is too high, "
					except ValueError:
						pass
				except:
					pass
			if self.check_MFC4Active.isChecked():
				try:
					mfc4 = float(str(self.txt_MFC4CurrentFlow.text()))
					try:
						if not self.txt_alarmMFC4min.editingFinishedBool:
							raise ValueError
						mfc4_min = float(str(self.txt_alarmMFC4min.text()))
						if mfc4 < mfc4_min:
							triggered = True
							cause += "mfc4 is too low, "
					except ValueError:
						pass
					try:
						if not self.txt_alarmMFC4max.editingFinishedBool:
							raise ValueError
						mfc4_max = float(str(self.txt_alarmMFC4max.text()))
						if mfc4 > mfc4_max:
							triggered = True
							cause += "mfc4 is too high, "
					except ValueError:
						pass
				except:
					pass
			try:
				mfcpressure = str(self.txt_MFCPressureReadingMtab.text())
				mfcpressure = siEval(mfcpressure) * 1e3 # multiplication factor important so that we stick with the same mbar
				try:
					if not self.txt_alarmMFCpressuremin.editingFinishedBool:
						raise ValueError
					mfcpressure_min = float(str(self.txt_alarmMFCpressuremin.text()))
					if mfcpressure < mfcpressure_min:
						triggered = True
						cause += "mfcpressure is too low, "
				except ValueError:
					pass
				try:
					if not self.txt_alarmMFCpressuremax.editingFinishedBool:
						raise ValueError
					mfcpressure_max = float(str(self.txt_alarmMFCpressuremax.text()))
					if mfcpressure > mfcpressure_max:
						triggered = True
						cause += "mfcpressure is too high, "
				except ValueError:
					pass
			except:
				pass
		if triggered:
			cause = cause.rstrip(", ")
			self.signalScanAlarmRaised.emit(cause)
	@QtCore.pyqtSlot(str)
	def alarmRaised(self, cause=None):
		# firstly, print message and raise a window in a new, non-blocking thread
		msg = "WARNING: an alarm was raised at %s\n\tcause: %s" % (datetime.datetime.now(), cause)
		log.info(msg)
		self.tempMessage = genericThread(partial(self.signalShowMessage.emit, "info", ["Alarm was raised!", msg]))
		self.tempMessage.start()
		# turn off if desired
		if self.check_alarmTurnOffAfterTrigger.isChecked():
			self.slider_alarmActivity.setValue(0)
		# send email
		if self.check_alarmEmail.isChecked():
			try:
				import smtplib
				hostname = socket.getfqdn()
				fromaddr = "jet-experiment@%s" % hostname
				toaddrs = str(self.txt_alarmEmail.text())
				if not len(toaddrs):
					raise UserWarning("the email field was empty.. skipping this")
				# build header (structure is important here!)
				msg = "From: %s" % fromaddr
				msg += "\nTo: %s" % toaddrs
				msg += "\nSubject: jet experiment notification"
				# add body of text
				msg += "\n\nThere was an alarm raised by the Jet GUI running on %s" % fromaddr
				msg += "\n\nCause: %s" % cause
				# send mail
				smtpserver = 'localhost'
				server = smtplib.SMTP(smtpserver)
				server.set_debuglevel(0)
				server.sendmail(fromaddr, toaddrs, msg)
				server.quit()
				log.info("an email was successfully sent to %s" % toaddrs)
			except socket.gaierror:
				e = sys.exc_info()[1]
				log.exception("ERROR: there appears to be no local mail server!")
				log.exception("\terror was: %s" % e)
				log.exception("\tto fix this, install postfix, which is a send-only local service")
				log.exception("\t(optionally) see also https://realpython.com/python-send-email/")
			except smtplib.SMTPRecipientsRefused:
				e = sys.exc_info()[1]
				log.exception("ERROR: there was a problem with the local mail server!")
				log.exception("\terror was: %s" % e)
				log.exception("\tto fix this, check /etc/postfix/main.cf.. maybe you need lines like:")
				log.exception("\t\tmynetworks = 127.0.0.0/8 [::ffff:127.0.0.0]/104 [::1]/128")
			except UserWarning as e:
				log.exception(e)
			except:
				e = sys.exc_info()[1]
				log.exception("ERROR: there was an unexpected problem sending an e-mail!")
				log.exception("\terror was: %s" % e)
		if self.check_alarmPauseScan.isChecked() and self.isScanning and not self.isPaused:
			self.scanPause()
		if self.check_alarmCloseMFCs.isChecked():
			for i in range(1,5):
				self.MFCClose(channel=i)
				time.sleep(0.1)
		if self.debugging:
			log.info("finished running all the alarm activities")




	### console-related
	def showConsole(self, mouseEvent=False):
		"""
		Provides a new window containing an interactive console.

		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		namespace = {'self': self}
		msg = "This is an active python console, where 'self' is the gui"
		msg += " object, whereby all its internal items/routines can thus"
		msg += " be made available for direct access."
		msg += "\n\nTo see, for example, the current scanning status, run:"
		msg += "\n>print(self.isScanning)"
		msg += "\n\nIf you want to enable additional print messages, run:"
		msg += "\n>self.debugging = True"
		msg += "\n\nEnjoy!"
		self.console = pg.dbg(namespace=namespace, text=msg)
		self.console.ui.catchAllExceptionsBtn.toggle()
		self.console.ui.onlyUncaughtCheck.setChecked(False)
		self.console.ui.runSelectedFrameCheck.setChecked(False)
		self.console.ui.exceptionBtn.toggle()



	### exit
	def exit(self, mouseEvent=False, confirm=False):
		"""
		Provides the routine that quits the GUI.

		For now, simply quits the running instance of Qt. In the future,
		will be used for saving the session's settings, and possibly other
		things before actually exiting the application.

		:param mouseEvent: (optional) the mouse event from a click
		:param confirm: (optional) whether to first use a confirmation dialog
		:type mouseEvent: QtGui.QMouseEvent
		:type confirm: bool
		"""
		# first invoke the confirmation dialog if necessary
		if confirm:
			msg = "Are you sure you want to exit the program?"
			response = QtGui.QMessageBox.question(self, "Confirmation", msg,
				QtGui.QMessageBox.Yes, QtGui.QMessageBox.No)
			if response == QtGui.QMessageBox.No:
				return
		# stop certain things that should be stopped
		if self.isScanning:
			self.scanStop()
		# save the current settings
		try:
			self.settingsSave(filename=self.defaultSaveFile)
		except IOError: # this prioritizes the exit
			pass
		# close certain things that should be closed
		if self.hasConnectedPressure2 and (self.socketPressure2.socket.port == 8000):
			self.disconnectPressure(readout=2)
		# finally quit
		QtCore.QCoreApplication.instance().quit()




if __name__ == '__main__':
	# monkey-patch the system exception hook so that it doesn't totally crash
	sys._excepthook = sys.excepthook
	def exception_hook(exctype, value, traceback):
		sys._excepthook(exctype, value, traceback)
	sys.excepthook = exception_hook
	
	# define GUI elements
	QtCore.QCoreApplication.setAttribute(QtCore.Qt.AA_X11InitThreads)
	qApp = QtGui.QApplication(sys.argv)
	mainGUI = SpecGUI()

	# parse arguments
	parser = argparse.ArgumentParser()
	parser.add_argument(
		"-d", "--debug", action='store_true',
		help="whether to add extra print messages to the terminal")
	parser.add_argument("-c", "--config", help="a file from which to load settings")
	parser.add_argument("-p", "--plot", help="a file to load in the plot window")
	parser.add_argument("-p2", "--plot2", help="a file to load in the plot window (extra)")
	args = parser.parse_args()
	if args.debug:
		log.debug("debugging was been activated")
		mainGUI.debugging = True
	if args.config and os.path.isfile(args.config):
		mainGUI.settingsLoad(filename=args.config)
	if args.plot and os.path.isfile(args.plot):
		mainGUI.scanLoad(filename=args.plot)
	if args.plot2 and os.path.isfile(args.plot2):
		mainGUI.scanLoad(filename=args.plot2, toSecond=True)

	# start GUI
	mainGUI.show()
	qApp.exec_()
	qApp.deleteLater()
	sys.exit()
