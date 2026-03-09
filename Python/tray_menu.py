#!/usr/bin/env python3
"""
tray_menu.py - System Tray Menu for Game Launcher

Provides a system tray icon with context menu for controlling the launcher.
"""

import os
import sys
import threading
import logging
import configparser
import subprocess
import platform
from pathlib import Path
from typing import Optional, Callable

try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    pass

try:
    from PIL import Image
    import pystray
    from pystray import MenuItem as item
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    logging.warning("pystray not available - tray menu disabled")

class ConfigEditor:
    """Tkinter-based configuration editor for Game.ini"""
    
    def __init__(self, ini_path, on_save_callback=None):
        self.ini_path = ini_path
        self.on_save_callback = on_save_callback
        self.config = configparser.ConfigParser()
        self.config.optionxform = str  # Preserve case
        self.root = None
        self.entries = {}
        
    def show(self):
        if not os.path.exists(self.ini_path):
            logging.error(f"Config file not found: {self.ini_path}")
            return
            
        try:
            self.config.read(self.ini_path)
        except Exception as e:
            logging.error(f"Failed to read config: {e}")
            return

        # Create main window
        self.root = tk.Tk()
        self.root.title("Configuration Editor")
        self.root.geometry("700x600")
        
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Scrollable area
        canvas = tk.Canvas(main_frame)
        scrollbar = ttk.Scrollbar(main_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        # Populate fields
        row = 0
        for section in self.config.sections():
            # Section Header
            ttk.Label(scrollable_frame, text=f"[{section}]", font=("Segoe UI", 10, "bold")).grid(
                row=row, column=0, columnspan=3, sticky="w", pady=(10, 5))
            row += 1
            
            for key, value in self.config.items(section):
                # Label
                ttk.Label(scrollable_frame, text=key).grid(row=row, column=0, sticky="w", padx=5, pady=2)
                
                # Entry
                var = tk.StringVar(value=value)
                entry = ttk.Entry(scrollable_frame, textvariable=var, width=50)
                entry.grid(row=row, column=1, sticky="ew", padx=5, pady=2)
                
                self.entries[(section, key)] = var
                
                # Browse button for paths
                if "path" in key.lower() or "executable" in key.lower() or "directory" in key.lower() or "profile" in key.lower():
                    btn = ttk.Button(scrollable_frame, text="...", width=3, 
                                   command=lambda v=var, k=key: self._browse(v, k))
                    btn.grid(row=row, column=2, padx=2)
                
                row += 1
        
        # Button Bar
        btn_frame = ttk.Frame(self.root, padding="10")
        btn_frame.pack(fill=tk.X)
        
        ttk.Button(btn_frame, text="Import", command=self._import_config).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Export", command=self._export_config).pack(side="left", padx=5)
        ttk.Button(btn_frame, text="Save", command=self._save).pack(side="right", padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.root.destroy).pack(side="right", padx=5)
        
        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'{width}x{height}+{x}+{y}')
        
        self.root.mainloop()
        
    def _browse(self, var, key):
        val = var.get()
        if "directory" in key.lower() or "folder" in key.lower():
            path = filedialog.askdirectory(initialdir=val)
        else:
            path = filedialog.askopenfilename(initialdir=os.path.dirname(val) if val else ".")
            
        if path:
            var.set(path)
            
    def _import_config(self):
        path = filedialog.askopenfilename(filetypes=[("INI Files", "*.ini"), ("All Files", "*.*")])
        if not path:
            return
            
        try:
            import_config = configparser.ConfigParser()
            import_config.optionxform = str
            import_config.read(path)
            
            for (section, key), var in self.entries.items():
                if import_config.has_section(section) and import_config.has_option(section, key):
                    var.set(import_config.get(section, key))
            
            messagebox.showinfo("Import", "Configuration imported successfully.")
        except Exception as e:
            messagebox.showerror("Import Error", f"Failed to import config: {e}")

    def _export_config(self):
        path = filedialog.asksaveasfilename(defaultextension=".ini", filetypes=[("INI Files", "*.ini"), ("All Files", "*.*")])
        if not path:
            return
            
        # Update config object with current UI values
        for (section, key), var in self.entries.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            self.config.set(section, key, var.get())
            
        try:
            with open(path, 'w') as f:
                self.config.write(f)
            messagebox.showinfo("Export", "Configuration exported successfully.")
        except Exception as e:
            messagebox.showerror("Export Error", f"Failed to export config: {e}")

    def _save(self):
        for (section, key), var in self.entries.items():
            self.config.set(section, key, var.get())
            
        try:
            with open(self.ini_path, 'w') as f:
                self.config.write(f)
            messagebox.showinfo("Success", "Configuration saved successfully.")
            if self.on_save_callback:
                self.on_save_callback()
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save config: {e}")

class LauncherTrayMenu:
    """System tray menu for the game launcher"""
    
    def __init__(self, launcher_instance):
        self.launcher = launcher_instance
        self.icon = None
        self.running = False
        
        if not TRAY_AVAILABLE:
            logging.warning("Tray menu not available - pystray not installed")
            return
        
        # Create icon
        self.create_icon()
        
    def create_icon(self):
        """Create the tray icon"""
        # Try to load icon from assets
        # When frozen by PyInstaller, assets are in sys._MEIPASS
        if getattr(sys, 'frozen', False):
            # Running as compiled executable
            base_path = getattr(sys, '_MEIPASS', os.path.dirname(sys.executable))
            icon_path = os.path.join(base_path, "assets", "Joystick.ico")
        else:
            # Running from source
            icon_path = os.path.join(self.launcher.home, "assets", "Joystick.ico")
        
        if os.path.exists(icon_path):
            try:
                image = Image.open(icon_path)
            except Exception as e:
                logging.warning(f"Failed to load icon from {icon_path}: {e}")
                image = self.create_default_icon()
        else:
            logging.warning(f"Icon not found at {icon_path}, using default")
            image = self.create_default_icon()
        
        # Create menu
        menu = pystray.Menu(
            item('Restart', self.restart_launcher),
            item('Stop', self.stop_game),
            item('Kill', self.kill_all),
            pystray.Menu.SEPARATOR,
            item('Display Config', self.display_config),
            item('Change Config', self.change_config),
            pystray.Menu.SEPARATOR,
            item('Exit Launcher', self.exit_launcher)
        )
        
        game_name = getattr(self.launcher, 'game_name', 'Game Launcher')
        self.icon = pystray.Icon(
            "launcher",
            image,
            f"{game_name} - Launcher",
            menu
        )
    
    def create_default_icon(self):
        """Create a default icon if no icon file is found"""
        # Create a simple 64x64 icon
        from PIL import Image, ImageDraw
        
        image = Image.new('RGB', (64, 64), color='#2196F3')
        draw = ImageDraw.Draw(image)
        
        # Draw a simple gamepad shape
        draw.ellipse([10, 20, 30, 40], fill='white')  # Left button
        draw.ellipse([34, 20, 54, 40], fill='white')  # Right button
        draw.rectangle([20, 35, 44, 50], fill='white')  # Center
        
        return image
    
    def start(self):
        """Start the tray icon in a separate thread"""
        if not TRAY_AVAILABLE or not self.icon:
            return
        
        self.running = True
        self.tray_thread = threading.Thread(target=self._run_icon, daemon=True)
        self.tray_thread.start()
        logging.info("Tray menu started")
    
    def _run_icon(self):
        """Run the tray icon (blocking)"""
        try:
            self.icon.run()
        except Exception as e:
            logging.error(f"Tray icon error: {e}")
    
    def stop(self):
        """Stop the tray icon"""
        if self.icon and self.running:
            self.icon.stop()
            self.running = False
            logging.info("Tray menu stopped")
    
    def restart_launcher(self, icon=None, item=None):
        """Restart the current launcher"""
        logging.info("Restart requested from tray menu")
        
        # Get the launcher link file
        lnk_file = getattr(self.launcher, 'plink', None)
        
        if lnk_file and os.path.exists(lnk_file):
            # Stop current game
            self.stop_game()
            
            # Restart launcher
            try:
                if sys.platform == 'win32':
                    os.startfile(lnk_file)
                else:
                    subprocess.Popen([lnk_file])
                
                logging.info(f"Restarted launcher: {lnk_file}")
            except Exception as e:
                logging.error(f"Failed to restart launcher: {e}")
        else:
            logging.warning("No launcher link file found for restart")
    
    def stop_game(self, icon=None, item=None):
        """Stop the game using exit sequences"""
        logging.info("Stop requested from tray menu")
        
        try:
            # Execute exit sequence
            if hasattr(self.launcher, 'executor'):
                self.launcher.executor.execute('exit_sequence')
            
            # Terminate game process
            if hasattr(self.launcher, 'game_process') and self.launcher.game_process:
                self.launcher.terminate_process_tree(self.launcher.game_process)
                logging.info("Game process terminated")
        except Exception as e:
            logging.error(f"Failed to stop game: {e}")
    
    def kill_all(self, icon=None, item=None):
        """Force quit game and all tracked processes"""
        logging.info("Kill all requested from tray menu")
        
        try:
            # Kill game process
            if hasattr(self.launcher, 'game_process') and self.launcher.game_process:
                self.launcher.game_process.kill()
                logging.info("Game process killed")
            
            # Kill processes in kill list
            if hasattr(self.launcher, 'kill_processes_in_list'):
                self.launcher.kill_processes_in_list()
            
            # Cleanup and exit
            if hasattr(self.launcher, 'executor'):
                self.launcher.executor.ensure_cleanup()
            
            # Exit launcher
            sys.exit(0)
        except Exception as e:
            logging.error(f"Failed to kill processes: {e}")
    
    def display_config(self, icon=None, item=None):
        """Display current configuration (opens file)"""
        logging.info("Display config requested from tray menu")
        self._open_config_file()
    
    def change_config(self, icon=None, item=None):
        """Open configuration editor (opens file)"""
        logging.info("Change config requested from tray menu (GUI)")
        ini_path = getattr(self.launcher, 'ini_path', None)
        if ini_path:
            editor = ConfigEditor(ini_path, on_save_callback=self.reload_config)
            editor.show()
        else:
            self._open_config_file()
        
    def _open_config_file(self):
        """Open the config file in the default editor"""
        
        ini_path = getattr(self.launcher, 'ini_path', None)
        if not ini_path or not os.path.exists(ini_path):
            logging.warning("No config file found")
            return
        
        try:
            if sys.platform == 'win32':
                os.startfile(ini_path)
            elif sys.platform == 'darwin':
                subprocess.Popen(['open', ini_path])
            else:
                subprocess.Popen(['xdg-open', ini_path])
            logging.info(f"Opened config file: {ini_path}")
        except Exception as e:
            logging.error(f"Failed to open config file: {e}")
    
    def reload_config(self):
        """Reload configuration in the launcher"""
        logging.info("Reloading configuration...")
        
        try:
            if hasattr(self.launcher, 'load_config'):
                self.launcher.load_config()
                logging.info("Configuration reloaded successfully")
        except Exception as e:
            logging.error(f"Failed to reload config: {e}")
    
    def exit_launcher(self, icon=None, item=None):
        """Exit the launcher gracefully"""
        logging.info("Exit requested from tray menu")
        
        # Stop game first
        self.stop_game()
        
        # Stop tray icon
        self.stop()
        
        # Exit
        sys.exit(0)
