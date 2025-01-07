#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import ctypes

scopelib = ctypes.cdll.LoadLibrary('./libreadfile.so')


class ScopeSocket(object):
    def __init__(self, host, port = 4000):
        self.host = host
        self.port = port
        self.sockfd = None
        self.connected = False

        self.open()
        
    def open(self):
        # check if socket is already opened; close it in that case
        if self.connected == True:
            self.close()

        # open socket        
        try:
            self.sockfd  = scopelib.create_socket(self.host, self.port)
            if self.sockfd > 0:
                self.connected = True
            else:
                self.connected = False
        except:
            self.sockfd = None
            self.connected = False

    def write(self, string):
        if self.connected:
            scopelib.write_buffer(self.sockfd, string+'\n')
        else:
            print("Not connected !")

    def read(self):
        if self.connected:
            retval = scopelib.read_buffer(self.sockfd)
        else:
            print("Not connected !")
            retval = None

    def get(self):
        if self.connected:
            buf = ctypes.create_string_buffer(8192)
            string_len = scopelib.get_buffer(self.sockfd, buf, len(buf))
        else:
            print("Not connected !")
            retval = None
        if string_len>0:
            return buf[0:string_len]
        else:
            return ""
        
    def query(self, string):
        self.write(string)
        return self.get()
        
    def read_curvestream(self):
        if self.connected:
            b = scopelib.read_from_server(self.sockfd)
        else:
            print("Not connected!")

    def close(self):
        scopelib.close_socket(self.sockfd)
        self.connected = False
