#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module provides several classes related to simple widgets.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
import logging, logging.handlers
logformat = '%(asctime)s - %(name)s:%(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=logformat)
log = logging.getLogger("Widgets-%s" % os.getpid())
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
import re
import time
import datetime
import distutils.version
from functools import partial
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
from pyqtgraph import getConfigOption
loadUiType = uic.loadUiType
if distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5.6":
	try:
		from PyQt5 import QtWebEngineWidgets     # must be imported now, if ever
	except ImportError:
		pass
	try:
		from OpenGL import GL               # to fix an issue with NVIDIA drivers
	except:
		pass
import numpy as np
# local
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
pass

if ((distutils.version.LooseVersion(pg.Qt.QtVersion) > "5") or
	sys.version_info[0] == 3):
	QtCore.QString = str



# thread subclasses (to be used with any PyQt-based widgets/dialogs/windows/etc)
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
	def __init__(self, function, parent=None, *args, **kwargs):
		"""
		Initializes the thread.

		:param function: the function to call from the thread
		:param args: arguments to pass to the function
		:param kwargs: keywords to pass to the function
		:type function: callable method
		:type args: tuple
		:type kwargs: dict
		"""
		QtCore.QThread.__init__(self, parent=parent)
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
ui_filename = "QtFitMainWindow.ui"
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

### general custom widgets based on native PyQt objects
class DoubleSlider(QtGui.QSlider):
	"""
	Provides a special type of slider that converts the integer	location
	to an interpreted-as-a-double slider.

	Also, this has two new features: 1) an internal variable is used to
	keep track of change activity, where bool(self.isChanging) reflects
	this activity, but is reset after a defined delay (see self.setRange);
	and, 2) a new signal (self.valueChangedSlow) can also be used to keep
	track of a rate-limited signal much like self.valueChanged except with
	a rate (s^-1) defined by the user (also see self.setRange).
	"""
	valueChangedSlow = QtCore.Signal(float)
	valueChangedDelayed = QtCore.Signal(float)
	def __init__(self, parent):
		"""
		Initializes the DoubleSlider object.

		:param parent: the parent window/widget containing the slider
		:type parent: QWidget
		"""
		QtGui.QSlider.__init__(self, parent)
		self.setRange()
	def setRange(
		self,
		minInt=0, maxInt=10000,
		minFloat=0.0, maxFloat=100.0,
		sigDelay=0.5, sigRate=10):
		"""
		Sets the lower/upper limits (both the standard integer type, as
		well as the floating-point type) of the slider, and re-initializes
		its states and slots.

		Note that the wisest use of the DoubleSlider is to set the int/
		float values so that each is off by the other by a specific factor
		of 10, which makes it easy to define the desired number of decimal
		digits of the float.

		:param minInt: (optional) minimum integer in range (default=0)
		:param maxInt: (optional) maximum integer in range (default=10000)
		:param minFloat: (optional) maximum float in range (default=0.0)
		:param maxFloat: (optional) maximum float in range (default=100.0)
		:param sigDelay: (optional) delay before the 'settled' signal is emitted, in unit [s] (default=0.5)
		:param sigRate: (optional) rate for emitting the slower signal, in unit [s^-1] (default=10)
		:type minInt: int
		:type maxInt: int
		:type minFloat: float
		:type maxFloat: float
		:type sigDelay: float
		:type sigRate: int
		"""
		# define limits (ints and floats)
		self.setMinimum(minInt)
		self.setMaximum(maxInt)
		self.minFloat = minFloat
		self.maxFloat = maxFloat
		# initialize delay-related things
		self.sigDelay = sigDelay
		self.sigRate = sigRate
		self.isChanging = False
		# define normal, 'instantaneous' connection
		self.instantChangeProxy = pg.SignalProxy(
			self.valueChanged,
			slot=self.instantChange)
		# define connection that always lags behind
		self.delayedChangeProxy = pg.SignalProxy(
			self.valueChanged,
			slot=self.delayedChange,
			delay=self.sigDelay)
		# define a rate-limited signal to connect to valueChangedSlow
		self.slowerChangeProxy = pg.SignalProxy(
			self.valueChanged,
			slot=self.slowChange,
			rateLimit=self.sigRate)
	def floatRange(self):
		"""
		Returns the total range of the min/max float values.

		:returns: the total range of the min/max float values
		:rtype: float
		"""
		return self.maxFloat-self.minFloat
	def value(self):
		"""
		Returns the current value of the slider.

		:returns: the current value
		:rtype: float
		"""
		value = float(super(self.__class__, self).value())
		value *= self.floatRange()/self.maximum()
		value += self.minFloat
		return value
	def setValue(self, value, delayedSignal=True):
		"""
		Used to set a new value to the slider.

		:param value: the new value
		:param delayedSignal: (optional) whether to also keep track of a delayed state
		:type value: float
		:type delayedSignal: bool
		"""
		value -= self.minFloat
		value *= self.maximum()/self.floatRange()
		value = int(value)
		super(self.__class__, self).setValue(value)
	def instantChange(self, sig):
		"""
		Method that is called immediately whenever the slider's value is
		changed.

		:param sig: signal from the SignalProxy
		:type sig: pyqtSignal
		"""
		self.isChanging = True
		self.lastValue = self.value()
	def delayedChange(self, sig):
		"""
		Method that is called immediately whenever the slider's value is
		changed, but at a specific latency behind the original activity.
		Then it checks if the current signal is the same as the original,
		and if so, it updates its self.isChanging status.

		:param sig: signal from the SignalProxy
		:type sig: pyqtSignal
		"""
		if self.value() == self.lastValue:
			self.isChanging = False
			self.valueChangedDelayed.emit(self.value())
	def slowChange(self):
		"""
		Method that is called immediately whenever the slider's value is
		changed, but at a user-defined rate. Then it emits the rate-limited
		signal.
		"""
		self.valueChangedSlow.emit(self.value())



class LEDWidget(QtGui.QWidget):
	"""
	Provides a class that draws a circle, that can be colored red or green,
	much like an indicator LED.
	"""
	knownColors = [
		"white", "black", "red", "darkRed", "green", "darkGreen", "blue",
		"darkBlue", "cyan", "darkCyan", "magenta", "darkMagenta", "yellow",
		"darkYellow", "gray", "darkGray", "lightGray", "color0", "color1"]
	def __init__(self, parent, radius=5, radx=None, rady=None):
		"""
		Initializes the led object.

		:param parent: the parent window/widget containing the widget
		:type parent: QWidget
		"""
		super(self.__class__, self).__init__(parent)
		# define size
		if radx is not None:
			self.radx = radx
		else:
			self.radx = max(radius, self.minimumWidth()/2.0)
		if rady is not None:
			self.rady = rady
		else:
			self.rady = max(radius, self.minimumHeight()/2.0)
		# set other drawing properties
		palette = QtGui.QPalette(self.palette())
		palette.setColor(palette.Background, QtCore.Qt.transparent)
		self.setPalette(palette)
		# initialize state & color properties
		self.isEnabled = False
		self.color = None
	def paintEvent(self, event=None):
		"""
		Draws the schematic picture of the widget.

		Note that this is invoked whenever the parent object is resized
		or refreshed in some way, but also when one calls forcefully
		self.update() (regardless of whether the parent is refreshed).

		:param event: the paint event
		:type event: PaintEvent
		"""
		painter = QtGui.QPainter()
		painter.begin(self)
		painter.setRenderHint(QtGui.QPainter.Antialiasing)
		if self.color is None:
			if self.isEnabled:
				painter.setBrush(QtCore.Qt.green)
			else:
				painter.setBrush(QtCore.Qt.red)
		elif self.color in (self.knownColors):
			painter.setBrush(getattr(QtCore.Qt, self.color))
		else:
			msg = "error: unknown color (%s)! options are limited to: %s" % (
				self.color, self.knownColors)
			raise NotImplementedError(msg)
		painter.drawEllipse(QtCore.QPoint(self.radx,self.rady), self.radx-1, self.rady-1)
		painter.end()
	def toggle(self, state=None):
		"""
		Toggles the color of the widget (default: red <-> green). If
		no state/color is specified, it simply flips the color. If
		'on' or 'off' is specified, it forces the color. If a color
		is specified and matches PyQt's predefined colors (see below),
		it uses that color.

		Predfined colors:
		"white", "black", "red", "darkRed", "green", "darkGreen",
		"blue", "darkBlue", "cyan", "darkCyan", "magenta", "darkMagenta",
		"yellow", "darkYellow", "gray", "darkGray", "lightGray",
		"color0", "color1"

		:param state: (optional) on or off or a color
		:type state: str
		"""
		if state is None:
			self.color = None
			if self.isEnabled:
				self.isEnabled = False
			else:
				self.isEnabled = True
		elif isinstance(state, bool):
			self.isEnabled = state
		elif isinstance(state, str) and (state.lower() in ("on", "off")):
			self.color = None
			if state == "on":
				self.isEnabled = True
			if state == "off":
				self.isEnabled = False
		elif state in self.knownColors:
			self.color = state
			self.isEnabled = True
		else:
			msg = "error: unknown state (%s)! options are limited to: %s" % (
				state, [True, False, "on", "off"]+self.knownColors)
			raise NotImplementedError(msg)
		self.update()



class ScrollableText(QtGui.QLineEdit):
	"""
	Provides a subclass of the QLineEdit field, so that one can use it
	with numbers, and scroll (via up/down or mouse-wheel) to change it
	by some constant value, or relative percentage.

	For catching/handling signals related to its contents, one should
	simply use the textChanged/textEdited signals.. it's possible to
	create the new signals valueChanged/valueEdited, but they would
	either only be added to the new Value-related methods or become
	piggy-backed onto the old textChanged/textEdited signals, and these
	both introduce their own undesirable issues.
	"""
	def __init__(self, parent, **opts):
		"""
		Initializes the object.

		:param parent: the parent window/widget containing the widget
		:type parent: QWidget
		"""
		super(self.__class__, self).__init__(parent)
		self.opts = dict(
			constStep = None,
			relStep = 10,
			formatString = "%.2e",
			min = None,
			max = None,
		)
		self.opts.update(opts)
		if "value" in opts:
			self.setValue(opts["value"])
			opts.pop("value")

		# feature: editingFinishedBool is a boolean state for:
		#     False - while text is manually being edited
		#     True - when item loses focused (and user is therefore finished editing)
		self.editingFinishedBool = True
		self.textEdited.connect(partial(self.updatedEditingState, finished=False))
		self.editingFinished.connect(partial(self.updatedEditingState, finished=True))

	def keyPressEvent(self, event):
		"""
		Hijacks all keypresses, and checks if they are an up or down
		arrow. For some reason, the standard way of assigning a QShortcut
		doesn't work in this case (maybe the wrong parent widget?).
		"""
		if event.key() == QtCore.Qt.Key_Up:
			self.increaseValue()
		elif event.key() == QtCore.Qt.Key_Down:
			self.decreaseValue()
		else:
			super(self.__class__, self).keyPressEvent(event)

	def updatedEditingState(self, finished=None):
		"""
		Updates the state of the editingFinishedBool property.

		I don't remember when this is actually used, instead of using the native
		signal editingFinished.
		"""
		if finished is None:
			return
		else:
			self.editingFinishedBool = finished

	def setStepSize(self, const=None, rel=None):
		"""
		Updates the step size for the scrollable value.

		:param const: a constant value for the step size
		:type const: float
		:param rel: a step size in terms of relative % of the current value
		:type rel: float
		"""
		if const is not None:
			self.opts["constStep"] = const
		elif rel is not None:
			self.opts["constStep"] = None
			self.opts["relStep"] = rel

	def increaseValue(self):
		"""
		Increases the current value. The increase depends on the option
		that has been set, defaulting first to the constant step.
		"""
		if not (self.opts['constStep'] or self.opts['relStep']):
			return
		try:
			value = float(str(self.text()))
			if self.opts['constStep']:
				value += self.opts['constStep']
			else:
				value *= (1 + self.opts['relStep']*0.01)
			if (self.opts['max'] is not None) and (value > self.opts['max']):
				value = self.opts['max']
			self.setText(self.opts['formatString'] % value)
			self.textEdited.emit(str(self.text()))
		except ValueError:
			pass
		except TypeError:
			pass

	def decreaseValue(self):
		"""
		Decreases the current value. The decrease depends on the option
		that has been set, defaulting first to the constant step.
		"""
		if not (self.opts['constStep'] or self.opts['relStep']):
			return
		try:
			value = float(str(self.text()))
			if self.opts['constStep']:
				value -= self.opts['constStep']
			else:
				value *= (1 - self.opts['relStep']*0.01)
			if (self.opts['min'] is not None) and (value < self.opts['min']):
				value = self.opts['min']
			self.setText(self.opts['formatString'] % value)
			self.textEdited.emit(str(self.text()))
		except ValueError:
			pass
		except TypeError:
			pass

	def wheelEvent(self,event):
		"""
		Invoked whenever the element catches a mouse-wheel event. In
		this case, it just calls increaseValue() or decreaseValue(),
		depending on the direction of the wheel movement.
		"""
		# bug fix: interpret the scroll direction according to the Qt version
		if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
			delta = event.angleDelta()
			delta = int(delta.y())
		else:
			delta = event.delta()
		# carry on...
		if delta > 0:
			self.increaseValue()
		else:
			self.decreaseValue()

	def value(self):
		"""
		Returns the current value as an interpreted floating-point value.
		This provides compatibility for a pain-free replacement of a
		spinbox or doublespinbox.
		"""
		try:
			return float(str(self.text()))
		except ValueError:
			return None
		except TypeError:
			return None

	def setValue(self, value):
		"""
		Allows the setting of a value via a number. This provides
		additional compatibility with a spinbox or doublespinbox.

		:param value: the new value to be set
		:type value: str or float
		"""
		if (self.opts['min'] is not None) and (value < self.opts['min']):
			value = self.opts['min']
		elif (self.opts['max'] is not None) and (value > self.opts['max']):
			value = self.opts['max']
		try:
			self.setText(self.opts['formatString'] % float(value))
		except ValueError:
			return None
		except TypeError:
			return None




class InteractiveListWidget(QtGui.QListWidget):
	"""
	Provides a subclass of the QListWidget, so that one can actually
	catch the mouse/keyboard events, and not just information about the
	clicked item or pressed key.
	"""
	def __init__(self, *args):
		"""
		Initializes the object.

		:param parent: the parent window/widget containing the widget
		:type parent: QWidget
		"""
		super(self.__class__, self).__init__(*args)

	def mousePressEvent(self, event):
		"""
		Hijacks all mouse clicks, to first save the most recent event as
		an instance variable for future reference, then passes it on to
		the parent class as normal.
		"""
		self._mouseEvent = event
		super(self.__class__, self).mousePressEvent(event)




class DetachableTabWidget(QtGui.QTabWidget):
	"""
	Provides a subclass of the QTabWidget, so that the tabs can be dragged out
	of their original location, into a new window.

	Original credit goes to "Hitesh Patel" via https://stackoverflow.com/a/48902281,
	but has been edited by JCL.. e.g.,
	- the internal documentation has been refactored,
	- changes were made for cross-compatibility across py2/py3 and PyQt4/PyQt5
	- icons are handled a bit better, in case they were simply single bitmaps
	- the tabs can now be correctly reordered within their current parent
	"""
	def __init__(self, *args):
		"""
		Initializes the object.

		:param parent: the parent window/widget containing the widget
		:type parent: QWidget
		"""
		super(self.__class__, self).__init__(*args)

		self.tabBar = self.TabBar(self)
		self.tabBar.onDetachTabSignal.connect(self.detachTab)
		self.tabBar.onMoveTabSignal.connect(self.moveTab)

		self.setTabBar(self.tabBar)


	def setMovable(self, movable):
		"""
		Overrides the default movable functionality of QTabWidget, because it
		must remain disabled so as to not conflict with the added features.
		"""
		pass

	@QtCore.pyqtSlot(int, int)
	def moveTab(self, fromIndex, toIndex):
		"""
		Move a tab from one position (index) to another

		:param fromIndex: the original index location of the tab
		:param toIndex: the new index location of the tab
		:type fromIndex: int
		:type toIndex: int
		"""
		widget = self.widget(fromIndex)
		icon = self.tabIcon(fromIndex)
		text = self.tabText(fromIndex)
		ttip = self.tabToolTip(fromIndex)

		self.removeTab(fromIndex)
		self.insertTab(toIndex, widget, icon, text)
		self.setCurrentIndex(toIndex)
		self.setTabToolTip(toIndex, ttip)


	@QtCore.pyqtSlot(int, QtCore.QPoint)
	def detachTab(self, index, point):
		"""
		Detach the tab by removing it's contents and placing them in
		a DetachedTab dialog

		:param index: the index location of the tab to be detached
		:param point: the screen position for creating the new DetachedTab dialog
		:type index: int
		:type point: QtCore.QPoint
		"""

		# Get the tab content
		name = self.tabText(index)
		icon = self.tabIcon(index)
		if icon.isNull():
			icon = self.window().windowIcon()
		contentWidget = self.widget(index)
		contentWidget.ttip = self.tabToolTip(index)
		contentWidgetRect = contentWidget.frameGeometry()

		# Create a new detached tab window
		detachedTab = self.DetachedTab(contentWidget, self.parentWidget())
		detachedTab.setWindowModality(QtCore.Qt.NonModal)
		detachedTab.setWindowTitle(name.replace("&", ""))
		detachedTab.setWindowIcon(icon)
		detachedTab.setObjectName(name)
		detachedTab.setGeometry(contentWidgetRect)
		detachedTab.onCloseSignal.connect(self.attachTab)
		detachedTab.move(point)
		detachedTab.show()


	@QtCore.pyqtSlot(QtGui.QWidget, QtCore.QString, QtGui.QIcon)
	def attachTab(self, contentWidget, name, icon):
		"""
		Re-attach the tab by removing the content from the DetachedTab dialog,
		closing it, and placing the content back into the DetachableTabWidget

		:param contentWidget: the content widget from the DetachedTab dialog
		:param name: the name of the detached tab
		:param icon: the window icon for the detached tab
		:type contentWidget: QtGui.QWidget
		:type name: QtCore.QString
		:type icon: QtGui.QIcon
		"""

		# Make the content widget a child of this widget
		contentWidget.setParent(self)

		# Create an image from the given icon
		if (not icon.isNull()) and len(icon.availableSizes()):
			tabIconPixmap = icon.pixmap(icon.availableSizes()[0])
			tabIconImage = tabIconPixmap.toImage()
		else:
			tabIconImage = None

		# Create an image of the main window icon
		if (not icon.isNull()) and len(icon.availableSizes()):
			windowIconPixmap = self.window().windowIcon().pixmap(icon.availableSizes()[0])
			windowIconImage = windowIconPixmap.toImage()
		else:
			windowIconImage = None

		# Determine if the given image and the main window icon are the same.
		# If they are, then do not add the icon to the tab
		if tabIconImage == windowIconImage:
			index = self.addTab(contentWidget, name)
		else:
			index = self.addTab(contentWidget, icon, name)

		# Return the old toolTip (if it existed)
		if "ttip" in vars(contentWidget):
			self.setTabToolTip(index, contentWidget.ttip)

		# Make this tab the current tab
		if index > -1:
			self.setCurrentIndex(index)


	class DetachedTab(QtGui.QDialog):
		"""
		When a tab is detached, the contents are placed into this QDialog.
		The tab can be re-attached by closing the dialog or by double clicking
		on its window frame.
		"""

		onCloseSignal = QtCore.pyqtSignal(QtGui.QWidget, QtCore.QString, QtGui.QIcon)

		def __init__(self, contentWidget, parent=None):
			"""
			:param contentWidget: the detached widget that will live here
			:param parent: the parent widget
			:type contentWidget: QWidget
			:type parent: QWidget
			"""
			QtGui.QDialog.__init__(self, parent)

			layout = QtGui.QVBoxLayout(self)
			self.contentWidget = contentWidget
			layout.addWidget(self.contentWidget)
			self.contentWidget.show()

			self.keyBoardEscape = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.close)


		def event(self, event):
			"""
			Capture a double click event on the dialog's window frame

			:param event: an incoming event
			:type event: QEvent
			:returns: true if the event was recognized
			:rtype: bool
			"""

			# QEvent.NonClientAreaMouseButtonDblClick (on the frame?) will also close
			# note: using an int because the enum is missing from some distros
			if event.type() == 176:
				event.accept()
				self.close()

			return QtGui.QDialog.event(self, event)


		def closeEvent(self, event):
			"""
			If the dialog is closed, emit the onCloseSignal and give the
			content widget back to the DetachableTabWidget

			:param event: a close event
			:type event: QEvent
			"""
			self.onCloseSignal.emit(self.contentWidget, self.objectName(), self.windowIcon())


	class TabBar(QtGui.QTabBar):
		"""
		The TabBar class re-implements some of the functionality of the
		QTabBar widget
		"""

		onDetachTabSignal = QtCore.pyqtSignal(int, QtCore.QPoint)
		onMoveTabSignal = QtCore.pyqtSignal(int, int)

		def __init__(self, parent=None):
			QtGui.QTabBar.__init__(self, parent)

			self.setAcceptDrops(True)
			self.setElideMode(QtCore.Qt.ElideRight)
			self.setSelectionBehaviorOnRemove(QtGui.QTabBar.SelectLeftTab)

			self.dragStartPos = QtCore.QPoint()
			self.dragDroppedPos = QtCore.QPoint()
			self.mouseCursor = QtGui.QCursor()
			self.dragInitiated = False


		def mouseDoubleClickEvent(self, event):
			"""
			Disabled: send the onDetachTabSignal when a tab is double clicked.

			Note: this is disabled until both: 1) it is no longer so sensitive,
			and 2) it no longer activates when a moving single-click is made.

			:param event: a mouse double click event
			:type event: QMouseEvent
			"""
			event.accept()
			#self.onDetachTabSignal.emit(self.tabAt(event.pos()), self.mouseCursor.pos())


		def mousePressEvent(self, event):
			"""
			Set the starting position for a drag event when the mouse button
			is pressed

			:param event: a mouse press event
			:type event: QMouseEvent
			"""
			if event.button() == QtCore.Qt.LeftButton:
				self.dragStartPos = event.pos()

			self.dragDroppedPos.setX(0)
			self.dragDroppedPos.setY(0)

			self.dragInitiated = False

			QtGui.QTabBar.mousePressEvent(self, event)


		def mouseMoveEvent(self, event):
			"""
			Determine if the current movement is a drag. If it is, convert it
			into a QDrag. If the drag ends inside the tab bar, emit an
			onMoveTabSignal. If the drag ends outside the tab bar, emit an
			onDetachTabSignal.

			:param event: a mouse move event
			:type event: QMouseEvent
			"""

			# Determine if the current movement is detected as a drag
			if not self.dragStartPos.isNull() and ((event.pos() - self.dragStartPos).manhattanLength() < QtGui.QApplication.startDragDistance()):
				self.dragInitiated = True

			# If the current movement is a drag initiated by the left button
			if ((event.buttons() & QtCore.Qt.LeftButton) and self.dragInitiated):

				# Stop the move event
				finishMoveEvent = QtGui.QMouseEvent(QtCore.QEvent.MouseMove, event.pos(), QtCore.Qt.NoButton, QtCore.Qt.NoButton, QtCore.Qt.NoModifier)
				QtGui.QTabBar.mouseMoveEvent(self, finishMoveEvent)

				# Convert the move event into a drag
				drag = QtGui.QDrag(self)
				mimeData = QtCore.QMimeData()
				#if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				if sys.version_info[0] == 3:
					mimeData.setData('action', bytes('application/tab-detach', 'utf-8'))
				else:
					mimeData.setData('action', 'application/tab-detach')
				drag.setMimeData(mimeData)

				# Create the appearance of dragging the tab content
				winId = self.parentWidget().currentWidget().winId()
				if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
					app = QtGui.QApplication.instance()
					pixmap = QtGui.QScreen.grabWindow(app.primaryScreen(), winId)
				else:
					pixmap = QtGui.QPixmap.grabWindow(winId)
				targetPixmap = QtGui.QPixmap(pixmap.size())
				targetPixmap.fill(QtCore.Qt.transparent)
				painter = QtGui.QPainter(targetPixmap)
				painter.setOpacity(0.85)
				painter.drawPixmap(0, 0, pixmap)
				painter.end()
				drag.setPixmap(targetPixmap)

				dropAction = drag.exec_(QtCore.Qt.MoveAction | QtCore.Qt.CopyAction)
				if dropAction == QtCore.Qt.IgnoreAction:
					if not self.dragDroppedPos.isNull(): # is still on the tabbar
						event.accept()
						self.onMoveTabSignal.emit(self.tabAt(self.dragStartPos), self.tabAt(self.dragDroppedPos))
					else: # went somewhere else
						event.accept()
						self.onDetachTabSignal.emit(self.tabAt(self.dragStartPos), self.mouseCursor.pos())
			else:
				QtGui.QTabBar.mouseMoveEvent(self, event)


		def dragEnterEvent(self, event):
			"""
			Determine if the drag has entered a tab position from another
			tab position

			:param event: some blah widget
			:type event: QEvent
			"""
			mimeData = event.mimeData()
			formats = mimeData.formats()

			if ((distutils.version.LooseVersion(pg.Qt.QtVersion) > "5" and 'action' in formats) or
				((not distutils.version.LooseVersion(pg.Qt.QtVersion) > "5") and formats.contains('action'))):
				action = mimeData.data('action')
				#if distutils.version.LooseVersion(pg.Qt.QtVersion) > "5":
				if sys.version_info[0] == 3:
					action = bytes(action).decode('utf-8')
				if action == 'application/tab-detach':
					event.acceptProposedAction()

			QtGui.QTabBar.dragMoveEvent(self, event)


		def dropEvent(self, event):
			"""
			Get the position of the end of the drag

			:param event: a drop event
			:type event: QEvent
			"""
			self.dragDroppedPos = event.pos()
			QtGui.QTabBar.dropEvent(self, event)




### pyLabSpec-related widgets.. is Dialogs a better location for this?
Ui_HeaderViewer, QDialog = loadUiType(os.path.join(ui_path, 'HeaderViewer.ui'))
class HeaderViewer(QDialog, Ui_HeaderViewer):
	"""
	Provides a simple dialog to retrieve the title and comments, via the
	contents of a QLineEdit and QTextEdit.
	"""
	def __init__(self, gui, header):
		super(self.__class__, self).__init__()
		self.setupUi(self)
		self.gui = gui
		self.header = header

		self.loadHeaderToTree()
		#self.loadHeaderToText()

		self.keyShortcutQuit = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.exit)

	def loadHeaderToTree(self):
		"""
		Updates the text box with the contents of the header.

		This routine will loop through an iterable header (i.e. like a list)
		and add items to a tree widget, with the keys becoming formatted in
		italics and the values becoming bold.

		The items in the header are expected to be a string that looks like:
		- 'KEY: VALUE'        (collected from any file format containing comments)
		- "#:KEY: 'VALUE'"    (collected within a categorized entry, providing a second-level tree system)
		-
		"""
		def getCatHTML(entry):
			match = re.search(r"^#+ (.*)$", entry)
			if match:
				return "%s" % (match.group(1))
			else:
				return "%s" % entry
		def getItemHTML(entry):
			casacMatch = re.search(r"^#:(.*): '(.*)'$", entry)
			generalMatch = re.search(r"^(.*): (.*)$", entry)
			if casacMatch:
				return "<i>%s</i>: <b>%s</b>" % (casacMatch.group(1), casacMatch.group(2))
			elif generalMatch:
				return "<i>%s</i>: <b>%s</b>" % (generalMatch.group(1), generalMatch.group(2))
			else:
				return "<i>%s</i>" % entry
		def getNiceLabel(parent):
			niceLabel = QtGui.QLabel(parent)
			niceLabel.setWordWrap(True)
			niceLabel.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
			return niceLabel
		tree = self.treeWidget
		for h in self.header:
			categoryMatch = re.search(r"^#+ (.*)$", h)
			itemMatch = re.search(r"^#:(.*): '(.*)'$", h)
			if categoryMatch:
				hsecond = QtGui.QTreeWidgetItem(tree)
				tree.addTopLevelItem(hsecond)
				htmltext = getNiceLabel(tree)
				htmltext.setText(getCatHTML(h))
				tree.setItemWidget(hsecond, 0, htmltext)
			elif itemMatch:
				hitem = QtGui.QTreeWidgetItem(hsecond)
				hsecond.addChild(hitem)
				htmltext = getNiceLabel(tree)
				htmltext.setText(getItemHTML(h))
				tree.setItemWidget(hitem, 0, htmltext)
			else:
				hsecond = QtGui.QTreeWidgetItem(tree)
				tree.addTopLevelItem(hsecond)
				htmltext = getNiceLabel(tree)
				htmltext.setText(getItemHTML(h))
				tree.setItemWidget(hsecond, 0, htmltext)

	def loadHeaderToText(self):
		"""
		Updates the text box with the contents of the header.
		"""
		def getHTML(entry):
			match = re.search(r"^#:(.*): '(.*)'$", entry)
			if match:
				return "<i>%s</i>: %s<br>" % (match.group(1), match.group(2))
			elif re.search(r"^#.*$", entry):
				return "<b>%s</b><br>" % entry
			else:
				return "%s<br>" % entry
		self.textEdit.setReadOnly(True)
		for i in self.header:
			for h in i:
				html = getHTML(h)
				self.textEdit.textCursor().insertHtml(html)

	def exit(self):
		"""
		Just closes the window by hiding it from view.
		"""
		self.hide()
		#QtCore.QCoreApplication.instance().quit()




try:
	if distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5.6":
		try:
			from PyQt5 import QtWebEngineWidgets
			webview = QtWebEngineWidgets.QWebEngineView
			QWebSettings = QtWebEngineWidgets.QWebEngineSettings
		except ImportError:
			log.exception("(Widgets) QtWebEngine isn't installed.. try something like "
				"'sudo apt-get install python[3]-pyqt5.qtwebengine'")
			raise
	elif distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5":
		# it turns out that early versions of PyQt5 still used webkit..
		try:
			from PyQt5 import QtWebKit
			webview = QtWebKit.QWebView
			QWebSettings = QtWebKit.QWebSettings
			QWebInspector = QtWebKit.QWebInspector
		except ImportError:
			log.exception("(Widgets) QtWebKit isn't installed.. try something like "
				"'sudo apt-get install python[3]-pyqt5.qtwebkit'")
			raise
	else:
		try:
			from PyQt4 import QtWebKit
			webview = QtWebKit.QWebView
			QWebSettings = QtWebKit.QWebSettings
			QWebInspector = QtWebKit.QWebInspector
		except ImportError:
			log.exception("(Widgets) QtWebKit isn't installed.. you really should switch "
				"to a newer python and pyqt5 installation..")
			raise
except:
	webview = object
	msg = "WARNING: there was a problem loading the QWebEngineView or QWebView."
	msg += " The error was: %s" % (sys.exc_info(),)
	log.exception("(Widgets) %s" % msg)
class CASDataBrowser(webview):
	"""
	Provides a subclass of the QWebEngineView or QWebView (depending
	on the version of PyQt) and a web interface to the DataManagement
	server for the CAS group.

	Besides a super simple browser widget, it also provides some
	functions that help to interface with the parent interfaces (e.g.
	retrieving a filtered list of spectra during a server-side search).
	"""
	jsFinished = QtCore.pyqtSignal()
	def __init__(self, parent=None, url=None, scale=None, usePlugins=False, *args):
		"""
		Initializes the object.

		:param parent: the parent window/widget containing the widget
		:type parent: QWidget
		"""
		super(self.__class__, self).__init__()

		if webview is object:
			raise NotImplementedError("this CASDataBrowser won't work at all "
				"without a proper webview or webengineview..")

		if distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5.6":
			log.info("(CASDataBrowser) tip: if you see a black screen and are using "
				"PyQt5, try installing PyOpenGL")

		# instance variables
		self.parent = parent
		self.url = url
		if scale is not None:
			try:
				self.setZoomFactor(scale)
			except:
				pass
		self.jsresult = None
		self.txt_jsresult = QtGui.QLineEdit()
		self.connectedSignals = []

		# set up web inspector dev tool
		self.setupInspector()

		# keyboard shortcuts
		self.shortcutZoomReset = QtGui.QShortcut(QtGui.QKeySequence("Ctrl+0"), self, self.zoomReset)
		self.shortcutZoomIn = QtGui.QShortcut(QtGui.QKeySequence.ZoomIn, self, self.zoomIn)
		self.shortcutZoomOut = QtGui.QShortcut(QtGui.QKeySequence.ZoomOut, self, self.zoomOut)
		self.shortcutBack = QtGui.QShortcut(QtGui.QKeySequence.Back, self, self.back)
		self.shortcutForward = QtGui.QShortcut(QtGui.QKeySequence.Forward, self, self.forward)
		self.shortcutRefresh = QtGui.QShortcut(QtGui.QKeySequence.Refresh, self, self.reload)
		self.shortcutEscape = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self, self.quit)

		if usePlugins:
			self.page().settings().setAttribute(QWebSettings.PluginsEnabled, True)

		# if a url was specified, launch it
		if url is not None:
			self.setUrl(QtCore.QUrl(url))

	def zoomIn(self, event=None):
		"""
		Increases the zoom level of the page by 10% until 200%, and then
		by 100% until 500%
		"""
		zoomFactor = float(self.zoomFactor())
		if zoomFactor > 4: # extreme case
			log.info("(CASDataBrowser) will not zoom in beyond 500 percent..")
		elif zoomFactor >= 2.0:
			zoomFactor += 1
		else:
			zoomFactor += 0.1
		self.setZoomFactor(zoomFactor)
	def zoomOut(self, event=None):
		"""
		Decreases the zoom level of the page by 10% if below 200%, or by 100%
		when above.
		"""
		zoomFactor = float(self.zoomFactor())
		if zoomFactor <= 0.25: # extreme case: zoomed in all the way
			log.info("(CASDataBrowser) will not zoom out beyond 25 percent..")
		elif zoomFactor > 2.0:
			zoomFactor -= 1
		else:
			zoomFactor -= 0.1
		self.setZoomFactor(zoomFactor)
	def zoomReset(self, event=None):
		"""
		Resets the zoom level to 100%.
		"""
		self.setZoomFactor(1.0)

	def setJavaScriptResult(self, jsresult):
		"""
		Simply sets the result of executed javascript to an internal
		variable.. is necessary for some versions of Qt, when the
		launched command doesn't directly return the result.
		"""
		self.jsresult = jsresult
		self.jsFinished.emit()
	def runJavaScript(self, js):
		"""
		Provides a wrapper to call runJavaScript or evaluateJavaScript,
		depending on the PyQt version.
		"""
		log.info("(CASDataBrowser) running js: %s" % js)
		if distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5.6":
			result = self.page().runJavaScript(js, self.setJavaScriptResult)
		else:
			result = self.page().mainFrame().evaluateJavaScript(js)
		return result


	def setupInspector(self):
		if distutils.version.LooseVersion(pg.Qt.QtVersion) < "5.6":
			page = self.page()
			page.settings().setAttribute(QWebSettings.DeveloperExtrasEnabled, True)
			self.webInspector = QWebInspector()
			self.webInspector.setPage(page)
			self.webInspector.setVisible(False)
			def toggleInspector():
				self.webInspector.setVisible(not self.webInspector.isVisible())
			self.shortcutF12 = QtGui.QShortcut(QtGui.QKeySequence("F12"), self, toggleInspector)
		elif distutils.version.LooseVersion(pg.Qt.QtVersion) >= "5.11":
			self.webInspector = None
			def toggleInspector():
				if self.webInspector is None:
					self.webInspector = webview()
					self.webInspector.page()
					self.page().setDevToolsPage(self.webInspector.page())
					self.webInspector.shortcutEsc = QtGui.QShortcut(QtGui.QKeySequence("Esc"), self.webInspector, toggleInspector)
					self.webInspector.show()
				else:
					self.webInspector.shortcutEsc.disconnect()
					self.webInspector.close()
					self.webInspector = None
			self.shortcutF12 = QtGui.QShortcut(QtGui.QKeySequence("F12"), self, toggleInspector)
		else:
			def toggleInspector():
				msg = "(CASDataBrowser) dev tools for PyQt v5.6-5.11 are best done this way:"
				msg += " re-launch the application with the ENV variable QTWEBENGINE_REMOTE_DEBUGGING=9090,"
				msg += " and then point a Chromium-based browser @ http://127.0.0.1:9090/"
				log.warning(msg)
			self.shortcutF12 = QtGui.QShortcut(QtGui.QKeySequence("F12"), self, toggleInspector)

	def quit(self, event=None):
		"""
		Closes the browser, but first ensures that old signals are
		disconnected. (fixes a bug for PyQt + new-style signals/slots)
		"""
		for s in self.connectedSignals:
			s.disconnect()
		self.close()




### pyqtgraph derivatives
import DateAxisItem
class TimePlotWidget(pg.PlotWidget):
	"""
	Provides a plot widget in which the bottom axis has been re-defined
	to use the DateAxisItem that is currently waiting to be merged into
	pyqtgraph (https://github.com/pyqtgraph/pyqtgraph/pull/74).
	"""
	def __init__(self, parent):
		timeAxis = DateAxisItem.DateAxisItem(orientation='bottom')
		super(self.__class__, self).__init__(parent, axisItems={'bottom': timeAxis})


class ScaledAxisItem(pg.AxisItem):
	"""
	Provides an AxisItem that properly takes into account a rescaled
	axis so that ticks are better handled.

	Note that this serves as a bug fix.
	"""
	def __init__(self, **opts):
		super(self.__class__, self).__init__(**opts)

	def tickValues(self, minVal, maxVal, size):
		"""
		Return the values and spacing of ticks to draw::

			[
				(spacing, [major ticks]),
				(spacing, [minor ticks]),
				...
			]

		By default, this method calls tickSpacing to determine the correct tick locations.
		This is a good method to override in subclasses.

		Note that this method has been duplicated from pyqtgraph, with only
		one difference: all rescaling has been removed.. it made things worse!
		"""
		minVal, maxVal = sorted((minVal, maxVal))

		#minVal *= self.scale # JCL: removed self.scale
		#maxVal *= self.scale # JCL: removed self.scale

		ticks = []
		tickLevels = self.tickSpacing(minVal, maxVal, size)
		allValues = np.array([])
		for i in range(len(tickLevels)):
			spacing, offset = tickLevels[i]

			## determine starting tick
			start = (np.ceil((minVal-offset) / spacing) * spacing) + offset

			## determine number of ticks
			num = int((maxVal-start) / spacing) + 1
			#values = (np.arange(num) * spacing + start) / self.scale
			values = (np.arange(num) * spacing + start) # JCL: removed self.scale
			## remove any ticks that were present in higher levels
			## we assume here that if the difference between a tick value and a previously seen tick value
			## is less than spacing/100, then they are 'equal' and we can ignore the new tick.
			values = list(filter(lambda x: all(np.abs(allValues-x) > spacing*0.01), values) )
			allValues = np.concatenate([allValues, values])
			#ticks.append((spacing/self.scale, values))
			ticks.append((spacing, values)) # JCL: removed self.scale

		if self.logMode:
			return self.logTickValues(minVal, maxVal, size, ticks)

		return ticks

	def tickSpacing(self, minVal, maxVal, size):
		"""Return values describing the desired spacing and offset of ticks.

		This method is called whenever the axis needs to be redrawn and is a
		good method to override in subclasses that require control over tick locations.

		The return value must be a list of tuples, one for each set of ticks::

			[
				(major tick spacing, offset),
				(minor tick spacing, offset),
				(sub-minor tick spacing, offset),
				...
			]
		"""
		# First check for override tick spacing
		if self._tickSpacing is not None:
			return self._tickSpacing

		dif = abs(maxVal - minVal)
		if dif == 0:
			return []

		## decide optimal minor tick spacing in pixels (this is just aesthetics)
		optimalTickCount = max(2., np.log(size))

		## optimal minor tick spacing
		optimalSpacing = dif / optimalTickCount

		## the largest power-of-10 spacing which is smaller than optimal
		p10unit = 10 ** np.floor(np.log10(optimalSpacing))

		## Determine major/minor tick spacings which flank the optimal spacing.
		intervals = np.array([1., 2., 10., 20., 100.]) * p10unit
		minorIndex = 0
		while intervals[minorIndex+1] <= optimalSpacing:
			minorIndex += 1

		levels = [
			(intervals[minorIndex+2], 0),
			(intervals[minorIndex+1], 0),
			#(intervals[minorIndex], 0)    ## Pretty, but eats up CPU
		]

		if self.style['maxTickLevel'] >= 2:
			## decide whether to include the last level of ticks
			minSpacing = min(size / 20., 30.)
			maxTickCount = size / minSpacing
			if dif / intervals[minorIndex] <= maxTickCount:
				levels.append((intervals[minorIndex], 0))

		# 	# return levels
		return levels # JCL: this was erroneously indented ^

class ScaledPlotWidget(pg.PlotWidget):
	"""
	Provides a plot widget in which the bottom axis has been re-defined
	to use the DateAxisItem that is currently waiting to be merged into
	pyqtgraph (https://github.com/pyqtgraph/pyqtgraph/pull/74).

	Also, its addItem() routine will add the item to its PlotItem, as well
	as correctly sets that item's parent.
	"""
	def __init__(self, parent, **opts):
		scaledAxis = ScaledAxisItem(orientation='bottom') # until JCL's contributions to pyqtgraph are official..
		#scaledAxis = pg.AxisItem(orientation='bottom')
		super(self.__class__, self).__init__(parent, axisItems={'bottom': scaledAxis}, **opts)
		self.getPlotItem().addItem = self.addItem

	def addItem(self, item, *args, **kargs):
		#print("adding item %s to self %s" % (item, self))
		if hasattr(item, "setParentItem"):
			log.info("(ScaledPlotWidget) also adding self %s to item %s" % (self, item))
			item.setParentItem(self)
		super(self.__class__, self).addItem(item, *args, **kargs)


class LegendItem(pg.LegendItem):
	"""
	Provides a sub-classed LegendItem from PyQtGraph which handles the
	widths correctly. In the main version of PyQtGraph, the legend seems
	to either grow bigger or not update at all, each time the legend is
	updated with items. This should provide the major (annoying) bug fix.
	"""
	def __init__(self, **opts):
		super(self.__class__, self).__init__(**opts)

	def removeItem(self, name):
		super(self.__class__, self).removeItem(name)
		self.updateSize()

	def updateSize(self):
		if self.size is not None:
			return

		height = 0
		width = 0
		for sample, label in self.items:
			height += max(sample.height(), label.height()) + 3
			width = max(width, sample.width(), label.width())
		self.setGeometry(0, 0, width+25, height)


class StickPlot(pg.BarGraphItem):
	"""
	Provides a stick plot item that is based on the BarGraphItem from
	PyQtGraph (v0.9.10), but modified so that it knows about setData(),
	and only draws single lines instead of rectangles (better performance).

	When initialized, the data must be supplied (even if only empty).
	The data must be named x and y (or height). No widths are specified,
	though a pen can be defined that may include an explicit width.

	Note that this entire class can be deleted if JCL's contributions to
	pg are available.
	"""
	def __init__(self, **opts):
		super(self.__class__, self).__init__(**opts)
		self.boundingCorners = [0, 0, 0, 0]
		self.menu = None

	def setData(self, *args, **kargs):
		"""
		Clears any data displayed by this item and displays new data.

		Note that this was taken directly from the PyQtGraph API code.
		See :func:`__init__() <pyqtgraph.PlotDataItem.__init__>` for details; it accepts the same arguments.
		"""
		x = None
		y = None
		width = None
		height = None
		err = None
		showErr = False
		pen = self.opts['pen']
		pens = self.opts['pens']
		if 'x' in kargs:
			x = kargs['x']
		if 'y' in kargs:
			y = kargs['y']
		if 'width' in kargs:
			width = kargs['width']
		if 'height' in kargs:
			height = kargs['height']
		if 'err' in kargs:
			err = kargs['err']
		if 'showErr' in kargs:
			showErr = kargs['showErr']
		if 'pens' in kargs:
			pens = kargs['pens']
		if 'pen' in kargs:
			pen = kargs['pen']

		opts = dict(
			x=x,
			y=y,
			width=width,
			height=height,
			err=err,
			showErr=showErr,
			pen=pen,
			pens=pens)
		self.setOpts(**opts)
		self.update()

	def setPen(self, *args, **kargs):
		self.opts['pen'] = pg.mkPen(*args, **kargs)
		self.update()

	def drawPicture(self):
		"""
		Draws the lines of the plot, using Qt's QPicture/QPainter methods.

		Note that only a defined pen is used, which is what provides the
		largest performance boost as compared to the BarGraphItem.
		"""
		self.picture = QtGui.QPicture()
		p = QtGui.QPainter(self.picture)

		pen = self.opts['pen']
		pens = self.opts['pens']

		if pen is None and pens is None:
			pen = getConfigOption('foreground')

		def asarray(x):
			if x is None or np.isscalar(x) or isinstance(x, np.ndarray):
				return x
			return np.array(x)

		x = asarray(self.opts.get('x'))
		y = asarray(self.opts.get('y'))
		width = asarray(self.opts.get('width'))
		height = asarray(self.opts.get('height'))
		err = self.opts.get('err')
		showErr = self.opts.get('showErr')

		if height is None:
			if y is None:
				raise Exception('must specify either y or height')
			height = y
		if (len(x) > 0) and np.isscalar(height):
			self.boundingCorners = [x.min(), 0, x.max(), height]
		elif (len(x) > 0) and (len(height) > 0):
			self.boundingCorners = [x.min(), 0, x.max(), height.max()]
		else:
			self.boundingCorners = [0, 0, 0, 0]

		p.setPen(pg.mkPen(pen))
		for i in range(len(x)):
			if pens is not None:
				p.setPen(pg.mkPen(pens[i]))
			if np.isscalar(height):
				line = QtCore.QLineF(x[i], 0, x[i], height)
				p.drawLine(line)
				if showErr and (err is not None):
					errLine = QtCore.QLineF(x[i]-err[i]/2.0, height/2.0, x[i]+err[i]/2.0, height/2.0)
					p.drawLine(errLine)
			else:
				line = QtCore.QLineF(x[i], 0, x[i], height[i])
				p.drawLine(line)
				if showErr and (err is not None):
					errLine = QtCore.QLineF(x[i]-err[i]/2.0, height[i]/2.0, x[i]+err[i]/2.0, height[i]/2.0)
					p.drawLine(errLine)

		p.end()
		self.prepareGeometryChange()

	def name(self):
		"""
		Returns the name of the plot, as normally set during
		initialization. This provides compatibility with a normal pg
		PlotItem.
		"""
		return self.opts.get('name')

	def boundingRect(self):
		"""
		Returns a QRectF based on the bounding corners that are updated
		within drawPicture(). Note that this differs significantly from
		BarGraphItem, because it was found that very small ranges in the
		y-data round up to [0..1].
		"""
		if self.picture is None:
			self.drawPicture()
		return QtCore.QRectF(
			self.boundingCorners[0],
			self.boundingCorners[1],
			self.boundingCorners[2]-self.boundingCorners[0],
			self.boundingCorners[3])

	def raiseContextMenu(self, pos):
		"""
		This raises a context menu on the plot. It is called directly
		from mouseClickEvent() whenever a right-click occurs.
		"""
		menu = self.getContextMenu()
		menu.popup(QtCore.QPoint(pos.x(), pos.y()))
		return True

	def mouseClickEvent(self, ev):
		"""
		This is called whenever a mouse click occurs on the plot.
		"""
		if ev.button() == QtCore.Qt.RightButton:
			if self.raiseContextMenu(ev):
				ev.accept()

	def getContextMenu(self, event=None):
		"""
		This is called when this item's _children_ want to raise a
		context menu that includes their parents' menus.

		For now, it provides a copy-the-data method and also the option
		to change the color of the trace to a named color.
		"""
		if self.menu is None:
			self.menu = QtGui.QMenu()
			self.menu.setTitle("%s" % self.name())

			colors = {
				"red": "r",
				"green": "g",
				"blue": "b",
				"cyan": "c",
				"magenta": "m",
				"yellow": "y",
				"black": "k",
				"white": "w"}
			for k,v in colors.items():
				c = self.menu.addAction("Turn %s" % k)
				c.triggered.connect(partial(self.setColor, color=v))

			copy = self.menu.addAction("Copy to clipboard")
			copy.triggered.connect(self.copy)

		return self.menu

	def setColor(self, color=None):
		"""
		Sets the color of the trace to a new named color. It is called
		directly from the context menu.
		"""
		if color in "rgbcmykw":
			self.setPen(pg.mkPen(color))
			self.update()

	def copy(self):
		"""
		Pushes the XY data of the plot to the clipboard as CSV format.
		"""
		def asarray(a):
			if a is None or np.isscalar(a) or isinstance(a, np.ndarray):
				return a
			return np.array(a)

		x = asarray(self.opts.get('x'))
		y = asarray(self.opts.get('y'))
		height = asarray(self.opts.get('height'))

		if height is None:
			if y is None:
				raise Exception('must specify either y or height')
			height = y

		text = ""
		for i in zip(x, height):
			text += "%s,%s\n" % (i[0], i[1])
		clipboard = QtGui.QApplication.clipboard()
		clipboard.setText(text)
		return text

	def update(self):
		self.drawPicture()


class SpectralPlot(pg.PlotDataItem):
	"""
	Provides a plot item based on PyQtGraph's PlotDataItem. The initial
	difference is that it provides an additional context menu that
	allows one to copy the plot to the clipboard.
	"""
	def __init__(self, **opts):
		super(self.__class__, self).__init__(**opts)
		self.menu = None
		self.sigClicked.connect(self.mouseClickEvent)

	def raiseContextMenu(self, pos):
		"""
		This raises a context menu on the plot. It is called directly
		from mouseClickEvent() whenever a right-click occurs.
		"""
		menu = self.getContextMenu()
		menu.popup(QtCore.QPoint(pos.x(), pos.y()))
		return True

	def mouseClickEvent(self, ev):
		"""
		This is called whenever a mouse click occurs on the plot.
		"""
		if ev.button() == QtCore.Qt.RightButton:
			if self.raiseContextMenu(ev):
				ev.accept()

	def getContextMenu(self, event=None):
		"""
		This is called when this item's _children_ want to raise a
		context menu that includes their parents' menus.

		For now, it provides a copy-the-data method and also the option
		to change the color of the trace to a named color.
		"""
		if self.menu is None:
			self.menu = QtGui.QMenu()
			self.menu.setTitle("%s" % self.name())

			colors = {
				"red": "r",
				"green": "g",
				"blue": "b",
				"cyan": "c",
				"magenta": "m",
				"yellow": "y",
				"black": "k",
				"white": "w"}
			for k,v in colors.items():
				c = self.menu.addAction("Turn %s" % k)
				c.triggered.connect(partial(self.setColor, color=v))

			copy = self.menu.addAction("Copy to clipboard")
			copy.triggered.connect(self.copy)

		return self.menu

	def setColor(self, color=None):
		"""
		Sets the color of the trace to a new named color. It is called
		directly from the context menu.
		"""
		if color in "rgbcmykw":
			self.setPen(pg.mkPen(color))
			self.update()

	def copy(self):
		"""
		Pushes the XY data of the plot to the clipboard as CSV format.
		"""
		text = ""
		for i in zip(self.xData, self.yData):
			text += "%s,%s\n" % (i[0], i[1])
		clipboard = QtGui.QApplication.clipboard()
		clipboard.setText(text)
		return text
