#!/usr/bin/env python3
"""
hotkey_handler.py - Lightweight Hotkey Handler for Game Launcher

Provides keyboard shortcuts as an alternative to the tray menu.
Uses Windows keyboard hooks (no external dependencies).
"""

import os
import sys
import threading
import logging
import ctypes
import time
from ctypes import wintypes

# Windows constants
WM_KEYDOWN = 0x0100
WM_SYSKEYDOWN = 0x0104
VK_CONTROL = 0x11
VK_SHIFT = 0x10
VK_MENU = 0x12  # Alt key

# Virtual key codes for hotkeys
VK_F1 = 0x70
VK_F2 = 0x71
VK_F3 = 0x72
VK_F4 = 0x73
VK_F5 = 0x74
VK_F6 = 0x75
VK_F7 = 0x76
VK_F8 = 0x77
VK_F9 = 0x78
VK_F10 = 0x79
VK_F11 = 0x7A
VK_F12 = 0x7B

# Hotkey definitions (Ctrl+Alt+Key)
HOTKEYS = {
    VK_F1: 'restart',      # Ctrl+Alt+F1: Restart launcher
    VK_F2: 'stop',         # Ctrl+Alt+F2: Stop game gracefully
    VK_F3: 'kill',         # Ctrl+Alt+F3: Force kill all
    VK_F4: 'display',      # Ctrl+Alt+F4: Display config (opens in notepad)
    VK_F5: 'edit',         # Ctrl+Alt+F5: Edit config (opens in notepad)
    VK_F6: 'reload',       # Ctrl+Alt+F6: Reload config
    VK_F9: 'help',         # Ctrl+Alt+F9: Show hotkey help
    VK_F12: 'exit',        # Ctrl+Alt+F12: Exit launcher
}

# Actions that require holding the key combo (destructive actions)
HOLD_REQUIRED_ACTIONS = {'kill', 'exit', 'restart'}
HOLD_DURATION = 0.5  # seconds - how long to hold for destructive actions

HOTKEY_AVAILABLE = sys.platform == 'win32'

if HOTKEY_AVAILABLE:
    try:
        # Windows API structures
        class KBDLLHOOKSTRUCT(ctypes.Structure):
            _fields_ = [
                ("vkCode", wintypes.DWORD),
                ("scanCode", wintypes.DWORD),
                ("flags", wintypes.DWORD),
                ("time", wintypes.DWORD),
                ("dwExtraInfo", ctypes.POINTER(wintypes.ULONG))
            ]
        
        # Windows API functions
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        
        WH_KEYBOARD_LL = 13
        LLKHF_INJECTED = 0x00000010
        
        # Function prototypes
        LowLevelKeyboardProc = ctypes.WINFUNCTYPE(
            ctypes.c_int,
            ctypes.c_int,
            wintypes.WPARAM,
            ctypes.POINTER(KBDLLHOOKSTRUCT)
        )
        
        SetWindowsHookEx = user32.SetWindowsHookExA
        SetWindowsHookEx.argtypes = [ctypes.c_int, LowLevelKeyboardProc, wintypes.HINSTANCE, wintypes.DWORD]
        SetWindowsHookEx.restype = wintypes.HHOOK
        
        CallNextHookEx = user32.CallNextHookEx
        CallNextHookEx.argtypes = [wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, ctypes.POINTER(KBDLLHOOKSTRUCT)]
        CallNextHookEx.restype = ctypes.c_int
        
        UnhookWindowsHookEx = user32.UnhookWindowsHookEx
        UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
        UnhookWindowsHookEx.restype = wintypes.BOOL
        
        GetMessage = user32.GetMessageW
        TranslateMessage = user32.TranslateMessage
        DispatchMessage = user32.DispatchMessageW
        PostQuitMessage = user32.PostQuitMessage
        
        GetAsyncKeyState = user32.GetAsyncKeyState
        GetAsyncKeyState.argtypes = [ctypes.c_int]
        GetAsyncKeyState.restype = ctypes.c_short
        
    except Exception as e:
        logging.error(f"Failed to initialize Windows API for hotkeys: {e}")
        HOTKEY_AVAILABLE = False


class HotkeyHandler:
    """Lightweight hotkey handler using Windows keyboard hooks"""
    
    def __init__(self, launcher_instance):
        self.launcher = launcher_instance
        self.running = False
        self.hook = None
        self.hook_thread = None
        self.last_action_time = {}
        self.debounce_delay = 0.5  # 500ms debounce
        self.hold_start_time = {}  # Track when keys are first pressed
        
        if not HOTKEY_AVAILABLE:
            logging.warning("Hotkey handler not available on this platform")
            return
        
        # Create the hook callback
        self.hook_callback = LowLevelKeyboardProc(self._keyboard_hook)
    
    def start(self):
        """Start the hotkey handler in a separate thread"""
        if not HOTKEY_AVAILABLE:
            return
        
        self.running = True
        self.hook_thread = threading.Thread(target=self._run_hook, daemon=True)
        self.hook_thread.start()
        logging.info("Hotkey handler started")
        logging.info("Available hotkeys:")
        for vk, action in HOTKEYS.items():
            key_name = self._vk_to_name(vk)
            logging.info(f"  Ctrl+Alt+{key_name}: {action}")
    
    def _run_hook(self):
        """Run the keyboard hook (blocking)"""
        try:
            # Install the hook
            self.hook = SetWindowsHookEx(
                WH_KEYBOARD_LL,
                self.hook_callback,
                kernel32.GetModuleHandleW(None),
                0
            )
            
            if not self.hook:
                logging.error("Failed to install keyboard hook")
                return
            
            logging.debug("Keyboard hook installed")
            
            # Message loop
            msg = wintypes.MSG()
            while self.running and GetMessage(ctypes.byref(msg), None, 0, 0) != 0:
                TranslateMessage(ctypes.byref(msg))
                DispatchMessage(ctypes.byref(msg))
            
        except Exception as e:
            logging.error(f"Hotkey handler error: {e}")
        finally:
            if self.hook:
                UnhookWindowsHookEx(self.hook)
                self.hook = None
    
    def stop(self):
        """Stop the hotkey handler"""
        if self.running:
            self.running = False
            PostQuitMessage(0)
            logging.info("Hotkey handler stopped")
    
    def _keyboard_hook(self, nCode, wParam, lParam):
        """Keyboard hook callback"""
        if nCode >= 0 and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            kb = lParam.contents
            vk_code = kb.vkCode
            
            # Check if Ctrl+Alt are pressed
            ctrl_pressed = GetAsyncKeyState(VK_CONTROL) & 0x8000
            alt_pressed = GetAsyncKeyState(VK_MENU) & 0x8000
            
            if ctrl_pressed and alt_pressed and vk_code in HOTKEYS:
                action = HOTKEYS[vk_code]
                current_time = time.time()
                
                # Check if this is a new key press or continuation
                if vk_code not in self.hold_start_time:
                    # New key press - record start time
                    self.hold_start_time[vk_code] = current_time
                    
                    # For actions that require holding, show a message
                    if action in HOLD_REQUIRED_ACTIONS:
                        print(f"\n[HOTKEY] Hold Ctrl+Alt+{self._vk_to_name(vk_code)} for {HOLD_DURATION}s to {action}...")
                        logging.info(f"Hotkey {action} initiated, waiting for hold duration")
                    
                    return CallNextHookEx(self.hook, nCode, wParam, lParam)
                
                # Check hold duration
                hold_duration = current_time - self.hold_start_time[vk_code]
                
                # For actions requiring hold, check if held long enough
                if action in HOLD_REQUIRED_ACTIONS:
                    if hold_duration >= HOLD_DURATION:
                        # Held long enough - execute once
                        # Check debounce to prevent multiple executions
                        last_time = self.last_action_time.get(action, 0)
                        if current_time - last_time >= self.debounce_delay:
                            self.last_action_time[action] = current_time
                            self.hold_start_time.pop(vk_code, None)  # Clear hold tracking
                            
                            # Execute action in a separate thread
                            threading.Thread(target=self._execute_action, args=(action,), daemon=True).start()
                            print(f"[HOTKEY] Executing {action}...")
                            
                            # Block the key from propagating
                            return 1
                else:
                    # Non-destructive action - execute immediately on first press
                    last_time = self.last_action_time.get(action, 0)
                    if current_time - last_time >= self.debounce_delay:
                        self.last_action_time[action] = current_time
                        self.hold_start_time.pop(vk_code, None)  # Clear hold tracking
                        
                        # Execute action in a separate thread
                        threading.Thread(target=self._execute_action, args=(action,), daemon=True).start()
                        
                        # Block the key from propagating
                        return 1
        
        # Key released - clear hold tracking
        if nCode >= 0 and wParam == 0x0101:  # WM_KEYUP
            kb = lParam.contents
            vk_code = kb.vkCode
            if vk_code in self.hold_start_time:
                action = HOTKEYS.get(vk_code)
                if action in HOLD_REQUIRED_ACTIONS:
                    hold_duration = time.time() - self.hold_start_time[vk_code]
                    if hold_duration < HOLD_DURATION:
                        print(f"[HOTKEY] {action.capitalize()} cancelled (not held long enough)")
                        logging.info(f"Hotkey {action} cancelled - released too early")
                self.hold_start_time.pop(vk_code, None)
        
        return CallNextHookEx(self.hook, nCode, wParam, lParam)
    
    def _execute_action(self, action):
        """Execute a hotkey action"""
        logging.info(f"Hotkey action triggered: {action}")
        
        try:
            if action == 'restart':
                self.restart_launcher()
            elif action == 'stop':
                self.stop_game()
            elif action == 'kill':
                self.kill_all()
            elif action == 'display':
                self.display_config()
            elif action == 'edit':
                self.edit_config()
            elif action == 'reload':
                self.reload_config()
            elif action == 'help':
                self.show_help()
            elif action == 'exit':
                self.exit_launcher()
        except Exception as e:
            logging.error(f"Error executing hotkey action '{action}': {e}")
    
    def restart_launcher(self):
        """Restart the current launcher"""
        logging.info("Restart requested via hotkey")
        
        lnk_file = getattr(self.launcher, 'plink', None)
        
        if lnk_file and os.path.exists(lnk_file):
            self.stop_game()
            
            try:
                if sys.platform == 'win32':
                    os.startfile(lnk_file)
                else:
                    import subprocess
                    subprocess.Popen([lnk_file])
                
                logging.info(f"Restarted launcher: {lnk_file}")
            except Exception as e:
                logging.error(f"Failed to restart launcher: {e}")
        else:
            logging.warning("No launcher link file found for restart")
    
    def stop_game(self):
        """Stop the game using exit sequences"""
        logging.info("Stop requested via hotkey")
        
        try:
            if hasattr(self.launcher, 'executor'):
                self.launcher.executor.execute('exit_sequence')
            
            if hasattr(self.launcher, 'game_process') and self.launcher.game_process:
                self.launcher.terminate_process_tree(self.launcher.game_process)
                logging.info("Game process terminated")
        except Exception as e:
            logging.error(f"Failed to stop game: {e}")
    
    def kill_all(self):
        """Force quit game and all tracked processes"""
        logging.info("Kill all requested via hotkey")
        
        try:
            if hasattr(self.launcher, 'game_process') and self.launcher.game_process:
                self.launcher.game_process.kill()
                logging.info("Game process killed")
            
            if hasattr(self.launcher, 'kill_processes_in_list'):
                self.launcher.kill_processes_in_list()
            
            if hasattr(self.launcher, 'executor'):
                self.launcher.executor.ensure_cleanup()
            
            sys.exit(0)
        except Exception as e:
            logging.error(f"Failed to kill processes: {e}")
    
    def display_config(self):
        """Display current configuration in notepad"""
        logging.info("Display config requested via hotkey")
        
        ini_path = getattr(self.launcher, 'ini_path', None)
        if not ini_path or not os.path.exists(ini_path):
            logging.warning("No config file found")
            return
        
        try:
            if sys.platform == 'win32':
                os.startfile(ini_path)
            else:
                import subprocess
                subprocess.Popen(['xdg-open', ini_path])
            
            logging.info(f"Opened config file: {ini_path}")
        except Exception as e:
            logging.error(f"Failed to open config: {e}")
    
    def edit_config(self):
        """Edit configuration in notepad"""
        logging.info("Edit config requested via hotkey")
        
        ini_path = getattr(self.launcher, 'ini_path', None)
        if not ini_path or not os.path.exists(ini_path):
            logging.warning("No config file found")
            return
        
        try:
            if sys.platform == 'win32':
                import subprocess
                subprocess.Popen(['notepad.exe', ini_path])
            else:
                import subprocess
                subprocess.Popen(['xdg-open', ini_path])
            
            logging.info(f"Opened config for editing: {ini_path}")
        except Exception as e:
            logging.error(f"Failed to open config editor: {e}")
    
    def reload_config(self):
        """Reload configuration in the launcher"""
        logging.info("Reload config requested via hotkey")
        
        try:
            if hasattr(self.launcher, 'load_config'):
                self.launcher.load_config()
                logging.info("Configuration reloaded successfully")
                print("\n[HOTKEY] Configuration reloaded!")
        except Exception as e:
            logging.error(f"Failed to reload config: {e}")
    
    def show_help(self):
        """Show hotkey help"""
        help_text = """
========================================
LAUNCHER HOTKEYS
========================================

Ctrl+Alt+F1  - Restart launcher (HOLD 0.5s)
Ctrl+Alt+F2  - Stop game gracefully
Ctrl+Alt+F3  - Force kill all processes (HOLD 0.5s)
Ctrl+Alt+F4  - Display config (read-only)
Ctrl+Alt+F5  - Edit config in notepad
Ctrl+Alt+F6  - Reload configuration
Ctrl+Alt+F9  - Show this help
Ctrl+Alt+F12 - Exit launcher (HOLD 0.5s)

NOTE: Destructive actions (marked HOLD) require
      holding the key combo for 0.5 seconds to
      prevent accidental triggering.

========================================
"""
        print(help_text)
        logging.info("Hotkey help displayed")
    
    def exit_launcher(self):
        """Exit the launcher gracefully"""
        logging.info("Exit requested via hotkey")
        
        self.stop_game()
        self.stop()
        sys.exit(0)
    
    def _vk_to_name(self, vk):
        """Convert virtual key code to name"""
        vk_names = {
            VK_F1: 'F1', VK_F2: 'F2', VK_F3: 'F3', VK_F4: 'F4',
            VK_F5: 'F5', VK_F6: 'F6', VK_F7: 'F7', VK_F8: 'F8',
            VK_F9: 'F9', VK_F10: 'F10', VK_F11: 'F11', VK_F12: 'F12',
        }
        return vk_names.get(vk, f'VK_{vk}')
