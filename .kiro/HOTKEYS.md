# Launcher Hotkeys Quick Reference

The launcher includes a lightweight hotkey system that provides full control without requiring a system tray menu.

## Hotkey List

All hotkeys use **Ctrl+Alt+Function Key** combination:

```
┌─────────────────────────────────────────────────────────┐
│                  LAUNCHER HOTKEYS                       │
├─────────────────┬───────────────────────────────────────┤
│  Ctrl+Alt+F1    │  Restart launcher (HOLD 0.5s)         │
│  Ctrl+Alt+F2    │  Stop game gracefully                 │
│  Ctrl+Alt+F3    │  Force kill all processes (HOLD 0.5s) │
│  Ctrl+Alt+F4    │  Display config (read-only)           │
│  Ctrl+Alt+F5    │  Edit config in notepad               │
│  Ctrl+Alt+F6    │  Reload configuration                 │
│  Ctrl+Alt+F9    │  Show this help                       │
│  Ctrl+Alt+F12   │  Exit launcher (HOLD 0.5s)            │
└─────────────────┴───────────────────────────────────────┘

NOTE: Actions marked "HOLD 0.5s" require holding the key combo
      for half a second to prevent accidental triggering.
```

## Detailed Actions

### Ctrl+Alt+F1 - Restart Launcher (HOLD 0.5s)
Stops the current game and restarts the launcher with the same shortcut/executable.

**Hold requirement:** This is a destructive action, so you must hold the key combo for 0.5 seconds.

**Use case:** After editing configuration and wanting to restart with new settings.

### Ctrl+Alt+F2 - Stop Game Gracefully
Executes the exit sequence and terminates the game process cleanly.

**Use case:** Normal game exit with proper cleanup (restore monitor config, stop controller mapper, etc.)

### Ctrl+Alt+F3 - Force Kill All (HOLD 0.5s)
Immediately kills the game process and all processes in the kill list without running exit sequences.

**Hold requirement:** This is a destructive action, so you must hold the key combo for 0.5 seconds.

**Use case:** Game is frozen or not responding. Emergency exit.

### Ctrl+Alt+F4 - Display Config
Opens the Game.ini file in the default text viewer (read-only).

**Use case:** Quick reference to see current configuration.

### Ctrl+Alt+F5 - Edit Config
Opens the Game.ini file in Notepad for editing.

**Use case:** Make changes to configuration while game is running.

### Ctrl+Alt+F6 - Reload Configuration
Reloads the Game.ini file without restarting the launcher.

**Use case:** After editing config with Ctrl+Alt+F5, reload to apply changes.

### Ctrl+Alt+F9 - Show Help
Displays the hotkey help in the console window.

**Use case:** Forgot a hotkey? Press this to see the list.

### Ctrl+Alt+F12 - Exit Launcher (HOLD 0.5s)
Stops the game gracefully and exits the launcher.

**Hold requirement:** This is a destructive action, so you must hold the key combo for 0.5 seconds.

**Use case:** Clean shutdown of everything.

## Features

- **Global hotkeys**: Work even when the game has focus
- **Hold-to-confirm**: Destructive actions require holding for 0.5s to prevent accidents
- **Debouncing**: 500ms delay prevents accidental double-triggers
- **Visual feedback**: Console messages show when holding and when action executes
- **No dependencies**: Uses Windows keyboard hooks (built into Windows)
- **Logging**: All actions are logged to `launcher.log`
- **Fallback**: Automatically activates if tray menu is not available

## Workflow Examples

### Hold-to-Confirm for Safety
Destructive actions (restart, kill, exit) require holding the key combo:

1. Press and hold **Ctrl+Alt+F3** (Force Kill)
2. Console shows: "Hold Ctrl+Alt+F3 for 0.5s to kill..."
3. Keep holding for 0.5 seconds
4. Console shows: "Executing kill..."
5. Action is performed

If you release early, you'll see: "Kill cancelled (not held long enough)"

### Quick Config Edit
1. Press **Ctrl+Alt+F5** to open config in notepad
2. Make your changes and save
3. Press **Ctrl+Alt+F6** to reload without restarting

### Emergency Exit
1. Press **Ctrl+Alt+F3** to force kill everything
2. Or press **Ctrl+Alt+F2** for graceful exit

### Restart with New Settings
1. Edit your config file
2. Press **Ctrl+Alt+F1** to restart the launcher

## Troubleshooting

### Hotkeys not working?
- Make sure you're pressing **Ctrl+Alt+Key** together
- Check that the launcher console window is still running
- Look in `launcher.log` for "Hotkey handler initialized"

### Hotkey conflicts?
- If another application uses the same hotkeys, they may conflict
- Check the log file to see if the hotkey was registered
- Consider closing other applications that might use global hotkeys

### Want to disable hotkeys?
- Set environment variable: `LAUNCHER_MINIMAL=0`
- Or use the full build with tray menu instead

## Comparison: Tray Menu vs Hotkeys

| Feature | Tray Menu | Hotkeys |
|---------|-----------|---------|
| Dependencies | pystray, PIL | None (Windows API) |
| Size impact | +5-10 MB | +0 MB |
| Visibility | Icon in system tray | Console message |
| Access | Right-click menu | Keyboard shortcuts |
| GUI | Yes (PyQt6 dialogs) | No (opens notepad) |
| Best for | Mouse users | Keyboard users |

## Platform Support

- **Windows**: Full support (uses Windows keyboard hooks)
- **Linux/macOS**: Not supported (hotkey handler is Windows-only)

On non-Windows platforms, the launcher will work but hotkeys will not be available.
