#!/usr/bin/env python
# -*- coding: utf8 -*-
#
"""
Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
import sys
import os

if sys.version_info[0] == 3:
    xrange = range

def get_fid_list(data_dir, filter_str = None, ftype = 'tekscope-csv'):
    """
    creates a list of fid's generated from files in the data directory.

    :param data_dir: directory which contains the FID data files.
    :type data_dir: str
    :param filter_str: rejects all files which do not have the defined string in their name
    :type filter_str: str
    :returns: dictionary with FID's (file name is used as key)
    """
    if data_dir[-1] != '/':
       data_dir += '/'
    if filter_str:
       file_list = [i for i in os.listdir(data_dir) if filter_str in i]
    else:
       file_list = os.listdir(data_dir) 

    fid_arr = {}
    for fname in file_list:
        fid_arr[fname] = fid = pd.load_fid(data_dir + fname, ftype = ftype)

    return fid_arr


def calibrate_on_pulse(fids, max_pos_pulse, min_pos_trunc):
    fids_trunc = {}
    fids_pulse = {}
    for fid in fids:
        fids_trunc[fid] = pd.FID(fids[fid].x[min_pos_trunc:], fids[fid].y[min_pos_trunc:])
        fids_pulse[fid] = pd.FID(fids[fid].x[:max_pos_pulse], fids[fid].y[:max_pos_pulse])
    
    return fids_trunc, fids_pulse


def batch_analyze(fids, frequencies, filter_span, time_start = None, time_stop = None, threshold = None, fixedDecay = None):
    """
    Processes a dictionary of fids. The envelope is fitted and a pdf-file is generated.

    :param fids: Dictionary of FIDs to be processed
    :type fids: dict(process_data.FID)
    :param frequencies: Frequencies to be analyzed
    :type frequencies: dict(int:float)
    :param filter_span: width of the frequency filter (+/-)
    :type filter_span: float
    :param time_start: Time window: start position for the fit
    :type time_start: float
    :param time_stop: Time window: stop position for the fit
    :type time_stop: float
    :returns: a dictionary with intensities and decayrates
    """

    # convert frequencies a dictionary
    if type(frequencies) == list:
       frequencies = {i:i for i in frequencies}
    elif type(frequencies) == float:
       frequencies = {frequencies:frequencies}
    else:
       pass

    result = {}
    for fid in fids:
        # process all frequencies: fit the envelope for each frequency and store the result in 'result'
        result[fid] = {}
        for freq in frequencies:
            fids[fid].filter(flow = frequencies[freq] - filter_span, fhigh = frequencies[freq] + filter_span)
            fids[fid].fit_envelope(time_start = time_start, time_stop = time_stop, threshold = threshold, fixedDecay = fixedDecay) 
            result[fid][freq] = {'intensity': fids[fid].intensity, 'decayrate': fids[fid].decayrate}
            # save the plot
            fig = fids[fid].plot_envelope(type = 'log', filename = fid + '_' + freq + '.pdf')
            # del fig
            pd.plt.close(fig)
            if fids[fid].intensity:
                print("%s: %s %lf %lf" % (fid, str(freq), fids[fid].intensity, fids[fid].decayrate))
            else:
                print("%s: %s ---  --- " % (fid, str(freq)))
            # restore the FID (remove the filter)
            fids[fid].restore()
    return result
   
def batch_analyze_fft(fids, frequencies, filter_span, time_start = None, time_stop = None, threshold = None):
    """
    Processes a dictionary of fids. The intensities from the FFT is determined and a pdf-file is generated.

    :param fids: Dictionary of FIDs to be processed
    :type fids: dict(process_data.FID)
    :param frequencies: Frequencies to be analyzed
    :type frequencies: dict(int:float)
    :param filter_span: width of the frequency filter (+/-)
    :type filter_span: float
    :param time_start: Time window: start position for the fit
    :type time_start: float
    :param time_stop: Time window: stop position for the fit
    :type time_stop: float
    :returns: a dictionary with intensities and decayrates
    """

    # convert frequencies a dictionary
    if type(frequencies) == list:
       frequencies = {i:i for i in frequencies}
    elif type(frequencies) == float:
       frequencies = {frequencies:frequencies}
    else:
       pass

    result = {}
    for fid in fids:
        # process all frequencies: fit the envelope for each frequency and store the result in 'result'
        result[fid] = {}
        print("Processing: %s" % fid)
        #fids[fid].calc_power_spec(time_start = time_start, time_stop = time_stop)
        fig = fids[fid].plot_power_spec(time_start = time_start, time_stop = time_stop, filename = fid + '_fft.pdf')
        for freq in frequencies:
            xmin = frequencies[freq] - filter_span
            xmax = frequencies[freq] + filter_span
            result[fid][freq] = {'intensity': max([fids[fid].spec_win_y[i] for i in xrange(len(fids[fid].spec_win_x)) if fids[fid].spec_win_x[i] >= xmin and fids[fid].spec_win_x[i] <= xmax])}
            if result[fid][freq]['intensity']:
               print("%s: %s %lf" % (fid, str(freq), result[fid][freq]['intensity']))
            else:
               print("%s: %s ---" % (fid, str(freq)))
        # del fig
        pd.plt.close(fig)
    return result
   



def save_results(fids, result, filename):
    """
    Saves the result of a batch analysis to a file.
    """
    f = open(filename, 'w')

    # sort results by temperature if possible
    try:
       # create list with sorted keys
       fid_keys = [i[0] for i in sorted(list(fids.items()), key= lambda x: float(x[1].header['Temperature']))]
    except:
       # sort keys by name
       fid_keys = sorted([i for i in result])

    for fid in fid_keys:
        f.write('%-45s ' % fid)
        if 'Temperature' in fids[fid].header:
            f.write('%8.3lf ' % float(fids[fid].header['Temperature']))
    
        if 'Pressure Line' in fids[fid].header:
            f.write('%10.7lf ' % float(fids[fid].header['Pressure Line']))
    
        if 'Pressure Chamber' in fids[fid].header:
            f.write('%10.7lf ' % float(fids[fid].header['Pressure Chamber']))
    
        for key in result[fid].keys():
            f.write('%10s ' % key)
            if result[fid][key]['decayrate']:
               f.write('%16.6lf ' % result[fid][key]['decayrate'])
            else:
               f.write('00.000 ')

            if result[fid][key]['intensity']:
               f.write('%10.6g ' % result[fid][key]['intensity'])
            else:
               f.write('00.000 ')
        f.write('\n')

        

