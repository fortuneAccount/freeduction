# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Users\\jesse\\Documents\\gitHub\\freeduction\\Python\\Launcher.py'],
    pathex=[],
    binaries=[],
    datas=[('C:\\Users\\jesse\\Documents\\gitHub\\freeduction\\assets', 'assets')],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['matplotlib', 'numpy', 'pandas', 'scipy', 'tensorflow', 'torch'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Launcher_full',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['C:\\Users\\jesse\\Documents\\gitHub\\freeduction\\assets\\Joystick.ico'],
)
