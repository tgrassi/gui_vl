#!/usr/bin/env python
# -*- coding: utf8 -*-
#
"""
This module provides classes for exception handling.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""

class MethodNotAvailableError(Exception):
    """
    Exception raised if method is not available.
    """
    def __init__(self):
       self.expr = "unsupported method"
       self.msg = "This method is not supported by the class"
       print(self.msg)

class NotANumberError(Exception):
    """
    Exception raised if Variable is not a number.
    """
    def __init__(self):
       self.expr = "Variable is not a number"
       self.msg = "Variable is not a number. Number is required"
       print(self.msg)
