#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
Code based on code published by Eli Bendersky:
http://eli.thegreenplace.net/2011/05/18/code-sample-socket-client-thread-in-python/
"""
import sys
import socket
import struct
import threading
import queue
import pickle

BUFFERSIZE = 8192

class ClientCommand(object):
    """ A command to the client thread.
        Each command type has its associated data:

        CONNECT:    (host, port) tuple
        SEND:       Data string
        RECEIVE:    None
        QUERY:      Data string
        CLOSE:      None
    """
    CONNECT, SEND, RECEIVE, QUERY, DUMPSTREAM_START, DUMPSTREAM_STOP, CLOSE = list(range(7))

    def __init__(self, type, data=None):
        self.type = type
        self.data = data


class ClientReply(object):
    """ A reply from the client thread.
        Each reply type has its associated data:

        ERROR:      The error string
        SUCCESS:    Depends on the command - for RECEIVE it's the received data string, for others None.
    """
    ERROR, SUCCESS = list(range(2))

    def __init__(self, type, data=None):
        self.type = type
        self.data = data


class SocketClientThread(threading.Thread):
    """ Implements the threading.Thread interface (start, join, etc.) and
        can be controlled via the cmd_q Queue attribute. Replies are
        placed in the reply_q Queue attribute.
    """
    def __init__(self, cmd_q=None, reply_q=None):
        super(SocketClientThread, self).__init__()
        self.cmd_q = cmd_q or Queue.Queue()
        self.reply_q = reply_q or Queue.Queue()
        self.alive = threading.Event()
        self.alive.set()
        self.socket = None

        self.handlers = {
            ClientCommand.CONNECT: self._handle_CONNECT,
            ClientCommand.CLOSE: self._handle_CLOSE,
            ClientCommand.SEND: self._handle_SEND,
            ClientCommand.RECEIVE: self._handle_RECEIVE,
            ClientCommand.QUERY: self._handle_QUERY,
            ClientCommand.DUMPSTREAM_START: self._handle_DUMPSTREAM_START, 
            ClientCommand.DUMPSTREAM_STOP: self._handle_DUMPSTREAM_STOP, 
        }

    def run(self):
        while self.alive.isSet():
            try:
                # Queue.get with timeout to allow checking self.alive
                cmd = self.cmd_q.get(True, 0.1)
                self.handlers[cmd.type](cmd)
            except Queue.Empty as e:
                continue

    def join(self, timeout=None):
        self.alive.clear()
        threading.Thread.join(self, timeout)

    def _handle_CONNECT(self, cmd):
        try:
            print("Try to connect")
            self.socket = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((cmd.data[0], cmd.data[1]))
            self.reply_q.put(self._success_reply())
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))

    def _handle_CLOSE(self, cmd):
        self.socket.close()
        reply = ClientReply(ClientReply.SUCCESS)
        self.reply_q.put(reply)

##     def _handle_SEND(self, cmd):
##         header = struct.pack('<L', len(cmd.data))
##         try:
##             self.socket.sendall(header + cmd.data)
##             self.reply_q.put(self._success_reply())
##         except IOError as e:
##             self.reply_q.put(self._error_reply(str(e)))

##     def _handle_RECEIVE(self, cmd):
##         try:
##             header_data = self._recv_n_bytes(4)
##             if len(header_data) == 4:
##                 msg_len = struct.unpack('<L', header_data)[0]
##                 data = self._recv_n_bytes(msg_len)
##                 if len(data) == msg_len:
##                     self.reply_q.put(self._success_reply(data))
##                     return
##             self.reply_q.put(self._error_reply('Socket closed prematurely'))
##         except IOError as e:
##             self.reply_q.put(self._error_reply(str(e)))

##     def _recv_n_bytes(self, n):
##         """ Convenience method for receiving exactly n bytes from
##             self.socket (assuming it's open and connected).
##         """
##         data = ''
##         while len(data) < n:
##             chunk = self.socket.recv(n - len(data))
##             if chunk == '':
##                 break
##             data += chunk
##         return data
    def _send(self, string):
        return self.socket.send(string)

    def _recvall(self):
        s = ""
        done = False
        while not done:
            s += self.socket.recv(BUFFERSIZE)
            if s[-1] == '\n':
                done = True
        return s
            
    def _recv(self, length):
        s = ""
        while len(s) < length:
            s += self.socket.recv(length-len(s))
        return s

    def  _handle_SEND(self, cmd):
        try:
            self._send(cmd.data+'\n')
            self.reply_q.put(self._success_reply())
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))
             
    def _handle_RECEIVE(self, cmd):
        try:
            data = self._recvall()[:-1]
            self.reply_q.put(self._success_reply(data))
        except IndexError:
            self.reply_q.put('No data returned')
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))

    def _handle_QUERY(self, cmd):
        # queries have to end with questionmark
        # append it if missing
        try:
            if cmd.data[-1] != '?':
                cmd.data += '?'
            self._handle_SEND(cmd)
            self._handle_RECEIVE(cmd)
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))

    def _handle_DUMPSTREAM_START(self, cmd):
        try:
            cmd.data = 'CURVESTREAM?'
            self._handle_SEND(cmd)
            # open file
            dumpfile = open('testdump.dat', 'wb')
            self.rundump = True
            while self.rundump:
                dumpfile.write( self.socket.recv(BUFFERSIZE) )
            dumpfile.close()
            cmd.data = '*DCL'
            self._handle_SEND(cmd)
            self.reply_q.put(self._success_reply())
        except IOError as e:
            self.reply_q.put(self._error_reply(str(e)))

    def DUMPSTREAM_STOP(self):
        self.rundump = False
        
    def _handle_DUMPSTREAM_STOP(self, cmd):
        self.rundump = False
        
    def _error_reply(self, errstr):
#        print("ERROR: %s \n" % errstr)
        return ClientReply(ClientReply.ERROR, errstr)

    def _success_reply(self, data=None):
#        print("SUCCESS \n")
        return ClientReply(ClientReply.SUCCESS, data)
