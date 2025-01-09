#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module provides several classes related to simple dialogs.

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
log = logging.getLogger("Dialogs-%s" % os.getpid())
logpath = os.path.expanduser("~/.log/pyLabSpec/GUIs.log")
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
import codecs
import time, datetime
import math
import re
from functools import partial
import subprocess
import webbrowser
import distutils.version
from timeit import default_timer as timer
import tempfile
import ast
from contextlib import contextmanager
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
from pyqtgraph.Qt import uic
loadUiType = uic.loadUiType
if distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5.6":
	try:
		from PyQt5 import QtWebEngineWidgets    # must be imported now, if ever
	except ImportError:
		if sys.platform == "win32" and getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):   # i.e. if bundled from pyinstaller
			pass
		else:
			log.exception("IMPORTERROR: if you got here, you should probably try 'sudo apt-get install python-pyqt5.qtwebengine'")
	try:
		from OpenGL import GL               # to fix an issue with NVIDIA drivers
	except:
		pass
try:
	import matplotlib
	import matplotlib.pyplot as plt
	from matplotlib.figure import Figure
	if distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5":
		from matplotlib.backends.backend_qt5agg import (
			FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
	else:
		from matplotlib.backends.backend_qt4agg import (
			FigureCanvas, NavigationToolbar2QT as NavigationToolbar)
	import matplotlibqtfigureoptions
	matplotlib.backends.qt_editor.figureoptions = matplotlibqtfigureoptions
	try:
		matplotlib.backends.backend_qt5.figureoptions = matplotlibqtfigureoptions
		matplotlib.backends.backend_qt4.figureoptions = matplotlibqtfigureoptions
	except:
		msg = "received an exception while trying to set the qtX.figureoptions"
		msg += ": %s" % (sys.exc_info(),)
		log.debug(msg)
		pass
except ImportError:
	pass
import numpy as np
import scipy
from scipy.odr import odrpack as odr
from scipy.odr import models
try:
	import yaml
except ImportError as e:
	pass
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import miscfunctions
from miscfunctions import strptime
import DateAxisItem
from Fit import fit
import Widgets
from Spectrum import Filters, spectrum

if sys.version_info[0] == 3:
	from importlib import reload
	unicode = str




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

Ui_LoadDialog, QDialog = loadUiType(os.path.join(ui_path, 'SpecLoadDialog.ui'))
class SpecLoadDialog(QDialog, Ui_LoadDialog):
	"""
	Provides a simple dialog to choose a file to load, where formatting
	can be pushed to the caller by way of a dictionary.
	"""
	signalFadedHighlight = QtCore.pyqtSignal(str, str)
	signalUpdateStyleSheet = QtCore.pyqtSignal(str, str)

	def __init__(self, gui):
		"""
		Initializes the dialog box for loading a scan, whereby the user
		can specify filetypes and load options.

		:param gui: the parent gui
		:type gui: QtGui.QMainWindow
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.setWindowIcon(QtGui.QIcon(os.path.join(ui_path, 'question.svg')))
		self.gui = gui

		# button functionality
		self.btn_preprocesses.clicked.connect(self.choosePreprocesses)
		self.btn_browse.clicked.connect(self.browseFile)
		self.btn_ok.clicked.connect(self.checkValues)
		self.btn_cancel.clicked.connect(self.reject)

		# keyboard shortcuts
		self.shortcutCtrlB = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+B"), self, self.browseFile)
		self.shortcutEscape = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.reject)
		self.shortcutReturn = QtGui.QShortcut(QtGui.QKeySequence("Return"), self, self.checkValues)

		# define group of buttons
		self.radioButtons = [
			self.radio_ssv,
			self.radio_tsv,
			self.radio_csv,
			self.radio_casac,
			self.radio_jpl,
			self.radio_gesp,
			self.radio_arbdc,
			self.radio_arbspacing,
			self.radio_fid,
			self.radio_fits,
			self.radio_hidencsv,
			self.radio_brukeropus,
			self.radio_batopt3ds]
		# populate the unit combobox
		units = [
			"arb.",
			"cm-1",
			u"μm",
			"Hz",
			"MHz",
			"GHz",
			"THz",
			"ms",
			"s",
			"mass amu"]
		for u in units:
			self.combo_unit.addItem(u)
		self.combo_unit.setCurrentIndex(units.index("MHz"))
		fftTypes = [
			"None",
			"Hamming",
			"Hann",
			"Blackman",
			"Flattop",
			"Blackmanharris",
			"Kaiser",
			"Triangle",
			"Bohman",
			"Barthann"]
			#"Tukey",
			#"Barlett",
		for t in fftTypes:
			self.combo_fftType.addItem(t)
		self.combo_fftType.setCurrentIndex(fftTypes.index("Hann"))
		sidebands = [
			"upper",
			"lower",
			"both"]
		for s in sidebands:
			self.combo_fftSideband.addItem(s)
		self.combo_fftSideband.setCurrentIndex(sidebands.index("upper"))
		self.preprocess = None

		# set tool tips for mouseover
		self.radio_ssv.setToolTip(
			"Loads a file containing two columns, separated by some amount"
			"\nof spaces.")
		self.radio_tsv.setToolTip(
			"Loads a file containing two columns, separated by some number"
			"\nof tab characters.")
		self.radio_csv.setToolTip("Loads a file containing two columns, separated by a comma.")
		self.radio_casac.setToolTip(
			"Loads a spectral file that conforms to that of the CASAC experiment."
			"\nThat is, a single file contains a single scan, preceded by a number"
			"\nof lines containing metadata relevant to that scan.")
		self.radio_jpl.setToolTip(
			"Loads a spectral file that conforms to that of the JPL Mol Spec"
			"\ngroup. That is, a single file containing lots of separate scans,"
			"\nand containing four lines of metadata preceding each dataset.")
		self.radio_gesp.setToolTip("Loads a file format based on that from Univ. Bologna.")
		self.radio_arbdc.setToolTip(
			"Loads a file that may contain lots of columns, separated by a"
			"\ntype of delimiter. The delimiter and column numbers must be"
			"\nspecified.")
		self.radio_arbspacing.setToolTip(
			"(NOT IMPLEMENTED YET!)"
			"\nLoads a file that is simply a space-/newline-separated list of"
			"\ny-values, which begin at a specific x-value and continue in an"
			"\nevenly-spaced fashion.")
		self.radio_fid.setToolTip(
			"Loads a FID from a CP-FTS. The start/stop/LO/fftType settings are required input.")
		self.radio_fits.setToolTip(
			"Loads a FITS spectral file. Note that this supports only a 1D data file!")
		self.radio_hidencsv.setToolTip(
			"Loads a CSV spectral file that has been exported from a Hiden mass-spec."
			"\nNote: you must manually select the unit ('ms' or 'mass amu') and the scan"
			"\nindex (or it defaults to the last 'cycle')."
			"\npro tip 1: you can select the unit 'ms' and then also specify a mass below"
			"\nand then you can watch the time variation of a single mass across all the"
			"\ncycles"
			"\npro tip 2: you can also set the scan index to -1 and then it will retrieve"
			"\nthe average intensity for each mass of a multi-cycle mass spectrum")
		self.radio_brukeropus.setToolTip(
			"Loads a Bruker Opus file (*.0, *.1, ...)."
			"\nNote: by default, it is assumed that one wants the 'AB' block. Alternatively,"
			"\none may load other spectra contained in the file by changing the 'scan index'"
			"\nto one of the following values:"
			"\n 0: tries AB, then ScSm, finally ScRf"
			"\n 1: the AB block (default)"
			"\n 2: the ScSm block (the single-channel spectrum of the sample)"
			"\n 3: the ScRf block (the single-channel spectrum of the reference)"
			"\n 4: the IgSm block (the interferogram of the sample)"
			"\n 5: the IgRf block (the interferogram of the reference)")
		self.check_appendData.setToolTip(
			"If this is checked, it will load all the files together as"
			"\none dataset, as if they were not in separate files. Otherwise,"
			"\nthe behavior may vary, depending on what interface you are"
			"\ncurrently using.")
		self.check_hasHeader.setToolTip("If this is checked, it will skip the first line in the file.")

		# other signals/slots
		for radio in self.radioButtons:
			radio.clicked.connect(self.radioGroupClicked)
		self.signalFadedHighlight.connect(self.fadedHighlight)
		self.signalUpdateStyleSheet.connect(self.updateStyleSheet)


	@QtCore.pyqtSlot(str, str)
	def updateStyleSheet(self, widgetName=None, stylesheet=None):
		"""
		Changes the stylesheet for a given widget.
		"""
		if sys.version_info[0] == 2:
			widgetName = str(widgetName)
		widget = getattr(self, widgetName)
		widget.setStyleSheet(stylesheet)
	
	def setHighlight(self, widgetName=None, colorName=None):
		"""
		Changes the stylesheet for a given widget.
		"""
		widget = getattr(self, widgetName)
		stylesheet = "background-color:%s;" % colorName
		widget.setStyleSheet(stylesheet)

	def clearHighlights(self):
		"""
		Loops through all the widgets that might possibly be highlighted
		and clears them. This is meant to be done before highlighting a
		new group.
		"""
		widgets = [
			"check_hasHeader",
			"combo_unit",
			"cb_scanIndex",
			"txt_delimiter",
			"cb_xCol", "cb_yCol",
			"txt_spacingStart", "txt_spacingDiff",
			"txt_fidStart", "txt_fidStop", "txt_fidLO", "combo_fftType", "combo_fftSideband",
			"cb_mass",
		]
		for widgetName in widgets:
			self.signalUpdateStyleSheet.emit(widgetName, "")

	@QtCore.pyqtSlot(str, str)
	def fadedHighlight(self, widgetName=None, colorName=None):
		"""
		Begins a timed background change for a widget.
		"""
		if sys.version_info[0] == 2:
			widgetName = str(widgetName)
		widget = getattr(self, widgetName)
		def timedHighlight(widget, colorName):
			"""
			Defines the actual timed background change for a widget.

			Note that since this involves a timed sleep(), this
			should be ran in a daughter thread. However, these
			daughter threads shouldn't actually be changing the
			state of the GUI, so, instead, they are emitting a
			signal to do so at specific times..
			"""
			try:
				origStyleSheet = widget.styleSheet()
				newStyleSheet = "background-color:%s;" % colorName
				self.signalUpdateStyleSheet.emit(widgetName, newStyleSheet)
				time.sleep(10)
				finalStyleSheet = widget.styleSheet()
				# self.signalUpdateStyleSheet.emit(widgetName, origStyleSheet)
				self.signalUpdateStyleSheet.emit(widgetName, "")
			except:
				e = sys.exc_info()
				print("got an exception", e)
		if hasattr(widget, "highlightThread") and not widget.highlightThread.isFinished():
			widget.highlightThread.terminate()
			widget.highlightThread.wait()    # without this, program crashes!
		widget.highlightThread = Widgets.genericThread(timedHighlight, parent=widget, widget=widget, colorName=colorName)
		widget.highlightThread.start()

	@QtCore.pyqtSlot()
	def radioGroupClicked(self):
		"""
		This function is called whenever one of the radio buttons is
		clicked. It primarily just updates the background color for
		required and optional parameter inputs.
		"""
		if self.radio_ssv.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("check_hasHeader", "green")
			self.signalFadedHighlight.emit("combo_unit", "green")
		elif self.radio_tsv.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("check_hasHeader", "green")
			self.signalFadedHighlight.emit("combo_unit", "green")
		elif self.radio_csv.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("check_hasHeader", "green")
			self.signalFadedHighlight.emit("combo_unit", "green")
		elif self.radio_casac.isChecked():
			self.clearHighlights()
		elif self.radio_jpl.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("cb_scanIndex", "yellow")
		elif self.radio_gesp.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("check_hasHeader", "green")
		elif self.radio_arbdc.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("combo_unit", "green")
			self.signalFadedHighlight.emit("txt_delimiter", "yellow")
			self.signalFadedHighlight.emit("cb_xCol", "yellow")
			self.signalFadedHighlight.emit("cb_yCol", "yellow")
		elif self.radio_arbspacing.isChecked():
			self.clearHighlights()
		elif self.radio_fid.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("txt_fidStart", "yellow")
			self.signalFadedHighlight.emit("txt_fidStop", "yellow")
			self.signalFadedHighlight.emit("txt_fidLO", "yellow")
		elif self.radio_fits.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("combo_unit", "green")
			self.signalFadedHighlight.emit("cb_scanIndex", "yellow")
		elif self.radio_hidencsv.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("combo_unit", "green")
			self.signalFadedHighlight.emit("cb_mass", "yellow")
		elif self.radio_brukeropus.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("combo_unit", "green")
		elif self.radio_batopt3ds.isChecked():
			self.clearHighlights()
			self.signalFadedHighlight.emit("combo_unit", "green")

	def browseFile(self):
		"""
		Instantiates a file selection dialog and puts the result into
		the text field.
		"""
		# determine the directory to show in the file dialog
		directory = os.getcwd()
		inserted_directory = os.path.dirname(str(self.txt_file.text()).split('|')[0])
		if os.path.isdir(inserted_directory):
			directory = os.path.realpath(inserted_directory)
		# get file(s)
		paths = QtGui.QFileDialog.getOpenFileNames(directory=directory)
		if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
			paths = paths[0]
		filenames = []
		for f in paths:
			filenames.append(str(f))
		# if file(s) exist(s), simply push them to the text field
		if paths and all(os.path.isfile(f) for f in filenames):
			filenames = "|".join(filenames) # this assumes a vertical line will NEVER appear in a filename..
			self.txt_file.setText(filenames)
	
	def choosePreprocesses(self, mouseEvent=None):
		"""
		Provides a selection dialog for defining preprocessing of the data file.
		Tooltips should more detail about the individual options.

		The selection dialog is an object CheckableSettingsWindow, which is
		connected to the following updatePreprocesses() routine.
		"""
		preProcessDialog = CheckableSettingsWindow(self, self.updatePreprocesses)
		preProcessDialog.addRow(
			"vlsrShift",
			"vlsrShift: Performs a velocity shift (m/s) across the frequency axis",
			entries=[{"format":"%.1f", "value":0.0}])
		preProcessDialog.addRow(
			"vlsrFix",
			"vlsrFix: Fixes the v_lsr (first removes old value, e.g. via FITS header)",
			entries=[{"format":"%.1f", "value":0.0}])
		preProcessDialog.addRow(
			"shiftX",
			"shiftX: Shifts the x-axis by a fixed value",
			entries=[{"format":"%g", "value":0.0}])
		preProcessDialog.addRow(
			"shiftY",
			"shiftY: Shifts the y-axis by a fixed value",
			entries=[{"format":"%g", "value":0.0}])
		preProcessDialog.addRow(
			"clipTopY",
			"clipTopY: Clips all y-values to a maximum value",
			entries=[{"format":"%g", "value":0.0}])
		preProcessDialog.addRow(
			"clipBotY",
			"clipBotY: Clips all y-values to a minimum value value",
			entries=[{"format":"%g", "value":0.0}])
		preProcessDialog.addRow(
			"clipAbsY",
			"clipAbsY: Clips all y-values to a min. -VAL1 and max. +VAL1",
			entries=[{"format":"%g", "value":0.0}])
		preProcessDialog.addRow(
			"wienerY",
			"wienerY: Performs Wiener filter (same as BR tab)",
			entries=[{"format":"%d", "value":10, "hover":"the window size"}])
		preProcessDialog.addRow(
			"medfiltY",
			"medfiltY: Performs a Median filter using a window size",
			entries=[{"format":"%d", "value":3, "hover":"the window size"}])
		preProcessDialog.addRow(
			"ffbutterY",
			"ffbutterY: Performs a low-pass filter (same as BR tab)",
			entries=[{"format":"%d", "value":1, "hover":"the roll-off order (range: 1 to 8)"},
			{"format":"%.1f", "value":5e-3, "hover":"the max Nyquist frequency (valid range: 0.0 to 1.0)"}])
		if preProcessDialog.exec_():
			pass
	
	def updatePreprocesses(self, mouseEvent=None, settings=None):
		"""
		Simply activates the chosen set of preprocessing parameters to be
		used for the spectrum during loading.

		:param settings: the set of preprocessing parameters
		:type settings: dict(tuple(tuple)) according to CheckableSettingsWindow
		"""
		self.preprocess = settings

	def checkValues(self):
		"""
		Checks the type of format that is selected, and makes sure the
		additional options are appropriate.

		Note that this is called directly by the OK button, and then it
		calls the dialogs accept() method if all is in order. This behavior
		was only possible by replacing the ButtonBox with normal buttons,
		otherwise the OK button would have called accept() directly and
		there is no way for one to interrupt the closing of the dialog
		with that default behavior. This is an important subtlety if one
		is interested in emulating this behavior in the future..
		"""
		if not any([radio.isChecked() for radio in self.radioButtons]):
			filetype = spectrum.guess_filetype(filename=str(self.txt_file.text()))
			if filetype == "ssv":
				self.radio_ssv.setChecked(True)
			elif filetype == "tsv":
				self.radio_tsv.setChecked(True)
			elif filetype == "csv":
				self.radio_csv.setChecked(True)
			elif filetype == "casac":
				self.radio_casac.setChecked(True)
			elif filetype == "jpl":
				self.radio_jpl.setChecked(True)
			elif filetype == "gesp":
				self.radio_gesp.setChecked(True)
			elif filetype == "fid":
				self.radio_fid.setChecked(True)
			elif filetype == "fits":
				self.radio_fits.setChecked(True)
			elif filetype == "hidencsv":
				self.radio_hidencsv.setChecked(True)
			elif filetype == "brukeropus":
				self.radio_brukeropus.setChecked(True)
			elif filetype == "batopt3ds":
				self.radio_batopt3ds.setChecked(True)
			else:
				msg = "none of the radio buttons are selected"
				msg += ", and couldn't guess the filetype!"
				raise SyntaxError(msg)
		# check special cases for radio buttons
		if self.radio_jpl.isChecked() and (self.cb_scanIndex.value() == 0):
			raise SyntaxError("you must select a scan index for JPL-style files!")
		if self.radio_arbdc.isChecked():
			if self.txt_delimiter.text() == "":
				raise SyntaxError("you must specify a delimiter (a character or set thereof)!")
			bothNull = bool((self.cb_xCol.value() == 0) and (self.cb_yCol.value() == 0))
			bothSame = bool(self.cb_xCol.value() == self.cb_yCol.value())
			if (not bothNull) and bothSame:
				raise SyntaxError("you cannot request the same columns for both axes!")
		if self.radio_arbspacing.isChecked():
			try:
				float(self.txt_spacingStart.text())
				float(self.txt_spacingDiff.text())
			except ValueError:
				raise SyntaxError("one (or both) of the start/spacing entries do not look like a number!")
		if self.radio_fid.isChecked():
			try:
				float(self.txt_fidStart.text())
				float(self.txt_fidStop.text())
				float(self.txt_fidLO.text())
			except ValueError:
				raise SyntaxError("one (or more) of the FID start/stop/LO entries do not look like a number!")
			#if not unicode(self.combo_unit.currentText()) == "Hz":
			#	raise SyntaxError("the fid unit may only be Hz!")
		if self.radio_hidencsv.isChecked():
			unit = unicode(self.combo_unit.currentText())
			if not unit in ["ms","mass amu"]:
				raise SyntaxError("only units 'ms' (for time plots) and 'mass amu' can be loaded from Hiden CSV files!")
		# check that file exists
		if not any([os.path.isfile(f) for f in self.txt_file.text().split("|")]):
			raise SyntaxError("you have selected a non-existent file!")
		# finally, thing otherwise look good from the syntax side
		self.accept()

	def getValues(self):
		"""
		Gathers all the currently selected options from the dialog, and
		returns this information via a dictionary.

		Note that the returned strings are converted first to a native
		python string type (instead of the GUI element's QString).

		:returns: a dictionary of all the chosen options
		:rtype: dict
		"""
		values = {}
		# check radio buttons for file type
		if self.radio_ssv.isChecked(): values["filetype"] = "ssv"
		elif self.radio_tsv.isChecked(): values["filetype"] = "tsv"
		elif self.radio_csv.isChecked(): values["filetype"] = "csv"
		elif self.radio_casac.isChecked(): values["filetype"] = "casac"
		elif self.radio_jpl.isChecked(): values["filetype"] = "jpl"
		elif self.radio_gesp.isChecked(): values["filetype"] = "gesp"
		elif self.radio_arbdc.isChecked(): values["filetype"] = "arbdc"
		elif self.radio_arbspacing.isChecked(): values["filetype"] = "arbs"
		elif self.radio_fid.isChecked(): values["filetype"] = "fid"
		elif self.radio_fits.isChecked(): values["filetype"] = "fits"
		elif self.radio_hidencsv.isChecked(): values["filetype"] = "hidencsv"
		elif self.radio_brukeropus.isChecked(): values["filetype"] = "brukeropus"
		elif self.radio_batopt3ds.isChecked(): values["filetype"] = "batopt3ds"
		else: raise SyntaxError
		# get others
		values["appendData"] = self.check_appendData.isChecked()
		values["skipFirst"] = self.check_hasHeader.isChecked()
		values["unit"] = unicode(self.combo_unit.currentText())
		values["scanIndex"] = self.cb_scanIndex.value() # int
		values["delimiter"] = str(self.txt_delimiter.text())
		values["xcol"] = self.cb_xCol.value() # int
		values["ycol"] = self.cb_yCol.value() # int
		values["xstart"] = str(self.txt_spacingStart.text())
		values["xstep"] = str(self.txt_spacingDiff.text())
		values["fidStart"] = str(self.txt_fidStart.text())
		values["fidStop"] = str(self.txt_fidStop.text())
		values["fidLO"] = str(self.txt_fidLO.text())
		values["fftType"] = str(self.combo_fftType.currentText())
		values["fftSideband"] = str(self.combo_fftSideband.currentText())
		values["mass"] = self.cb_mass.value() # int
		values["preprocess"] = self.preprocess
		values["filenames"] = str(self.txt_file.text()).split("|")
		# finally return
		return values




Ui_TitleCommentDialog, QDialog = loadUiType(os.path.join(ui_path, 'TitleCommentDialog.ui'))
class TitleCommentDialog(QDialog, Ui_TitleCommentDialog):
	"""
	Provides a simple dialog to retrieve the title and comments, via the
	contents of a QLineEdit and QTextEdit.
	"""

	forbiddenChars = '*#?\\/:;|<>'

	def __init__(self, gui):
		"""
		Initializes the dialog box, wherein the user can input the
		optional title/comment(s) of the scan to be saved.

		:param gui: the parent gui
		:type gui: QtGui.QMainWindow
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.setWindowIcon(QtGui.QIcon(os.path.join(ui_path, 'question.svg')))
		self.gui = gui
		# button functionality
		self.btn_ok.clicked.connect(self.checkValues)
		self.btn_cancel.clicked.connect(self.reject)

		# keyboard shortcuts
		self.shortcutEscape = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.reject)
		self.shortcutReturn = QtGui.QShortcut(QtGui.QKeySequence("Return"), self.txt_Title, self.checkValues)

	def checkValues(self):
		"""
		Invoked when the "OK" button is clicked. In this case, it only
		checks that the title is not blank.
		"""
		title = self.txt_Title.text()
		if title == "":
			msg = "You have a blank title!"
			QtGui.QMessageBox.warning(self, "Error!", msg, QtGui.QMessageBox.Ok)
			return
		elif any(x in title for x in self.forbiddenChars):
			msg = "You have a forbidden character!"
			msg += "\n\nYou may not use any of the following characters:"
			msg += "\n%s" % ' '.join(list(self.forbiddenChars))
			QtGui.QMessageBox.warning(self, "Error!", msg, QtGui.QMessageBox.Ok)
			return
		else:
			self.accept()

	def getValues(self):
		"""
		Returns the contents of the title and comment entries in a
		dictionary.
		"""
		values = {}
		if sys.version_info[0] == 3:
			values["title"] = str(self.txt_Title.text())
			values["comment"] = str(self.textedit_Comment.toPlainText())
		else:
			values["title"] = unicode(self.txt_Title.text())
			values["comment"] = unicode(self.textedit_Comment.toPlainText().toUtf8(), 'utf-8')
		return values




Ui_ScrollableSettings, QDialog = loadUiType(os.path.join(ui_path, 'ScrollableSettings.ui'))
class ScrollableSettingsWindow(QDialog, Ui_ScrollableSettings):
	"""
	Provides a simple window containing a grid contained within a scroll
	area. A public routine addParam allows for the construction of a window
	listing any desired number of parameters, so that this class is meant
	to be used for the 'advanced settings' dialogs.
	"""
	def __init__(self, parent, acceptFunction):
		"""
		Initializes the dialog box.

		:param gui: the parent window/widget
		:param acceptFunction: the function to invoke upon exit
		:type gui: QtGui.QMainWindow
		:type acceptFunction: callable
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.parent = parent
		self.setFont(self.parent.font()) # prevent some weird bugs
		self.numrow = 0
		self.contents = {}
		self.addHeader()
		self.acceptFunction = acceptFunction
		self.buttonBox.accepted.connect(self.acceptInputs)
		self.buttonBox.rejected.connect(self.reject)

	def addHeader(self):
		"""
		Simply adds the text to be placed above the rows of parameters.
		"""
		# define the label (text + tooltip)
		mainLabel = QtGui.QLabel()
		mainLabel.setText("Description")
		hover = "there's nothing to see here.."
		mainLabel.setToolTip(hover)
		self.gridLayout.addWidget(mainLabel,0,0)
		# define the entry line
		entry = QtGui.QLabel()
		entry.setText("Entry")
		self.gridLayout.addWidget(entry,0,1)
		# define the unit label
		unitLabel = QtGui.QLabel()
		unitLabel.setText("Unit")
		self.gridLayout.addWidget(unitLabel,0,2)

	def addRow(self, name, label, value, unit, hover=""):
		"""
		Adds a row to the settings window.

		:param name: the name of the parameter, preferably its actual variable name
		:param label: a description of the parameter
		:param value: the value of the parameter
		:param unit: a description of the parameter's units
		:param hover: (optional) the text that appears upon mouse-over
		:type name: str
		:type label: str
		:type value: str, int, float, bool
		:type unit: str
		:type hover: str
		"""
		# keep track of row
		self.numrow += 1
		row = self.numrow
		# define the description (text + tooltip)
		mainLabel = QtGui.QLabel()
		mainLabel.setText(label)
		if hover:
			mainLabel.setToolTip(hover)
		self.gridLayout.addWidget(mainLabel,row,0)
		# define the entry line
		entry = QtGui.QLineEdit()
		entry.setText(str(value))
		if hover:
			entry.setToolTip(hover)
		self.gridLayout.addWidget(entry,row,1)
		# define the unit label
		unitLabel = QtGui.QLabel()
		unitLabel.setText(unit)
		self.gridLayout.addWidget(unitLabel,row,2)
		# add row to the instance variable
		self.contents[name] = entry
		self.resize( # update the size until some reasonable limit
			min(700, self.gridLayout.sizeHint().width()+50),
			min(500, self.gridLayout.sizeHint().height()+100))

	def acceptInputs(self):
		"""
		Invoked when the "OK" button is clicked. In this case, it calls
		the linked function of the parent GUI, with the contents of each
		parameter name/object pair.
		"""
		self.acceptFunction(self.contents)
		super(self.__class__, self).accept()


class CheckableSettingsWindow(QDialog, Ui_ScrollableSettings):
	"""
	Provides an alternative take on the ScrollableSettingsWindow, which
	contains checkboxes for each entry, as well as rows that optionally
	accept multiple values.
	"""
	contentsChanged = QtCore.Signal()
	def __init__(self, parent, acceptFunction):
		"""
		Initializes the dialog box.

		:param gui: the parent window/widget
		:param acceptFunction: the function to invoke upon exit
		:type gui: QtGui.QMainWindow
		:type acceptFunction: callable
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.parent = parent
		
		self.setFont(self.parent.font()) # prevent some weird bugs
		self.numrow = 0
		self.contents = {}
		self.addHeader()
		self.acceptFunction = acceptFunction
		#self.buttonBox.accepted.connect(self.test)
		self.buttonBox.accepted.connect(self.acceptInputs)
		self.buttonBox.rejected.connect(self.reject)

	def test(self, mouseEvent=None):
		log.debug("running CheckableSettingsWindow.test()...")

	def addHeader(self):
		"""
		Simply adds the text to be placed above the rows of parameters.
		"""
		# define the label (text + tooltip)
		mainLabel = QtGui.QLabel()
		mainLabel.setText("Description")
		hover = "there's nothing to see here.."
		mainLabel.setToolTip(hover)
		self.gridLayout.addWidget(mainLabel,0,0)
		# define the entry line
		entry = QtGui.QLabel()
		entry.setText("Use?")
		self.gridLayout.addWidget(entry,0,1)
		# define the entry line
		entry = QtGui.QLabel()
		entry.setText("Value(s)")
		self.gridLayout.addWidget(entry,0,2)

	def addRow(self, name, label, checked=False, entries=[], hover=None):
		"""
		Adds a row to the settings window.

		:param name: the name of the parameter, preferably its actual variable name
		:param label: a description of the parameter
		:param entries: the value of the parameter
		:param hover: (optional) the text that appears upon mouse-over
		:type name: str
		:type label: str
		:type entries: list(str, str)
		:type hover: str
		"""
		# keep track of row
		self.numrow += 1
		row = self.numrow
		self.contents[name] = []
		# define the description (text + tooltip)
		mainLabel = QtGui.QLabel()
		mainLabel.setText(label)
		if hover is not None:
			mainLabel.setToolTip(hover)
		self.gridLayout.addWidget(mainLabel,row,0)
		# add checkbox
		check = QtGui.QCheckBox()
		check.setChecked(checked)
		self.gridLayout.addWidget(check,row,1)
		self.contents[name].append(check)
		# define the entry line
		for idx,e in enumerate(entries):
			entry = Widgets.ScrollableText(self)
			if ("format" in e) and (e["format"] is not None):
				entry.opts['formatString'] = e["format"]
			if ("value" in e) and (e["value"] is not None):
				entry.setValue(e["value"])
			if ("hover" in e) and (e["hover"] is not None):
				entry.setToolTip(e["hover"])
			self.gridLayout.addWidget(entry,row,2+idx)
			# add row to the instance variable
			self.contents[name].append(entry)
		self.resize( # update the size until some reasonable limit
			min(700, self.gridLayout.sizeHint().width()+50),
			min(500, self.gridLayout.sizeHint().height()+100))

	def acceptInputs(self):
		"""
		Invoked when the "OK" button is clicked. In this case, it calls
		the linked function of the parent GUI, with the contents of each
		parameter name/object pair.
		"""
		settings = []
		for name,row in self.contents.items():
			if row[0].isChecked():
				settings.append(name)
				for v in row[1:]:
					settings.append(v.value())
		self.acceptFunction(settings=settings)
		super(self.__class__, self).accept()




class BasicTextViewer(QtGui.QDialog):
	"""
	Provides a basic window that shows a scrollable TextEdit region.
	"""
	def __init__(self, text="", size=()):
		"""
		Initializes the basic text dialog
		
		:param text: (optional) text to use for initializing the window
		:param size: (optional) initial size of the window
		:type text: str
		:type size: tuple(int,int)
		"""
		super(self.__class__, self).__init__()
		self.text = text
		self.size = size

		self.shortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)

		self.initUI()

	def initUI(self):
		"""
		Sets up all the UI elements
		"""

		self.layout = QtGui.QVBoxLayout()
		self.setLayout(self.layout)

		self.editor = QtGui.QTextEdit()
		self.layout.addWidget(self.editor)
		self.editor.setPlainText(self.text)

		font = QtGui.QFont()
		font.setFamily('Mono')
		self.editor.setFont(font)

		if len(self.size):
			self.resize(self.size[0], self.size[1])
		else:
			# estimate a reasonable sizeHint, using fontmetrics + 50px for border
			fm = QtGui.QFontMetrics(font)
			textWidths = [fm.width(line) for line in self.text.split("\n")]
			textWidth = min(1000, max(textWidths)+50)
			textHeights = len(self.text.split("\n"))*fm.height()+50
			textHeight = min(500, len(self.text.split("\n"))*fm.height()+50)
			if textHeights > 500:
				textWidth += 20 # for the scrollbar!
			self.resize(textWidth, textHeight)

		self.show()




class BasicTextInput(QtGui.QDialog):
	"""
	Provides a basic window that shows a scrollable TextEdit region
	that allows one to input text.
	
	Similar to BasicTextViewer, but has OK/Cancel buttons
	"""
	def __init__(self, text='', size=()):
		super(self.__class__, self).__init__()
		self.text = text
		self.size = size

		self.shortcutOK = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Return"), self, self.accept)
		self.shortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)

		self.initUI()

	def initUI(self):
		"""
		Sets up the UI and defines various parameters.
		"""

		self.mainLayout = QtGui.QVBoxLayout()
		self.setLayout(self.mainLayout)

		self.editor = QtGui.QTextEdit()
		self.mainLayout.addWidget(self.editor)
		self.editor.setPlainText(self.text)

		font = QtGui.QFont()
		font.setFamily('Mono')
		self.editor.setFont(font)

		if len(self.size):
			self.resize(self.size[0], self.size[1])
		else:
			# estimate a reasonable sizeHint, using fontmetrics + 50px for border
			fm = QtGui.QFontMetrics(font)
			textHeight = len(self.text.split("\n"))*fm.height()
			self.resize(250, min(500, 50+textHeight))

		self.buttonLayout = QtGui.QHBoxLayout()
		self.mainLayout.addLayout(self.buttonLayout)

		self.btn_ok = QtGui.QPushButton("Okay", self)
		self.btn_ok.clicked.connect(self.accept)
		self.buttonLayout.addWidget(self.btn_ok)
		self.btn_cancel = QtGui.QPushButton("Cancel", self)
		self.btn_cancel.clicked.connect(self.reject)
		self.buttonLayout.addWidget(self.btn_cancel)

		self.show()




class WarningBox(QtGui.QMessageBox):
	"""
	Provides a warning dialog that's been subclassed specifically for treating the
	width of the detailed text properly. In other words, it simply fixes the
	default behavior, which is thought of as a bug.
	"""
	def __init__(self, *args, **kwargs):
		"""
		Initializes the message box.
		"""
		super(self.__class__, self).__init__(*args, **kwargs)
		self.setWindowIcon(QtGui.QIcon(os.path.join(ui_path, 'exclamation.svg')))
	
	# hijack the resizeEvent event, so the box fits the details
	def resizeEvent(self, event):
		"""
		Replaces the parent method. This is called when the message box
		is resized (i.e. when dragged or when the details are shown). The
		primary purpose of this replacement is to do a better job of
		computing the new width, so that it better matches that of the
		detailed text.

		:param event: the resize signal
		:type event: resizeEvent
		
		:returns: the original resize event
		:rtype: resizeEvent
		"""
		result = super(self.__class__, self).resizeEvent(event)
		details_box = self.findChild(QtGui.QTextEdit)
		if details_box is not None:
			size = details_box.sizeHint().width()*2
			details_box.setFixedWidth(size)
		return result




Ui_CASACSensorViewer, QDialog = loadUiType(os.path.join(ui_path, 'CASACSensorViewer.ui'))
class CASACSensorViewer(QDialog, Ui_CASACSensorViewer):
	"""
	Provides a dialog window that allows one to view all the sensor readouts
	in a single, convenient display. It also provides time-dependent plots
	of each readout, so that one can view trends over time.
	"""
	def __init__(self,
		gui=None,
		filename=None,
		UTCoffset=None,
		contFileUpdate=False):
		"""
		Initializes the dialog window.

		:param gui: (optional) the parent gui
		:param filename: (optional) the filename of stored sensor data
		:param UTCoffset: (optional) the timezone offset from UTC
		:param contFileUpdate: (optional) whether to constantly refresh the file contents
		:type gui: QtGui.QMainWindow
		:type filename: str
		:type UTCoffset: int
		:type contFileUpdate: bool
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)

		# set internal attributes
		self.gui = gui
		self.filename = filename
		self.updateperiodReadouts = 500
		self.updateperiodFile = 5000
		if UTCoffset:
			self.UTC_offset = UTCoffset * -3600
		else:
			self.UTC_offset = time.timezone # assumes the system timezone is correct

		# initialize plots
		self.initPressurePlots()
		self.initTemperaturePlot()
		self.initMFCPlot()

		# initialize containers
		self.dataP1 = {'t':[], 'y':[]}
		self.dataP2a = {'t':[], 'y':[]}
		self.dataP2b = {'t':[], 'y':[]}
		self.dataP3a = {'t':[], 'y':[]}
		self.dataP3b = {'t':[], 'y':[]}
		self.dataP4 = {'t':[], 'y':[]}
		self.dataT1 = {'t':[], 'y':[]}
		self.dataT2 = {'t':[], 'y':[]}
		self.dataT3 = {'t':[], 'y':[]}
		self.dataT4 = {'t':[], 'y':[]}
		self.dataT5 = {'t':[], 'y':[]}
		self.dataMFC1 = {'t':[], 'y':[]}
		self.dataMFC2 = {'t':[], 'y':[]}
		self.dataMFC3 = {'t':[], 'y':[]}
		self.dataMFC4 = {'t':[], 'y':[]}

		# load a file or set one for continuous viewing
		if contFileUpdate:
			self.timerFileUpdate = QtCore.QTimer()
			self.timerFileUpdate.timeout.connect(self.loadSensorData)
			self.timerFileUpdate.start(self.updateperiodFile)
		else:
			self.loadSensorData()
		# if a gui is attached, continuously update its readouts
		if self.gui:
			self.timerReadoutsUpdate = QtCore.QTimer()
			self.timerReadoutsUpdate.timeout.connect(self.updateReadouts)
			self.timerReadoutsUpdate.start(self.updateperiodReadouts)

		# keyboard shortcuts
		self.shortcutCtrlL = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self, self.loadSensorData)
		
		# if the pgauge checkboxes are clicked, update the plots
		self.cb_useLogTop.stateChanged.connect(self.updatePlots)
		self.cb_showTopP1.stateChanged.connect(self.updatePlots)
		self.cb_showTopP2a.stateChanged.connect(self.updatePlots)
		self.cb_showTopP2b.stateChanged.connect(self.updatePlots)
		self.cb_showTopP3a.stateChanged.connect(self.updatePlots)
		self.cb_showTopP3b.stateChanged.connect(self.updatePlots)
		self.cb_showTopP4.stateChanged.connect(self.updatePlots)
		self.cb_useLogBot.stateChanged.connect(self.updatePlots)
		self.cb_showBotP1.stateChanged.connect(self.updatePlots)
		self.cb_showBotP2a.stateChanged.connect(self.updatePlots)
		self.cb_showBotP2b.stateChanged.connect(self.updatePlots)
		self.cb_showBotP3a.stateChanged.connect(self.updatePlots)
		self.cb_showBotP3b.stateChanged.connect(self.updatePlots)
		self.cb_showBotP4.stateChanged.connect(self.updatePlots)

	def loadSensorData(self, filename=None):
		"""
		Loads a CSV file containing the sensor data collected from the
		main CASAC scanning routine.

		If a filename is not specified as an argument, it checks the
		instance for `self.filename`. If this does not exist, it will
		invoke a file selection dialog to choose a file, which is then
		always referenced in future calls.

		Each time it is called, it will first clear the internal memory
		before loading the data. It will then also force an update of
		the plots, by directly calling self.updatePlots() at the end.

		:param filename: (optional) a file to use for loading the data
		:type filename: str
		"""
		# reset the containers
		self.dataP1 = {'t':[], 'y':[]}
		self.dataP2a = {'t':[], 'y':[]}
		self.dataP2b = {'t':[], 'y':[]}
		self.dataP3a = {'t':[], 'y':[]}
		self.dataP3b = {'t':[], 'y':[]}
		self.dataP4 = {'t':[], 'y':[]}
		self.dataT1 = {'t':[], 'y':[]}
		self.dataT2 = {'t':[], 'y':[]}
		self.dataT3 = {'t':[], 'y':[]}
		self.dataT4 = {'t':[], 'y':[]}
		self.dataT5 = {'t':[], 'y':[]}
		self.dataMFC1 = {'t':[], 'y':[]}
		self.dataMFC2 = {'t':[], 'y':[]}
		self.dataMFC3 = {'t':[], 'y':[]}
		self.dataMFC4 = {'t':[], 'y':[]}
		# define filename based on a couple possibilities
		if filename: # overrides self.filename
			self.filename = filename
		if not self.filename:
			self.filename = QtGui.QFileDialog.getOpenFileName()
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				self.filename = self.filename[0]
		# check that it exists, and return immediately if there is a problem
		if not os.path.isfile(self.filename):
			self.filename = None # so that another attempt may be made
			return
		# walk through the file and populate the internal containers
		with codecs.open(self.filename, 'r', encoding='utf-8') as f:
			colP1, colP2a, colP2b = 0, 0, 0
			colP3a, colP3b, colP4 = 0, 0, 0
			colT1, colT2, colT3, colT4, colT5 = 0, 0, 0, 0, 0
			colMFC1, colMFC2, colMFC3, colMFC4 = 0, 0, 0, 0
			for lineIdx,line in enumerate(f):
				columns = line.split(',')
				# use the header to identify which columns are what
				if lineIdx==0:
					if 'pressure1' in columns: colP1 = columns.index('pressure1')
					if 'pressure2a' in columns: colP2a = columns.index('pressure2a')
					if 'pressure2b' in columns: colP2b = columns.index('pressure2b')
					if 'pressure3a' in columns: colP2a = columns.index('pressure3a')
					if 'pressure3b' in columns: colP2b = columns.index('pressure3b')
					if 'pressure4' in columns: colP1 = columns.index('pressure4')
					if 'temperature1' in columns: colT1 = columns.index('temperature1')
					if 'temperature2' in columns: colT2 = columns.index('temperature2')
					if 'temperature3' in columns: colT3 = columns.index('temperature3')
					if 'temperature4' in columns: colT4 = columns.index('temperature4')
					if 'temperature5' in columns: colT5 = columns.index('temperature5')
					if 'mfc1' in columns: colMFC1 = columns.index('mfc1')
					if 'mfc2' in columns: colMFC2 = columns.index('mfc2')
					if 'mfc3' in columns: colMFC3 = columns.index('mfc3')
					if 'mfc4' in columns: colMFC4 = columns.index('mfc4')
				else:
					dt = (strptime(columns[0])-datetime.datetime(1970, 1, 1)).total_seconds()
					dt += self.UTC_offset # UTC correction
					# check that the column is defined, and that data exists there
					if colP1 and columns[colP1]:
						self.dataP1['t'].append(dt)
						p = float(columns[colP1].split(' ')[0])
						p = columns[colP2a]
						p = p.replace("Torr",'torr')
						if len(p.split(' ')) == 2:
							try:
								p = miscfunctions.siEval(p)
							except:
								p = np.nan
						else:
							p = np.nan
						self.dataP1['y'].append(p)
					if colP2a and columns[colP2a]:
						self.dataP2a['t'].append(dt)
						p = columns[colP2a]
						p = p.replace("Torr",'torr')
						if len(p.split(' ')) == 2:
							try:
								p = miscfunctions.siEval(p)
							except:
								p = np.nan
						else:
							p = np.nan
						self.dataP2a['y'].append(p)
					if colP2b and columns[colP2b]:
						self.dataP2b['t'].append(dt)
						p = columns[colP2b]
						p = p.replace("Torr",'torr')
						if len(p.split(' ')) == 2:
							try:
								p = miscfunctions.siEval(p)
							except:
								p = np.nan
						else:
							p = np.nan
						self.dataP2b['y'].append(p)
					if colP3a and columns[colP3a]:
						self.dataP3a['t'].append(dt)
						p = columns[colP3a]
						p = p.replace("Torr",'torr')
						if len(p.split(' ')) == 2:
							try:
								p = miscfunctions.siEval(p)
							except:
								p = np.nan
						else:
							p = np.nan
						self.dataP3a['y'].append(p)
					if colP3b and columns[colP3b]:
						self.dataP3b['t'].append(dt)
						p = columns[colP3b]
						p = p.replace("Torr",'torr')
						if len(p.split(' ')) == 2:
							try:
								p = miscfunctions.siEval(p)
							except:
								p = np.nan
						else:
							p = np.nan
						self.dataP3b['y'].append(p)
					if colP4 and columns[colP4]:
						self.dataP4['t'].append(dt)
						p = columns[colP4]
						p = p.replace("Torr",'torr')
						if len(p.split(' ')) == 2:
							try:
								p = miscfunctions.siEval(p)
							except:
								p = np.nan
						else:
							p = np.nan
						self.dataP4['y'].append(p)
					if colT1 and columns[colT1]:
						self.dataT1['t'].append(dt)
						self.dataT1['y'].append(float(columns[colT1]))
					if colT2 and columns[colT2]:
						self.dataT2['t'].append(dt)
						self.dataT2['y'].append(float(columns[colT2]))
					if colT3 and columns[colT3]:
						self.dataT3['t'].append(dt)
						self.dataT3['y'].append(float(columns[colT3]))
					if colT4 and columns[colT4]:
						self.dataT4['t'].append(dt)
						self.dataT4['y'].append(float(columns[colT4]))
					if colT5 and columns[colT5]:
						self.dataT5['t'].append(dt)
						self.dataT5['y'].append(float(columns[colT5]))
					if colMFC1 and columns[colMFC1]:
						self.dataMFC1['t'].append(dt)
						self.dataMFC1['y'].append(float(columns[colMFC1]))
					if colMFC2 and columns[colMFC2]:
						self.dataMFC2['t'].append(dt)
						self.dataMFC2['y'].append(float(columns[colMFC2]))
					if colMFC3 and columns[colMFC3]:
						self.dataMFC3['t'].append(dt)
						self.dataMFC3['y'].append(float(columns[colMFC3]))
					if colMFC4 and columns[colMFC4]:
						self.dataMFC4['t'].append(dt)
						self.dataMFC4['y'].append(float(columns[colMFC4]))
		self.updatePlots()

	def updateReadouts(self):
		"""
		Refreshes all the displayed readouts. This requires that the parent
		be referenced during the window's initialization.

		Beware: any changes to the names of the parent's relevant GUI
		elements will affect the functionality here.
		"""
		try:
			self.txt_PGauge1Reading.setText(self.gui.txt_PGauge1Reading.text())
			self.txt_PGauge2aReading.setText(self.gui.txt_PGauge2aReading.text())
			self.txt_PGauge2bReading.setText(self.gui.txt_PGauge2bReading.text())
			self.txt_PGauge3aReading.setText(self.gui.txt_PGauge3aReading.text())
			self.txt_PGauge3bReading.setText(self.gui.txt_PGauge3bReading.text())
			self.txt_PGauge4Reading.setText(self.gui.txt_PGauge4Reading.text())
			self.lcd_TempLeft.display(self.gui.lcd_TempLeft.value())
			self.lcd_TempMidLeft.display(self.gui.lcd_TempMidLeft.value())
			self.lcd_TempMiddle.display(self.gui.lcd_TempMiddle.value())
			self.lcd_TempMidRight.display(self.gui.lcd_TempMidRight.value())
			self.lcd_TempRight.display(self.gui.lcd_TempRight.value())
			if self.gui.txt_MFC1CurrentFlow.text(): self.lcd_MFC1.display(float(self.gui.txt_MFC1CurrentFlow.text()))
			if self.gui.txt_MFC2CurrentFlow.text(): self.lcd_MFC2.display(float(self.gui.txt_MFC2CurrentFlow.text()))
			if self.gui.txt_MFC3CurrentFlow.text(): self.lcd_MFC3.display(float(self.gui.txt_MFC3CurrentFlow.text()))
			if self.gui.txt_MFC4CurrentFlow.text(): self.lcd_MFC4.display(float(self.gui.txt_MFC4CurrentFlow.text()))
		except AttributeError as e:
			pass

	def updatePlots(self, inputEvent=None):
		"""
		Updates all the plots by pointing them to the new in-memory lists.
		"""
		self.pressurePlotFig1.setLogMode(y=self.cb_useLogTop.isChecked())
		self.pressurePlotFig2.setLogMode(y=self.cb_useLogBot.isChecked())
		if self.cb_showTopP1.isChecked():
			self.pressurePlot1Top.setData(self.dataP1['t'], self.dataP1['y'])
			self.pressurePlot1Top.update()
		else:
			self.pressurePlot1Top.clear()
		if self.cb_showTopP2a.isChecked():
			self.pressurePlot2aTop.setData(self.dataP2a['t'], self.dataP2a['y'])
			self.pressurePlot2aTop.update()
		else:
			self.pressurePlot2aTop.clear()
		if self.cb_showTopP2b.isChecked():
			self.pressurePlot2bTop.setData(self.dataP2b['t'], self.dataP2b['y'])
			self.pressurePlot2bTop.update()
		else:
			self.pressurePlot2bTop.clear()
		if self.cb_showTopP3a.isChecked():
			self.pressurePlot3aTop.setData(self.dataP3a['t'], self.dataP3a['y'])
			self.pressurePlot3aTop.update()
		else:
			self.pressurePlot3aTop.clear()
		if self.cb_showTopP3b.isChecked():
			self.pressurePlot3bTop.setData(self.dataP3b['t'], self.dataP3b['y'])
			self.pressurePlot3bTop.update()
		else:
			self.pressurePlot3bTop.clear()
		if self.cb_showTopP4.isChecked():
			self.pressurePlot4Top.setData(self.dataP4['t'], self.dataP4['y'])
			self.pressurePlot4Top.update()
		else:
			self.pressurePlot4Top.clear()
		if self.cb_showBotP1.isChecked():
			self.pressurePlot1Bot.setData(self.dataP1['t'], self.dataP1['y'])
			self.pressurePlot1Bot.update()
		else:
			self.pressurePlot1Bot.clear()
		if self.cb_showBotP2a.isChecked():
			self.pressurePlot2aBot.setData(self.dataP2a['t'], self.dataP2a['y'])
			self.pressurePlot2aBot.update()
		else:
			self.pressurePlot2aBot.clear()
		if self.cb_showBotP2b.isChecked():
			self.pressurePlot2bBot.setData(self.dataP2b['t'], self.dataP2b['y'])
			self.pressurePlot2bBot.update()
		else:
			self.pressurePlot2bBot.clear()
		if self.cb_showBotP3a.isChecked():
			self.pressurePlot3aBot.setData(self.dataP3a['t'], self.dataP3a['y'])
			self.pressurePlot3aBot.update()
		else:
			self.pressurePlot3aBot.clear()
		if self.cb_showBotP3b.isChecked():
			self.pressurePlot3bBot.setData(self.dataP3b['t'], self.dataP3b['y'])
			self.pressurePlot3bBot.update()
		else:
			self.pressurePlot3bBot.clear()
		if self.cb_showBotP4.isChecked():
			self.pressurePlot4Bot.setData(self.dataP4['t'], self.dataP4['y'])
			self.pressurePlot4Bot.update()
		else:
			self.pressurePlot4Bot.clear()

		self.temperaturePlot1.setData(self.dataT1['t'], self.dataT1['y'])
		self.temperaturePlot2.setData(self.dataT2['t'], self.dataT2['y'])
		self.temperaturePlot3.setData(self.dataT3['t'], self.dataT3['y'])
		self.temperaturePlot4.setData(self.dataT4['t'], self.dataT4['y'])
		self.temperaturePlot5.setData(self.dataT5['t'], self.dataT5['y'])
		self.temperaturePlot1.update()
		self.temperaturePlot2.update()
		self.temperaturePlot3.update()
		self.temperaturePlot4.update()
		self.temperaturePlot5.update()

		self.MFCPlot1.setData(self.dataMFC1['t'], self.dataMFC1['y'])
		self.MFCPlot2.setData(self.dataMFC2['t'], self.dataMFC2['y'])
		self.MFCPlot3.setData(self.dataMFC3['t'], self.dataMFC3['y'])
		self.MFCPlot4.setData(self.dataMFC4['t'], self.dataMFC4['y'])
		self.MFCPlot1.update()
		self.MFCPlot2.update()
		self.MFCPlot3.update()
		self.MFCPlot4.update()

	def initPressurePlots(self):
		"""
		Initializes the two plots for the pressure gauges.
		"""
		# set log-mode for the full-range
		self.pressurePlotFig1.setLogMode(y=True)
		# labels
		labelStyle = {'color':'#FFF', 'font-size':'16pt'}
		self.pressurePlotFig1.setLabel('left', "Pressure", units='Torr', **labelStyle)
		self.pressurePlotFig1.setLabel('bottom', "Time", **labelStyle)
		self.pressurePlotFig1Legend = self.pressurePlotFig1.addLegend()
		self.pressurePlotFig2.setLabel('left', "Pressure", units='Torr', **labelStyle)
		self.pressurePlotFig2.setLabel('bottom', "Time", **labelStyle)
		self.pressurePlotFig2Legend = self.pressurePlotFig2.addLegend()
		# y-ranges
		# add plots
		timeAxis = DateAxisItem.DateAxisItem(orientation='bottom')
		self.pressurePlot1Top = self.pressurePlotFig1.plot(
			name='gauge 1', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot2aTop = self.pressurePlotFig1.plot(
			name='gauge 2a', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot2bTop = self.pressurePlotFig1.plot(
			name='gauge 2b', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot3aTop = self.pressurePlotFig1.plot(
			name='gauge 3a', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot3bTop = self.pressurePlotFig1.plot(
			name='gauge 3b', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot4Top = self.pressurePlotFig1.plot(
			name='gauge 4', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot1Bot = self.pressurePlotFig2.plot(
			name='gauge 1', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot2aBot = self.pressurePlotFig2.plot(
			name='gauge 2a', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot2bBot = self.pressurePlotFig2.plot(
			name='gauge 2b', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot3aBot = self.pressurePlotFig2.plot(
			name='gauge 3a', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot3bBot = self.pressurePlotFig2.plot(
			name='gauge 3b', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.pressurePlot4Bot = self.pressurePlotFig2.plot(
			name='gauge 4', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		# set colors
		self.pressurePlot2aTop.setPen('g')
		self.pressurePlot2bTop.setPen('b')
		self.pressurePlot2aBot.setPen('g')
		self.pressurePlot2bBot.setPen('b')
		self.pressurePlot3aTop.setPen((255,150,0,255))
		self.pressurePlot3bTop.setPen('y')
		self.pressurePlot3aBot.setPen((255,150,0,255))
		self.pressurePlot3bBot.setPen('y')
		self.pressurePlot4Top.setPen('r')
		self.pressurePlot4Bot.setPen('r')

	def initTemperaturePlot(self):
		"""
		Initializes the plot for the temperature readings.
		"""
		# labels
		labelStyle = {'color':'#FFF', 'font-size':'16pt'}
		self.temperaturePlotFig.setLabel('left', "Temperature", units='K', **labelStyle)
		self.temperaturePlotFig.setLabel('bottom', "Time", **labelStyle)
		self.temperaturePlotFigLegend = self.temperaturePlotFig.addLegend()
		# add plots
		timeAxis = DateAxisItem.DateAxisItem(orientation='bottom')
		self.temperaturePlot1 = self.temperaturePlotFig.plot(
			name='left', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.temperaturePlot2 = self.temperaturePlotFig.plot(
			name='mid-left', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.temperaturePlot3 = self.temperaturePlotFig.plot(
			name='middle', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.temperaturePlot4 = self.temperaturePlotFig.plot(
			name='mid-right', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.temperaturePlot5 = self.temperaturePlotFig.plot(
			name='right', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		# set colors
		self.temperaturePlot1.setPen('r')
		self.temperaturePlot2.setPen('m')
		self.temperaturePlot3.setPen('y')
		self.temperaturePlot4.setPen('g')
		self.temperaturePlot5.setPen('b')

	def initMFCPlot(self):
		"""
		Initiates the plot for the current flow values of the MFCs.
		"""
		# labels
		labelStyle = {'color':'#FFF', 'font-size':'16pt'}
		self.MFCPlotFig.setLabel('left', "Flow", units='sccm', **labelStyle)
		self.MFCPlotFig.setLabel('bottom', "Time", **labelStyle)
		self.MFCPlotFigLegend = self.MFCPlotFig.addLegend()
		# add plots
		timeAxis = DateAxisItem.DateAxisItem(orientation='bottom')
		self.MFCPlot1 = self.MFCPlotFig.plot(
			name='MFC1', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.MFCPlot2 = self.MFCPlotFig.plot(
			name='MFC2', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.MFCPlot3 = self.MFCPlotFig.plot(
			name='MFC3', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		self.MFCPlot4 = self.MFCPlotFig.plot(
			name='MFC4', axisItems={'bottom': timeAxis},
			clipToView=True, autoDownsample=True, downsampleMethod='subsample')
		# set colors
		self.MFCPlot1.setPen('r')
		self.MFCPlot2.setPen('y')
		self.MFCPlot3.setPen('g')
		self.MFCPlot4.setPen('b')




Ui_VAMDCSpeciesBrowser, QDialog = loadUiType(os.path.join(ui_path, 'VAMDCSpeciesBrowser.ui'))
class VAMDCSpeciesBrowser(QDialog, Ui_VAMDCSpeciesBrowser):
	"""
	Provides a dialog window that contains a lists of species pulled
	from the VAMDC, as well as an entry for filtering raw strings.
	
	This class is heavily connected to the VAMDC python library found
	as a submodule, as well as the routines in qtfit that utilize said
	library.
	"""
	def __init__(self, speciesList, parent=None):
		"""
		Initializes the dialog window.

		:param speciesList: a list of species available from the VAMDC library (see pyLabSpec.GUIs.qtfit.getVAMDCSpeciesList())
		:param gui: (optional) the parent gui
		:type speciesList: list
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		
		# add hovertext tooltips
		stoiToolTip = "matches against the stoichiometry of the molecules"
		stoiToolTip += "\n\nNote 1: isotopes are collapsed into their main element"
		stoiToolTip += "\n\ti.e. 'D2O' looks like 'H2O'"
		stoiToolTip += "\n\nNote 2: elements have (mostly) a strict order: C H N O P S Si"
		stoiToolTip += "\n\ti.e. 'NH2OH' looks like 'H3NO'"
		stoiToolTip += "\n\twarning: unfortunately there are many exceptions o_0"
		stoiToolTip += "\n\nNote 3: regular expressions are also allowed"
		stoiToolTip += "\nuseful metacharacters:  .  ^  $  *  +  ?  { } [ ] \ | ( )"
		stoiToolTip += "\nuseful character sets: \d = [0-9],   \D = [^0-9],   \w = [a-zA-Z0-9_],   . = (anything)"
		stoiToolTip += "\n\ti.e. 'CH\d+O' would match with ['CH2O', 'CH3O', ...]"
		stoiToolTip += "\n\ti.e. 'C.O' would match with ['CHO', 'CNO', ...]"
		stoiToolTip += "\n\ti.e. '.S$' would match all diatomics of S paired with a lighter element"
		stoiToolTip += "\n\ti.e. '.*S(?!i)' would match S-containing species EXCEPT when S is part of 'Si'"
		self.txt_filterStoi.setToolTip(stoiToolTip)

		# set internal attributes
		self.parent = parent
		self.speciesList = speciesList
		# button functionality
		self.btn_test.clicked.connect(self.test)
		self.btn_ok.clicked.connect(self.check)
		self.btn_cancel.clicked.connect(self.reject)
		# list functionality
		self.listWidget.setSelectionMode(QtGui.QAbstractItemView.ExtendedSelection)
		self.listWidget.itemDoubleClicked.connect(self.accept)
		if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5.0.0":
			self.listWidget.itemPressed.connect(self.mouseClicked)
		else:
			self.listWidget.itemClicked.connect(self.mouseClicked)
		# update contents
		self.txt_filterFormula.textChanged.connect(self.updateList)
		self.txt_filterStoi.textChanged.connect(self.updateList)
		self.txt_filterName.textChanged.connect(self.updateList)
		self.updateList()

	def test(self):
		log.debug("VAMDCSpeciesBrowser.test() does nothing at the moment...")

	def updateList(self):
		"""
		Updates the list of species shown, based on the filters provided
		by the text entries. This routine is called whenever said text
		entries are modified.
		"""
		reload(Widgets)
		self.curList = []
		self.listWidget.clear()
		fltForm = str(self.txt_filterFormula.text())
		fltStoi = str(self.txt_filterStoi.text())
		REmetacharacters = ".^$*+?{}[]\|()"
		fltStoiLooksLikeRE = any([c in fltStoi for c in REmetacharacters])
		try:
			fltStoiRE = re.compile(fltStoi)
		except:
			pass
		fltName = str(self.txt_filterName.text())
		for s in self.speciesList:
			if (not fltForm == "") and (not fltForm in s.OrdinaryStructuralFormula):
				continue
			# try matching the stoichiometry
			if (not fltStoi == ""):
				# first as a normal substring
				if (not fltStoiLooksLikeRE) and (not fltStoi in s.StoichiometricFormula):
					continue
				elif fltStoiLooksLikeRE: # then as a regular expression
					try:
						if (not fltStoiRE.search(s.StoichiometricFormula)):
							continue
					except UnboundLocalError:
						pass
			try:
				if (not fltName == "") and (not fltName.lower() in s.ChemicalName.lower()):
					continue
			except AttributeError:
				log.warning("(VAMDCSpeciesBrowser) entry Comment='%s' has no ChemicalName attribute and was thus ignored" % s.Comment)
				continue
			i = QtGui.QListWidgetItem()
			i.model = s
			try:
				i.setText("%s: %s (%s)    %s" % (
					s.Comment[:6],
					s.OrdinaryStructuralFormula,
					s.ChemicalName,
					s.Comment.split(';')[-1].strip()))
			except AttributeError:
				i.setText("%s: %s ()    %s" % (
					s.Comment[:6],
					s.OrdinaryStructuralFormula,
					s.Comment.split(';')[-1].strip()))
			toolTip = 'full comment: %s' % (s.Comment)
			for prop in ["OrdinaryStructuralFormula",
				"StoichiometricFormula",
				"ChemicalName",
				"MolecularWeight",
				"InChI",
				"InChIKey",
				"Id",
				"SpeciesID",
				"VAMDCSpeciesID"]:
				try:
					toolTip += "\n%s: %s" % (prop, getattr(s, prop))
				except AttributeError:
					log.warning("(VAMDCSpeciesBrowser) entry Comment='%s' has no attribute '%s'" % (s.Comment, prop))
			i.setToolTip(toolTip)
			self.listWidget.addItem(i)
		self.label_filterStatus.setText("%s items found" % self.listWidget.count())
	
	
	### define a number of routines for viewing more info about the entries
	def mouseClicked(self, item):
		"""
		Provides a method that is called whenever an item in the list is
		clicked with the mouse. At the moment, the right-click will
		activate a small menu that provides additional interaction of
		the item of interest (data/info exploration).
		
		Note that this interface is established via the signal
		listWidget.itemClicked, which is activated from __init__() above.

		:param item: the active item during this call
		:type item: QListWidgetItem
		"""
		event = self.listWidget._mouseEvent
		pos = QtGui.QCursor().pos()
		if event.button() == QtCore.Qt.RightButton:
			tag = item.model.Comment[:6].strip()
			popMenu = QtGui.QMenu(self.listWidget)
			if tag[-3] == "5":
				viewCat = popMenu.addAction('view cat (cdms only)')
				viewCat.triggered.connect(partial(self.viewCat, item=item))
			downloadCat = popMenu.addAction('download cat')
			downloadCat.triggered.connect(partial(self.downloadCat, item=item))
			viewDoc = popMenu.addAction('view online doc')
			viewDoc.triggered.connect(partial(self.viewOnlineDoc, item=item))
			viewDocNew = popMenu.addAction('view online doc (new)')
			viewDocNew.triggered.connect(partial(self.viewOnlineDocNew, item=item))
			viewNISTwebbook = popMenu.addAction('search NIST webbook')
			viewNISTwebbook.triggered.connect(partial(self.viewNISTwebbook, item=item))
			popMenu.exec_(pos)
	
	def viewCat(self, item):
		"""
		Attempts to load the target catalog via the system's default
		web browser.
		
		This is called from a menu entry.

		:param item: the active item during this call
		:type item: QListWidgetItem
		"""
		tag = item.model.Comment[:6].replace(' ', '0')
		jplurl = 'c%s.cat'
		cdmsurl = 'https://cdms.astro.uni-koeln.de/cgi-bin/cdmssearch?file=c%s.cat'
		if tag[-3] == "5":
			url = cdmsurl % tag
		else:
			raise NotImplementedError("there is no direct link to view the JPL catalogs yet!")
		log.info("(VAMDCSpeciesBrowser) will try to load url: %s" % (url))
		webbrowser.open(url)
		#try:
		#	subprocess.call(['xdg-open', url])
		#except OSError:
		#	msg = "ERROR: cannot access 'xdg-open' for loading the link!"
		#	msg += " install it via the 'xdg-utils' package..."
		#	msg += "\n\t-> debian/ubuntu: sudo apt-get install xdg-utils"
		#	msg += "\n\t-> macports: sudo port install xdg-utils"
		#	print(msg)
		#from PyQt4 import QtWebKit
		#self.parent.catViewer = QtWebKit.QWebView()
		#self.parent.catViewer.setUrl(QtCore.QUrl(url))
		#self.parent.catViewer.show()
	
	def downloadCat(self, item):
		"""
		Attempts to download the target catalog via the system's default
		web browser.
		
		This is called from a menu entry.

		:param item: the active item during this call
		:type item: QListWidgetItem
		"""
		tag = item.model.Comment[:6].replace(' ', '0')
		jplurl = 'https://spec.jpl.nasa.gov/ftp/pub/catalog/c%s.cat'
		cdmsurl = 'https://cdms.astro.uni-koeln.de/classic/entries/c%s.cat'
		if tag[-3] == "5":
			url = cdmsurl % tag
		else:
			url = jplurl % tag
		log.info("(VAMDCSpeciesBrowser) will try to load url: %s" % (url))
		webbrowser.open(url)
	
	def viewOnlineDoc(self, item):
		"""
		Attempts to load the target's online documentation via the system's
		default web browser.
		
		This is called from a menu entry.

		:param item: the active item during this call
		:type item: QListWidgetItem
		"""
		tag = item.model.Comment[:6].replace(' ', '0')
		jplurl = 'https://spec.jpl.nasa.gov/ftp/pub/catalog/doc/d%s.pdf'
		cdmsurl = 'https://cdms.astro.uni-koeln.de/cgi-bin/cdmsinfo?file=e%s.cat'
		if tag[-3] == "5":
			url = cdmsurl % tag
		else:
			url = jplurl % tag
		log.info("will try to load url: %s" % (url))
		webbrowser.open(url)
	
	def viewOnlineDocNew(self, item):
		"""
		Attempts to load the target's online documentation via the system's
		default web browser.
		
		This is called from a menu entry.

		:param item: the active item during this call
		:type item: QListWidgetItem
		"""
		speciesid = item.model.SpeciesID
		urltemplate = 'https://cdms.astro.uni-koeln.de/cdms/portal/catalog/%s/'
		if (speciesid[0:5] == "XCDMS") or (speciesid[0:4] == "XJPL"):
			url = urltemplate % (speciesid.split("-")[1])
		else:
			msg = "this has a strange SpeciesID (instead of XCDMS-xxx or XJPL-xxx): %s!" % speciesid
			raise NotImplementedError(msg)
		log.info("(VAMDCSpeciesBrowser) will try to load url: %s" % (url))
		webbrowser.open(url)
	
	def viewNISTwebbook(self, item):
		"""
		Attempts to load the target from the NIST Chemistry WebBook.
		
		This is called from a menu entry.

		:param item: the active item during this call
		:type item: QListWidgetItem
		"""
		speciesid = item.model.SpeciesID
		url = 'https://webbook.nist.gov/cgi/cbook.cgi?InChI=%s'
		url = url % (item.model.InChI)
		log.info("(VAMDCSpeciesBrowser) will try to load url: %s" % (url))
		webbrowser.open(url)


	### defines a number routines for interacting/retrieving with parent interface
	def check(self):
		"""
		Checks that an item is selected, and could do other tasks.
		"""
		# DO SOMETHING HERE
		if not self.listWidget.selectedItems():
			self.reject()
		else:
			self.accept()

	def getModel(self):
		"""
		Returns the entry/entries that was selected.
		"""
		return [item.model for item in self.listWidget.selectedItems()]

	def getSpeciesID(self):
		"""
		Returns which one was selected.
		"""
		return [item.model.SpeciesID for item in self.listWidget.selectedItems()]




Ui_QtBasicLineFitter, QDialog = loadUiType(os.path.join(ui_path, 'QtBasicLineFitter.ui'))
class QtBasicLineFitter(QDialog, Ui_QtBasicLineFitter):
	"""
	Provides a dialog window that for performing basic fits to (multiple)
	lines, where the profiles are only a Gaussian or a 2f-Gaussian.

	Note that this has been superceded by QtProLineFitter, since these routines
	only fit basic analytic models that are not so physically realistic.
	"""
	def __init__(self, x, y):
		"""
		:param x: the x-axis
		:param y: the y-axis
		:type x: list, np.ndarray
		:type y: list, np.ndarray
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.setWindowTitle("QtBasicLineFitter")
		self.setWindowIcon(QtGui.QIcon(os.path.join(ui_path, 'lineprofile.svg')))

		self.btn_fitGaussian.clicked.connect(self.fitGaussian)
		self.btn_fit2f.clicked.connect(self.fit2f)
		self.btn_test.clicked.connect(self.test)
		self.btn_settings.clicked.connect(self.showSettings)
		self.btn_reset.clicked.connect(self.reset)

		self.shortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.accept)

		# init instance containers/lists
		self.dataOrig = {"x":x, "y":y}
		self.mouseClickLabels = []

		# misc parameters that affect the fits
		self.linewidth = 0.3 # MHz
		self.maxit = 50 # maximum number of iterations to try
		self.fit_type = 0 # for scipy.odr.ODR.set_job()
		self.iprint = 0 # for scipy.odr.ODR.set_iprint()

		# init plots
		self.initPlot()


	### top plot functionality
	def initPlot(self):
		"""
		Initializes the plot.
		"""
		# figure properties
		self.fitPlot.setLabel('left', "Intensity", units='arb')
		self.fitPlot.setLabel('bottom', "Frequency", units='Hz')
		self.fitPlot.getAxis('bottom').setScale(scale=1e6)
		# plots
		self.plotOrig = self.fitPlot.plot(
			name='orig', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.plotFit = self.fitPlot.plot(
			name='fit', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.plotFit.setPen(pg.mkPen('g'))
		self.plotRes = self.fitPlot.plot(
			name='residual', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.plotRes.setPen(pg.mkPen('r'))
		# signals
		self.plotSigMouseMove = pg.SignalProxy(
			self.fitPlot.scene().sigMouseMoved,
			rateLimit=30,
			slot=self.plotMousePosition)
		self.plotSigMouseClick = pg.SignalProxy(
			self.fitPlot.scene().sigMouseClicked,
			rateLimit=10,
			slot=self.plotMouseClicked)
		# hover label
		self.mouseHoverLabelAnchor = pg.TextItem(text="*", anchor=(0.5,0.5), fill=(0,0,0,127))
		self.mouseHoverLabelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,127))
		self.fitPlot.addItem(self.mouseHoverLabelAnchor, ignoreBounds=True)
		self.fitPlot.addItem(self.mouseHoverLabelText, ignoreBounds=True)
		# set the data
		self.plotOrig.setData(self.dataOrig["x"], self.dataOrig["y"])
		self.plotOrig.update()

	def plotMousePosition(self, mouseEvent):
		"""
		This is the function that is called each time the mouse cursor
		moves above the fitting plot.

		At the moment, it does nothing.

		:param mouseEvent: the mouse event that is sent by the PlotWidget signal
		:type mouseEvent: tuple(PyQt4.QtCore.QPointF, None)
		"""
		# process keyboard modifiers and perform appropriate action
		modifier = QtGui.QApplication.keyboardModifiers()
		if modifier == QtCore.Qt.ShiftModifier:
			# convert mouse coordinates to XY wrt the plot
			mousePos = self.fitPlot.plotItem.getViewBox().mapSceneToView(mouseEvent[0])
			mouseX, mouseY = mousePos.x(), mousePos.y()
			self.mouseHoverLabelAnchor.setPos(mouseX, mouseY)
			self.mouseHoverLabelText.setPos(mouseX, mouseY)
			self.mouseHoverLabelText.setText("%.1f\n%g" % (mouseX,mouseY))
		else:
			self.mouseHoverLabelAnchor.setPos(0,0)
			self.mouseHoverLabelText.setPos(0,0)
			self.mouseHoverLabelText.setText("")

	def plotMouseClicked(self, mouseEvent):
		"""
		This is the function that is called each time the mouse is
		clicked on the fitting plot.

		At the moment, it does nothing.

		:param mouseEvent: the mouse event that is sent by the PlotWidget signal
		:type mouseEvent: tuple(pyqtgraph.GraphicsScene.mouseEvents.MouseClickEvent, None)
		"""
		mousePos = self.fitPlot.plotItem.getViewBox().mapSceneToView(mouseEvent[0].scenePos())
		mouseX, mouseY = mousePos.x(), mousePos.y()
		modifier = QtGui.QApplication.keyboardModifiers()
		# update mouse label if SHIFT
		if modifier == QtCore.Qt.ShiftModifier:
			labelDot = pg.TextItem(text="*",anchor=(0.5,0.5))
			labelDot.setPos(mouseX, mouseY)
			self.fitPlot.addItem(labelDot, ignoreBounds=True)
			labelText = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,127))
			labelText.setPos(mouseX, mouseY)
			labelText.setText("%.1f\n%g" % (mouseX,mouseY))
			self.fitPlot.addItem(labelText, ignoreBounds=True)
			self.mouseClickLabels.append((labelDot,labelText))

	def fitGaussian(self):
		"""
		Performs a fit to the current data, assuming a model Gaussian
		curve.

		Ref: https://github.com/tiagopereira/python_tips/wiki/Scipy:-curve-fitting
		"""
		if self.check_clearLog.isChecked(): self.txt_log.clear()
		self.txt_log.insertPlainText("\n======================")
		self.txt_log.insertHtml("<br><p>Running a gaussian fit..</p>")
		#results = gauss_lsq(self.dataOrig["x"].copy(), self.dataOrig["y"].copy(),
		#	verbose=True)
		new_y = self.dataOrig["y"].copy()
		fit_y = np.zeros_like(new_y)
		res_y = new_y - fit_y
		x2 = self.dataOrig["x"] - np.mean(self.dataOrig["x"])
		beta0 = [0, self.linewidth, np.max(fit_y)]
		if not len(self.mouseClickLabels):
			ifreq = [np.mean(self.dataOrig["x"])]
			self.txt_log.insertHtml("<br><p>There seems to be no cursors, so will try to fit a line in the center.</p>")
		else:
			ifreq = []
			for labelPair in self.mouseClickLabels:
				ifreq.append(labelPair[0].pos().x())
			self.txt_log.insertHtml("<br><p>Will try to fit line(s) under the marker(s), at the following rest frequencies:<br>%s</p>" % ifreq)
		for f in ifreq:
			beta0[0] = f - np.mean(self.dataOrig["x"])
			self.txt_log.insertHtml("<br><p>Working on f=%s</p>" % f)
			gauss = odr.Model(fit.gauss_func)
			mydata = odr.Data(x2, res_y)
			myodr = odr.ODR(mydata, gauss, beta0=beta0, maxit=self.maxit)
			myodr.set_job(fit_type=self.fit_type)
			if self.iprint:
				myodr.set_iprint(
					init=self.iprint,
					iter=self.iprint,
					final=self.iprint)
			myfit = myodr.run()
			self.txt_log.insertHtml("<br><p>The fit finished:<br>%s</p" % myfit.stopreason[0])
			myfit.beta[0] += np.mean(self.dataOrig["x"])
			#self.txt_log.insertPlainText("\n\nThe coefficients are:")
			#for i,b in enumerate(fit.beta):
			#	fmt = "\n%g +/- %.1e"
			#	self.txt_log.insertPlainText(fmt % (fit.beta[i], fit.sd_beta[i]))
			resultsHTML = "<br><p>The coefficients are:</p>"
			resultsHTML += "<table border='1' cellpadding='5'>"
			resultsHTML += "<tr><td>&nu;</td><td>%.4f &plusmn; %.1e</td></tr>" % (myfit.beta[0], myfit.sd_beta[0])
			resultsHTML += "<tr><td>&Delta;&nu;</td><td>%g &plusmn; %.1e</td></tr>" % (myfit.beta[1], myfit.sd_beta[1])
			resultsHTML += "<tr><td>int</td><td>%.1e &plusmn; %.1e</td></tr>" % (myfit.beta[2], myfit.sd_beta[2])
			resultsHTML += "</table>"
			self.txt_log.insertHtml(resultsHTML)
			new_fit = fit.gauss_func(myfit.beta, self.dataOrig["x"])
			new_y -= new_fit
			fit_y += new_fit
			res_y -= new_fit
			self.plotFit.setData(self.dataOrig["x"], fit_y)
			self.plotFit.update()
			self.plotRes.setData(self.dataOrig["x"], res_y)
			self.plotRes.update()
			self.txt_log.insertPlainText("\n")
			self.txt_log.verticalScrollBar().setValue(
				self.txt_log.verticalScrollBar().maximum())

	def fit2f(self):
		"""
		see fitGaussian()
		"""
		if self.check_clearLog.isChecked(): self.txt_log.clear()
		self.txt_log.insertPlainText("\n======================")
		self.txt_log.insertHtml("<br><p>Running a 2f fit..</p>")
		new_y = self.dataOrig["y"].copy()
		fit_y = np.zeros_like(new_y)
		res_y = new_y - fit_y
		x2 = self.dataOrig["x"] - np.mean(self.dataOrig["x"])
		beta0 = [0, self.linewidth, np.max(fit_y)]#, 0, 0]
		if not len(self.mouseClickLabels):
			ifreq = [np.mean(self.dataOrig["x"])]
			self.txt_log.insertHtml("<br><p>There seems to be no cursors, so will try to fit a line in the center.</p>")
		else:
			ifreq = []
			for labelPair in self.mouseClickLabels:
				ifreq.append(labelPair[0].pos().x())
			self.txt_log.insertHtml("<br><p>Will try to fit line(s) under the marker(s), at the following rest frequencies:<br>%s</p>" % ifreq)
		for f in ifreq:
			beta0[0] = f - np.mean(self.dataOrig["x"])
			self.txt_log.insertHtml("<br><p>Working on f=%s</p>" % f)
			gauss = odr.Model(fit.gauss2f_func)
			mydata = odr.Data(x2, res_y)
			myodr = odr.ODR(mydata, gauss, beta0=beta0, maxit=self.maxit)
			myodr.set_job(fit_type=self.fit_type)
			if self.iprint:
				myodr.set_iprint(
					init=self.iprint,
					iter=self.iprint,
					final=self.iprint)
			myfit = myodr.run()
			self.txt_log.insertHtml("<br><p>The fit finished:<br>%s</p" % myfit.stopreason[0])
			myfit.beta[0] += np.mean(self.dataOrig["x"])
			resultsHTML = "<br><p>The coefficients are:</p>"
			resultsHTML += "<table border='1' cellpadding='5'>"
			resultsHTML += "<tr><td>&nu;</td><td>%.4f &plusmn; %.1e</td></tr>" % (myfit.beta[0], myfit.sd_beta[0])
			resultsHTML += "<tr><td>&Delta;&nu;</td><td>%g &plusmn; %.1e</td></tr>" % (myfit.beta[1], myfit.sd_beta[1])
			resultsHTML += "<tr><td>int</td><td>%.1e &plusmn; %.1e</td></tr>" % (myfit.beta[2], myfit.sd_beta[2])
			#resultsHTML += "<tr><td>y-slope</td><td>%.1e &plusmn; %.1e</td></tr>" % (fit.beta[3], fit.sd_beta[3])
			#esultsHTML += "<tr><td>y-offset</td><td>%.1e &plusmn; %.1e</td></tr>" % (fit.beta[4], fit.sd_beta[4])
			resultsHTML += "</table>"
			self.txt_log.insertHtml(resultsHTML)
			new_fit = fit.gauss2f_func(myfit.beta, self.dataOrig["x"])
			new_y -= new_fit
			fit_y += new_fit
			res_y -= new_fit
			self.plotFit.setData(self.dataOrig["x"], fit_y)
			self.plotFit.update()
			self.plotRes.setData(self.dataOrig["x"], res_y)
			self.plotRes.update()
			self.txt_log.insertPlainText("\n")
			self.txt_log.verticalScrollBar().setValue(
				self.txt_log.verticalScrollBar().maximum())

	def showSettings(self):
		"""
		Loads the current 'Advanced Settings' into a ScrollableSettingsWindow
		"""
		advSettingsWindow = ScrollableSettingsWindow(self, self.setSettings)
		advSettingsWindow.addRow(
			"linewidth", "Initial guess for the line width",
			self.linewidth, "MHz")
		hoverText = "0 -> no report\n1 -> short report\n2 -> long report"
		advSettingsWindow.addRow(
			"maxit", "Maximum number of fit iterations",
			self.maxit, "(none)", hover=hoverText)
		hoverText = "0 -> explicit ODR\n1 -> implicit ODR\n2 -> ordinary least-squares"
		advSettingsWindow.addRow(
			"fit_type", "The fit type",
			self.fit_type, "(none)", hover=hoverText)
		advSettingsWindow.addRow(
			"iprint", "The verbosity (terminal only!) of the ODRPACK routine",
			self.iprint, "(none)")
		if advSettingsWindow.exec_():
			pass
	def setSettings(self, advsettings):
		"""
		Updates 'Advanced Settings' from the ScrollableSettingsWindow.

		Note that this should only be directly called from the ScrollableSettingsWindow.

		:param advsettings: the dictionary containing all the new parameters from the ScrollableSettingsWindow
		:type advsettings: dict
		"""
		from numpy import rint
		def to_float(lineedit):
			"""
			Provides a helper routine that converts the entry of a LineEdit
			object to a floating point.

			Note that this simply reduces lots of otherwise duplicate code
			for the repetitive processing of parameters.

			:param lineedit: the LineEdit PyQT object
			:type lineedit: QtGui.LineEdit
			:returns: the floating point value
			:rtype: float
			"""
			text = lineedit.text()
			return float(text)
		def to_int(lineedit):
			"""
			Provides a helper routine that converts the entry of a LineEdit
			object to a rounded integer.

			Note that this simply reduces lots of otherwise duplicate code
			for the repetitive processing of parameters.

			:param lineedit: the LineEdit PyQT object
			:type lineedit: QtGui.LineEdit
			:returns: the rounded integer
			:rtype: int
			"""
			text = lineedit.text()
			return int(rint(float(text)))
		self.linewidth = to_float(advsettings["linewidth"])
		self.maxit = to_int(advsettings["maxit"])
		self.fit_type = to_int(advsettings["fit_type"])
		self.iprint = to_int(advsettings["iprint"])

	def reset(self):
		"""
		Clears fit constants and plot labels, as if starting from scratch.
		"""
		# clear log
		if self.check_clearLog.isChecked():
			self.txt_log.clear()
		# clear fit
		self.plotFit.setData([], [])
		self.plotFit.update()
		self.plotRes.setData([], [])
		self.plotRes.update()
		# clear labels
		for items in self.mouseClickLabels:
			self.fitPlot.removeItem(items[0])
			self.fitPlot.removeItem(items[1])
		self.mouseClickLabels = []

	def test(self):
		log.debug("QtBasicLineFitter.test() does nothing at the moment...")


Ui_QtProLineFitter, QDialog = loadUiType(os.path.join(ui_path, 'QtProLineFitter.ui'))
class QtProLineFitter(QDialog, Ui_QtProLineFitter):
	"""
	Provides a dialog window that for performing fits to a variety
	of line profiles, including the speed-dependent profiles discussed
	by Luca Dore in his 2003 manuscript (Dore, L., J. Mol. Spec., 2003).
	"""
	fitFinishedSignal = QtCore.pyqtSignal()
	newFitSignal = QtCore.pyqtSignal(dict)
	fit_methods = [
		"trf", # Trust Region Reflective algorithm
		"dogbox", # dogleg algorithm with rectangular trust regions
		"lm"] # Levenberg-Marquardt algorithm as implemented in MINPACK
	fit_types = [
		"blank", "boxcar", # test functions
		"gauss", "gauss2f", "lorentzian", "lorentzian2f", # analytic functions
		"voigt", "voigt2f", "galatry2f", "sdvoigt2f", "sdgalatry2f"] # the Dore2003 convolutions
	def __init__(self, parent=None, spec=None, x=None, y=None, filename=None, cursorxy=()):
		"""
		:param parent: (optional) the parent GUI
		:param spec: (optional) the spectrum for initialization
		:param x: (optional) the x-axis for initialization
		:param y: (optional) the y-axis for initialization
		:param filename: (optional) the filename to use for loading a spectrum
		:type parent: QtGui.QMainWindow
		:type spec: pyLabSpec.spectrum.Spectrum
		:type x: list, np.ndarray
		:type y: list, np.ndarray
		:type filename: str
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.setWindowTitle("QtProLineFitter")
		self.setWindowIcon(QtGui.QIcon(os.path.join(ui_path, 'lineprofile.svg')))
		self.parent = parent
		self.debug = False
		
		if distutils.version.LooseVersion(scipy.__version__) < "0.17":
			msg = "ERROR: your scipy version is outdated, and thus the "
			msg += "scipy.optimize.least_squares() method is not available!"
			msg += "\n\ncurrent version: %s" % scipy.__version__
			msg += "\nrequired version: >0.17"
			raise ImportError(msg)

		# button functionality
		self.btn_loadConf.clicked.connect(self.loadConf)
		self.btn_saveConf.clicked.connect(self.saveConf)
		self.btn_getProfiles.clicked.connect(self.getProfiles)
		self.btn_loadSpec.clicked.connect(self.loadSpec)
		self.btn_fit.clicked.connect(self.fit)
		self.btn_fitMulti.clicked.connect(self.fitMulti)
		self.btn_fitAll2f.clicked.connect(self.fitAll2f)
		#self.btn_test.clicked.connect(self.test)
		self.btn_clearLabels.clicked.connect(self.clearLabels)
		self.btn_reset.clicked.connect(self.reset)
		self.btn_quit.clicked.connect(self.quit)
		# others
		# self.combo_fitFunction.currentIndexChanged is set after it is populated
		self.txt_temperature.textChanged.connect(self.physParamChanged)
		self.txt_pressure.textChanged.connect(self.physParamChanged)
		self.txt_mass.textChanged.connect(self.physParamChanged)

		### add tooltips
		# main buttons
		self.btn_getProfiles.setToolTip(
			"Plots all the available line profiles."
			"\nNote that this will reset the plot.")
		self.btn_reset.setToolTip(
			"Clears the fits and log/table contents, and reloads the spectrum."
			"\ntip: holding SHIFT will not reload the spectrum..")
		self.btn_fit.setToolTip(
			"Runs a fit on the loaded spectrum, using all the settings from the parameter tab.")
		# parameter tab
		self.tabWidget.setCurrentWidget(self.tab_parameters)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Parameters</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Allows fine control of all the input parameters necessary for each possible line profile.
				For more details about some parameters, hover the mouse above their labels.
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- fits must be initialized with reasonably-guessed parameters<br/>
				- constrained fits are possible for each line profile type<br/>
				- switching the fit function will disable/enable which parameters are used
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Tab - cycle through the elements/parameters<br/>
				Ctrl+PgUp/PgDown - cycle through the tabs<br/>
				Ctrl+[Shift]+Tab - cycle through the tabs<br/>
				Escape - exits the GUI<br/>
				Delete - clears the labels from the plot<br/>
				Shift+Delete - removes any/all labels, loaded spectra, profile simulations (i.e. reset)<br/>
				Ctrl+Z - remove the most recently added plot label<br/>
				Ctrl+L - load a spectrum<br/>
				Ctrl+F - run a fit<br/>
				Ctrl+Shift+F - run a multi-line fit<br/>
				Ctrl+T - run the test routine (development only)<br/>
				Ctrl+Shift+T - run the 'shifted' test routine (development only)<br/>
				Ctrl+P - launch the matplotlib-based plot designer
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts:</span><br/>
				(nothing special)
			</p>
			</body></html>
			""")
		self.check_useMultParams.setToolTip(
			"If checked, the fit coefficients (and phase detuning) will be split and used"
			"\nuniquely across all fitted line profiles. Variable names will be suffixed"
			"\nwith numbers, to reference individual profiles.")
		self.label_fitMethod.setToolTip(
			"Select the fit method for scipy.optimize.least_squares(). See scipy docs for more"
			"\ndetails, but briefly:"
			"\n- 'trf' uses the 'Trust Region Reflective' algorithm and respects bounds"
			"\n- 'dogbox' is similar to 'trf' but doesn't converge so well"
			"\n- 'lm' uses the Levenberg-Marquardt algorithm, but respects no bounds and may"
			"\n  give inappropriate values for this universe..")
		self.label_fitFscale.setToolTip(
			"If empty, the 'tfr' and 'dogbox' methods use a linear loss function, otherwise"
			"\na number here will activate the 'soft_l1' loss function and use this"
			"\nvalue for C (see the docs for scipy.optimize.least_squares for details).")
		self.label_harmonic.setToolTip(
			"This is only used for choosing which profiles to show with"
			"\nthe button 'get profiles'.")
		self.label_oversample.setToolTip(
			"This is for running a fit with oversampled axis, for testing"
			"\nfitted accuracy/resolution, but it's not implemented at all..")
		self.label_windowSize.setToolTip(
			"This defines how much of the x-axis to use, centered around the labeled"
			"\nline profiles. If the checkbox is set to 'use' it, you can specify the"
			"\nmanual size, otherwise it just uses the current view range of the plot.")
		self.label_velColl.setToolTip(
			"The collisional relaxation rate, i.e. the Lorentzian half-width.")
		self.label_velDopp.setToolTip(
			"The 1/e Doppler half-width from inhomogeneous broadening.")
		self.label_coeffNar.setToolTip(
			"The narrowing coefficient z that relates the dynamic friction coefficient β"
			"\n(based itself on a diffusion coefficient) to the Doppler coefficient."
			"\nUsed for line profiles based on the work of Galatry.")
		self.label_velSD.setToolTip(
			"The speed-dependent relaxation rate.")
		msg = """
			This is used for fitting to a baseline. The letters a,b,c, & d
			are used for choosing which orders to allow as a baseline. One
			may keep these letters, or even provide initial guesses for each
			order. When using numbers, you must also include the multiplication
			of the x (frequency) variable/axis. For each order, the parser
			looks first for a floating point number and then the corresponding
			letter if no initial value is found.. it should be very flexible.
			
			Here are some possible examples:
			\tonly a y-offset would look like: 'a' or -0.0004 or 3.4e5
			\ta linear baseline would look like: 'ab' or 'a,b' or 'a+b*x'
			\ta parabola would look like: 'c'
			\ta full polynomial to 3rd order could be:
			\t\t'a + b*x + c*x^2 + d*x^3' or '135e-6 + 8.2e-7*x + -7e-7*x^2 + d'
			"""
		self.label_polynom.setToolTip(msg.replace("\t\t\t",""))
		msg = "PRO TIP: hold SHIFT to change/choose a filename"
		self.btn_loadConf.setToolTip(msg)
		self.btn_saveConf.setToolTip(msg)
		self.txt_confFile.setToolTip("Specifies a file to use for saving/loading a set of parameters..")
		# plot tab
		self.tabWidget.setCurrentWidget(self.tab_plot)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Plot</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Allows one to load/view a spectrum, as well as the fitted line profiles.
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- load a spectrum<br/>
				- view a fitted profile
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Ctrl+PgUp/PgDown - cycle through the tabs<br/>
				Ctrl+[Shift]+Tab - cycle through the tabs<br/>
				Escape - exits the GUI<br/>
				Delete - clears the labels from the plot<br/>
				Shift+Delete - removes any/all labels, loaded spectra, profile simulations (i.e. reset)<br/>
				Ctrl+Z - remove the most recently added plot label<br/>
				Ctrl+L - load a spectrum<br/>
				Ctrl+F - run a fit<br/>
				Ctrl+Shift+F - run a multi-line fit<br/>
				Ctrl+T - run the test routine (development only)<br/>
				Ctrl+Shift+T - run the 'shifted' test routine (development only)<br/>
				Ctrl+P - launch the matplotlib-based plot designer
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts:</span><br/>
				Shift/Ctrl+Hover - View XY coordinates under the mouse<br/>
				Shift+LeftClick - Add a new XY label (for multi-component fits)<br/>
				Ctrl+LeftClick - Add/move a single XY label (for a single fit or start new multi-line points)<br/>
				LeftClick+Drag - Pan the plot<br/>
				RightClick - View plot menu<br/>
				RightClick+Drag - Zoom the plot
			</p>
			</body></html>
			""")
		# log tab
		self.tabWidget.setCurrentWidget(self.tab_log)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Log</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Contains the output from a line profile fit by way of (hopefully) human-readable
				text. The output is a combination of formatted/processed results, as well as
				output directly from the internal solver. Should be most useful during errors
				or problems or questional results.
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- selectable ascii text<br/>
				- output from solver routines are accessible, even if no terminal is available
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Ctrl+PgUp/PgDown - cycle through the tabs<br/>
				Ctrl+[Shift]+Tab - cycle through the tabs<br/>
				Escape - exits the GUI<br/>
				Delete - clears the labels from the plot<br/>
				Shift+Delete - removes any/all labels, loaded spectra, profile simulations (i.e. reset)<br/>
				Ctrl+Z - remove the most recently added plot label<br/>
				Ctrl+L - load a spectrum<br/>
				Ctrl+F - run a fit<br/>
				Ctrl+Shift+F - run a multi-line fit<br/>
				Ctrl+T - run the test routine (development only)<br/>
				Ctrl+Shift+T - run the 'shifted' test routine (development only)<br/>
				Ctrl+P - launch the matplotlib-based plot designer
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts:</span><br/>
				(nothing special)
			</p>
			</body></html>
			""")
		# table tab
		self.tabWidget.setCurrentWidget(self.tab_table)
		self.tabWidget.setTabToolTip(self.tabWidget.currentIndex(), """
			<html><head/><body>
			<p>
				<span style=" font-weight:600;">Table</span>
			</p>
			<p>
				<span style=" font-style:italic;">Usage:</span><br/>
				Contains the output from a line profile fit in the form of a spreadsheet. This
				should be most useful during a multi-component fit, where the parameters for each
				component can be seen side-by-side.
			</p>
			<p>
				<span style=" font-style:italic;">Features:</span><br/>
				- selectable table of fitted parameters
			</p>
			<p>
				<span style=" font-style:italic;">Keyboard Shortcuts:</span><br/>
				Ctrl+PgUp/PgDown - cycle through the tabs<br/>
				Ctrl+[Shift]+Tab - cycle through the tabs<br/>
				Escape - exits the GUI<br/>
				Delete - clears the labels from the plot<br/>
				Shift+Delete - removes any/all labels, loaded spectra, profile simulations (i.e. reset)<br/>
				Ctrl+Z - remove the most recently added plot label<br/>
				Ctrl+L - load a spectrum<br/>
				Ctrl+F - run a fit<br/>
				Ctrl+Shift+F - run a multi-line fit<br/>
				Ctrl+T - run the test routine (development only)<br/>
				Ctrl+Shift+T - run the 'shifted' test routine (development only)<br/>
				Ctrl+P - launch the matplotlib-based plot designer
			</p>
			<p>
				<span style=" font-style:italic;">Mouse Shortcuts:</span><br/>
				(nothing special)
			</p>
			</body></html>
			""")


		# keyboard shortcuts
		self.keyShortcutCtrlL = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+L"), self, self.loadSpec)
		self.keyShortcutCtrlF = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+F"), self, self.fit)
		self.keyShortcutCtrlShiftF = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+F"), self, self.fitMulti)
		self.keyShortcutCtrlT = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+T"), self, self.test)
		self.keyShortcutCtrlP = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+P"), self, self.launchPlotDesigner)
		self.keyShortcutCtrlZ = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Z"), self, partial(self.clearLabels, onlyLastOne=True))
		self.keyShortcutCtrlShiftT = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+T"), self, partial(self.test, shift=True))
		self.keyShortcutCtrlPgUp = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+PgUp"), self, self.tabPrev)
		self.keyShortcutCtrlPgDn = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+PgDown"), self, self.tabNext)
		self.keyShortcutCtrlTab = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Tab"), self, self.tabNext)
		self.keyShortcutCtrlShiftTab = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+Shift+Tab"), self, self.tabPrev)
		self.keyShortcutDelete = QtGui.QShortcut(QtGui.QKeySequence("Delete"), self, self.clearLabels)
		self.keyShortcutShiftDelete = QtGui.QShortcut(QtGui.QKeySequence("Shift+Delete"), self, self.reset)
		self.keyShortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, partial(self.quit, confirm=False))

		# gui elements/containers
		self.plots = []
		self.plotLabels = []
		self.fitLabels = []
		self.spectrum = None
		for m in self.fit_methods:
			self.combo_fitMethod.addItem(m)
		for t in self.fit_types:
			self.combo_fitFunction.addItem(t)
		self.combo_fitFunction.setCurrentIndex(self.fit_types.index("voigt2f"))
		self.combo_fitFunction.currentIndexChanged.connect(self.fitFunctionChanged)
		self.txt_mass.opts.update({"constStep":1, "relStep":None, "formatString":"%g"})
		self.HTMLCoordinates = "<div style='text-align:left'><span style='font-size: 14pt'>x=%.1f"
		self.HTMLCoordinates += "<br>y=%g</span></div>"
		self.HTMLFitFreq = "<div style='text-align:left'>"
		self.HTMLFitFreq += "<span style='font-size:14pt;color:yellow'>"
		self.HTMLFitFreq += "%.5f +/- %7.2e</span></div>"

		# initializations
		self.init_misc()
		self.init_plot()
		self.init_text()
		self.init_table()
		if spec is not None:
			self.loadSpec(spec=spec)
		elif all([axis is not None for axis in (x, y)]):
			self.loadSpec(x=x, y=y)
		elif filename is not None:
			self.loadSpec(filename=filename)
		self.tabWidget.setCurrentWidget(self.tab_plot)
		
		# provide file loading from drag-and-drop
		for itemForDragIn in (
				self.btn_loadSpec,
				self.plotWidget,
				self.plotWidget.plotItem.vb
			):
			itemForDragIn.setAcceptDrops(True)
			itemForDragIn.dragEnterEvent = self.dragEnterEvent
			itemForDragIn.dropEvent = self.dropEvent
		
		if cursorxy is not ():
			self.addPlotLabel(cursorxy[0], cursorxy[1])

	def tabNext(self, inputEvent=None):
		currentIdx = self.tabWidget.currentIndex()
		self.tabWidget.setCurrentIndex(currentIdx+1)
	def tabPrev(self, inputEvent=None):
		currentIdx = self.tabWidget.currentIndex()
		self.tabWidget.setCurrentIndex(currentIdx-1)

	def init_misc(self):
		"""
		initializes the misc tab
		"""
		pass

	def init_plot(self):
		"""
		initializes the plot tab
		"""
		self.plotWidget.setLabel('left', "arb")
		self.plotWidget.setLabel('bottom', "x-axis", units='Hz')
		self.plotWidget.getAxis('bottom').setScale(scale=1e6)
		self.plotLegend = Widgets.LegendItem(offset=(30, 30))
		self.plotWidget.getPlotItem().legend = self.plotLegend
		self.plotLegend.setParentItem(self.plotWidget.getPlotItem().vb)
		# signals for interacting with the mouse
		self.plotMouseHoverDot = pg.TextItem(text="*", anchor=(0.5,0.5), fill=(0,0,0,100))
		self.plotMouseHoverXY = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
		self.plotMouseHoverDot.setZValue(999)
		self.plotMouseHoverXY.setZValue(999)
		self.plotWidget.addItem(self.plotMouseHoverDot, ignoreBounds=True)
		self.plotWidget.addItem(self.plotMouseHoverXY, ignoreBounds=True)
		self.plotMouseMoveSignal = pg.SignalProxy(
			self.plotWidget.plotItem.scene().sigMouseMoved,
			rateLimit=15,
			slot=self.plotMousePosition)
		self.plotMouseClickSignal = pg.SignalProxy(
			self.plotWidget.plotItem.scene().sigMouseClicked,
			rateLimit=5,
			slot=self.plotMouseClicked)
		# menu entries for copying to clipboard
		menu = self.plotWidget.plotItem.getViewBox().menu
		menu.addSeparator()
		copyExp = menu.addAction("copy spectrum")
		copyExp.triggered.connect(partial(self.copyPlot, plot="exp"))
		copyFit = menu.addAction("copy fit")
		copyFit.triggered.connect(partial(self.copyPlot, plot="fit"))
		copyRes = menu.addAction("copy residual")
		copyRes.triggered.connect(partial(self.copyPlot, plot="res"))

	def loadConf(self, inputEvent=None, filename=None):
		# define filename
		if filename is not None:
			pass
		elif QtGui.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
			filename = QtGui.QFileDialog.getOpenFileName(
				parent=self, caption='Open configuration file',
				filter='YAML files (*.yml)')
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5.0.0":
				filename = str(filename[0])
			else:
				filename = str(filename)
			if not os.path.isfile(filename):
				return
			self.txt_confFile.setText(filename)
		else:
			filename = str(self.txt_confFile.text())
		filename = os.path.expanduser(filename) # in case it has a tilda
		# make sure pyyaml works, so print message can help the user
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
			data = yaml.full_load(open(filename, 'r'))
		except:
			data = yaml.load(open(filename, 'r'))
		# apply settings
		checkboxes = [
			"showFitFreqLabels", "calcPairAvgCen", "useMultParams",
			"showGuess", "showDebaselined"
		]
		for check in checkboxes:
			if check in data:
				try:
					getattr(self, "check_%s" % check).setChecked(bool(data[check]))
				except:
					log.exception("(QtProLineFitter) there was an error applying %s" % check)
		if ("fitMethod" in data) and (data["fitMethod"] in self.fit_methods):
			idx = self.fit_methods.index(data["fitMethod"])
			self.combo_fitMethod.setCurrentIndex(idx)
		if "fitFscale" in data:
			self.txt_fitFscale.setText(data["fitFscale"])
		if ("fitFunction" in data) and (data["fitFunction"] in self.fit_types):
			idx = self.fit_types.index(data["fitFunction"])
			self.combo_fitFunction.setCurrentIndex(idx)
		if "harmonic" in data:
			self.txt_harmonic.setText(data["harmonic"])
		# collect parameters
		paramNames = [
			"oversample", "windowSize", "freqCenter",
			"tauRad", "temperature", "pressure", "mass",
			"fwhm", "velColl", "velDopp", "coeffNar", "velSD",
			"modDepth", "modRate", "phi", "polynom"
		]
		stdElements = ["check_%sLock", "txt_%sMin", "txt_%sMax"]
		for p in paramNames:
			pUse = "%sUse" % p
			if pUse in data:
				try:
					getattr(self, "check_%s" % pUse).setChecked(bool(data[pUse]))
				except:
					log.exception("(QtProLineFitter) there was an error applying %s" % pUse)
			pInit = "%sInit" % p
			if pInit in data:
				try:
					getattr(self, "txt_%s" % p).setText(data[pInit])
				except:
					log.exception("(QtProLineFitter) there was an error applying %s" % pInit)
			data["%sUse" % p] = getattr(self, "check_%sUse" % p).isChecked()
			data["%sInit" % p] = str(getattr(self, "txt_%s" % p).text())
			for e in stdElements:
				eName = e % p
				try:
					if (eName[:3] == "txt") and hasattr(self, eName) and (eName in data):
						getattr(self, eName).setText(data[eName[4:]])
					elif (eName[:5] == "check") and hasattr(self, eName) and (eName in data):
						getattr(self, eName).setChecked(bool(data[eName[6:]]))
				except:
					log.exception("(QtProLineFitter) there was an error applying %s" % eName)
	def saveConf(self, inputEvent=None):
		# define filename
		if QtGui.QApplication.keyboardModifiers() == QtCore.Qt.ShiftModifier:
			directory = os.getcwd()
			filename = str(self.txt_confFile.text())
			if len(filename):
				filename = os.path.expanduser(filename)
				directory = os.path.dirname(filename)
			filename = QtGui.QFileDialog.getSaveFileName(
				parent=self, caption='Select output file',
				directory=directory, filter='YAML files (*.yml)')
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5.0.0":
				filename = str(filename[0])
			else:
				filename = str(filename)
			if not len(filename):
				return
			if not filename[-4:] == ".yml":
				filename += ".yml"
			self.txt_confFile.setText(filename)
		else:
			filename = str(self.txt_confFile.text())
		filename = os.path.expanduser(filename) # in case it has a tilda
		# make sure pyyaml works, so print message can help the user
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
		# collect settings
		data = {}
		data["showFitFreqLabels"] = self.check_showFitFreqLabels.isChecked()
		data["calcPairAvgCen"] = self.check_calcPairAvgCen.isChecked()
		data["useMultParams"] = self.check_useMultParams.isChecked()
		data["showGuess"] = self.check_showGuess.isChecked()
		data["fitMethod"] = str(self.combo_fitMethod.currentText())
		data["fitFscale"] = str(self.txt_fitFscale.text())
		data["fitFunction"] = str(self.combo_fitFunction.currentText())
		data["harmonic"] = str(self.txt_harmonic.text())
		data["showDebaselined"] = self.check_showDebaselined.isChecked()
		# collect parameters
		paramNames = [
			"oversample", "windowSize", "freqCenter",
			"tauRad", "temperature", "pressure", "mass",
			"fwhm", "velColl", "velDopp", "coeffNar", "velSD",
			"modDepth", "modRate", "phi", "polynom"
		]
		stdElements = ["check_%sLock", "txt_%sMin", "txt_%sMax"]
		for p in paramNames:
			data["%sUse" % p] = getattr(self, "check_%sUse" % p).isChecked()
			data["%sInit" % p] = str(getattr(self, "txt_%s" % p).text())
			for e in stdElements:
				eName = e % p
				if eName[:3] == "txt" and hasattr(self, eName):
					data[eName[4:]] = str(getattr(self, eName).text())
				elif eName[:5] == "check" and hasattr(self, eName):
					data[eName[6:]] = getattr(self, eName).isChecked()
		# dump them to file
		log.info("(QtProLineFitter) saving the current configuration to '%s'" % filename)
		fh = open(filename, 'w')
		header = """#
		# DESCRIPTION
		# This is a configuration file for pyLabSpec's QtProLineFitter.
		# The format is YAML (1), which "may be the most human friendly
		# format for structured data invented so far" (2).
		#
		# REFS
		# 1: https://yaml.org/
		# 2: https://wiki.python.org/moin/YAML
		#
		# You may modify it yourself, but it is automatically saved when
		# you close a profitter UI.
		#
		"""
		header = header.replace('\t', '')
		header += "# CREATED: %s\n#\n" % (datetime.datetime.now())
		fh.write(header)
		yaml.dump(data, fh)
		fh.close()

	def copyPlot(self, plot="fit"):
		"""
		Provides a routine that copies the desired plot data to the
		clipboard.
		
		:param plot: the name of the plot to copy (default: fit)
		:type plot: str
		"""
		# initialize some things..
		fullText = ""
		clipboard = QtGui.QApplication.clipboard()
		# identify plot and copy its data
		plotText = ""
		for p in self.plots:
			if p.name() == plot:
				plotText += "#%s\n" % p.name()
				for i in zip(p.xData, p.yData):
					plotText += "%s,%s\n" % (i[0], i[1])
				break
		# combine data
		fullText += plotText
		clipboard.setText(fullText)

	def plotMousePosition(self, mouseEvent):
		"""
		Updates whenever the mouse moves above the plot
		
		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# process keyboard modifiers and perform appropriate action
		modifier = QtGui.QApplication.keyboardModifiers()
		if modifier in (QtCore.Qt.ShiftModifier, QtCore.Qt.ControlModifier):
			# convert mouse coordinates to XY wrt the plot
			mousePos = self.plotWidget.plotItem.getViewBox().mapSceneToView(mouseEvent[0])
			mouseX, mouseY = mousePos.x(), mousePos.y()
			self.plotMouseHoverDot.setPos(mouseX, mouseY)
			self.plotMouseHoverXY.setPos(mouseX, mouseY)
			self.plotMouseHoverXY.setText("  %.1f\n%g" % (mouseX,mouseY))
		else:
			self.plotMouseHoverDot.setPos(0, 0)
			self.plotMouseHoverXY.setPos(0, 0)
			self.plotMouseHoverXY.setText("")
	def plotMouseClicked(self, mouseEvent):
		"""
		Updates whenever the mouse is clicked on the plot
		
		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# convert mouse coordinates to XY wrt the plot
		screenPos = mouseEvent[0].screenPos()
		mousePos = mouseEvent[0].scenePos()
		viewBox = self.plotWidget.plotItem.getViewBox()
		mousePos = viewBox.mapSceneToView(mousePos)
		mouseX, mouseY = mousePos.x(), mousePos.y()
		modifier = QtGui.QApplication.keyboardModifiers()
		# add the XY label if SHIFT
		if (modifier == QtCore.Qt.ShiftModifier):
			self.addPlotLabel(x=mouseX, y=mouseY)
		elif (modifier == QtCore.Qt.ControlModifier):
			self.clearLabels()
			self.addPlotLabel(x=mouseX, y=mouseY)
	def addPlotLabel(self, x=None, y=None):
		"""
		Called from plotMouseClicked().. adds a plot label to the x,y.
		
		:param x: the x-coordinate for the new label
		:param y: the y-coordinate for the new label
		:type x: int
		:type y: int
		"""
		if (x is None) and (y is None):
			return
		dot = pg.TextItem(text="*", anchor=(0.5,0.5), fill=(0,0,0,100))
		coordinates = pg.TextItem(text="", anchor=(0,0), fill=(0,0,0,100))
		dot.setZValue(999)
		coordinates.setZValue(999)
		dot.setPos(x, y)
		coordinates.setPos(x, y)
		coordinates.setHtml(self.HTMLCoordinates % (x, y))
		self.plotWidget.addItem(dot, ignoreBounds=True)
		self.plotWidget.addItem(coordinates, ignoreBounds=True)
		self.plotLabels.append((dot,coordinates))

	def dragEnterEvent(self, inputEvent):
		if hasattr(inputEvent, "mimeData") and inputEvent.mimeData().hasUrls:
			inputEvent.accept()
		else:
			inputEvent.ignore()
	def dropEvent(self, inputEvent=None):
		urls = inputEvent.mimeData().urls()
		if not len(urls) == 1:
			return
		filename = urls[0].toLocalFile()
		self.loadSpec(filename=filename, settings=None)

	def init_text(self):
		"""
		initializes the text tab
		"""
		font = QtGui.QFont()
		font.setFamily('Mono')
		self.textEdit.setFont(font)

	def init_table(self):
		"""
		initializes the table tab
		"""
		self.tableWidget.setRowCount(0)
		self.tableWidget.setColumnCount(4)
		headerLabels = ["Fit Type", "Cen. Freq.", "Freq. Unc.", "Fit Message"]
		self.tableWidget.setHorizontalHeaderLabels(headerLabels)

	def clearPlots(self, skipFirst=False):
		"""
		clears all the plot items from the plot
		
		:param skipFirst: (optional) whether to skip the first item in the plot (i.e. the spectrum) (default: False)
		:type skipFirst: bool
		"""
		startIdx = 0
		if skipFirst: startIdx += 1
		# clear plots
		for p in self.plots[startIdx:]:
			self.plotWidget.removeItem(p)
			self.plotLegend.removeItem(p.name())
		self.plots = self.plots[:startIdx]
	def clearLabels(self, fitOnly=False, onlyLastOne=False):
		"""
		resets the label elements

		:param fitOnly: (bool) whether to clear only the labels related to a fitted profile (default: False)
		:type fitOnly: bool
		:param onlyLastOne: (bool) whether to clear only the most recently-added label (default: False)
		:type onlyLastOne: bool
		"""
		if not fitOnly:
			self.plotMouseHoverDot.setPos(0, 0)
			self.plotMouseHoverXY.setPos(0, 0)
			self.plotMouseHoverXY.setText("")
			if onlyLastOne:
				self.plotWidget.removeItem(self.plotLabels[-1][0])
				self.plotWidget.removeItem(self.plotLabels[-1][1])
				self.plotLabels = self.plotLabels[:-1]
			else:
				for labels in self.plotLabels:
					self.plotWidget.removeItem(labels[0])
					self.plotWidget.removeItem(labels[1])
				self.plotLabels = []
		for label in self.fitLabels:
			self.plotWidget.removeItem(label)
		self.fitLabels = []
	def clearTable(self):
		"""
		clears all the plot items from the plot
		"""
		self.init_table()

	def reset(self, mouseEvent=None, reloadSpec=True):
		"""
		Resets the GUI data, plots, and text contents.
		
		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		:param reloadSpec: whether to reset/reload the spectrum
		:type reloadSpec: bool
		"""
		modifier = QtGui.QApplication.keyboardModifiers()
		if (modifier == QtCore.Qt.ShiftModifier):
			reloadSpec = False
		if not reloadSpec:
			self.spectrum = None
		self.clearPlots()
		self.clearLabels()
		self.clearTable()
		self.textEdit.clear()
		if reloadSpec:
			self.loadSpec(spec=self.spectrum)

	def fitFunctionChanged(self, newIndex=None):
		"""
		This function is called whenever the desired profile type is changed.
		
		It will set active/inactive the bare minimum input parameters
		required for a given line profile fit.
		
		:param newIndex: (optional) the new index of the combobox
		:type newIndex: int
		"""
		def updateCheckBox(name, checkState):
			myCheckBox = getattr(self, 'check_%sUse' % name)
			myCheckBox.setChecked(checkState)
		newProfile = self.combo_fitFunction.currentText()
		if newProfile == "blank":
			updateCheckBox("tauRad", False)
			#updateCheckBox("temperature", False)
			#updateCheckBox("pressure", False)
			updateCheckBox("fwhm", False)
			updateCheckBox("velColl", False)
			updateCheckBox("velDopp", False)
			updateCheckBox("coeffNar", False)
			updateCheckBox("velSD", False)
			updateCheckBox("modDepth", False)
			updateCheckBox("modRate", False)
		if newProfile == "boxcar":
			updateCheckBox("tauRad", False)
			#updateCheckBox("temperature", False)
			#updateCheckBox("pressure", False)
			updateCheckBox("fwhm", True)
			updateCheckBox("velColl", False)
			updateCheckBox("velDopp", False)
			updateCheckBox("coeffNar", False)
			updateCheckBox("velSD", False)
			updateCheckBox("modDepth", False)
			updateCheckBox("modRate", False)
		if newProfile in ("gauss", "gauss2f", "lorentzian", "lorentzian2f"):
			updateCheckBox("tauRad", False)
			#updateCheckBox("temperature", False)
			#updateCheckBox("pressure", False)
			updateCheckBox("fwhm", True)
			updateCheckBox("velColl", False)
			updateCheckBox("velDopp", False)
			updateCheckBox("coeffNar", False)
			updateCheckBox("velSD", False)
			updateCheckBox("modDepth", False)
			updateCheckBox("modRate", False)
		if newProfile == "voigt":
			updateCheckBox("tauRad", False)
			#updateCheckBox("temperature", False)
			#updateCheckBox("pressure", False)
			updateCheckBox("fwhm", False)
			updateCheckBox("velColl", True)
			updateCheckBox("velDopp", True)
			updateCheckBox("coeffNar", False)
			updateCheckBox("velSD", False)
			updateCheckBox("modDepth", False)
			updateCheckBox("modRate", False)
		if newProfile == "voigt2f":
			updateCheckBox("tauRad", False)
			#updateCheckBox("temperature", False)
			#updateCheckBox("pressure", False)
			updateCheckBox("fwhm", False)
			updateCheckBox("velColl", True)
			updateCheckBox("velDopp", True)
			updateCheckBox("coeffNar", False)
			updateCheckBox("velSD", False)
			updateCheckBox("modDepth", True)
			updateCheckBox("modRate", True)
		if newProfile == "galatry2f":
			updateCheckBox("tauRad", False)
			#updateCheckBox("temperature", False)
			#updateCheckBox("pressure", False)
			updateCheckBox("fwhm", False)
			updateCheckBox("velColl", True)
			updateCheckBox("velDopp", True)
			updateCheckBox("coeffNar", True)
			updateCheckBox("velSD", False)
			updateCheckBox("modDepth", True)
			updateCheckBox("modRate", True)
		if newProfile == "sdvoigt2f":
			updateCheckBox("tauRad", False)
			#updateCheckBox("temperature", False)
			#updateCheckBox("pressure", False)
			updateCheckBox("fwhm", False)
			updateCheckBox("velColl", True)
			updateCheckBox("velDopp", True)
			updateCheckBox("coeffNar", False)
			updateCheckBox("velSD", True)
			updateCheckBox("modDepth", True)
			updateCheckBox("modRate", True)
		if newProfile == "sdgalatry2f":
			updateCheckBox("tauRad", False)
			#updateCheckBox("temperature", False)
			#updateCheckBox("pressure", False)
			updateCheckBox("fwhm", False)
			updateCheckBox("velColl", True)
			updateCheckBox("velDopp", True)
			updateCheckBox("coeffNar", True)
			updateCheckBox("velSD", True)
			updateCheckBox("modDepth", True)
			updateCheckBox("modRate", True)
	def physParamChanged(self, inputEvent):
		"""
		This function is called whenever one of the physical parameters
		has changed (pressure, temperature, mass).
		
		It will check which parameter has changed. If it's set to be
		active, it will also update the spectral parameters which may
		be estimated from it.
		
		:param paramField: the text field of the input parameter
		:type paramField: Widgets.ScrollableText
		"""
		useTemp = self.check_temperatureUse.isChecked()
		usePressure = self.check_pressureUse.isChecked()
		useMass = self.check_massUse.isChecked()
		
		if useTemp and useMass:
			temp = self.txt_temperature.value()
			mass = self.txt_mass.value()
			velDopp = 7.16e-7 * math.sqrt(temp/mass) # ref: Eq. 3.30c from Demtröder (2014)
			velDopp *= np.mean(self.spectrum.x) # assumes loaded spectrum is in MHz
			self.txt_velDopp.setValue(velDopp)
	def getParams(self, idx=0):
		"""
		processes all the parameters from the tab, and returns them
		
		:returns: a list of activated parameters
		:rtype: pyLabSpec.fit.Parameters
		"""
		if not len(self.plotLabels):
			log.warning("(QtProLineFitter) no plot labels are present! you need to start somewhere..")
			return
		reload(fit)
		params = fit.Parameters()
		initPos = self.plotLabels[idx][0].pos()
		initX, initY = float(initPos.x()), float(initPos.y())
		# process window
		if self.check_windowSizeUse.isChecked():
			params.add(
				name="width",
				value=float(self.txt_windowSize.text()))
		else:
			viewRange = self.plotWidget.getViewBox().state['viewRange']
			width = float(viewRange[0][1] - viewRange[0][0])
			params.add(
				name="width",
				value=width)
		# process frequency center & intensity
		if self.check_freqCenterUse.isChecked():
			center = float(self.txt_freqCenter.text())
		else:
			center = initX
		try:
			min = center + float(self.txt_freqCenterMin.text())
		except ValueError:
			min = -np.inf
		try:
			max = center + float(self.txt_freqCenterMax.text())
		except ValueError:
			max = np.inf
		params.add(
			name="center",
			value=center,
			locked=False,
			min=min, max=max)
		params.add(
			name="intensity",
			value=initY,
			locked=False,
			min=-np.inf, max=np.inf)
		# process radiative lifetime
		if self.check_tauRadUse.isChecked():
			raise NotImplementedError("radiative lifetime is not ready yet!")
			try:
				min = float(self.txt_tauRadMin.text())
			except ValueError:
				min = -np.inf
			try:
				max = float(self.txt_tauRadMax.text())
			except ValueError:
				max = np.inf
			params.add(
				name="tauRad",
				value=float(self.txt_tauRad.text()),
				locked=self.check_tauRadLock.isChecked(),
				min=min, max=max)
		# process temperature, pressure, & mass
		#if self.check_temperatureUse.isChecked():
		#	raise NotImplementedError("temperature is not ready yet!")
		#	params.add(
		#		name="temperature",
		#		value=float(self.txt_temperature.text()),
		#		locked=self.check_temperatureLock.isChecked(),
		#		min=None, max=None)
		#if self.check_pressureUse.isChecked():
		#	raise NotImplementedError("pressure is not ready yet!")
		#	params.add(
		#		name="pressure",
		#		value=float(self.txt_pressure.text()),
		#		locked=self.check_pressureLock.isChecked(),
		#		min=None, max=None)
		#if self.check_massUse.isChecked():
		#	raise NotImplementedError("mass is not ready yet!")
		#	params.add(
		#		name="pressure",
		#		value=float(self.txt_pressure.text()),
		#		locked=self.check_pressureLock.isChecked(),
		#		min=None, max=None)
		# some generic full-width at half-max
		if self.check_fwhmUse.isChecked():
			try:
				min = float(self.txt_fwhmMin.text())
			except ValueError:
				min = 0
			try:
				max = float(self.txt_fwhmMax.text())
			except ValueError:
				max = np.inf
			params.add(
				name="fwhm",
				value=float(self.txt_fwhm.text()),
				locked=self.check_fwhmLock.isChecked(),
				min=min, max=max)
		# process velocity-related components
		if self.check_velCollUse.isChecked():
			try:
				min = float(self.txt_velCollMin.text())
			except ValueError:
				min = -np.inf
			try:
				max = float(self.txt_velCollMax.text())
			except ValueError:
				max = np.inf
			params.add(
				name="velColl",
				value=float(self.txt_velColl.text()),
				locked=self.check_velCollLock.isChecked(),
				min=min, max=max)
		if self.check_velDoppUse.isChecked():
			try:
				min = float(self.txt_velDoppMin.text())
			except ValueError:
				min = -np.inf
			try:
				max = float(self.txt_velDoppMax.text())
			except ValueError:
				max = np.inf
			params.add(
				name="velDopp",
				value=float(self.txt_velDopp.text()),
				locked=self.check_velDoppLock.isChecked(),
				min=min, max=max)
		if self.check_coeffNarUse.isChecked():
			try:
				min = float(self.txt_coeffNarMin.text())
			except ValueError:
				min = -np.inf
			try:
				max = float(self.txt_coeffNarMax.text())
			except ValueError:
				max = np.inf
			params.add(
				name="coeffNar",
				value=float(self.txt_coeffNar.text()),
				locked=self.check_coeffNarLock.isChecked(),
				min=min, max=max)
		if self.check_velSDUse.isChecked():
			try:
				min = float(self.txt_velSDMin.text())
			except ValueError:
				min = -np.inf
			try:
				max = float(self.txt_velSDMax.text())
			except ValueError:
				max = np.inf
			params.add(
				name="velSD",
				value=float(self.txt_velSD.text()),
				locked=self.check_velSDLock.isChecked(),
				min=min, max=max)
		# process modulation information
		if self.check_phiUse.isChecked():
			try:
				min = float(self.txt_phiMin.text())
			except ValueError:
				min = -np.inf
			try:
				max = float(self.txt_phiMax.text())
			except ValueError:
				max = np.inf
			params.add(
				name="phi",
				value=float(self.txt_phi.text()),
				locked=self.check_phiLock.isChecked(),
				min=min, max=max)
		if self.check_modDepthUse.isChecked():
			try:
				min = float(self.txt_modDepthMin.text())
			except ValueError:
				min = -np.inf
			try:
				max = float(self.txt_modDepthMax.text())
			except ValueError:
				max = np.inf
			params.add(
				name="modDepth",
				value=float(self.txt_modDepth.text()),
				locked=self.check_modDepthLock.isChecked(),
				min=min, max=max)
		if self.check_modRateUse.isChecked():
			try:
				min = float(self.txt_modRateMin.text())
			except ValueError:
				min = -np.inf
			try:
				max = float(self.txt_modRateMax.text())
			except ValueError:
				max = np.inf
			params.add(
				name="modRate",
				value=float(self.txt_modRate.text()),
				locked=self.check_modRateLock.isChecked(),
				min=min, max=max)
		# baseline corrections
		if self.check_polynomUse.isChecked():
			polystring = str(self.txt_polynom.text()).lower()
			begin = "(?: ^|[+\s])"
			digit = """
				([-+]? # optional sign
					(?:
						(?: \d* \. \d+ ) # .1 .12 .123 etc 9.1 etc 98.1 etc
						|
						(?: \d+ \.? ) # 1. 12. 123. etc 1 12 123 etc
					)
					# followed by optional exponent part if desired
					(?: [Ee] [+-]? \d+ ) ?
				)
				"""
			end = "(?: [+\s]|$)"
			rastring = r"%s %s %s" % (begin, digit, end)
			ramatch = re.search(rastring, polystring, re.VERBOSE)
			rbstring = r"%s %s (?: \*? x) %s" % (begin, digit, end)
			rbmatch = re.search(rbstring, polystring, re.VERBOSE)
			rcstring = r"%s %s (?: \*? x\^2) %s" % (begin, digit, end)
			rcmatch = re.search(rcstring, polystring, re.VERBOSE)
			rdstring = r"%s %s (?: \*? x\^3) %s" % (begin, digit, end)
			rdmatch = re.search(rdstring, polystring, re.VERBOSE)
			# get y-offset
			if ramatch:
				try:
					a0 = float(ramatch.group(1).replace(" ",""))
					params.add( name="a0", value=a0,
						locked=False, min=-np.inf, max=np.inf)
					log.debug("(QtProLineFitter) using ca. %.2e for the y-offset" % a0)
					params.getByName("intensity").value -= a0
				except:
					log.warning("(QtProLineFitter) there was a problem parsing the a0 constant!")
			elif 'a' in polystring:
				params.add( name="a0", value=0.0,
					locked=False, min=-np.inf, max=np.inf)
			
			if rbmatch:
				try:
					a1 = float(rbmatch.group(1).replace(" ",""))
					params.add( name="a1", value=a1,
						locked=False, min=-np.inf, max=np.inf)
					log.debug("(QtProLineFitter) using ca. %.2e for a1" % a1)
				except:
					log.warning("(QtProLineFitter) there was a problem parsing the a1 constant!")
			elif 'b' in polystring:
				params.add( name="a1", value=0.0,
					locked=False, min=-np.inf, max=np.inf)
			
			if rcmatch:
				try:
					a2 = float(rcmatch.group(1).replace(" ",""))
					params.add( name="a2", value=a2,
						locked=False, min=-np.inf, max=np.inf)
					log.debug("(QtProLineFitter) using ca. %.2e for a2" % a2)
				except:
					log.warning("(QtProLineFitter) there was a problem parsing the a2 constant!")
			elif 'c' in polystring:
				params.add( name="a2", value=0.0,
					locked=False, min=-np.inf, max=np.inf)
			
			if rdmatch:
				try:
					a3 = float(rdmatch.group(1).replace(" ",""))
					params.add( name="a3", value=a3,
						locked=False, min=-np.inf, max=np.inf)
					log.debug("(QtProLineFitter) using ca. %.2e for a3" % a3)
				except:
					log.warning("(QtProLineFitter) there was a problem parsing the a3 constant!")
			elif 'd' in polystring:
				params.add( name="a3", value=0.0,
					locked=False, min=-np.inf, max=np.inf)
		log.info("(QtProLineFitter) the following parameters were loaded from the GUI:")
		log.info("(QtProLineFitter) %s" % params.pprint())
		return params

	def test(self, inputEvent=None, shift=False):
		"""
		runs temporary tests (for debugging only)

		For now, it loads some imaginary data to benchmark the supported routines.
		"""
		log.info("(QtProLineFitter) will load some imaginary data...")
		self.reset(reloadSpec=False)
		
		def noise(x, sig):
			return np.random.normal(loc=0.0, scale=sig, size=np.shape(x))
		def lorentzian(x, x0, fwhm):
			y = fwhm / ((x-x0)**2 + (fwhm/2.0)**2)
			return (y-y.min())/y.max()
		def gauss(x, x0, fwhm):
			y = np.exp(-(x-x0)**2.0 / fwhm**2.0 * 4*math.log(2))
			return (y-y.min())/y.max()
		gaussian_true = lambda x, x0, sig: 1 / math.sqrt(2*np.pi) / sig * np.exp(-(x-x0)**2.0 / 2.0 / sig**2.0)
		gaussian2f_true = lambda x, x0, sig: gaussian_true(x,x0,sig) * (sig-(x-x0)) * (sig+(x-x0)) / sig**4.0
		def voigt(x, x0, velColl, velDopp, phi=0.0):
			pi = np.pi
			center = x0 - np.mean(x)
			fp = scipy.fftpack
			### OLD STYLE.. purely defined in fourier "time"
			alphaL = velColl*np.pi
			alphaD = velDopp*4
			T = np.linspace(0, 1/(x[1]-x[0]), len(x))
			#line = lambda t: np.exp(-1j*t*center*pi*2 - phi)
			line = lambda t: np.cos(-t*center*pi*2 - phi) + 1j*np.sin(-2*pi*t*center + phi)
			phi_coll = lambda t: np.exp(-t*alphaL)
			phi_doppler = lambda t: np.exp(-(t*alphaD)**2.0 / 4.0)
			voigt = lambda t: phi_coll(t) * phi_doppler(t) * line(t)
			conv = voigt(T)
			y = fp.ifftshift(fp.ifft(conv)).real
			y = (y-y.min())/y.max()
			return y
		def voigt2f(x, x0, velColl, velDopp, phi=0.0):
			y = voigt(x, x0, velColl, velDopp, phi=phi)
			from scipy import interpolate
			rep = interpolate.splrep(x, y)
			y = -1*interpolate.splev(x, rep, der=2)
			y /= y.max()
			return y
		
		x0 = 69696.9
		x = np.linspace(x0-50, x0+50, 2000)
		if shift:
			x0 += 10
		lineShape = str(self.combo_fitFunction.currentText())
		if lineShape == "lorentzian":
			fwhm = float(str(self.txt_fwhm.text()))
			y = lorentzian(x, 69690, fwhm)
			y /= y.max()
			log.info("(QtProLineFitter) created a lorentzian profile at f=69690")
		elif lineShape == "lorentzian2f":
			fwhm = float(str(self.txt_fwhm.text()))
			y = lorentzian(x, 69690, fwhm)
			from scipy import interpolate
			rep = interpolate.splrep(x, y)
			y = -1*interpolate.splev(x, rep, der=2)
			y /= y.max()
			log.info("(QtProLineFitter) created a lorentzian2f profile at f=69690")
		elif lineShape == "gauss":
			fwhm = float(str(self.txt_fwhm.text()))
			sig = fwhm / 2 / math.sqrt(2*math.log(2))
			#y = gauss(x, 69690, fwhm)
			y = gaussian_true(x, 69690, sig)
			y /= y.max()
			log.info("(QtProLineFitter) created a gauss profile at f=69690")
		elif lineShape == "gauss2f":
			fwhm = float(str(self.txt_fwhm.text()))
			sig = fwhm / 2 / math.sqrt(2*math.log(2))
			y = gaussian2f_true(x, 69690, sig)
			y /= y.max()
			log.info("(QtProLineFitter) created a gauss2f profile at f=69690")
		elif lineShape == "voigt":
			velColl = float(str(self.txt_velColl.text()))
			velDopp = float(str(self.txt_velDopp.text()))
			phi = float(str(self.txt_phi.text()))
			y = voigt(x, x0, velColl, velDopp, phi=phi)
			log.info("(QtProLineFitter) created a voigt profile at f=%s V_coll=%s V_dopp=%s" % (x0, velColl, velDopp))
		elif lineShape == "voigt2f":
			velColl = float(str(self.txt_velColl.text()))
			velDopp = float(str(self.txt_velDopp.text()))
			phi = float(str(self.txt_phi.text()))/180.0*np.pi
			y = voigt2f(x, x0, velColl, velDopp, phi=phi)
			log.info("created a voigt2f profile at f=%s V_coll=%s V_dopp=%s" % (x0, velColl, velDopp))
		else:
			log.warning("(QtProLineFitter) %s isn't supported for this test, sorry!" % lineShape)
			return
		yn = noise(x, 0.005)
		if shift:
			yn *= 5
			y += yn
		self.loadSpec(x=x, y=y)

	def fit(self, mouseEvent=None):
		"""
		Performs a fit, centered at the location of the plot cursor.
		
		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		doNotShiftToZero = True
		# sanity checks for fit
		if self.spectrum is None:
			log.warning("(QtProLineFitter) no spectrum was loaded yet!")
			return
		self.clearLabels(fitOnly=True)
		initPos = self.plotLabels[0][0].pos()
		initX = float(initPos.x())
		initY = float(initPos.y())
		if (initX < min(self.spectrum.x)) or (initX > max(self.spectrum.x)):
			log.warning("(QtProLineFitter) the initial guess is not within the bounds of the spectrum!")
			return

		log.info("(QtProLineFitter) " + "-"*50)
		log.info("(QtProLineFitter) beginning a new fit...")
		reload(fit)
		params = self.getParams()
		# reset label & plots
		if not doNotShiftToZero:
			initX = 0
		self.clearPlots(skipFirst=True)
		center = params.getByName("center")
		self.spectrum.x -= center.value
		self.plots[0].setData(x=self.spectrum.x, y=self.spectrum.y)
		self.plots[0].update()
		center.min -= center.value
		center.max -= center.value
		center.value = 0.0

		# sanity check on the window size
		step = float(abs(self.spectrum.x[0]-self.spectrum.x[1]))
		width = params.getByName("width").value
		if step == 0:
			log.warning("(QtProLineFitter) WARNING! stepsize was found to be zero.. using an average")
			log.warning("(QtProLineFitter)          based on the number of points across the spectrum")
			step = (max(self.spectrum.x)-min(self.spectrum.x))/len(self.spectrum.x)
		idx_rad = int(round(width/2.0/step))
		idx_z = np.abs(self.spectrum.x).argmin()
		if ((idx_z+idx_rad) > len(self.spectrum.x)) or ((idx_z-idx_rad) < 0):
			log.warning("(QtProLineFitter) WARNING! your requested window size exceeds the bounds")
			log.warning("(QtProLineFitter)          of the loaded spectrum! fixing this now..")
			idx_rad = min(idx_z, int(len(self.spectrum.x)-idx_z))
			width = idx_rad * 2 * step
			self.txt_windowSize.setText("%.1f" % width)
			params.getByName("width").value = width

		# plot initial guess
		params.add("step", value=step)
		lineprofile = fit.LineProfile(params=params)
		profileType = self.combo_fitFunction.currentText()
		if profileType == "blank":
			modelX, modelY = lineprofile.getBlank()
		elif profileType == "boxcar":
			modelX, modelY = lineprofile.getBoxcar()
		elif profileType == "gauss":
			modelX, modelY = lineprofile.getGauss()
		elif profileType == "gauss2f":
			modelX, modelY = lineprofile.getGauss2f()
		elif profileType == "lorentzian":
			modelX, modelY = lineprofile.getLorentzian()
		elif profileType == "lorentzian2f":
			modelX, modelY = lineprofile.getLorentzian2f()
		elif profileType in ("voigt", "voigt2f", "galatry2f", "sdvoigt2f", "sdgalatry2f"):
			modelX, modelY = lineprofile.getDore(profileType=profileType)
		if self.check_polynomUse.isChecked():
			# determine coefficients and get polynomial
			coefficients = [0.0, 0.0, 0.0, 0.0]
			if params.getByName("a0"): coefficients[0] = params.getByName("a0").value
			if params.getByName("a1"): coefficients[1] = params.getByName("a1").value
			if params.getByName("a2"): coefficients[2] = params.getByName("a2").value
			if params.getByName("a3"): coefficients[3] = params.getByName("a3").value
			x = modelX - np.median(modelX)
			polynom = self.getPolynom(x, coefficients)
			modelY += polynom
		if self.check_showGuess.isChecked():
			self.plots.append(self.plotWidget.plot(
				x=modelX, y=modelY, pen=pg.mkPen('m'),
				name='initial',
				autoDownsample=True, downsampleMethod='subsample'))

		# run fit
		fitLog = "\n"
		fitLog += "="*50
		fitLog += "\nRunning a new fit (%s) at f=%s" % (profileType, initX)
		try:
			method = str(self.combo_fitMethod.currentText())
			f_scale = str(self.txt_fitFscale.text())
			if len(f_scale):
				f_scale = float(f_scale)
			else:
				f_scale = None
			results = lineprofile.runfit(
				spec=self.spectrum,
				params=params,
				profileType=profileType,
				method=method,
				f_scale=f_scale)
		except:
			e = sys.exc_info()[1]
			if doNotShiftToZero: # shift the plots & results back if desired
				self.spectrum.x += initX
				self.plots[0].setData(x=self.spectrum.x)
				self.plots[0].update()
				modelX += initX
				self.plots[1].setData(x=modelX)
				self.plots[1].update()
			msg = "received the following error during a fit: %s" % e
			raise UserWarning(e)
		fitLog += "\n\nThe fit finished:\n%s" % results["output"].message
		# generate baseline-subtracted data if desired
		if self.check_polynomUse.isChecked() and self.check_showDebaselined.isChecked():
			# determine coefficients and get polynomial
			coefficients = [0.0, 0.0, 0.0, 0.0]
			log.info(results["params"])
			paramNames = list(results["params"].keys())
			if "a0" in paramNames: coefficients[0] = results["params"]["a0"]["value"]
			if "a1" in paramNames: coefficients[1] = results["params"]["a1"]["value"]
			if "a2" in paramNames: coefficients[2] = results["params"]["a2"]["value"]
			if "a3" in paramNames: coefficients[3] = results["params"]["a3"]["value"]
			polynom = self.getPolynom(results["dataOrig"]["x"], coefficients)
			# make copy of data and subtract polynomial
			data_debaselined = np.copy(results["dataOrig"]["y"]) - polynom
			fit_debaselined = np.copy(results["fit"]) - polynom
			## determine y-offset to use, which could just be the maximum of the y-data
			#ySpan = np.max(results["dataOrig"]["y"]) - np.min(results["dataOrig"]["y"])
			#yOffset = np.max(results["dataOrig"]["y"]) + ySpan
			#data_debaselined += yOffset
			#fit_debaselined += yOffset
		# process the output from the GUI, rather than the fit library
		if doNotShiftToZero: # shift the plots & results back if desired
			# shift spectrum back
			self.spectrum.x += initX
			self.plots[0].setData(x=self.spectrum.x)
			self.plots[0].update()
			# shift initial plot back
			modelX += initX
			if self.check_showGuess.isChecked():
				self.plots[1].setData(x=modelX)
				self.plots[1].update()
			# shift results back
			results["x"] += initX
			results["params"]["center"]["value"] += initX
		fitLog += "\n\nThe final coefficients are:"
		for k,v in sorted(results["params"].items()):
			val = v["value"]
			unc = v["unc"]
			fitLog += '\n%15s -> %20s +/- %7.2e' % (k, val, unc)
		log.info(fitLog)
		# update table
		newRow = self.tableWidget.rowCount()
		self.tableWidget.insertRow(newRow)
		self.tableWidget.setItem(newRow, 0, QtGui.QTableWidgetItem(profileType))
		self.tableWidget.setItem(newRow, 1, QtGui.QTableWidgetItem("%.5f" % results["params"]["center"]["value"]))
		self.tableWidget.setItem(newRow, 2, QtGui.QTableWidgetItem("%7.2e" % results["params"]["center"]["unc"]))
		self.tableWidget.setItem(newRow, 3, QtGui.QTableWidgetItem(results["output"].message))
		# emit signals that might communicate back to a parent interface/routine
		self.fitFinishedSignal.emit()
		self.newFitSignal.emit({
			"frequency": results["params"]["center"],
			"fit": (results["x"], np.copy(results["fit"])),
			"res": (results["x"], np.copy(results["res"]))})
		# move cursor to the end, and update its contents
		cursor = self.textEdit.textCursor()
		cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor)
		self.textEdit.setTextCursor(cursor)
		self.textEdit.insertPlainText(fitLog)
		# plot the FitProfile
		if self.check_polynomUse.isChecked() and self.check_showDebaselined.isChecked():
			self.plots.append(self.plotWidget.plot(
				x=results["x"], y=data_debaselined, pen=pg.mkPen('w'),
				name='de-baselined data',
				autoDownsample=True, downsampleMethod='subsample'))
			self.plots.append(self.plotWidget.plot(
				x=results["x"], y=fit_debaselined, pen=pg.mkPen('y'),
				name='de-baselined fit',
				autoDownsample=True, downsampleMethod='subsample'))
		results["res"] += np.min(results["dataOrig"]["y"]) # used to be only if showDebaselined
		results["res"] -= (results["dataOrig"]["y"].max() - results["dataOrig"]["y"].min()) * 0.1 # 10% offset
		self.plots.append(self.plotWidget.plot(
			x=results["x"], y=results["fit"], pen=pg.mkPen('y'),
			name='fit',
			autoDownsample=True, downsampleMethod='subsample'))
		self.plots.append(self.plotWidget.plot(
			x=results["x"], y=results["res"], pen=pg.mkPen('r'),
			name='res',
			autoDownsample=True, downsampleMethod='subsample'))
		self.textEdit.insertPlainText("\n")
		self.textEdit.verticalScrollBar().setValue(
			self.textEdit.verticalScrollBar().maximum())
		# add labels from fit, if desired
		if self.check_showFitFreqLabels.isChecked():
			yOffset = 0.0
			try:
				yOffset += results["params"]["a0"]["value"]
			except KeyError:
				pass
			fitCen = results["params"]["center"]["value"]
			fitUnc = results["params"]["center"]["unc"]
			fitInt = results["params"]["intensity"]["value"]
			label = pg.TextItem(text="", anchor=(0.5,1), fill=(0,0,0,100))
			label.setHtml(self.HTMLFitFreq % (fitCen, fitUnc))
			label.setPos(fitCen, yOffset+fitInt*1.1)
			self.plotWidget.addItem(label, ignoreBounds=False)
			self.fitLabels.append(label)
	def fitMulti(self, mouseEvent=None):
		"""
		Runs a multi-line fit, similar to the normal fit but drops/ignores lots
		of code that is used for sanity checks or preprocessing. Therefore,
		one should really make sure that a single-component fit works well,
		before trying this for multiple components.
		"""
		doNotShiftToZero = True
		# sanity checks for fit
		if self.spectrum is None:
			log.warning("(QtProLineFitter) no spectrum was loaded yet!")
			return
		self.clearLabels(fitOnly=True)
		
		# define parameter space
		params = self.getParams()
		frequencies = [label[0].pos().x() for label in self.plotLabels]
		intensities = [label[0].pos().y() for label in self.plotLabels]
		profileType = self.combo_fitFunction.currentText()
		
		initX = float(np.mean([min(frequencies), max(frequencies)]))
		if (initX < min(self.spectrum.x)) or (initX > max(self.spectrum.x)):
			log.warning("(QtProLineFitter) the initial guess is not within the bounds of the spectrum!")
			return

		log.info("(QtProLineFitter) " + "-"*50)
		log.info("(QtProLineFitter) beginning a new fit...")
		reload(fit)
		# reset label & plots
		if not doNotShiftToZero:
			initX = 0
		self.clearPlots(skipFirst=True)
		self.spectrum.x -= initX
		self.plots[0].setData(x=self.spectrum.x, y=self.spectrum.y)
		self.plots[0].update()

		# sanity check on the window size
		step = float(abs(self.spectrum.x[0]-self.spectrum.x[1]))
		width = params.getByName("width").value
		if step == 0:
			log.warning("(QtProLineFitter) WARNING! stepsize was found to be zero.. using an average")
			log.warning("(QtProLineFitter)          based on the number of points across the spectrum")
			step = (max(self.spectrum.x)-min(self.spectrum.x))/len(self.spectrum.x)
		idx_rad = int(round(width/2.0/step))
		idx_z = np.abs(self.spectrum.x).argmin()
		if ((idx_z+idx_rad) > len(self.spectrum.x)) or ((idx_z-idx_rad) < 0):
			log.warning("(QtProLineFitter) WARNING! your requested window size exceeds the bounds")
			log.warning("(QtProLineFitter)          of the loaded spectrum! fixing this now..")
			idx_rad = min(idx_z, int(len(self.spectrum.x)-idx_z))
			width = idx_rad * 2 * step
			self.txt_windowSize.setText("%.1f" % width)
			params.getByName("width").value = width
		span = max(frequencies)-min(frequencies)
		if width < span:
			log.warning("(QtProLineFitter) WARNING! your requested window size is smaller than the")
			log.warning("(QtProLineFitter)          range of center frequencies to fit! will fix")
			log.warning("(QtProLineFitter)          this now by extending the width by 5 MHz..")
			params.getByName("width").value = span + 5
		
		params.add("step", value=step)
		lineprofile = fit.LineProfile(params=params)
		profileType = self.combo_fitFunction.currentText()
		
		width = params.getByName("width").value
		idx_radius = int(round(width/2.0/step))
		idx_cen = np.abs(self.spectrum.x).argmin()
		modelXsum = self.spectrum.x[idx_cen-idx_radius:idx_cen+idx_radius+1].copy()
		modelYsum = None
		for (c,i) in zip(frequencies,intensities):
			c -= float(np.mean([min(frequencies), max(frequencies)])) + step
			if profileType == "blank":
				modelX, modelY = lineprofile.getBlank(x=modelXsum, center=c, intensity=i)
			elif profileType == "boxcar":
				modelX, modelY = lineprofile.getBoxcar(x=modelXsum, center=c, intensity=i)
			elif profileType == "gauss":
				modelX, modelY = lineprofile.getGauss(x=modelXsum, center=c, intensity=i)
			elif profileType == "gauss2f":
				modelX, modelY = lineprofile.getGauss2f(x=modelXsum, center=c, intensity=i)
			elif profileType == "lorentzian":
				modelX, modelY = lineprofile.getLorentzian(x=modelXsum, center=c, intensity=i)
			elif profileType == "lorentzian2f":
				modelX, modelY = lineprofile.getLorentzian2f(x=modelXsum, center=c, intensity=i)
			elif profileType in ("voigt", "voigt2f", "galatry2f", "sdvoigt2f", "sdgalatry2f"):
				modelX, modelY = lineprofile.getDore(
					profileType=profileType,
					x=modelXsum, center=c, intensity=i)
			if modelYsum is None:
				modelYsum = modelY
			else:
				modelYsum += modelY
		if self.check_polynomUse.isChecked():
			# determine coefficients and get polynomial
			coefficients = [0.0, 0.0, 0.0, 0.0]
			if params.getByName("a0"): coefficients[0] = params.getByName("a0").value
			if params.getByName("a1"): coefficients[1] = params.getByName("a1").value
			if params.getByName("a2"): coefficients[2] = params.getByName("a2").value
			if params.getByName("a3"): coefficients[3] = params.getByName("a3").value
			x = modelXsum - np.median(modelXsum)
			polynom = self.getPolynom(x, coefficients)
			modelYsum += polynom
		modelXsum += float(np.mean([min(frequencies), max(frequencies)]))
		if self.check_showGuess.isChecked():
			self.plots.append(self.plotWidget.plot(
				x=modelXsum, y=modelYsum, pen=pg.mkPen('m'),
				name='initial',
				autoDownsample=True, downsampleMethod='subsample'))

		# run fit
		fitLog = "\n"
		fitLog += "="*50
		fitLog += "\nRunning a new fit (%s) at f=%s" % (profileType, frequencies)
		try:
			time_start = timer()
			results = lineprofile.runmultifit(
				method=str(self.combo_fitMethod.currentText()),
				f_scale=self.txt_fitFscale.value(),
				spec=self.spectrum,
				params=params,
				center=initX,
				frequencies=frequencies,
				intensities=intensities,
				profileType=profileType,
				useMultiParams=self.check_useMultParams.isChecked())
			time_finish = timer()
			fitLog += "\nelapsed time for fit was: %s" % (time_finish-time_start)
		except:
			e = sys.exc_info()[1]
			if doNotShiftToZero: # shift the plots & results back if desired
				self.spectrum.x += initX
				self.plots[0].setData(x=self.spectrum.x)
				self.plots[0].update()
			msg = "received the following error during a fit: %s" % e
			raise UserWarning(e)
		fitLog += "\n\nThe fit finished:\n%s" % results["output"].message
		# generate baseline-subtracted data if desired
		if self.check_polynomUse.isChecked() and self.check_showDebaselined.isChecked():
			# determine coefficients and get polynomial
			coefficients = [0.0, 0.0, 0.0, 0.0]
			log.info(results["params"])
			paramNames = list(results["params"].keys())
			if "a0" in paramNames: coefficients[0] = results["params"]["a0"]["value"]
			if "a1" in paramNames: coefficients[1] = results["params"]["a1"]["value"]
			if "a2" in paramNames: coefficients[2] = results["params"]["a2"]["value"]
			if "a3" in paramNames: coefficients[3] = results["params"]["a3"]["value"]
			polynom = self.getPolynom(results["dataOrig"]["x"], coefficients)
			# make copy of data and subtract polynomial
			data_debaselined = np.copy(results["dataOrig"]["y"]) - polynom
			fit_debaselined = np.copy(results["fit"]) - polynom
			## determine y-offset to use, which could just be the maximum of the y-data
			#ySpan = np.max(results["dataOrig"]["y"]) - np.min(results["dataOrig"]["y"])
			#yOffset = np.max(results["dataOrig"]["y"]) + ySpan
			#data_debaselined += yOffset
			#fit_debaselined += yOffset
		# process the output from the GUI, rather than the fit library
		if doNotShiftToZero: # shift the plots & results back if desired
			# shift spectrum back
			self.spectrum.x += initX
			self.plots[0].setData(x=self.spectrum.x, y=self.spectrum.y)
			#self.plots[0].setData(x=self.spectrum.x)
			self.plots[0].update()
			# shift results back
			results["x"] += initX
			for i in range(len(self.plotLabels)):
				name = "center_%s" % i
				results["params"][name]["value"] += initX
		fitLog += "\n\nThe final coefficients are:"
		for k,v in sorted(results["params"].items()):
			val = v["value"]
			unc = v["unc"]
			fitLog += '\n%15s -> %20s +/- %7.2e' % (k, val, unc)
		log.info(fitLog)
		# update table
		for i in range(len(self.plotLabels)):
			name = "center_%s" % i
			newRow = self.tableWidget.rowCount()
			self.tableWidget.insertRow(newRow)
			self.tableWidget.setItem(newRow, 0, QtGui.QTableWidgetItem(profileType))
			self.tableWidget.setItem(newRow, 1, QtGui.QTableWidgetItem("%.5f" % results["params"][name]["value"]))
			self.tableWidget.setItem(newRow, 2, QtGui.QTableWidgetItem("%7.2e" % results["params"][name]["unc"]))
			self.tableWidget.setItem(newRow, 3, QtGui.QTableWidgetItem(results["output"].message))
		# emit signals that might communicate back to a parent interface/routine
		self.fitFinishedSignal.emit()
		self.newFitSignal.emit({
			"frequency": results["params"]["center_0"],   # only the first line or fix QtFit.LAfitPro() !
			"fit": (results["x"], np.copy(results["fit"])),
			"res": (results["x"], np.copy(results["res"]))})
		# move cursor to the end, and update its contents
		cursor = self.textEdit.textCursor()
		cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor)
		self.textEdit.setTextCursor(cursor)
		self.textEdit.insertPlainText(fitLog)
		# plot the FitProfile
		if self.check_polynomUse.isChecked() and self.check_showDebaselined.isChecked():
			self.plots.append(self.plotWidget.plot(
				x=results["x"], y=data_debaselined, pen=pg.mkPen('w'),
				name='de-baselined data',
				autoDownsample=True, downsampleMethod='subsample'))
			self.plots.append(self.plotWidget.plot(
				x=results["x"], y=fit_debaselined, pen=pg.mkPen('y'),
				name='de-baselined fit',
				autoDownsample=True, downsampleMethod='subsample'))
		results["res"] += np.min(results["dataOrig"]["y"])
		results["res"] -= (results["dataOrig"]["y"].max() - results["dataOrig"]["y"].min()) * 0.1 # 10% offset
		self.plots.append(self.plotWidget.plot(
			x=results["x"], y=results["fit"], pen=pg.mkPen('y'),
			name='fit',
			autoDownsample=True, downsampleMethod='subsample'))
		self.plots.append(self.plotWidget.plot(
			x=results["x"], y=results["res"], pen=pg.mkPen('r'),
			name='res',
			autoDownsample=True, downsampleMethod='subsample'))
		self.textEdit.insertPlainText("\n")
		self.textEdit.verticalScrollBar().setValue(
			self.textEdit.verticalScrollBar().maximum())
		if self.check_showFitFreqLabels.isChecked():
			yOffset = 0.0
			try:
				yOffset += results["params"]["a0"]["value"]
			except KeyError:
				pass
			for i in range(len(self.plotLabels)):
				nameCen = "center_%s" % i
				nameInt = "intensity_%s" % i
				fitCen = results["params"][nameCen]["value"]
				fitUnc = results["params"][nameCen]["unc"]
				fitInt = results["params"][nameInt]["value"]
				label = pg.TextItem(text="", anchor=(0.5,1), fill=(0,0,0,100))
				label.setHtml(self.HTMLFitFreq % (fitCen, fitUnc))
				label.setPos(fitCen, yOffset+fitInt*1.1)
				self.plotWidget.addItem(label, ignoreBounds=False)
				self.fitLabels.append(label)
		if self.check_calcPairAvgCen.isChecked():
			yOffset = 0.0
			try:
				yOffset += results["params"]["a0"]["value"]
			except KeyError:
				pass
			log.info("(QtProLineFitter) averages are:")
			self.textEdit.insertPlainText("\naverages are:\n")
			cen0,cen1 = 0,0
			unc0,unc1 = 0,0
			int0,int1 = 0,0
			for i in range(len(self.plotLabels)):
				nameCen = "center_%s" % i
				nameInt = "intensity_%s" % i
				if (i % 2) == 0:
					cen0 = results["params"][nameCen]["value"]
					unc0 = results["params"][nameCen]["unc"]
					int0 = results["params"][nameInt]["value"]
				else:
					cen1 = results["params"][nameCen]["value"]
					unc1 = results["params"][nameCen]["unc"]
					int1 = results["params"][nameInt]["value"]
					# calc avg
					cenAvg = (cen0 + cen1) / 2.0
					uncAvg = math.sqrt(unc0**2 + unc1**2)
					intAvg = (int0 + int1) / 2.0
					msg = "\t%.5f +/- %7.2e" % (cenAvg, uncAvg)
					log.info("(QtProLineFitter) %s" % msg)
					self.textEdit.insertPlainText("%s\n" % msg)
					# place label
					label = pg.TextItem(text="", anchor=(0.5,1), fill=(0,0,0,100))
					label.setHtml(self.HTMLFitFreq.replace("yellow","lime") % (cenAvg, uncAvg))
					label.setPos(cenAvg, yOffset+intAvg*1.1)
					self.plotWidget.addItem(label, ignoreBounds=False)
					self.fitLabels.append(label)
	def fitAll2f(self, mouseEvent=None):
		"""
		runs loops through the 2f line profiles, and runs a fit
		"""
		log.info("(QtProLineFitter) %s " % "="*50)
		log.info("(QtProLineFitter) running a fit on the current line, using all the proFit lines profiles")
		first_idx = 6
		for i,ft in enumerate(self.fit_types[first_idx:]):
			self.combo_fitFunction.setCurrentIndex(first_idx+i)
			self.fitFunctionChanged()
			self.update()
			self.fit()

	def loadSpec(self, mouseEvent=None, spec=None, x=None, y=None, filename=None, settings={}):
		"""
		loads a spectrum
		
		:param mouseEvent: (optional) the mouse event from a click
		:param spec: (optional) the spectrum for initialization
		:param x: (optional) the x-axis for initialization
		:param y: (optional) the y-axis for initialization
		:param filename: (optional) the filename to use for loading a spectrum
		:type mouseEvent: QtGui.QMouseEvent
		:type parent: QtGui.QMainWindow
		:type spec: pyLabSpec.spectrum.Spectrum
		:type x: list, np.ndarray
		:type y: list, np.ndarray
		"""
		from Spectrum import spectrum
		if spec is not None:
			self.textEdit.insertPlainText("\nloading a Spectrum directly (or reset)\n")
			self.spectrum = spec
		elif all([axis is not None for axis in (x, y)]):
			log.info("(QtProLineFitter) converting a pair of x/y axes")
			self.textEdit.insertPlainText("\nconverting a pair of x/y axes to a Spectrum")
			self.spectrum = spectrum.Spectrum(x, y)
		elif filename is not None:
			log.info("(QtProLineFitter) loading file '%s' as a Spectrum" % filename)
			ftype = None
			if "fid" in filename.lower():
				ftype = "fid"
			elif os.path.splitext(filename)[1][1:] == "lwa":
				ftype = "jpl"
			else:
				knownExts = ("ssv", "tsv", "csv", "fits")
				thisExt = os.path.splitext(filename)[1][1:]
				for ext in knownExts:
					log.debug("checking ext %s against %s" % (ext, thisExt))
					if ext == thisExt:
						ftype = ext
						break
			if ftype is None:
				raise SyntaxError("could not determine the filetype, so you should fix this..")
			self.spectrum = spectrum.load_spectrum(filename, ftype=ftype)
			self.textEdit.insertPlainText("\nloaded spectral file '%s'\n" % filename)
		else:
			if settings == {}:
				# provide dialog (if no settings)
				if (not "loadDialog" in vars(self)):
					self.loadDialog = SpecLoadDialog(self)
				if not self.loadDialog.exec_():
					return
				else:
					settings = self.loadDialog.getValues()
			filenames = settings["filenames"]
			if isinstance(filenames, str):
				filenames = filenames.split("|")
			if not any([os.path.isfile(f) for f in filenames]):
				raise IOError("could not locate one of the requested input files!")
			# sanity check about: multiple files but not appending them
			if (not settings["appendData"]) and (len(filenames) > 1):
				raise SyntaxError("you cannot load multiple files without appending them!")
			if settings["appendData"]:
				raise NotImplementedError("multiple files are not allowed in the fitter window yet!")
			elif isinstance(self.x, type(np.array([]))):
				self.x = self.x.copy().tolist()
				self.y = self.y.copy().tolist()
			# loop through it and push to memory
			fileIn = filenames[0]
			if settings["filetype"] in ["ssv", "tsv", "csv", "casac", "gesp"]:
				expspec = spectrum.load_spectrum(
					fileIn, ftype=settings["filetype"],
					skipFirst=settings["skipFirst"])
			elif settings["filetype"]=="jpl":
				raise NotImplementedError("JPL-style spectral files are still not supported yet..")
			elif settings["filetype"]=="arbdc":
				delimiter = settings["delimiter"]
				xcol = settings["xcol"]
				ycol = settings["ycol"]
				expspec = spectrum.load_spectrum(
					fileIn, ftype="arbdelim",
					skipFirst=settings["skipFirst"], xcol=xcol, ycol=ycol,
					delimiter=delimiter)
			elif settings["filetype"]=="arbs":
				raise NotImplementedError("arbs-type files are not supported in the fitterwindow.. they may be somewhere else, so buy Jake a beer to fix this")
			if settings["unit"]=="Hz":
				expspec.x *= 1e6
			self.spectrum = expspec
		### sanity checks and header processing
		# remove any "nan" entries
		x_non_nans = np.logical_not(np.isnan(self.spectrum.x))
		self.spectrum.x = self.spectrum.x[x_non_nans]
		self.spectrum.y = self.spectrum.y[x_non_nans]
		y_non_nans = np.logical_not(np.isnan(self.spectrum.y))
		self.spectrum.x = self.spectrum.x[y_non_nans]
		self.spectrum.y = self.spectrum.y[y_non_nans]
		# width
		width = float(self.txt_windowSize.text())
		step = float(abs(self.spectrum.x[0]-self.spectrum.x[1]))
		if step == 0:
			log.warning("(QtProLineFitter) WARNING: the step size for this spectrum was zero, based on the difference")
			log.warning("                           between the first two datapoints.. will now use the average, based")
			log.warning("                           on the width and the number of points")
			step = (max(self.spectrum.x)-min(self.spectrum.x))/len(self.spectrum.x)
		if float(width/step) > 1e4:
			log.warning("(QtProLineFitter) WARNING: the window size for this spectrum's step size is")
			log.warning("(QtProLineFitter)           a bit excessive! lowering it to 10k points now..")
			self.txt_windowSize.setText("%f" % float(1e4*step))
		# head items
		if "header" in dir(self.spectrum):
			header = self.spectrum.header
			header_str = "%s" % (header,)
			for h in header:
				match = ""
				# temperature
				if "temperature" in h:
					log.info("(QtProLineFitter) PRO TIP: found a temperature-related entry in the header,")
					log.info("(QtProLineFitter)          which could be used for the fit:\n\t%s" % h)
					log.info("(QtProLineFitter)          match was: '%s'" % match)
				# pressure
				if "pressure" in h:
					log.info("(QtProLineFitter) PRO TIP: found a pressure-related entry in the header,")
					log.info("(QtProLineFitter)          which could be used for the fit: %s" % h)
					log.info("(QtProLineFitter)          match was: '%s'" % match)
				# fm depth
				match = re.match(r"#:txt_SynthFMWidth: '(.*)'", h)
				if match:
					log.info("(QtProLineFitter) found a CASAC-style header entry..")
					log.info("(QtProLineFitter) setting the modDepth to %s kHz" % match.group(1))
					modDepth = float(match.group(1))/1e3
					if "Jet Experiment GUI" in header_str:
						log.info("(QtProLineFitter) the modDepth was adjusted for FUJ")
						modDepth *= 0.5
					self.txt_modDepth.setText("%f" % modDepth)
				# fm rate
				match = re.match(r"#:txt_SynthFMFreq: '(.*)'", h)
				if match:
					log.info("(QtProLineFitter) found a CASAC-style header entry!")
					log.info("(QtProLineFitter) setting the modRate to %s kHz" % match.group(1))
					modRate = float(match.group(1))/1e3
					self.txt_modRate.setText("%f" % modRate)
			# general adjustments for a jet experiment..
			if "Jet Experiment GUI" in header_str:
				log.info("(QtProLineFitter) changing the loss function for FUJ")
				self.txt_fitFscale.setValue(1.1)
				log.info("(QtProLineFitter) adjusting the Doppler parameter for FUJ")
				self.txt_velDopp.setValue(0.00001)
				log.info("(QtProLineFitter) disabling the polynomial baseline (by default) for FUJ")
				self.check_polynomUse.setChecked(False)
		# send to the plot
		self.clearPlots()
		self.plots.append(self.plotWidget.plot(
			x=self.spectrum.x, y=self.spectrum.y, pen=pg.mkPen('w'),
			name='exp',
			autoDownsample=True, downsampleMethod='subsample'))

	def getProfiles(self, mouseEvent=None):
		"""
		Clears the plot and refills it with all the various line profiles
		defined in the external library, based on the active parameters.

		Note that it will retrieve ALL profiles (all harmonics), unless a
		harmonic is specified in the parameters tab.
		
		:param mouseEvent: (optional) the mouse event from a click
		:type mouseEvent: QtGui.QMouseEvent
		"""
		# clear current plots
		self.spectrum = None
		self.clearPlots()

		# activate the required parameters
		def updateCheckBox(name, checkState):
			myCheckBox = getattr(self, 'check_%sUse' % name)
			myCheckBox.setChecked(checkState)
		updateCheckBox("fwhm", True)
		updateCheckBox("velColl", True)
		updateCheckBox("velDopp", True)
		updateCheckBox("coeffNar", True)
		updateCheckBox("velSD", True)
		updateCheckBox("modDepth", True)
		updateCheckBox("modRate", True)

		# get parameters
		reload(fit)
		params = self.getParams()
		params.add("center", value=0.0)
		params.add("step", value=0.02)
		params.add("width", value=20.0)
		params.add("intensity", value=1.0)
		# define line profile
		testprofile = fit.LineProfile(params=params)

		harmonic = str(self.txt_harmonic.text())
		if harmonic == "":
			# add blank
			x, y = testprofile.getBlank()
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen('c'),
				name='blank',
				autoDownsample=True, downsampleMethod='subsample'))
			# add boxcar
			x, y = testprofile.getBoxcar()
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen('c'),
				name='boxcar',
				autoDownsample=True, downsampleMethod='subsample'))
		if harmonic == "" or harmonic == 1:
			# add analytic gaussian
			x, y = testprofile.getGauss()
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen('r'),
				name='gauss',
				autoDownsample=True, downsampleMethod='subsample'))
			# add analytic lorentzian
			x, y = testprofile.getLorentzian()
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen('b'),
				name='lorentzian',
				autoDownsample=True, downsampleMethod='subsample'))
			# add voigt
			x, y = testprofile.getDore(profileType="voigt", useBesselExpansion=True)
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen('y'),
				name='voigt',
				autoDownsample=True, downsampleMethod='subsample'))
		if harmonic == "" or harmonic == 2:
			# add analytic 2f-gaussian
			x, y = testprofile.getGauss2f()
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen('r'),
				name='gauss_2f',
				autoDownsample=True, downsampleMethod='subsample'))
			# add Dore's F2 profiles
			x, y = testprofile.getDore(profileType="lorentzian2f", useBesselExpansion=True)
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen('b'),
				name='dore - lorentzian2f',
				autoDownsample=True, downsampleMethod='subsample'))
			x, y = testprofile.getDore(profileType="voigt2f", useBesselExpansion=True)
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen('y'),
				name='dore - voigt2f',
				autoDownsample=True, downsampleMethod='subsample'))
			x, y = testprofile.getDore(profileType="galatry2f", useBesselExpansion=True)
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen('m'),
				name='dore - galatry2f',
				autoDownsample=True, downsampleMethod='subsample'))
			x, y = testprofile.getDore(profileType="sdvoigt2f", useBesselExpansion=True)
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen(color=(0, 100, 0)),
				name='dore - sdvoigt2f',
				autoDownsample=True, downsampleMethod='subsample'))
			x, y = testprofile.getDore(profileType="sdgalatry2f", useBesselExpansion=True)
			self.plots.append(self.plotWidget.plot(
				x=x, y=y, pen=pg.mkPen(color=(0, 255, 0)),
				name='dore - sdgalatry2f',
				autoDownsample=True, downsampleMethod='subsample'))
	def getPolynom(self, x, polynom=[0.0, 0.0, 0.0, 0.0]):
		"""
		Returns a 3rd-order polynomial based on x-data and coefficients.

		:param x: an array of x data
		:type x: np.ndarray
		"""
		return polynom[0] + polynom[1]*x + polynom[2]*x**2 + polynom[3]*x**3
	
	def launchPlotDesigner(self, inputEvent=None):
		"""
		Launches the PlotDesigner with the loaded spectrum and fitted profile.
		"""
		flatten = lambda l: [item for sublist in l for item in sublist]
		viewrange = flatten(self.plotWidget.getViewBox().state['viewRange'])
		spectra = []
		for idx,p in enumerate(self.plots):
			name = p.name()
			color = p.opts['pen'].color().getRgbF()
			if name == "exp":
				color = (0.0, 0.0, 0.0, 1.0)
			elif name == "initial":
				continue
			spectra.append({
				'name': name,
				'color': color,
				'x': p.xData,
				'y': p.yData})
		self.PlotDesigner = PlotDesigner(
			spectra=spectra,
			viewrange=viewrange)
		self.PlotDesigner.show()

	def quit(self, mouseEvent=None, confirm=False):
		"""
		Provides the routine that quits the GUI.

		For now, simply quits the running instance of Qt.

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
		# save the current settings
		self.saveConf()
		# finally quit
		if self.parent is not None:
			self.accept()
		else:
			QtCore.QCoreApplication.instance().quit()




Ui_QtProLineFitter, QDialog = loadUiType(os.path.join(ui_path, 'JetMFLISWTriggerViewer.ui'))
class JetMFLISWTriggerViewer(QDialog, Ui_QtProLineFitter):
	"""
	Provides a dialog window that for viewing the pulse triggers and
	the SW Trigger data stream from the lockin (ZI MFLI).
	"""
	def __init__(self, parent):
		"""
		:param parent: the parent GUI
		:type parent: QtGui.QMainWindow
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.parent = parent
		
		# init plots
		self.initTriggerPlots()
		
		# set thread to update plot
		self.parent.signalSWTrigUpdated.connect(self.updateSWTrigPlot)
		
		# get parent GUI's save directory
		dt = datetime.datetime.now()
		timeScanSave = dt
		# check the save directory and process it
		saveDir = str(self.parent.txt_SpecOut.text())
		saveDir += "/" + str(datetime.date(dt.year, dt.month, dt.day))
		saveDir = os.path.expanduser(saveDir)
		if not os.path.exists(saveDir):
			os.makedirs(saveDir)
		self.saveDir = saveDir
		
		# populate the GUI elements for filters
		self.combo_useFilter2.addItem("only show here (full trace)")
		self.combo_useFilter2.addItem("only show here (windows only)")
		self.combo_useFilter2.addItem("use filter for scan (full trace)")
		self.combo_useFilter2.addItem("use filter for scan (windows only)")
		self.combo_useFilter2.setCurrentIndex(0)
		filters = [
			"none",
			("clipAbsY","coeff1 is used as the absolute cutoff"),
			("wienerY","coeff1 is the window size for a Wiener filter"),
			("medfiltY","coeff1 is the window size for a median filter"),
			("ffbutterY","coeff1 is the filter ord, coeff2 is the Nyquist freq-norm'd rolloff")]
		tooltip = "provides some specific filters to help with transients:\n"
		for f in filters:
			if isinstance(f, str):
				self.combo_filterType.addItem(f)
				tooltip += "\t%s: (no comment)\n" % f
			elif isinstance(f, tuple):
				self.combo_filterType.addItem(f[0])
				if len(f)==1:
					tooltip += "\t%s: (no comment)\n" % f[0]
				else:
					tooltip += "\t%s: %s\n" % f
		self.combo_filterType.setCurrentIndex(filters.index("none"))
		self.combo_filterType.setToolTip(tooltip.rstrip())
		self.txt_filterCoeff1.setToolTip("coeff1")
		self.txt_filterCoeff2.setToolTip("coeff2")
		
		self.lastUpdateTime = timer()
	
	
	def initTriggerPlots(self):
		"""
		Initializes the plot.
		"""
		labelStyle = {'color':'#FFF', 'font-size':'16pt'}
		self.triggerPlotFig.setLabel('left', "Signal", units='V', **labelStyle)
		self.triggerPlotFig.setLabel('bottom', "Time", units='s', **labelStyle)
		#self.triggerPlotFig.getAxis('bottom').setScale(scale=1e-3)
		self.triggerPlotSWTrig = Widgets.SpectralPlot(
			name='trigger_sample', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.triggerPlotSWTrig.setZValue(999)
		self.triggerPlotFig.addItem(self.triggerPlotSWTrig)
		self.triggerPlotSWTrigPreFilt = Widgets.SpectralPlot(
			name='trigger_sample_prefilter', clipToView=True,
			autoDownsample=True, downsampleMethod='subsample')
		self.triggerPlotSWTrigPreFilt.setZValue(500)
		self.triggerPlotSWTrigPreFilt.setPen(pg.mkPen(0.5))
		self.triggerPlotFig.addItem(self.triggerPlotSWTrigPreFilt)
		brushes = { # default: rgba=(0, 0, 255, 50)
			"Valve": QtGui.QBrush(QtGui.QColor(200, 200, 200, 75)),
			"LockinSingle": QtGui.QBrush(QtGui.QColor(0, 0, 255, 50)),
			"LockinInt": QtGui.QBrush(QtGui.QColor(0, 255, 255, 75)),
			"LockinBase": QtGui.QBrush(QtGui.QColor(112, 166, 255, 50)),
			"HV": QtGui.QBrush(QtGui.QColor(255, 120, 0, 75)),
			"DG4": QtGui.QBrush(QtGui.QColor(0, 0, 255, 50))}
		for i in ["Valve", "LockinInt", "LockinBase"]:
			# define new linear region
			regionName = "pulsePlotRegion_%s" % i
			if i == "LockinBase":
				lowerBound = None
			else:
				lowerBound = 0
			setattr(self, regionName, pg.LinearRegionItem(
				bounds=[lowerBound,None],
				brush=brushes[i]))
			localRegion = getattr(self, regionName)
			# set its range to that of the parent's
			parentRegion = getattr(self.parent, "pulsePlotRegion_%s" % i)
			localRegion.setRegion(parentRegion.getRegion())
			# add to plot
			self.triggerPlotFig.addItem(localRegion)
			# define new signal+slot to update parent when local changes
			setattr(self, "local_%s_sigChanged" % regionName, pg.SignalProxy(
				localRegion.sigRegionChanged,
				rateLimit=10,
				slot=partial(
					self.updateParentRegion,
					name=regionName)))
			# define new signal+slot to update local when parent changes
			setattr(self, "parent_%s_sigChanged" % regionName, pg.SignalProxy(
				parentRegion.sigRegionChanged,
				rateLimit=10,
				slot=partial(
					self.updateLocalRegion,
					name=regionName)))
	
	
	def updateParentRegion(self, signal=None, name=None):
		"""
		Called whenever a window is changed in the trigger viewer and
		should also update the main GUI's plot in the pulse tab.

		:param name: the name of the plot region
		:type name: str
		"""
		if (name is not None) and (self.check_syncRegionsWithParent.isChecked()):
			localRegion = getattr(self, name)
			parentRegion = getattr(self.parent, name)
			parentRegion.setRegion(localRegion.getRegion())
	def updateLocalRegion(self, signal=None, name=None):
		"""
		Called whenever a window is changed in the main GUI (pulse tab)
		and should also update the viewer's plot.

		:param name: the name of the plot region
		:type name: str
		"""
		if (name is not None) and (self.check_syncRegionsWithParent.isChecked()):
			localRegion = getattr(self, name)
			parentRegion = getattr(self.parent, name)
			localRegion.setRegion(parentRegion.getRegion())
	
	
	def doFilter(self):
		"""
		Performs a filter on the plotted data, based on what is specified by the GUI
		elements.

		Note that this is called whenever the plotted items are updated.
		"""
		self.triggerPlotSWTrigPreFilt.setData(self.parent.swTrig['t'], list(self.parent.swTrig['x']))
		if self.combo_useFilter2.currentIndex() == 0: # show fully-filtered trace
			try:
				if self.combo_filterType.currentIndex() == 0:
					log.warning("(JetMFLISWTriggerViewer) you haven't selected a filter to perform!")
					return
				elif self.combo_filterType.currentIndex() == 1:
					val = self.txt_filterCoeff1.value()
					if val == 0.0:
						log.warning("(JetMFLISWTriggerViewer) you must set an absolute cutoff for the clipAbsY filter!")
						return
					self.parent.swTrig['x'] = np.clip(self.parent.swTrig['x'], -val, val)
				elif self.combo_filterType.currentIndex() == 2:
					val = int(self.txt_filterCoeff1.value())
					if val == 0.0:
						log.warning("(JetMFLISWTriggerViewer) you must set a window size for the wienerY filter!")
						return
					self.parent.swTrig['x'] -= Filters.get_wiener(self.parent.swTrig['x'], val)
				elif self.combo_filterType.currentIndex() == 3:
					val = int(self.txt_filterCoeff1.value())
					if val == 0.0:
						log.warning("(JetMFLISWTriggerViewer) you must set a window size for the medfiltY filter!")
						return
					self.parent.swTrig['x'] = scipy.signal.medfilt(self.parent.swTrig['x'], int(val))
				elif self.combo_filterType.currentIndex() == 4:
					ford = int(self.txt_filterCoeff1.value())
					ffreq = self.txt_filterCoeff2.value()
					if ford == 0:
						log.warning("(JetMFLISWTriggerViewer) you must set a window size for the ffbutterY filter!")
						return
					if (ffreq < 0) or (ffreq > 1):
						log.warning("(JetMFLISWTriggerViewer) you must set a Nyquist-normalized frequency (0.0 to 0.99) for the ffbutterY filter!")
						return
					b, a = scipy.signal.butter(ford, ffreq, btype='low', analog=False, output='ba')
					self.parent.swTrig['x'] = scipy.signal.filtfilt(b, a, self.parent.swTrig['x'], padlen=20)
			except:
				log.exception("(JetMFLISWTriggerViewer) received an exception: %s" % sys.exc_info()[1])
				return
		elif self.combo_useFilter2.currentIndex() == 1: # show windowed trace
			log.warning("(JetMFLISWTriggerViewer) filtering only the window is not yet supported!")
			return
		elif self.combo_useFilter2.currentIndex() > 1: # show windowed trace
			try:
				self.triggerPlotSWTrigPreFilt.setData(self.parent.swTrig['t'], self.parent.swTrig['xBackup'])
			except:
				return
		else: # filter should already be done from main thread
			return
	def updateSWTrigPlot(self, signal=None):
		"""
		Updates the trace for the current time-resolved SW Trig data.
		"""
		if self.check_useFilter1.isChecked():
			self.doFilter()
		else:
			self.triggerPlotSWTrigPreFilt.setData([],[])
		self.triggerPlotSWTrig.setData(self.parent.swTrig['t'], self.parent.swTrig['x'])
		if self.check_saveTraces.isChecked():
			timestamp = str(datetime.datetime.now()).replace(':', '-').replace(' ', '_')
			scanFilename = "%s/SWTrigTrace_%s.csv" % (self.saveDir, timestamp)
			fileHandle = codecs.open(scanFilename, 'w', encoding='utf-8')
			fileHandle.write('#t,x\n')
			for t,x in zip(self.parent.swTrig['t'], self.parent.swTrig['x']):
				fileHandle.write('%e,%e\n' % (t,x))
			fileHandle.close()
		if self.check_showTiming.isChecked():
			dt = timer() - self.lastUpdateTime
			fps = 1/dt
			msg = "dt was %.1e (%.1e per s)" % (dt, fps)
			self.triggerPlotFig.getPlotItem().setTitle(msg)
			self.lastUpdateTime = timer()




Ui_QtProLineFitter, QDialog = loadUiType(os.path.join(ui_path, 'JetMFLIScopeViewer.ui'))
class JetMFLIScopeViewer(QDialog, Ui_QtProLineFitter):
	"""
	Provides a dialog window that for viewing the pulse triggers and
	the SW Trigger data stream from the lockin (ZI MFLI).
	"""
	def __init__(self, parent=None):
		"""
		:param parent: the parent GUI
		:type parent: QtGui.QMainWindow
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.parent = parent
		
		# set up GUI elements
		self.combo_connType.addItem("172.16.27.30")
		self.combo_connType.addItem("parent GUI")
		self.txt_connStatus.setText("disconnected")
		self.combo_trigChan.addItem("TrigIn1")
		self.combo_trigChan.addItem("TrigIn2")
		self.combo_trigChan.setCurrentIndex(0)
		self.combo_trigEdge.addItem("Rising")
		self.combo_trigEdge.addItem("Falling")
		self.combo_trigEdge.setCurrentIndex(0)
		self.txt_trigDelay.opts['formatString'] = "%.1e"
		self.txt_trigDelay.setValue(0.0)
		self.sigChannels = [
			"SigInVoltage", "SigInCurrent",
			"TrigIn1", "TrigIn2",
			"AuxIn1", "AuxIn2"]
		self.sigChannelsToNum = {
			"SigInVoltage":0,
			"SigInCurrent":1,
			"TrigIn1":2,
			"TrigIn2":3,
			"AuxIn1":8,
			"AuxIn2":9}
		for c in self.sigChannels:
			self.combo_sigChan.addItem(c)
		self.combo_sigChan.setCurrentIndex(self.sigChannels.index("AuxIn2"))
		self.samplingRates = [
			"60 MHz", "30 MHz", "15 MHz", "7.5 MHz", "3.75 MHz", "1.88 MHz",
			"938 kHz", "469 kHz", "234 kHz", "117 kHz", "58.6 kHz", "29.3 kHz",
			"14.6 kHz", "7.32 kHz", "3.66 kHz", "1.83 kHz", "916 Hz"]
		for f in self.samplingRates:
			self.combo_sampRate.addItem(f)
		self.combo_sampRate.setCurrentIndex(self.samplingRates.index("469 kHz"))
		self.txt_bufferLen.opts['formatString'] = "%d"
		self.txt_bufferLen.opts['min'] = 10
		self.txt_bufferLen.opts['max'] = 16384
		self.txt_bufferLen.setValue(4000)
		self.txt_pollLen.opts['formatString'] = "%.1e"
		self.txt_pollLen.setValue(1)
		self.txt_pollTimeout.opts['formatString'] = "%d"
		self.txt_pollTimeout.setValue(50)
		
		# initialize internal settings
		self.socketMFLI = None
		self.plots = []
		
		# button functionalities
		self.btn_connect.clicked.connect(self.connect)
		self.btn_disconnect.clicked.connect(self.disconnect)
		self.btn_calcTimes.clicked.connect(self.calcTimes)
		self.check_autoUpdateTimes.stateChanged.connect(self.autoUpdateTimes)
		self.btn_pollAsync.clicked.connect(self.pollAsync)
		self.btn_pollTrig.clicked.connect(self.pollTrig)
		self.btn_pollTest.clicked.connect(self.pollTest)
	
	
	def connect(self, mouseEvent=None):
		"""
		Connects to the MFLI.
		"""
		if self.socketMFLI is not None:
			log.warning("(JetMFLIScopeViewer) there's already a socket connection..")
			return
		elif str(self.combo_connType.currentText()) == "172.16.27.30":
			try:
				from Instruments import lockin
				self.socketMFLI = lockin.mfli(host="172.16.27.30", port=8004)
			except ImportError:
				self.txt_connStatus.setText("disconnected; ImportError")
			except RuntimeError:
				self.txt_connStatus.setText("disconnected; RuntimeError")
			else:
				self.socketMFLI.identify()
				self.txt_connStatus.setText("connected: %s" % self.socketMFLI.identifier)
				log.info("(JetMFLIScopeViewer) %s" % (self.socketMFLI.props,))
				return
		else:
			raise NotImplementedError("this is still a standalone program.. buy Jake a beer")
	def disconnect(self, mouseEvent=None):
		"""
		Clears the MFLI connection.
		"""
		self.socketMFLI = None
		self.txt_connStatus.setText("disconnected")
	
	
	def calcTimes(self, mouseEvent=None, sigEvent=None):
		"""
		Updates all the GUI elements based on buffer delay/offset/length.

		Note that the signal events are all ignored, but necessary because
		some of the slots emit them by default.
		"""
		# get relevant parameters
		delay = self.txt_trigDelay.value()
		offset = self.slider_timeOffset.value() * 0.01
		numPts = self.txt_bufferLen.value()
		rate = str(self.combo_sampRate.currentText())
		rate = miscfunctions.siEval(rate)
		# update gui elements
		dt = 1/rate
		start = 0.0 - (dt*numPts*offset) + delay
		end = dt*numPts*(1-offset) + delay
		self.txt_timeStep.setText(miscfunctions.siFormat(dt, suffix='s'))
		self.txt_timeStart.setText(miscfunctions.siFormat(start, suffix='s'))
		self.txt_timeEnd.setText(miscfunctions.siFormat(end, suffix='s'))
	def autoUpdateTimes(self, sigEvent=None):
		if self.check_autoUpdateTimes.isChecked():
			self.txt_trigDelay.textChanged.connect(self.calcTimes)
			self.combo_sampRate.currentIndexChanged.connect(self.calcTimes)
			self.txt_bufferLen.textChanged.connect(self.calcTimes)
			self.slider_timeOffset.valueChanged.connect(self.calcTimes)
		else:
			self.txt_trigDelay.textChanged.disconnect(self.calcTimes)
			self.combo_sampRate.currentIndexChanged.disconnect(self.calcTimes)
			self.txt_bufferLen.textChanged.disconnect(self.calcTimes)
			self.slider_timeOffset.valueChanged.disconnect(self.calcTimes)
	
	
	def pollAsync(self, mouseEvent=None):
		"""
		Collects a trace from the MFLI asynchronously.
		"""
		### check/setup connection
		if self.socketMFLI is None:
			log.warning("(JetMFLIScopeViewer) the MFLI is not connected! fix this and try again...")
			return
		daq = self.socketMFLI.daq
		device = self.socketMFLI.device
		### collect settings
		scope_channel = 0
		in_channel = self.sigChannelsToNum[str(self.combo_sigChan.currentText())]
		rate = self.samplingRates.index(self.combo_sampRate.currentText())
		numPts = int(self.txt_bufferLen.value())
		poll_length = self.txt_pollLen.value()
		poll_timeout = int(self.txt_pollTimeout.value())
		poll_flags = 0
		poll_return_flat_dict = True
		# activate settings
		daq.setInt("/%s/scopes/*/enable" % device, 0) # first disable the scopes
		daq.sync()
		daq.setInt('/%s/scopes/0/length' % device, numPts)
		daq.setInt('/%s/scopes/0/channel' % device, 1 << scope_channel)
		daq.setInt('/%s/scopes/0/channels/%d/inputselect' % (device, scope_channel), in_channel)
		daq.setInt('/%s/scopes/0/channels/%d/bwlimit' % (device, scope_channel), 1) # prevent anti-aliasing
		daq.setInt('/%s/scopes/0/time' % device, rate)
		daq.setInt('/%s/scopes/0/single' % device, 0)
		daq.setInt('/%s/scopes/0/trigenable' % device, 0)
		daq.sync()
		daq.setInt('/%s/scopes/0/enable' % device, 1)
		daq.unsubscribe('*')
		daq.sync()
		### do poll
		daq.subscribe('/%s/scopes/0/wave' % device)
		data = daq.poll(poll_length, poll_timeout, poll_flags, poll_return_flat_dict)
		daq.setInt('/%s/scopes/0/enable' % device, 0)
		daq.sync()
		log.info("(JetMFLIScopeViewer) %s" % data)
		log.info("(JetMFLIScopeViewer) len: %s" % len(data['/%s/scopes/0/wave' % device]))
		### plot
		self.clearPlot()
		for idx,shot in enumerate(data['/%s/scopes/0/wave' % device]):
			log.info("(JetMFLIScopeViewer) processing wave #%s" % (idx+1))
			wave = shot['wave']
			totalsamples = len(wave)
			t = np.linspace(0, shot['dt']*totalsamples, totalsamples)
			plot = Widgets.SpectralPlot(
				name='%s'%idx, clipToView=True,
				autoDownsample=True, downsampleMethod='subsample')
			self.plotFig.addItem(plot)
			plot.setData(x=t, y=wave)
			plot.update()
			self.plots.append(plot)

	
	def pollTrig(self, mouseEvent=None):
		"""
		Collects triggered data from the MFLI.
		"""
		### check/setup connection
		if self.socketMFLI is None:
			log.warning("(JetMFLIScopeViewer) the MFLI is not connected! fix this and try again...")
			return
		daq = self.socketMFLI.daq
		device = self.socketMFLI.device
		### collect settings
		scope_channel = 0
		trigChan = self.combo_trigChan.currentIndex() + 2
		trigEdge = str(self.combo_trigEdge.currentText())
		delay = self.txt_trigDelay.value()
		in_channel = self.sigChannelsToNum[str(self.combo_sigChan.currentText())]
		log.info("(JetMFLIScopeViewer) %s" % in_channel)
		rate = self.samplingRates.index(self.combo_sampRate.currentText())
		log.info("(JetMFLIScopeViewer) %s" % rate)
		numPts = int(self.txt_bufferLen.value())
		offset = self.slider_timeOffset.value() * 0.01
		poll_length = self.txt_pollLen.value()
		poll_timeout = int(self.txt_pollTimeout.value())
		poll_flags = 0
		poll_return_flat_dict = True
		# activate settings
		daq.setInt("/%s/scopes/*/enable" % device, 0) # first disable the scopes
		daq.setInt('/%s/scopes/0/channel' % device, 1 << scope_channel)
		daq.setInt('/%s/scopes/0/single' % device, 0)
		daq.setInt('/%s/scopes/0/trigenable' % device, 1)
		daq.setInt('/%s/scopes/0/trigchannel' % device, trigChan)
		if trigEdge.lower() == "rising":
			daq.setInt('/%s/scopes/0/trigrising' % device, 1)
			daq.setInt('/%s/scopes/0/trigfalling' % device, 0)
		else:
			daq.setInt('/%s/scopes/0/trigrising' % device, 0)
			daq.setInt('/%s/scopes/0/trigfalling' % device, 1)
		daq.setDouble('/%s/scopes/0/triglevel' % device, 0.5)
		daq.setDouble('/%s/scopes/0/trigdelay' % device, delay)
		daq.setInt('/%s/scopes/0/channels/%d/inputselect' % (device, scope_channel), in_channel)
		daq.setInt('/%s/scopes/0/time' % device, rate)
		daq.setInt('/%s/scopes/0/length' % device, numPts)
		daq.setDouble('/%s/scopes/0/trigreference' % device, offset)
		daq.setInt('/%s/scopes/0/channels/%d/bwlimit' % (device, scope_channel), 1) # prevent anti-aliasing
		daq.sync()
		daq.setInt('/%s/scopes/0/enable' % device, 1)
		daq.unsubscribe('*')
		daq.sync()
		### do poll
		daq.subscribe('/%s/scopes/0/wave' % device)
		data = daq.poll(poll_length, poll_timeout, poll_flags, poll_return_flat_dict)
		daq.setInt('/%s/scopes/0/enable' % device, 0)
		daq.sync()
		log.info("(JetMFLIScopeViewer) %s" % data)
		log.info("(JetMFLIScopeViewer) len: %s" % len(data['/%s/scopes/0/wave' % device]))
		### plot
		self.plotFig.clear()
		for idx,shot in enumerate(data['/%s/scopes/0/wave' % device]):
			log.info("(JetMFLIScopeViewer) processing wave #%s" % (idx+1))
			wave = shot['wave']
			totalsamples = len(wave)
			t = np.linspace(0, shot['dt']*totalsamples, totalsamples)
			self.plots.append(Widgets.SpectralPlot(
				name='%s'%idx, clipToView=True,
				autoDownsample=True, downsampleMethod='subsample'))
			self.plotFig.addItem(self.plots[-1])
			self.plots[-1].setData(x=t, y=wave)
			self.plots[-1].update()
	
	
	def pollTest(self, mouseEvent=False):
		"""
		Performs some tests of the polling.
		"""
		import zhinst
		### check/setup connection
		#if self.socketMFLI is None:
		#	print("the MFLI is not connected! fix this and try again...")
		#	return
		#daq = self.socketMFLI.daq
		#device = self.socketMFLI.device
		#props = self.socketMFLI.props
		import zhinst.utils
		(daq, device, props) = zhinst.utils.create_api_session('dev3367', 5)
		log.info("(JetMFLIScopeViewer) %s" % (props,))
		
		# Create a base instrument configuration: disable all outputs, demods and scopes.
		general_setting = [['/%s/sigouts/*/enables/*' % device, 0],
						   ['/%s/scopes/*/enable' % device, 0]]
		node_branches = daq.listNodes('/%s/' % device, 0)
		if 'DEMODS' in node_branches:
			general_setting.append(['/%s/demods/*/enable' % device, 0])
		daq.set(general_setting)
		# Perform a global synchronisation between the device and the data server:
		# Ensure that the settings have taken effect on the device before setting
		# the next configuration.
		daq.sync()
		
		# Now configure the instrument for this experiment. The following channels
		# and indices work on all device configurations. The values below may be
		# changed if the instrument has multiple input/output channels and/or either
		# the Multifrequency or Multidemodulator options installed.
		# Signal output mixer amplitude [V].
		amplitude = 0.500
		out_channel = 0
		# Get the value of the instrument's default Signal Output mixer channel.
		out_mixer_channel = 0 #zhinst.utils.default_output_mixer_channel(props)
		in_channel = 0
		osc_index = 0
		scope_in_channel = 0  # scope input channel
		frequency = 400e3
		exp_setting = [
			# The output signal.
			['/%s/sigouts/%d/on'             % (device, out_channel), 1],
			['/%s/sigouts/%d/enables/%d'     % (device, out_channel, out_mixer_channel), 1],
			['/%s/sigouts/%d/range'          % (device, out_channel), 1],
			['/%s/sigouts/%d/amplitudes/%d'  % (device, out_channel, out_mixer_channel), amplitude],
			['/%s/sigins/%d/imp50'           % (device, in_channel), 1],
			['/%s/sigins/%d/ac'              % (device, in_channel), 0],
			['/%s/sigins/%d/range'           % (device, in_channel), 2*amplitude],
			['/%s/oscs/%d/freq'              % (device, osc_index), frequency]]
		if 'DEMODS' in node_branches:
			# NOTE we don't need any demodulator data for this example, but we need
			# to configure the frequency of the output signal on out_mixer_c.
			general_setting.append(['/%s/demods/%d/oscselect' % (device, out_mixer_channel), osc_index])
		daq.set(exp_setting)
		
		# Perform a global synchronisation between the device and the data server:
		# Ensure that the signal input and output configuration has taken effect
		# before calculating the signal input autorange.
		daq.sync()
		
		# Perform an automatic adjustment of the signal inputs range based on the
		# measured input signal's amplitude measured over approximately 100 ms.
		# This is important to obtain the best bit resolution on the signal inputs
		# of the measured signal in the scope.
		# zhinst.utils.sigin_autorange(daq, device, in_channel)
		
		# Now configure the scope via the /devx/scopes/0/ node tree branch.
		# 'length' : the length of the scope shot
		daq.setInt('/%s/scopes/0/length' % device, int(4.0e3))
		# 'channel' : select the scope channel(s) to enable.
		#  Bit-encoded as following:
		#   1 - enable scope channel 0
		#   2 - enable scope channel 1
		#   3 - enable both scope channels (requires DIG option)
		# NOTE we are only interested in one scope channel: scope_in_c and leave the
		# other channel unconfigured
		daq.setInt('/%s/scopes/0/channel' % device, 1 << in_channel)
		# 'channels/0/bwlimit' : bandwidth limit the scope data. Enabling bandwidth
		# limiting avoids antialiasing effects due to subsampling when the scope
		# sample rate is less than the input channel's sample rate.
		#  Bool:
		#   0 - do not bandwidth limit
		#   1 - bandwidth limit
		daq.setInt('/%s/scopes/0/channels/%d/bwlimit' % (device, scope_in_channel), 1)
		# 'channels/0/inputselect' : the input channel for the scope:
		#   0 - signal input 1
		#   1 - signal input 2
		#   2, 3 - trigger 1, 2 (front)
		#   8-9 - auxiliary inputs 1-2
		#   The following inputs are additionally available with the DIG option:
		#   10-11 - oscillator phase from demodulator 3-7
		#   16-23 - demodulator 0-7 x value
		#   32-39 - demodulator 0-7 y value
		#   48-55 - demodulator 0-7 R value
		#   64-71 - demodulator 0-7 Phi value
		#   80-83 - pid 0-3 out value
		#   96-97 - boxcar 0-1
		#   112-113 - cartesian arithmetic unit 0-1
		#   128-129 - polar arithmetic unit 0-1
		#   144-147 - pid 0-3 shift value
		daq.setInt('/%s/scopes/0/channels/%d/inputselect' % (device, scope_in_channel), 9)
		# 'time' : timescale of the wave, sets the sampling rate to 1.8GHz/2**time.
		#   0 - sets the sampling rate to 1.8 GHz
		#   1 - sets the sampling rate to 900 MHz
		#   ...
		#   16 - sets the samptling rate to 27.5 kHz
		daq.setInt('/%s/scopes/0/time' % device, 7)
		# 'single' : only get a single scope shot.
		#   0 - take continuous shots
		#   1 - take a single shot
		daq.setInt('/%s/scopes/0/single' % device, 0)
		# 'trigenable' : enable the scope's trigger (boolean).
		#   0 - take continuous shots
		#   1 - take a single shot
		daq.setInt('/%s/scopes/0/trigenable' % device, 0)
		
		# Perform a global synchronisation between the device and the data server:
		# Ensure that the settings have taken effect on the device before issuing the
		# ``poll`` command and clear the API's data buffers to remove any old data.
		daq.sync()
		
		# 'enable' : enable the scope
		daq.setInt('/%s/scopes/0/enable' % device, 1)
		
		# Unsubscribe from any streaming data
		#daq.unsubscribe('*')
		
		# Perform a global synchronisation between the device and the data server:
		# Ensure that the settings have taken effect on the device before issuing the
		# ``poll`` command and clear the API's data buffers to remove any old data.
		daq.sync()
		
		# Subscribe to the scope's data.
		daq.subscribe('/%s/scopes/0/wave' % device)
		
		# First, poll data without triggering enabled.
		poll_length = 1.0  # [s]
		poll_timeout = 10  # [ms]
		poll_flags = 0
		poll_return_flat_dict = True
		data_no_trig = daq.poll(poll_length, poll_timeout, poll_flags, poll_return_flat_dict)
		
		# Disable the scope.
		daq.setInt('/%s/scopes/0/enable' % device, 0)
		
		# Now configure the scope's trigger to get aligned data
		# 'trigenable' : enable the scope's trigger (boolean).
		#   0 - take continuous shots
		#   1 - take a single shot
		daq.setInt('/%s/scopes/0/trigenable' % device, 1)
		
		# Specify the trigger channel, we choose the same as the scope input
		daq.setInt('/%s/scopes/0/trigchannel' % device, 2)
		
		# Trigger on rising edge?
		daq.setInt('/%s/scopes/0/trigrising' % device, 1)
		
		# Trigger on falling edge?
		daq.setInt('/%s/scopes/0/trigfalling' % device, 0)
		
		# Set the trigger threshold level.
		daq.setDouble('/%s/scopes/0/triglevel' % device, 0.5)
		
		# Set hysteresis triggering threshold to avoid triggering on noise
		# 'trighysteresis/mode' :
		#  0 - absolute, use an absolute value ('scopes/0/trighysteresis/absolute')
		#  1 - relative, use a relative value ('scopes/0trighysteresis/relative') of the trigchannel's input range
		#      (0.1=10%).
		daq.setDouble('/%s/scopes/0/trighysteresis/mode' % device, 1)
		daq.setDouble('/%s/scopes/0/trighysteresis/relative' % device, 0.1)  # 0.1=10%
		
		# Set the trigger hold-off mode of the scope. After recording a trigger event, this specifies when the scope should
		# become re-armed and ready to trigger, 'trigholdoffmode':
		#  0 - specify a hold-off time between triggers in seconds ('scopes/0/trigholdoff'),
		#  1 - specify a number of trigger events before re-arming the scope ready to trigger ('scopes/0/trigholdcount').
		daq.setInt('/%s/scopes/0/trigholdoffmode' % device, 0)
		daq.setDouble('/%s/scopes/0/trigholdoff' % device, 0.01)
		daq.setDouble('/%s/scopes/0/trigreference' % device, 0.5)
		
		# Set trigdelay to 0.: Start recording from when the trigger is activated.
		daq.setDouble('/%s/scopes/0/trigdelay' % device, 0.0)
		
		# Disable trigger gating.
		daq.setInt('/%s/scopes/0/triggate/enable' % device, 0)
			
		# Disable segmented data recording.
		daq.setInt('/%s/scopes/0/segments/enable' % device, 0)
		
		# Perform a global synchronisation between the device and the data server:
		# Ensure that the settings have taken effect on the device before issuing the
		# ``poll`` command and clear the API's data buffers to remove any old data.
		daq.sync()
		
		# 'enable' : enable the scope.
		daq.setInt('/%s/scopes/0/enable' % device, 1)
		
		# Subscribe to the scope's data.
		#daq.subscribe('/%s/scopes/0/wave' % device)
		
		data_with_trig = daq.poll(poll_length, poll_timeout, poll_flags, poll_return_flat_dict)
		log.info("(JetMFLIScopeViewer) %s" % (data_with_trig,))
		
		# Disable the scope.
		daq.setInt('/%s/scopes/0/enable' % device, 0)
		
		# Unsubscribe from any streaming data.
		#daq.unsubscribe('*')
	
	
	def clearPlot(self):
		"""
		Clears the plots.
		"""
		if not len(self.plots):
			return
		else:
			for p in self.plots:
				self.plotFig.removeItem(p)
			self.plots = []




Ui_QtProLineFitter, QDialog = loadUiType(os.path.join(ui_path, 'OnlineDataBrowser.ui'))
class OnlineDataBrowser(QDialog, Ui_QtProLineFitter):
	"""
	Provides a dialog window that provides browsing/selection/loading of
	various online spectral data.

	The elements are all organized in a nested tree, where the primary entries
	are groups of child items.
	"""
	def __init__(self, parent=None):
		"""
		:param parent: the parent GUI
		:type parent: QtGui.QMainWindow
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.setWindowTitle("Online Data Browser")
		self.parent = parent
		
		self.treeWidget.setHeaderHidden(True) # if hidden, user cannot sort...
		self.treeWidget.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
		self.treeWidget.customContextMenuRequested.connect(self.showCustomMenu)
		
		# button functionality
		self.btn_update.clicked.connect(self.update)
		self.btn_test.clicked.connect(self.test)
		self.btn_ok.clicked.connect(self.accept)
		self.btn_cancel.clicked.connect(self.reject)
		
		# add standard items (reachable from anywhere)
		self.addASAIsurveys()
		self.addCSOsurveys()
		self.addAirTrans()
		
		# add special-case items (only if reachable)
		self.getCASData()
	
	def update(self, mouseEvent=False):
		"""
		Provides a general routine for refreshing certain elements that
		may not be permanent or defined as built-in (e.g. a node that
		depends on an active browser page that may be refreshed/changed).
		"""
		self.getCASData()

	def test(self, mouseEvent=False):
		"""
		Provides a test routine..
		"""
		log.debug("OnlineDataBrowser.test() does nothing at the moment...")

	def ok(self):
		"""
		'Accepts' the dialog if there are any selected items, yields a 'rejected'
		return signal otherwise. Closes the dialog.
		"""
		if not self.treeWidget.selectedItems():
			self.reject()
		else:
			self.accept()
	def getSpectrum(self):
		"""
		Returns the current item.

		:returns: the currently selected item
		:rtype: list(QTreeWidgetItem)
		"""
		return [self.treeWidget.currentItem()]
	def getSpectra(self):
		"""
		Returns the current items.

		:returns: the currently selected items
		:rtype: list(QTreeWidgetItem)
		"""
		return self.treeWidget.selectedItems()
    
	def showCustomMenu(self, pos):
		"""
		Shows a pop-up menu with links to various URLs related to the
		clicked item.

		Note that unlike the VAMDC browser, this is called in a more
		standard (for Qt) way, where the QTreeWidget has had its
		context menu policy set to provide a custom context menu,
		which is connected to this routine.

		:param pos: the cursor position when called
		:type pos: QPoint
		"""
		item = self.treeWidget.itemAt(pos)
		menu = QtGui.QMenu(self.treeWidget)
		showMenu = False
		if getattr(item, "links", None) is not None:
			showMenu = True
			for link in item.links:
				label = link[0]
				url = link[1]
				linkAction = menu.addAction('view link: %s' % label)
				linkAction.triggered.connect(partial(webbrowser.open, url))
		if getattr(item, "sourceurl", None) is not None:
			showMenu = True
			sourceurlAction = menu.addAction('open source in browser')
			sourceurlAction.triggered.connect(partial(webbrowser.open, item.sourceurl))
		if showMenu:
			menu.exec_(self.treeWidget.mapToGlobal(pos))


	def addParent(self, parent, column, title, links=None, expand=False):
		"""
		Adds a new primary item to the tree.

		:param parent: the parent node for the new item (typically the self.treeWidget.invisibleRootItem())
		:type parent: QTreeWidgetItem
		:param column: unused column specifier
		:type column: int
		:param title: the title of the new item
		:type title: str
		:param links: (optional) a list of links for the context menu (name and URL)
		:type links: enumerable(str, str)
		:param expand: whether to expand the item
		:type expand: bool
		"""
		item = QtGui.QTreeWidgetItem(parent, [title])
		item.setChildIndicatorPolicy(QtGui.QTreeWidgetItem.ShowIndicator)
		item.links = links
		if expand:
			item.setExpanded(True)
		item.setFlags(item.flags() & ~QtCore.Qt.ItemIsSelectable)
		return item
	def addChild(self, parent, column, title, tooltip, sourceurl, links=None, extras=None):
		"""
		Adds a child item to the tree.

		:param parent: the parent node for the new item (typically the self.treeWidget.invisibleRootItem())
		:type parent: QTreeWidgetItem
		:param column: column specifier related to the tooltip
		:type column: int
		:param title: the title of the new item
		:type title: str
		:param tooltip: a tooltip describing the item
		:type tooltip: str
		:param sourceurl: the URL to be used for accessing the item
		:type sourceurl: str
		:param links: (optional) a list of links for the context menu (name and URL)
		:type links: enumerable(str, str)
		:param extras: (optional) a set of extra settings to be used when downloading/plotting the item
		:type extras: dict
		"""
		item = QtGui.QTreeWidgetItem(parent, [title])
		item.setToolTip(column, tooltip)
		item.sourceurl = sourceurl
		item.extras = extras
		item.links = links
		return item
	
	def addCSOsurveys(self, showExpanded=False):
		"""
		Adds a number of broadband line surveys from the CSO.

		:param showExpanded: whether to expand all items when added
		:type showExpanded: bool
		"""
		## parent
		tooltip = (
			"Contains a collection of unbiased line surveys around\n"
			u"λ=1.4mm (240 GHz) toward a variety of star-forming regions.\n"
			"ref: Susanna L. Widicus Weaver et al 2017 ApJS 232 3"
			"\n\nnote: velocity corrections may differ from the publication above\n"
			"during plotting, to better match spectral lines (only if the vel\n"
			"LSR entry shows something like 'a -> b')")
		column = 0
		parent = self.treeWidget.invisibleRootItem()
		cso_item = self.addParent(
			parent, column,
			u"CSO λ=1.3mm (240 GHz) Line Surveys",
			links=[("ApJ pub", "https://doi.org/10.3847/1538-4365/aa8098")],
			expand=showExpanded)
		cso_item.setToolTip(column, tooltip)
		## children
		# B1-b
		name = 'B1-b'
		sourceurl = "https://laasworld.de/storage/cso_surveys/B1-b.csv"
		tooltip = (
			"type: Class 0\n"
			u"α: 3h33m20.8s\n"
			u"δ: +31°7′40.0″\n"
			"vel LSR: +0.39 -> +6.9 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",(-0.39+6.9)*1e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# DR21(OH)
		name = 'DR21(OH)'
		sourceurl = "https://laasworld.de/storage/cso_surveys/DR21-OH.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 20h39m1.1s\n"
			u"δ: +42°22′49.1″\n"
			"vel LSR: -3 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# GAL 10.47+0.03
		name = 'GAL 10.47+0.03'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL10.47+0.03.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 18h08m38.4s\n"
			u"δ: -19°51′51.8″\n"
			"vel LSR: +67.8 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# GAL 12.21-0.1
		name = 'GAL 12.21-0.1'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL12.21-0.1.csv"
		tooltip = (
			"type: HII region\n"
			u"α: 18h12m39.7s\n"
			u"δ: -18°24′20.9″\n"
			"vel LSR: +24 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# GAL 12.91-0.26
		name = 'GAL 12.91-0.26'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL12.91-0.26.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 18h14m39.0s\n"
			u"δ: -17°52′0.0″\n"
			"vel LSR: +37.5 -> +38 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",(-37.5+38)*1e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# GAL 19.61-0.23
		name = 'GAL 19.61-0.23'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL19.61-0.23.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α:  18h27m37.99s\n"
			u"δ: -11°56′42″\n"
			"vel LSR: +40 -> +42 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",(-40+42)*1e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# GAL 24.33+0.11-MM1
		name = 'GAL 24.33+0.11-MM1'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL24.33+0.11-MM1.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 18h35m8.14s\n"
			u"δ: -7°35′1.1″\n"
			"vel LSR: +113.4 -> +114.4 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",1*1e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# GAL 24.78+0.08
		name = 'GAL 24.78+0.08'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL24.78+0.08.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 18h36m12.6s\n"
			u"δ: -7°12′11.0″\n"
			"vel LSR: +111 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# GAL 31.41+0.31
		name = 'GAL 31.41+0.31'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL31.41+0.31.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 18h47m34.61s\n"
			u"δ: -1°12′42.8″\n"
			"vel LSR: +97 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# GAL 34.3+0.2
		name = 'GAL 34.3+0.2'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL34.3+0.2.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 18h53m18.54s\n"
			u"δ: +1°14′57.9″\n"
			"vel LSR: +58 -> +58.6 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",0.6*1e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# GAL 45.47+0.05
		name = 'GAL 45.47+0.05'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL45.47+0.05.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 19h14m25.6s\n"
			u"δ: +11°9′26.0″\n"
			"vel LSR: +62 -> +62.8 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",0.8e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# GAL 75.78+0.34
		name = 'GAL 75.78+0.34'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GAL75.78+0.34.csv"
		tooltip = (
			"type: HII Region\n"
			u"α: 20h21m44.09s\n"
			u"δ: +37°26′39.8″\n"
			"vel LSR: +4 -> 0 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",-4e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# GCM+0.693-0.027
		name = 'GCM+0.693-0.027'
		sourceurl = "https://laasworld.de/storage/cso_surveys/GCM+0.693-0.027.csv"
		tooltip = (
			"type: Shocked Region\n"
			u"α: 17h47m21.86s\n"
			u"δ: -28°21′27.1″\n"
			"vel LSR: +68 -> +72 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",4e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# HH 80-81
		name = 'HH 80-81'
		sourceurl = "https://laasworld.de/storage/cso_surveys/HH80-81.csv"
		tooltip = (
			"type: Outflow\n"
			u"α: 18h19m12.3s\n"
			u"δ: -20°47′27.5″\n"
			"vel LSR: +12.2 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# L1157 MM
		name = 'L1157 MM (aka the B1 region)'
		sourceurl = "https://laasworld.de/storage/cso_surveys/L1157-MM.csv"
		tooltip = (
			"type: Class 0 + Outflow\n"
			u"α: 20h39m10.2s\n"
			u"δ: +68°1′11.5″\n"
			"vel LSR: +2.7 -> +1 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",-1.7e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# L1448-MM1
		name = 'L1448-MM1'
		sourceurl = "https://laasworld.de/storage/cso_surveys/L1448-MM1.csv"
		tooltip = (
			"type: Class 0 + Outflow\n"
			u"α: 3h25m38.8s\n"
			u"δ: +30°44′5″\n"
			"vel LSR: 0 -> +5.3 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",5.3e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# NGC 1333-2A
		name = 'NGC 1333-IRAS2A'
		sourceurl = "https://laasworld.de/storage/cso_surveys/NGC1333-2A.csv"
		tooltip = (
			"type: Hot Corino\n"
			u"α: 3h28m55.4s\n"
			u"δ: +31°14′35.0″\n"
			"vel LSR: +7.8 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# NGC 1333-4A
		name = 'NGC 1333-IRAS4A'
		sourceurl = "https://laasworld.de/storage/cso_surveys/NGC1333-4A.csv"
		tooltip = (
			"type: Hot Corino\n"
			u"α: 3h29m10.3s\n"
			u"δ: +31°13′31.0″\n"
			"vel LSR: +6.8 -> 7.2 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",0.4e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# NGC 1333-4B
		name = 'NGC 1333-IRAS4B'
		sourceurl = "https://laasworld.de/storage/cso_surveys/NGC1333-4B.csv"
		tooltip = (
			"type: Hot Corino\n"
			u"α: 3h29m11.99s\n"
			u"δ: +31°13′8.9″\n"
			"vel LSR: +5 -> +7.2 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",2.2e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# NGC 2264
		name = 'NGC 2264'
		sourceurl = "https://laasworld.de/storage/cso_surveys/NGC2264.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 6h41m12.0s\n"
			u"δ: +9°29′9.0″\n"
			"vel LSR: +7.6 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# NGC 6334-29
		name = 'NGC 6334-29'
		sourceurl = "https://laasworld.de/storage/cso_surveys/NGC6334-29.csv"
		tooltip = (
			"type: Class 0\n"
			u"α: 17h19m57s\n"
			u"δ: -35°57′51″\n"
			"vel LSR: -5 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# NGC 6334-38
		name = 'NGC 6334-38'
		sourceurl = "https://laasworld.de/storage/cso_surveys/NGC6334-38.csv"
		tooltip = (
			"type: Class 0\n"
			u"α: 17h20m18.0s\n"
			u"δ: -35°54′42.0″\n"
			"vel LSR: -5 -> -3.4 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",1.6e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# NGC 6334-43
		name = 'NGC 6334-43'
		sourceurl = "https://laasworld.de/storage/cso_surveys/NGC6334-43.csv"
		tooltip = (
			"type: Class 0\n"
			u"α: 17h20m23.0s\n"
			u"δ: -35°54′55.0″\n"
			"vel LSR: -2.6 -> -0.6 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",2e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# NGC 6334-IN
		name = 'NGC 6334-I(N)'
		sourceurl = "https://laasworld.de/storage/cso_surveys/NGC6334-IN.csv"
		tooltip = (
			"type: Class 0\n"
			u"α: 17h20m55.0s\n"
			u"δ: -35°45′40.0″\n"
			"vel LSR: -2.6 -> -5.2 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",-1.6e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# NGC 7538
		name = 'NGC 7538'
		sourceurl = "https://laasworld.de/storage/cso_surveys/NGC7538.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 23h13m45.7s\n"
			u"δ: +61°28′21.0″\n"
			"vel LSR: -57 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# Orion KL
		name = 'Orion-KL'
		sourceurl = "https://laasworld.de/storage/cso_surveys/Orion-KL.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 5h35m14.16s\n"
			u"δ: -5°22′21.5″\n"
			"vel LSR: +8 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# Sgr B2(N-LMH)
		name = 'Sgr B2(N-LMH)'
		sourceurl = "https://laasworld.de/storage/cso_surveys/Sgr_B2-N-LMH.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 17h47m19.89s\n"
			u"δ: -28°22′19.3″\n"
			"vel LSR: +64 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# W3(H2O)
		name = 'W3(H2O)'
		sourceurl = "https://laasworld.de/storage/cso_surveys/W3-H2O.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 2h27m4.61s\n"
			u"δ: +61°52′25″\n"
			"vel LSR: -47 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
		# W51
		name = 'W51'
		sourceurl = "https://laasworld.de/storage/cso_surveys/W51.csv"
		tooltip = (
			"type: Hot Core\n"
			u"α: 19h23m43.5s\n"
			u"δ: +14°30′34″\n"
			"vel LSR: +55 -> +57 km/s")
		links = None
		extras = {"preprocess": ["vlsrShift",2e3]}
		self.addChild(cso_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# W75N
		name = 'W75N'
		sourceurl = "https://laasworld.de/storage/cso_surveys/W75N.csv"
		tooltip = (
			"type: UC HII\n"
			u"α: 20h38m36.6s\n"
			u"δ: +42°37′32″\n"
			"vel LSR: +10 km/s")
		links = None
		self.addChild(cso_item, column, name, tooltip, sourceurl, links)
	
	def addASAIsurveys(self, showExpanded=False):
		"""
		Adds a number of broadband line surveys from the ASAI IRAM 30m project.

		:param showExpanded: whether to expand all items when added
		:type showExpanded: bool
		"""
		## parent
		links = (
			("MNRAS pub", "https://doi.org/10.1093/mnras/sty937"),
			("project overview", "http://www.iram-institute.org/EN/content-page-344-7-158-240-344-0.html")
		)
		tooltip = (
			"Contains a collection of unbiased line surveys around\n"
			"toward 10 young stellar objects.\n"
			"refs: https://doi.org/10.1093/mnras/sty937 &\n"
			"http://www.iram.fr/ILPA/LP007/readme_asai.txt &\n"
			"http://www.iram-institute.org/EN/content-page-344-7-158-240-344-0.html"
			"\n\nnote: velocity corrections may differ from the header info\n"
			"during plotting, to better match spectral lines (if arrow, ->)!")
		column = 0
		parent = self.treeWidget.invisibleRootItem()
		asai_item = self.addParent(
			parent, column,
			u"ASAI Line Surveys",
			links=links,
			expand=showExpanded)
		asai_item.setToolTip(column, tooltip)
		## children
		# Barnard 1
		name = 'B1 82-112 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/Barnard1/b1_82_112.fits"
		tooltip = (
			"type: First hydrostatic core\n"
			u"α: 3h33m20.8s\n"
			u"δ: +31°7′34.0″\n"
			"vel LSR: +6.5 km/s")
		links = None
		extras = None #{"preprocess": ["vlsrFix",6.5e3]}
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'B1 130-173 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/Barnard1/b1_130_173.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'B1 200-276 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/Barnard1/b1_200_276.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# L1157-B1
		name = 'L1157-B1 72-80 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157-B1/l1157b1_72_80.fits"
		tooltip = (
			"type: Outflow shock spot\n"
			u"α: 20h39m10.2s\n"
			u"δ: +68°1′10.5″\n"
			"vel LSR: +2.6 -> +1 km/s")
		links = None
		extras = {"preprocess": ["vlsrFix",1e3]}
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-B1 78-118 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157-B1/l1157b1_78_118.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-B1 125-133 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157-B1/l1157b1_125_133.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-B1 128-174 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157-B1/l1157b1_128_174.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-B1 200-265 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157-B1/l1157b1_200_265.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-B1 260-320 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157-B1/l1157b1_260_320.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-B1 328-350 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157-B1/l1157b1_328_350.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# L1157mm
		name = 'L1157-mm 72-80 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157mm/l1157mm_72_80.fits"
		tooltip = (
			"type: Class 0, WCCC\n"
			u"α: 20h39m6.3s\n"
			u"δ: +68°2′15.8″\n"
			"vel LSR: +2.6 km/s")
		links = None
		extras = None #{"preprocess": ["vlsrFix",2.6e3]}
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-mm 80-112 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157mm/l1157mm_80_112.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-mm 125-133 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157mm/l1157mm_125_133.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-mm 130-173 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157mm/l1157mm_130_173.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1157-mm 200-276 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1157mm/l1157mm_200_276.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# L1448-R2
		name = 'L1448-R2 80-116 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1448-R2/l1448r2_80_116.fits"
		tooltip = (
			"type: Outflow shock spot\n"
			u"α: 3h25m40.1s\n"
			u"δ: +30°43′31.0″\n"
			"vel LSR: +5.3 km/s")
		links = None
		extras = None #{"preprocess": ["vlsrFix",5.3e3]}
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1448-R2 130-173 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1448-R2/l1448r2_130_173.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1448-R2 200-276 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1448-R2/l1448r2_200_276.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# L1527
		name = 'L1527 72-80 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1527/l1527_72_80.fits"
		tooltip = (
			"type: Class 0, WCCC prototype\n"
			u"α: 4h39m53.9s\n"
			u"δ: +26°3′11.0″\n"
			"vel LSR: +5.9 km/s")
		links = None
		extras = None #{"preprocess": ["vlsrFix",5.9e3]}
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1527 80-112 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1527/l1527_80_112.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1527 125-133 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1527/l1527_125_133.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1527 130-172 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1527/l1527_130_172.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'L1527 200-276 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1527/l1527_200_276.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# L1544
		name = 'L1544 80-106 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/L1544/L1544_80_106.fits"
		tooltip = (
			"type: Evolved prestellar core\n"
			u"α: 5h4m17.2s\n"
			u"δ: +25°10′42.8″\n"
			"vel LSR: +6 -> +7.2 km/s")
		links = None
		extras = {"preprocess": ["vlsrFix",7.2e3]}
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# NGC 1333-IRAS4A
		name = 'NGC 1333-IRAS4A 72-80 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/IRAS4A/iras4a_72_80.fits"
		tooltip = (
			"type: Class 0, Hot corino\n"
			u"α: 3h29m10.4s\n"
			u"δ: +31°13′32.2″\n"
			"vel LSR: +6.8 -> +7.2 km/s")
		links = None
		extras = {"preprocess": ["vlsrFix",7.2e3]}
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'NGC 1333-IRAS4A 80-112 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/IRAS4A/iras4a_80_112.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'NGC 1333-IRAS4A 125-133 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/IRAS4A/iras4a_125_133.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'NGC 1333-IRAS4A 130-173 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/IRAS4A/iras4a_130_173.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'NGC 1333-IRAS4A 200-276 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/IRAS4A/iras4a_200_276.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# SVS 13A
		name = 'SVS 13A 72-80 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/SVS13A/svs13a_72_80.fits"
		tooltip = (
			"type: Class I, Hot corino\n"
			u"α: 3h29m3.7s\n"
			u"δ: +31°16′3.8″\n"
			"vel LSR: +6 -> +8 km/s")
		links = None
		extras = {"preprocess": ["vlsrFix",8e3]}
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'SVS 13A 80-116 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/SVS13A/svs13a_80_116.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'SVS 13A 125-133 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/SVS13A/svs13a_125_133.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'SVS 13A 130-173 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/SVS13A/svs13a_130_173.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		name = 'SVS 13A 200-276 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/SVS13A/svs13a_200_276.fits"
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# TMC-1
		name = 'TMC-1 130-165 GHz'
		sourceurl = "https://laasworld.de/storage/asai_surveys/TMC1/tmc1_130_165.fits"
		tooltip = (
			"type: Early prestellar core\n"
			u"α: 4h41m41.9s\n"
			u"δ: +25°41′27.1″\n"
			"vel LSR: +6.0 km/s")
		links = None
		extras = None #{"preprocess": ["vlsrFix",6e3]}
		self.addChild(asai_item, column, name, tooltip, sourceurl, links=links, extras=extras)
	
	def addAirTrans(self, showExpanded=False):
		"""
		Adds a number of transmission spectra according to a model of
		air under STP (standard temperature and pressure).

		:param showExpanded: whether to expand all items when added
		:type showExpanded: bool
		"""
		## parent
		tooltip = (
			"Contains a collection of model transmission spectra through\n"
			"1 meter of air (1 ATM pressure, unknown temp. & humidity).\n"
			"source: C.Endres via J.R. Pardo (priv. comm.)\n"
			"ref: J.R. Pardo, J. Cernicharo, and E. Serabyn (2001)")
		column = 0
		parent = self.treeWidget.invisibleRootItem()
		misc_item = self.addParent(
			parent, column,
			"1m Air Transmission",
			links=None,
			expand=showExpanded)
		misc_item.setToolTip(column, tooltip)
		## children
		# Atm1mLaborGHz
		name = '1m Air Transmission (frequency)'
		sourceurl = "https://laasworld.de/storage/Atm1mLabor/Atm1mLaborGHz.csv"
		tooltip = ("ref: C.Endres via J.R. Pardo (priv. comm.)")
		links = None
		extras = {"unit": "GHz", "skipFirst":True, "filetype":"csv"}
		self.addChild(misc_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# Atm1mLaborWavenumber
		name = '1m Air Transmission (wavenumber)'
		sourceurl = "https://laasworld.de/storage/Atm1mLabor/Atm1mLaborWavenumber.csv"
		tooltip = ("ref: C.Endres via J.R. Pardo (priv. comm.)")
		links = None
		extras = {"unit": "cm-1", "skipFirst":True, "filetype":"csv"}
		self.addChild(misc_item, column, name, tooltip, sourceurl, links=links, extras=extras)
		# Atm1mLaborMicron
		name = '1m Air Transmission (wavelength)'
		sourceurl = "https://laasworld.de/storage/Atm1mLabor/Atm1mLaborMicron.csv"
		tooltip = ("ref: C.Endres via J.R. Pardo (priv. comm.)")
		links = None
		extras = {"unit": u"μm", "skipFirst":True, "filetype":"csv"}
		self.addChild(misc_item, column, name, tooltip, sourceurl, links=links, extras=extras)
	
	def getCASData(self, event=None, showExpanded=False):
		"""
		Initializes the routine to possibly interface with the CAS
		DataManagement server. If a browser appears to exist as a
		child of the parent widget, this will execute some javascript
		in an attempt to retrieve the current (filtered!) table of
		data.

		If a table of items was successfully retrieved, it populates
		a parent and children in a similar fashion to other routines
		above.

		Note that the javascript is executed asynchronously, and will
		therefore usually not update immediately.

		:param showExpanded: whether to expand all items when added
		:type showExpanded: bool
		"""
		if "CASbrowser" in dir(self.parent):
			if distutils.version.LooseVersion(pg.Qt.QtVersion) < "5.6":
				log.warning("(OnlineDataBrowser) ignoring the WebKit-based browser")
				return
			try:
				@contextmanager
				def wait_signal(signal, timeout=2000):
					"""Block loop until signal emitted, or timeout (ms) elapses."""
					loop = QtCore.QEventLoop()
					signal.connect(loop.quit)
					yield
					if timeout is not None:
						QtCore.QTimer.singleShot(timeout, loop.quit)
					loop.exec_()
				with wait_signal(self.parent.CASbrowser.jsFinished, timeout=2000):
					jsreturn = self.parent.CASbrowser.runJavaScript("table;")
				jsresult = self.parent.CASbrowser.jsresult
				if jsresult is not None and "context" in jsresult:
					table = jsresult['context'][0]
				else:
					return
				filteredIdx = table['aiDisplay']
				if ("oInit" in table) and ("aaData" in table['oInit']):
					filteredData = [table['oInit']['aaData'][idx] for idx in filteredIdx]
				elif ("aoData" in table):
					filteredData = [table['aoData'][idx]['_aFilterData'][:-1] for idx in filteredIdx]
				else:
					filteredData = "missing something here..."
					for k,v in table.items():
						log.debug("(OnlineDataBrowser) %s -> %s" % (k,v))
				if len(filteredData):
					## parent
					tooltip = (
						"Contains spectra shown in the CASDataBrowser (CTRL+B).\n"
						"Use the search form to narrow down the selection.. will\n"
						"not work well if you haven't narrowed the selection down\n"
						"to a reasonable number of spectra (ca. <100).")
					column = 0
					parent = self.treeWidget.invisibleRootItem()
					casdata_item = self.addParent(
						parent, column,
						"CAS Spectral Data (%s)" % (datetime.datetime.now(),),
						links=None,
						expand=showExpanded)
					casdata_item.setToolTip(column, tooltip)
					## children
					for dataItem in filteredData:
						specID = dataItem[0]
						specName = dataItem[1]
						name = '%s - %s' % (specID, specName)
						sourceurl = "%s/spectra/spectra/%s/download" % (
							self.parent.CASbrowser.url.rstrip("/"), specID)
						tooltip = "\n".join([
							"experiment: %s" % dataItem[2],
							"sample: %s" % dataItem[3],
							"freq range: %s" % dataItem[4],
							"saved on: %s" % dataItem[5],
							"full title: %s" % dataItem[6],
							"full comments: %s" % dataItem[7],
						])
						links = None
						extras = {"filetype":"casac"}
						self.addChild(casdata_item, column, name, tooltip, sourceurl, links=links, extras=extras)
				else:
					log.warning("(OnlineDataBrowser) data is missing from the CAS data browser.. try to refesh")
			except:
				log.exception("(OnlineDataBrowser) received an error with the CAS data browser: %s" % (sys.exc_info(),))
		else:
			log.warning("(OnlineDataBrowser) CAS data browser is missing.. try CTRL+B first")




Ui_PlotDesigner, QDialog = loadUiType(os.path.join(ui_path, 'PlotDesigner.ui'))
class PlotDesigner(QDialog, Ui_PlotDesigner):
	"""
	Provides a dialog for generating a print-worthy plot.
	"""
	def __init__(
		self,
		spectra=None,
		catalogs=None,
		labels=None,
		style=None,
		viewrange=None,
		useDefaultRC=True):
		"""
		Initializes the dialog.
		
		Note about lists of plots:
		Spectra and catalogs can either be lists of objects containing
		Spectrum and Predictions objects, or they can be a list of dicts
		which contain both the 'spec' and 'cat' items alongside a 'style'
		item.
		
		Note about styles:
		Styles should be a list of dictionaries, which use
		items/value pairs that match the keywords compatible with the
		relevant matplotlib plot (i.e. matplotlib.lines.Line2D or
		matplotlib.pyplot.bar) properties.
		
		:param spectra: a list of spectra
		:type spectra: list
		:param catalogs: a list of spectral line catalogs
		:type catalogs: list
		:param style: predefined styles for the plots
		:type style: dict or list
		:param viewrange: plot range, four components: xmin, xmax, ymin, ymax
		:type viewrange: list or tuple
		:param useDefaultRC: whether to clear the matplotlib rcParams upon initialization
		:type useDefaultRC: bool
		"""
		super(self.__class__, self).__init__()
		#self.setWindowIcon(QtGui.QIcon(os.path.join(ui_path, 'question.svg')))
		self.setupUi(self)
		
		# button functionality
		self.btn_resetPlot.clicked.connect(self.initPlot)
		self.btn_setStyle.clicked.connect(self.setStyle)
		self.btn_exportStyle.clicked.connect(self.exportStyle)
		self.btn_setTight.clicked.connect(partial(self.setLayout, style="tight"))
		self.btn_setLoose.clicked.connect(partial(self.setLayout, style="loose"))
		self.btn_resizeSavePrint.clicked.connect(self.resizeSavePrint)
		self.btn_addFillBetween.clicked.connect(self.addFill)
		self.btn_updatePlot.clicked.connect(self.updatePlot)
		self.btn_showConsole.clicked.connect(self.showConsole)
		self.btn_runTest.clicked.connect(self.runTest)
		
		# set tooltips
		self.btn_exportStyle.setToolTip(
			"usage: copy and paste this dictionary near the top of your script, "
			"and then activate it before you make your plots, via\n"
			">matplotlib.pyplot.style.use(myNewPlotStyle)"
			"\n\n"
			"pro tip: you can also put it in your user-defined matplotlibrc for permanence!")
		self.btn_setLoose.setToolTip("pro tip: hold SHIFT to only loosen the current margins")
		
		# keyboard shortcuts
		self.shortcutCtrlT = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+T"), self, self.runTest)
		self.shortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)
		
		# set initial elements/containers
		self.spectra = spectra
		self.catalogs = catalogs
		self.labels = labels
		self.style = "default"
		self.viewrange = viewrange
		self.useDefaultRC = useDefaultRC
		self.combo_style.addItem('default')
		self.combo_style.addItem('custom')
		for s in plt.style.available:
			self.combo_style.addItem(s)
		self.printCMD = "lpr"
		if (sys.platform == 'darwin'):
			self.printCMD += " -o ORIENTATION"
		
		# draw the UI
		self.setupUI() # note this is my own, with CAPITAL-aye (i.e. not the built-in one)
		self.initPlot()
	
	
	def setupUI(self, resetRC=None):
		"""
		Sets up the figure canvas and adds a toolbar (but not the plot itself).
		
		Note that most Dialogs do not involve this additional step, but
		matplotlib appears to demand special care.
		"""
		if (resetRC is not None and resetRC) or (resetRC is None and self.useDefaultRC):
			plt.rcParams = dict(plt.rcParamsDefault)
		
		# first clean up old plot
		if hasattr(self, "canvas"):
			self.removeToolBar(self.navbar)
			del self.navbar
			del self.axis
			self.layout_plot.removeWidget(self.canvas)
			del self.canvas
		# add empty plot
		self.canvas = FigureCanvas(Figure())
		self.layout_plot.addWidget(self.canvas)
		self.navbar = NavigationToolbar(self.canvas, self)
		self.addToolBar(self.navbar)
		self.axis = self.canvas.figure.subplots()
	
	
	def initPlot(self):
		"""
		Creates the plot during initialization. If called later, clears the
		customizations and redraws the plot.
		"""
		self.axis.clear()
		self.plots = []
		if self.viewrange is not None:
			self.axis.axis(self.viewrange)
		from Spectrum import plotlib
		reload(matplotlibqtfigureoptions)
		reload(plotlib)
		if self.spectra is not None:
			results = plotlib.plot_data_with_errorbars(
				spectra=self.spectra,
				xlabel="Frequency (MHz)",
				ylabel="Intensity",
				ax=self.axis)
			self.plots += results['plots']
		if self.catalogs is not None:
			results = plotlib.plot_line_catalogs(
				catalogs=self.catalogs,
				xlabel="Frequency (MHz)",
				ylabel="Intensity",
				ax=self.axis)
			self.plots += results['plots']
		if self.labels is not None:
			for label in self.labels:
				x, y = label['pos']
				s = label['text']
				self.axis.text(x, y, s)
		self.updatePlot()
	
	def setStyle(self, event=None, style=None):
		"""
		Changes the overall visual style of the plot, based either on
		a variety of prefined style libraries built-in, or "custom"
		which provides an input dialog for inserting a dictionary of
		key/value pairs that can be interpreted by matplotlib's rcParams
		system. Alternatively, one could also directly input a dictionary.
		
		:param event: an input event that might come from a signal (mouse click)
		:type event: QEvent
		:param style: the name of a matplotlib style library, or an equivalent dictionary
		:type style: str or dictionary
		"""
		if style is None:
			style = str(self.combo_style.currentText())
		if style == "custom":
			tip = "# Provide here a dictionary with valid key/value pairs for matplotlib.rcParams.\n"
			tip += "# Important: only native Python objects are allowed values (strings, numbers, tuples, lists, dicts, booleans, and None)\n"
			tip += "#\n# For example:"
			tip += """
				#myNewPlotStyle = {
				#  "axes.grid": "True",
				#  "axes.grid.axis": "both",
				#  "axes.labelsize": "medium",
				#  "grid.color": "#cbcbcb",
				#  "grid.linestyle": "dotted",
				#  "xtick.labelsize": "small",
				#  "ytick.labelsize": "small",
				#}
			"""
			tip += "# (you can delete all this, or it will be interpreted as comments and ignored)\n"
			customStyleDialog = BasicTextInput(text=tip.replace("\t",""), size=(400,400))
			if not customStyleDialog.exec_():
				return
			newStyle = str(customStyleDialog.editor.document().toPlainText())
			newStyle = re.sub(r'^#.+\n', '', newStyle, flags=re.M)
			if "=" in newStyle:
				newStyle = re.sub(r'.+=\s?', '', newStyle)
			if "cycler" in newStyle:
				log.warning("(PlotDesigner) color cyclers are not allowed with this dialog!")
				newStyle = re.sub(r'.+cycler.+', '', newStyle, flags=re.M)
			style = ast.literal_eval(newStyle)
			if not isinstance(style, dict):
				return
			if isinstance(self.style, dict) and ("lines." in " ".join(self.style.keys())):
				log.warning("(PlotDesigner) you are trying to define properties for curves, but this only works for future plots.. you must change active curves manually!")
			if "axes.titlesize" in self.style:
				log.warning("(PlotDesigner) unfortunately the title size cannot be applied from the style.. you must change this manually!")
		self.style = style
		plt.style.use(self.style)
		if isinstance(style, str) and (style in plt.style.library):
			style = dict(plt.style.library[style])
		if style == "default":
			plt.rcParams = dict(plt.rcParamsDefault)
		else:
			plt.rcParams.update(style)
		self.setupUI(resetRC=False)
		self.initPlot()
	
	def exportStyle(self, event=None):
		"""
		Provides a text viewer that contains a list of current plot
		customizations, formatted as a dictionary that could also be
		inserted directly into a separate python script to work on
		external matplotlib plots.
		
		:param event: an input event that might come from a signal (mouse click)
		:type event: QEvent
		"""
		### build style dictionary
		# get current style (if a library style was applied)
		if isinstance(self.style, str):
			try:
				style = dict(plt.style.library[self.style])
			except KeyError:
				style = {}
		else:
			style = self.style.copy()
		# helper routines/libraries
		def copyFromRC(key):
			style[key] = plt.rcParams[key]
		FONTSIZES = {
			5.789999999999999: 'xx-small',
			6.9399999999999995: 'x-small',
			8.33: 'small',
			10.0: 'medium',
			12.0: 'large',
			14.399999999999999: 'x-large',
			17.28: 'xx-large',
		}
		# add all the options from the qtfigureoptions dialog
		style['figure.subplot.left'] = self.canvas.figure.subplotpars.left
		style['figure.subplot.top'] = self.canvas.figure.subplotpars.top
		style['figure.subplot.bottom'] = self.canvas.figure.subplotpars.bottom
		style['figure.subplot.right'] = self.canvas.figure.subplotpars.right
		style['figure.subplot.hspace'] = self.canvas.figure.subplotpars.hspace
		style['figure.subplot.wspace'] = self.canvas.figure.subplotpars.wspace
		style['figure.edgecolor'] = self.canvas.figure.properties()['edgecolor']
		style['figure.facecolor'] = self.canvas.figure.properties()['facecolor']
		style['figure.frameon'] = self.canvas.figure.properties()['frameon']
		style['axes.facecolor'] = self.axis.properties()['facecolor']
		if len(self.axis._left_title.get_text()):
			tsize = self.axis._left_title.get_fontsize()
		elif len(self.axis._right_title.get_text()):
			tsize = self.axis._right_title.get_fontsize()
		else:
			tsize = self.axis.title.get_fontsize()
		style['axes.titlesize'] = FONTSIZES.get(tsize, tsize)
		hasXgrid = self.axis.xaxis._gridOnMajor
		hasYgrid = self.axis.yaxis._gridOnMajor
		if hasXgrid or hasYgrid:
			style['axes.grid'] = True
			if hasXgrid and hasYgrid:
				style['axes.grid.axis'] = 'both'
			elif hasXgrid:
				style['axes.grid.axis'] = 'x'
			elif hasYgrid:
				style['axes.grid.axis'] = 'y'
		if self.axis.xaxis.label.get_fontsize() == self.axis.yaxis.label.get_fontsize():
			size = self.axis.yaxis.label.get_fontsize()
			style['axes.labelsize'] = FONTSIZES.get(size, size)
		size = self.axis.get_xticklabels()[0].get_fontsize()
		style['xtick.labelsize'] = FONTSIZES.get(size, size)
		size = self.axis.get_yticklabels()[0].get_fontsize()
		style['ytick.labelsize'] = FONTSIZES.get(size, size)
		xtpos = self.axis.xaxis.properties()['ticks_position']
		if xtpos == "bottom":
			style['xtick.bottom'] = True
			style['xtick.top'] = False
			if len(self.axis.get_xminorticklabels()):
				style['xtick.minor.bottom'] = True
				style['xtick.minor.top'] = False
		elif xtpos == "top":
			style['xtick.bottom'] = False
			style['xtick.top'] = True
			if len(self.axis.get_xminorticklabels()):
				style['xtick.minor.bottom'] = False
				style['xtick.minor.top'] = True
		else:
			style['xtick.bottom'] = True
			style['xtick.top'] = True
			if len(self.axis.get_xminorticklabels()):
				style['xtick.minor.bottom'] = True
				style['xtick.minor.top'] = True
		ytpos = self.axis.yaxis.properties()['ticks_position']
		if xtpos == "left":
			style['ytick.left'] = True
			style['ytick.right'] = False
			if len(self.axis.get_yminorticklabels()):
				style['ytick.minor.bottom'] = True
				style['ytick.minor.top'] = False
		elif xtpos == "right":
			style['ytick.left'] = False
			style['ytick.right'] = True
			if len(self.axis.get_yminorticklabels()):
				style['ytick.minor.bottom'] = False
				style['ytick.minor.top'] = True
		else:
			style['ytick.left'] = True
			style['ytick.right'] = True
			if len(self.axis.get_yminorticklabels()):
				style['ytick.minor.bottom'] = True
				style['ytick.minor.top'] = True
		try:
			style['lines.linewidth'] = self.plots[0].get_linewidth()
			style['lines.linestyle'] = self.plots[0].get_linestyle()
		except AttributeError: # then it's a Container of some sort..
			pass
		copyFromRC('figure.dpi')
		copyFromRC('savefig.dpi')
		copyFromRC('savefig.orientation')
		copyFromRC('ps.papersize')
		copyFromRC('figure.figsize')
		copyFromRC('savefig.format')
		copyFromRC('savefig.transparent')
		### convert to a long string
		text = "myNewPlotStyle = {\n"
		prefix = "  "
		suffix = ",\n"
		for key in sorted(style.keys()):
			value = style[key]
			if isinstance(value, (str, bool)):
				fmt = '"%s"'
			elif isinstance(value, int):
				fmt = "%g"
			elif isinstance(value, float):
				fmt = "%s"
			else:
				msg = "unknown type: %s (%s)" % (value, type(value))
				fmt = '%s'
			text += prefix
			text += '"%s": ' % key
			text += fmt % (value,)
			text += suffix
		text += "}"
		self.styleViewer = BasicTextViewer(text)
		self.styleViewer.show()
	
	def resizeSavePrint(self, event=None, width=None, height=None):
		"""
		Provides a dialog for resizing/saving/printing the plot.
		
		Note about printing: most systems will just use CUPS to print,
		which entails simply running the command "lpr FILETOPRINT", and
		this is the default action in the dialog. Alternatively, one
		can modify the entry for the print command, and this will be
		reused for the current session.
		
		:param event: an input event that might come from a signal (mouse click)
		:type event: QEvent
		:param width: a new width (pixels)
		:type width: int
		:param height: a new height (pixels)
		:type height: int
		"""
		# determine window padding
		padx = self.size().width() - self.canvas.size().width()
		pady = self.size().height() - self.canvas.size().height()
		# process inputs
		if width is None:
			width = self.canvas.size().width()
		if height is None:
			height = self.canvas.size().height()
		# build UI
		import matplotlib.pyplot as plt
		resizeDialog = QtGui.QDialog(parent=None)
		mainlayout = QtGui.QVBoxLayout()
		resizeDialog.setLayout(mainlayout)
		form = QtGui.QFormLayout()
		mainlayout.addLayout(form)
		# add buttons
		btnbox = QtGui.QDialogButtonBox(resizeDialog)
		btnbox.setStandardButtons(QtGui.QDialogButtonBox.Close|QtGui.QDialogButtonBox.Apply|QtGui.QDialogButtonBox.Save)
		def handleButtonClick(button):
			sb = btnbox.standardButton(button)
			if sb == QtGui.QDialogButtonBox.Close:
				resizeDialog.reject()
			elif sb == QtGui.QDialogButtonBox.Apply:
				resizeDialog.apply()
			elif sb == QtGui.QDialogButtonBox.Save:
				resizeDialog.accept()
		btnbox.clicked.connect(handleButtonClick)
		mainlayout.addWidget(btnbox)
		
		# define dpi
		if "savefig.dpi" in plt.rcParams:
			dpi = plt.rcParams['savefig.dpi']
		else:
			dpi = 100
		text_dpi = Widgets.ScrollableText(resizeDialog, constStep=5, formatString="%g")
		text_dpi.setValue(dpi)
		self.olddpi = dpi
		form.addRow("DPI", text_dpi)
		
		# define unit
		combo_unit = QtGui.QComboBox()
		units = ("px", "in.", "cm", "mm")
		for u in units:
			combo_unit.addItem(u)
		self.oldunit = "px"
		form.addRow("Unit", combo_unit)
		
		# define width/height
		unit2fmt = {
			"px":"%g",
			"in.":"%.3f",
			"cm":"%.2f",
			"mm":"%.1f"}
		text_width = Widgets.ScrollableText(resizeDialog, formatString=unit2fmt["px"])
		text_width.setValue(width)
		form.addRow("Width", text_width)
		text_height = Widgets.ScrollableText(resizeDialog, formatString=unit2fmt["px"])
		text_height.setValue(height)
		form.addRow("Height", text_height)
		
		# define orientation
		combo_orientation = QtGui.QComboBox()
		for o in ("landscape", "portrait"):
			combo_orientation.addItem(o)
		form.addRow("Orientation", combo_orientation)
		
		# define papersize
		combo_paper = QtGui.QComboBox()
		papersizes = ("auto", 'letter', 'a5', 'a4', 'a3', 'a2', 'a1', 'a0')
		paper2size = {
			"letter": (8.5, 11),
			"a5": (148, 210),
			"a4": (210, 297),
			"a3": (297, 420),
			"a2": (420, 594),
			"a1": (594, 841),
			"a0": (841, 1189),
		}
		for u in papersizes:
			combo_paper.addItem(u)
		form.addRow("Papersize", combo_paper)
		
		# whether to update tight layout
		combo_newlayout = QtGui.QComboBox()
		for i in ("tight", "full", "loose", "skip"):
			combo_newlayout.addItem(i)
		form.addRow("Update layout", combo_newlayout)
		
		# define format
		combo_format = QtGui.QComboBox()
		formats = ("pdf", "png", "ps", "eps")
		for f in formats:
			combo_format.addItem(f)
		form.addRow("Format", combo_format)
		
		# whether to use transparency
		check_transp = QtGui.QCheckBox()
		form.addRow("Transparency", check_transp)
		
		# define output filename
		btn_fname = QtGui.QPushButton("Output")
		text_fname = QtGui.QLineEdit("")
		form.addRow(btn_fname, text_fname)
		
		# whether to print
		check_print = QtGui.QCheckBox()
		if sys.platform == "win32":
			check_print.setDisabled(True)
		form.addRow("Print", check_print)
		
		# define margins
		label_margins = QtGui.QLabel("Margins")
		label_margins.setToolTip("note: uses the unit above (but if px, margins are ignored)")
		text_mtop = Widgets.ScrollableText(resizeDialog, value=0, formatString="%.2f", constStep=1, min=0)
		text_mleft = Widgets.ScrollableText(resizeDialog, value=0, formatString="%.2f", constStep=1, min=0)
		text_mright = Widgets.ScrollableText(resizeDialog, value=0, formatString="%.2f", constStep=1, min=0)
		text_mbottom = Widgets.ScrollableText(resizeDialog, value=0, formatString="%.2f", constStep=1, min=0)
		for i in (text_mtop, text_mleft, text_mright, text_mbottom):
			i.setAlignment(QtCore.Qt.AlignHCenter)
			i.setMaximumWidth(80)
		# layouts
		layout_margins = QtGui.QVBoxLayout()
		layout_mtop = QtGui.QHBoxLayout()
		layout_mtop.addStretch()
		layout_mtop.addWidget(text_mtop)
		layout_mtop.addStretch()
		layout_margins.addLayout(layout_mtop)
		layout_mcenter = QtGui.QHBoxLayout()
		layout_mcenter.addStretch()
		layout_mcenter.addWidget(text_mleft)
		layout_mcenter.addWidget(text_mright)
		layout_mcenter.addStretch()
		layout_margins.addLayout(layout_mcenter)
		layout_mbottom = QtGui.QHBoxLayout()
		layout_mbottom.addStretch()
		layout_mbottom.addWidget(text_mbottom)
		layout_mbottom.addStretch()
		layout_margins.addLayout(layout_mbottom)
		layout_margins.addWidget(text_mbottom)
		form.addRow(label_margins, layout_margins)
		
		# define print command
		text_print = QtGui.QLineEdit(self.printCMD)
		ttip_print = "To print, this command is called with the output file.."
		ttip_print += "\nHere are some tips for CUPS (use a separate terminal):"
		ttip_print += "\n - view the available printers and default: '>lpstat -p -d'"
		ttip_print += "\n - view the current queue: '>lpq'"
		text_print.setToolTip(ttip_print)
		form.addRow("Print Cmd", text_print)
		
		# define functions
		def dpi_changed(event=None):
			"""
			Sets new pixel sizes (if unit == px), based on a new DPI.
			"""
			if str(combo_unit.currentText()) == "px":
				width = text_width.value()
				height = text_height.value()
				newdpi = text_dpi.value()
				text_width.setValue(width * self.olddpi / newdpi)
				text_height.setValue(height * self.olddpi / newdpi)
				self.olddpi = newdpi
		def convert_unit(value=None, u1=None, u2=None):
			"""
			Converts from one unit to another, based on the DPI, and returns
			this new value.
			"""
			dpi = text_dpi.value()
			# convert to pixels
			if u1 == "px":
				pass
			elif u1 == "in.":
				value *= dpi
			elif u1 == "cm":
				value *= 1/ 2.54 * dpi
			elif u1 == "mm":
				value *= 1 / 25.4 * dpi
			else:
				raise NotImplementedError
			value = int(value)
			# convert to preferred unit
			if u2 == "px":
				pass
			elif u2 == "in.":
				value *= 1 / dpi
			elif u2 == "cm":
				value *= 2.54 / dpi
			elif u2 == "mm":
				value *= 25.4 / dpi
			else:
				raise NotImplementedError
			return value
		def unit_changed(event=None):
			"""
			Updates the size entries if the unit has changed.
			"""
			u1 = self.oldunit
			u2 = str(combo_unit.currentText())
			text_width.opts["constStep"] = convert_unit(1, "px", u2)
			text_width.opts["formatString"] = unit2fmt[u2]
			text_width.setValue(convert_unit(text_width.value(), u1, u2))
			text_height.opts["constStep"] = convert_unit(1, "px", u2)
			text_height.opts["formatString"] = unit2fmt[u2]
			text_height.setValue(convert_unit(text_height.value(), u1, u2))
			for i in (text_mleft, text_mbottom, text_mright, text_mtop):
				if u2 == "px":
					i.opts["constStep"] = 0
				elif u2 == "in.":
					i.opts["constStep"] = 0.25
				elif u2 == "cm":
					i.opts["constStep"] = 0.1
				elif u2 == "mm":
					i.opts["constStep"] = 1
			self.oldunit = u2
		def size_changed(event=None):
			# go back to "auto" paper size
			combo_paper.setCurrentIndex(0)
		def paper_changed():
			"""
			Sets width/height (and changes the unit), if not auto.
			"""
			paper = str(combo_paper.currentText())
			if paper == "auto":
				return
			unit = str(combo_unit.currentText())
			oldwidth = text_width.value()
			oldheight = text_height.value()
			if paper in ("letter",):
				combo_unit.setCurrentIndex(units.index("in."))
			else:
				combo_unit.setCurrentIndex(units.index("mm"))
			size = list(paper2size[paper])
			if str(combo_orientation.currentText()) == "landscape":
				size = list(reversed(size))
			text_width.setValue(size[0])
			text_height.setValue(size[1])
		def choose_fname():
			"""
			Sets width/height (and changes the unit), if not auto.
			"""
			format = str(combo_format.currentText())
			fname = str(text_fname.text())
			if not len(fname):
				fname = os.path.expanduser("~/image.%s" % format)
			filters = ["Any (*.*)"] + ["%s (*.%s)" % (f.upper(), f) for f in formats]
			fname = QtGui.QFileDialog.getSaveFileName(
				parent=self,
				caption="Choose an output file..",
				directory=fname,
				filter=";;".join(filters),
				initialFilter=filters[1+formats.index(format)])
			if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				fname = fname[0]
			if len(fname):
				format = fname.split(".")[-1]
				if format.lower() in formats:
					combo_format.setCurrentIndex(formats.index(format.lower()))
				text_fname.setText(fname)
		
		# set signals
		text_dpi.textChanged.connect(dpi_changed)
		combo_unit.currentIndexChanged.connect(unit_changed)
		text_width.textEdited.connect(size_changed)
		text_height.textEdited.connect(size_changed)
		combo_paper.currentIndexChanged.connect(paper_changed)
		btn_fname.clicked.connect(choose_fname)
		
		# collect values
		def apply():
			unit = str(combo_unit.currentText())
			width = convert_unit(text_width.value(), unit, "px")
			height = convert_unit(text_height.value(), unit, "px")
			dpi_print = text_dpi.value()
			plt.rcParams['savefig.dpi'] = dpi_print
			screenSize = QtGui.QApplication.desktop().availableGeometry()
			if width+padx > screenSize.width() or height+pady > screenSize.height():
				dpi_screen = QtGui.QApplication.desktop().logicalDpiX()
				plt.rcParams['figure.dpi'] = dpi_screen
				width_ratio = (width+padx)/float(screenSize.width())
				height_ratio = (height+pady)/float(screenSize.height())
				aspect_ratio = width/float(height)
				if width_ratio > height_ratio:
					sm_width = int(width/width_ratio*0.8)
					sm_height = int(sm_width/aspect_ratio)
				else:
					sm_height = int(height/height_ratio*0.8)
					sm_width = int(sm_height*aspect_ratio)
				self.resize(sm_width+padx, sm_height+pady)
			else:
				plt.rcParams['figure.dpi'] = dpi_print
				self.resize(width+padx, height+pady)
			newlayout = str(combo_newlayout.currentText())
			if not newlayout == "skip":
				if not unit == "px":
					mleft = text_mleft.value() / text_width.value()
					mbottom = text_mbottom.value() / text_height.value()
					mright = 1 - text_mright.value() / text_width.value()
					mtop = 1 - text_mtop.value() / text_height.value()
				else:
					mleft,mbottom,mright,mtop = 0,0,1,1
				self.setLayout(style=newlayout, margins=(mleft,mbottom,mright,mtop))
		resizeDialog.apply = apply
		if not resizeDialog.exec_():
			return
		resizeDialog.apply() # resize window..
		unit = str(combo_unit.currentText())
		width = convert_unit(text_width.value(), unit, "px")
		height = convert_unit(text_height.value(), unit, "px")
		dpi_print = text_dpi.value()
		paper = str(combo_paper.currentText())
		orientation = str(combo_orientation.currentText())
		format = str(combo_format.currentText())
		plt.rcParams['savefig.format'] = format
		plt.rcParams['ps.papersize'] = paper
		plt.rcParams['savefig.orientation'] = orientation
		width = convert_unit(width, "px", "in.")      # note that mpl prefers inches..
		height = convert_unit(height, "px", "in.")    # ..so the sizes are converted first
		plt.rcParams['figure.figsize'] = width, height
		# get/process filename
		fname = str(text_fname.text())
		if not len(fname):       # blank filename goes to /tmp
			fh, fname = tempfile.mkstemp(
				suffix=".%s" % format)
			os.close(fh)
		elif not "/" in fname:   # bare filenames go to home directory
			fname = "~/%s" % fname
		if "~" in fname:
			fname = os.path.expanduser(fname)
		if not fname[-len(format):] == format:
			fname = "%s.%s" % (fname, format)
		# save figure
		self.axis.figure.savefig(
			fname = fname,
			dpi=dpi_print,
			orientation=orientation,
			papertype=paper,
			transparent=check_transp.isChecked(),
			format=format)
		self.statusbar.showMessage('saved to: %s (%s)' % (fname,datetime.datetime.now()))
		# (optionally) print
		if check_print.isChecked():
			if sys.platform == 'darwin':
				ftype = "pdf" # because it cannot print EPS, but PDF *does* work
			else:
				ftype = "eps"
			fname = "%s.%s" % (fname, ftype)
			self.axis.figure.savefig(
				fname=fname,
				dpi=dpi_print,
				orientation=orientation,
				papertype=paper,
				transparent=check_transp.isChecked(),
				format=ftype)
			self.printCMD = str(text_print.text()).strip()
			self.printCMD = self.printCMD.replace("ORIENTATION", orientation)
			cmd = self.printCMD.split(" ") + [fname]
			log.info("printing using the command: %s" % " ".join(cmd))
			try:
				output = subprocess.check_output(cmd)
			except OSError as e:
				msg = "There was an error invoking %s.." % cmd
				msg += "\n%s" % e
				QtGui.QMessageBox.warning(self, "Runtime Error!", msg, QtGui.QMessageBox.Ok)

	def addFill(self):
		"""
		Provides a dialog where a curve may be filled above or below
		itself, down to or up to a floating point value.
		
		It's basically only good for the niche case of plotting spectral
		transmission through air, and then painting the "blocked"
		transmission with a color.
		"""
		# create basic dialog
		fillDialog = QtGui.QDialog(parent=self)
		mainlayout = QtGui.QVBoxLayout()
		fillDialog.setLayout(mainlayout)
		form = QtGui.QFormLayout()
		mainlayout.addLayout(form)
		# add buttons
		btnbox = QtGui.QDialogButtonBox(fillDialog)
		btnbox.setStandardButtons(QtGui.QDialogButtonBox.Cancel|QtGui.QDialogButtonBox.Ok)
		btnbox.accepted.connect(fillDialog.accept)
		btnbox.rejected.connect(fillDialog.reject)
		mainlayout.addWidget(btnbox)
		# set a dictionary for dynamically choosing/accessing plots
		pDict = {}
		for p in self.plots:
			if not "Line2D" in str(type(p)):
				continue
			pDict[p.get_label()] = p
		# choose target plot
		combo_target = QtGui.QComboBox()
		for p in pDict.keys():
			combo_target.addItem(p)
		form.addRow("Target", combo_target)
		# choose bottom (float or ydata)
		layout_bottom = QtGui.QHBoxLayout()
		combo_bottom = QtGui.QComboBox()
		combo_bottom.addItem("y-data")
		combo_bottom.addItem("float ->")
		combo_bottom.setCurrentIndex(1)
		layout_bottom.addWidget(combo_bottom)
		text_bottom = QtGui.QLineEdit("0.0")
		layout_bottom.addWidget(text_bottom)
		form.addRow("Bottom", layout_bottom)
		# choose top (float or ydata)
		layout_top = QtGui.QHBoxLayout()
		combo_top = QtGui.QComboBox()
		combo_top.addItem("y-data")
		combo_top.addItem("float ->")
		combo_top.setCurrentIndex(0)
		layout_top.addWidget(combo_top)
		text_top = QtGui.QLineEdit("1.0")
		layout_top.addWidget(text_top)
		form.addRow("Top", layout_top)
		# choose color
		import matplotlib.backends.qt_editor.formlayout as mplform
		from matplotlib import colors as mcolors
		layout_color = mplform.ColorLayout(QtGui.QColor(112,112,112,255))
		def update_color(e=None):
			line = pDict.get(str(combo_target.currentText()))
			ec = mcolors.to_rgba(line.get_markerfacecolor(), line.get_alpha())
			ec = mplform.to_qcolor(ec)
			layout_color.update_text(ec)
			layout_color.colorbtn.color = ec
		update_color()
		combo_target.currentIndexChanged.connect(update_color)
		form.addRow("Color", layout_color)
		# choose stacking
		combo_stacking = QtGui.QComboBox()
		combo_stacking.addItem("above all")
		combo_stacking.addItem("same")
		combo_stacking.addItem("below all")
		combo_stacking.setCurrentIndex(1)
		form.addRow("Stacking", combo_stacking)
		
		# get values
		if not fillDialog.exec_():
			return
		p = pDict.get(str(combo_target.currentText()))
		x = p.get_xdata()
		bottom = str(combo_bottom.currentText())
		top = str(combo_top.currentText())
		if all([text[0] == "y" for text in [bottom, top]]):
			log.exception("(PlotDesigner) you can't use ydata for both top and bottom of a filled curve!")
			return
		if bottom[0] == "f":
			bottom = float(str(text_bottom.text()))
		else:
			bottom = p.get_ydata()
		if top[0] == "f":
			top = float(str(text_top.text()))
		else:
			top = p.get_ydata()
		color = layout_color.text()
		stacking = str(combo_stacking.currentText())
		zorder = p.get_zorder()
		if stacking[0] == "a":
			zorder = 1e6
		elif stacking[0] == "b":
			zorder = -1e6
		self.axis.fill_between(x, bottom, top, facecolor=color, zorder=zorder)
		
		# update the plot (just in case)
		self.updatePlot()
	
	def adjustText(self):
		"""
		Tries to use the adjustText package to auto-adjust the
		plot labels (i.e. prevent overlapping items).
		"""
		try:
			from adjustText import adjust_text
			adjust_text(self.axis.texts)
			self.updatePlot()
		except:
			msg = "(PlotDesigner) adjustText wasn't available to fix the"
			msg += " label positions.. try running 'pip install adjustText' (or conda)"
			log.warning(msg)

	def updatePlot(self):
		"""
		Updates the figure canvas and legend.. necessary because the
		plots are not automatically refreshed (because mpl is sloooow).
		"""
		# update legend
		legend = self.axis.legend(loc='best')
		try:
			legend.set_draggable(True)
		except:
			pass
		# update canvas
		self.canvas.draw_idle()
	
	def setLayout(self, event=None, style="tight", margins=None):
		"""
		Redraws the plot after recentering the plot, or fixing/setting
		the margins and/or padding.
		
		:param event: an input event that might come from a signal (mouse click)
		:type event: QEvent
		:param style: the style for the margins/padding (tight, loose or full)
		:type style: str
		:param margins: additional margins to add around the plot (the rect argument for matplotlib.figure.Figure.tight_layout())
		:type margins: str
		"""
		modifier = QtGui.QApplication.keyboardModifiers()
		if style == "full":
			pad = 0.0
		else:
			pad = 1.08
		if not modifier == QtCore.Qt.ShiftModifier:
			if (margins is not None) and isinstance(margins,tuple) and (len(margins)==4):
				self.axis.figure.tight_layout(rect=margins, pad=pad)
			else:
				self.axis.figure.tight_layout(pad=pad)
			self.updatePlot()
		if style == "loose":
			factor = 1.1
			rpad = 1 - self.canvas.figure.subplotpars.right
			tpad = 1 - self.canvas.figure.subplotpars.top
			self.loosenedx = rpad*factor
			self.loosenedy = tpad*factor
			newmargins = {
				"left": self.canvas.figure.subplotpars.left+self.loosenedx,
				"right": self.canvas.figure.subplotpars.right-self.loosenedx,
				"top": self.canvas.figure.subplotpars.top-self.loosenedy,
				"bottom": self.canvas.figure.subplotpars.bottom+self.loosenedy,
			}
			self.canvas.figure.subplots_adjust(**newmargins)
			self.updatePlot()
	
	def showConsole(self):
		"""
		Invoked when the 'Console' button is clicked. It provides a new
		window containing an interactive console that provides a direct
		interface to the current python instance, and adds the gui to
		that namespace for direct interactions.
		"""
		namespace = {
			'self': self,
			'plt': plt,
			'update': self.updatePlot}
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
	
	def runTest(self, inputEvent=None):
		"""
		Invoked when the 'test' button is clicked. It is used only for
		running any temporary tests that might be useful when debugging.
		"""
		testBool = True
		testInt = 457
		testFloat = 3.14152
		testString = "Hello, world!"
		testUnicode = u"Γειά Kóσμε!"
		log.debug("running PlotDesigner.runTest()")



