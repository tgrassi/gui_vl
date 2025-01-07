#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
"""
This module provides support for nice print-worthy plots, via matplotlib.

Copyright (c) 2020 pyLabSpec Development Team
Distributed under the 3-clause BSD license. See LICENSE for more infomation.
"""
# standard library
import os
import sys
import random
# third-party
import numpy as np
import matplotlib.pyplot as plt
# local
if not os.path.dirname(os.path.realpath(__file__)) in sys.path:
    sys.path.append(os.path.dirname(os.path.realpath(__file__)))
import Spectrum.spectrum as sp
from Catalog import catalog
import miscfunctions

if sys.version_info[0] == 3:
    from importlib import reload
    xrange = range
    unicode = str

#################################################################
# PLOT
#################################################################
plotlog = True
plotabs = True

# reset to default in case something has been changed before
# jake: removed this, because rcParams should stick, to fix other bugs
#plt.rcParams = dict(plt.rcParamsDefault)

plt.style.use( u'ggplot')
plt.style.use( u'seaborn-v0_8-ticks')

params = {'legend.fontsize': 'x-large',
          #'figure.figsize': (15, 10),
          'axes.labelsize': 'x-large',
          'axes.titlesize':'x-large',
          #'xtick.labelsize':20, #'x-large',
          #'ytick.labelsize':20, #'x-large',
          'figure.dpi': 80,
          'axes.grid': True,
          #'xtick.major.width': 1,
          #'xtick.major.size': 12,
          #'xtick.minor.width': 1,
          #'xtick.minor.size': 4,
          #'xtick.minor.pad': 15,
          #'xtick.major.pad': 15,
          'figure.subplot.left': 0.125,
          'figure.subplot.top': 0.9,
          'figure.subplot.bottom': 0.125,
          'figure.subplot.right': 0.95,
          'legend.loc':'upper right',
          'savefig.dpi': 300
          }

plt.rcParams.update(params)

Line2DProperties = [# from Axes.plot()
                    "scalex", "scaley", "data",
                    # from matplotlib.lines.Line2D
                    "linewidth", "linestyle", "ls", "lw", "color", "marker", "markersize",
                    "markeredgewidth", "markeredgecolor", "markerfacecolor", "markevery",
                    "markerfacecoloralt", "fillstyle", "antialiased", "dash_capstyle",
                    "solid_capstyle", "dash_joinstyle", "solid_joinstyle", "pickradius",
                    "drawstyle"
                    ]

BarProperties = [# from Axes.bar()
                 "width", "bottom", "align", "data",
                 # other parameters
                 "tick_label", "xerr", "yerr", "ecolor", "capsize", "error_kw",
                 "log", "orientation",
                 # from matplotlib.pyplot.bar
                 "agg_filter", "alpha", "animated", "antialiased", "aa", "capstyle",
                 "clip_box", "clip_on", "clip_path", "color", "contains", "edgecolor",
                 "ec", "facecolor", "fc", "figure", "fill", "gid", "hatch",
                 "in_layout", "joinstyle", "label", "linestyle", "ls", "linewidth",
                 "lw", "path_effects", "picker", "rasterized", "sketch_params",
                 "snap", "transform", "url", "visible", "zorder"
                 ]

defaultCatWidth = 0.003 # this is a percentage of the x-range
defaultSpecStyle = {"aa":True}
defaultCatStyle = {
    "aa" : True,
    "linestyle" : "None"
}

####### PLOT ##################

def set_plot_options(xlabel = None,
                     ylabel = None,
                     xscale = "linear",
                     yscale = "linear",
                     xmin = None,
                     xmax = None,
                     ymin = None,
                     ymax = None,
                     fmt = 'none',
                     title = None,
                     fig = None, # use a previously-defined figure
                     ax = None, # use a previously-defined axis
                     ):

    ### work out the figure and axes to use
    if all([i is None for i in (fig, ax)]):
        fig, ax = plt.subplots()
    elif ax is not None and fig is None:
        fig = ax.figure
    elif fig is not None and ax is None:
        ax = fig.add_axes()

    ### set plot options
    if xlabel is not None:
        ax.set_xlabel(xlabel)
    else:
        if len(spectra)>0 and hasattr(spectra[0], 'xlabel'):
            ax.set_xlabel(spectra[0].xlabel)

    if ylabel is not None:
        ax.set_ylabel(ylabel)
    else:
        if len(spectra)>0 and hasattr(spectra[0], 'ylabel'):
            ax.set_ylabel(spectra[0].ylabel)

    if xscale == 'log':
        ax.set_xscale(xscale, nonposx='clip')
    else:
        ax.set_xscale(xscale)
    if yscale == 'log':
        ax.set_yscale(yscale, nonposy='clip')
    else:
        ax.set_yscale(yscale)

    if ymin is not None and ymax is not None:
        ax.set_ylim([ymin, ymax])
    if xmin is not None and xmax is not None:
        ax.set_xlim([xmin, xmax])
    if title is not None:
        ax.set_title(title)

    results = {
        "fig": fig,
        "ax": ax}

    return results


def plot_data_with_errorbars(spectra = [],
                             legend = True,
                             xlabel = None,
                             ylabel = None,
                             xscale = "linear",
                             yscale = "linear",
                             xmin = None,
                             xmax = None,
                             ymin = None,
                             ymax = None,
                             fmt = 'none',
                             title = None,
                             fig = None, # use a previously-defined figure
                             ax = None, # use a previously-defined axis
                             ):

    ### check inputs
    if spectra is None:
        spectra = []
    elif not isinstance(spectra, list):
        # data contains only one spectrum
        # -> make it iterable
        spectra = [spectra]

    ### work out the figure and axes to use
    if all([i is None for i in (fig, ax)]):
        fig, ax = plt.subplots()
    elif ax is not None and fig is None:
        fig = ax.figure
    elif fig is not None and ax is None:
        ax = fig.add_axes()

    ### set plot options
    results = set_plot_options(
        xlabel=xlabel, ylabel=ylabel,
        xscale=xscale, yscale=yscale,
        xmin=xmin, xmax=xmax,
        ymin=ymin, ymax=ymax,
        fmt=fmt, title=title,
        fig=fig, ax=ax)
    fig = results["fig"]
    ax = results["ax"]

    plots = []

    ### add plots of spectra
    def generate_points(x,
                        y,
                        dx = None,
                        dy = None,
                        label = None,
                        color = 'b',
                        fmt = 'none'
                        ):
        return ax.errorbar(x = x,
                    y = y,
                    yerr = dy,
                    xerr = dx,
                    label = label,
                    ecolor = color,
                    fmt = fmt
                    )

    for idx,spec in enumerate(spectra):
        style = dict(defaultSpecStyle)
        label, x, y = None, None, None
        # identify style
        if isinstance(spec, dict): # for paired styles
            # update the style
            for key in Line2DProperties:
                if key in spec:
                    if (key == 'color' and
                      isinstance(spec['color'], (list, tuple)) and
                      all([isinstance(color, int) for color in spec['color']])):
                        spec['color'] = miscfunctions.RGBtoRgbF(spec['color'])
                    style[key] = spec[key]
            if 'label' in spec:
                label = spec['label']
            elif 'name' in spec:
                label = spec['name']
            if 'x' in spec:
                x = spec['x']
            if 'y' in spec:
                y = spec['y']
            if 'spec' in spec:
                spec = spec['spec']
            else:
                spec = sp.Spectrum(x, y)
        else:
            if not isinstance(spec, sp.Spectrum):
                msg = "You must input either:\n"
                msg += "\ta) a Spectrum object, or\n"
                msg += "\tb) a dictionary containing at least 'x' and 'y' entries."
                raise NotImplementedError(msg)
        if label is None:
            if isinstance(legend, list) and len(legend) > idx:
                label = legend[idx]
            elif hasattr(spec, 'legend'):
                label = spec.legend
            elif hasattr(spec, 'title'):
                label = spec.title
            elif hasattr(spec, 'h') and 'title' in spec.h:
                label = spec.h['title']
            elif hasattr(spec, 'h') and 'sourcefile' in spec.h:
                label = spec.h['sourcefile']
        style['label'] = label

        if x is None:
            x = spec.x
        if y is None:
            y = spec.y
        if hasattr(spec, 'fit_x') and hasattr(spec, 'fit_y'):
            p, = ax.plot(spec.fit_x, spec.fit_y, **style)
        else:
            p, = ax.plot(x, y, **style)
        plots.append(p)

        if not hasattr(spec, 'dx'):
            spec.dx = None
        if not hasattr(spec, 'dy'):
            spec.dy = None
        if spec.dx is not None or spec.dy is not None:
            g = generate_points(x = x,
                                y = y,
                                dy = spec.dy,
                                dx = spec.dx,
                                fmt = fmt,
                                color=p.get_color()
                                )
            plots.append(g)

    ### (optionally) update legend after adding plots
    if legend:
        legend = ax.legend()
        try:
            legend.set_draggable(True)
        except:
            pass

    results = {
        "fig": fig,
        "ax": ax,
        "plots": plots}

    return results


def plot_line_catalogs(catalogs = [],
                       legend = True,
                       xlabel = None,
                       ylabel = None,
                       xscale = "linear",
                       yscale = "linear",
                       xmin = None,
                       xmax = None,
                       ymin = None,
                       ymax = None,
                       fmt = 'none',
                       title = None,
                       fig = None, # use a previously-defined figure
                       ax = None, # use a previously-defined axis
                       ):
    ### check inputs
    if catalogs is None:
        catalogs = []
    elif not isinstance(catalogs, list):
        # data contains only one catalog
        # -> make it iterable
        catalogs = [catalogs]

    ### work out the figure and axes to use
    if all([i is None for i in (fig, ax)]):
        fig, ax = plt.subplots()
    elif ax is not None and fig is None:
        fig = ax.figure
    elif fig is not None and ax is None:
        ax = fig.add_axes()

    ### set plot options
    results = set_plot_options(
        xlabel=xlabel, ylabel=ylabel,
        xscale=xscale, yscale=yscale,
        xmin=xmin, xmax=xmax,
        ymin=ymin, ymax=ymax,
        fmt=fmt, title=title,
        fig=fig, ax=ax)
    fig = results["fig"]
    ax = results["ax"]

    plots = []

    ### add plots of line catalogs
    for idx,cat in enumerate(catalogs):
        style = dict(defaultCatStyle)
        viewrange = ax.axis()
        style.update({'width': float(defaultCatWidth * float(viewrange[1]-viewrange[0]))})
        label = None
        x, y, xerr = None, None, None
        trot, scale = 300, 1.0
        # identify style
        if isinstance(cat, dict): # for paired styles
            # update the style
            for key in BarProperties:
                if key in cat:
                    if (key == 'color' and
                      isinstance(cat['color'], (list, tuple)) and
                      all([isinstance(color, int) for color in cat['color']])):
                        cat['color'] = miscfunctions.RGBtoRgbF(cat['color'])
                    style[key] = cat[key]
            if 'label' in cat:
                label = cat['label']
            elif 'name' in cat:
                label = cat['name']
            if 'x' in cat:
                x = cat['x']
            if 'y' in cat:
                y = cat['y']
            if 'xerr' in cat:
                xerr = cat['xerr']
            if 'scale' in cat:
                scale = cat['scale']
            if 'trot' in cat:
                trot = cat['trot']
            cat = cat['cat']
        if not isinstance(cat, catalog.Predictions):
            print("Only Catalog.catalog.Predictions are supported for catalogs..")
            continue
        if label is None:
            label = cat.filename
        style['label'] = label
        # add to plot
        if x is None and y is None:
            idx, y = cat.temperature_rescaled_intensities(freq_min=xmin, freq_max=xmax, trot=trot)
            x, xerr = [], []
            for i in idx:
                x.append(cat.transitions[i].calc_freq)
                xerr.append(cat.transitions[i].calc_unc)
            xerr = np.asarray(xerr)
        x, y = np.asarray(x), np.asarray(y)
        y *= scale
        style['xerr'] = xerr
        p = ax.bar(x, y, **style)
        plots.append(p)

    ### (optionally) update legend after adding plots
    if legend:
        legend = ax.legend()
        try:
            legend.set_draggable(True)
        except:
            pass

    results = {
        "fig": fig,
        "ax": ax,
        "plots": plots}

    return results

def getColormap(lib="matplotlib",
                palette="nipy_spectral",
                format="rgb",
                num=0,
                randomize=False,
                lowerLimit=0.0,
                upperLimit=1.0):
    """
    Provides a wrapper for getting a list of colors, based on many different
    color schemes/colormaps.

    Original source:
    JCL's "ggackal" package, MIT License, https://bitbucket.org/notlaast/ggackal/
    """
    # see https://lisacharlotterost.github.io/2016/04/22/Colors-for-DataVis/
    # do something with https://xkcd.com/color/rgb/
    def hex_to_rgbtuples(hexcolors):
        # return [[ord(c) for c in h[1:].decode('hex')] for h in hexcolors]
        return [tuple(int(h[1:][i:i+2], 16) for i in range(0, 6, 2)) for h in hexcolors]
    def float2index(f,num):
        return np.argmin([np.abs(x-f) for x in np.arange(num)])
    misc = [
        "cielab256", # https://stackoverflow.com/questions/33295120/how-to-generate-gif-256-colors-palette/33295456
        "coloralphabet26", # https://graphicdesign.stackexchange.com/a/3815
        "gilbertson", # https://graphicdesign.stackexchange.com/a/3686
        ]
    if palette in misc:
        if palette == "cielab256":
            if num > 256:
                raise RuntimeError("the cielab256 palette only supports a maximum of 256 colors: %g" % num)
            hexcolors = ["#B88183", "#922329", "#5A0007", "#D7BFC2", "#D86A78", "#FF8A9A", "#3B000A",
                "#E20027", "#943A4D", "#5B4E51", "#B05B6F", "#FEB2C6", "#D83D66", "#895563", "#FF1A59",
                "#FFDBE5", "#CC0744", "#CB7E98", "#997D87", "#6A3A4C", "#FF2F80", "#6B002C", "#A74571",
                "#C6005A", "#FF5DA7", "#300018", "#B894A6", "#FF90C9", "#7C6571", "#A30059", "#DA007C",
                "#5B113C", "#402334", "#D157A0", "#DDB6D0", "#885578", "#962B75", "#A97399", "#D20096",
                "#E773CE", "#AA5199", "#E704C4", "#6B3A64", "#FFA0F2", "#6F0062", "#B903AA", "#C895C5",
                "#FF34FF", "#320033", "#DBD5DD", "#EEC3FF", "#BC23FF", "#671190", "#201625", "#F5E1FF",
                "#BC65E9", "#D790FF", "#72418F", "#4A3B53", "#9556BD", "#B4A8BD", "#7900D7", "#A079BF",
                "#958A9F", "#837393", "#64547B", "#3A2465", "#353339", "#BCB1E5", "#9F94F0", "#9695C5",
                "#0000A6", "#000035", "#636375", "#00005F", "#97979E", "#7A7BFF", "#3C3E6E", "#6367A9",
                "#494B5A", "#3B5DFF", "#C8D0F6", "#6D80BA", "#8FB0FF", "#0045D2", "#7A87A1", "#324E72",
                "#00489C", "#0060CD", "#789EC9", "#012C58", "#99ADC0", "#001325", "#DDEFFF", "#59738A",
                "#0086ED", "#75797C", "#BDC9D2", "#3E89BE", "#8CD0FF", "#0AA3F7", "#6B94AA", "#29607C",
                "#404E55", "#006FA6", "#013349", "#0AA6D8", "#658188", "#5EBCD1", "#456D75", "#0089A3",
                "#B5F4FF", "#02525F", "#1CE6FF", "#001C1E", "#203B3C", "#A3C8C9", "#00A6AA", "#00C6C8",
                "#006A66", "#518A87", "#E4FFFC", "#66E1D3", "#004D43", "#809693", "#15A08A", "#00846F",
                "#00C2A0", "#00FECF", "#78AFA1", "#02684E", "#C2FFED", "#47675D", "#00D891", "#004B28",
                "#8ADBB4", "#0CBD66", "#549E79", "#1A3A2A", "#6C8F7D", "#008941", "#63FFAC", "#1BE177",
                "#006C31", "#B5D6C3", "#3D4F44", "#4B8160", "#66796D", "#71BB8C", "#04F757", "#001E09",
                "#D2DCD5", "#00B433", "#9FB2A4", "#003109", "#A3F3AB", "#456648", "#51A058", "#83A485",
                "#7ED379", "#D1F7CE", "#A1C299", "#061203", "#1E6E00", "#5EFF03", "#55813B", "#3B9700",
                "#4FC601", "#1B4400", "#C2FF99", "#788D66", "#868E7E", "#83AB58", "#374527", "#98D058",
                "#C6DC99", "#A4E804", "#76912F", "#8BB400", "#34362D", "#4C6001", "#DFFB71", "#6A714A",
                "#222800", "#6B7900", "#3A3F00", "#BEC459", "#FEFFE6", "#A3A489", "#9FA064", "#FFFF00",
                "#61615A", "#FFFFFE", "#9B9700", "#CFCDAC", "#797868", "#575329", "#FFF69F", "#8D8546",
                "#F4D749", "#7E6405", "#1D1702", "#CCAA35", "#CCB87C", "#453C23", "#513A01", "#FFB500",
                "#A77500", "#D68E01", "#B79762", "#7A4900", "#372101", "#886F4C", "#A45B02", "#E7AB63",
                "#FAD09F", "#C0B9B2", "#938A81", "#A38469", "#D16100", "#A76F42", "#5B4534", "#5B3213",
                "#CA834E", "#FF913F", "#953F00", "#D0AC94", "#7D5A44", "#BE4700", "#FDE8DC", "#772600",
                "#A05837", "#EA8B66", "#391406", "#FF6832", "#C86240", "#29201D", "#B77B68", "#806C66",
                "#FFAA92", "#89412E", "#E83000", "#A88C85", "#F7C9BF", "#643127", "#E98176", "#7B4F4B",
                "#1E0200", "#9C6966", "#BF5650", "#BA0900", "#FF4A46", "#F4ABAA", "#000000", "#452C2C",
                "#C8A1A1"]
            rgb_tuples = hex_to_rgbtuples(hexcolors)
        elif palette == "coloralphabet26":
            if num > 26:
                raise RuntimeError("the coloralphabet26 palette only supports a maximum of 26 colors: %g" % num)
            rgb_tuples = [[240,163,255],[0,117,220],[153,63,0],[76,0,92],[25,25,25],[0,92,49],
                [43,206,72],[255,204,153],[128,128,128],[148,255,181],[143,124,0],[157,204,0],
                [194,0,136],[0,51,128],[255,164,5],[255,168,187],[66,102,0],[255,0,16],[94,241,242],
                [0,153,143],[224,255,102],[116,10,255],[153,0,0],[255,255,128],[255,255,0],[255,80,5]]
            rgb_tuples = rgb_tuples[:num]
        elif palette == "gilbertson":
            if num > 24:
                raise RuntimeError("the gilbertson palette only supports a maximum of 24 colors: %g" % num)
            rgb_tuples = [[255,0,0], [228,228,0], [0,255,0], [0,255,255], [176,176,255], [255,0,255],
                [228,228,228], [176,0,0], [186,186,0], [0,176,0], [0,176,176], [132,132,255], [176,0,176],
                [186,186,186], [135,0,0], [135,135,0], [0,135,0], [0,135,135], [73,73,255], [135,0,135],
                [135,135,135], [85,0,0], [84,84,0], [0,85,0], [0,85,85], [0,0,255], [85,0,85], [84,84,84]]
            rgb_tuples = rgb_tuples[:num]
        if randomize:
            rgb_tuples = random.sample(rgb_tuples, k=len(rgb_tuples))
        rgb_tuples = [rgb_tuples[int(np.round(i*(len(rgb_tuples)-1)))] for i in np.linspace(lowerLimit, upperLimit, num)]
    elif lib == "matplotlib":
        cm = plt.cm
        # define palettes that contain white colors, so they can be avoided (sort of..)
        whiteTop = [
            "Greys", "Purples", "Blues", "Greens", "Oranges", "Reds",
            "YlOrBr", "YlOrRd", "OrRd", "PuRd", "RdPu", "BuPu",
            "GnBu", "PuBu", "YlGnBu", "PuBuGn", "BuGn", "YlGn",
            "gist_gray", "gray", "bone", "pink",
            "hot", "afmhot", "gist_heat",
            "ocean", "gist_earth", "terrain", "gist_stern",
            "gnuplot2", "CMRmap", "cubehelix",
            "gist_ncar"]
        whiteCenter = [
            "PiYG", "PRGn", "BrBG", "PuOr", "RdGy", "RdBu",
            "RdYlBu", "RdYlGn", "bwr"]
        whiteBottom = [
            "binary", "gist_yarg"]
        if palette in whiteTop:
            upperLimit = 0.9
        elif palette in whiteBottom:
            lowerLimit = 0.1
        elif palette in whiteCenter:
            print("WARNING:")
            print("\tyou are using a color palette (%s) that will likely yield a white color!" % palette)
            print("\tyou might want to avoid these (%s)" % whiteCenter)
            print("\tsee https://matplotlib.org/users/colormaps.html for alternatives")
        try:
            colormap = getattr(cm, "%s" % palette)
        except AttributeError:
            print("WARNING: you tried to request a color palette (%s) from matplotlib that doesn't appear to exist!" % palette)
            print("Trying 'cmocean' next..")
            print("\tIf that's not what you want, see https://matplotlib.org/users/colormaps.html for alternatives")
            return getColormap(format=format, num=num, lib="cmocean", palette=palette)
        rgb_tuples = [colormap(i)[:-1] for i in np.linspace(lowerLimit, upperLimit, num)]
        rgb_tuples = [[int(c*255) for c in rgb] for rgb in rgb_tuples]
    elif lib == "cmocean":
        # http://matplotlib.org/cmocean/
        try:
            from cmocean import cm, tools
        except ImportError:
            print("WARNING: could not import cmocean! try 'pip install cmocean' next time.. returning the default for now..")
            return getColormap(format=format, num=num)
        try:
            colormap = getattr(cm, "%s" % palette)
        except AttributeError:
            print("WARNING: you tried to request a color palette '%s' from cmocean that doesn't appear to exist!" % palette)
            print("Reverting to defaults..")
            print("\tsee http://matplotlib.org/cmocean/ for alternatives")
            return getColormap(format=format, num=num)
        rgb_dict = tools.get_dict(colormap, N=num)
        rgb_tuples = []
        for i in range(num):
            rgb_tuples.append((rgb_dict["red"][i][1], rgb_dict["green"][i][1], rgb_dict["blue"][i][1]))
        rgb_tuples = [[int(c*255) for c in rgb] for rgb in rgb_tuples]
    if format == "rgb":
        return rgb_tuples
    elif format == "html":
        return ["#"+''.join(["%0.2X" % c for c in rgb]).lower() for rgb in rgb_tuples]
    else:
        return None
