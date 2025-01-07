# -*- coding: utf-8 -*-
#
# Copyright 2009 Pierre Raybaut
# Licensed under the terms of the MIT License
# see the mpl licenses directory for a copy of the license
#
# Edited by Jacob Laas (Copyright 2020) to support additional
# options.
#
"""Module that provides a GUI-based editor for matplotlib's figure options."""
from __future__ import (absolute_import, division, print_function,
                        unicode_literals)

import os.path
import re
import math

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import cm, colors as mcolors, markers, image as mimage, ticker
import matplotlib.backends.qt_editor.formlayout as formlayout
from matplotlib.backends.qt_compat import QtGui


def get_icon(name):
    basedir = os.path.join(matplotlib.rcParams['datapath'], 'images')
    return QtGui.QIcon(os.path.join(basedir, name))

FONTSIZES = {
    5.789999999999999: '05.8: (xx-small)',
    6.9399999999999995: '06.9: (x-small)',
    8.33: '08.3: (small)',
    10.0: '10: (medium)',
    12.0: '12: (large)',
    14.399999999999999: '14.4: (x-large)',
    17.28: '17.3 (xx-large)',
}
for x in range(2, 41):
    if not x in FONTSIZES.keys():
        FONTSIZES[x] = "%02d" % x

FONTSTRETCHES = {
    'ultra-condensed': 'ultra-condensed',
    'extra-condensed': 'extra-condensed',
    'condensed': 'condensed',
    'semi-condensed': 'semi-condensed',
    'normal': 'normal',
    'semi-expanded': 'semi-expanded',
    'expanded': 'expanded',
    'extra-expanded': 'extra-expanded',
    'ultra-expanded': 'ultra-expanded'
}

FONTWEIGHTS = {
    'ultralight': 'ultralight',
    'light': 'light',
    'normal': 'normal',
    'regular': 'regular',
    'book': 'book',
    'medium': 'medium',
    'roman': 'roman',
    'semibold': 'semibold',
    'demibold': 'demibold',
    'demi': 'demi',
    'bold': 'bold',
    'heavy': 'heavy',
    'extra': 'extra',
    'bold': 'bold',
    'black': 'black'
}

TICKNUMBER = {
    "off": "off",
    0: "off",
    "auto": "auto",
    "manual": "manual",
}
for x in range(1, 11):
    TICKNUMBER[x] = "%02d" % x

TICKNUMBERMINOR = TICKNUMBER.copy()
TICKNUMBERMINOR.pop("manual")

TICKSTYLES = {
    "in": "in",
    "both": "both",
    "out": "out",
}

TICKOFFSETS = {
    True: "Auto",
    False: "Off",
}

TICKPOSITIONX = {
    "bottom": "bottom",
    "top": "top",
    "both": "both"
}
TICKPOSITIONY = {
    "left": "left",
    "right": "right",
    "both": "both"
}

LINESTYLES = {'-': 'Solid',
              '--': 'Dashed',
              '-.': 'DashDot',
              ':': 'Dotted',
              'None': 'None',
              }

DRAWSTYLES = {
    'default': 'Default',
    'steps-pre': 'Steps (Pre)', 'steps': 'Steps (Pre)',
    'steps-mid': 'Steps (Mid)',
    'steps-post': 'Steps (Post)'}

HATCHSTYLES = {
    None : "none",
    "/" : "diagonal hatching",
    "\\": "back diagonal",
    "|" : "vertical",
    "-" : "horizontal",
    "+" : "crossed",
    "x" : "crossed diagonal",
    "o" : "small circle",
    "O" : "large circle",
    "." : "dots",
    "*" : "stars"}

MARKERS = markers.MarkerStyle.markers

TEXTVERTALIGN = {
    'center':'center',
    'top':'top',
    'bottom':'bottom',
    'baseline':'baseline',
    'center_baseline':'center_baseline'
}

TEXTHORIZALIGN = {
    'center':'center',
    'left':'left',
    'right':'right'
}

def figure_edit(axes, parent=None):
    """Edit matplotlib figure options"""
    

    def prepare_data(d, init):
        """Prepare entry for FormLayout.

        `d` is a mapping of shorthands to style names (a single style may
        have multiple shorthands, in particular the shorthands `None`,
        `"None"`, `"none"` and `""` are synonyms); `init` is one shorthand
        of the initial style.

        This function returns an list suitable for initializing a
        FormLayout combobox, namely `[initial_name, (shorthand,
        style_name), (shorthand, style_name), ...]`.
        """
        if init not in d:
            d[init] = str(init)
        # Drop duplicate shorthands from dict (by overwriting them during
        # the dict comprehension).
        name2short = {name: short for short, name in d.items()}
        # Convert back to {shorthand: name}.
        short2name = {short: name for name, short in name2short.items()}
        # Find the kept shorthand for the style specified by init.
        canonical_init = name2short[d[init]]
        # Sort by representation and prepend the initial value.
        return ([canonical_init] +
                sorted(short2name.items(),
                       key=lambda short_and_name: short_and_name[1]))
    
    sep = (None, None)  # separator

    # Get / General
    # Cast to builtin floats as they have nicer reprs.
    xmin, xmax = map(float, axes.get_xlim())
    ymin, ymax = map(float, axes.get_ylim())
    if len(axes._left_title.get_text()):
        title = axes._left_title
        tpos = "left"
    elif len(axes._right_title.get_text()):
        title = axes._right_title
        tpos = "right"
    else:
        title = axes.title
        tpos = "center"
    general = [('Title', title.get_text()),
               ('Size', prepare_data(FONTSIZES, title.get_fontsize())),
               ('Position', [tpos, "left","center","right"]),
               sep,
               (None, "<b>X-Axis</b>"),
               ('Left', xmin), ('Right', xmax),
               ('Label', axes.get_xlabel()),
               ('Size', prepare_data(FONTSIZES, axes.xaxis.label.get_fontsize())),
               ('Scale', [axes.get_xscale(), 'linear', 'log', 'logit']),
               sep,
               (None, "<b>Y-Axis</b>"),
               ('Bottom', ymin), ('Top', ymax),
               ('Label', axes.get_ylabel()),
               ('Size', prepare_data(FONTSIZES, axes.yaxis.label.get_fontsize())),
               ('Scale', [axes.get_yscale(), 'linear', 'log', 'logit']),
               sep,
               ('(Re-)Generate automatic legend', False),
               ]

    # Save the unit data
    xconverter = axes.xaxis.converter
    yconverter = axes.yaxis.converter
    xunits = axes.xaxis.get_units()
    yunits = axes.yaxis.get_units()

    # Get / Label Ticks
    ticks = [('X Ticks', ", ".join(["%s" % tick for tick in list(axes.get_xticks())])),
             ('Major', prepare_data(TICKNUMBER, 'auto')),
             ('Minor', prepare_data(TICKNUMBERMINOR, math.ceil(len(axes.get_xminorticklabels())/len(axes.get_xticklabels())))),
             ('Label size', prepare_data(FONTSIZES, axes.get_xticklabels()[0].get_fontsize())),
             ('Style', prepare_data(TICKSTYLES, axes.xaxis.properties()['ticks_direction'][0])),
             ('Use offset', prepare_data(TICKOFFSETS, bool(len(axes.xaxis.properties()['offset_text'].get_text())))),
             ('Scale', ""),
             ('Position', prepare_data(TICKPOSITIONX, axes.xaxis.properties()['ticks_position'])),
             ('Grid', axes.xaxis._gridOnMajor),
             sep,
             ('Y Ticks', ", ".join(["%s" % tick for tick in list(axes.get_yticks())])),
             ('Major', prepare_data(TICKNUMBER, 'auto')),
             ('Minor', prepare_data(TICKNUMBERMINOR, math.ceil(len(axes.get_yminorticklabels())/len(axes.get_yticklabels())))),
             ('Label size', prepare_data(FONTSIZES, axes.get_yticklabels()[0].get_fontsize())),
             ('Style', prepare_data(TICKSTYLES, axes.yaxis.properties()['ticks_direction'][0])),
             ('Use offset', prepare_data(TICKOFFSETS, bool(len(axes.yaxis.properties()['offset_text'].get_text())))),
             ('Scale', ""),
             ('Position', prepare_data(TICKPOSITIONY, axes.yaxis.properties()['ticks_position'])),
             ('Grid', axes.yaxis._gridOnMajor)]

    # Sorting for default labels (_lineXXX, _imageXXX).
    def cmp_key(label):
        match = re.match(r"(_annotation|_line|_image|_annotation|_container)(\d+)", label)
        if match:
            return match.group(1), int(match.group(2))
        else:
            return label, 0

    # Get / Annotations
    annotationdict = {}
    for text in axes.texts:
        label = text.get_text()
        annotationdict[label] = text
    annotations = []

    annotationlabels = sorted(annotationdict, key=cmp_key)
    for label in annotationlabels:
        text = annotationdict[label]
        color = mcolors.to_hex(
            mcolors.to_rgba(text.get_color(), text.get_alpha()),
            keep_alpha=True)
        fontproperties = text._fontproperties
        annotationdata = [
            ('Text', label),
            sep,
            (None, '<b>Font Style</b>'),
            ('Color (RGBA)', color),
            ('Font size', prepare_data(FONTSIZES, fontproperties.get_size())),
            ('Font weight', prepare_data(FONTWEIGHTS, fontproperties.get_weight())),
            ('Line spacing', text._linespacing),
            # ('Font stretch', prepare_data(FONTSTRETCHES, fontproperties.get_stretch())),
            sep,
            (None, '<b>Other</b>'),
            ('Pos X', text.get_position()[0]),
            ('Pos Y', text.get_position()[1]),
            ('Vert. Alignment', prepare_data(TEXTVERTALIGN, text.get_verticalalignment())),
            ('Horiz. Alignment', prepare_data(TEXTHORIZALIGN, text.get_horizontalalignment())),
            sep,
            ('Remove', False),
        ]
        annotations.append([annotationdata, label, ""])
    # Is there a curve displayed?
    has_annotation = bool(annotations)

    # Get / Curves
    linedict = {}
    for line in axes.get_lines():
        label = line.get_label()
        if label in (None, '_nolegend_'):
            continue
        linedict[label] = line
    curves = []

    curvelabels = sorted(linedict, key=cmp_key)
    for label in curvelabels:
        line = linedict[label]
        color = mcolors.to_hex(
            mcolors.to_rgba(line.get_color(), line.get_alpha()),
            keep_alpha=True)
        ec = mcolors.to_hex(
            mcolors.to_rgba(line.get_markeredgecolor(), line.get_alpha()),
            keep_alpha=True)
        fc = mcolors.to_hex(
            mcolors.to_rgba(line.get_markerfacecolor(), line.get_alpha()),
            keep_alpha=True)
        curvedata = [
            ('Label', label),
            sep,
            (None, '<b>Line</b>'),
            ('Line style', prepare_data(LINESTYLES, line.get_linestyle())),
            ('Draw style', prepare_data(DRAWSTYLES, line.get_drawstyle())),
            ('Width', line.get_linewidth()),
            ('Color (RGBA)', color),
            sep,
            (None, '<b>Marker</b>'),
            ('Style', prepare_data(MARKERS, line.get_marker())),
            ('Size', line.get_markersize()),
            ('Face color (RGBA)', fc),
            ('Edge color (RGBA)', ec)]
        curves.append([curvedata, label, ""])
    # Is there a curve displayed?
    has_curve = bool(curves)

    # Get / Images
    imagedict = {}
    for image in axes.get_images():
        label = image.get_label()
        if label in (None, '_nolegend_'):
            continue
        imagedict[label] = image
    imagelabels = sorted(imagedict, key=cmp_key)
    images = []
    cmaps = [(cmap, name) for name, cmap in sorted(cm.cmap_d.items())]
    for label in imagelabels:
        image = imagedict[label]
        cmap = image.get_cmap()
        if cmap not in cm.cmap_d.values():
            cmaps = [(cmap, cmap.name)] + cmaps
        low, high = image.get_clim()
        imagedata = [
            ('Label', label),
            ('Colormap', [cmap.name] + cmaps),
            ('Min. value', low),
            ('Max. value', high),
            ('Interpolation',
             [image.get_interpolation()]
             + [(name, name) for name in sorted(mimage.interpolations_names)])]
        images.append([imagedata, label, ""])
    # Is there an image displayed?
    has_image = bool(images)

    # Get / Containers (of patches, e.g. BarContainer)
    contdict = {}
    for cont in axes.containers:
        label = cont.get_label()
        if label in (None, '_nolegend_'):
            continue
        contdict[label] = cont
    containers = []

    contlabels = sorted(contdict, key=cmp_key)
    for label in contlabels:
        line = contdict[label][0] # only queries the first patch in the collection
        fc = mcolors.to_hex(
            mcolors.to_rgba(line.get_facecolor()))
        ec = mcolors.to_hex(
            mcolors.to_rgba(line.get_edgecolor()))
        curvedata = [
            ('Label', label),
            sep,
            (None, '<b>Fill</b>'),
            ('Fill style', prepare_data(HATCHSTYLES, line.get_hatch())),
            ('Width', line.get_width()),
            ('Alpha', line.get_alpha()),
            ('Face color (RGBA)', fc),
            sep,
            (None, '<b>Edge</b>'),
            ('Linestyle', prepare_data(LINESTYLES, line.get_linestyle())),
            ('Linewidth', line.get_linewidth()),
            ('Edge color (RGBA)', ec)]
        containers.append([curvedata, label, ""])
    # Is there a curve displayed?
    has_container = bool(containers)

    datalist = [(general, "Axes", ""),
                (ticks, "Ticks", "")]
    if annotations:
        datalist.append((annotations, "Annotations", ""))
    if curves:
        datalist.append((curves, "Curves", ""))
    if images:
        datalist.append((images, "Images", ""))
    if containers:
        datalist.append((containers, "Others", ""))

    def apply_callback(data):
        """This function will be called to apply changes"""
        orig_xlim = axes.get_xlim()
        orig_ylim = axes.get_ylim()

        general = data.pop(0)
        ticks = data.pop(0)
        annotations = data.pop(0) if has_annotation else []
        curves = data.pop(0) if has_curve else []
        images = data.pop(0) if has_image else []
        containers = data.pop(0) if has_container else []
        if data:
            raise ValueError("Unexpected field")

        # Set / General
        (title, titlesize, titleposition,
         xmin, xmax, xlabel, xlabelsize, xscale,
         ymin, ymax, ylabel, ylabelsize, yscale,
         generate_legend) = general

        if axes.get_xscale() != xscale:
            axes.set_xscale(xscale)
        if axes.get_yscale() != yscale:
            axes.set_yscale(yscale)

        axes.set_title(title, fontsize=titlesize, loc=titleposition)
        axes.set_xlim(xmin, xmax)
        axes.set_xlabel(xlabel, fontsize=xlabelsize)
        axes.set_ylim(ymin, ymax)
        axes.set_ylabel(ylabel, fontsize=ylabelsize)

        # Restore the unit data
        axes.xaxis.converter = xconverter
        axes.yaxis.converter = yconverter
        axes.xaxis.set_units(xunits)
        axes.yaxis.set_units(yunits)
        axes.xaxis._update_axisinfo()
        axes.yaxis._update_axisinfo()

        # Set / Ticks
        (xticks, xtmaj, xtmin, xtsize, xtstyle, xtoffset, xtscale, xtpos, xgrid,
         yticks, ytmaj, ytmin, ytsize, ytstyle, ytoffset, ytscale, ytpos, ygrid,
        ) = ticks
        # general
        if xtmin == "off" and ytmin == "off":
            axes.minorticks_off()
        else:
            axes.minorticks_on()
        # x
        if xtmaj == "manual":
            axes.set_xticks(list(map(float, xticks.split(","))))
        elif xtmaj == "auto":
            axes.xaxis.set_major_locator(plt.AutoLocator())
        elif xtmaj == "off":
            axes.xaxis.set_major_locator(plt.NullLocator())
        else:
            axes.xaxis.set_major_locator(plt.MaxNLocator(int(xtmaj)))
        if xtmin in ("off", 0):
            axes.xaxis.set_minor_locator(plt.NullLocator())
        elif xtmin == "auto":
            axes.xaxis.set_minor_locator(ticker.AutoMinorLocator())
        elif xtmin == "manual":
            pass
        else:
            axes.xaxis.set_minor_locator(plt.MaxNLocator(xtmin*len(axes.get_xticklabels())))
        for tick in axes.get_xticklabels():
            tick.set_fontsize(xtsize)
        if xtstyle == "both":
            xtstyle = "inout"
        axes.tick_params(axis='x', direction=xtstyle, length=plt.rcParams['xtick.major.size']) # length fixes a bug
        if isinstance(axes.xaxis.get_major_formatter(), ticker.ScalarFormatter):
            axes.ticklabel_format(axis='x', useOffset=xtoffset)
        if len(xtscale):
            try:
                xtscale = float(xtscale)
                xticks = ticker.FuncFormatter(lambda x, pos: '{0:g}'.format(x*xtscale))
                axes.xaxis.set_major_formatter(xticks)
            except:
                pass
        axes.xaxis.set_ticks_position(xtpos)
        axes.grid(b=xgrid, axis='x')
        # y
        if ytmaj == "manual":
            axes.set_yticks(list(map(float, yticks.split(","))))
        elif ytmaj == "auto":
            axes.yaxis.set_major_locator(plt.AutoLocator())
        elif ytmaj == "off":
            axes.yaxis.set_major_locator(plt.NullLocator())
        else:
            axes.yaxis.set_major_locator(plt.MaxNLocator(int(ytmaj)))
        if ytmin == "auto":
            axes.yaxis.set_minor_locator(ticker.AutoMinorLocator())
        elif ytmin in ("off", 0):
            axes.yaxis.set_minor_locator(plt.NullLocator())
        elif ytmin == "manual":
            pass
        else:
            axes.xaxis.set_minor_locator(plt.MaxNLocator(ytmin*len(axes.get_yticklabels())))
        for tick in axes.get_yticklabels():
            tick.set_fontsize(ytsize)
        if ytstyle == "both":
            ytstyle = "inout"
        axes.tick_params(axis='y', direction=ytstyle, length=plt.rcParams['ytick.major.size'])
        if isinstance(axes.yaxis.get_major_formatter(), ticker.ScalarFormatter):
            axes.ticklabel_format(axis='y', useOffset=ytoffset)
        if len(ytscale):
            try:
                ytscale = float(ytscale)
                yticks = ticker.FuncFormatter(lambda y, pos: '{0:g}'.format(y*ytscale))
                axes.yaxis.set_major_formatter(yticks)
            except:
                pass
        axes.yaxis.set_ticks_position(ytpos)
        axes.grid(b=ygrid, axis='y')

        # Set / Annotations
        for index, annotation in enumerate(annotations):
            text = annotationdict[annotationlabels[index]]
            (
                label, color,
                fontsize, fontweight, linespacing,
                # fontstretch, # basically no effect
                posx, posy,
                alignvert, alignhoriz,
                remove
            ) = annotation
            if remove:
                text.remove()
                continue
            label = label.replace('\\n', '\n')
            text.set_text(label)
            text.set_color(color)
            text.set_fontsize(fontsize)
            text.set_fontweight(fontweight)
            text.set_linespacing(linespacing)
            # text.set_fontstretch(fontstretch)
            text.set_x(posx)
            text.set_y(posy)
            text.set_va(alignvert)
            text.set_ha(alignhoriz)

        # Set / Curves
        for index, curve in enumerate(curves):
            line = linedict[curvelabels[index]]
            (label, linestyle, drawstyle, linewidth, color, marker, markersize,
             markerfacecolor, markeredgecolor) = curve
            line.set_label(label)
            line.set_linestyle(linestyle)
            line.set_drawstyle(drawstyle)
            line.set_linewidth(linewidth)
            rgba = mcolors.to_rgba(color)
            line.set_alpha(None)
            line.set_color(rgba)
            if marker is not 'none':
                line.set_marker(marker)
                line.set_markersize(markersize)
                line.set_markerfacecolor(markerfacecolor)
                line.set_markeredgecolor(markeredgecolor)

        # Set / Images
        for index, image_settings in enumerate(images):
            image = imagedict[imagelabels[index]]
            label, cmap, low, high, interpolation = image_settings
            image.set_label(label)
            image.set_cmap(cm.get_cmap(cmap))
            image.set_clim(*sorted([low, high]))
            image.set_interpolation(interpolation)

        # Set / Containers
        for index, container in enumerate(containers):
            line = contdict[contlabels[index]]
            (
                label,
                hatch, width, alpha, facecolor,
                linestyle, linewidth, edgecolor) = container
            if linestyle == "None":
                linewidth = 0
            #[rect.set_label(label) for rect in line]
            line.set_label(label)
            [rect.set_hatch(hatch) for rect in line]
            [rect.set_width(width) for rect in line]
            [rect.set_alpha(alpha) for rect in line]
            [rect.set_facecolor(facecolor) for rect in line]
            [rect.set_linestyle(linestyle) for rect in line]
            [rect.set_linewidth(linewidth) for rect in line]
            [rect.set_edgecolor(edgecolor) for rect in line]

        # re-generate legend, if checkbox is checked
        if generate_legend:
            draggable = None
            ncol = 1
            if axes.legend_ is not None:
                old_legend = axes.get_legend()
                draggable = old_legend._draggable is not None
                ncol = old_legend._ncol
            new_legend = axes.legend(ncol=ncol)
            if new_legend:
                new_legend.set_draggable(draggable)

        # Redraw
        figure = axes.get_figure()
        figure.canvas.draw()
        if not (axes.get_xlim() == orig_xlim and axes.get_ylim() == orig_ylim):
            figure.canvas.toolbar.push_current()

    data = formlayout.fedit(datalist, title="Figure options", parent=parent,
                            icon=get_icon('qt4_editor_options.svg'),
                            apply=apply_callback)
    if data is not None:
        apply_callback(data)
