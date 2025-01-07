#!/usr/bin/env python
# -*- coding: utf8 -*-
#
# TODO
# - (647C) figure out *correct* coding of the status string
#
"""
This module provides a class for communicating with a variety of mass
flow controller boxes.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import sys
import os
import re
import math
import time
# third-party
import serial
from serial.serialposix import portNotOpenError
import numpy as np
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from . import instrument as instr




class MassFlowController(instr.InstSocket):
    """
    Provides a general socket for a mass flow controller.
    """
    
    # Ref: Except where noted otherwise, table is copied from MKS 946 user manual
    # note1: Cp in units (Cal/g K); Density in units (g/L @ STP == 25°C and 760 torr)
    # note1: CF refers to the correction/scaling factor for thermal-based MFCs
    #        and are relative to N2 (i.e. for determining absolute flow rates
    #        of gases through MFCs that were calibrated using nitrogen), and are
    #        theoretical.. there may be non-linear deviations at some temperatures/pressures
    # note2: from the MKS 247D user manual, the correction factor can be calculated as,
    #                      CFx = 0.3106 * s / (d_x * cp_x),
    #        where,
    #                0.3106 is the scaling factor from N2,
    #                s is a scaling for structure, and is:
    #                      1.030 for monatomics
    #                      1.000 for diatomics
    #                      0.941 for triatomics
    #                      0.880 for polyatomics,
    #                d_x is the density of the gas at STP in units (g/L = kg/m^3)
    #                cp_x is the specific heat capacity of the gas in units (cal/g °C = kcal/kg K = Btu/lb °F)
    # note3: if one can only find molar heat capacity, take that value and divide by its molar mass, e.g.:
    #                CO has Cp = 29.8 J/mol K (CRC Handbook of Chem. and Phys., 98th ed.)
    #                CO weighs 28 g/mol
    #                -> (29.8 J/mol K) / (28 g/mol) = 1.064 J/g K
    #                but this is J and not cal.. 1 J = 4.184 cal
    #                -> (1.064 J/g K) / (4.184 J/cal) = 0.254 cal/g K.. 2% difference from MKS' value of 0.2488
    gas_properties = {
        "Acetylene" : {"Symbol":"C2H2", "Cp":0.4032, "Density":1.161, "CF":0.58},
        "Air" : {"Symbol":"---", "Cp":0.24, "Density":1.293, "CF":1.00},
        "Ammonia" : {"Symbol":"NH3", "Cp":0.492, "Density":0.76, "CF":0.73},
        "Argon" : {"Symbol":"Ar", "Cp":0.1244, "Density":1.782, "CF":1.39},
        "Arsine" : {"Symbol":"AsH3", "Cp":0.1167, "Density":3.478, "CF":0.67},
        "Boron Trichloride" : {"Symbol":"BCl3", "Cp":0.1279, "Density":5.227, "CF":0.41},
        "Bromine" : {"Symbol":"Br2", "Cp":0.0539, "Density":7.13, "CF":0.81},
        "Carbon Dioxide" : {"Symbol":"CO2", "Cp":0.2016, "Density":1.964, "CF":0.70},
        "Carbon Monoxide" : {"Symbol":"CO", "Cp":0.2488, "Density":1.25, "CF":1.00},
        "Carbon Tetrachloride" : {"Symbol":"CCl4", "Cp":0.1655, "Density":6.86, "CF":0.31},
        "Carbon Tetrafluoride (Freon 14)" : {"Symbol":"CF4", "Cp":0.1654, "Density":3.926, "CF":0.42},
        "Carbonyl Sulfide" : {"Symbol":"OCS", "Cp":0.165, "Density":2.18, "CF":0.812}, # Cp/density from HBCP; CF calc'd
        "Chlorine" : {"Symbol":"Cl2", "Cp":0.1144, "Density":3.163, "CF":0.86},
        "Chlorodifluoromethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.46},
        "Chloropentafluoroethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.24},
        "Chlorotrifluoromethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.38},
        "Cyanogen" : {"Symbol":"C2N2", "Cp":"", "Density":"", "CF":0.61},
        "Deuterium" : {"Symbol":"D2", "Cp":1.722, "Density":0.1799, "CF":1.00},
        "Diborane" : {"Symbol":"B2H6", "Cp":"", "Density":"", "CF":0.44},
        "Dibromodifluoromethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.19},
        "Dichlorodifluoromethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.35},
        "Dichlorofluoromethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.42},
        "Dichloromethylsilane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.25},
        "Dichlorosilane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.40},
        "1,2-Dichlorotetrafluoroethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.22},
        "1,1-Difluoroethylene" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.43},
        "2,2-Dimethylpropane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.22},
        "Ethane" : {"Symbol":"CH3CH3", "Cp":0.4097, "Density":1.342, "CF":0.50},
        "Fluorine" : {"Symbol":"F2", "Cp":"", "Density":"", "CF":0.98},
        "Fluoroform" : {"Symbol":"CHF3", "Cp":"", "Density":"", "CF":0.50},
        "Freon-11" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.33},
        "Freon-12" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.35},
        "Freon-13" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.38},
        "Freon-13 B1" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.37},
        "Freon-21" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.42},
        "Freon-22" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.46},
        "Freon-23" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.50},
        "Freon-113" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.20},
        "Freon-114" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.22},
        "Freon-115" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.24},
        "Freon-116" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.24},
        "Freon-C318" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.164},
        "Freon-1132A" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.43},
        "Helium" : {"Symbol":"He", "Cp":1.241, "Density":0.1786, "CF":1.45},
        "Hexafluoroethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.24},
        "Hydrogen" : {"Symbol":"H2", "Cp":3.419, "Density":0.0899, "CF":1.01},
        "Hydrogen Bromide" : {"Symbol":"HBr", "Cp":"", "Density":"", "CF":1.00},
        "Hydrogen Chloride" : {"Symbol":"HCl", "Cp":"", "Density":"", "CF":1.00},
        "Hydrogen Fluoride" : {"Symbol":"HF", "Cp":"", "Density":"", "CF":1.00},
        "Hydrogen Sulfide" : {"Symbol":"H2S", "Cp":0.24, "Density":1.5, "CF":0.81}, # Cp from HBCP; CF calc'd
        "Isobutylene" : {"Symbol":"CH2C(CH3)2", "Cp":0.3701, "Density":2.503, "CF":0.29},
        "Krypton" : {"Symbol":"Kr", "Cp":"", "Density":"", "CF":1.54},
        "Methane" : {"Symbol":"CH4", "Cp":0.5328, "Density":0.715, "CF":0.72},
        "Methyl Fluoride" : {"Symbol":"CH3F", "Cp":"", "Density":"", "CF":0.56},
        "Molybdenum Hexafluoride" : {"Symbol":"MoF6", "Cp":"", "Density":"", "CF":0.21},
        "Neon" : {"Symbol":"Ne", "Cp":0.246, "Density":0.9, "CF":1.46},
        "Nitric Oxide" : {"Symbol":"NO", "Cp":0.2328, "Density":1.339, "CF":0.99},
        "Nitrogen" : {"Symbol":"N2", "Cp":0.2485, "Density":1.25, "CF":1.00},
        "Nitrogen Dioxide" : {"Symbol":"NO2", "Cp":0.1933, "Density":2.052, "CF":0.71}, # CF from Omega
        "Nitrogen Trifluoride" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.48},
        "Nitrous Oxide" : {"Symbol":"N2O", "Cp":0.2088, "Density":1.964, "CF":0.71},
        "Octafluorocyclobutane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.164},
        "Oxygen" : {"Symbol":"O2", "Cp":0.2193, "Density":1.427, "CF":1.00},
        "Pentane" : {"Symbol":"C5H12 == CH3(CH2)3CH3", "Cp":0.398, "Density":3.219, "CF":0.21},
        "Perfluoropropane" : {"Symbol":"C3F8", "Cp":"", "Density":"", "CF":0.17},
        "Phosgene" : {"Symbol":"COCl2", "Cp":"", "Density":"", "CF":0.44},
        "Phosphine" : {"Symbol":"PH3", "Cp":"", "Density":"", "CF":0.76},
        "Propane" : {"Symbol":"C3H8 == CH3CH2CH3", "Cp":0.3885, "Density":1.967, "CF":0.36},
        "Propylene" : {"Symbol":"C3H6 == CH3C(H)=CH2", "Cp":0.3541, "Density":1.877, "CF":0.41},
        "Silane" : {"Symbol":"SiH4", "Cp":"", "Density":"", "CF":0.60},
        "Silicon Tetrachloride" : {"Symbol":"SiCl4", "Cp":"", "Density":"", "CF":0.28},
        "Silicon Tetrafluoride" : {"Symbol":"SiF4", "Cp":"", "Density":"", "CF":0.35},
        "Sulfur Dioxide" : {"Symbol":"SO2", "Cp":0.1488, "Density":2.858, "CF":0.69},
        "Sulfur Hexafluoride" : {"Symbol":"SF6", "Cp":0.1592, "Density":6.516, "CF":0.26},
        "Trichlorofluoromethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.33},
        "Trichlorosilane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.33},
        "1,1,2-Trichloro-1,2,2-Trifluoroethane" : {"Symbol":"", "Cp":"", "Density":"", "CF":0.20},
        "Tungsten Hexafluoride" : {"Symbol":"WF6", "Cp":"", "Density":"", "CF":0.25},
        "Xenon" : {"Symbol":"Xe", "Cp":0.0378, "Density":5.858, "CF":1.32}}
    
    def __init__(self, com="COM", **kwds):
        """
        Initializes the communication to the pressure readout/controller.
        
        :param com: the method of communication (e.g. "COM" or "TCPIP")
        :param port: (optional) the serial/ethernet port to use (e.g. '/dev/ttyS2' or 4001)
        :param baudrate: (optional) the baudrate of the communication
        :param parity: (optional) the type of parity checking to use
        :param bytesize: (optional) the number of data bits in each signal
        :param stopbits: (optional) the number of stop bits for each signal
        :param timeout: (optional) the timeout to wait before exiting the input buffer
        :param xonxoff: (optional) whether to use software flow control
        :param rtscts: (optional) whether to use hardware (RTS/CTS) flow control
        :type com: str
        :type port: str or int
        :type baudrate: int
        :type parity: int
        :type bytesize: int
        :type stopbits: int
        :type timeout: float
        :type xonxoff: bool
        :type rtscts: bool
        """
        self.socket = instr.InstSocket(com, **kwds)
        self.clear = self.socket.clear
        self.write = self.socket.write
        if not isinstance(self, MKS_946): # 946 queries are way too non-standard!!
            self.query = self.socket.query
        self.com = com
        self.clear()
        self.connected = True
    
    def to_bits(self, s):
        """
        Helper function for converting a string to a list of bits.
        
        :param s: an arbitrary string
        :type s: str
        :returns: a list of bits
        :rtype: list[ints]
        """
        result = []
        for c in s:
            bits = bin(ord(c))[2:]
            bits = '00000000'[len(bits):] + bits
            result.extend([int(b) for b in bits])
        return result
    def from_bits(self, bits):
        """
        Helper function for converting a list of bits to a string.
        
        :param bits: a list of bits
        :type bits: list[ints]
        :returns: the interpreted string
        :rtype: str
        """
        chars = []
        for b in range(len(bits) / 8):
            byte = bits[b*8:(b+1)*8]
            chars.append(chr(int(''.join([str(bit) for bit in byte]), 2)))
        return ''.join(chars)



class MKS_647C(MassFlowController):
    """
    Provides a more specific class for the MKS 647C unit.
    """
    
    pressure_units = [
        "1 mtorr", "10 mtorr", "100 mtorr", "1000 mtorr",
        "1 torr", "10 torr", "100 torr", "1000 torr",
        "1 ktorr", "10 ktorr", "100 ktorr",
        "1 μbar", "10 μbar", "100 μbar", "1000 μbar",
        "1 mbar", "10 mbar", "100 mbar", "1000 mbar",
        "1 bar", "10 bar", "100 bar",
        "1 Pa", "10 Pa", "100 Pa",
        "1 kPa", "10 kPa", "100 kPa", "1000 kPa",
        "2 mtorr", "5 mtorr", "20 mtorr", "50 mtorr",
        "200 mtorr", "500 mtorr", "2000 mtorr", "5000 mtorr",
        "2 torr", "5 torr", "20 torr", "50 torr",
        "200 torr", "500 torr", "2000 torr", "5000 torr",
        "2 ktorr", "5 ktorr", "20 ktorr", "50 ktorr",
        "2 μbar", "5 μbar", "20 μbar", "50 μbar",
        "200 μbar", "500 μbar", "2000 μbar", "5000 μbar",
        "2 mbar", "5 mbar", "20 mbar", "50 mbar",
        "200 mbar", "500 mbar", "2000 mbar", "5000 mbar",
        "2 bar", "5 bar", "20 bar", "50 bar",
        "2 Pa", "5 Pa", "20 Pa", "50 Pa", "200 Pa", "500 Pa",
        "2 kPa", "5 kPa", "20 kPa", "50 kPa",
        "200 kPa", "500 kPa", "2000 kPa", "5000 kPa",
        "1 MPa", "2 MPa", "5 MPa", "10 MPa"]
    
    range_units = [
        "1 SCCM", "2 SCCM", "5 SCCM", "10 SCCM", "20 SCCM",
        "50 SCCM", "100 SCCM", "200 SCCM", "500 SCCM",
        "1 SLM", "2 SLM", "5 SLM", "10 SLM", "20 SLM",
        "50 SLM", "100 SLM", "200 SLM", "400 SLM", "500 SLM",
        "1 SCMM",
        "1 SCFH", "2 SCFH", "5 SCFH", "10 SCFH", "20 SCFH",
        "50 SCFH", "100 SCFH", "200 SCFH", "500 SCFH",
        "1 SCFM", "2 SCFM", "5 SCFM", "10 SCFM", "20 SCFM",
        "50 SCFM", "100 SCFM", "200 SCFM", "500 SCFM",
        "30 SLM", "300 SLM"]
    
    known_gases = [
        "acetylene", "air", "ammonia", "argon", "arsine", "boron_trichloride",
        "bromine", "carbon_dioxide", "carbon_monoxide", "carbon_tetrachloride",
        "carbon_tetrachloride", "chlorine", "chlorodifluoromethane",
        "chloropentafluoroethane", "chlorotrifluoromethane", "cyanogen", "deuterium",
        "diborane", "dibromodifluoromethane", "dichlorodifluoromethane",
        "dichlorofluoromethane", "dichloromethylsilane", "dichlorosilane",
        "1,2-dichlorotetrafluoroethane", "1,1-difluoroethylene", "2,2-dimethylpropane",
        "ethane", "fluorine", "fluoroform", "freon-11", "freon-12", "freon-13",
        "freon-13_b1", "freon-14", "freon-21", "freon-22", "freon-23", "freon-113",
        "freon-114", "freon-115", "freon-116", "freon-c318", "freon-1132a", "helium",
        "hexafluoroethane", "hydrogen", "hydrogen_bromide", "hydrogen_chloride",
        "hydrogen_fluoride", "isobutylene", "krypton", "methane", "methyl_fluoride",
        "molybdenum_hexafluoride", "neon", "nitric_oxide", "nitrogen",
        "nitrogen_dioxide", "nitrogen_trifluoride", "nitrous_oxide",
        "octafluorocyclobutane", "oxygen", "pentane", "perfluoropropane",
        "phosgene", "phosphine", "propane", "propylene", "silane",
        "silicon_tetrachloride", "silicon_tetrafluoride", "sulfur_dioxide",
        "sulfur_hexafluoride", "trichlorofluoromethane", "trichlorosilane",
        "1,1,2-trichloro-1,2,2-trifluoroethane", "tungsten_hexafluoride", "xenon"]
    
    def __init__(
        self,
        com="COM",
        address="001",
        terminator="\r",
        **kwds):
        """
        See the documentation for the parent class about this.
        """
        super(self.__class__, self).__init__(com=com, **kwds)
        self.address = address
        self.terminator = terminator
        self.socket.queriesAlwaysUseQMark = False
        self.identify()
        if not self.identifier:
            self.socket.close()
            self.socket = None
            raise RuntimeError
        else:
            print("Connected:", self.identifier)
        
    
    def is_good_channel(self, channel):
        """
        Returns the identification string of the instrument.
        
        :param channel: a channel number
        :type channel: int
        :returns: whether the input channel was acceptable
        :rtype: bool
        """
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in list(range(0,9)):
            raise SyntaxError("The requested channel is not 1-8 (or sometimes 0=all): %s" % channel)
        else:
            return True
    
    def identify(self):
        """
        Returns the identification string of the instrument.
        
        :returns: the identification string: `MKS 647C Vx.x - mm dd yyyy`
        :rtype: str
        """
        self.identifier = self.query('ID', size=30)
        return self.identifier
    
    def reset_hardware(self):
        """
        Performs a hardware reset (like power up).
        """
        self.write('RE')
    def reset_default(self):
        """
        Performs a soft reset (all parameters to default).
        """
        self.write('DF')
    
    def get_status(self, channel=0):
        """
        Returns the current status of the channel.
        
        Note that the returned keys 'status' and 'bitarray' of the dictionary
        contain the direct response of the query and the list of bits,
        respectively.
        
        :param channel: (optional) the channel number
        :type channel: int
        :returns: a dictionary of the interpreted bitarray of the statuses
        :rtype: dict[str] -> str
        """
        if not self.is_good_channel(channel):
            return
        if not channel:
            raise SyntaxError("You must specify a channel for the status query: %s" % channel)
        status_dict = {
            "state":"OFF",
            "trip_low":"NO",
            "trip_high":"NO",
            "overflow_in":"NO",
            "underflow_in":"NO",
            "overflow_out":"NO",
            "underflow_out":"NO"}
        status = self.query('ST %s' % channel, size=7)
        #status_bitarray = self.to_bits(status)
        status_bitarray = list(status)
        try:
            if status_bitarray[0]: status_dict["state"]="ON"
            if status_bitarray[4]: status_dict["trip_low"]="YES"
            if status_bitarray[5]: status_dict["trip_high"]="YES"
            if status_bitarray[6]: status_dict["overflow_in"]="YES"
            if status_bitarray[7]: status_dict["underflow_in"]="YES"
            if status_bitarray[8]: status_dict["overflow_out"]="YES"
            if status_bitarray[9]: status_dict["underflow_out"]="YES"
        except IndexError:
            pass
        status_dict["bitarray"]=status_bitarray
        status_dict["string"]=status
        return status_dict
    
    def open_valve(self, channel=0):
        """
        Open the valve. If no channel is specified, all are opened.
        
        :param channel: (optional) the channel number
        :type channel: int
        """
        if not self.is_good_channel(channel):
            return
        self.write('ON %s' % channel)
    def close_valve(self, channel=0):
        """
        Close the valve. If no channel is specified, all are closed.
        
        :param channel: (optional) the channel number
        :type channel: int
        """
        if not self.is_good_channel(channel):
            return
        self.write('OF %s' % channel)
    
    def set_range_unit(self, channel, range_string):
        """
        Sets the unit's range based on the user-defined string.
        
        :param channel: the channel number
        :param range_string: the full scale range of the MFC (see self.range_units)
        :type channel: int
        :type range_string: str
        """
        if not self.is_good_channel(channel):
            return
        if not range_string in self.range_units:
            raise SyntaxError("The requested pressure unit is not known: %s" % range_string)
        range_index = self.range_units.index(range_string)
        self.write('RA %s %s' % (channel, range_index))
    def get_range_unit(self, channel):
        """
        Returns the unit's range.
        
        :param channel: the channel number
        :type channel: int
        :returns: the range for the MFC
        :rtype: str
        """
        if not self.is_good_channel(channel):
            return
        return self.range_units[int(self.query('RA %s R' % channel, size=2))]
    
    def set_setpoint(self, channel, setpoint):
        """
        Sets the set point of a channel, with respect to the full scale.
        
        :param channel: the channel number
        :param setpoint: the setpoint of the flow, in unit [%], up to 110%
        :type channel: int
        :type setpoint: float
        """
        if not self.is_good_channel(channel):
            return
        if not isinstance(setpoint, (int, float)):
            raise NotANumberError
        setpoint = int(np.rint(setpoint*10))
        if not setpoint in list(range(0,1100)):
            raise SyntaxError("The requested set point is not within limits of 0-110\%: %s" % setpoint)
        self.write('FS %s %s' % (channel, setpoint))
    def get_setpoint(self, channel):
        """
        Returns the setpoint of a channel.
        
        :param channel: the channel number
        :type channel: int
        :returns: the setpoint of the channel in unit [%]
        :rtype: float
        """
        if not self.is_good_channel(channel):
            return
        cmd = 'FS %s R' % channel
        pct = self.query(cmd)
        if (not pct) or pct[0]=="E":
            pct = 0
        pct = float(pct)/10
        return pct
    def get_actual_flow(self, channel):
        """
        Returns the actual flow of a channel.
        
        Note that the actual flow is scaled by the gas correction factor.
        
        :param channel: the channel number
        :type channel: int
        :returns: the actual flow of the channel in unit [%]
        :rtype: float
        """
        if not self.is_good_channel(channel):
            return
        response = self.query('FL %s' % (channel), size=7).lstrip('0')
        try:
            flow = float(response)/10
        except ValueError:
            flow = 0
        return flow
    
    def set_pressure_unit(self, pressure_string):
        """
        Sets the pressure unit based on the user-defined string.
        
        :param pressure_string: the pressure unit to use for main unit (see self.pressure_units)
        :type pressure_string: str
        """
        if not pressure_string in self.pressure_units:
            raise SyntaxError("The requested pressure unit is not known: %s" % pressure_string)
        pressure_index = self.pressure_units.index(pressure_string)
        self.write('PU %s' % pressure_index)
    def get_pressure_unit(self):
        """
        Returns the pressure unit.
        
        :returns: the pressure unit used in the main unit
        :rtype: str
        """
        return self.pressure_units[int(self.query('PU R', size=2))]
    
    def set_gas_menu(self, val):
        """
        Sets the gas menu.
        
        :param val: the gas menu
        :type val: int
        """
        if not isinstance(val, int):
            raise NotANumberError
        self.write('GM %s' % val)
    def get_gas_menu(self):
        """
        Returns the pressure unit.
        
        :returns: the active gas menu
        :rtype: int
        """
        return self.query('GM R', size=1)
    
    def set_correction_factor(self, channel, cf):
        """
        Sets the correction factor for the gas.
        
        :param channel: the channel number
        :param cf: the gas correction factor for the gas through that channel
        :type channel: int
        :type cf: float
        """
        if not self.is_good_channel(channel):
            return
        if not isinstance(cf, (int, float)):
            raise SyntaxError("The desired correction factor doesn't make sense: %s" % cf)
        cf = int(np.rint(cf*100))
        self.write('GC %s %s' % (channel, cf))
    def get_correction_factor(self, channel):
        """
        Reads the correction factor for the gas.
        
        :param channel: the channel number
        :type channel: int
        :returns: the active gas correction factor for that channel
        :rtype: float
        """
        return float(self.query('GC %s R' % channel))/100
    
    def set_trip_limit(self, channel, low, high):
        """
        Sets the trip limits for the channel.
        
        :param channel: the channel number
        :param low: the lower trip limit for the channel, in units [%] of the full scale
        :param high: the upper trip limit for the channel, in units [%] of the full scale
        :type channel: int
        :type low: float
        :type high: float
        """
        if not self.is_good_channel(channel):
            return
        if (not isinstance(low, (int, float))) or (not isinstance(high, (int, float))):
            raise SyntaxError("The desired correction factor doesn't make sense: %s/%s" % (low, high))
        low = int(np.rint(low*10))
        high = int(np.rint(high*10))
        self.write('LL %s %s' % (channel, low))
        self.write('HL %s %s' % (channel, high))
    def get_trip_limits(self, channel):
        """
        Queries the trip limits for the channel.
        
        :param channel: the channel number
        :type channel: int
        :returns: the current trip limits set for the channel (lower, upper)
        :rtype: tuple(float, float)
        """
        low = float(self.query('LL %s R' % channel))/10
        high = float(self.query('HL %s R' % channel))/10
        return (low, high)


class MKS_946(MassFlowController):
    """
    Provides a more specific class for the MKS 946 unit.
    
    Note that this is still a work in progress.
    """
    
    range_units = [
        "5 SCCM", "10 SCCM", "20 SCCM", "50 SCCM",
        "100 SCCM", "200 SCCM", "500 SCCM", "1000 SCCM"]
    pressure_units = ["Torr", "MBAR", "PASCAL", "Micron"]
    pressure_sensors = ["CM", "PR", "CP", "CC", "HC"]
    chan_to_abc = {
        1: "A",
        2: "A",
        3: "B",
        4: "B",
        5: "C",
        6: "C"}
    chan_to_abc12 = {
        1: "A1",
        2: "A2",
        3: "B1",
        4: "B2",
        5: "C1",
        6: "C2",
        None: "NA"}
    
    def __init__(
        self,
        com=None,
        address=None,
        terminator="\r",
        eol=";FF",
        enforceTermination=False,
        **kwds):
        """
        See the documentation for the parent class about this.
        """
        super(self.__class__, self).__init__(
            com=com, __TERM=terminator, enforceTermination=enforceTermination, **kwds)
        self.address = address
        self.terminator = terminator
        self.eol = eol
        self.socket._sock.set_termination_char(term=self.terminator)
        self.write = self.socket.write
        self.status = ""
        self.fs = [None,None,None,None,None,None]
        self.cf = [None,None,None,None,None,None]
        self.sensor_types = []
        self.punit = None
        self.pr = [None,None,None,None,None,None]
        print("Connected: %s" % self.identify())
        
        self.do_test()
    
    def do_test(self):
        pass
    
    ## system control
    def chan2InstInt(self, channel):
        """
        Converts a human-readable channel number (1-8) to the proper
        value that refers to the instrument's modules:
        1,2 -> 1 (i.e. module A)
        3,4 -> 2 (i.e. module B)
        5,6 -> 3 (i.e. module C)
        7,8 -> 4 (i.e. internal/serial)
        """
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in list(range(1,9)):
            raise SyntaxError("The requested channel is not 1-8: %s" % channel)
        else:
            channel = channel - 1
            return int(math.floor(channel/2.0))
    
    def is_good_channel(self, channel):
        """
        Returns the identification string of the instrument.
        
        :param channel: a channel number
        :type channel: int
        :returns: whether the input channel was acceptable
        :rtype: bool
        """
        # check input
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in list(range(1,7)):
            raise SyntaxError("The requested channel is not 1-6 (or sometimes 0=all): %s" % channel)
        # then check actual goodness
        if "NC" in self.get_sensor_type(channel):
            time.sleep(0.01)
            return False
        else:
            return True
    
    def identify(self):
        """
        Returns the identification string of the instrument.
        
        :returns: the identification string: MKS XXX (s/n XXXXX, firmware vX.XX)
        :rtype: str
        """
        device_type = self.query("MD")
        device_sn = self.query("SN")
        device_fw = self.query("FV6")
        self.identifier = "MKS %s (s/n %s, firmware v%s)" % (device_type, device_sn, device_fw)
        return self.identifier
    
    def reset_hardware(self):
        """
        Does nothing.. no command is apparently capable of this.
        """
        self.status = "hardware reset not available"
    def reset_default(self):
        """
        Performs a factory (default) reset.
        """
        self.set('FDS')
    
    def reset_soft(self, n=1):
        """
        Performs a 'soft' reset, simply clearing the socket.
        """
        for i in range(n):
            self.socket.clear()
            time.sleep(0.05)
    
    def get_status(self, channel=0):
        """
        Returns the current status of the channel.
        
        Note that this just returns a single string: the most
        recent acknowledgment from the device.
        
        :param channel: (optional) the channel number, but it's useless
        :type channel: int
        :returns: the status string
        :rtype: str
        """
        if not self.is_good_channel(channel):
            return
        if not channel:
            pass
        return self.status
    
    def get_module_type(self, channel=0):
        """
        Returns the type of module (1-6) that is found in one of the card
        slots (A,B,C).
        
        :returns: the module type
        :rtype: str
        """
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in list(range(1,9)):
            raise SyntaxError("The requested channel is not 0-7 (or sometimes 0=all): %s" % channel)
        else:
            module_type = self.query("MT").split(",")
            module_type = module_type[self.chan2InstInt(channel)]
            return module_type
    
    def get_sensor_type(self, channel=0):
        """
        Returns the sensor type (1-6) that is found in one of the modules.
        
        :returns: the sensor type
        :rtype: str
        """
        if not isinstance(channel, int):
            raise NotANumberError
        elif not channel in list(range(1,7)):
            raise SyntaxError("The requested channel is not 1-6 (or sometimes 0=all): %s" % channel)
        elif not len(self.sensor_types):
            for abc in ["A","B","C"]:
                sensor_types = self.query("ST%s" % abc).split(",")
                self.sensor_types += sensor_types
            return self.sensor_types[channel-1]
        else:
            return self.sensor_types[channel-1]
    
    ## MFC control
    def open_valve(self, channel=0):
        """
        Open the valve. If no channel is specified, all are opened.
        
        :param channel: (optional) the channel number
        :type channel: int
        """
        if not channel:
            channel = [1,2,3,4,5,6]
        else:
            channel = [channel]
        for c in channel:
            if not self.is_good_channel(c):
                continue
            cmd = "QMD%s" % c
            value = "Open"
            self.set(cmd, value)
    def close_valve(self, channel=0):
        """
        Close the valve. If no channel is specified, all are closed.
        
        :param channel: (optional) the channel number
        :type channel: int
        """
        if not channel:
            channel = [1,2,3,4,5,6]
        else:
            channel = [channel]
        for c in channel:
            if not self.is_good_channel(c):
                pass
            cmd = "QMD%s" % c
            value = "Close"
            self.set(cmd, value)
    def get_valve_mode(self, channel=0):
        """
        Close the valve. If no channel is specified, all are closed.
        
        :param channel: (optional) the channel number
        :type channel: int
        """
        if not self.is_good_channel(channel):
            pass
        return self.query("QMD%s" % channel)
    
    def set_range_unit(self, channel, range_string):
        """
        Sets the unit's range based on the user-defined string.
        
        :param channel: the channel number
        :param range_string: the full scale range of the MFC (see self.range_units)
        :type channel: int
        :type range_string: str
        """
        if not self.is_good_channel(channel):
            return
        range_string = str(range_string)
        if not range_string in self.range_units:
            raise SyntaxError("The requested pressure unit is not known: %s" % range_string)
        range_value = range_string.split(" ")[0]
        cmd = "RNG%s" % channel
        self.set(cmd, range_value)
        self.fs[channel-1] = "%s SCCM" % range_value
    def get_range_unit(self, channel):
        """
        Returns the unit's range.
        
        :param channel: the channel number
        :type channel: int
        :returns: the range for the MFC
        :rtype: str
        """
        if not self.fs[channel-1]:
            if not self.is_good_channel(channel):
                return
            response = self.query("RNG%s" % channel)
            self.fs[channel-1] = response
            return "%g SCCM" % float(response)
        else:
            return self.fs[channel-1]
    
    def set_setpoint(self, channel, setpoint):
        """
        Sets the set point of a channel, with respect to the full scale.
        
        :param channel: the channel number
        :param setpoint: the setpoint of the flow, in unit [%], up to 110%
        :type channel: int
        :type setpoint: float
        """
        if not self.is_good_channel(channel):
            return
        if not isinstance(setpoint, (int, float)):
            raise NotANumberError
        # update the set point
        fs = float(self.get_range_unit(channel).split(" ")[0])
        cf = float(self.get_correction_factor(channel))
        setpoint = "%.2E" % (setpoint/100.0*fs*cf)
        cmd = "QSP%s" % channel
        self.set(cmd, setpoint)
        time.sleep(0.1)
        # switch the valve to that mode (instead of open)
        cmd = "QMD%s" % channel
        self.set(cmd, "Setpoint")
    def get_setpoint(self, channel):
        """
        Returns the setpoint of a channel.
        
        :param channel: the channel number
        :type channel: int
        :returns: the setpoint of the channel in unit [%]
        :rtype: float
        """
        if not self.is_good_channel(channel):
            return
        setpoint = float(self.query("QSP%s" % channel))
        fs = float(self.get_range_unit(channel).split(" ")[0])
        return setpoint/fs*100
    def get_actual_flow(self, channel):
        """
        Returns the actual flow of a channel.
        
        Note that the actual flow is scaled by the gas correction factor.
        
        :param channel: the channel number
        :type channel: int
        :returns: the actual flow of the channel in unit (sccm)
        :rtype: float
        """
        if not self.is_good_channel(channel):
            return
        absflow = float(self.query("FR%s" % channel))
        return absflow
    
    def set_correction_factor(self, channel, cf):
        """
        Sets the correction factor for the gas.
        
        :param channel: the channel number
        :param cf: the gas correction factor for the gas through that channel
        :type channel: int
        :type cf: float
        """
        if not self.is_good_channel(channel):
            return
        if not isinstance(cf, (int, float)):
            raise SyntaxError("The desired correction factor doesn't make sense: %s" % cf)
        self.cf[channel-1] = cf
        cf = "%.2e" % cf
        cmd = "QSF%s" % channel
        self.set(cmd, cf)
    def get_correction_factor(self, channel):
        """
        Reads the correction factor for the gas.
        
        :param channel: the channel number
        :type channel: int
        :returns: the active gas correction factor for that channel
        :rtype: float
        """
        if not self.cf[channel-1]:
            if not self.is_good_channel(channel):
                return
            cf = float(self.query("QSF%s" % channel))
            self.cf[channel-1] = cf
            return cf
        else:
            return self.cf[channel-1]
    
    ## pressure control
    def set_pressure_unit(self, unit):
        """
        Sets the pressure unit for the system (if a pressure sensor is installed).
        
        :param unit: the channel number
        :type unit: str
        """
        if not self.is_good_channel(channel):
            return
        if (not isinstance(unit, str)) or (not unit in self.pressure_units):
            raise SyntaxError("The desired unit must be %s: %s" % (good_units, unit))
        cmd = "U"
        self.set(cmd, unit)
    def get_pressure_unit(self):
        """
        Reads the pressure unit for the system.
        
        :returns: the pressure unit
        :rtype: str
        """
        if not self.punit:
            unit = str(self.query("U"))
            self.punit = unit
            return unit
        else:
            return self.punit
    def get_pressure(self, channel, showUnits=False):
        """
        Returns the pressure of a channel.
        
        Note that the actual flow is scaled by the gas correction factor.
        
        :param channel: the channel number
        :param showUnits: (optional) whether to return a string with the pressure unit
        :type channel: int
        :type showUnits: bool
        :returns: the current pressure (in the system unit)
        :rtype: float or str
        """
        if not self.is_good_channel(channel):
            print("this pressure channel is 'not good'!")
            return
        module_type = self.get_sensor_type(channel)
        if not module_type in self.pressure_sensors:
            raise Exception("this channel does not look like a valid pressure sensor!")
        pr = self.query("PR%s" % channel)
        try:
            pr = float(pr)
        except:
            pass
        if showUnits:
            if isinstance(pr, float):
                pr = "%.3e %s" % (pr, self.get_pressure_unit())
            else:
                pr = "%s %s" % (pr, self.get_pressure_unit())
        return pr
    
    ## PID control
    def set_ratio(self, recipeNum=None,
        mfc1=None, mfc2=None,
        mfc3=None, mfc4=None,
        mfc5=None, mfc6=None):
        """
        Sets up ratio control of system pressure using multiple MFCs.
        See Section 6.7.3.2 of the user manual for more details!
        
        Note that this does not actually active the recipe! For this,
        one must also make sure an appropriate PID recipe is also
        defined, and then finally the ratio control may be activated
        using the function set_active_recipe() below.
        
        Note also that the flow rates are agnostic in terms of both the
        unit and correction factor, which depend on what's been set in
        the channel setup.
        
        :param recipeNum: the recipe index to use (i.e. 1 will set up recipe RR1)
        :type recipeNum: int
        :param mfc1: the initial flow rate to use for the MFC at channel A1
        :type mfc1: int
        :param mfc2: the initial flow rate to use for the MFC at channel A2
        :type mfc2: int
        :param mfc3: the initial flow rate to use for the MFC at channel B1
        :type mfc3: int
        :param mfc4: the initial flow rate to use for the MFC at channel B2
        :type mfc4: int
        :param mfc5: the initial flow rate to use for the MFC at channel C1
        :type mfc5: int
        :param mfc6: the initial flow rate to use for the MFC at channel C2
        :type mfc6: int
        """
        # process the recipe number
        if recipeNum is None:
            recipeNum = 1
        elif not recipeNum in range(1,5):
            print("you must select a recipeNum 1-4! you requested %s" % recipeNum)
            return
        cmd = "RRCP"
        self.set(cmd, recipeNum)
        # make sure all the impacted channels are MFCs
        if (mfc1 is not None) and (not "FC" in self.get_sensor_type(1)):
            msg = "channel 1 is not a flow controller! will not set up this ratio recipe"
            raise Exception(msg)
        if (mfc2 is not None) and (not "FC" in self.get_sensor_type(2)):
            msg = "channel 2 is not a flow controller! will not set up this ratio recipe"
            raise Exception(msg)
        if (mfc3 is not None) and (not "FC" in self.get_sensor_type(3)):
            msg = "channel 3 is not a flow controller! will not set up this ratio recipe"
            raise Exception(msg)
        if (mfc4 is not None) and (not "FC" in self.get_sensor_type(4)):
            msg = "channel 4 is not a flow controller! will not set up this ratio recipe"
            raise Exception(msg)
        if (mfc5 is not None) and (not "FC" in self.get_sensor_type(5)):
            msg = "channel 5 is not a flow controller! will not set up this ratio recipe"
            raise Exception(msg)
        if (mfc6 is not None) and (not "FC" in self.get_sensor_type(6)):
            msg = "channel 6 is not a flow controller! will not set up this ratio recipe"
            raise Exception(msg)
        # set each of the flow rates then..
        if (mfc1 is not None):
            cmd = "RRQ1"
            val = "%.2E" % mfc1
            self.set(cmd, val)
        if (mfc2 is not None):
            cmd = "RRQ2"
            val = "%.2E" % mfc2
            self.set(cmd, val)
        if (mfc3 is not None):
            cmd = "RRQ3"
            val = "%.2E" % mfc3
            self.set(cmd, val)
        if (mfc4 is not None):
            cmd = "RRQ4"
            val = "%.2E" % mfc4
            self.set(cmd, val)
        if (mfc5 is not None):
            cmd = "RRQ5"
            val = "%.2E" % mfc5
            self.set(cmd, val)
        if (mfc6 is not None):
            cmd = "RRQ6"
            val = "%.2E" % mfc6
            self.set(cmd, val)
    
    def set_pid(self, recipeNum=None,
        pidChannel=None, pidPSensor=None, pSP=None,
        kp=None, ti=None, td=None,
        ramp=None, start=None, end=None,
        base=None, ceiling=None, direction=None, preset=None,
        band=None, gain=None):
        """
        Sets up a recipe for PID control. See Section 6.7.3.2 of the user
        manual for more details!
        
        Note that this does not actually active the recipe! For this,
        see the function set_active_recipe() below.
        
        Note also that the pressure set point is agnostic in terms of the
        unit, and depend on what's been defined in the channel setup.
        
        :param recipeNum: the recipe index to use (i.e. 1 will set up recipe R1)
        :type recipeNum: int
        :param pidChannel: the channel 1-6/Rat/Vlv to use with the set point
        :type pidChannel: int or str
        :param pidPSensor: the channel 1-6 connected to the pressure sensor
        :type pidPSensor: int
        :param pSP: the target pressure to use as the set point (see the system unit)
        :type pSP: float
        :param kp: the proportional control parameter K_p
        :type kp: float
        :param ti: the integral control parameter T_i
        :type ti: float
        :param td: the derivative control paramter T_d
        :type td: float
        :param ramp: the time period (in seconds) ramps from start to end
        :type ramp: float
        :param start: the starting set point for the MFCs during the initial ramp
        :type start: float
        :param end: the ending set point for the MFCs during the initial ramp
        :type end: float
        :param base: the lower limit (in percent) for the MFCs in terms of full scale
        :type base: float
        :param ceiling: the upper limit (in percent) for the MFCs in terms of full scale
        :type ceiling: float
        :param direction: the location of the valves wrt the pressure sensor
        :type direction: str
        :param preset: the flow rate to set the MFCs once the PID control is terminated
        :type preset: float
        :param band: the band for gain scheduling PID control
        :type band: int
        :param gain: the gain for gain scheduling PID control
        :type gain: int
        """
        ### check inputs
        if recipeNum is None:
            recipeNum = 1
        elif not recipeNum in range(1,9):
            msg = "you must select a recipeNum 1-8: %s" % recipeNum
            raise Exception(msg)
        if not pidChannel in list(range(1,7))+[None, "rat", "Rat", "vlv", "Vlv"]:
            msg = "you must select a pidChannel 1-6, 'rat', or 'vlv': %s" % pidChannel
            raise Exception(msg)
        if pidPSensor in range(1,7):
            module_type = self.get_sensor_type(pidPSensor)
            if not module_type in self.pressure_sensors:
                msg = "channel %s does not look like a valid pressure sensor: %s" % (pidPSensor, module_type)
                raise Exception(msg)
        if (kp is not None) and (kp < 0.00002 or kp > 10000):
            msg = "kp must be within range 0.00002 to 10000: %s" % kp
            raise Exception(msg)
        if (ti is not None) and (ti < 0.01 or ti > 10000):
            msg = "ti must be within range 0.01 to 10000: %s" % ti
            raise Exception(msg)
        if (td is not None) and (td < 0.0 or td > 1000):
            msg = "td must be within range 0.0 to 1000: %s" % td
            raise Exception(msg)
        if (band is not None) and (band < 0 or band > 30):
            msg = "band must be within range 0 to 30: %s" % band
            raise Exception(msg)
        if (gain is not None) and (gain < 1 or gain > 200):
            msg = "gain must be within range 1 to 200: %s" % gain
            raise Exception(msg)
        if (ramp is not None) and (ramp < 0.0 or ramp > 1000):
            msg = "ramp must be within range 0.0 to 1000: %s" % ramp
            raise Exception(msg)
        if (start is not None) and (start < 0.0 or start > 100):
            msg = "start must be within range 0.0 to 100: %s" % start
            raise Exception(msg)
        if (end is not None) and (end < 0.0 or end > 100):
            msg = "end must be within range 0.0 to 100: %s" % end
            raise Exception(msg)
        if (base is not None) and (base < 0.0):
            msg = "base must be greater than 0.0: %s" % base
            raise Exception(msg)
        if (ceiling is not None) and (ceiling > 100.0):
            msg = "ceiling must be greater than 100.0: %s" % ceiling
            raise Exception(msg)
        if (base is not None) and (ceiling is not None):
            diff = ceiling - base
            if diff < 10:
                msg = "base and ceiling must differ by at least 10.0: "
                msg += "%s-%s = %s" % (ceiling, base, diff)
                raise Exception(msg)
        if (direction is not None):
            if not direction.lower() in ["upstream", "downstream"]:
                msg = "direction must be upstream or downstream: %s" % direction
                raise Exception(msg)
        if (preset is not None) and (preset < 0.0 or preset > 100):
            msg = "preset must range from 0 to 100: %s" % preset
            raise Exception(msg)
        ### finally set up the recipe
        # set the recipe number
        #cmd = "RCP"
        #self.set(cmd, recipeNum)
        # set the channel number
        if pidChannel is not None:
            if pidChannel in range(1,7):
                pidChannel = self.chan_to_abc12[pidChannel]
            elif pidChannel == "rat":
                pidChannel = "Rat"
            elif pidChannel == "vlv":
                pidChannel = "Vlv"
            cmd = "RDCH"
            val = "%s:%s" % (recipeNum, pidChannel)
            self.set(cmd, val)
        # pressure sensor
        if pidPSensor is not None:
            pidPSensor = self.chan_to_abc12[pidPSensor]
            cmd = "RPCH"
            val = "%s:%s" % (recipeNum, pidPSensor)
            self.set(cmd, val)
        # maths
        if kp is not None:
            cmd = "RKP"
            val = "%s:%.2E" % (recipeNum, kp)
            self.set(cmd, val)
        if ti is not None:
            cmd = "RTI"
            val = "%s:%.2E" % (recipeNum, ti)
            self.set(cmd, val)
        if td is not None:
            cmd = "RTD"
            val = "%s:%.2E" % (recipeNum, td)
            self.set(cmd, val)
        if band is not None:
            cmd = "RGSB"
            val = "%s:%s" % (recipeNum, band)
            self.set(cmd, val)
        if gain is not None:
            cmd = "RGSG"
            val = "%s:%s" % (recipeNum, gain)
            self.set(cmd, val)
        # initializations
        if ramp is not None:
            cmd = "RCST"
            val = "%s:%.2E" % (recipeNum, ramp)
            self.set(cmd, val)
        if start is not None:
            cmd = "RSTR"
            val = "%s:%.2E" % (recipeNum, start)
            self.set(cmd, val)
        if end is not None:
            cmd = "REND"
            val = "%s:%.2E" % (recipeNum, end)
            self.set(cmd, val)
        # ranges
        if base is not None:
            cmd = "RBAS"
            val = "%s:%.2E" % (recipeNum, base)
            self.set(cmd, val)
        if ceiling is not None:
            cmd = "RCEI"
            val = "%s:%.2E" % (recipeNum, ceiling)
            self.set(cmd, val)
        if direction is not None:
            cmd = "RDIR"
            if direction == "upstream":
                direction = "Upstream"
            elif direction == "downstream":
                direction = "Downstream"
            val = "%s:%s" % (recipeNum, direction)
            self.set(cmd, val)
        if preset is not None:
            cmd = "RPST"
            val = "%s:%.2E" % (recipeNum, preset)
            self.set(cmd, val)
        # pressure set point
        if pSP is not None:
            cmd = "RPSP"
            val = "%s:%.2E" % (recipeNum, pSP)
            self.set(cmd, val)
    
    def set_active_recipe(self, state=None):
        """
        Activates PID/ratio control. OFF will terminate it, PID
        will activate the PID control, and MAN will activate
        manual ratio control.
        
        Note that a bug with the communication interface of the box
        does not allow one to remotely select which recipes to use,
        so these must be manually selected/changed from the box
        itself!
        
        :param state: the state to use for the PID/ratio control
        :type state: str
        """
        if state.lower() == "off":
            self.set("PID", "OFF")
            self.set("RM", "OFF")
        elif state.lower() == "pid":
            self.set("PID", "ON")
            self.set("RM", "OFF")
        elif state.lower() == "man":
            self.set("PID", "OFF")
            self.set("RM", "ON")
    
    ## communication control
    def query(self, cmd, size=0):
        """
        Sends a command to the instrument and returns the response.
        
        :param cmd: an arbitrary command string
        :param size: (optional) the expected length of the response in [bytes]
        :type cmd: str
        :type size: int
        :returns: the direct response string from the socket
        :rtype: str
        """
        # set format
        cmd = '@%s%s?%s%s' % (self.address, cmd, self.eol, self.terminator)
        # send command to return the pressure
        self.write(cmd)
        time.sleep(0.01)
        if not size:
            response = self.socket.readline(eol=self.eol)
        elif isinstance(size, int):
            response = self.socket.read(size=size)
        else:
            response = 0
        if not "ACK" in response:
            print("WARNING! response did not look like an acknowledgment: %s -> %s" % (cmd.strip(), response.strip()))
            self.status = response.strip()
            return None
        else:
            retest = r"@%sACK(.+)%s" % (self.address, self.eol)
            match = re.search(retest, response)
            if match:
                self.status = match.group(1)
                return match.group(1)
            else:
                self.status = response.strip()
                return response
    
    def set(self, cmd, value):
        """
        Sends a command to the instrument.
        
        :param cmd: an arbitrary command string
        :param value: an arbitrary value for the new parameter
        :type cmd: str
        :type value: str or int or float
        """
        # set format
        cmd = '@%s%s!%s%s%s' % (self.address, cmd, value, self.eol, self.terminator)
        # send command to return the pressure
        self.write(cmd)
        response = self.socket.readline(eol=self.eol)
        if not "ACK" in response:
            print("WARNING! response did not look like an acknowledgment: %s -> %s" % (cmd.strip(), response.strip()))
            self.status = response.strip()
        else:
            retest = r"@%sACK(.+)%s" % (self.address, self.eol)
            match = re.search(retest, response)
            if match:
                self.status = match.group(1)
            else:
                self.status = response.strip()
