#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
This module provides a single source for details about the current version
of the package and some other related information.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
# third-party
pass
# local
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
	sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import miscfunctions

# doesn't work for sdist-installed version.. better to find an alternative
# try:
#     __commit__ = miscfunctions.get_git_hash()
# except:
#     __commit__ = "unknown"

__license__ = "3-clause BSD license"

__version__ = '0.3.2'
