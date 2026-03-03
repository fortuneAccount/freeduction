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
    excludes=['pygame', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx', 'psutil', 'matplotlib', 'numpy', 'pandas', 'Python.hotkey_handler', 'Python.managers.plugin_manager', 'Python.plugins', 'Python.marketplace', 'test', 'unittest', 'pydoc', 'email', 'http', 'xml', 'distutils'],
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
    name='Launcher_minimal',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
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
