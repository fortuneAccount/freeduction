# Building the Launcher

Quick reference for building different versions of the Launcher.

## TL;DR

```bash
# Install PyInstaller
pip install pyinstaller

# Build with a preset
python assets/launcher/Build_PyLauncher.py [preset]
```

## Available Presets

| Command | Size | Description |
|---------|------|-------------|
| `python assets/launcher/Build_PyLauncher.py full` | 50+ MB | Full-featured (default) |
| `python assets/launcher/Build_PyLauncher.py minimal` | 10-15 MB | Smallest, hotkeys only |
| `python assets/launcher/Build_PyLauncher.py standard` | 20-25 MB | Balanced, no heavy GUI |
| `python assets/launcher/Build_PyLauncher.py portable` | 15-20 MB | Optimized for distribution |
| `python assets/launcher/Build_PyLauncher.py debug` | 50+ MB | With console & debug info |

## List All Presets

```bash
python assets/launcher/Build_PyLauncher.py --list
```

## Documentation

- **Detailed preset information:** [assets/launcher/BUILD_PRESETS.md](assets/launcher/BUILD_PRESETS.md)
- **Minimal build guide:** [BUILD_MINIMAL.md](BUILD_MINIMAL.md)
- **Hotkey reference:** [HOTKEYS.md](HOTKEYS.md)

## Quick Comparison

### Full Build
- ✅ All features
- ✅ Splash screen
- ✅ Tray menu
- ✅ Plugin system
- 📦 50+ MB

### Minimal Build
- ✅ Core features
- ✅ Hotkeys (Ctrl+Alt+F1-F12)
- ❌ No splash/tray/plugins
- 📦 10-15 MB

### Standard Build
- ✅ Core features
- ✅ Hotkeys
- ✅ Process management (psutil)
- ❌ No splash/tray
- 📦 20-25 MB

### Portable Build
- ✅ Core features
- ✅ Hotkeys
- ✅ Tray menu
- ❌ No plugins
- 📦 15-20 MB

## Output

Built executables are in the `dist/` folder:
- `dist/Launcher_full.exe`
- `dist/Launcher_minimal.exe`
- `dist/Launcher_standard.exe`
- `dist/Launcher_portable.exe`
- `dist/Launcher_debug.exe`

## Recommendations

- **Personal use:** `full` or `standard`
- **Distribution:** `portable` or `minimal`
- **Development:** `debug`
- **Size matters:** `minimal`
- **Best balance:** `standard`
