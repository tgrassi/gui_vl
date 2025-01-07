#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module simply loads the sensorviewer.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import sys
import os
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
# local
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import Dialogs


if __name__ == '__main__':
	# define GUI elements
	qApp = QtGui.QApplication(sys.argv)
	if (len(sys.argv) > 1):
		mainGUI = Dialogs.CASACSensorViewer(filename=sys.argv[1], contFileUpdate=False)
	else:
		mainGUI = Dialogs.CASACSensorViewer()
	
	# start GUI
	mainGUI.show()
	qApp.exec_()
	qApp.deleteLater()
	sys.exit()
