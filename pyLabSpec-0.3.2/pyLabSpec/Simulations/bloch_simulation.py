#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module provides a class for running bloch simulations.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import sys

import numpy as np
from scipy.integrate import odeint
from scipy.linalg import expm
import matplotlib.pyplot as plt

hbar = 1.054571726e-34
debye = 3.33564095198152e-30
c = 299792458.0

if sys.version_info[0] == 3:
    xrange = range

solver_parameters = {'abserr':1.0e-8, 'relerr':1.0e-6, 'stoptime': 100.0e-6, 'numpoints': 10000}

def convert_fwhm2rate(fwhm):
    # fwhm = 1.0/2 pi T1 = k / 2 pi
    return fwhm * 2.0 * np.pi
def convert_hwhm2rate(hwhm):
    return hwhm * np.pi
def convert_rate2hwhm(rate):
    return rate/np.pi
def convert_rate2fwhm(rate):
    return rate/(2.0 * np.pi)

class bloch_vector():
    def __init__(self, u = 0.0, v = 0.0, w = 1.0):
       self.u = u
       self.v = v
       self.w = w

class environment():
    def __init__(self, T1, T2, mu, fieldstrength, delta_w):
       """
       Defines an environment for the evolution (E-field, frequency, ...)

       :param T1: T1 in s
       :type T1: float
       :param T2: T2 in s
       :type T2: float
       :param mu: Transition dipole moment in D
       :type mu: float
       :param fieldstrength: Electric field in V/m
       :type fieldstrength: float
       :param delta_w: frequency offset (from resonance) in Hz
       :param type: float
       """ 
       self.set_xab(mu, fieldstrength)
       self.set_decay_rates(T1, T2)
       self.delta_w = delta_w

    def set_decay_rates(self, T1, T2):
       self.T1 = T1
       self.T2 = T2
       self.gamma = 1.0 / T2
       self.zeta = 1.0 / T1

    def set_xab(self, mu, fieldstrength):
       self.mu = mu
       self.fieldstrength = fieldstrength
       self.kappa = mu * (debye / hbar)
       self.xab = self.kappa * self.fieldstrength

class density_matrix():
    """
    Defines a densitiy matrix and methods for its transformation.
    """
    def __init__(self, s, u, v, w):

       self.s = s
       self.u = u
       self.v = v
       self.w = w

       self.init_density_matrix()
 
    def init_density_matrix(self):
       self.rho_kk = 0.5 * (self.s + self.w)
       self.rho_ll = 0.5 * (self.s - self.w)
       self.rho_kl = 0.5 * (self.u + 1.0j * self.v)
       self.rho_lk = 0.5 * (self.u - 1.0j * self.v)

       self.rho = np.matrix([[self.rho_kk, self.rho_kl],[self.rho_lk, self.rho_ll]])

    def rotate2rotframe(self, Ea, Eb, t, theta):
       w0_kl = (Ea - Eb) / hbar
       k_kl = w0_kl / c

       smatrix = Smatrix(Ea, w0_kl, theta = theta, t = t)

       return expm( -1.0j * smatrix) * self.rho * expm( 1.0j * smatrix)

    def rotate2labframe(self, Ea, Eb, t, theta):
       w0_kl = (Ea - Eb) / hbar
       k_kl = w0_kl / c

       smatrix = Smatrix(Ea, w0_kl, theta = theta, t = t)

       return expm(np.array( 1.0j * smatrix)) * self.rho * expm(np.array( -1.0j * smatrix))



def Smatrix(Ea, w_ab, theta = 0.0, t = 0.0, y = 0.0):

    return np.matrix([[Ea/hbar, 0.0],[0.0, Ea * t / hbar + w_ab * t + theta - w_ab * y / c]])


def bloch_derivative(theta, t, p):

    #u, v, w = theta
    xab_on, delta_w, gamma, zeta, w0, tau1, tau2, alpha, delta_w_start = p
    # switch off power after first pulse
    if tau1 and t > tau1:
       xab = 0.0
    else:
       xab = xab_on

    if tau2 and t > tau2:
       xab = xab_on

    l = np.matrix([[ -gamma, -delta_w, 0.0], [delta_w, -gamma, -xab], [0.0, xab, -zeta]])
    f = np.array( np.dot(l,theta) + [0.0, 0.0, zeta * w0] )[0]

    return f

def delta_wab(alpha, delta_w_start, t):
    """
    Returns the frequency offset of the actual frequency of the chirp at time t

    :param alpha: sweep speed in Hz / s
    :type alpha: float
    :param delta_w_start: frequency offset at time 0 s
    :type delta_w_start: float
    :param t: time at which offset will be determined
    :type t: float
    """
    return (alpha * t + delta_w_start)


def bloch_derivative_chirp(theta, t, p):
    """
    Calculate derivative of the Bloch vector for a chirped pulse

    :param theta: Bloch vector
    :type theta: vector
    :param t: time
    :type t: float
    :param p: parameters 
    :type p: list

    Returns d theta / dt
    """

    #u, v, w = theta
    xab_on, delta_w, gamma, zeta, w0, tau1, tau2, alpha, delta_w_start = p
    # switch off power after first pulse
    if tau1 and t > tau1:
       xab = 0.0
       delta_w = delta_wab(alpha, delta_w_start, tau1) #0.0
    else:
       xab = xab_on
       delta_w = delta_wab(alpha, delta_w_start, t)

    delta_w = delta_w * 2.0 * np.pi

    if tau2 and t > tau2:
       xab = xab_on
    l = np.matrix([[ -gamma, -delta_w, 0.0], [delta_w, -gamma, -xab], [0.0, xab, -zeta]])
    f = np.array( np.dot(l,theta) + [0.0, 0.0, zeta * w0] )[0]

    return f


def solve_bloch_equations(bloch_vector, 
                          environment, 
                          w0, 
                          t = None, 
                          tau1 = None,
                          tau2 = None, 
                          solver_parameters = solver_parameters, 
                          pulse_type = 'resonant'
                         ):
    """
    :param bloch_vector: inital Bloch vector at time t=0
    :param environment: Object that contains parameters defining the environment
    :param t: List of times
    :param tau1: Start time of the pulse
    :param tau2: Stop time of the pulse
    :param solver_parameters: Parameters that control the solver
    :param pulse_type: Defines what type of pulse is calculated ('resonant', 'chirp')
    """    
    # Parameters
#    T1 = 50.0 # time constant for population decay (in microseconds)
#    T2 = 5.0    # time constant for loss of coherence (in microseconds)
#    mu = 1.4 # transition dipole moment in debey
#    kappa = mu * (debye / hbar) 
#    fieldstrength = 0.0002 # field strength in V/m
#    xab = kappa * fieldstrength  # 
#    delta_w = 0.0 # frequency offset
#    gamma = 1.0 / T2 
#    zeta = 1.0 / T1

    # Initial condition
    
#    u = 0.0
#    v = 0.0
#    w = 0.2 # normalized population difference (delta N / N)

    # ODE solver parameters
#    abserr = 1.0e-8
#    relerr = 1.0e-6
#    stoptime = 100.0
#    numpoints = 10000

    # Create the time samples for the output of the ODE solver.
    # I use a large number of points, only because I want to make
    # a plot of the solution that looks nice.
    if not t:
        t = [solver_parameters['stoptime'] * float(i) / (solver_parameters['numpoints'] - 1) for i in range(solver_parameters['numpoints'])]
    # pack parameters and initial conditions
    p = [environment.xab, environment.delta_w, environment.gamma,
         environment.zeta, w0, tau1, tau2, environment.alpha,
         environment.delta_w_start]
    theta0 = [bloch_vector.u, bloch_vector.v, bloch_vector.w]

    # Call the solver
    if pulse_type == 'resonant':
        wsol = odeint(bloch_derivative, theta0, t, args=(p,), atol = solver_parameters['abserr'], rtol = solver_parameters['relerr'])
    elif pulse_type == 'chirp':
        wsol = odeint(bloch_derivative_chirp, theta0, t, args=(p,), atol = solver_parameters['abserr'], rtol = solver_parameters['relerr'])
    else:
        print("Wrong Pulse-Type! Possible values are 'resonant', 'chirp'")
 
    return t, wsol



def plot_simulation(t, wsol, freq = 23.870e9, phase = 0.0):

    u = []
    v = []
    w = []
    p = []

#    t, wsol = solve_bloch_equations()
    for i in xrange(len(t)):
       data = wsol[i]
       u.append(data[0])
       v.append(data[1])
       w.append(data[2])
       p.append(calc_polarization(wsol[i], t[i], freq, phase))
    
    fig = plt.figure()
    ax = fig.add_subplot(111)

    ax.plot(t,p )
    ax.plot(t,u)
    ax.plot(t,v)
    ax.plot(t,w)
    plt.show()
   
def simulate_pulse_probe(bv, en, w0, t_pulse1, t_delay, t_pulse2):
    """
    Simulates a pump probe experiment with two defined pulses (radiation on) separated by a delay (radiation off).

    :param bv: Bloch vector (u, v, w)
    :type bv: bloch_vector
    :param en: Environment (radiation on)
    :type en: environment
    :param w0: population difference in thermal equilibrium
    :type w0: float
    :param t_pulse1: length of the first pulse in microseconds
    :type t_pulse1: float
    :param t_delay: delay between pulses in microseconds
    :type t_delay: float
    :param t_pulse2: length of the second pulse in microseconds
    :type t_pulse2: float
    :rtype: 2-dim tuple (t, array(u,v,w)) which contains the time and u,v,w
    """

    # Define radiation off environment
    en_off = environment(en.T1, en.T2, en.mu, 0.0, en.delta_w)
    # Generate time list
    solver_parameters['stoptime'] = t_pulse1 + t_delay + t_pulse2
    t = [solver_parameters['stoptime'] * float(i) / (solver_parameters['numpoints'] - 1) for i in range(solver_parameters['numpoints'])]

    # Calculate first pulse
    t1 = [time for time in t if time <= t_pulse1]
    t1, w1 = solve_bloch_equations(bv, en, w0, t = t1)
    bv1 = bloch_vector(w1[-1][0], w1[-1][1], w1[-1][2])

    # Calculate delay 
    t2 = [time for time in t if t_pulse1 < time <= t_pulse1 + t_delay]
    t2, w2 = solve_bloch_equations(bv1, en_off, w0, t = t2)
    bv2 = bloch_vector(w2[-1][0], w2[-1][1], w2[-1][2])

    # Calculate second pulse
    t3 = [time for time in t if t_pulse1 + t_delay < time ]
    t3, w3 = solve_bloch_equations(bv2, en, w0, t = t3)
   
    return t1 + t2 + t3, np.concatenate((w1, w2, w3))


def simulate_delay_dependence(bv, en, w0, t_pulse1, t_pulse2, t_delay_max):

   num_points = 1000
   step = t_delay_max / 1000.0

   t = []
   w = []
   
   for i in xrange(num_points):
      st, sw = simulate_pulse_probe(bv, en, w0, t_pulse1, i * step, t_pulse2)
      t.append(i * step)
      w.append(sw[-1])

   return t,w


def simulate_chirp_pulse():
    """
    """

    


def calc_polarization(bloch_vector, t, freq, phase = 0.0):
    """
    Calculates the polarization based on a single tone (rotating frame with constant frequency)
    """
    current_phase = 2.0 * np.pi * freq * t + phase
    return bloch_vector[0] * np.cos( current_phase) - bloch_vector[1] * np.sin( current_phase)


def calc_polarization_chirp(bv, t, pulse_length, freq0, alpha, phase0 = 0.0):
    """
    Calculates the polarization based on a chirped pulse (rotating frame with
    chirped frequency).

    :param bloch_vector: Bloch vector at time t
    :type bloch_vector: object
    :param t: time in s at which the polarization is calculated
    :type t: float
    :param pulse_length: length of the chirped pulse (tau) in s
    :type pulse_length: float
    :param freq0: initial frequency of the chirped pulse
    :type freq0: float
    :param alpha: sweep speed d freq / dt
    :type alpha: float
    :param phase0: initial phase of the chirped pulse
    :type phase0: float
    """
    if t>pulse_length:
        tt = pulse_length
    else:
        tt = t
    current_phase = 2.0 * np.pi * (freq0 + alpha *tt) * t \
            + phase0 - np.pi * alpha * np.power(tt,2)
    try:
        return bv.u * np.cos( current_phase) + bv.v * np.sin( current_phase)
    except:
        return bv[0] * np.cos( current_phase) + bv[1] * np.sin( current_phase)
 


def save_simulation(t, w, filename, freq = 23.870e9, phase = 0.0):
    """
    """
    f = open(filename, 'w')
    for i in xrange(len(t)):
        p = calc_polarization(w[i], t[i], freq, phase)
        f.write("%12.6g %12.6g %12.6g %12.6g %12.6g \n" % (t[i], w[i][0], w[i][1], w[i][2], p))
    f.close()

