#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# TODO
# - update to be safer with multiple connections and errors
# - add a checkbox and display for simply showing the current output
#
"""
This module provides an interface for reading/retrieving data from the
Keithley digital multimeter found somewhere in one of the CAS laboratories.

Note: untested for the Keysight devices! They probably work, though..

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import sys
import os
import glob
from functools import partial
import time
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
import numpy as np
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Instruments import multimeter


# determine the correct containing the *.ui files
ui_filename = 'dmm.ui'
ui_path = ""
for p in (os.path.dirname(os.path.realpath(__file__)),
		  os.path.dirname(__file__),
		  os.path.dirname(os.path.realpath(sys.argv[0]))):
	if os.path.isfile(os.path.join(p, ui_filename)):
		ui_path = p # should be most reliable, even through symlinks
		break
	elif os.path.isfile(os.path.join(p, "resources", ui_filename)):
		ui_path = os.path.join(p, "resources") # should be most reliable, even through symlinks
		break
if ui_path == "":
	raise IOError("could not identify the *.ui files")

Ui_dmm, QDialog = loadUiType(os.path.join(ui_path, ui_filename))
class dmmGUI(QDialog, Ui_dmm):
	"""
	blah
	"""
	def __init__(self, gui=None, filename=None, UTCoffset=None):
		"""
		blah
		"""
		super(self.__class__, self).__init__()
		self.setWindowTitle("DMM Reader")
		self.setupUi(self)
		
		# buttons
		self.btn_refreshDev.clicked.connect(self.populateDevList)
		self.btn_connect.clicked.connect(self.connect)
		self.btn_clear.clicked.connect(self.clear)
		self.btn_reset.clicked.connect(self.reset)
		self.btn_reboot.clicked.connect(partial(self.reset, hard_reset=True))
		self.btn_disconnect.clicked.connect(self.disconnect)
		self.btn_initTrig.clicked.connect(self.initTrig)
		self.btn_fetchMem.clicked.connect(self.fetchMem)
		self.btn_readValues.clicked.connect(self.readValues)
		self.btn_console.clicked.connect(self.runConsole)
		self.btn_test.clicked.connect(self.test)
		
		# initialiations
		self.dev = None
		self.populateDevList()
		self.disconnect()
		
		# keyboard shortcuts
		self.keyShortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, partial(self.exit, confirm=False))
	
	
	def populateDevList(self):
		"""
		Populates the QComboBox with candidate /dev/usbtmcXX file entries.
		"""
		devs = ["/dev/usbtmc0"]
		#for d in devs:
		for d in glob.glob('/dev/usbtmc*'):
			self.combo_dev.addItem(d)
	
	
	def connect(self):
		"""
		Attempts to connect to the selected device.
		
		Problems that might arise here:
			* File permissions
				* cause: it's a new computer or clean slate, and the udev
					rules must be updated
				* solution: copy /dev/udev/rules.d/50-usbtmc.rules from
					one of the older lab computers (CASAC or Jet)
			* No USBTMC device is visible
				* cause: who knows..
				* solution: restart the device..check the cables..unplug/re-plug..
		"""
		if self.combo_dev.currentText():
			try:
				host = str(self.combo_dev.currentText())
				self.dev = multimeter.k2100(host=host)
				self.dev.identify()
				status = "connected: %s" % self.dev.identifier
				self.txt_identity.setText(status)
				self.dev.display_text("CONNECTED TO PC")
			except OSError as e:
				print("ERROR: if you see 'Permission denied' below, you should probably update /etc/udev/rules.d/50-usbtmc.rules..")
				self.txt_identity.setText("error connecting!")
				raise e
		else:
			status = "disconnected: no device"
			self.txt_identity.setText(status)
	def disconnect(self):
		"""
		Disconnects the device.
		"""
		if self.dev:
			self.reset()
			self.clear()
			self.dev = None
		status = "disconnected"
		self.txt_identity.setText(status)
	
	def clear(self):
		"""
		Clears the device (error & display).
		"""
		self.dev.clear()
		self.dev.display_clear()
	def reset(self, hard_reset=False):
		"""
		Resets the device trigger/delay.
		"""
		if hard_reset:
			self.dev.reset()
			time.sleep(0.5)
		self.dev.set_delay(0)
		self.dev.set_count(0)
		self.dev.clear_trigger()
		self.dev.send_trigger()
	
	
	
	def initTrig(self):
		"""
		Sets up the trigger to begin collecting data. The data will
		remain in the device's memory until it is fetched. See fetchMem()
		for this next step.
		"""
		if not self.dev: return
		delay = self.combo_delay.value()
		self.dev.set_delay(delay)
		num = int(self.combo_numBuffer.value())
		self.dev.set_count(num)
		self.dev.display_text("READING ACTIVE")
		self.dev.send_trigger()
		self.dev.display_text("READING FINISHED")
	def fetchMem(self):
		"""
		Retrieves the data from the internal memory, which was collected
		using the initTrig() function.
		"""
		if not self.dev: return
		data = self.dev.fetch()
		if data:
			data = data.split(",")
			self.updateTable(data)
	
	
	def readValues(self):
		"""
		Makes a number of instantaneous readings from the device.
		
		Note that this establishes a persistent communication thread
		until the readings are finished, and will therefore timeout
		if the request takes too long (must keep <num> * <delay> < 3 seconds).
		"""
		if not self.dev: return
		delay = self.combo_delay.value()
		num = int(self.combo_numReadings.value())
		if delay*num > 3:
			msg = "You must use the memory buffer, because this"
			msg += "\nfeature does not work for extended measurements"
			msg += "\n(it times out!).."
			QtGui.QMessageBox.warning(self, "Warning!", msg, QtGui.QMessageBox.Ok)
			return
		self.dev.set_delay(delay)
		self.dev.set_count(num)
		data = self.dev.do_readval(num=num)
		data = data.split(",")
		self.updateTable(data)
	
	
	def updateTable(self, data=None):
		"""
		Updates the spreadsheet grid with a set of measurements. The table
		is first cleared, and then populated with columns <num>,<value>.
		"""
		if not data: return
		data_list = []
		self.table_data.clear()
		self.table_data.setRowCount(0)
		self.table_data.setColumnCount(2)
		for d in data:
			try:
				data_list.append(float(d))
			except ValueError as e:
				print("was not able to convert the data to floating-point numbers: %s" % d)
		data_list = list(zip(list(range(len(data_list))), data_list))
		data_list = np.asarray(data_list, dtype=[('index', int),('reading', float)])
		self.table_data.setData(data_list)
	
	
	def runConsole(self):
		"""
		Loads an interactive console that is connected to the namespace
		of the GUI. All instance variables of the main window (i.e. self.XXX)
		can be referenced/checked/modified, named as gui.XXX.
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
		
	
	def test(self):
		"""
		runs temporary tests (for debugging only).
		
		At the moment, this does nothing.
		"""
		pass
	
	
	def exit(self, confirm=False):
		"""
		Provides the routine that quits the GUI.
		
		For now, simply quits the running instance of Qt.
		
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
		# finally quit
		QtCore.QCoreApplication.instance().quit() 


if __name__ == '__main__':
	# monkey-patch the system exception hook so that it doesn't totally crash
	sys._excepthook = sys.excepthook
	def exception_hook(exctype, value, traceback):
		sys._excepthook(exctype, value, traceback)
	sys.excepthook = exception_hook
	
	# define GUI elements
	qApp = QtGui.QApplication(sys.argv)
	mainGUI = dmmGUI()
	
	# start GUI
	mainGUI.show()
	qApp.exec_()
	qApp.deleteLater()
	sys.exit()
