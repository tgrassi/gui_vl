:: this is meant to be run from the base directory, after following the instructions about building a pyqt-based exe on windows!
:: note: this is deprecated! it was used to build the initial .spec file, but is no longer valid for newer versions of python, pyqt5, and astropy
pyinstaller ^
 --hidden-import numpy.random.common --hidden-import numpy.random.bounded_integers --hidden-import numpy.random.entropy ^
 --hidden-import PyQt5.QtNetwork --hidden-import PyQt5.QtWebEngineCore --hidden-import PyQt5.QtWebChannel ^
 -p pyLabSpec -p pyLabSpec\Catalog -p pyLabSpec\Fit -p pyLabSpec\GUIs -p pyLabSpec\Instruments -p pyLabSpec\Simulations -p pyLabSpec\Spectrum ^
 pyLabSpec\GUIs\qtfit.py