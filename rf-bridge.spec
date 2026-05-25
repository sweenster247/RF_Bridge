# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

hiddenimports = []
hiddenimports += collect_submodules('PySide6')
hiddenimports += collect_submodules('pyqtgraph')
hiddenimports += [
    'serial',
    'serial.tools',
    'serial.tools.list_ports',
]

a = Analysis(
    ['rf-bridge.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
        'CFBundleShortVersionString': '1.8.0',
        'CFBundleVersion': '1.8.0',
        'NSHighResolutionCapable': True,
    },
)
