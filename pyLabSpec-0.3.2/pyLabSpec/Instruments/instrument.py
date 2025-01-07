#!/usr/bin/env python
# -*- coding: utf8 -*-
#
# TODO
# - add a routine for accessing a GPIB device's DevClear command
# - update docs for "direct" socket
# - finish port to python 3
#   - sockets use <class 'bytes'>==type(b'foo'), which matches str only in py2
#     solution: use encode() & decode()
#        >ENCODING = 'utf-8'
#        >ser.write('hello'.encode(ENCODING))
#        >response_bytes = ser.readline()
#        >response_str = response_bytes.decode(ENCODING)
#
"""
This module provides classes and methods to manage the communciation with
instrument devices. It is an abstraction layer in order to remove all
dependencies of the communication protocol from the instrument classes, e.g.
synthesizers can be controlled via TCP/IP or GPIB and all dependencies of the
used protocol are treated here whereas the synthesizer class does not contain
dependencies on the protocol.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import sys
import os
import socket
import time
# third-party
import serial
from serial.tools import list_ports
import numpy as np
try:
    import Gpib
except ImportError:
    pass
# local
if not os.path.dirname(os.path.dirname(os.path.realpath(__file__))) in sys.path:
    sys.path.append(os.path.dirname(os.path.dirname(os.path.realpath(__file__))))
from settings import *
import Simulations.waveformbuilder as wb

if sys.version_info[0] == 3:
    print("WARNING: the port to Python 3 is a work in progress!")

BUFFERSIZE = 8192


class Settings(object):
    """
    Class to store settings for an instrument
    """
    identifier = 'unkown'

    def set(self, key, value):
        setattr(self, key, value)

    def get(self, key):
        if hasattr(self, key):
            return vars(self)[key]
        else:
            return None

    def apply_settings(self, settings):
        """
        Applies all settings defined in the settings object.

        :param settings: settings - object 
        :type settings: Instruments.instrument.Settings
        """
        for key in vars(settings):
            self.set(key, vars(settings)[key])

def get_serial_usb_devices():
    return [i for i in list_ports.grep('USB')]

def get_ethernet_devices(subnet, timeout = 1.0):
    """
    Scans for Pfeiffer gauges connected via ethernet (just works if you are in
    the same subnet.
    """
    all_devices = []
    pressure_gauges = []
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    sock.settimeout(timeout)
    sock.bind(('', 7000))
    # Ask for IP-address
    cmd = '\x02\x00\x06\x01\x01\n'
    sock.sendto(cmd, (subnet, 7000))
    time.sleep(0.2)
    try:
        while True:
            answer = sock.recvfrom(4096)
            ip = answer[1][0]
            # if device does not understand command it just returns it
            if len(answer[0]) > len(cmd):
                pressure_gauges.append(ip)
            all_devices.append(ip)
    except socket.timeout:
        pass
    sock.close()

    return pressure_gauges, all_devices

# function to convert integer value into signed binary
tobin = lambda x, count=8: "".join(map(lambda y:str((x>>y)&1), range(count-1, -1, -1)))

class InstSocket(object):
    """
    General instrument socket, which provides protocol indipendent methods and
    controls the communication.
    """
    def __init__(self, com = 'TCPIP', **kwds):
        """
        Initialize a new socket according to the requested protocol.

        :param com: Communication socket (TCPIP, GPIB, or COM)
        :param type: string
        :param **kwds: Additional keywords which are protocol dependent such as
        host, port, baudrate,...
        """
        self.connected = False
        self.host = None
        self.port = None
        self.protokol = None
        self.identifier = None
        
        # process additional arguments
        for ck in kwds.keys():
            if ck in vars(self).keys():
                self.__dict__.update({ck: kwds[ck]})
            else:
                setattr(self, ck, kwds[ck])
        if com == 'TCPIP':
            self._sock = TCPIPSocket(**kwds)
        elif com == 'GPIB':
            self._sock = GpibSocket(**kwds)
        elif com == 'COM':
            self._sock = SerialSocket(**kwds)
        elif com == 'direct':
            self._sock = DirectSocket(**kwds)
        else:
            raise exception
        
        self.connected = True
        self.protocol = com
        
        if com != 'COM':
            self.close = self._sock._close
        else:
            self.close = self._sock.close
            self.open = self._sock.open
            
        self.read =  self._sock.read
        self.readall = self._sock.readall
        self.write =  self._sock.write
        self.query = self._sock.query
        self.isOpen = self._sock.isOpen
        if com != 'GPIB':
            self.readline = self._sock.readline
            self.clear = self._sock.clear
        else:
            self.readline = self._sock.readall
            self.clear = self._sock.readall

    def identify(self):
        self.identifier = self.query('*IDN?')

class TCPIPSocket(object):
    """
    Class which is used to control the communication via TCP/IP.
    """
    def __init__(self, **kwds):
        """
        Initialize a TCP/IP-Socket.

        Arguments host = IP-address (str) and port (int) are required. Timeout
        can be set via the argument 'timeout'.
        """
        self._sock = None
        self.connected = False
        self.__TERM = '\n'
        self.timeout = 1.0
        self.queriesAlwaysUseQMark = True
        self.enforceTermination = True

        # process additional arguments
        for ck in kwds.keys():
            #print(ck, kwds[ck])
            if ck in vars(self).keys():
                self.__dict__.update({ck: kwds[ck]})
            else:
                setattr(self, ck, kwds[ck])
        if "__TERM" in kwds.keys(): # the process above doesn't work in this case!!
            self.__TERM = kwds["__TERM"]
        
        self.len_term = len(self.__TERM)
        self._open()
        self.sta = self.err = self.cnt = 0
        self.settimeout(self.timeout)
    
    def _open(self):
        """
        Opens a new socket and connects to this socket using the parameters host and port.
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        if 'timeout' in vars(self).keys():
            self.settimeout(self.timeout)

        ipaddr = (self.host, self.port)
        self._sock.connect(ipaddr)
        self.connected = True

    def _send(self, string):
        """
        Provides a wrapper for sending a command to the underlying socket.
        
        :param string: the command string to send
        :type string: str
        
        :returns: the number of bytes sent
        :rtype: int
        """
        if sys.version_info[0] == 3:
            string = string.encode('utf-8')
        return self._sock.send(string)
    
    def _recvall(self):
        """
        Performs a readall-like. Does this actually work properly? BUFFERSIZE
        doesn't appear to be defined, and therefore this should raise an
        exception..
        """
        s = ""
        done = False
        while not done:
            response = self._sock.recv(BUFFERSIZE)
            if sys.version_info[0] == 3:
                response = response.decode('utf-8')
            s += response
            if s[-self.len_term] == self.__TERM:
                done = True
        return s
    
    def _recv(self, length):
        s = ""
        while len(s) < length:
            response = self._sock.recv(length-len(s))
            if sys.version_info[0] == 3:
                response = response.decode('utf-8')
            s += response
        return s
    
    def _close(self):
        """
        Closes/disconnects/unsets the socket.
        """
        self._sock.close()
        self._sock = None
        self.connected = False

    def set_termination_char(self, term):
        """
        Provides an interface for redefining the __TERM character because
        it's currently essentially (why?) a private variable and untouchable
        from outside the class.
        
        Note that this is assumed to be a single character, and there are
        some methods of this class that assume it is and will not behave as
        expected if its length is greater than one.
        
        :param term: the new termination character
        :type term: str
        """
        self.__TERM = term
        self.len_term = len(term)

    def clear(self):
        """
        Clear the interface buffer by reading everything from the output buffer.
        """
        # read everything from the buffer.
        self.gettimeout()
        self.settimeout(0.01)

        # read buffer until its empty
        try:
            s = self._sock.recv(BUFFERSIZE)
            while len(s) == BUFFERSIZE:
                s = self._sock.recv(BUFFERSIZE)
        except socket.timeout:
            pass

        self.settimeout(self.timeout)

    def write(self, cmd):
        """
        Send a command to the socket.

        :param cmd: Command
        :type cmd: string
        """
        if self.enforceTermination and self.len_term and (cmd[-self.len_term:] != self.__TERM):
            #print("adding __TERM char: %s -> %s%s" % (cmd, cmd, self.__TERM))
            cmd += self.__TERM
        self._send(cmd)
    
    def readall(self):
        """
        Read all until the buffer ends with the termination string.
        
        Note that the final termination character/string is dropped..
        """
        if not self.len_term:
            raise NotImplementedError("you have no terminator (__TERM) defined, so readall won't work!")
        return self._recvall()[:-self.len_term]

    def read(self, size = 1):
        """
        Read specified number of bytes.

        :param size: Number of bytes (Default = 1)
        :type size: int
        """
        return self._recv(size)
    
    def readline(self, eol=None):
        """
        Reads the buffer until the final termination character or an (optional)
        eol string is reached.
        
        :param eol: (optional) the string marking the end of the buffer, if not __TERM
        :type eol: str
        :returns: the buffer
        :rtype: str
        """
        ret_val = ""
        s = "1"
        while len(s)>0:
            s = self.read()
            ret_val += s
            # exit if EOL
            if (eol is not None) and (ret_val[-len(eol):] == eol):
                break
            # or exit if terminator received
            elif s == self.__TERM:
                break
        return ret_val

    def query(self, cmd):
        """
        Perform a standard IEEE query.
        
        Note that an instance variable 'queriesAlwaysUseQMark' controls
        whether to enforce the inclusion of the '?' character before
        the termination character. This should be redefined at initialization
        of the socket for a non-standard device.

        :param cmd: Command query string
        :type cmd: str
        :returns: the buffer
        :rtype: str
        """
        if self.queriesAlwaysUseQMark and (cmd[-1] != '?'):
            # queries have to end with questionmark
            # append it if missing
            cmd += '?'
        self.write(cmd)
        return self.readline().strip()

    def settimeout(self, timeout):
        """
        Set or change the timeout.

        :param timeout: Time in seconds
        :type timeout: float
        """
        self._sock.settimeout(timeout)

    def gettimeout(self):
        """
        Return the current timeout in seconds.
        """
        self.timeout = self._sock.gettimeout()
        return self.timeout

    def isOpen(self):
        """
        Return if the socket connection has been established. Does not test if
        the connection is still alive.
        """
        return self.connected

class GpibSocket(object):
    """
    Class which provides methods to communicate via GPIB.
    """

    def __init__(self, host, **kwds):
        """
        Initialize the socket and connect to the device.

        :param host: Host to connect to
        :type host: str
        :param **kwds: Additional arguments (currently not used)
        """
        if not "gpib" in sys.modules.keys():
            raise ImportError("Could not import the GPIB library! Please consult a system administrator.")
        self.connected = False
        self.__TERM = '\n'
        self._host = host
        self._sock = None
        self.queriesAlwaysUseQMark = True
        self.enforceTermination = True

        # process additional arguments
        for ck in kwds.keys():
            if ck in vars(self).keys():
                self.__dict__.update({ck: kwds[ck]})
            else:
                setattr(self, ck, kwds[ck])
        if "__TERM" in kwds.keys(): # the process above doesn't work in this case!!
            self.__TERM = kwds["__TERM"]
        
        self._open()
    
    def _open(self):
        self._sock = Gpib.Gpib(self._host, timeout=1)
        self.connected = True
    
    def _close(self):
        self._sock.close()
        self._sock = None
        self.connected = False
    
    def read(self, num=0):
        """
        Read from the socket.
        """
        if not num:
            num = 512
        res = self._sock.read(len=num)
        if sys.version_info[0] == 3:
            res = res.decode('utf-8')
        if isinstance(res, str):
            res = res.strip()
        return res
    
    def readline(self, eol=None):
        """
        Reads the buffer until the final termination character or an (optional)
        eol string is reached.
        
        :param eol: (optional) the string marking the end of the buffer, if not __TERM
        :type eol: str
        :returns: the buffer
        :rtype: str
        """
        ret_val = ""
        s = "1"
        while len(s) > 0:
            s = self.read()
            ret_val += s
            # exit if EOL
            if (eol is not None) and (ret_val[-len(eol):] == eol):
                break
            # or exit if terminator received
            elif s == self.__TERM:
                break
        return ret_val
    
    def readall(self):
        """
        Read from socket.
        """
        ret_val = ""
        s = "1"
        while len(s) > 0:
            s = self.read(num=1)
            ret_val += s
        return ret_val
    
    def write(self, cmd):
        """
        Write to the socket.

        :param cmd: Command which is send.
        :type cmd: str
        """
        if sys.version_info[0] == 3:
            cmd = cmd.encode('utf-8')
        self._sock.write(cmd)
    
    def query(self, cmd, num=0):
        """
        Perform a query (IEEE format: Write and read)

        :param cmd: Command which is send
        :type cmd: str
        """
        if self.queriesAlwaysUseQMark and (cmd[-1] != '?'):
            cmd += '?'
        self.write(cmd)
        return self.read(num=num)
    
    def isOpen(self):
        """
        Returns if a connection has been established. Does not check if the
        connection is alive.
        """
        return self.connected
    
    def clear(self):
        self._sock.clear()

class SerialSocket(object):
    """
    Socket for communication with a serial device.
    """

    def __init__(self, **kwds):
        """
        Initializes the communication to a serial port.
        
        As with the other sockets above, an array of arguments are accepted,
        which all become instance variables and are used for initialization
        of the socket..
        """
        self.socket = None
        self.connected = False
        self.__TERM = "\r"
        self.timeout = 1.0
        self.queriesAlwaysUseQMark = True
        self.enforceTermination = True
        self.port = kwds["port"]
        
        for ck in kwds.keys():
            if ck in vars(self).keys():
                self.__dict__.update({ck: kwds[ck]})
            else:
                setattr(self, ck, kwds[ck])
        if "__TERM" in kwds.keys(): # the process above doesn't work in this case!!
            self.__TERM = kwds["__TERM"]
        self.len_term = len(self.__TERM)

        self.socket = serial.Serial(**kwds)
        #self.clear()

        self.open = self.socket.open
        self.readline = self.socket.readline
        self.read = self.socket.read
        self.readall = self.socket.readall
        self.isOpen = self.socket.isOpen
        self.close = self.socket.close

    def set_termination_char(self, term):
        """
        Provides an interface for redefining the __TERM character because
        it's currently essentially (why?) a private variable and untouchable
        from outside the class.
        
        Note that this is assumed to be a single character, and there are
        some methods of this class that assume it is and will not behave as
        expected if its length is greater than one.
        
        :param term: the new termination character
        :type term: str
        """
        self.__TERM = term
        self.len_term = len(term)

    def clear(self):
        """
        Reset the serial interface buffer.
        """
        self.socket.flushInput()
        self.socket.flush()
        self.socket.reset_input_buffer()
        self.socket.reset_output_buffer()

    def write(self, cmd):
        """
        Writes a command to the instrument.
        
        :param cmd: an arbitrary command to send to the instrument
        :type cmd: str
        """
        if not self.socket.isOpen():
            return
        # append line feed if not present
        if self.enforceTermination and self.len_term and (cmd[-self.len_term:] != self.__TERM):
            cmd += self.__TERM
        # clear buffer
        self.clear()
        # send command to return the pressure
        if sys.version_info[0] == 3:
            cmd = cmd.encode('utf-8')
        x = self.socket.write(cmd)
    
    def query(self, cmd, size=0, strip=True):
        """
        Perform a query (IEEE format: Write and read)

        :param cmd: Command which is send
        :type cmd: str
        """
        if self.queriesAlwaysUseQMark and (cmd[-1] != '?'):
            cmd += '?'
        self.write(cmd)
        if not size:
            data = self.socket.readline()
            if sys.version_info[0] == 3:
                data = data.decode('utf-8')
        elif isinstance(size, int):
            data = self.socket.read(size=size)
            if sys.version_info[0] == 3:
                data = data.decode('utf-8')
        else:
            data = 0
        if strip:
            data = data.strip()
        return data



class DirectSocket(object):
    def __init__(self, host, **kwds):
        self._host = host
        self._open()
    
    def _open(self):
        self._sock = os.open(self._host, os.O_RDWR)
    
    def _close(self):
        self._sock.close()
        self._sock = None
    
    def read(self, num=0):
        rlen = 50
        if num:
            rlen = 16*num
        response = os.read(self._sock, rlen)
        if sys.version_info[0] == 3:
            response = response.decode('utf-8')
        return response.strip()
    
    def readline(self):
        """
        Reads until end of buffer or EOL (First occurance of LineFeed-character).
        """
        ret_val = ""
        s = "1"
        while len(s)>0:
            s = self.read()
            ret_val += s
            # exit if EOL
            if s == '\n':
                break
        return ret_val
    
    def readall(self):
        """
        Read from socket.
        """
        return self.read()
    
    def write(self, cmd):
        if sys.version_info[0] == 3:
            cmd = cmd.encode('utf-8')
        os.write(self._sock, cmd)
    
    def query(self, cmd, num=0):
        self.clear()
        if cmd[-1] != '?':
            cmd += '?'
        self.write(cmd)
        return self.read(num=num)
        #if num:
        #    return self.read(num=num)
        #else:
        #    return self.readline()
    
    def clear(self):
        self.write("*CLS")
    
    def reset(self):
        '''
        Resets instrument to default values
        '''
        self.write('*RST')

    def isOpen(self):
        """
        Return if the socket connection has been established. Does not test if
        the connection is still alive.
        """
        if self._sock:
            return True
        else:
            return False
