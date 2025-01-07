#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This file simply provides dictionaries for the Spectrum class.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
specHeaderDict = {
    "title": "title of the spectrum",
    "comment": "some comment about the spectrum",
    "timestamp": "the timestamp for spectral acquisition",
    "sourcefile": "the pathname of the file that was loaded",
    "loadTime": "the timestamp for the loading of the spectrum",
    "modTime": "the timestamp for any particular modification of the spectrum",
    "freqStart": "the starting frequency of the spectrum", # JCL: is this appropriate? what about wavelength?
    "freqStop": "the ending frequency of the spectrum",
    "freqStep": "the frequency step of the spectrum",
    "xrange": "the spectral bandwidth",
    "yrange": "the range of the y-values",
    "numPoints": "the length of the x & y data (should be the same!)",
    "detAmplitute": "the amplitude used for the detection (not gain)",
    "detGain": "the amplification used for the detection",
    "detSamplerate": "the sampling rate used for the detection (same as time constant for a lockin-amplifier)",
    "multFact": "the multiplication factor used for the spectral axis",
    "scanTime": "the integration/scan time for the spectrum",
    "numScans": "the number of averages used for the spectral acquisition",
}
