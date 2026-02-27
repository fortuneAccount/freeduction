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
    excludes=['pygame', 'PIL', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx', 'psutil', 'win32gui', 'win32con', 'win32process', 'win32api', 'pywintypes', 'win32com', 'matplotlib', 'numpy', 'pandas', 'Python.managers.plugin_manager', 'Python.managers.plugin_loader', 'Python.plugins', 'Python.marketplace', 'Python.tray_menu', 'pystray', 'infi.systray'],
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
    strip=True,
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
