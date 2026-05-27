# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

hiddenimports = [
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
    'pyqtgraph',
    'serial',
    'serial.tools',
    'serial.tools.list_ports',
]

excludes = [
    'PySide6.Qt3DCore',
    'PySide6.Qt3DRender',
    'PySide6.QtCharts',
    'PySide6.QtDataVisualization',
    'PySide6.QtDesigner',
    'PySide6.QtHelp',
    'PySide6.QtMultimedia',
    'PySide6.QtNetworkAuth',
    'PySide6.QtOpenGL',
    'PySide6.QtPdf',
    'PySide6.QtPositioning',
    'PySide6.QtQml',
    'PySide6.QtQuick',
    'PySide6.QtQuick3D',
    'PySide6.QtRemoteObjects',
    'PySide6.QtScxml',
    'PySide6.QtSensors',
    'PySide6.QtSerialPort',
    'PySide6.QtSql',
    'PySide6.QtSvg',
    'PySide6.QtTest',
    'PySide6.QtWebChannel',
    'PySide6.QtWebEngineCore',
    'PySide6.QtWebEngineWidgets',
    'PySide6.QtWebSockets',
    'PySide6.QtXml',
    'PySide6.QtXmlPatterns',
    'tkinter',
    'matplotlib',
    'numpy.tests',
    'scipy',
    'pandas',
]

a = Analysis(
    ['rf-bridge.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='RF Bridge',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='RF Bridge',
)
app = BUNDLE(
    coll,
    name='RF Bridge.app',
    icon='assets/rf-bridge.icns',
    bundle_identifier='org.rfbridge.app',
    info_plist={
        'CFBundleDisplayName': 'RF Bridge',
        'CFBundleName': 'RF Bridge',
        'CFBundleShortVersionString': '1.9.5.11',
        'CFBundleVersion': '1.9.5.11',
        'NSHighResolutionCapable': True,
    },
)
