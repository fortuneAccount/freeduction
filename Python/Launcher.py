#!/usr/bin/env python3
"""
Launcher.py - Game Launcher Script

A Python port of the Launcher.ahk script for launching games with pre/post actions
"""

import os
import sys
import subprocess
import configparser
import time
import ctypes
import shutil
import datetime
import tempfile
import signal
import logging
from pathlib import Path
import shlex
from typing import Dict, List, Optional, Tuple, Union
import platform
import argparse
import glob

# Optional heavy imports - only import if needed
PSUTIL_AVAILABLE = False
PYGAME_AVAILABLE = False
WIN32_AVAILABLE = False

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    pass

# Conditional imports for Windows
if sys.platform == 'win32':
    try:
        import win32gui
        import win32con
        import win32process
        import win32api
        WIN32_AVAILABLE = True
    except ImportError:
        pass

# Import the sequence executor
try:
    from Python.sequence_executor import SequenceExecutor
except ImportError:
    from sequence_executor import SequenceExecutor

class DynamicSplash:
    """Stubbed splash screen for minimal build."""
    def __init__(self, base_dir):
        self.running = False
        
    def show(self):
        pass
    
    def close(self):
        pass

class GameLauncher:
    def __init__(self):
        # Initialize variables
        if getattr(sys, 'frozen', False):
            self.home = os.path.dirname(sys.executable)
            if os.path.basename(self.home).lower() == 'bin':
                self.home = os.path.dirname(self.home)
            # Attach to parent console to allow --help to print to stdout
            if platform.system() == 'Windows':
                try:
                    if ctypes.windll.kernel32.AttachConsole(-1):
                        sys.stdout = open("CONOUT$", "w")
                        sys.stderr = open("CONOUT$", "w")
                except Exception:
                    pass
        else:
            # If running from source (Python dir), set home to project root
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if os.path.basename(current_dir).lower() == 'python':
                self.home = os.path.dirname(current_dir)
            else:
                self.home = current_dir
            
        # Ensure stdout/stderr exist to prevent argparse crashes (e.g. pythonw or noconsole)
        if sys.stdout is None:
            sys.stdout = open(os.devnull, 'w')
        if sys.stderr is None:
            sys.stderr = open(os.devnull, 'w')
            
        self.source = os.path.join(self.home, "Python")
        self.binhome = os.path.join(self.home, "bin")
        self.curpidf = os.path.join(self.home, "rjpids.ini")
        self.current_pid = os.getpid()
        self.multi_instance = 0
        self.game_path = ""
        self.game_name = ""
        self.game_dir = ""
        self.plink = ""
        self.scpath = ""
        self.scextn = ""
        self.ini_path = ""
        self.exe_list = ""
        self.joymessage = "No joysticks detected"
        self.joycount = 0
        self.mapper_extension = "gamecontroller.amgp"  # Default for antimicrox
        
        self.game_process = None
        self.borderless_process = None
        self.dynamic_splash = None
        self.args = None
        self.iso_path = ""

        # Set up message display (logging) early
        self.setup_message_display()

        self.update_splash_progress(10, "Initializing...")

        # Get command line arguments
        self.update_splash_progress(20, "Parsing arguments...")
        self.parse_arguments()
        
        # Check if we're running as admin
        self.update_splash_progress(30, "Checking permissions...")
        self.is_admin = self.check_admin()
        
        # Check for other instances
        self.update_splash_progress(40, "Checking instances...")
        if not self.check_instances():
            sys.exit(0)
        
        # Load configuration
        self.update_splash_progress(50, "Loading configuration...")
        self.load_config()
        # Update log to write to Game.ini directory (matching C launcher behavior)
        if self.ini_path:
            log_dir = os.path.dirname(self.ini_path)
            log_file = os.path.join(log_dir, "launcher.log")
            for handler in logging.getLogger().handlers:
                if isinstance(handler, logging.FileHandler):
                    handler.close()
                    handler.baseFilename = os.path.abspath(log_file)
                    break
        
        # Modify config if requested via CLI
        if self.args and (self.args.set or self.args.clear):
            self.modify_config()
            self.load_config() # Reload to apply changes

        # Initialize joystick detection
        self.update_splash_progress(70, "Detecting input devices...")
        self.detect_joysticks()
        
        # Initialize the sequence executor
        self.update_splash_progress(90, "Preparing execution sequences...")
        
        # Initialize plugin manager if available (optional for minimal build)
        self.plugin_manager = None
        if os.environ.get('LAUNCHER_MINIMAL') != '1':
            try:
                from Python.managers.plugin_manager import PluginManager
                self.plugin_manager = PluginManager()
            except ImportError:
                try:
                    from managers.plugin_manager import PluginManager
                    self.plugin_manager = PluginManager()
                except ImportError:
                    logging.debug("Plugin manager not available")
        
        self.executor = SequenceExecutor(self)
        
        # Initialize tray menu or hotkey handler (optional for minimal build)
        self.hotkey_handler = None
        self.tray_menu = None 
        
        # Try to initialize tray menu for all builds
        try:
            from Python.tray_menu import LauncherTrayMenu, TRAY_AVAILABLE
            if TRAY_AVAILABLE:
                self.tray_menu = LauncherTrayMenu(self)
                self.tray_menu.start()
                logging.info("Tray menu initialized")
        except ImportError:
            try:
                from tray_menu import LauncherTrayMenu, TRAY_AVAILABLE
                if TRAY_AVAILABLE:
                    self.tray_menu = LauncherTrayMenu(self)
                    self.tray_menu.start()
                    logging.info("Tray menu initialized")
            except ImportError:
                logging.debug("Tray menu not available")
        
        # If tray menu failed, fall back to hotkey handler (but not for minimal build)
        if not self.tray_menu and os.environ.get('LAUNCHER_MINIMAL') != '1':
            try:
                from Python.hotkey_handler import HotkeyHandler, HOTKEY_AVAILABLE
                if HOTKEY_AVAILABLE:
                    self.hotkey_handler = HotkeyHandler(self)
                    self.hotkey_handler.start()
                    logging.info("Hotkey handler initialized (Ctrl+Alt+F9 for help)") 
                    print("\n[INFO] Hotkey handler active. Press Ctrl+Alt+F9 for help.\n")
            except ImportError:
                try:
                    from hotkey_handler import HotkeyHandler, HOTKEY_AVAILABLE
                    if HOTKEY_AVAILABLE:
                        self.hotkey_handler = HotkeyHandler(self)
                except ImportError:
                    logging.debug("Hotkey handler not available")

        # Close splash screen after initialization is done
        self.update_splash_progress(100, "Ready to launch!")
        self.close_splash()
        
        # Start dynamic splash (after static splash closes)
        self.dynamic_splash = DynamicSplash(self.scpath if self.scpath else self.home)
        self.dynamic_splash.show()

    def parse_arguments(self):
        """Parse command line arguments"""
        parser = argparse.ArgumentParser(description="Game Launcher - A portable environment manager for games.")
        parser.add_argument("target", nargs="?", help="Target shortcut or executable")
        parser.add_argument("--home", help="Override home directory for asset redirection")
        parser.add_argument("--set", action="append", help="Set config value: Section.Key=Value")
        parser.add_argument("--clear", action="append", help="Clear config value: Section.Key")
        
        # Use parse_known_args to allow for other potential flags
        self.args, unknown = parser.parse_known_args()
        args = self.args

        # Reconstruct target path if it contained spaces and wasn't quoted in the shortcut.
        # This is required because Shortcut.exe crashes (0xC0000005) if parameters are double-quoted.
        if args.target and unknown:
            # Collect all positional tokens
            pos_tokens = [args.target]
            for item in unknown:
                if item.startswith('-'):
                    break
                pos_tokens.append(item)
            # Try progressive joins from longest to shortest
            for t in range(len(pos_tokens), 0, -1):
                reconstructed = " ".join(pos_tokens[:t])
                if os.path.exists(reconstructed) or reconstructed.lower().endswith('.lnk'):
                    args.target = reconstructed
                    break

        if args.home:
            self.home = os.path.abspath(args.home)
            self.source = os.path.join(self.home, "Python")
            self.binhome = os.path.join(self.home, "bin")
            self.curpidf = os.path.join(self.home, "rjpids.ini")
            
        if args.target:
            self.plink = args.target
            # Get file extension
            _, self.scpath, self.scextn, self.game_name = self.split_path(self.plink)
            # Display message
            self.show_message(f"Launching: {self.plink}")
        else:
            self.show_message("No Item Detected")
            self.close_splash()
            time.sleep(3)
            sys.exit(0)
    
    def check_admin(self):
        """Check if running as administrator"""
        try:
            if platform.system() == 'Windows':
                return ctypes.windll.shell32.IsUserAnAdmin() != 0
            else:
                return os.geteuid() == 0
        except:
            return False
    
    def setup_message_display(self):
        """Set up message display (tooltip or console)"""
        # Configure logging to file (default to home, will update to Game.ini dir later)
        log_file = os.path.join(self.home, "launcher.log")
        logging.basicConfig(
            filename=log_file,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            filemode='w'
        )

        # Redirect stderr to capture crashes
        def handle_exception(exc_type, exc_value, exc_traceback):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_traceback)
                return
            logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))
        
        sys.excepthook = handle_exception
        logging.info(f"Launcher started. Home directory: {self.home}")
    
    def show_message(self, message):
        """Show a message to the user"""
        print(message)
        logging.info(message)
        try:
            import pyi_splash
            if pyi_splash.is_alive():
                pyi_splash.update_text(message)
        except ImportError:
            pass
        # In a full implementation, this could update a GUI or show a notification

    def update_splash_progress(self, percent, message):
        """Update splash screen with text-based progress bar"""
        try:
            import pyi_splash
            if pyi_splash.is_alive():
                bar_len = 25
                filled = int(bar_len * percent / 100)
                bar = "█" * filled + "-" * (bar_len - filled)
                pyi_splash.update_text(f"{message}\n[{bar}] {percent}%")
        except ImportError:
            pass
        logging.info(f"Progress {percent}%: {message}")
    
    def check_instances(self):
        """Check for other instances of the launcher"""
        if os.path.exists(self.curpidf):
            config = configparser.ConfigParser()
            config.read(self.curpidf)
            
            try:
                instance_pid = int(config.get('Instance', 'pid', fallback='0'))
                self.multi_instance = int(config.get('Instance', 'multi_instance', fallback='0'))
                
                if self.multi_instance == 1:
                    return True
                
                # Check if the process is still running
                if instance_pid != 0 and instance_pid != self.current_pid:
                    if PSUTIL_AVAILABLE:
                        try:
                            process = psutil.Process(instance_pid)
                            if process.is_running():
                                # Ask user if they want to terminate the running instance
                                response = input("Would you like to terminate the running instance? (y/n): ")
                                if response.lower() == 'y':
                                    process.terminate()
                                    time.sleep(1)
                                    if process.is_running():
                                        process.kill()
                                else:
                                    return False
                        except (psutil.NoSuchProcess, Exception):
                            pass  # Process doesn't exist, continue
                    else:
                        # Without psutil, just log a warning
                        logging.warning(f"Cannot check if PID {instance_pid} is running (psutil not available)")
            except Exception as e:
                pass
        
        return True
    
    def load_config(self):
        """Load configuration from Game.ini"""
        # First check if there's a Game.ini in the same directory as the shortcut
        game_ini = self._find_game_ini(self.scpath)

        if not game_ini:
            # Fall back to config.ini in the home directory
            game_ini = os.path.join(self.home, "config.ini")

        if not os.path.exists(game_ini):
            self.show_message("No configuration file found")
            return
        self.ini_path = game_ini

        config = configparser.ConfigParser()
        config.read(game_ini)

        s = lambda name: self._get_section(config, name)

        # Load game information
        sec = s('Game')
        if sec:
            self.game_path = config.get(sec, 'executable', fallback='')
            self.game_dir = config.get(sec, 'directory', fallback='')
            self.game_name = config.get(sec, 'name', fallback=self.game_name)
            self.iso_path = config.get(sec, 'isopath', fallback='')

        # Load Options section
        sec = s('Options')
        if sec:
            self.run_as_admin = config.getboolean(sec, 'RunAsAdmin', fallback=False)
            self.hide_taskbar = config.getboolean(sec, 'HideTaskbar', fallback=False)
            self.borderless = config.get(sec, 'Borderless', fallback='0')
            self.use_kill_list = config.getboolean(sec, 'UseKillList', fallback=False)
            self.kill_list_str = config.get(sec, 'KillList', fallback='')
            self.kill_list = [x.strip() for x in self.kill_list_str.split(',') if x.strip()]
            self.terminate_borderless_on_exit = config.getboolean(sec, 'TerminateBorderlessOnExit', fallback=True)

        # Load mapperprofiles section
        sec = s('mapperprofiles')
        if sec:
            self.player1_profile = config.get(sec, 'player1profile', fallback='')
            self.player1_profile_options = config.get(sec, 'player1profileoptions', fallback='')
            self.player1_profile_arguments = config.get(sec, 'player1profilearguments', fallback='')
            self.player2_profile = config.get(sec, 'player2profile', fallback='')
            self.player2_profile_options = config.get(sec, 'player2profileoptions', fallback='')
            self.player2_profile_arguments = config.get(sec, 'player2profilearguments', fallback='')
            self.desk_profile = config.get(sec, 'deskprofile', fallback='')
            self.desk_profile_options = config.get(sec, 'deskprofileoptions', fallback='')
            self.desk_profile_arguments = config.get(sec, 'deskprofilearguments', fallback='')
        else:
            self.player1_profile = ''
            self.player1_profile_options = ''
            self.player1_profile_arguments = ''
            self.player2_profile = ''
            self.player2_profile_options = ''
            self.player2_profile_arguments = ''
            self.desk_profile = ''
            self.desk_profile_options = ''
            self.desk_profile_arguments = ''

        # Load MonitorLayouts section
        sec = s('MonitorLayouts')
        if sec:
            self.monitor_game_cfg = config.get(sec, 'monitorgamecfg', fallback='')
            self.monitor_game_cfg_options = config.get(sec, 'monitorgamecfgoptions', fallback='')
            self.monitor_game_cfg_arguments = config.get(sec, 'monitorgamecfgarguments', fallback='')
            self.monitor_desk_cfg = config.get(sec, 'monitordeskcfg', fallback='')
            self.monitor_desk_cfg_options = config.get(sec, 'monitordeskcfgoptions', fallback='')
            self.monitor_desk_cfg_arguments = config.get(sec, 'monitordeskcfgarguments', fallback='')

        # Load ControllerMapper section
        sec = s('ControllerMapper')
        if sec:
            self.controller_mapper_app = config.get(sec, 'controllermapperpath', fallback='')
            self.controller_mapper_options = config.get(sec, 'controllermapperpathoptions', fallback='')
            self.controller_mapper_arguments = config.get(sec, 'controllermapperpatharguments', fallback='')

        # Load BorderlessWindowing section
        sec = s('BorderlessWindowing')
        if sec:
            self.borderless_app = config.get(sec, 'borderlesswindowingpath', fallback='')
            self.borderless_options = config.get(sec, 'borderlesswindowingpathoptions', fallback='')
            self.borderless_arguments = config.get(sec, 'borderlesswindowingpatharguments', fallback='')

        # Load Monitor section
        sec = s('Monitor')
        if sec:
            self.monitorapp = config.get(sec, 'monitorapppath', fallback='')
            self.monitorapp_options = config.get(sec, 'monitorapppathoptions', fallback='')
            self.monitorapp_arguments = config.get(sec, 'monitorapppatharguments', fallback='')

        # Load DiscMount section
        sec = s('DiscMount')
        if sec:
            self.disc_mount_app = config.get(sec, 'discmountpath', fallback='')
            self.disc_mount_options = config.get(sec, 'discmountpathoptions', fallback='')
            self.disc_mount_arguments = config.get(sec, 'discmountpatharguments', fallback='')
            self.disc_mount_wait = config.getboolean(sec, 'discmountpathrunwait', fallback=False)
        # Load DiscDrivePrefs section
        sec = s('DiscDrivePrefs')
        if sec:
            self.disc_mount_cfg_enabled = config.getboolean(sec, 'enablediscmountcfg', fallback=False)
            self.disc_mount_cfg = config.get(sec, 'discmountcfgpath', fallback='')
            self.disc_mount_cfg_options = config.get(sec, 'discmountcfgpathoptions', fallback='')
            self.disc_mount_cfg_arguments = config.get(sec, 'discmountcfgpatharguments', fallback='')
            self.disc_unmount_cfg_enabled = config.getboolean(sec, 'enablediscunmountcfg', fallback=False)
            self.disc_unmount_cfg = config.get(sec, 'discunmountcfgpath', fallback='')
            self.disc_unmount_cfg_options = config.get(sec, 'discunmountcfgpathoptions', fallback='')
            self.disc_unmount_cfg_arguments = config.get(sec, 'discunmountcfgpatharguments', fallback='')

        # Load AudioApp section
        sec = s('AudioApp')
        if sec:
            self.audio_app_enabled = config.getboolean(sec, 'enableaudioapp', fallback=False)
            self.audio_app = config.get(sec, 'audioapppath', fallback='')
            self.audio_app_options = config.get(sec, 'audioapppathoptions', fallback='')
            self.audio_app_arguments = config.get(sec, 'audioapppatharguments', fallback='')
            self.audio_app_run_wait = config.getboolean(sec, 'audioapppathrunwait', fallback=False)

        # Load BorderlessProfiles section
        sec = s('BorderlessProfiles')
        if sec:
            self.unborder_cfg_enabled = config.getboolean(sec, 'enableunbordercfg', fallback=False)
            self.unborder_cfg = config.get(sec, 'unbordercfgpath', fallback='')
            self.unborder_cfg_options = config.get(sec, 'unbordercfgpathoptions', fallback='')
            self.unborder_cfg_arguments = config.get(sec, 'unbordercfgpatharguments', fallback='')
            self.reborder_cfg_enabled = config.getboolean(sec, 'enablerebordercfg', fallback=False)
            self.reborder_cfg = config.get(sec, 'rebordercfgpath', fallback='')
            self.reborder_cfg_options = config.get(sec, 'rebordercfgpathoptions', fallback='')
            self.reborder_cfg_arguments = config.get(sec, 'rebordercfgpatharguments', fallback='')

        # Load AudioPresets section
        sec = s('AudioPresets')
        if sec:
            self.audio_game_cfg_enabled = config.getboolean(sec, 'enableaudiogamecfg', fallback=False)
            self.audio_game_cfg = config.get(sec, 'audiogamecfgpath', fallback='')
            self.audio_game_cfg_options = config.get(sec, 'audiogamecfgpathoptions', fallback='')
            self.audio_game_cfg_arguments = config.get(sec, 'audiogamecfgpatharguments', fallback='')
            self.audio_desk_cfg_enabled = config.getboolean(sec, 'enableaudiodeskcfg', fallback=False)
            self.audio_desk_cfg = config.get(sec, 'audiodeskcfgpath', fallback='')
            self.audio_desk_cfg_options = config.get(sec, 'audiodeskcfgpathoptions', fallback='')
            self.audio_desk_cfg_arguments = config.get(sec, 'audiodeskcfgpatharguments', fallback='')

        # Load CloudSync configuration
        sec = s('CloudSync')
        if sec:
            self.cloud_enabled = config.getboolean(sec, 'enablecloudsync', fallback=False)
            self.cloud_app = config.get(sec, 'cloudsyncpath', fallback='')
            self.cloud_options = config.get(sec, 'cloudsyncpathoptions', fallback='')
            self.cloud_arguments = config.get(sec, 'cloudsyncpatharguments', fallback='')
            self.cloud_wait = config.getboolean(sec, 'cloudsyncpathrunwait', fallback=False)
        else:
            self.cloud_enabled = False

        # Load LocalBackup configuration
        sec = s('LocalBackup')
        if sec:
            self.backup_enabled = config.getboolean(sec, 'enablelocalbackup', fallback=False)
            self.backup_app = config.get(sec, 'localbackuppath', fallback='')
            self.backup_options = config.get(sec, 'localbackuppathoptions', fallback='')
            self.backup_arguments = config.get(sec, 'localbackuppatharguments', fallback='')
            self.backup_wait = config.getboolean(sec, 'localbackuppathrunwait', fallback=False)
        else:
            self.backup_enabled = False

        # Load PreLaunch section
        sec = s('PreLaunch')
        if sec:
            self.pre_launch_app_1 = config.get(sec, 'App1', fallback='')
            self.pre_launch_app_1_options = config.get(sec, 'App1Options', fallback='')
            self.pre_launch_app_1_arguments = config.get(sec, 'App1Arguments', fallback='')
            self.pre_launch_app_1_wait = config.getboolean(sec, 'App1Wait', fallback=False)

            self.pre_launch_app_2 = config.get(sec, 'App2', fallback='')
            self.pre_launch_app_2_options = config.get(sec, 'App2Options', fallback='')
            self.pre_launch_app_2_arguments = config.get(sec, 'App2Arguments', fallback='')
            self.pre_launch_app_2_wait = config.getboolean(sec, 'App2Wait', fallback=False)

            self.pre_launch_app_3 = config.get(sec, 'App3', fallback='')
            self.pre_launch_app_3_options = config.get(sec, 'App3Options', fallback='')
            self.pre_launch_app_3_arguments = config.get(sec, 'App3Arguments', fallback='')
            self.pre_launch_app_3_wait = config.getboolean(sec, 'App3Wait', fallback=False)

        # Load PostLaunch section
        sec = s('PostLaunch')
        if sec:
            self.post_launch_app_1 = config.get(sec, 'App1', fallback='')
            self.post_launch_app_1_options = config.get(sec, 'App1Options', fallback='')
            self.post_launch_app_1_arguments = config.get(sec, 'App1Arguments', fallback='')
            self.post_launch_app_1_wait = config.getboolean(sec, 'App1Wait', fallback=False)

            self.post_launch_app_2 = config.get(sec, 'App2', fallback='')
            self.post_launch_app_2_options = config.get(sec, 'App2Options', fallback='')
            self.post_launch_app_2_arguments = config.get(sec, 'App2Arguments', fallback='')
            self.post_launch_app_2_wait = config.getboolean(sec, 'App2Wait', fallback=False)

            self.post_launch_app_3 = config.get(sec, 'App3', fallback='')
            self.post_launch_app_3_options = config.get(sec, 'App3Options', fallback='')
            self.post_launch_app_3_arguments = config.get(sec, 'App3Arguments', fallback='')
            self.post_launch_app_3_wait = config.getboolean(sec, 'App3Wait', fallback=False)

            self.just_after_launch_app = config.get(sec, 'JustAfterLaunchApp', fallback='')
            self.just_after_launch_options = config.get(sec, 'JustAfterLaunchOptions', fallback='')
            self.just_after_launch_arguments = config.get(sec, 'JustAfterLaunchArguments', fallback='')
            self.just_after_launch_wait = config.getboolean(sec, 'JustAfterLaunchWait', fallback=False)

            self.just_before_exit_app = config.get(sec, 'JustBeforeExitApp', fallback='')
            self.just_before_exit_options = config.get(sec, 'JustBeforeExitOptions', fallback='')
            self.just_before_exit_arguments = config.get(sec, 'JustBeforeExitArguments', fallback='')
            self.just_before_exit_wait = config.getboolean(sec, 'JustBeforeExitWait', fallback=False)

        # Load sequences
        sec = s('Sequences')
        if sec:
            # Get launch sequence
            launch_sequence_str = config.get(sec, 'launchsequence', fallback='')
            if launch_sequence_str:
                self.launch_sequence = launch_sequence_str.split(',')
            else:
                # Default launch sequence
                self.launch_sequence = [
                    "Controller-Mapper", 
                    "Monitor-Config", 
                    "Kill-List",
                    "Kill-Game",
                    "mount-disc"
                    "No-TB",
                    "Pre1", 
                    "Pre2", 
                    "Borderless", 
                    "Pre3", 
                    "Cloud-Sync",
                    "Borderless",
                    "RunAudio"
                    "Backup",
                ]
            
            # Get exit sequence
            exit_sequence_str = config.get('Sequences', 'exitsequence', fallback='')
            if exit_sequence_str:
                self.exit_sequence = exit_sequence_str.split(',')
            else:
                # Default exit sequence
                self.exit_sequence = [
                    "Kill-Game",
                    "Kill-List",
                    "Monitor-Config", 
                    "Taskbar",
                    "Post1", 
                    "Controller-Mapper",
                    "Borderless", 
                    "Post2", 
                    "ReturnAudio",
                    "Post3", 
                    "Unmount-disc",
                    "Cloud-Sync",
                    "Backup",
                ]
        
        # Launcher options/arguments fallback: if an application's options/arguments
        # are empty, use the corresponding profile section as fallback source.
        # Mapping: application section → profile section with fallback options/arguments
        launcher_fallbacks = [
            ('controller_mapper_options', 'controller_mapper_arguments', 'player1_profile_options', 'player1_profile_arguments'),
            ('monitorapp_options', 'monitorapp_arguments', 'monitor_game_cfg_options', 'monitor_game_cfg_arguments'),
            ('disc_mount_options', 'disc_mount_arguments', 'disc_mount_cfg_options', 'disc_mount_cfg_arguments'),
            ('audio_app_options', 'audio_app_arguments', 'audio_game_cfg_options', 'audio_game_cfg_arguments'),
            ('borderless_options', 'borderless_arguments', 'unborder_cfg_options', 'unborder_cfg_arguments'),
        ]
        for app_opts_key, app_args_key, profile_opts_key, profile_args_key in launcher_fallbacks:
            if not getattr(self, app_opts_key, ''):
                fallback_opts = getattr(self, profile_opts_key, '')
                if fallback_opts:
                    setattr(self, app_opts_key, fallback_opts)
                    logging.info(f"Fallback: {app_opts_key} empty, using {profile_opts_key}")
            if not getattr(self, app_args_key, ''):
                fallback_args = getattr(self, profile_args_key, '')
                if fallback_args:
                    setattr(self, app_args_key, fallback_args)
                    logging.info(f"Fallback: {app_args_key} empty, using {profile_args_key}")

        # Run path discovery if needed (discover save/config files from PCGW templates)
        try:
            from Python.utils.path_discovery import discover_and_update_paths
            if discover_and_update_paths(game_ini, context='launch'):
                logging.info(f"Pre-launch path discovery completed for {self.game_name}")
                # Reload config to get updated paths
                config.read(game_ini)
        except Exception as e:
            logging.warning(f"Pre-launch path discovery failed: {e}")

    def modify_config(self):
        """Modify the configuration file based on CLI arguments."""
        if not self.ini_path or not os.path.exists(self.ini_path):
            self.show_message("Config file not found, cannot modify.")
            return

        config = configparser.ConfigParser()
        config.read(self.ini_path)

        changed = False

        if self.args.set:
            for item in self.args.set:
                if '=' in item:
                    key_part, value = item.split('=', 1)
                    if '.' in key_part:
                        section, key = key_part.split('.', 1)
                        existing = self._get_section(config, section)
                        if not existing:
                            config.add_section(section)
                        else:
                            section = existing
                        config.set(section, key, value)
                        changed = True
                        self.show_message(f"Set {section}.{key} = {value}")

        if self.args.clear:
            for item in self.args.clear:
                if '.' in item:
                    section, key = item.split('.', 1)
                    existing = self._get_section(config, section)
                    if existing and config.has_option(existing, key):
                        config.remove_option(existing, key)
                        changed = True
                        self.show_message(f"Cleared {existing}.{key}")

        if changed:
            with open(self.ini_path, 'w') as f:
                config.write(f)
            self.show_message("Configuration updated.")

    def resolve_path(self, path):
        """Substitute variables in path."""
        if not path or not isinstance(path, str):
            return path
            
        # Define variables
        vars_map = {
            '$MAPPER': self.controller_mapper_app,
            '$BORDERLESS': self.borderless_app,
            '$MONITORAPP': self.monitorapp,
            '$CLOUDAPP': getattr(self, 'cloud_app', ''),
            '$BACKUPAPP': getattr(self, 'backup_app', ''),
            '$GAMEDIR': self.game_dir,
            '$GAMEEXE': self.game_path,
            '$GAMENAME': self.game_name,
            '$HOME': self.home,
            '$ISO': self.iso_path
        }
        
        # Simple replacement
        for var, value in vars_map.items():
            if var in path:
                path = path.replace(var, value)
        return path
    
    def detect_joysticks(self):
        """Detect connected joysticks - stubbed for minimal build"""
        self.joycount = 0
        self.joymessage = "Joystick detection disabled (minimal build)"
    
    def backup_save_files(self):
        """Backs up the saves directory if configured."""
        if not getattr(self, 'backup_saves', False):
            return

        # Determine save directory (default to Saves in profile dir)
        save_dir = os.path.join(self.home, "Saves")
        
        if not os.path.exists(save_dir):
            self.show_message("Save directory not found, skipping backup.")
            return

        backup_root = os.path.join(self.home, "Backups")
        if not os.path.exists(backup_root):
            os.makedirs(backup_root)

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = f"SaveBackup_{timestamp}"
        backup_path = os.path.join(backup_root, backup_name)

        try:
            shutil.make_archive(backup_path, 'zip', save_dir)
            self.show_message(f"Backed up saves to {backup_name}.zip")
            
            # Rotate backups
            backups = sorted([f for f in os.listdir(backup_root) if f.startswith("SaveBackup_") and f.endswith(".zip")])
            while len(backups) > self.max_backups:
                oldest = backups.pop(0)
                os.remove(os.path.join(backup_root, oldest))
                self.show_message(f"Removed old backup: {oldest}")
        except Exception as e:
            self.show_message(f"Backup failed: {e}")

    def cloud_sync_download(self):
        """Download saves from cloud before launching game."""
        if not getattr(self, 'cloud_enabled', False) or not getattr(self, 'cloud_backup_on_launch', False):
            return
        
        try:
            from Python.utils.cloud_path_utils import build_rclone_command, generate_remote_path, strip_path_variables
            
            cloud_app = self.resolve_path(self.cloud_app)
            if not cloud_app or not os.path.exists(cloud_app):
                logging.warning(f"Cloud sync app not found: {cloud_app}")
                return
            
            # Get save path (use cloud_save_path or discover from SAVE section)
            save_path = self.cloud_save_path
            if not save_path:
                # Try to get from SAVE section
                config = configparser.ConfigParser()
                config.read(self.ini_path)
                from Python.utils.cloud_path_utils import get_primary_save_path
                save_path = get_primary_save_path(config, 'SAVE', 'Windows')
            
            if not save_path:
                logging.warning("No save path configured for cloud sync")
                return
            
            # Expand save path
            local_path = os.path.expandvars(save_path)
            if '<path-to-game>' in local_path:
                local_path = local_path.replace('<path-to-game>', self.game_dir)
            
            # Generate remote path
            remote_path = generate_remote_path(
                self.cloud_user_prefix,
                self.game_name,
                save_path,
                self.game_dir
            )
            
            # Build rclone command
            cmd = build_rclone_command(
                cloud_app,
                self.cloud_remote_name,
                remote_path,
                local_path,
                sync_mode='sync',
                direction='download',
                options=self.cloud_options
            )
            
            if self.cloud_arguments:
                cmd += f' {self.cloud_arguments}'
            
            self.show_message(f"Downloading saves from cloud: {remote_path}")
            logging.info(f"Cloud sync download: {cmd}")
            
            self.run_process(cmd, wait=self.cloud_wait)
            
        except Exception as e:
            logging.error(f"Cloud sync download failed: {e}", exc_info=True)
            self.show_message(f"Cloud sync download failed: {e}")

    def cloud_sync_upload(self):
        """Upload saves to cloud after game exits."""
        if not getattr(self, 'cloud_enabled', False) or not getattr(self, 'cloud_upload_on_exit', False):
            return
        
        try:
            from Python.utils.cloud_path_utils import build_rclone_command, generate_remote_path, strip_path_variables
            
            cloud_app = self.resolve_path(self.cloud_app)
            if not cloud_app or not os.path.exists(cloud_app):
                logging.warning(f"Cloud sync app not found: {cloud_app}")
                return
            
            # Get save path
            save_path = self.cloud_save_path
            if not save_path:
                config = configparser.ConfigParser()
                config.read(self.ini_path)
                from Python.utils.cloud_path_utils import get_primary_save_path
                save_path = get_primary_save_path(config, 'SAVE', 'Windows')
            
            if not save_path:
                logging.warning("No save path configured for cloud sync")
                return
            
            # Expand save path
            local_path = os.path.expandvars(save_path)
            if '<path-to-game>' in local_path:
                local_path = local_path.replace('<path-to-game>', self.game_dir)
            
            # Generate remote path
            remote_path = generate_remote_path(
                self.cloud_user_prefix,
                self.game_name,
                save_path,
                self.game_dir
            )
            
            # Build rclone command
            cmd = build_rclone_command(
                cloud_app,
                self.cloud_remote_name,
                remote_path,
                local_path,
                sync_mode='sync',
                direction='upload',
                options=self.cloud_options
            )
            
            if self.cloud_arguments:
                cmd += f' {self.cloud_arguments}'
            
            self.show_message(f"Uploading saves to cloud: {remote_path}")
            logging.info(f"Cloud sync upload: {cmd}")
            
            self.run_process(cmd, wait=self.cloud_wait)
            
        except Exception as e:
            logging.error(f"Cloud sync upload failed: {e}", exc_info=True)
            self.show_message(f"Cloud sync upload failed: {e}")

    def local_backup_create(self, on_launch=True):
        """Create local backup of saves."""
        if not getattr(self, 'backup_enabled', False):
            return
        
        # Check if we should backup at this point
        if on_launch and not getattr(self, 'backup_backup_on_launch', False):
            return
        if not on_launch and not getattr(self, 'backup_backup_on_exit', False):
            return
        
        try:
            from Python.utils.cloud_path_utils import build_ludusavi_command, generate_local_backup_path
            
            backup_app = self.resolve_path(self.backup_app)
            if not backup_app or not os.path.exists(backup_app):
                logging.warning(f"Backup app not found: {backup_app}")
                return
            
            # Generate backup path with timestamp
            backup_path = generate_local_backup_path(
                self.backup_local_prefix,
                self.game_name,
                use_timestamp=True
            )
            
            # Build ludusavi command
            cmd = build_ludusavi_command(
                backup_app,
                backup_path,
                self.game_name,
                action='backup',
                options=self.backup_options
            )
            
            if self.backup_arguments:
                cmd += f' {self.backup_arguments}'
            
            timing = "pre-launch" if on_launch else "post-exit"
            self.show_message(f"Creating local backup ({timing}): {backup_path}")
            logging.info(f"Local backup ({timing}): {cmd}")
            
            self.run_process(cmd, wait=self.backup_wait)
            
            # Rotate backups if max_backups is set
            if hasattr(self, 'backup_max_backups_new'):
                self._rotate_local_backups()
            
        except Exception as e:
            logging.error(f"Local backup failed: {e}", exc_info=True)
            self.show_message(f"Local backup failed: {e}")

    def _rotate_local_backups(self):
        """Remove old backups beyond max_backups limit."""
        try:
            from Python.utils.cloud_path_utils import generate_local_backup_path
            
            # Get base backup directory (without timestamp)
            base_backup_dir = generate_local_backup_path(
                self.backup_local_prefix,
                self.game_name,
                use_timestamp=False
            )
            
            if not os.path.exists(base_backup_dir):
                return
            
            # Get all backup directories (timestamped subdirectories)
            backups = []
            for item in os.listdir(base_backup_dir):
                item_path = os.path.join(base_backup_dir, item)
                if os.path.isdir(item_path):
                    backups.append((item, item_path))
            
            # Sort by name (timestamp format ensures chronological order)
            backups.sort()
            
            # Remove oldest backups if we exceed max
            max_backups = getattr(self, 'backup_max_backups_new', 5)
            while len(backups) > max_backups:
                oldest_name, oldest_path = backups.pop(0)
                shutil.rmtree(oldest_path)
                logging.info(f"Removed old backup: {oldest_name}")
                self.show_message(f"Removed old backup: {oldest_name}")
                
        except Exception as e:
            logging.error(f"Backup rotation failed: {e}", exc_info=True)


    def run_game(self):
        """Run the main game executable"""
        self.show_message(f"Launching game: {self.game_name}")
        
        # Prepare the command
        if not self.game_path:
            self.game_path = self.plink
        
        # Get the game directory
        if not self.game_dir:
            self.game_dir = os.path.dirname(self.game_path)
    
        # Close dynamic splash before launching the game
        if self.dynamic_splash:
            self.dynamic_splash.close()

        game_path_resolved = self.resolve_path(self.game_path)
        # Run the game
        if self.run_as_admin and platform.system() == 'Windows' and not self.is_admin:
            # Use PowerShell to run as admin
            cmd = f'powershell -Command "Start-Process \'{game_path_resolved}\' -Verb RunAs"'
            self.game_process = self.run_process(cmd, cwd=self.game_dir)
        else:
            self.game_process = self.run_process(f'"{game_path_resolved}"', cwd=self.game_dir)
        
        # Wait for the game to exit
        if self.game_process:
            self.game_process.wait()

    def run(self):
        """Main execution flow"""
        try:
            # Write current PID to the PID file
            self.write_pid_file()
            
            # Cloud sync download (before launch)
            self.cloud_sync_download()
            
            # Local backup (before launch)
            self.local_backup_create(on_launch=True)
            
            # Backup saves if enabled
            self.backup_save_files()

            # Execute launch sequence
            self.executor.execute('launch_sequence')
            
            # Run the game
            self.run_game()
            
            # Run path discovery after game exits (to discover newly created saves)
            try:
                from Python.utils.path_discovery import discover_and_update_paths
                if discover_and_update_paths(self.ini_path, context='exit'):
                    logging.info(f"Post-exit path discovery completed for {self.game_name}")
            except Exception as e:
                logging.warning(f"Post-exit path discovery failed: {e}")
            
            # Local backup (after exit)
            self.local_backup_create(on_launch=False)
            
            # Cloud sync upload (after exit)
            self.cloud_sync_upload()
            
            # Execute exit sequence
            self.executor.execute('exit_sequence')
            
        except Exception as e:
            self.show_message(f"Error: {e}")
        finally:
            # Stop tray menu or hotkey handler
            if self.tray_menu:
                self.tray_menu.stop()
            if self.hotkey_handler:
                self.hotkey_handler.stop()
            
            # Final cleanup to ensure system state is restored
            self.executor.ensure_cleanup()
            if self.use_kill_list:
                self.kill_processes_in_list()
            self.show_message("Exiting launcher")
    
    # Helper methods
    @staticmethod
    def _find_game_ini(directory):
        """Find Game.ini in directory with case-insensitive matching."""
        if not os.path.isdir(directory):
            return None
        for entry in os.listdir(directory):
            if entry.lower() == 'game.ini':
                return os.path.join(directory, entry)
        return None

    @staticmethod
    def _get_section(config, name):
        """Case-insensitive section lookup in a ConfigParser."""
        for section in config.sections():
            if section.lower() == name.lower():
                return section
        return None

    def split_path(self, path):
        """Split a path into components (similar to SplitPath in AHK)"""
        p = Path(path)
        return str(p), str(p.parent), p.suffix.lstrip('.'), p.stem
    
    def run_process(self, cmd: Union[str, List[str]], cwd: Optional[str] = None, wait: bool = False, hide: bool = False) -> Optional[subprocess.Popen]:
        """
        Run a process with the given command in a more robust and secure way.

        Args:
            cmd: The command to run, as a string or a list of arguments.
            cwd: The working directory for the process.
            wait: If True, wait for the process to complete and capture output.
            hide: If True on Windows, create the process with no window.

        Returns:
            A subprocess.Popen object if wait is False and the process starts, otherwise None.
        """
        kwargs = {'cwd': cwd}
        
        # On Windows, we use shlex to safely parse command strings into lists,
        # avoiding shell=True for better security.
        if platform.system() == 'Windows':
            if isinstance(cmd, str):
                cmd_list = shlex.split(cmd)
            else:
                cmd_list = cmd # Assume it's already a list
            
            # Set creation flags for hiding the window
            creation_flags = 0
            if hide:
                creation_flags = subprocess.CREATE_NO_WINDOW
            kwargs['creationflags'] = creation_flags
        else: # For Linux/macOS
            # On non-Windows, shell=True is often more convenient for string commands.
            # For list commands, shell=False is the default and correct way.
            if isinstance(cmd, str):
                kwargs['shell'] = True
            cmd_list = cmd

        try:
            self.show_message(f"Executing: {cmd}")
            
            # If we need to wait, it's better to capture output for debugging.
            if wait:
                # Redirect stdout and stderr to capture output for logging
                process = subprocess.Popen(cmd_list, **kwargs, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                stdout, stderr = process.communicate() # This also waits for the process to finish
                if process.returncode != 0:
                    # Decode stderr and log it if the process failed
                    error_message = stderr.decode('utf-8', errors='ignore').strip()
                    self.show_message(f"Process '{cmd_list[0]}' exited with error code {process.returncode}: {error_message}")
                    logging.warning(f"Process '{cmd_list}' exited with code {process.returncode}. Stderr: {error_message}")
                return None
            else:
                # For non-waiting processes, don't capture stdout/stderr to avoid pipe buffer deadlocks
                process = subprocess.Popen(cmd_list, **kwargs)
                return process

        except FileNotFoundError:
            self.show_message(f"Error: Command not found for '{str(cmd)}'")
            logging.error(f"Command not found: {cmd}", exc_info=True)
            return None
        except PermissionError:
            self.show_message(f"Error: Permission denied for '{str(cmd)}'. Try running as administrator.")
            logging.error(f"Permission denied for: {cmd}", exc_info=True)
            return None
        except Exception as e:
            self.show_message(f"Error running process '{str(cmd)}': {e}")
            logging.error(f"Failed to run process '{cmd}': {e}", exc_info=True)
            return None
    
    def _on_terminate(self, proc):
        """Callback for psutil.wait_procs to log terminated processes."""
        if PSUTIL_AVAILABLE:
            self.show_message(f"  - Process {proc.name()} (PID: {proc.pid}) terminated.")
            logging.info(f"Process {proc.name()} (PID: {proc.pid}) terminated.")

    def terminate_process_tree(self, proc, timeout: int = 3):
        """
        Gracefully terminates a process and its entire process tree.
        Tries to terminate, waits for a timeout, then forcefully kills if necessary.
        """
        if not PSUTIL_AVAILABLE:
            logging.warning("Cannot terminate process tree (psutil not available)")
            return
            
        if not proc or not psutil.pid_exists(proc.pid):
            return

        try:
            proc_name = proc.name()
            self.show_message(f"Terminating process tree for {proc_name} (PID: {proc.pid})...")

            # Get all children of the process before terminating the parent
            children = proc.children(recursive=True)
            all_procs_to_terminate = [proc] + children

            for p in all_procs_to_terminate:
                try:
                    p.terminate()
                except psutil.NoSuchProcess:
                    continue # Process already ended

            # Wait for all processes to terminate
            gone, alive = psutil.wait_procs(all_procs_to_terminate, timeout=timeout, callback=self._on_terminate)

            # If any are still alive, kill them forcefully
            for p in alive:
                try:
                    self.show_message(f"  - Process {p.name()} (PID: {p.pid}) did not exit gracefully. Killing.")
                    p.kill()
                except psutil.NoSuchProcess:
                    continue

        except psutil.NoSuchProcess:
            # This can happen if the process terminates between the pid_exists check and the name() call
            self.show_message(f"Process with PID {proc.pid} no longer exists.")
        except psutil.AccessDenied as e:
            self.show_message(f"Access denied terminating process {proc.pid}: {e}")
            logging.warning(f"Access denied terminating process {proc.pid}: {e}", exc_info=True)
        except Exception as e:
            self.show_message(f"Error terminating process {proc.pid}: {e}")
            logging.error(f"Error terminating process {proc.pid}: {e}", exc_info=True)

    def kill_process_by_name(self, process_name: str, timeout: int = 3):
        """Finds and kills processes by exact name match."""
        if not PSUTIL_AVAILABLE:
            # Fallback to taskkill on Windows
            if platform.system() == 'Windows':
                try:
                    subprocess.run(['taskkill', '/F', '/IM', process_name], 
                                 capture_output=True, timeout=5)
                    logging.info(f"Killed process {process_name} using taskkill")
                except Exception as e:
                    logging.error(f"Failed to kill {process_name}: {e}")
            return
            
        if platform.system() != 'Windows':
            return
        for proc in psutil.process_iter(['pid', 'name']):
            if proc.info['name'].lower() == process_name.lower():
                self.terminate_process_tree(proc, timeout=timeout)
    
    def kill_processes_in_list(self):
        """Kill processes in the kill list"""
        if not self.use_kill_list or not hasattr(self, 'kill_list'):
            return
        
        for proc_name in self.kill_list:
            self.show_message(f"Killing process from list: {proc_name}")
            self.kill_process_by_name(proc_name)
    
    def write_pid_file(self):
        """Write the current PID to the PID file"""
        config = configparser.ConfigParser()
        
        # Read existing file if it exists
        if os.path.exists(self.curpidf):
            config.read(self.curpidf)
        
        # Ensure sections exist
        if 'Instance' not in config:
            config['Instance'] = {}
        
        # Update PID
        config['Instance']['pid'] = str(self.current_pid)
        config['Instance']['multi_instance'] = str(self.multi_instance)
        
        # Write to file
        with open(self.curpidf, 'w') as f:
            config.write(f)

    def close_splash(self):
        """Close the PyInstaller splash screen if it exists"""
        try:
            import pyi_splash
            if pyi_splash.is_alive():
                pyi_splash.close()
        except ImportError:
            pass

# Entry point
if __name__ == "__main__":
    launcher = GameLauncher()
    launcher.run()
