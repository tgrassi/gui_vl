# -*- mode: python ; coding: utf-8 -*-

import os

block_cipher = None

# make sure all the submodules are also on the path (only when frozen)
pathex=[
    '.',
    'pyLabSpec',
    'pyLabSpec\\Catalog',
    'pyLabSpec\\Fit',
    'pyLabSpec\\GUIs',
    'pyLabSpec\\Instruments',
    'pyLabSpec\\Simulations',
    'pyLabSpec\\Spectrum'
]

# include additional resources
datas=[
    ('LICENSE', '.'),
    ('pyLabSpec\\GUIs\\*.ui', 'resources'),
    ('pyLabSpec\\GUIs\\*.svg', 'resources'),
    ('pyLabSpec\\GUIs\\*.ico', 'resources'),
    ('pyLabSpec\\GUIs\\*.ico', '.'),
    #(os.path.join(HOMEPATH, 'PyQt5\\Qt\\plugins\\platforms\\*'), 'platforms'),   # required for python v3.5.0 + pyqt5 v5.6.0
    (os.path.join(HOMEPATH, 'PyQt5\\Qt\\bin'), 'PyQt5\\Qt\\bin'),   # required for python v3.7.0 + pyqt5 v5.13.0
]

# some libraries are not correctly identified for import/inclusion
hiddenimports=[
    ### required fixes for python v3.5.0 + pyqt5 v5.6.0
    #'numpy.random.common', 'numpy.random.bounded_integers', 'numpy.random.entropy',
    #'PyQt5.QtNetwork', 'PyQt5.QtWebEngineCore', 'PyQt5.QtWebChannel',
    ### required fix for setuptools == 45.0.0 (until it or pyinstaller is updated appropriately)
    'pkg_resources.py2_warn',
]

a = Analysis(['pyLabSpec\\GUIs\\qtfit.py'],
             pathex=pathex,
             binaries=[],
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
b = Analysis(['pyLabSpec\\GUIs\\profitter.py'],
             pathex=pathex,
             binaries=[],
             datas=datas,
             hiddenimports=hiddenimports,
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz_a = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
pyz_b = PYZ(b.pure, b.zipped_data, cipher=block_cipher)
exe_a = EXE(pyz_a,
          a.scripts,
          [],
          exclude_binaries=True,
          name='qtfit',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          icon="pyLabSpec\\GUIs\\linespec.ico")
exe_b = EXE(pyz_b,
          b.scripts,
          [],
          exclude_binaries=True,
          name='profitter',
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True,
          console=True,
          icon="pyLabSpec\\GUIs\\linespec.ico")
coll = COLLECT(exe_a, exe_b,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='qtfit')

print("\n**NOTE** if using python 3.7.0 + pyqt5 5.13, don't forget to delete the duplicate, Qt5WebEngineCore and opengl32sw DLLs!")
