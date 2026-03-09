# Launcher Build Presets

This document describes the available build presets for the Python Launcher.

## Quick Start

```bash
# List all available presets
python assets/launcher/Build_PyLauncher.py --list

# Build with a specific preset
python assets/launcher/Build_PyLauncher.py minimal

# Build with modifiers for further size reduction
python assets/launcher/Build_PyLauncher.py standard nocs nopd upx

# Build with default (full) preset
python assets/launcher/Build_PyLauncher.py
```

## Optional Modifiers

You can add modifiers to any preset to further customize the build:

| Modifier | Effect | Size Savings |
|----------|--------|--------------|
| **nocs** | Exclude cloud sync utilities | ~1-2 MB |
| **nopd** | Exclude path discovery/PCGW templates | ~1-2 MB |
| **upx** | Enable UPX compression | ~30-40% |

**Example:**
```bash
# Standard build without cloud sync and path discovery, with UPX compression
python assets/launcher/Build_PyLauncher.py standard nocs nopd upx
```

## Available Presets

### 1. Full (Default)
**Size:** 50+ MB  
**Console:** No  
**Features:** Everything enabled

The complete launcher with all features:
- ✅ Dynamic splash screen (pygame)
- ✅ Joystick detection (pygame)
- ✅ Advanced process management (psutil)
- ✅ System tray menu (pystray)
- ✅ Plugin system
- ✅ All GUI features

**Use when:** You want all features and size is not a concern.

**Build command:**
```bash
python assets/launcher/Build_PyLauncher.py full
```

---

### 2. Minimal
**Size:** 10-15 MB  
**Console:** No  
**Features:** Core functionality + hotkeys

The smallest build with essential features only:
- ✅ Game launching
- ✅ Pre/Post sequences
- ✅ Configuration management
- ✅ Hotkey handler (Ctrl+Alt+F1-F12)
- ✅ Cloud sync & backups
- ❌ Splash screen (stubbed)
- ❌ Joystick detection (stubbed)
- ❌ Tray menu (replaced by hotkeys)
- ❌ Plugin system
- ❌ Advanced process management (uses taskkill)

**Use when:** You need the smallest possible executable and don't need GUI features.

**Build command:**
```bash
python assets/launcher/Build_PyLauncher.py minimal
```

**Environment:** Sets `LAUNCHER_MINIMAL=1`

---

### 3. Standard
**Size:** 20-25 MB  
**Console:** No  
**Features:** Core + process management

Balanced build without heavy GUI:
- ✅ Game launching
- ✅ Pre/Post sequences
- ✅ Advanced process management (psutil)
- ✅ Hotkey handler
- ✅ Plugin system
- ✅ Cloud sync & backups
- ❌ Splash screen
- ❌ Joystick detection
- ❌ Tray menu (replaced by hotkeys)

**Use when:** You want good process management but don't need GUI features.

**Build command:**
```bash
python assets/launcher/Build_PyLauncher.py standard
```

---

### 4. Portable
**Size:** 15-20 MB  
**Console:** No  
**Features:** Optimized for distribution

Portable build optimized for sharing:
- ✅ Game launching
- ✅ Pre/Post sequences
- ✅ Advanced process management (psutil)
- ✅ Hotkey handler
- ✅ Tray menu (pystray + PIL)
- ✅ Cloud sync & backups
- ❌ Splash screen
- ❌ Joystick detection
- ❌ Plugin system (for portability)

**Use when:** You need to distribute the launcher to others.

**Build command:**
```bash
python assets/launcher/Build_PyLauncher.py portable
```

---

### 5. Debug
**Size:** 50+ MB  
**Console:** Yes (visible)  
**Features:** Everything + debug info

Full build with debugging enabled:
- ✅ All features from 'full' preset
- ✅ Console window visible
- ✅ Verbose logging
- ✅ Debug symbols

**Use when:** You're developing or troubleshooting issues.

**Build command:**
```bash
python assets/launcher/Build_PyLauncher.py debug
```

**Environment:** Sets `LAUNCHER_DEBUG=1`

---

## Comparison Table

| Feature | Full | Minimal | Standard | Portable | Debug |
|---------|------|---------|----------|----------|-------|
| **Size** | 50+ MB | 10-15 MB | 20-25 MB | 15-20 MB | 50+ MB |
| **Console** | No | No | No | No | Yes |
| Game Launching | ✅ | ✅ | ✅ | ✅ | ✅ |
| Sequences | ✅ | ✅ | ✅ | ✅ | ✅ |
| Cloud Sync | ✅ | ✅ | ✅ | ✅ | ✅ |
| Hotkeys | ✅ | ✅ | ✅ | ✅ | ✅ |
| Splash Screen | ✅ | ❌ | ❌ | ❌ | ✅ |
| Joystick Detection | ✅ | ❌ | ❌ | ❌ | ✅ |
| Tray Menu | ✅ | ❌ | ❌ | ✅ | ✅ |
| Plugin System | ✅ | ❌ | ✅ | ❌ | ✅ |
| Process Management | psutil | taskkill | psutil | psutil | psutil |
| Debug Logging | Normal | Normal | Normal | Normal | Verbose |

---

## Further Size Reduction with Modifiers

You can use optional modifiers with any preset to reduce size further:

### nocs - No Cloud Sync
Excludes cloud sync utilities if you don't use cloud backup features.

**Modules excluded:**
- `Python.utils.cloud_path_utils`
- `Python.managers.cloud_sync`

**Size savings:** ~1-2 MB

**Example:**
```bash
python assets/launcher/Build_PyLauncher.py standard nocs
```

### nopd - No Path Discovery
Excludes path discovery and PCGW template functionality if you don't use automatic save file detection.

**Modules excluded:**
- `Python.utils.path_discovery`
- `Python.managers.pcgw_manager`

**Size savings:** ~1-2 MB

**Example:**
```bash
python assets/launcher/Build_PyLauncher.py portable nopd
```

### upx - UPX Compression
Enables UPX compression for the executable. Requires UPX to be installed and in your PATH.

**Download UPX:** https://upx.github.io/

**Size savings:** ~30-40% of final executable size

**Example:**
```bash
python assets/launcher/Build_PyLauncher.py minimal upx
```

### Combining Modifiers
You can combine multiple modifiers:

```bash
# Minimal build with all size reductions
python assets/launcher/Build_PyLauncher.py minimal nocs nopd upx

# Standard build without cloud features, with compression
python assets/launcher/Build_PyLauncher.py standard nocs upx

# Portable build optimized for smallest size
python assets/launcher/Build_PyLauncher.py portable nocs nopd upx
```

---

## Customizing Presets

You can modify the presets in `Build_PyLauncher.py`:

```python
PRESETS = {
    'my_custom': {
        'name': 'Launcher_custom',
        'description': 'My custom build',
        'console': False,
        'env_vars': {'MY_VAR': '1'},
        'excluded_modules': [
            'pygame',
            'psutil',
            # Add more modules to exclude
        ],
        'extra_args': ['--strip'],
        'expected_size': '15-20 MB',
    },
}
```

Then build with:
```bash
python assets/launcher/Build_PyLauncher.py my_custom
```

---

## Module Exclusion Reference

Common modules you might want to exclude:

### GUI Libraries (~20-30 MB)
- `pygame` - Splash screen, joystick detection
- `PIL` / `Pillow` - Image processing for tray icons
- `tkinter` - Tk GUI toolkit
- `PyQt5`, `PyQt6`, `PySide2`, `PySide6` - Qt GUI toolkits
- `wx` - wxWidgets GUI toolkit

### Process Management (~5 MB)
- `psutil` - Advanced process management (falls back to taskkill)

### Windows GUI (~10 MB)
- `win32gui`, `win32con`, `win32process`, `win32api` - Windows API
- `pywintypes`, `win32com` - COM support

### Tray Menu (~5-10 MB)
- `pystray` - System tray integration
- `infi.systray` - Alternative tray library

### Plugin System (~2-5 MB)
- `Python.managers.plugin_manager`
- `Python.managers.plugin_loader`
- `Python.plugins`
- `Python.marketplace`

### Data Science (Never needed, ~50+ MB)
- `matplotlib`, `numpy`, `pandas`, `scipy`
- `tensorflow`, `torch`

---

## Build Output

After building, you'll find:
- **Executable:** `dist/Launcher_[preset].exe`
- **Build files:** `build/` (can be deleted)
- **Spec file:** `Launcher_[preset].spec` (can be reused)

---

## Troubleshooting

### Build fails with "Module not found"
- Make sure you have the required dependencies installed
- For minimal builds, this is expected (modules are excluded)
- Check that you're using the correct Python environment

### Executable is larger than expected
- Check PyInstaller warnings for unexpected includes
- Use `--log-level=DEBUG` in extra_args to see what's bundled
- Consider adding more modules to excluded_modules

### Executable doesn't run
- Try the debug preset to see error messages
- Check launcher.log for errors
- Make sure all required DLLs are present

### Hotkeys don't work
- Hotkeys only work on Windows
- Make sure the console window is running
- Check launcher.log for "Hotkey handler initialized"

---

## Advanced Usage

### Using a spec file
After the first build, you can reuse the generated spec file:

```bash
pyinstaller Launcher_minimal.spec
```

### Adding custom data files
Edit the preset's extra_args:

```python
'extra_args': [
    '--add-data=my_data:data',
    '--add-binary=my_lib.dll:.',
]
```

### Changing the icon
Place your icon in `assets/` and it will be used automatically (Windows only).

---

## Recommendations

- **For personal use:** `full` or `standard`
- **For distribution:** `portable` or `minimal`
- **For development:** `debug`
- **For size-constrained environments:** `minimal`
- **For best balance:** `standard` or `portable`
