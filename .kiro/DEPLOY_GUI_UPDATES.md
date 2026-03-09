# Deploy GUI Updates - Launcher Build Presets

The deploy.py GUI now includes integrated launcher build preset options.

## New Features

### Launcher Build Options Section

A new "Launcher Build Options" section has been added to the deploy GUI with:

1. **Preset Selector** - Dropdown to choose build preset:
   - `full` - Full-featured (50+ MB)
   - `minimal` - Minimal with hotkeys (10-15 MB)
   - `standard` - Standard without GUI (20-25 MB)
   - `portable` - Optimized for distribution (15-20 MB)
   - `debug` - Debug with console (50+ MB)

2. **Modifier Checkboxes** - Optional size reduction flags:
   - `nocs` - No cloud sync utilities (saves ~1-2 MB)
   - `nopd` - No path discovery/PCGW templates (saves ~1-2 MB)
   - `upx` - Enable UPX compression (reduces size by 30-40%)

### Configuration Persistence

All launcher build options are saved to `deploy_ui.ini` under the `[launcher_build]` section:

```ini
[launcher_build]
preset = minimal
nocs = True
nopd = False
upx = True
```

### Build Integration

When you click "Compile" in the deploy GUI:

1. The main application (anattagen) is built as before
2. The launcher is built using `assets/launcher/Build_PyLauncher.py` with your selected preset and modifiers
3. The resulting executable is copied to `bin/Launcher.python.exe`

### Example Workflow

1. Open deploy GUI: `python -m Python.deploy`
2. Select launcher preset: `minimal`
3. Check modifiers: `nocs`, `nopd`, `upx`
4. Click "Compile"
5. Result: Smallest possible launcher (~7-10 MB with UPX)

## Benefits

- **Visual Selection**: No need to remember command-line arguments
- **Persistent Settings**: Your preferences are saved between sessions
- **Integrated Workflow**: Build everything from one interface
- **Size Optimization**: Easy access to all size reduction options
- **Fallback Support**: Falls back to legacy build if Build_PyLauncher.py not found

## Technical Details

### Files Modified

- `Python/deploy.py` - Added launcher build options UI and integration

### New INI Section

```ini
[launcher_build]
preset = full
nocs = False
nopd = False
upx = False
```

### Build Command Generated

Based on selections, the GUI generates commands like:

```bash
# Minimal with all optimizations
python assets/launcher/Build_PyLauncher.py minimal nocs nopd upx

# Standard with UPX only
python assets/launcher/Build_PyLauncher.py standard upx

# Full build (default)
python assets/launcher/Build_PyLauncher.py full
```

## Screenshots

The new section appears below the existing build options:

```
┌─────────────────────────────────────────────────┐
│ Build Portable Binary                          │
├─────────────────────────────────────────────────┤
│ ☐ Onefile  Dest: [dist/          ] [...]      │
│ Workpath: [build/                 ] [...]      │
│ Commit Msg: [Update                          ] │
│ ☐ Skip Python  ☐ Skip Anattagen  ☐ Skip C    │
├─────────────────────────────────────────────────┤
│ Launcher Build Options                          │
│ Preset: [minimal ▼] Minimal with hotkeys...    │
│ Modifiers:                                      │
│ ☑ nocs (no cloud sync, -1-2 MB)               │
│ ☑ nopd (no path discovery, -1-2 MB)           │
│ ☑ upx (UPX compression, -30-40%)              │
└─────────────────────────────────────────────────┘
```

## Compatibility

- Works with existing deploy.py functionality
- Backward compatible with old INI files (uses defaults)
- Falls back to legacy PyInstaller build if Build_PyLauncher.py not found
- All existing features remain unchanged
