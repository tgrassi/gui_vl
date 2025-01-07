pyLabSpec - a spectroscopy library
==================================



Summary
-------

#### Description

This repository holds a number of python-based libraries allowing the control of laboratory instruments and spectral analysis/visualization. The primary focus is on rotational spectroscopy at mm/submm wavelengths, but the libraries are general enough to be extended to other wavelengths/units as the need/interest arises.

This software has grown organically, having been inspired by a number of other software projects and spectroscopy laboratories around the world. PyLabSpec has grown simply out of need during the development of the new research laboratories of [CAS@MPE](http://www.mpe.mpg.de/CAS), with the focus being on a self-sufficient toolkit for efficient molecular spectroscopy.

Bugs are fixed as they are found, but feel free to let us know if you have discovered an issue or a solution for any major problems.


#### Feature Overview

The directories in this repository contain a number of different libraries/modules for various functionality:

- `/doc` - Documentation.
- `/pyLabSpec/Catalog` - Handle molecular line catalogs.
    - supports [Picket's calpgm](https://spec.jpl.nasa.gov/) (spfit/spcat) files for mm/submm rotational spectroscopy
- `/pyLabSpec/External` - Used for (optionally) housing external packages.
    - `vamdclib` is available for interfacing to the [VAMDC consortium](http://portal.vamdc.org/vamdc_portal/home.seam), and is activated via the [git-submodule](https://git-scm.com/docs/git-submodule) plugin
- `/pyLabSpec/Fit` - Libraries to fit data (kinetics & line profiles).
    - supports a number of line profiles, including gaussian/lorentzian/voigt/galatry profiles, plus their 2f (second harmonic) and/or speed-dependent versions
- `/pyLabSpec/GUIs` - GUIs for spectrometer software and data analysis/visualization.
    - Two separate (but similar) interfaces for operating mm/submm CAS spectrometers
    - Includes the "QtFit" interface for overlaying spectra/line catalogs (including directly browsing/downloading from the [JPL](https://spec.jpl.nasa.gov/ftp/pub/catalog/catdir.html) and [CDMS](https://www.astro.uni-koeln.de/cdms/entries) databases), basic statistics of windowed spectral data, baseline removal, interactive line assignments, and real-time interaction of an spfit project
    - Includes the "QtProLineFitter" interface for running (multi)-line fits on spectral data
- `/pyLabSpec/Instruments` - Library to control instrument devices.
    - Provides modules for handling communication to instruments connected via GPIB/USB/serial/ethernet
    - Wrappers provide python-based controls to:
        - [Keysight PSG](http://www.keysight.com/en/pdx-x202237-pn-E8257D/) analog synthesizers,
        - a [Keysight AWG](http://www.keysight.com/en/pc-1000000231%3Aepsg%3Apgr/function-arbitrary-waveform-generators),
        - [SRS SR8XX](http://www.thinksrs.com/products/SR810830.htm) and [ZI MFLI](http://www.zhinst.com/products/mfli) digital lock-in amplifiers,
        - a [Keithley 2100](http://www.tek.com/tektronix-and-keithley-digital-multimeter/keithley-2100-series-6%C2%BD-digit-usb-multimeter) digital multimeters,
        - a number of [Leybold](http://www.leyboldproducts.uk/products/vacuum-measuring/) and [Pfeiffer](http://www.pfeiffer-vacuum.com/en/products/measurement/) pressure gauges/readouts,
        - a [Keysight PCIe digitizer](http://www.keysight.com/en/pc-1881370/PCIe-Digitizers-and-Related-Product),
        - MKS [647C](http://www.mksinst.com/docs/UR/647.pdf) and [946](http://www.mksinst.com/product/product.aspx?ProductID=1434) mass flow controllers,
        - the [SRS DG645](http://www.thinksrs.com/products/DG645.htm) digital delay generator
        - a number of Tektronix & Keysight digital oscilloscopes
- `/pyLabSpec/Scripts` - Miscellaneous scripts for predefined processes.
    - Includes a script for preparing chirp waveforms
    - Batch scripts for running pre-defined series of chirped-pulse acquisitions
    - Includes an advanced commandline tool for reading/storing values from a tabletop digital multimeter
- `/pyLabSpec/Simulations` - Library to perform spectral simulations.
- `/pyLabSpec/Spectrum` - Library to manage (plot, ...) spectra and their file formats.
    - Supports the loading/viewing of comma-/tab-/whitespace-/arbitrarily-delimited 2D (freq vs intensity) spectral files, as well as a few proprietary formats (those of JPL & U. di Bologna).



Installation
------------

#### Runtime Dependencies

- python (v2.7.x or v3.6+)
- [scipy](https://www.scipy.org/) (v0.17+)
- [numpy](http://www.numpy.org/) (v1.14+)


#### Optional Dependencies
- [linux-gpib](http://linux-gpib.sourceforge.net/) (GPIB-based instruments only)
- pyserial (instrument module)
- [pyads](https://github.com/chwiede/pyads/) (PLC-based instruments only)
- [pyqtgraph](http://www.pyqtgraph.org/) (GUIs only)
- PyQt4 or PyQt5 (GUIs only)
- matplotlib (plot designer GUI)
- pyFFTW (faster line profile fitting)
- [vamdclib]("https://github.com/notlaast/vamdclib/) (for line catalogs)
- make (to generate docs)
- sphinx (to generate docs)
- graphviz (to generate diagrams in docs)
- latex (to generate latex-based docs)


#### Public Access

The primary home is found under the [GitLab](https://about.gitlab.com/) server of the [MPCDF](http://www.mpcdf.mpg.de/) at [https://gitlab.mpcdf.mpg.de/chre/pyLabSpec](https://gitlab.mpcdf.mpg.de/chre/pyLabSpec). If you have been granted access to this repository, the easiest way of obtaining pyLabSpec is by cloning the [repository](https://gitlab.mpcdf.mpg.de/chre/pyLabSpec):

    >git clone https://gitlab.mpcdf.mpg.de/chre/pyLabSpec.git

Then you can easily update it. Alternatively, the page at [http://www.mpe.mpg.de/~jclaas/pylabspec.php](http://www.mpe.mpg.de/~jclaas/pylabspec.php) contains a link to an archive that may or may not be reasonably updated.


#### Developer Access

One can either [fork](https://gitlab.mpcdf.mpg.de/chre/pyLabSpec/forks/new) or request to join the project. See CONTRIBUTING.md file for more details.


#### General Installation Procedures

This software includes both modules (e.g. classes providing interfaces to instrumentation, classes describing spectra/line catalogs, and classes providing Qt-based widgets) and standalone programs (e.g. spectrometer acquisition software, sensor monitors, data browsers). While the software itself doesn't necessarily require system-wide installation, two general steps must first be taken: a) install the dependencies listed above, and b) either add the parent directory of pyLabSpec to your python executable path, launch python from within the directory, or install the package to your python distribution. Internally, the modules generally perform part (b) automatically upon successful launch of one of the programs or scripts.

Regarding python versions, pyLabSpec supports both v2 and v3 of python. Since Python 2.x will soon reach end-of-life, Python 3.x is recommended. We have now made sure that the GUIs work with both PyQt4 and PyQt5.


#### Installation via PIP

In general, the file "setup.py" keeps track of the required packages, and this is automatically checked by "pip" if you use it for installation. The simplest method of installation is something like (from the pyLabSpec directory):

    >pip install --user -e .

This will automatically install "qtfit.py", "profitter.py", and "read_dmm.py" to your PATH as executables. It will also install pyLabSpec as a python package, and some of the standalone programs can be launched directly, e.g.

    >python -m pyLabSpec.GUIs.qtfit

For more details about installation options using "setup.py", do:

    >python setup.py --help


#### Note about dependencies on Linux (Debian/Ubuntu + apt)

Most of the basic packages are available from the native software repositories, so something like this should suffice:

    >sudo apt-get install python python-scipy python-serial python-numpy

The interfaces are all based on PyQt and the plotting functionalities of the interfaces and Spectrum class rely *heavily* on the pyqtgraph library. It can be found in the apt catalog, but also the python PIP system. Its installation will ensure PyQt is also installed:

    >sudo apt-get install python-pyqtgraph

The line profile fitting relies on the numpy and scipy packages. One of the line profiles is defined in Fourier space, and is able to make use of the `libfftw3` and `pyFFTW` packages to speed up Fourier transforms. `libfftw3` can be installed via:

    >sudo apt-get install libfftw3-dev

To install the python module, it is highly recommended to use the `pip` package manager:

    >pip install --user pyFFTW

Two packages are known not to exist in mainline repositories, and "pip" must be used in any case:

    >pip install --user "git+https://github.com/chwiede/pyads.git"
    >pip install --user "git+https://github.com/notlaast/vamdclib.git"

The *docs* must be generated on the fly. For this, `make` and `sphinx` are required:

    >sudo apt-get install make sphinx

For doc generation, see below for more details.

If you are using an OS from 2014-2018, python 3.x packages are also available separately, so you could replace the package names above with "python3".


#### Notes about Anaconda

[Anaconda](https://anaconda.org/anaconda/python) is currently the most recommended science-related distribution of python, and it is also the least painful method for installing all the external dependencies, especially PyQt and reasonably up-to-date versions of numpy and scipy.

Most of the dependencies come preinstalled in the full Anaconda distribution, but some may be installed separately. First try to launch QtFit or something else, then if it complains about a package, try conda:

    >conda install pyserial

The command above only looks within the official repository. You might also try the community-supported 'conda-forge' source:

    >conda install -c conda-forge pyserial

If that fails, you would try pip for individual packages, e.g.:

    >pip install --user "git+https://github.com/notlaast/vamdclib.git"

Feel free to contact one of the developers about help with Anaconda.


#### Installation on MacOS

Users running macOS can typically follow the linux instructions, except that Qt doesn't work with the native python (e.g., xcode + macports) and therefore anaconda (python 3.x) is required. For Anaconda, see that section further below.

If you want a launchable icon to install into Applications, then make sure "py2app" is installed:

    >pip install py2app

Then run

    >python setup.py --qtfit2app

And then you should have the launcher under "dist", which you can drag into Applications.

For more information, contact one of the developers.


#### Installation on Microsoft Windows

It is possible to use this software from Microsoft Windows, but it has only been used to build/test QtFit and related GUIs. It has not been used at all for anything instrument-related. For running the GUIs, the experience can be hit-or-miss, depending on method of installation. In general, you have two options: anaconda (see above) or manually installing python and all the dependencies.

For awhile, Anaconda was the best solution, but newer versions of the installer (and PyQt-based interfaces) appear to be buggy. Therefore, it is recommended to install Python (important: x86, i.e. 32-bit) from its exe installer (https://www.python.org/downloads/windows/), manually upgrading pip:

    >python -m pip install --upgrade pip

and then installing the dependencies manually:

    >pip install PyQt5 PyQtWebEngine pyqtgraph scipy requests numpy pyyaml astropy

    >pip install "git+https://github.com/notlaast/vamdclib.git"

It is also recommended to install git (32-bit, https://git-scm.com/download/win). Then you can access the git bash shell and run python as normal.

And it IS recommended to add git and Anaconda/Python to your path.



Documentation
-------------

We have attempted to make heavy use of internal documentation. This not only enhances user-friendliness, but it also allows for full generation of documentation behind the internal API.

To generate this documentation yourself (assuming the dependencies are already installed, as discussed above), run the following command within the the `/doc/full` folder:

    >make html

or:

    >make latexpdf

The generated documentation can then be found in the folder `/doc/full/_build/`.
