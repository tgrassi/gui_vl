#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
To quote Luke Campagnola from pyqtgraph author:
'Miscellaneous functions with no other home'

This should be the location for helper functions that serve general purposes
that may be of use to a variety of situations. It is preferred to include such
functions here, rather than add a dependency based on a third-party library (&
with the exception of commonly-installed ones such as the SciPy suite) or to
keep duplicating often-defined subroutines.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import subprocess
import tempfile
import socket
# third-party
import numpy as np
# local
pass




def get_git_hash():
	"""
	Returns the hash of the current git HEAD
	"""
	getGitHashCmd = ['git',
		'-C', os.path.dirname(os.path.dirname(os.path.realpath(__file__))),
		'rev-parse', '--short', 'HEAD']
	return subprocess.check_output(getGitHashCmd).strip()




################################################################################
################################################################################
# time formatting #
###################

def datetime2sec(s):
	try:
		times = list(map(float, s.split(':')))
		return times[0]*3600 + times[1]*60 + times[2]
	except:
		return 0


import datetime
def strptime(val):
	if not ('.' in val):
		return datetime.datetime.strptime(val, "%Y-%m-%d %H:%M:%S")
	
	nofrag, frag = val.split(".")
	date = datetime.datetime.strptime(nofrag, "%Y-%m-%d %H:%M:%S")
	
	frag = frag[:6]  # truncate to microseconds
	frag += (6 - len(frag)) * '0'  # add 0s
	return date.replace(microsecond=int(frag))


import os, time
def getFileAge(filename=None, unit="seconds"):
	if (not filename) or (not os.path.isfile(filename)):
		raise IOError
	else:
		age = time.time() - os.path.getmtime(filename)
		if unit == "minutes":
			age /= (60.0)
		elif unit == "hours":
			age /= (3600.0)
		elif unit == "days":
			age /= (86400.0)
		elif unit == "months":
			age /= (2.628e6)
		elif unit == "years":
			age /= (3.154e+7)
		return age


################################################################################
################################################################################
# string formatting #
#####################

def cleanText(text, remNewlines=True, remTabs=True, remMultSpaces=True):
	"""
	Converts a body of text containing newline and tab characters
	a single continuous string. At its inception, its sole purpose
	was to allow input text defined from a long block of text
	in a similar manner to docstrings.

	:param text: a body of text containing newlines and tabs
	:type text: string
	:return: a one-line string of text without newlines and tabs
	:rtype: string

	Example:
		>inputString = '''this is a very
		>	long string if I had the
		>	energy to type more and more...'''
		>outputString = cleanText(inputString)
		>print(outputString)
		this is a very long string if I had the energy to type more and more...
	"""
	if remNewlines:
		text = text.replace('\n', ' ')
		text = text.replace('\r', ' ')
	if remTabs:
		text = text.replace('\t', ' ')
	if remMultSpaces:
		while '  ' in text:
			text = text.replace('  ', ' ')
	return text


import math
def getStringPrecision(value):
	"""
	Returns what should be a reasonable string format for a floating
	point-like value (str/int/float). At its inception, its intended
	use was to consider a step value and use this for determining what
	decimal precision should be used for other floating point values.
	"""
	# do something with int
	if isinstance(value, int):
		return "{:d}"
	# convert float to str
	value = "%s" % value
	# do something with a str
	if not "." in value:
		return "{:d}"
	else:
		numDec = len(value.split(".")[1])
		return "{:.%sf}" % numDec


################################################################################
################################################################################
# other formatting #
####################

def qcolorToRGBA(qcolor):
	"""
	Gets the QColor components and returns a tuple of RGBA integers (0-255).
	"""
	from pyqtgraph.Qt import QtGui, QtCore
	if isinstance(qcolor, (QtGui.QBrush, QtGui.QPen)):
		qcolor = qcolor.color()
	elif not isinstance(qcolor, QtGui.QColor):
		raise SyntaxError("%s is not a QColor, QBrush, or QPen object!" % (qcolor))
	r = qcolor.red()
	g = qcolor.green()
	b = qcolor.blue()
	a = qcolor.alpha()
	return [r, g, b, a]

def RGBtoRgbF(rgb):
	"""
	Gets RGB(A) integers (0-255) and returns floats (0-1).
	"""
	r = rgb[0] / 255.0
	g = rgb[1] / 255.0
	b = rgb[2] / 255.0
	if len(rgb) > 3:
		a = rgb[3] / 255.0
	else:
		a = 1.0
	return [r, g, b, a]


################################################################################
################################################################################
# profiling functions #
#######################

def runsnake(command, globals=None, locals=None):
	r"""
	Loads the RunSnakeRun graphical profiler
	
	Note that `runsnake` requires the program ``runsnake``. On Ubuntu,
	this can be done with:
	> sudo apt-get install python-profiler python-wxgtk2.8
	> sudo pip install RunSnakeRun
	See the ``runsnake`` website for instructions for other platforms.
	
	`runsnake` further assumes that the system wide Python is
	installed in ``/usr/bin/python``.
	
	see also:
		* `The runsnake website <http://www.vrplumber.com/programming/runsnakerun/>`
		* ``%prun``
	
	:param command: the desired command to run, including the parentheses
	:type command: str
	"""
	if not isinstance(command, str):
		raise SyntaxError("the desired command should be a string")
	import cProfile
	fd, tmpfile = tempfile.mkstemp()
	os.close(fd)
	print("profiling command '%s' to file '%s' and launching it with 'runsnakerun'.." % (command, tmpfile))
	# cProfile.run(command.lstrip().rstrip(), filename=tmpfile)
	cProfile.runctx(command.lstrip().rstrip(), globals=globals, locals=locals, filename=tmpfile)
	try:
		os.system("/usr/bin/env python -E `which runsnake` %s &" % tmpfile)
	except:
		print("there was a problem calling runsnake!")


################################################################################
################################################################################
# converter functions #
#######################

def str_to_bool(s):
	"""
	A helper function that converts True/False strings to a boolean.

	This is necessary because a non-empty string will always return
	"True", even if its contents is "False".

	:param s: the True/False string
	:type s: str
	:returns: the boolean version of the True/False string
	:rtype: bool
	"""
	if s.lower() == "true":
		return True
	elif s.lower() == "false":
		return False
	else:
		msg = "Cannot convert %s to a bool (type = %s)" % (s, type(s))
		title = "Value Error!"
		print("%s: %s" % (title, msg))
		return None

def str_to_int(s):
	"""
	Provides a helper routine that converts the entry of a LineEdit
	object to a rounded integer.

	:param s: the string to be converted
	:type s: str
	:returns: the rounded integer
	:rtype: int
	"""
	return int(np.rint(float(s)))

def qlineedit_to_str(lineedit):
	"""
	Provides a helper routine that converts the entry of a QLineEdit
	object to a native string.

	Note that this simply reduces lots of otherwise duplicate code
	for the repetitive processing of parameters.

	:param lineedit: the LineEdit PyQT object
	:type lineedit: QtGui.LineEdit
	:returns: the contents
	:rtype: str
	"""
	text = str(lineedit.text())
	return text

def qlineedit_to_int(lineedit):
	"""
	Provides a helper routine that converts the entry of a QLineEdit
	object to a rounded integer.

	:param lineedit: the LineEdit PyQT object
	:type lineedit: QtGui.LineEdit
	:returns: the contents
	:rtype: int
	"""
	text = str(lineedit.text())
	return int(np.rint(float(text)))

def qlineedit_to_float(lineedit):
	"""
	Provides a helper routine that converts the entry of a QLineEdit
	object to a rounded integer.

	:param lineedit: the LineEdit PyQT object
	:type lineedit: QtGui.LineEdit
	:returns: the contents
	:rtype: float
	"""
	text = str(lineedit.text())
	return float(text)

def qlineedit_to_bool(lineedit):
	"""
	Provides a helper routine that converts the entry of a QLineEdit
	object to a rounded integer.

	:param lineedit: the LineEdit PyQT object
	:type lineedit: QtGui.LineEdit
	:returns: the contents
	:rtype: bool
	"""
	text = str(lineedit.text())
	if text.lower() == "true":
		return True
	elif text.lower() == "false":
		return False
	else:
		msg = "Cannot convert %s to a bool" % (text)
		title = "Value Error!"
		print("%s: %s" % (title, msg))
		return None


################################################################################
################################################################################
# pyqtgraph helper functions #
##############################


"""
The following code in this group all come from the pyqtgraph package (v0.9.10),
which is distributed under the MIT/X11 license (appended here):
---
Copyright (c) 2012  University of North Carolina at Chapel Hill
Luke Campagnola    ('luke.campagnola@%s.com' % 'gmail')

The MIT License
Permission is hereby granted, free of charge, to any person obtaining a copy of
this software and associated documentation files (the "Software"), to deal in
the Software without restriction, including without limitation the rights to use,
copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the
Software, and to permit persons to whom the Software is furnished to do so,
subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
import sys, re
import numpy as np
import decimal

def asUnicode(x):
	if sys.version_info[0] == 2:
		if isinstance(x, unicode):
			return x
		elif isinstance(x, str):
			return x.decode('UTF-8')
		else:
			return unicode(x)
	else:
		return str(x)

SI_PREFIXES = asUnicode('yzafpnµm kMGTPEZY')
SI_PREFIXES_ASCII = 'yzafpnum kMGTPEZY'

def siScale(x, minVal=1e-25, allowUnicode=True):
	"""
	Return the recommended scale factor and SI prefix string for x.
	
	Example::
	
		siScale(0.0001)   # returns (1e6, 'μ')
		# This indicates that the number 0.0001 is best represented as 0.0001 * 1e6 = 100 μUnits
	"""
	
	if isinstance(x, decimal.Decimal):
		x = float(x)
		
	try:
		if np.isnan(x) or np.isinf(x):
			return(1, '')
	except:
		print(x, type(x))
		raise
	if abs(x) < minVal:
		m = 0
		x = 0
	else:
		m = int(np.clip(np.floor(np.log(abs(x))/np.log(1000)), -9.0, 9.0))
	
	if m == 0:
		pref = ''
	elif m < -8 or m > 8:
		pref = 'e%d' % (m*3)
	else:
		if allowUnicode:
			pref = SI_PREFIXES[m+8]
		else:
			pref = SI_PREFIXES_ASCII[m+8]
	p = .001**m
	
	return (p, pref)	

def siFormat(x, precision=3, suffix='', space=True, error=None, minVal=1e-25, allowUnicode=True):
	"""
	Return the number x formatted in engineering notation with SI prefix.
	
	Example::
		siFormat(0.0001, suffix='V')  # returns "100 μV"
	"""
	
	if space is True:
		space = ' '
	if space is False:
		space = ''
		
	
	(p, pref) = siScale(x, minVal, allowUnicode)
	if not (len(pref) > 0 and pref[0] == 'e'):
		pref = space + pref
	
	if error is None:
		fmt = "%." + str(precision) + "g%s%s"
		return fmt % (x*p, pref, suffix)
	else:
		if allowUnicode:
			plusminus = space + asUnicode("±") + space
		else:
			plusminus = " +/- "
		fmt = "%." + str(precision) + "g%s%s%s%s"
		return fmt % (x*p, pref, suffix, plusminus, siFormat(error, precision=precision, suffix=suffix, space=space, minVal=minVal))

def siEval(s):
	"""
	Convert a value written in SI notation to its equivalent prefixless value
	
	Example::
	
		siEval("100 μV")  # returns 0.0001
	"""
	
	s = asUnicode(s)
	m = re.match(r'(-?((\d+(\.\d*)?)|(\.\d+))([eE]-?\d+)?)\s*([u' + SI_PREFIXES + r']?).*$', s)
	if m is None:
		raise Exception("Can't convert string '%s' to number." % s)
	v = float(m.groups()[0])
	p = m.groups()[6]
	#if p not in SI_PREFIXES:
		#raise Exception("Can't convert string '%s' to number--unknown prefix." % s)
	if p ==  '':
		n = 0
	elif p == 'u':
		n = -2
	else:
		n = SI_PREFIXES.index(p) - 8
	return v * 1000**n


################################################################################
################################################################################
# system helper functions #
###########################

def get_local_ip():
    """
    Returns a single IP that is active as the default route.
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # doesn't even have to be reachable
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP


################################################################################
################################################################################

