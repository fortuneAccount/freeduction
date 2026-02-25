#!/usr/bin/env python3
"""
launcher_c_style.py - A Procedural Game Launcher Script

This script is a refactored, C-style procedural version of the original
GameLauncher. It is intended to serve as a clear blueprint for porting
the launcher logic to the C programming language.
"""

import os
import sys
import subprocess
import configparser
import time
import ctypes
import psutil
import logging
import shutil
import datetime
from pathlib import Path
import winreg
import win32gui
import win32con
import shlex
from typing import Dict, List, Optional, Union

# --- Global State Variables (mimicking C-style globals) ---

CONFIG: Dict[str, Union[str, bool, int, List[str]]] = {}
RUNNING_PROCESSES: Dict[str, subprocess.Popen] = {}
GAME_PROCESS: Optional[subprocess.Popen] = None
BORDERLESS_PROCESS: Optional[subprocess.Popen] = None

TASKBAR_HWND = None
TASKBAR_WAS_HIDDEN = False
DYNAMIC_SPLASH_HWND = None

# --- Helper Functions ---

def find_path_case_insensitive(path: str) -> Optional[str]:
    """
    Find a file or directory with case-insensitive matching.
    Returns the actual path if found, None otherwise.
    """
    if not path:
        return None
    
    # If the path exists as-is, return it
    if os.path.exists(path):
        return path
    
    # Split the path into components
    path_obj = Path(path)
    parts = path_obj.parts
    
    # Start with the root (drive letter on Windows, / on Unix)
    if len(parts) == 0:
        return None
    
    # Build the path component by component with case-insensitive matching
    current_path = parts[0]
    
    # For Windows drive letters, ensure we have the backslash
    if len(current_path) == 2 and current_path[1] == ':':
        current_path = current_path + '\\'
    
    for part in parts[1:]:
        if not os.path.exists(current_path):
            return None
        
        # List items in current directory
        try:
            items = os.listdir(current_path)
        except (PermissionError, OSError):
            return None
        
        # Find matching item (case-insensitive)
        found = False
        for item in items:
            if item.lower() == part.lower():
                current_path = os.path.join(current_path, item)
                found = True
                break
        
        if not found:
            return None
    
    return current_path if os.path.exists(current_path) else None

# --- Core Functions ---

def show_message(message: str):
    """Prints a message to the console and logs it."""
    print(message)
    logging.info(message)

def run_process(cmd: Union[str, List[str]], cwd: Optional[str] = None, wait: bool = False, hide: bool = False) -> Optional[subprocess.Popen]:
    """Runs a process securely and robustly."""
    # This function is already well-suited for translation.
    # In C, this will map to the CreateProcess WinAPI function.
    kwargs = {'cwd': cwd}
    if isinstance(cmd, str):
        cmd_list = shlex.split(cmd)
    else:
        cmd_list = cmd

    creation_flags = 0
    if hide:
        creation_flags = subprocess.CREATE_NO_WINDOW
    kwargs['creationflags'] = creation_flags

    try:
        show_message(f"Executing: {cmd}")
        if wait:
            process = subprocess.Popen(cmd_list, **kwargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8', errors='ignore')
            stdout, stderr = process.communicate()
            if process.returncode != 0:
                show_message(f"Process '{cmd_list[0]}' exited with error code {process.returncode}: {stderr.strip()}")
            return None
        else:
            process = subprocess.Popen(cmd_list, **kwargs)
            return process
    except (FileNotFoundError, PermissionError) as e:
        show_message(f"Error executing process '{str(cmd)}': {e}")
        return None
    except Exception as e:
        show_message(f"An unexpected error occurred with '{str(cmd)}': {e}")
        return None

def terminate_process_tree(proc: psutil.Process, timeout: int = 3):
    """Gracefully terminates a process and its children."""
    # This logic will be re-implemented in C using CreateToolhelp32Snapshot,
    # Process32First/Next, OpenProcess, and TerminateProcess.
    if not proc or not psutil.pid_exists(proc.pid):
        return
    try:
        children = proc.children(recursive=True)
        for p in children:
            p.terminate()
        gone, alive = psutil.wait_procs(children, timeout=timeout)
        for p in alive:
            p.kill()
        proc.terminate()
        proc.wait(timeout)
    except (psutil.NoSuchProcess, psutil.TimeoutExpired):
        try:
            proc.kill()
        except psutil.NoSuchProcess:
            pass # Already gone
    except Exception as e:
        show_message(f"Error terminating process tree for PID {proc.pid}: {e}")

def kill_process_by_name(process_name: str, timeout: int = 3):
    """Finds and kills processes by exact name match."""
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'].lower() == process_name.lower():
            terminate_process_tree(proc, timeout=timeout)

def load_configuration(plink_path: str):
    """Loads configuration into the global CONFIG dictionary."""
    scpath = Path(plink_path).parent
    game_ini_path = scpath / "Game.ini"

    if not game_ini_path.exists():
        show_message(f"Configuration file not found at {game_ini_path}")
        return False

    parser = configparser.ConfigParser()
    parser.read(game_ini_path)

    # Load all settings into the global CONFIG dict
    for section in parser.sections():
        for key, value in parser.items(section):
            # Simple type inference
            if value.lower() in ['true', 'false']:
                CONFIG[key.lower()] = parser.getboolean(section, key)
            elif value.isdigit():
                CONFIG[key.lower()] = parser.getint(section, key)
            elif ',' in value:
                 CONFIG[key.lower()] = [item.strip() for item in value.split(',')]
            else:
                CONFIG[key.lower()] = value
    return True

def check_instances():
    """Checks for running instances and handles single-instance logic."""
    # In C, this would use CreateMutex or a lock file.
    pid_file = Path(sys.argv[0]).parent / "rjpids.ini"
    current_pid = os.getpid()
    
    if pid_file.exists():
        try:
            parser = configparser.ConfigParser()
            parser.read(pid_file)
            if parser.has_section('Instance'):
                old_pid = parser.getint('Instance', 'pid', fallback=0)
                multi = parser.getint('Instance', 'multi_instance', fallback=0)
                
                if multi == 1:
                    return True
                
                if old_pid != 0 and old_pid != current_pid:
                    if psutil.pid_exists(old_pid):
                        # In C, we would show a MessageBox here
                        print(f"Another instance (PID {old_pid}) is running.")
                        # Logic to ask user to kill it would go here
        except Exception:
            pass
            
    # Write current PID
    with open(pid_file, 'w') as f:
        f.write(f"[Instance]\npid={current_pid}\nmulti_instance=0\n")
    return True

def backup_save_files():
    """Backs up save files if configured."""
    if not CONFIG.get('backupsaves', False):
        return
        
    home = Path(sys.argv[0]).parent
    save_dir = home / "Saves"
    if not save_dir.exists():
        return
        
    backup_root = home / "Backups"
    backup_root.mkdir(exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_name = f"SaveBackup_{timestamp}"
    backup_path = backup_root / backup_name
    
    try:
        shutil.make_archive(str(backup_path), 'zip', str(save_dir))
        show_message(f"Backed up saves to {backup_name}.zip")
        
        # Rotate
        max_backups = CONFIG.get('maxbackups', 5)
        backups = sorted(list(backup_root.glob("SaveBackup_*.zip")))
        while len(backups) > max_backups:
            oldest = backups.pop(0)
            oldest.unlink()
            show_message(f"Removed old backup: {oldest.name}")
    except Exception as e:
        show_message(f"Backup failed: {e}")

def show_dynamic_splash(base_dir):
    """
    Displays a splash screen.
    In C, this would use CreateWindowEx with WS_EX_LAYERED and UpdateLayeredWindow.
    """
    global DYNAMIC_SPLASH_HWND
    # Simplified logic to find image
    extensions = ['jpg', 'png', 'gif']
    names = ['Backdrop', 'background', 'fanart', 'box-art', 'coverart']
    image_path = None
    
    for name in names:
        for ext in extensions:
            p = Path(base_dir) / f"{name}.{ext}"
            if p.exists():
                image_path = p
                break
        if image_path: break
    
    if image_path:
        show_message(f"Showing splash image: {image_path}")
        # In C, load image (GDI+ or stb_image), create window, fade in.
        # Here we just simulate the state.
        DYNAMIC_SPLASH_HWND = 1 # Fake handle

def close_dynamic_splash():
    """Closes the splash screen."""
    global DYNAMIC_SPLASH_HWND
    if DYNAMIC_SPLASH_HWND:
        show_message("Closing splash screen")
        # In C, fade out and DestroyWindow
        DYNAMIC_SPLASH_HWND = None

# --- Action Functions (from SequenceExecutor) ---

def run_controller_mapper():
    app = CONFIG.get('controllermapperapp', '')
    p1 = CONFIG.get('player1profile', '')
    
    # Resolve paths case-insensitively
    app = find_path_case_insensitive(app)
    p1 = find_path_case_insensitive(p1)
    
    if app and p1:
        cmd = f'"{app}" --tray --hidden --profile "{p1}"'
        # Simplified for blueprint; C version will need to build this command string.
        process = run_process(cmd)
        if process:
            RUNNING_PROCESSES['controller_mapper'] = process

def kill_controller_mapper():
    process = RUNNING_PROCESSES.pop('controller_mapper', None)
    if process:
        terminate_process_tree(process)
    elif CONFIG.get('controllermapperapp'):
        kill_process_by_name(Path(CONFIG['controllermapperapp']).name)

def run_monitor_config_game():
    tool = CONFIG.get('multimonitortool', '')
    config = CONFIG.get('multimonitorgamingconfig', '')
    
    # Resolve paths case-insensitively
    tool = find_path_case_insensitive(tool)
    config = find_path_case_insensitive(config)
    
    if tool and config:
        run_process(f'"{tool}" /load "{config}"', wait=True)

def run_monitor_config_desktop():
    tool = CONFIG.get('multimonitortool', '')
    config = CONFIG.get('multimonitordesktopconfig', '')
    
    # Resolve paths case-insensitively
    tool = find_path_case_insensitive(tool)
    config = find_path_case_insensitive(config)
    
    if tool and config:
        run_process(f'"{tool}" /load "{config}"', wait=True)

def hide_taskbar():
    global TASKBAR_HWND, TASKBAR_WAS_HIDDEN
    if CONFIG.get('hidetaskbar') and TASKBAR_HWND:
        win32gui.ShowWindow(TASKBAR_HWND, win32con.SW_HIDE)
        TASKBAR_WAS_HIDDEN = True

def show_taskbar():
    global TASKBAR_HWND
    if TASKBAR_HWND:
        win32gui.ShowWindow(TASKBAR_HWND, win32con.SW_SHOW)

def run_generic_app(app_key: str, wait_key: str):
    app_path = CONFIG.get(app_key, '')
    wait = CONFIG.get(wait_key, False)
    
    # Resolve path case-insensitively
    app_path = find_path_case_insensitive(app_path)
    
    if app_path:
        process = run_process(f'"{app_path}"', wait=wait)
        if process and not wait:
            RUNNING_PROCESSES[app_key] = process

def kill_borderless():
    global BORDERLESS_PROCESS
    if CONFIG.get('terminateborderlessonexit') and BORDERLESS_PROCESS:
        terminate_process_tree(BORDERLESS_PROCESS)
        BORDERLESS_PROCESS = None

def ensure_cleanup():
    """Final cleanup to restore system state."""
    if TASKBAR_WAS_HIDDEN:
        show_taskbar()
    for name, process in list(RUNNING_PROCESSES.items()):
        terminate_process_tree(process)
    RUNNING_PROCESSES.clear()

# --- Sequence Execution Logic ---

def execute_action(action_name: str, is_exit_sequence: bool):
    """Executes a single action based on its name."""
    show_message(f"  - Running: {action_name}")
    
    # This if/elif structure is a direct blueprint for a C switch or if/else block.
    if action_name == 'Controller-Mapper':
        if is_exit_sequence: kill_controller_mapper()
        else: run_controller_mapper()
    elif action_name == 'Monitor-Config':
        if is_exit_sequence: run_monitor_config_desktop()
        else: run_monitor_config_game()
    elif action_name == 'No-TB':
        if not is_exit_sequence: hide_taskbar()
    elif action_name == 'Taskbar':
        if is_exit_sequence: show_taskbar()
    elif action_name == 'Borderless':
        # This action is a placeholder; the logic is handled in run_game_process
        if not is_exit_sequence: show_message("  - Borderless windowing will be applied after game launch.")
        else: kill_borderless()
    elif action_name == 'Pre1':
        run_generic_app('app1', 'app1wait')
    elif action_name == 'Post1':
        run_generic_app('postlaunch_app1', 'postlaunch_app1wait')
    # ... Add all other Pre/Post/Just-In-Time apps here
    else:
        show_message(f"  - Unknown action: {action_name}")

def execute_sequence(sequence_key: str):
    """Executes a full sequence (e.g., 'launchsequence')."""
    sequence = CONFIG.get(sequence_key, [])
    is_exit = 'exit' in sequence_key
    show_message(f"Executing {sequence_key}...")
    for item in sequence:
        try:
            execute_action(item, is_exit)
        except Exception as e:
            show_message(f"  - Error executing '{item}': {e}")
            logging.error(f"Error in sequence item '{item}': {e}", exc_info=True)

def run_game_process():
    """The core logic for launching the game itself."""
    global GAME_PROCESS, BORDERLESS_PROCESS
    game_path = CONFIG.get('executable', '')
    game_dir = CONFIG.get('directory', '')

    # Resolve paths case-insensitively
    game_path = find_path_case_insensitive(game_path)
    game_dir = find_path_case_insensitive(game_dir)

    if not (game_path and game_dir):
        show_message("Game executable or directory not found in config.")
        return

    show_message(f"Launching game: {CONFIG.get('name', 'Unknown Game')}")
    GAME_PROCESS = run_process(f'"{game_path}"', cwd=game_dir)

    # Handle borderless windowing after game launch
    borderless_app = find_path_case_insensitive(CONFIG.get('borderlesswindowingapp', ''))
    if CONFIG.get('borderless') in ['E', 'K'] and borderless_app:
        time.sleep(5) # Give the game window time to appear
        BORDERLESS_PROCESS = run_process(f'"{borderless_app}"')

    if GAME_PROCESS:
        GAME_PROCESS.wait()

# --- Main Entry Point ---

def main():
    """Main execution flow of the launcher."""
    global TASKBAR_HWND
    if len(sys.argv) < 2:
        print("Usage: launcher_c_style.py <path_to_shortcut>")
        sys.exit(1)

    plink = sys.argv[1]
    show_message(f"Launcher starting for: {plink}")

    # Basic logging setup
    log_path = Path(plink).parent / "launcher.log"
    logging.basicConfig(filename=log_path, level=logging.INFO, format='%(asctime)s - %(message)s')

    # Find taskbar for later use
    if platform.system() == 'Windows':
        TASKBAR_HWND = win32gui.FindWindow("Shell_TrayWnd", None)

    # Load configuration
    if not load_configuration(plink):
        sys.exit(1)

    if not check_instances():
        sys.exit(0)

    try:
        # Execute launch sequence
        execute_sequence('launchsequence')

        # Run the game and wait for it to close
        run_game_process()

        # Backup saves
        backup_save_files()

        # Execute exit sequence
        execute_sequence('exitsequence')

    except Exception as e:
        show_message(f"A critical error occurred: {e}")
        logging.error("Critical error in main loop", exc_info=True)
    finally:
        # Final cleanup
        ensure_cleanup()
        show_message("Launcher finished.")

if __name__ == "__main__":
    main()