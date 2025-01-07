#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module loads an interface that provides some nice widgets for
testing programs.

Depends on PyQt4 & pyqtgraph for the interface. The rest, as you please.
"""
# standard library
import sys
import os
import time
from functools import partial
from timeit import default_timer as timer
# third-party
import numpy as np
import scipy
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
from pyqtgraph.Qt import QtGui, QtCore, QtSvg
from pyqtgraph.Qt import uic
loadUiType = uic.loadUiType
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from Instruments import redpitaya_socket as rp
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import Widgets
import Dialogs

if sys.version_info[0] == 3:
	from importlib import reload
	unicode = str
	xrange = range


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
			#print(msg)
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
ui_filename = 'redpitaya_monitor.ui'
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

Ui_MainWindow, QMainWindow = loadUiType(os.path.join(ui_path, ui_filename))
class rpGUI(QMainWindow, Ui_MainWindow):
	"""
	blah
	"""
	def __init__(self, debugging=False):
		"""
		blah
		"""
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.debugging = debugging
		
		### button functionality
		self.btn_ledOn.clicked.connect(partial(self.ledtoggle, state="on"))
		self.btn_ledOff.clicked.connect(partial(self.ledtoggle, state="off"))
		self.btn_blinkStart.clicked.connect(self.ledBlinkStart)
		self.btn_blinkStop.clicked.connect(self.ledBlinkStop)
		self.btn_monAnInStart.clicked.connect(self.monitorAnInStart)
		self.btn_monAnInStop.clicked.connect(self.monitorAnInStop)
		self.btn_fastoutput1Start.clicked.connect(partial(self.fastOutputStart, ch=1))
		self.btn_fastoutput2Start.clicked.connect(partial(self.fastOutputStart, ch=2))
		self.btn_fastoutputReset.clicked.connect(self.fastoutputReset)
		self.btn_mon1start.clicked.connect(self.monitorCh1Start)
		self.btn_mon1stop.clicked.connect(self.monitorCh1Stop)
		self.btn_mon1clear.clicked.connect(self.monitorCh1Clear)
		self.btn_connect.clicked.connect(self.connect)
		self.btn_reset.clicked.connect(self.reset)
		self.btn_disconnect.clicked.connect(self.disconnect)
		#
		self.btn_test.clicked.connect(self.test)
		self.btn_console.clicked.connect(self.showConsole)
		self.btn_quit.clicked.connect(self.quit)
		
		### keyboard shortcuts
		self.keyShortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, partial(self.quit, confirm=False))
		
		### gui elements/containers
		self.rp = None
		try:
			raise NotImplementedError
			ip = ""
			self.txt_rpIP.setText(ip)
		except:
			self.txt_rpIP.setText("130.183.139.221")
			#self.txt_rpIP.setText("172.16.27.221")
		decs = rp.RedPitaya.decimations
		for d in decs:
			self.cb_decimation.addItem("%s" % d)
		self.txt_offset.opts['constStep'] = 0.1
		self.txt_delay.opts['constStep'] = 10
		self.txt_length.opts['constStep'] = 100
		self.txt_threshold.opts['constStep'] = 0.1
		
		self.txt_period.setValue(0.01)
		self.txt_frequency.setValue(20)
		self.txt_delay.setValue(200)
		self.txt_length.setValue(16e3)
		self.cb_decimation.setCurrentIndex(decs.index(64))
		
		### initializations
		self.init_misc()
		self.init_plot()
		self.init_text()
		self.init_table()
		
		self.move(270, 400)
	
	
	def init_misc(self):
		"""
		initializes the misc tab
		"""
		if self.debugging:
			print("initializing the misc tab")
		pass
	
	
	def init_plot(self):
		"""
		initializes the plot tab
		"""
		if self.debugging:
			print("initializing the plot tab")
		#self.plotWidget.setLabel('left', "arb")
		#self.plotWidget.setLabel('bottom', "x-axis", units='arb')
		## plots
		#self.test_plot1 = self.plotWidget.plot(
		#	name='exp', clipToView=True,
		#	autoDownsample=True, downsampleMethod='subsample')
	
	
	def init_text(self):
		"""
		initializes the text tab
		"""
		if self.debugging:
			print("initializing the text tab")
		font = QtGui.QFont()
		font.setFamily('Mono')
		self.textEdit.setFont(font)
	
	
	def init_table(self):
		"""
		initializes the table tab
		"""
		if self.debugging:
			print("initializing the table tab")
		pass
	
	
	def updateWaveforms(self):
		def updatecombobox(waveforms):
			self.cb_waveform.clear()
			for w in waveforms:
				self.cb_waveform.addItem(w)
		if self.method == "scpi":
			waveforms = rp.RedPitaya.waveforms
			updatecombobox(waveforms)
		else:
			waveforms = ['sin', 'cos', 'ramp', 'halframp', 'square', 'dc', 'noise']
			updatecombobox(waveforms)
		self.cb_waveform.setCurrentIndex(waveforms.index("square"))
	
	
	def ledtoggle(self, state=None):
		self.rp.setLED(pin="all", state=state)
		self.led_led.toggle(state)
	
	
	def ledBlinkStart(self):
		if "blinker" in dir(self) and self.blinker is not None:
			self.ledBlinkStop()
			self.ledBlinkStart()
			return
		def blinker(parent=None, period=1):
			parent.rp.setLED(pin=0, state="on")
			parent.led_blinker.toggle("on")
			time.sleep(period/2.0)
			parent.rp.setLED(pin=0, state="off")
			parent.led_blinker.toggle("off")
		period = self.txt_period.value()
		self.blinker = genericThreadContinuous(
			function=blinker, waittime=period*500,
			parent=self, period=period)
		self.blinker.start()
	def ledBlinkStop(self):
		if not "blinker" in dir(self) or self.blinker is None:
			return
		else:
			self.blinker.stop()
			del self.blinker
	
	
	def monitorAnInStart(self):
		if "monAnInThread" in dir(self) and self.monAnInThread is not None:
			self.monitorAnInStop()
			self.monitorCh1Start()
			return
		# collect settings
		period = self.txt_period.value()
		# define a loop
		def runMonLoop(parent=None):
			cursor = parent.textEdit.textCursor()
			cursor.movePosition(QtGui.QTextCursor.End, QtGui.QTextCursor.MoveAnchor)
			parent.textEdit.setTextCursor(cursor)
			for i in range(4):
				value = parent.rp.readAnalogInput(ch=i)
				msg = "Measured voltage on AI[%s] = %f V\n" % (i, value)
				parent.textEdit.insertPlainText(msg)
		# define the thread & start it
		self.monAnInThread = genericThreadContinuous(
			function=runMonLoop, waittime=period*1000, parent=self)
		self.monAnInThread.start()
	def monitorAnInStop(self):
		if "monAnInThread" in dir(self) and self.monAnInThread is not None:
			self.monAnInThread.stop()
			del self.monAnInThread
	
	
	def fastOutputStart(self, ch=None):
		waveform = str(self.cb_waveform.currentText())
		frequency = self.txt_frequency.value()
		amplitude = self.txt_amplitude.value()
		offset = self.txt_offset.value()
		if self.method == "scpi":
			self.rp.setFastOutput(
				ch=ch,
				waveform=waveform,
				frequency=frequency,
				amplitude=amplitude,
				offset=offset)
		else:
			self.r.asg0.output_direct = "out%s" % ch
			self.r.asg1.output_direct = "off"
			self.r.asg0.setup(
				waveform=waveform,
				frequency=frequency,
				amplitude=amplitude,
				offset=offset,
				trigger_source='immediately')
			
	def fastoutputReset(self):
		if self.method == "scpi":
			self.rp.resetFastOutput()
		else:
			try:
				self.r.asg0.output_direct = "off"
			except:
				pass
	
	
	def monitorCh1Start(self, event=None):
		if "mon1thread" in dir(self) and not self.mon1thread.stopped:
			self.monitorCh1Clear()
			self.monitorCh1Start()
			return
		# collect settings
		period = self.txt_period.value()
		if not "ch1plot" in dir(self):
			# initialize plot
			self.plotWidget.setLabel('left', "Signal", units='V')
			self.plotWidget.setLabel('bottom', "Time", units='s')
			self.ch1plot = Widgets.SpectralPlot(
				name='trigger_sample', clipToView=True,
				autoDownsample=True, downsampleMethod='subsample')
			self.plotWidget.addItem(self.ch1plot)
		# define a loop
		decimation = int(self.cb_decimation.currentText())
		mv = int(self.txt_threshold.value()*1e3)
		delay = self.txt_delay.value()
		
		if self.method == "scpi":
			# everything is done on-the-fly during the loop
			pass
		else:
			#self.r.scope.input1 = "in1"
			self.r.scope.ch1_active = True
			self.r.scope.ch2_active = False
			self.r.scope.decimation = decimation
			self.r.scope.threshold = mv/1e3
			self.r.scope.hysteresis = 0.01
			self.r.scope.rolling_mode = False
			self.r.scope.trigger_source = 'ch1_positive_edge'
			self.r.scope.trigger_delay = 0
			self.r.scope.setup()
		
		self.lastTime = timer()
		def runMonLoop():
			print("beginning a loop..")
			timer_acqstart = timer()
			# (re-)activate the trigger
			if self.method == "scpi":
				decimation = int(self.cb_decimation.currentText())
				self.rp.set_acq_decimation(decimation)
				self.rp.set_acq_trig_level(mv)
				self.rp.set_acq_trig_source(source="ch1", edge="pos")
				self.rp.set_acq_state("start")
				while (not self.rp.get_acq_trig_status() == "TD"):
					if self.mon1thread.stopped:
						break
					print("waiting")
					time.sleep(0.01)
				print("acquiring data")
				
				try:
					length = int(self.txt_length.value())
					sleeptime = length / 125e6 * decimation + 0.02 + 1/self.txt_frequency.value()
					time.sleep(sleeptime)
					print(sleeptime)
					
					### gets first x from buffer
					tpos = self.rp.get_acq_tpos()
					offset = int(self.txt_delay.value())
					tpos = tpos - offset
					if int(tpos-offset+length) > self.rp.buffsize:
						tpos -= self.rp.buffsize
					buff = self.rp.get_acq_data(start=tpos, length=length)
					x = (np.arange(len(buff))-offset) / 125e6 * decimation
				
				except TypeError: # when length isn't an integer
					### gets the full buffer
					tpos = self.rp.get_acq_tpos()
					buff = self.rp.get_acq_data()
					x = (np.arange(len(buff))-tpos) / 125e6 * decimation
				
				except:
					print("tripped an error: %s" % sys.exc_info()[1])
					return
				
				self.ch1plot.setData(x=x, y=buff)
				#self.plotWidget.viewport().update()
			
			else:
				### uses pyrpl
				print("starting acquisition")
				self.r.scope._start_acquisition()
				# do some things that might take a few milliseconds
				decimation = int(self.cb_decimation.currentText())
				delaylength = int(self.txt_delay.value())
				try:
					bufferlength = int(self.txt_length.value())
				except ValueError:
					bufferlength = 16384 - delaylength
				sampletime = 1 / 125e6 * decimation
				delay = delaylength * sampletime
				duration = bufferlength * sampletime
				x = -delay + np.linspace(0, duration, bufferlength, endpoint=False)
				# finished setup
				timer_pretrigger = timer()
				while not self.r.scope._write_pointer_trigger:
					time.sleep(0.001)
				tpos = self.r.scope._write_pointer_trigger
				timer_triggered = timer()
				remtime = duration - (timer()-timer_triggered)
				if remtime > 0:
					print("remtime is %s" % remtime)
					time.sleep(remtime)
				# get ch1 data and pull out the desired data
				y = np.array(np.roll(self.r.scope._rawdata_ch1,
				                     -(tpos-delaylength)
				             )[:bufferlength],
				             dtype=np.float)
				y /= 2**13 # normalize voltage..
				self.ch1plot.setData(x=x, y=y)
				#self.plotWidget.viewport().update()
				### returns "rolling" data (i.e. most recently updated)
				#curves = self.r.scope._get_rolling_curve()
				#self.ch1plot.setData(curves[0], curves[1][0])
				waittime = timer_triggered - timer_pretrigger + remtime
				print("time spent waiting (pretrigger-triggered + remtime): %s" % waittime)
			
			timer_acqstop = timer()
			if self.debugging:
				dt = timer() - self.lastTime
				fps = 1/float(dt)
				print("step took approx. %.3e s (%.1f s^-1)" % (dt,fps))
				self.lastTime = timer()
		# define the thread & start it
		self.mon1thread = genericThreadContinuous(function=runMonLoop, waittime=period*1000)
		self.mon1thread.start()
	def monitorCh1Stop(self):
		if "mon1thread" in dir(self):
			self.mon1thread.stopped = 1
	def monitorCh1Clear(self):
		self.monitorCh1Stop()
		del self.mon1thread
		self.ch1plot.clear()
		self.plotWidget.removeItem(self.ch1plot)
		del self.ch1plot
	
	
	def connect(self, doreset=False, debugging=False):
		kbmods = QtGui.QApplication.keyboardModifiers()
		if not debugging and kbmods == QtCore.Qt.ShiftModifier:
			debugging = True
		
		if self.rp is not None:
			reload(rp)
			self.disconnect()
			self.connect()
			return
		
		try:
			ip = str(self.txt_rpIP.text())
			self.rp = rp.RedPitaya(ip, debugging=debugging)
			self.method = "scpi"
			if kbmods == QtCore.Qt.ShiftModifier:
				if self.debugging:
					print("trying to connect via pyrpl")
				import pyrpl
				self.r = pyrpl.RedPitaya(hostname=ip)
				self.method = "pyrpl"
			self.rp.setLEDbarGraph(percent=50)
			self.pb_connection.setValue(50)
			if doreset:
				self.reset()
			self.rp.setLEDbarGraph(percent=100)
			self.pb_connection.setValue(100)
			if self.method == "pyrpl":
				for i in range(8):
					state = i % 2
					self.rp.setLED(pin=i, state=state)
			self.updateWaveforms()
		except:
			e = None
			raise
	def reset(self):
		"""
		resets various things on the hardware
		"""
		if not self.rp:
			return
		# clear all the LEDs
		self.rp.setLED(pin="all", state="off")
		self.rp.setAnalogOutput(ch="all", voltage=0.0)
		self.rp.resetFastOutput()
		self.rp.reset_acq()
	def disconnect(self):
		if self.rp is None:
			return
		try:
			self.rp.setLEDbarGraph(percent=0)
		except:
			pass
		self.rp.close()
		self.rp = None
		if self.method == "pyrpl":
			#self.r.end_all()
			del self.r
		self.pb_connection.setValue(0)
	
	
	def test(self):
		"""
		runs temporary tests (for debugging only)
		"""
		pass
	
	def showConsole(self):
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
	
	def quit(self, confirm=False):
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
		self.reset()
		self.disconnect()
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
	mainGUI = rpGUI(debugging=True)
	
	# start GUI
	mainGUI.show()
	qApp.exec_()
	qApp.deleteLater()
	sys.exit()
