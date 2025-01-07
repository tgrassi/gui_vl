#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# TODO
#
# LineProfile:
# - add routine to LineProfile that reports all the defined values
# - estimate errors/uncertainties...
#	https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html
#	http://stackoverflow.com/questions/14581358/getting-standard-errors-on-fitted-parameters-using-the-optimize-leastsq-method-i
#	http://central.scipy.org/item/36/2/error-estimates-for-fit-parameters-resulting-from-least-squares-fits-using-bootstrap-resampling
#	http://stats.stackexchange.com/questions/71154/when-an-analytical-jacobian-is-available-is-it-better-to-approximate-the-hessia
#
"""
This package contains classes and methods used for fitting spectral data.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
from __future__ import print_function
# standard library
import sys
import os
import math
import warnings
import distutils.version
# thirdy-party
import numpy as np
import scipy
from scipy import optimize, signal
from scipy.integrate import quad
try:
	import pyfftw
except ImportError:
	msg = "pyFFTW not found! this speeds up the FFT routines immensely, which "
	msg += "are used in the 2f line profiles defined in Fourier space. "
	msg += "if this is important to you, try 'sudo pip install pyFFTW' "
	msg += "(you may also need the 'libfftw3-dev' and related packages.."
	warnings.warn(msg)
except AttributeError:
	msg = "pyFFTW version mismatch! newer versions of pyFFTW (v0.11.1+)"
	msg += " are known to raise issues.. until they fix this, you should"
	msg += " switch to v0.10.4 (e.g. 'pip install pyFFTW==0.10.4')"
	warnings.warn(msg)
	raise
# local
pass

# define shortcuts for math functions
exp = np.exp
sqrt = np.sqrt
ln = math.log
pi = math.pi
cos = np.cos
sin = np.sin

class Parameter(object):

	"""
	This class defines an object that may serve as an input parameter
	for the line profile fits.
	"""
	#def __init__(self, value):
	#	"""
	#	Initialization of the parameter
	#
	#	:param value: Parameter value
	#	:type value: float
	#	"""
	#	self.value = value
	def __init__(
		self, name=None,
		value=None, unc=0.0,
		locked=True, min=None, max=None):
		self.name = name
		self.value = value
		self.locked = locked
		self.min = min
		self.max = max
		self.unc = unc

	def set(self, value):
		"""
		Sets the parameter value

		:param value: Parameter value
		:type value: float
		"""
		self.value = value

	def __call__(self):
		"""
		Returns the parameter value

		:returns: parameter value
		"""
		return self.value


class Parameters(object):
	"""
	This class defines an object that may serve as a collection of
	parameters for the line profile fits.
	"""
	def __init__(self, params=[]):
		"""
		Initializes the Parameters object
		
		:param params: (optional) a predefined list of parameters
		:type params: list, Parameters
		"""
		# initialize containers/parameters
		self.params = params

	def add(self, name, value=0.0, locked=True, min=None, max=None, unc=0.0):
		"""
		Adds a new parameter to the collection
		
		:param name: the name of the new parameter
		:param value: (optional) the value to initialize it (default: 0.0)
		:param locked: (optional) whether the parameter should be locked (fits only) (default: True)
		:param min: (optional) the minimum value to allow in a constrained fit (default: None)
		:param max: (optional) the minimum value to allow in a constrained fit (default: None)
		:param unc: (optional) the uncertainty of its value (fit results only)
		:type name: str
		:type value: float
		:type locked: bool
		:type min: Nonetype, float
		:type max: Nonetype, float
		:type unc: float
		"""
		p = Parameter(
			name=name,
			value=value, unc=unc,
			locked=locked, min=min, max=max)
		self.params.append(p)

	def remove(self, name):
		"""
		Removes the named parameter from the collection
		
		:param name: the name of the targeted parameter
		:type name: str
		"""
		if name not in [p.name for p in self.params]:
			print("WARNING: you attempted to remove")
		for i,p in enumerate(self.params):
			if name == p.name:
				del self.params[i]
				break

	def getAll(self):
		"""
		Returns the current collection of parameters
		
		:returns: the collection of parameters, abc-sorted by their name
		:rtype: list
		"""
		return sorted(self.params, key=lambda x: x.name)

	def getByName(self, name=None):
		"""
		Returns the named parameter
		
		:param name: the name of the parameter of interest
		:type name: str
		
		:returns: the named parameter (or None, if the name doesn't exist)
		:rtype: Parameter, Nonetype
		"""
		if name is None:
			raise SyntaxError("this routine requires an input argument for the desired name")
		for p in self.params:
			if p.name == name:
				return p
		return None

	def pprint(self, printout=False):
		"""
		Returns a pprint report (table w/ header) of the collection of parameters
		
		:param printout: whether to also print the result to STDOUT
		:type printout: bool
		
		:returns: the pprint report
		:rtype: str
		"""
		name_w = 0
		val_w = 0
		lock_w = 0
		min_w = 0
		max_w = 0
		unc_w = 0
		for p in self.params:
			name_w = max(name_w, len("%s" % p.name), 4)
			val_w = max(val_w, len("%s" % p.value), 5)
			lock_w = max(lock_w, len("%s" % p.locked), 5)
			min_w = max(min_w, len("%s" % p.min), 3)
			max_w = max(max_w, len("%s" % p.max), 3)
			unc_w = max(unc_w, len("%s" % p.unc), 3)
		name_f = '%{0}s'.format(name_w)
		val_f = '%{0}s'.format(val_w)
		lock_f = '%{0}s'.format(lock_w)
		min_f = '%{0}s'.format(min_w)
		max_f = '%{0}s'.format(max_w)
		unc_f = '%{0}s'.format(unc_w)

		entry_f = "%s  %s  %s  %s  %s  %s\n" % (name_f, val_f, lock_f, min_f, max_f, unc_f)
		header = entry_f % ("NAME", "VALUE", "LOCK?", "MIN", "MAX", "UNC")
		message = header
		for p in self.params:
			message += entry_f % (p.name, p.value, p.locked, p.min, p.max, p.unc)
		if printout: print(message)
		return message

	def unlockedNaN(self):
		"""
		Returns a copy of itself (i.e. of type Parameters), except converts the
		all the values/uncertainties of the unlocked parameters to np.nan
		
		:returns: nan'd Parameters
		:rtype: Parameters
		"""
		import copy
		copy_of_self = copy.deepcopy(self)
		for p in copy_of_self.getAll():
			if not p.locked:
				p.value = np.nan
				p.unc = np.nan
		return copy_of_self

class LineProfile(object):
	"""
	This class defines an object that provides line profile shapes.
	"""
	splittableParams = [
		"tauRad", "fwhm",
		"velColl", "velDopp",
		"coeffNar", "velSD",
		"phi"]
	
	def __init__(
		self,
		params=None,
		debugging=False,
		center=None,
		length=None,
		width=None,
		step=None,
		fwhm=None,
		intensity=None,
		tauRad=None,
		temperature=None, # temperature [K]
		pressure=None, # pressure [mTorr]
		velColl=None, # collisional relaxation rate [Hz]
		velDopp=None, # doppler broadening [Hz]
		phi=0.0, # phase detuning
		modDepth=0.0, # FM depth [Hz]
		modRate=0.0, # FM rate [Hz]
		**kwargs):
		"""
		Initializes the LineProfile object
		
		:param params: (optional) a Parameters object
		:param debugging: (optional) whether to activate debugging-related messages
		:param center: (optional) the rest frequency of the line profile (units: MHz)
		:param length: (optional) the length of frequency axis in data points
		:param width: (optional) the span of the frequency axis (units: MHz)
		:param step: (optional) the stepsize of the frequency axis (units: MHz)
		:param fwhm: (optional) the fwhm to use for some of the line profiles (only the 1f gaussian & lorentzian) (units: MHz)
		:param intensity: (optional) the peak intensity of the line profile
		:param tauRad: (unused!) (optional) the A_ul (radiative lifetime of the upper state) defining the minimal linewidth of the transition (units: Hz)
		:param temperature: (unused!) (optional) the temperature (units: K)
		:param pressure: (unused!) (optional) the pressure (units: mTorr?)
		:param velColl: (optional) collisional relaxation rate, associated with Lorentzian profiles (units: MHz)
		:param velDopp: (optional) doppler broadening rate, associated with Gaussian profiles (units: MHz)
		:param phi: (optional) the phase detuning offset contributing to dispersion-related profile asymmetry (units: deg)
		:param modDepth: (optional) the frequency-modulation depth (units: MHz)
		:param modRate: (optional) the frequency-modulation rate (units: MHz)
		:type params: list, Parameters
		:type debugging: bool
		:type center: float
		:type length: int
		:type width: float
		:type step: float
		:type fwhm: float
		:type intensity: float
		:type tauRad: float
		:type temperature: float
		:type pressure: float
		:type velColl: float
		:type velDopp: float
		:type phi: float
		:type modDepth: float
		:type modRate: float
		"""

		self.debugging = debugging

		self.width = width
		self.length = length
		self.step = step
		self.center = center
		self.fwhm = fwhm
		self.intensity = intensity
		self.tauRad = tauRad
		self.velColl = velColl
		self.velDopp = velDopp
		self.phi = phi
		self.modDepth = modDepth
		self.modRate = modRate
		if params is not None:
			self.params = params
			self.loadParams()
		self.updateParams()

		self.kwargs = kwargs


	def loadParams(self, params=None):
		"""
		Processes all the input params.
		
		:param params: (optional) a Parameters object
		:type params: list, Parameters
		"""
		if params is not None:
			self.params = params
		if isinstance(self.params, (list, tuple)):
			self.params = Parameters(params)
		if self.debugging:
			self.params.pprint()

		for p in self.params.getAll():
			setattr(self, "%s" % p.name, p.value)

		self.updateParams()

	def updateParams(self):
		"""
		Rederives some parameters, based on others.
		"""
		# if no length, derive from width/step
		if not self.length and (self.width and self.step):
			self.length = self.width / float(self.step)
		# update precision, based on step
		self.updatePrecision()

	def updatePrecision(self):
		"""
		Updates the step precision, ensuring the avoidance of rounding errors
		involved with floating-point precision.
		"""
		if self.step is not None:
			digitsstring = "%s" % self.step
			self.precision = len(digitsstring.split(".")[1])
			if self.debugging:
				print("precision is: %s" % self.precision)
		else:
			raise SyntaxError("the stepsize has not yet been set!")


	def getBlank(self, x=[], center=None,
		length=None, width=None, step=None):
		"""
		Returns a blank spectrum, containing the frequency axis and
		intensities at zero.
		
		:param x: (optional) an array containing the frequency axis
		:param center: (optional) the rest frequency of the line profile (units: MHz)
		:param length: (optional) the length of frequency axis in data points
		:param width: (optional) the span of the frequency axis (units: MHz)
		:param step: (optional) the stepsize of the frequency axis (units: MHz)
		:type x: list, np.ndarray
		:type center: float
		:type length: int
		:type width: float
		:type step: float
		
		:returns: the frequency and intensity axes
		:rtype: tuple(np.ndarray, np.ndarray)
		"""
		if center: self.center = center
		if length: self.length = length
		if width: self.width = width
		if step:
			self.step = step
			self.updatePrecision()
		if not len(x):
			if length is not None:
				self.length = length
			if not self.length % 2:
				self.length += 1
			if step is not None:
				self.step = step
				self.updatePrecision()
			if (not self.step) and any([not x for x in (self.length, self.width)]):
				message = "LineProfile.getBlank() requires at minimum, a defined x-axis, or a length and step."
				raise SyntaxError(message)
			if self.center is not None:
				x_lower = self.center - ((self.length-1) / 2.0) * self.step
				x_upper = self.center + ((self.length-1) / 2.0) * self.step
			else:
				x_lower = 0.0
				x_upper = (self.length-1)*self.step
			x = np.linspace(x_lower, x_upper, self.length)
		self.length = len(x)
		self.step = abs(x[1]-x[0])
		self.updatePrecision()

		y = np.zeros_like(x)
		return x, y

	def getBoxcar(self, x=[],
		center=None, length=None, step=None,
		fwhm=None, intensity=None, **kwargs):
		"""
		Returns a boxcar function, with the 'fwhm' interval centered at
		'center' set to 'intensity', and the rest set to 0.
		
		:param x: (optional) an array containing the frequency axis
		:param center: (optional) the rest frequency of the line profile (units: MHz)
		:param length: (optional) the length of frequency axis in data points
		:param step: (optional) the stepsize of the frequency axis (units: MHz)
		:param fwhm: (optional) the fwhm to use for some of the line profiles (only the 1f gaussian & lorentzian) (units: MHz)
		:param intensity: (optional) the peak intensity of the line profile
		:type x: list, np.ndarray
		:type center: float
		:type length: int
		:type step: float
		:type fwhm: float
		:type intensity: float
		
		:returns: the frequency and intensity axes
		:rtype: tuple(np.ndarray, np.ndarray)
		"""
		if center: self.center = center
		if length: self.length = length
		if step:
			self.step = step
			self.updatePrecision()
		if fwhm: self.fwhm = fwhm
		if intensity: self.intensity = intensity
		if not len(x):
			if length is not None: self.length = length
			if step is not None:
				self.step = step
				self.updatePrecision()
			x, y = self.getBlank()
		self.length = len(x)
		self.step = abs(x[1]-x[0])
		self.updatePrecision()

		for index,val in np.ndenumerate(x):
			val = np.around(val, self.precision)
			in_range = (val >= (self.center-self.fwhm/2.0)) and (val <= (self.center+self.fwhm/2.0))
			if val == self.center or in_range:
				y[index] = self.intensity
		return x, y

	def getGauss(self, x=[], center=None, length=None,
		step=None, fwhm=None, intensity=None, **kwargs):
		"""
		Returns a gaussian curve via its analytic definition.
		
		:param x: (optional) an array containing the frequency axis
		:param center: (optional) the rest frequency of the line profile (units: MHz)
		:param length: (optional) the length of frequency axis in data points
		:param step: (optional) the stepsize of the frequency axis (units: MHz)
		:param fwhm: (optional) the fwhm to use for some of the line profiles (only the 1f gaussian & lorentzian) (units: MHz)
		:param intensity: (optional) the peak intensity of the line profile
		:type x: list, np.ndarray
		:type center: float
		:type length: int
		:type step: float
		:type fwhm: float
		:type intensity: float
		
		:returns: the frequency and intensity axes
		:rtype: tuple(np.ndarray, np.ndarray)
		"""
		if center: self.center = center
		if length: self.length = length
		if step:
			self.step = step
			self.updatePrecision()
		if fwhm: self.fwhm = fwhm
		if intensity: self.intensity = intensity
		if not len(x):
			if length is not None: self.length = length
			if step is not None:
				self.step = step
				self.updatePrecision()
			x, y = self.getBlank()
		self.length = len(x)
		self.step = abs(x[1]-x[0])
		self.updatePrecision()

		gaussian = lambda x, x0, fwhm: exp(-(x-x0)**2.0 / fwhm**2.0 * 4*ln(2))
		y = gaussian(x, self.center, self.fwhm)
		return x, y/y.max()*self.intensity

	def getGauss2f(self, x=[], center=None, length=None,
		step=None, fwhm=None, intensity=None, **kwargs):
		"""
		Returns a 2f-gaussian curve via its analytic definition.
		
		:param x: (optional) an array containing the frequency axis
		:param center: (optional) the rest frequency of the line profile (units: MHz)
		:param length: (optional) the length of frequency axis in data points
		:param step: (optional) the stepsize of the frequency axis (units: MHz)
		:param fwhm: (optional) the fwhm to use for some of the line profiles (only the 1f gaussian & lorentzian) (units: MHz)
		:param intensity: (optional) the peak intensity of the line profile
		:type x: list, np.ndarray
		:type center: float
		:type length: int
		:type step: float
		:type fwhm: float
		:type intensity: float
		
		:returns: the frequency and intensity axes
		:rtype: tuple(np.ndarray, np.ndarray)
		"""
		if center: self.center = center
		if length: self.length = length
		if step:
			self.step = step
			self.updatePrecision()
		if fwhm: self.fwhm = fwhm
		if intensity: self.intensity = intensity
		if not len(x):
			if length is not None: self.length = length
			if step is not None:
				self.step = step
				self.updatePrecision()
			x, y = self.getBlank()
		self.length = len(x)
		self.step = abs(x[1]-x[0])
		self.updatePrecision()

		gaussian_true = lambda x, x0, sig: 1 / sqrt(2*pi) / sig * exp(-(x-x0)**2.0 / 2.0 / sig**2.0)
		gaussian2f_true = lambda x, x0, sig: gaussian_true(x,x0,sig) * (sig-(x-x0)) * (sig+(x-x0)) / sig**4.0
		sig = self.fwhm / 2 / sqrt(2*ln(2))
		y = gaussian2f_true(x, self.center, sig)
		y *= self.intensity/y.max()
		## notes:
		# first zero-point crossing should be at 85.0184% its fwhm
		# ratio of the sidelobes should be -2.24544569249
		return x, y

	def getLorentzian(self, x=[], center=None, length=None,
		step=None, fwhm=None, intensity=None, **kwargs):
		"""
		Returns a Lorentzian curve via its analytic definition.
		
		:param x: (optional) an array containing the frequency axis
		:param center: (optional) the rest frequency of the line profile (units: MHz)
		:param length: (optional) the length of frequency axis in data points
		:param step: (optional) the stepsize of the frequency axis (units: MHz)
		:param fwhm: (optional) the fwhm to use for some of the line profiles (only the 1f gaussian & lorentzian) (units: MHz)
		:param intensity: (optional) the peak intensity of the line profile
		:type x: list, np.ndarray
		:type center: float
		:type length: int
		:type step: float
		:type fwhm: float
		:type intensity: float
		
		:returns: the frequency and intensity axes
		:rtype: tuple(np.ndarray, np.ndarray)
		"""
		if center: self.center = center
		if length: self.length = length
		if step:
			self.step = step
			self.updatePrecision()
		if fwhm: self.fwhm = fwhm
		if intensity: self.intensity = intensity
		if not len(x):
			if length is not None: self.length = length
			if step is not None:
				self.step = step
				self.updatePrecision()
			x, y = self.getBlank()
		self.length = len(x)
		self.step = abs(x[1]-x[0])
		self.updatePrecision()

		lorentzian = lambda x, x0, fwhm: (fwhm/2.0)**2 / ((fwhm/2.0)**2 + (x-x0)**2)
		y = lorentzian(x, self.center, self.fwhm)
		return x, y/y.max()*self.intensity
	def getLorentzian2f(self, x=[], center=None, length=None,
		step=None, fwhm=None, intensity=None, **kwargs):
		"""
		Returns a Lorentzian curve via its analytic definition.
		
		Note that this function is superceded by getDore(profileType="lorentzian2f").
		
		:param x: (optional) an array containing the frequency axis
		:param center: (optional) the rest frequency of the line profile (units: MHz)
		:param length: (optional) the length of frequency axis in data points
		:param width: (optional) the span of the frequency axis (units: MHz)
		:param step: (optional) the stepsize of the frequency axis (units: MHz)
		:param fwhm: (optional) the fwhm to use for some of the line profiles (only the 1f gaussian & lorentzian) (units: MHz)
		:param intensity: (optional) the peak intensity of the line profile
		:type x: list, np.ndarray
		:type center: float
		:type length: int
		:type step: float
		:type fwhm: float
		:type intensity: float
		
		:returns: the frequency and intensity axes
		:rtype: tuple(np.ndarray, np.ndarray)
		"""
		if center: self.center = center
		if length: self.length = length
		if step:
			self.step = step
			self.updatePrecision()
		if fwhm: self.fwhm = fwhm
		if intensity: self.intensity = intensity
		if not len(x):
			if length is not None: self.length = length
			if step is not None:
				self.step = step
				self.updatePrecision()
			x, y = self.getBlank()
		self.length = len(x)
		self.step = abs(x[1]-x[0])
		self.updatePrecision()

		lorentzian = lambda x, x0, fwhm: (fwhm/2.0)**2 / ((fwhm/2.0)**2 + (x0-x)**2)
		y = lorentzian(x, self.center, self.fwhm)
		from scipy import interpolate
		rep = interpolate.splrep(x, y)
		y2 = -1*interpolate.splev(x, rep, der=2)
		return x, y2*self.intensity/y2.max()


	def getDore(self, x=[], center=None, intensity=None, length=None, step=None,
		fwhm=None, velColl=None, velDopp=None, velSD=None, coeffNar=None,
		modDepth=None, modRate=None, phi=None, profileType="voigt2f",
		useBesselExpansion=False, **kwargs):
		"""
		Returns a variety of convolved line profiles based on
		Dore, L., J. Mol. Spec. (2003).
		
		The available profiles types (profileType="blah") are:
		lorentzian2f - a 2f-lorentzian, where the width is based on an exponential decay of the relaxation due to collisions
		voigt - a convolution of a gaussian and lorentzian, with the gaussian width caused by inhomogeneous Doppler broadening
		voigt2f - the 2f-voigt
		galatry2f - a profile in which the Doppler broadening is reduced by a narrowing coefficient
		sdvoigt2f - speed-dependent relaxation is added to the 2f-voigt
		sdgalatry2f - speed-dependent relaxation is added to the 2f-galatry
		
		:param x: (optional) an array containing the frequency axis
		:param center: (optional) the rest frequency of the line profile (units: MHz)
		:param length: (optional) the length of frequency axis in data points
		:param step: (optional) the stepsize of the frequency axis (units: MHz)
		:param fwhm: (optional) the fwhm to use for some of the line profiles (only the 1f gaussian & lorentzian) (units: MHz)
		:param intensity: (optional) the peak intensity of the line profile
		:param velColl: (optional) collisional relaxation rate, associated with Lorentzian profiles (units: MHz)
		:param velDopp: (optional) doppler broadening rate, associated with Gaussian profiles (units: MHz)
		:param phi: (optional) the phase detuning offset contributing to dispersion-related profile asymmetry (units: deg)
		:param modDepth: (optional) the frequency-modulation depth (units: MHz)
		:param modRate: (optional) the frequency-modulation rate (units: MHz)
		:param profileType: (optional) the type of line profile to return, discussed above/separately
		:type x: list, np.ndarray
		:type center: float
		:type length: int
		:type step: float
		:type fwhm: float
		:type intensity: float
		:type velColl: float
		:type velDopp: float
		:type phi: float
		:type modDepth: float
		:type modRate: float
		:type profileType: str
		
		:returns: the frequency and intensity axes
		:rtype: tuple(np.ndarray, np.ndarray)
		"""
		from scipy import integrate, interpolate
		from scipy.special import jv
		try:
			import pyfftw
		except ImportError:
			#print("WARNING: the pyFFTW module was not available, and thus cannot be used to speed up the FFT-related functions")
			pass
		else:
			scipy.fftpack = pyfftw.interfaces.scipy_fftpack
			pyfftw.interfaces.cache.enable()
		
		if center is not None: self.center = center
		if intensity is not None: self.intensity = intensity
		if velColl is not None: self.velColl = velColl
		if velDopp is not None: self.velDopp = velDopp
		if coeffNar is not None: self.coeffNar = coeffNar
		if velSD is not None: self.velSD = velSD
		if modDepth is not None: self.modDepth = modDepth
		if modRate is not None: self.modRate = modRate
		if phi is not None: self.phi = phi

		# check that enough variables are defined for a given profile type
		# note that the normalization factors match He & Zhang (2007)
		if self.velColl is None:
			raise SyntaxError("velColl must be defined for all the convoluted profiles!")
		alphaL = self.velColl * pi
		if ("voigt" in profileType) or ("galatry" in profileType):
			if self.velDopp is None:
				raise SyntaxError("velDopp must be defined for the Voigt-style profiles!")
			alphaD = self.velDopp *pi/sqrt(ln(2))
		if "galatry" in profileType:
			if self.coeffNar is None:
				raise SyntaxError("the narrowing coefficient is not defined for the Galatry-style profiles!")
			beta = alphaD * self.coeffNar
		if "sd" in profileType:
			if self.velSD is None:
				raise SyntaxError("the phenomenological relaxation rate must be defined for the speed-dependent profiles!")
			alphaSD = self.velSD /2.0/pi

		# define the Fourier space
		if not len(x):
			if length is not None: self.length = length
			if step is not None:
				self.step = step
				self.updatePrecision()
			x, y = self.getBlank()
		self.length = len(x)
		self.step = (max(x)-min(x))/len(x)
		self.updatePrecision()
		T = np.linspace(0, 1/self.step, self.length)

		### generate basic line profile
		#lines = lambda t: exp(-1j*2*pi*t*self.center) # basic generalization
		lines = lambda t: cos(-2*pi*t*self.center-self.phi*pi/180.0)+1j*sin(-2*pi*t*self.center+self.phi*pi/180.0) # with IM dispersion
		phi_coll = lambda t: exp(-t*alphaL)
		phi_doppler = lambda t: exp(-(alphaD*t)**2.0 / 4.0)
		phi_gal = lambda t: exp((1 - t*beta - exp(-t*beta))/(2*(beta/alphaD)**2.0))
		phi_phen = lambda t: exp(-t*(alphaL-3/2.0*alphaSD))/(1+alphaSD*t)**(3/2.0)
		phi_sdvoigt = lambda t: exp(-(alphaD*t)**2.0 / (4*(1+alphaSD*t)))
		phi_sdgal = lambda t: exp(alphaSD*t*(1-exp(-t*beta))**2.0 / (4*(beta/alphaD)**2 * (1+alphaSD*t)))
		dore_lorentzian = lambda t: lines(t) * phi_coll(t)
		dore_voigt = lambda t: lines(t) * phi_coll(t) * phi_doppler(t)
		dore_galatry = lambda t: lines(t) * phi_coll(t) * phi_gal(t)
		dore_sdgalatry = lambda t: lines(t) * phi_gal(t) * phi_phen(t) * phi_sdgal(t)
		dore_sdvoigt = lambda t: lines(t) * phi_phen(t) * phi_sdvoigt(t)
		if profileType == "lorentzian2f":
			y = scipy.fftpack.ifftshift(scipy.fftpack.ifft(dore_lorentzian(T))).real
		elif profileType in ("voigt", "voigt2f"):
			y = scipy.fftpack.ifftshift(scipy.fftpack.ifft(dore_voigt(T))).real
		elif profileType == "galatry2f":
			y = scipy.fftpack.fftshift(scipy.fftpack.ifft(dore_galatry(T))).real
		elif profileType == "sdvoigt2f":
			y = scipy.fftpack.fftshift(scipy.fftpack.ifft(dore_sdvoigt(T))).real
		elif profileType == "sdgalatry2f":
			y = scipy.fftpack.fftshift(scipy.fftpack.ifft(dore_sdgalatry(T))).real
		### normalize intensity and convert to 2f if appropriate
		y = (y-y.min())/y.max()
		if "2f" in profileType:
			rep = interpolate.splrep(x, y)
			y = -interpolate.splev(x, rep, der=2)
			y /= y.max()
		### convolve with bessel
		#useBesselExpansion = True
		self.modDepth *= 5 / sqrt(alphaL**2 + alphaD**2)
		if useBesselExpansion: # note: is not actually INFINITE.. up to 5th order, but doesn't work well anyway
			bessels = lambda t: jv(0, t*self.modDepth) + 2*np.sum([jv(n, t*self.modDepth) * np.cos(n*self.modRate) * 1j**n for n in range(1,6)])
		else:
			if "2f" in profileType:
				#bessels = lambda t: -2*jv(2, t*self.modDepth) # best results, but initial guess is NaN
				bessels = lambda t: jv(0, t*self.modDepth) - 2*jv(2, t*self.modDepth)*np.cos(2*self.modRate)
			else:
				bessels = lambda t: jv(0, t*self.modDepth) # problem: ignores mod rate
		#bessels = lambda t: t # a quick hack to return something of the correct shape
		#bessels = lambda t: exp(1j*self.modDepth*t * np.cos(self.modRate)) # according to Eq. 3 from Dore (2003)
		mod = scipy.fftpack.fftshift(scipy.fftpack.ifft(bessels(T))).real
		y = signal.fftconvolve(y, mod, mode='same')
		#y = mod
		if y.max() > -y.min():
			y /= y.max()
		else:
			y /= y.min()
		return x, y/y.max()*self.intensity

	def runfit(self,
		spec=None, x=None, y=None,
		params=None, profileType=None,
		method="trf", f_scale=0.1):
		"""
		Fits a line profile to a set of spectral data using the least_squares
		routine from scipy.optimize. This code therefore requires scipy > 0.17.
		
		The available profiles types (profileType="blah") are:
		gauss - based on the profile provided by getGauss()
		gauss2f - based on the profile provided by getGauss2f()
		lorentzian - based on the profile provided by getLorentzian()
		lorentzian2f - based on the profile provided by getDore()
		voigt - based on the profile provided by getDore()
		voigt2f - based on the profile provided by getDore()
		galatry2f - based on the profile provided by getDore()
		sdvoigt2f - based on the profile provided by getDore()
		sdgalatry2f - based on the profile provided by getDore()
		
		:param spec: (optional) a Spectrum representing the data to fit
		:param x: (optional) an array containing the frequency axis to fit
		:param y: (optional) an array containing the intensity axis to fit
		:param params: (optional) a Parameters object
		:param profileType: (optional) the type of line profile to return, discussed above/separately
		:type spec: pyLabSpec.spectrum.Spectrum
		:type x: list, np.ndarray
		:type y: list, np.ndarray
		:type params: list, Parameters
		:type profileType: str
		
		:returns: the frequency and intensity axes
		:rtype: tuple(np.ndarray, np.ndarray)
		"""
		if distutils.version.LooseVersion(scipy.__version__) < "0.17":
			msg = "ERROR: your scipy version is outdated, and thus the "
			msg += "scipy.optimize.least_squares() method is not available!"
			msg += "\n\ncurrent version: %s" % scipy.__version__
			msg += "\nrequired version: 0.17 or above"
			raise ImportError(msg)
		if params is None:
			raise SyntaxError("you did not give any input parameters to use for the fit!")

		### initialize new arrays
		dataOrig = {"x":[], "y":[]}
		if spec:
			idx_radius = 150
			if self.width is not None:
				self.step = float(np.abs(spec.x[0] - spec.x[1]))
				if self.step == 0:
					self.step = (max(spec.x)-min(spec.x))/len(spec.x)
				idx_radius = int(round(self.width/2.0/self.step))
			idx_cen = np.abs(spec.x).argmin()
			idx_low = idx_cen-idx_radius
			idx_hi = idx_cen+idx_radius
			dataOrig["x"] = spec.x[idx_low:idx_hi+1]
			dataOrig["y"] = spec.y[idx_low:idx_hi+1]
		elif x & y:
			dataOrig["x"] = x
			dataOrig["y"] = y
		x = dataOrig["x"].copy()
		new_y = dataOrig["y"].copy()
		fit_y = np.zeros_like(new_y)
		res_y = new_y - fit_y

		# run some sanity checks and possibly activate warnings
		try:
			# check that length of x is close to original
			if not np.isclose(len(x), len(dataOrig["x"]), rtol=1e-1):
				UserWarning("the length of the dummy x axis was not close to the original (within 10%)!")
			# check for duplicate entries in x
			elif not len(list(set(x))) == len(x):
				UserWarning("the x axis appears to have duplicate values! this might cause unexpected problems")
		except:
			raise UserWarning("there was trouble ensuring the dummy x axis is similar to the original")

		### process parameters & run fit
		if params is not None:
			self.params = params
		if isinstance(self.params, (list, tuple)):
			self.params = Parameters(params)
		polynom = [0.0, 0.0, 0.0, 0.0]
		###
		### scipy.optimize.odrpack version (no constraints -> possible runtime errors!)
		###
		#from scipy.odr import odrpack as odr
		#from scipy.odr import models
		#beta0 = []
		#for k in sorted(params.keys()):
		#	beta0.append(params[k])
		#def get_fit(B, x):
		#	kwargs = {}
		#	for i,k in enumerate(sorted(params.keys())):
		#		kwargs[k] = abs(B[i])
		#	print(kwargs)
		#	profile = self.getGauss2f(x=x, **kwargs)
		#	return profile[1]
		#mydata = odr.Data(x, res_y)
		#mymodel = odr.Model(get_fit)
		#myodr = odr.ODR(mydata, mymodel, beta0=beta0, maxit=self.maxit)
		#myodr.set_job(fit_type=self.fit_type)
		#if self.iprint:
		#	myodr.set_iprint(
		#		init=self.iprint,
		#		iter=self.iprint,
		#		final=self.iprint)
		#try:
		#	myfit = myodr.run()
		#except RuntimeError:
		#	print("received a RuntimeError")
		#	return None
		###
		### lmfit version (no constraints!)
		###
		#try:
		#	import lmfit
		#except ImportError:
		#	print("lmfit not found! try 'sudo pip install lmfit'")
		#	raise
		#beta0 = lmfit.Parameters()
		#for k in sorted(params.keys()):
		#	minimum = None
		#	maximum = None
		#	if not k == "center":
		#		minimum = 0
		#	else:
		#		minimum = -1
		#		maximum = 1
		#	beta0.add(k, value=params[k], min=minimum, max=maximum)
		#def get_fit(beta0):
		#	kwargs = {}
		#	for i,k in enumerate(sorted(params.keys())):
		#		kwargs[k] = beta0[k].value
		#	print(kwargs)
		#	profile = lineprofile.getDore(x=x, **kwargs)
		#	return profile[1]-new_y
		#result = lmfit.minimize(get_fit, beta0, args=())
		###
		### scipy.optimize.least_squares version
		###
		beta0 = []
		betaNames = []
		betaMins = []
		betaMaxs = []
		for p in self.params.getAll():
			if not p.locked:
				betaNames.append(p.name)
				beta0.append(p.value)
				betaMins.append(p.min)
				betaMaxs.append(p.max)
		if method == "lm":
			bounds = bounds=(-np.inf, np.inf)
		else:
			bounds = (betaMins, betaMaxs)
		idx_iter = [0]
		def get_fit(beta0):
			kwargs = {}
			for p in params.getAll():
				if p.name in betaNames:
					kwargs[p.name] = beta0[betaNames.index(p.name)]
				else:
					kwargs[p.name] = p.value
			if profileType == "gauss":
				profile = self.getGauss(x=x.copy(), **kwargs)[1]
			if profileType == "gauss2f":
				profile = self.getGauss2f(x=x.copy(), **kwargs)[1]
			elif profileType == "lorentzian":
				profile = self.getLorentzian(x=x.copy(), **kwargs)[1]
			elif profileType == "lorentzian2f":
				profile = self.getLorentzian2f(x=x.copy(), **kwargs)[1]
			elif profileType in (
				"voigt", "lorentzian2f", "voigt2f",
				"galatry2f", "sdvoigt2f", "sdgalatry2f"):
				profile = self.getDore(x=x.copy(), profileType=profileType, **kwargs)[1]
			if "a0" in betaNames:
				polynom[0] = beta0[betaNames.index("a0")]
			if "a1" in betaNames:
				polynom[1] = beta0[betaNames.index("a1")]
			if "a2" in betaNames:
				polynom[2] = beta0[betaNames.index("a2")]
			if "a3" in betaNames:
				polynom[3] = beta0[betaNames.index("a3")]
			profile += polynom[0] + polynom[1]*x + polynom[2]*x**2 + polynom[3]*x**3
			return profile
		def get_res(beta0, idx_iter=None):
			if idx_iter is not None:
				idx_iter[0] += 1
				print("%g.." % idx_iter[0], end=' ')
			profile = get_fit(beta0)
			return (profile-new_y)
		if isinstance(f_scale, float) and not method == "lm":
			loss = "soft_l1"
		else:
			loss = "linear"
		print("running the fit...", end=' ')
		result = optimize.least_squares(
			get_res, beta0, bounds=bounds, args=(idx_iter,),
			method=method, x_scale='jac', loss=loss, f_scale=f_scale)
		### process and return the results
		print("fit finished\n")
		fit_y = get_fit(result.x)
		res_y = -get_res(result.x)
		# estimate uncertainties
		def uncFromCov(coeffs=None,
			cov=None, hess=None, jac=None,
			res=None, scale=1):
			try:
				if coeffs is None:
					raise SyntaxError("you must provide the coefficients themselves (array-like)")
				coeffs = np.asarray(coeffs)
				if cov is None:
					if hess is None:
						if jac is None:
							raise SyntaxError("you must provide the coefficients themselves (array-like)")
						else:
							print("using the jacobian to determine the covariance")
							if coeffs.shape[0] == np.asarray(jac).shape[0]:
								np.transpose(np.asarray(jac))
							elif coeffs.shape[0] == np.asarray(jac).shape[1]:
								pass
							else:
								raise SyntaxError("neither dimension of the jacobian matches that of the coefficients!")
						hess = np.dot(np.transpose(np.asarray(jac)), np.asarray(jac))
					else:
						print("using the hessian to determine the covariance")
					cov = np.linalg.inv(hess)
					#print("H^-1 is: %s" % cov)
				if res is None:
					print("WARNING: you did not supply any residuals, therefore the uncertainties are unscaled!")
					res = np.ones(len(coeffs)+1)
				unc = []
				for i in range(len(coeffs)):
					u = cov[i][i]
					u *= scale/float((len(res)-len(coeffs)))
					u = sqrt(u)
					u *= 1.96
					unc.append(u)
				unc = np.asarray(unc)
			except (ValueError, np.linalg.LinAlgError) as e:
				print("WARNING! uncertainties could not be determined because of a numerical error: %s" % e)
				unc = []
				for i in range(len(coeffs)):
					unc.append(np.nan)
				unc = np.asarray(unc)
			return unc
		norm_factor = 1/float(abs(params.getByName("intensity").value))
		unc = uncFromCov(coeffs=result.x, jac=result.jac,
			res=res_y, scale=1/norm_factor)
		paramsOut = {}
		for p in self.params.getAll():
			pOut = {}
			pOut["min"] = p.min
			pOut["max"] = p.max
			if p.name in betaNames:
				pOut["value"] = result.x[betaNames.index(p.name)]
				pOut["unc"] = unc[betaNames.index(p.name)]
			else:
				pOut["value"] = p.value
				pOut["unc"] = 0.0
			paramsOut[p.name] = pOut
		test = np.zeros(len(x))
		results = {
			"test" : test,
			"output" : result,
			"x"   : x,
			"dataOrig" : dataOrig,
			"fit" : fit_y,
			"res" : res_y,
			"params": paramsOut}
		return results
	
	def runmultifit(self,
		spec=None, x=None, y=None,
		params=None, useMultiParams=False, profileType=None,
		center=None, frequencies=None, intensities=None,
		method="trf", f_scale=0.1):
		"""
		Runs a multi-line fit. This basically bahves the same as runfit()
		except with the following differences:
		- params MUST be a list of Parameters() sets, instead of the option
		of inputting a native list and then re-interpreting them as a single
		set of Parameters()
		- a new list as input is used for individual center frequencies,
		which is essentially looped over for constructing the global
		fit
		- lots of unused/excess code has been removed wrt runfit(), so one
		should really make sure you can run individual fits under similar
		conditions, before trying this routine
		"""
		if (frequencies is None) or (intensities is None):
			raise SyntaxError("you did not supply a list of frequencies/intensities")
		if center is None:
			center = float(np.mean(frequencies))
		### initialize new arrays
		dataOrig = {"x":[], "y":[]}
		if spec:
			idx_radius = 150
			if self.width is not None:
				self.step = float(np.abs(spec.x[0] - spec.x[1]))
				if self.step == 0:
					self.step = (max(spec.x)-min(spec.x))/len(spec.x)
				idx_radius = int(round(self.width/2.0/self.step))
			idx_cen = np.abs(spec.x).argmin()
			idx_low = idx_cen-idx_radius
			idx_hi = idx_cen+idx_radius
			dataOrig["x"] = spec.x[idx_low:idx_hi+1]
			dataOrig["y"] = spec.y[idx_low:idx_hi+1]
		elif x & y:
			dataOrig["x"] = x
			dataOrig["y"] = y
		x = dataOrig["x"].copy()
		new_y = dataOrig["y"].copy()
		fit_y = np.zeros_like(new_y)
		res_y = new_y - fit_y

		# run some sanity checks and possibly activate warnings
		# check for duplicate entries in x
		try:
			if not len(list(set(x))) == len(x):
				UserWarning("the x axis appears to have duplicate values! this might cause unexpected problems")
		except:
			raise UserWarning("there was trouble testing for duplicate entries in the x axis")
		# check that length of x is close to original
		try:
			if not len(x):
				UserWarning("the length of the dummy x axis was not close to the original!")
		except:
			raise UserWarning("there was trouble comparing the length of the x axis")

		### process parameters & run fit
		polynom = [0.0, 0.0, 0.0, 0.0]
		beta0 = []
		betaNames = []
		betaMins = []
		betaMaxs = []
		# build list of beta-coefficients, which are a full set of parameters + individual centers/intensities
		for p in self.params.getAll():
			if p.locked:
				continue
			elif p.name == "center":
				for i in range(len(frequencies)):
					betaNames.append("%s_%s" % (p.name, i))
					c = frequencies[i]-center
					lb = p.min + c - p.value
					ub = p.max + c - p.value
					beta0.append(c)
					betaMins.append(lb)
					betaMaxs.append(ub)
			elif p.name == "intensity":
				for i in range(len(frequencies)):
					betaNames.append("%s_%s" % (p.name, i))
					beta0.append(intensities[i])
					betaMins.append(p.min)
					betaMaxs.append(p.max)
			elif useMultiParams and (p.name in self.splittableParams):
				for i in range(len(frequencies)):
					betaNames.append("%s_%s" % (p.name, i))
					beta0.append(p.value)
					betaMins.append(p.min)
					betaMaxs.append(p.max)
			else:
				betaNames.append(p.name)
				beta0.append(p.value)
				betaMins.append(p.min)
				betaMaxs.append(p.max)
		if method == "lm":
			bounds = bounds=(-np.inf, np.inf)
		else:
			bounds = (betaMins, betaMaxs)
		idx_iter = [0]
		def get_fit(beta0):
			# define polynomial first
			if "a0" in betaNames:
				polynom[0] = beta0[betaNames.index("a0")]
			if "a1" in betaNames:
				polynom[1] = beta0[betaNames.index("a1")]
			if "a2" in betaNames:
				polynom[2] = beta0[betaNames.index("a2")]
			if "a3" in betaNames:
				polynom[3] = beta0[betaNames.index("a3")]
			profile = polynom[0] + polynom[1]*x + polynom[2]*x**2 + polynom[3]*x**3
			# loop through frequencies, setting specific parameters when appropriate
			for i in range(len(frequencies)):
				kwargs = {}
				for p in params.getAll():
					if p.name in [n.split("_")[0] for n in betaNames]:
						name = p.name
						if (p.name in ["center","intensity"] or
							(useMultiParams and p.name in self.splittableParams)):
							name = "%s_%s" % (name, i)
						kwargs[p.name] = beta0[betaNames.index(name)]
					else:
						kwargs[p.name] = p.value
				if profileType == "gauss":
					profile += self.getGauss(x=x.copy(), **kwargs)[1]
				if profileType == "gauss2f":
					profile += self.getGauss2f(x=x.copy(), **kwargs)[1]
				elif profileType == "lorentzian":
					profile += self.getLorentzian(x=x.copy(), **kwargs)[1]
				elif profileType == "lorentzian2f":
					profile += self.getLorentzian2f(x=x.copy(), **kwargs)[1]
				elif profileType in (
					"voigt", "voigt2f", "sdvoigt2f",
					"galatry2f", "sdgalatry2f"):
					profile += self.getDore(x=x.copy(), profileType=profileType, **kwargs)[1]
			return profile
		def get_res(beta0, idx_iter=None):
			if idx_iter is not None:
				idx_iter[0] += 1
				print("%g.." % idx_iter[0], end=' ')
			profile = get_fit(beta0)
			return (profile-new_y)
		if isinstance(f_scale, float) and not method == "lm":
			loss = "soft_l1"
		else:
			loss = "linear"
		print("running the fit...", end=' ')
		result = optimize.least_squares(
			get_res, beta0, bounds=bounds, args=(idx_iter,),
			method=method, x_scale='jac', loss=loss, f_scale=f_scale)
		### process and return the results
		print("fit finished\n")
		fit_y = get_fit(result.x)
		res_y = -get_res(result.x)
		# estimate uncertainties
		def uncFromCov(coeffs=None,
			cov=None, hess=None, jac=None,
			res=None, scale=1):
			try:
				if coeffs is None:
					raise SyntaxError("you must provide the coefficients themselves (array-like)")
				coeffs = np.asarray(coeffs)
				if cov is None:
					if hess is None:
						if jac is None:
							raise SyntaxError("you must provide the coefficients themselves (array-like)")
						else:
							print("using the jacobian to determine the covariance")
							if coeffs.shape[0] == np.asarray(jac).shape[0]:
								np.transpose(np.asarray(jac))
							elif coeffs.shape[0] == np.asarray(jac).shape[1]:
								pass
							else:
								raise SyntaxError("neither dimension of the jacobian matches that of the coefficients!")
						hess = np.dot(np.transpose(np.asarray(jac)), np.asarray(jac))
					else:
						print("using the hessian to determine the covariance")
					cov = np.linalg.inv(hess)
					#print("H^-1 is: %s" % cov)
				if res is None:
					print("WARNING: you did not supply any residuals, therefore the uncertainties are unscaled!")
					res = np.ones(len(coeffs)+1)
				unc = []
				for i in range(len(coeffs)):
					u = cov[i][i]
					u *= scale/float((len(res)-len(coeffs)))
					u = sqrt(u)
					u *= 1.96
					unc.append(u)
				unc = np.asarray(unc)
			except (ValueError, np.linalg.LinAlgError) as e:
				print("WARNING! uncertainties could not be determined because of a numerical error: %s" % e)
				unc = []
				for i in range(len(coeffs)):
					unc.append(np.nan)
				unc = np.asarray(unc)
			return unc
		norm_factor = 1/float(abs(params.getByName("intensity").value))
		unc = uncFromCov(coeffs=result.x, jac=result.jac,
			res=res_y, scale=1/norm_factor)
		paramsOut = {}
		for p in self.params.getAll():
			pOut = {}
			pOut["min"] = p.min
			pOut["max"] = p.max
			if p.locked:
				pOut["value"] = p.value
				pOut["unc"] = 0.0
			elif (p.name in ["center","intensity"]
				or (useMultiParams and p.name in self.splittableParams)):
				continue
			elif p.name in betaNames:
				pOut["value"] = result.x[betaNames.index(p.name)]
				pOut["unc"] = unc[betaNames.index(p.name)]
			paramsOut[p.name] = pOut
		for ib,b in enumerate(betaNames):
			if not "_" in b:
				continue
			pOut = {}
			if b.split("_")[0] == "center":
				pOut["value"] = result.x[ib]
				pOut["unc"] = unc[ib]
				pOut["min"] = params.getByName("center").min + pOut["value"]
				pOut["max"] = params.getByName("center").max + pOut["value"]
			else:
				pOut["value"] = result.x[ib]
				pOut["unc"] = unc[ib]
				pOut["min"] = params.getByName("%s" % b.split("_")[0]).min
				pOut["max"] = params.getByName("%s" % b.split("_")[0]).max
			paramsOut[b] = pOut
		test = np.zeros(len(x))
		results = {
			"test" : test,
			"output" : result,
			"x"   : x,
			"dataOrig" : dataOrig,
			"fit" : fit_y,
			"res" : res_y,
			"params": paramsOut}
		return results


def fit(function, parameters, y, x=None, output = 'raw'):
    """
    Fits x,y data points to the function using parameters.

    :param function: Function which is used in the fit
    :type function: method
    :param parameters: list of parameters
    :type parameters: list of type Parameter
    :param y: y-datapoints
    :type y: list of float
    :param x: x-datapoints
    :type x: list of float
    :param output: Controls wether only the output is return as retrieved from
                   the optimize-package (raw) or only the parameters including
                   errrors (param) are returned.
    :type output: str
    :returns: fit result from leastsq
    """
    def f(params):
        i = 0
        for p in parameters:
            if p.locked == False:
                p.set(params[i])
                i += 1
        return y - function(x)

    if x is None:
        y = np.array(y)
        x = np.arange(y.shape[0])
    p = [param() for param in parameters if param.locked == False]

    res= optimize.leastsq(f, p, full_output = True)

    if output == 'raw':
        return res

    pfinal = res[0]
    covar = res[1]
    info = res[2]
    mesg = res[3]
    success = res[4]

    if (len(y) > len(p)) and covar is not None:
        s_sq = (f(pfinal)**2.0).sum() / float(len(y) - len(p))
        covar = covar * s_sq
    else:
        covar = np.inf
    err = []
    for i in range(len(pfinal)):
        try:
            err.append(np.sqrt(np.absolute(covar[i][i])))
        except:
            err.append(0.00)
    
    return pfinal, err
    ## calculate final chi square
    #chisq=sum(info["fvec"]*info["fvec"])
    #
    #for i in range(len(p)):
    #    para = self.H.parameter.adj_parameter[i]
    #    try:
    #        try:
    #            err = np.sqrt(covar[i,i])*np.sqrt(chisq/dof)
    #        except:
    #            err = 9999999.999
    #        try:
    #            relerr = np.sqrt(covar[i,i]) \
    #                    np.sqrt(chisq/self.dof) / para['value']
    #        except:
    #            relerr = 999999.999
    #    except:
    #        err = 9999999.999
    #        relerr = 999999.999

    return res
    #return pout, success

#-----------------------------------------------------
# Functions
#-----------------------------------------------------

# Defines a linear function f = ax + b
linear = lambda x, a, b: a * x + b

# Defines the gaussian function to be used in the fit routine
gaussian = lambda x, f, i, fwhm: i * \
    np.exp(-(f - x) ** 2.0 / (0.36067376022224085 * fwhm * fwhm))

gaussian_true = lambda x, f, i, fwhm: i/(fwhm*math.sqrt(2*math.pi)) * np.exp(-(f-x)**2.0 / (2*fwhm**2.0))

# Defines a 2f gaussian
gaussian2f_true = lambda x, f, i, fwhm: gaussian_true(x,f,i,fwhm) * (fwhm**2.0 - (f-x)**2.0) / (fwhm**4.0)

# Defines a pure analytic Lorenztian
lorentzian = lambda x, f, i, fwhm: i * (fwhm/2)**2 / ((fwhm/2)**2 + (f-x)**2)

def gauss_func(B, x):
	'''
	Returns the gaussian function for:
	B = [x0, stdev, max, y-offset]
	'''
	return B[2] / (B[1] * math.sqrt(2*math.pi)) * np.exp( -((x-B[0])**2 / (2*B[1]**2)) )

def gauss2f_func(B, x):
	'''
	Returns the 2f-gaussian function for:
	B = [x0, stdev, max, y-offset]
	'''
	return gauss_func(B,x) * ((B[1]**2)-(x-B[0])**2) / B[1]**4

def chirp_freq(t, span = 5.0e9, pulseWidth = 0.240e-6, start_freq = -2500.0e6):
    return start_freq + span / pulseWidth * t

def chirp_fid_func(x, 
                   A, 
                   gamma, 
                   dx, 
                   transitions = None,
                   pulseWidth = 0.240e-6,
                   chirpType = 'increasing',
                   phase = 0.0,
                   span = 5000.0,
                   offset = 0.0,
                   lo = 22000.0,
                   fstart = -2500.0
                  ):
    print(A)
    # use the same amplitude factor for all transitions
    if type(A) == float:
        A = [A]

    if type(dx) == float:
        dx = [dx]
 
    num_components = len(np.unique(np.array([i[2] for i in transitions]))) 

    if num_components != len(A):
#        print("Number of components %d does not match number of amplitude ratios %d"\
#              % (num_components, len(A)))

        # use the same value for all components
        if len(A) == 1:
            A = [A[0] for i in range(num_components)]
        else:
            return

    if num_components != len(dx):
#        print("Number of components %d does not match number of offset params %d"\
#              % (num_components, len(dx)))

        # use the same value for all components
        if len(dx) == 1:
#            print("Use same value for all components")
            dx = [dx[0] for i in range(num_components)]
        else:
            return

    y = 0.0
    for i in range(len(transitions)):
        # Time at which chirped pulse hits resonance of a transition
        t_i = (transitions[i][0] - lo - fstart) / span * pulseWidth
        # phase at that time
        phase_at_t_i = 2.0 * np.pi * quad(chirp_freq, 
                                          0.0, 
                                          t_i, 
                                          args =  (span*1.0e6, pulseWidth, fstart * 1.0e6)
                                         )[0]
        y += A[transitions[i][2]] * np.power(10, transitions[i][1]) * \
                np.exp(-np.abs(gamma) * (x + dx[transitions[i][2]])) * \
                np.cos(phase_at_t_i + 2.0 * np.pi * (transitions[i][0] - lo) * 1.0e6 \
                       * (x + dx[transitions[i][2]] - t_i))
#        y += A[transitions[i][2]] * np.power(10, transitions[i][1]) * \
#                np.exp(-np.abs(gamma) * (x + dx[0])) * \
#                np.cos(phase_at_t_i + 2.0 * np.pi * (transitions[i][0] - lo) * 1.0e6 \
#                       * (x + dx[0] - t_i))

    return y

#-----------------------------------------------------
# Standard fits
#-----------------------------------------------------

def fit_linear(y, x = None, init_a = 1.0, init_b = 1.0, output = 'raw'):
    """
    Fits x,y data points to a linear.

    :param y: y-datapoints
    :type y: list of float
    :param x: x-datapoints
    :type x: list of float
    :param init_a: Initial parameter for gradient
    :type init_a: float
    :param init_b: Initial parameter for offset
    :type init_b: float
    :param output: Controls wether only the output is return as retrieved from
                   the optimize-package (raw) or only the parameters including
                   errrors (param) are returned. 
    :type output: str
    :returns: fit result from leastsq
    """
    a = Parameter(value = init_a, locked = False)
    b = Parameter(value = init_b, locked = False)
    func = lambda x: linear(x, a(), b())
    return fit(func, [a, b], y, x, output = output)




