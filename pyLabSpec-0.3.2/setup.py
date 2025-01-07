#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# TODO
# - add doc dependencies
#
# standard library
import setuptools
import os
import sys
import argparse
if sys.version_info[0] == 3:
	import urllib.request
	from urllib.request import urlretrieve
else:
	from urllib import urlretrieve
# third-party
pass
# local
sys.path.append(os.path.dirname(os.path.realpath(__file__))) # important to prioritize the local version first
import pyLabSpec

### initialize some things that may get populated below
options = {}
setup_requires = []
data_files = []


### define optional arguments
"""
Provides an additional commandline interface.. and '--help' will show
options at the top that are not standard for setuptools.
"""
argparser = argparse.ArgumentParser(add_help=False)


### define (optionally) user-installed scripts
"""
Provides ability to install scripts to the user's path.
"""
scripts = ["pyLabSpec/GUIs/qtfit.py",
           "pyLabSpec/GUIs/profitter.py",
           "pyLabSpec/Scripts/read_dmm.py",
]
scripts_help_msg = "Besides the standard information below, the option '--noscripts' will "
scripts_help_msg += "skip the installation of the following files:"
for s in scripts:
    scripts_help_msg += "\n\t%s" % s
scripts_help_msg += "\n"
argparser.add_argument('--noscripts', action='store_true', help=scripts_help_msg, required=False)


### define (optionally) creation of MacOS apps
"""
Provides ability for macOS users to install applications launchable
from the Applications bar or to open files with it via the Finder.
"""
argparser.add_argument(
    '--qtfit2app', action='store_true', required=False,
    help="Creates an 'QtFit.app' bundle that can be installed for the user (clashes with other foo2app entries, run separately).")
argparser.add_argument(
    '--profitter2app', action='store_true', required=False,
    help="Creates an 'ProLineFitter.app' bundle that can be installed for the user (clashes with other foo2app entries, run separately).")


### process the arguments
args, unknown = argparser.parse_known_args()
sys.argv = [sys.argv[0]] + unknown # removes unknown options so setuptools doesn't see it
# for help
if "--help" in sys.argv:     # unlike the standard parse_args(), parse_known_args() doesn't automatically provide this
    argparser.print_help()
    print("")
# for installable scripts to the path
if args.noscripts:
    scripts = []
# for installable MacOS apps
if args.qtfit2app or args.profitter2app:
    setup_requires.append("py2app")
    if not "py2app" in sys.argv:
        sys.argv.append("py2app")
    if (not "--alias" in sys.argv) or (not "-A" in sys.argv):
        sys.argv.append("--alias")
    options["py2app"] = {
        'argv_emulation': True,
        "iconfile": os.path.realpath("./pyLabSpec/GUIs/linespec.icns")
    }
    try:
        from plistlib import Plist
        plist = Plist.fromFile('Info.plist')
    except:
        plist = {}
    urlretrieve('https://gist.github.com/tkf/d980eee120611604c0b9b5fef5b8dae6/raw/36bd53aa36bbe7fa06412b07cf72437361549dd3/find_libpython.py', 'find_libpython.py')
    import find_libpython
    libpython = find_libpython.find_libpython()
    plist.update({
        'PyRuntimeLocations': [
            '@executable_path/../Frameworks/%s' % os.path.basename(libpython),
            libpython
    ]})
if args.qtfit2app:
    app = [os.path.realpath("./pyLabSpec/GUIs/qtfit.py")]
    plist.update({
        'CFBundleDisplayName': 'QtFit',
        'CFBundleExecutable': 'QtFit',
        'CFBundleIdentifier': 'org.pyLabSpec.qtfit',
        'CFBundleName': 'QtFit',
    })
    options['py2app']['plist'] = plist
elif args.profitter2app:
    app = [os.path.realpath("./pyLabSpec/GUIs/profitter.py")]
    plist.update({
        'CFBundleDisplayName': 'ProLineFitter',
        'CFBundleExecutable': 'ProLineFitter',
        'CFBundleIdentifier': 'org.pyLabSpec.ProLineFitter',
        'CFBundleName': 'ProLineFitter',
    })
    options['py2app']['plist'] = plist
else:
    app = []


### define some optional dependencies
"""
Helps setuptoolsfind the correct versions of additional packages not available from pip.
"""
dependency_links = []
dependency_links.append("git+https://github.com/chwiede/pyads.git") # apparently not on pip..
dependency_links.append("git+https://github.com/notlaast/vamdclib.git") # definitely not on pip..
# also, zhinst (64-bit, probably ucs4)
if sys.version_info[0] == 3:
    dependency_links.append("https://www.zhinst.com/system/files/downloads/files/ziPython2.7_ucs4-16.12.42529-linux64.tar.gz")
else:
    dependency_links.append("https://www.zhinst.com/system/files/downloads/files/ziPython3.5_ucs4-16.12.42529-linux64.tar.gz")
# define extras as lists
inst_extras = ["pyserial", "pyads", "ziPython==16.12.42529"]
gui_extras = ["pyqtgraph", "pyFFTW", "vamdclib"]
full_extras = inst_extras + gui_extras




### continue with the normal setuptools business
with open("README.md", "r") as fh:
    long_description = fh.read()
version = pyLabSpec.__version__

setuptools.setup(
    name="pyLabSpec",
    version=version,
    author="Christian Endres, Jacob Laas",
    author_email="cendres@mpe.mpg.de, jclaas@mpe.mpg.de",
    description="a spectroscopic library",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://gitlab.mpcdf.mpg.de/chre/pyLabSpec",
    packages=setuptools.find_packages(),
    classifiers=["Programming Language :: Python :: 2",
                 "Programming Language :: Python :: 3",
                 "License :: OSI Approved :: GPLv3 License",
                 "Operating System :: Linux",
                 "Operating System :: Windows",
                 "Operating System :: macOS",
    ],
    options=options,
    setup_requires=setup_requires,
    scripts=scripts,
    app=app,
    install_requires=[
        "numpy>=1.14",
        "scipy>=0.17"
    ],
    dependency_links=dependency_links,
    extras_require={
        'full': full_extras,
        'inst': inst_extras,
        'gui': gui_extras,
    },
    include_package_data=True, # for copying the extra files during installation
)

### add something helpful for the user who made it this far with extra settings
if args.qtfit2app or args.profitter2app:
    print("\n***An .app bundle has been created in the 'dist' folder. Use this to install it as an application (and cross your fingers).***")
