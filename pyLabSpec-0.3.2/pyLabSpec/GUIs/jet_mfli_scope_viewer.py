#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This program simply launches the JetMFLIScopeViewer from the Dialogs
module.

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
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import Dialogs
import Widgets
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
	sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
import Instruments




if __name__ == '__main__':
	# define GUI elements
	qApp = QtGui.QApplication(sys.argv)
	mainGUI = Dialogs.JetMFLIScopeViewer()
	
	# start GUI
	mainGUI.show()
	qApp.exec_()
	qApp.deleteLater()
	sys.exit()
