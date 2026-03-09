# Launcher Build System

This guide explains the flexible build system for creating different versions of Launcher.exe.

## Quick Start

The launcher now uses a preset-based build system located in `assets/launcher/Build_PyLauncher.py`.

```bash
# List all available presets
python assets/launcher/Build_PyLauncher.py --list

# Build minimal version (10-15 MB)
python assets/launcher/Build_PyLauncher.py minimal

# Build standard version (20-25 MB)
python assets/launcher/Build_PyLauncher.py standard

# Build full version (50+ MB) - default
python assets/launcher/Build_PyLauncher.py full
```

For detailed information about all presets, see [BUILD_PRESETS.md](assets/launcher/BUILD_PRESETS.md).

## Available Presets

| Preset | Size | Features | Use Case |
|--------|------|----------|----------|
| **full** | 50+ MB | Everything | Personal use, all features |
| **minimal** | 10-15 MB | Core + hotkeys | Size-constrained, no GUI |
| **standard** | 20-25 MB | Core + psutil | Balanced, no heavy GUI |
| **portable** | 15-20 MB | Optimized | Distribution to others |
| **debug** | 50+ MB | Everything + console | Development, troubleshooting |

## Minimal Build Details

The minimal preset creates the smallest possible executable by excluding heavy dependencies.

1. **pygame** (~20 MB) - Used for splash screen and joystick detection
2. **psutil** (~5 MB) - Used for advanced process management
3. **pywin32** (~10 MB) - Used for Windows GUI features (except hotkeys)
4. **Plugin system** - All plugin-related modules
5. **Tray menu** - System tray integration (replaced by hotkey handler)

## What Still Works

- ✅ Game launching
- ✅ Pre/Post launch sequences
- ✅ Configuration loading (Game.ini)
- ✅ Cloud sync (if configured)
- ✅ Local backup (if configured)
- ✅ Disc mounting/unmounting
- ✅ Controller mapper integration
- ✅ Borderless gaming integration
- ✅ Multi-monitor configuration
- ✅ Kill list (using taskkill fallback)
- ✅ All core launcher functionality
- ✅ **Hotkey handler** (Ctrl+Alt+F1-F12 shortcuts)

## What Doesn't Work

- ❌ Dynamic splash screen (stubbed)
- ❌ Joystick detection (stubbed)
- ❌ Advanced process tree termination (falls back to taskkill)
- ❌ Plugin system
- ❌ System tray menu (replaced by hotkeys)
- ❌ Instance checking with psutil (basic check still works)

## Hotkey System

The minimal build includes a lightweight hotkey handler that provides the same functionality as the tray menu, but without requiring pystray or PyQt6. All hotkeys use **Ctrl+Alt+Function Key**:

| Hotkey | Action | Description |
|--------|--------|-------------|
| **Ctrl+Alt+F1** | Restart | Restart the launcher (HOLD 0.5s) |
| **Ctrl+Alt+F2** | Stop | Stop game gracefully (runs exit sequences) |
| **Ctrl+Alt+F3** | Kill | Force kill all processes (HOLD 0.5s) |
| **Ctrl+Alt+F4** | Display | Display config (opens in default viewer) |
| **Ctrl+Alt+F5** | Edit | Edit config in notepad |
| **Ctrl+Alt+F6** | Reload | Reload configuration without restarting |
| **Ctrl+Alt+F9** | Help | Show hotkey help in console |
| **Ctrl+Alt+F12** | Exit | Exit launcher gracefully (HOLD 0.5s) |

**Safety Feature:** Destructive actions (restart, kill, exit) require holding the key combo for 0.5 seconds to prevent accidental triggering. You'll see a message like "Hold Ctrl+Alt+F3 for 0.5s to kill..." and if you release early, the action is cancelled.

The hotkey handler:
- Uses Windows keyboard hooks (no external dependencies)
- Works globally (even when game has focus)
- Has hold-to-confirm for destructive actions (0.5s)
- Has built-in debouncing (500ms)
- Provides visual feedback in console
- Automatically activates if tray menu is not available
- Logs all actions to launcher.log

## Building

### Using the preset system (Recommended)

```bash
# Install PyInstaller
pip install pyinstaller

# Build minimal version
python assets/launcher/Build_PyLauncher.py minimal
```

### Legacy method (deprecated)

The old `build_minimal.py` script is deprecated. Use the new preset system instead.

## Environment Variable

The minimal build checks for the `LAUNCHER_MINIMAL` environment variable. When set to `1`, it:
- Skips plugin manager initialization
- Skips tray menu initialization
- Uses fallback methods for process management

This is automatically set by the build script.

## Size Comparison

| Build Type | Size | Dependencies |
|------------|------|--------------|
| Full Build | 50+ MB | pygame, psutil, pywin32, plugins, tray |
| Minimal Build | 10-15 MB | None (stdlib only) |

## Further Size Reduction

If you need even smaller size:

1. **Remove cloud sync utilities**: If you don't use cloud sync, remove `Python/utils/cloud_path_utils.py`
2. **Remove path discovery**: If you don't use PCGW templates, remove `Python/utils/path_discovery.py`
3. **Use UPX compression**: Add `--upx-dir=/path/to/upx` (can reduce by 30-40%)
4. **Remove unused sequence executor**: If you only use basic sequences, simplify `sequence_executor_v2.py`

## Testing the Minimal Build

After building, test with a simple Game.ini:

```ini
[Game]
Executable=C:\Path\To\Game.exe
Name=Test Game

[Launcher]
RunAsAdmin=0
UseKillList=0

[Sequences]
LaunchSequence=Pre1
ExitSequence=Post1
```

Run:
```bash
Launcher_minimal.exe "C:\Path\To\Game.lnk"
```

### Testing Hotkeys

Once the launcher is running, test the hotkey system:

1. **Press Ctrl+Alt+F9** to see the hotkey help
2. **Press Ctrl+Alt+F6** to reload configuration
3. **Press Ctrl+Alt+F5** to edit the config in notepad
4. **Press Ctrl+Alt+F2** to stop the game gracefully
5. **Press Ctrl+Alt+F12** to exit the launcher

The hotkeys work globally, even when the game has focus. All actions are logged to `launcher.log`.

## Troubleshooting

### "Module not found" errors
- Make sure you're using `requirements_minimal.txt` and not the full `requirements.txt`
- Check that excluded modules aren't imported in your custom code

### Process killing doesn't work
- The minimal build uses `taskkill` as a fallback
- This requires the process name to be exact (e.g., "game.exe" not "game")

### Larger than expected size
- Check PyInstaller warnings for included modules
- Use `--log-level=DEBUG` to see what's being bundled
- Consider using `--exclude-module` for additional modules

## Reverting to Full Build

To build the full version with all features:

```bash
pip install -r requirements_win.txt
pyinstaller Launcher.spec
```

Or use the existing build scripts in the repository.
