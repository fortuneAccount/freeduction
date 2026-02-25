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
from pathlib import Path
from typing import Optional, Callable

try:
    from PIL import Image
    import pystray
    from pystray import MenuItem as item
    TRAY_AVAILABLE = True
except ImportError:
    TRAY_AVAILABLE = False
    logging.warning("pystray not available - tray menu disabled")

try:
    from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                                  QLineEdit, QPushButton, QTextEdit, QFileDialog,
                                  QFormLayout, QGroupBox, QScrollArea, QWidget)
    from PyQt6.QtCore import Qt
    QT_AVAILABLE = True
    
    # Import advanced config editor
    try:
        from Python.config_editor_dialog import AdvancedConfigEditor
        ADVANCED_EDITOR_AVAILABLE = True
    except ImportError:
        try:
            from config_editor_dialog import AdvancedConfigEditor
            ADVANCED_EDITOR_AVAILABLE = True
        except ImportError:
            ADVANCED_EDITOR_AVAILABLE = False
            logging.warning("Advanced config editor not available")
except ImportError:
    QT_AVAILABLE = False
    ADVANCED_EDITOR_AVAILABLE = False
    logging.warning("PyQt6 not available - GUI dialogs disabled")


class ConfigEditorDialog(QDialog):
    """Modal dialog for editing Game.ini configuration"""
    
    def __init__(self, ini_path: str, on_reload: Callable):
        super().__init__()
        self.ini_path = ini_path
        self.on_reload = on_reload
        self.config = configparser.ConfigParser()
        self.config.optionxform = str  # Preserve case
        self.config.read(ini_path)
        
        self.setWindowTitle(f"Edit Configuration - {Path(ini_path).name}")
        self.setMinimumSize(800, 600)
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Scroll area for config sections
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        self.field_widgets = {}
        
        # Create sections
        for section in self.config.sections():
            group = QGroupBox(section)
            form = QFormLayout()
            
            for key in self.config.options(section):
                value = self.config.get(section, key)
                
                # Create appropriate widget based on key name
                if 'path' in key.lower() or 'app' in key.lower() or 'profile' in key.lower():
                    # File/folder picker
                    h_layout = QHBoxLayout()
                    line_edit = QLineEdit(value)
                    browse_btn = QPushButton("Browse...")
                    browse_btn.clicked.connect(
                        lambda checked, le=line_edit, k=key: self.browse_file(le, k)
                    )
                    h_layout.addWidget(line_edit)
                    h_layout.addWidget(browse_btn)
                    form.addRow(key, h_layout)
                    self.field_widgets[f"{section}.{key}"] = line_edit
                else:
                    # Regular text field
                    line_edit = QLineEdit(value)
                    form.addRow(key, line_edit)
                    self.field_widgets[f"{section}.{key}"] = line_edit
            
            group.setLayout(form)
            scroll_layout.addWidget(group)
        
        scroll.setWidget(scroll_widget)
        layout.addWidget(scroll)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_config)
        reload_btn = QPushButton("Reload")
        reload_btn.clicked.connect(self.reload_config)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addWidget(reload_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        self.setLayout(layout)
    
    def browse_file(self, line_edit: QLineEdit, key: str):
        """Open file browser"""
        current = line_edit.text()
        if 'directory' in key.lower() or 'folder' in key.lower():
            path = QFileDialog.getExistingDirectory(self, f"Select {key}", current)
        else:
            path, _ = QFileDialog.getOpenFileName(self, f"Select {key}", current)
        
        if path:
            # Normalize path to use forward slashes
            path = path.replace('\\', '/')
            line_edit.setText(path)
    
    def save_config(self):
        """Save configuration to file"""
        for full_key, widget in self.field_widgets.items():
            section, key = full_key.split('.', 1)
            value = widget.text()
            self.config.set(section, key, value)
        
        with open(self.ini_path, 'w') as f:
            self.config.write(f)
        
        logging.info(f"Configuration saved to {self.ini_path}")
        self.accept()
    
    def reload_config(self):
        """Reload configuration and notify launcher"""
        self.save_config()
        if self.on_reload:
            self.on_reload()


class DisplayConfigDialog(QDialog):
    """Modal dialog for displaying current configuration"""
    
    def __init__(self, ini_path: str):
        super().__init__()
        self.ini_path = ini_path
        
        self.setWindowTitle(f"Current Configuration - {Path(ini_path).name}")
        self.setMinimumSize(700, 500)
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Read and display config
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setFontFamily("Courier New")
        
        try:
            with open(self.ini_path, 'r') as f:
                text_edit.setPlainText(f.read())
        except Exception as e:
            text_edit.setPlainText(f"Error reading config: {e}")
        
        layout.addWidget(text_edit)
        
        # Close button
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)
        
        self.setLayout(layout)


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
        """Display current configuration in a modal window"""
        logging.info("Display config requested from tray menu")
        
        if not QT_AVAILABLE:
            logging.warning("Qt not available - cannot display config dialog")
            return
        
        ini_path = getattr(self.launcher, 'ini_path', None)
        if not ini_path or not os.path.exists(ini_path):
            logging.warning("No config file found")
            return
        
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication(sys.argv)
            dialog = DisplayConfigDialog(ini_path)
            dialog.exec()
        except Exception as e:
            logging.error(f"Failed to display config: {e}")
    
    def change_config(self, icon=None, item=None):
        """Open configuration editor"""
        logging.info("Change config requested from tray menu")
        
        if not QT_AVAILABLE:
            logging.warning("Qt not available - cannot open config editor")
            return
        
        ini_path = getattr(self.launcher, 'ini_path', None)
        if not ini_path or not os.path.exists(ini_path):
            logging.warning("No config file found")
            return
        
        try:
            from PyQt6.QtWidgets import QApplication
            app = QApplication.instance() or QApplication(sys.argv)
            
            # Use advanced editor if available, otherwise fall back to basic
            if ADVANCED_EDITOR_AVAILABLE:
                dialog = AdvancedConfigEditor(ini_path, self.reload_config)
            else:
                dialog = ConfigEditorDialog(ini_path, self.reload_config)
            
            if dialog.exec():
                logging.info("Configuration updated")
        except Exception as e:
            logging.error(f"Failed to open config editor: {e}")
    
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
