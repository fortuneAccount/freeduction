#!/usr/bin/env python3
"""
config_editor_dialog.py - Advanced Configuration Editor for Game.ini

Provides a sophisticated GUI for editing Game.ini with appropriate widgets
for different value types (paths, booleans, lists, etc.)
"""

import os
import configparser
from pathlib import Path
from typing import Dict, List, Tuple, Optional

try:
    from PyQt6.QtWidgets import (
        QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
        QCheckBox, QComboBox, QScrollArea, QWidget, QGroupBox, QFormLayout,
        QFileDialog, QSizePolicy, QFrame
    )
    from PyQt6.QtCore import Qt, QSize
    from PyQt6.QtGui import QFont
    QT_AVAILABLE = True
except ImportError:
    QT_AVAILABLE = False


# Define all possible keys and their types
CONFIG_SCHEMA = {
    'Game': {
        'executable': 'file',
        'directory': 'folder',
        'name': 'text',
        'isopath': 'file',
        'steamid': 'text',
    },
    'Paths': {
        'controllermapperapp': 'file',
        'controllermapperoptions': 'text',
        'controllermapperarguments': 'text',
        'borderlesswindowingapp': 'file',
        'borderlesswindowingoptions': 'text',
        'borderlesswindowingarguments': 'text',
        'monitorapp': 'file',
        'monitorappoptions': 'text',
        'monitorapparguments': 'text',
        'player1profile': 'file',
        'player2profile': 'file',
        'deskprofile': 'file',
        'monitorgamingcfg': 'file',
        'monitordeskcfg': 'file',
        'cloudapp': 'file',
        'cloudappoptions': 'text',
        'cloudapparguments': 'text',
        'discmountapp': 'file',
        'discmountoptions': 'text',
        'discmountarguments': 'text',
        'discmountwait': 'bool',
        'discunmountapp': 'file',
        'discunmountoptions': 'text',
        'discunmountarguments': 'text',
        'discunmountwait': 'bool',
        'gameexecutablepath': 'file',
        'launcherexecutable': 'file',
        'launchershortcut': 'file',
        'profiledirectory': 'folder',
    },
    'Options': {
        'runasadmin': 'bool',
        'hidetaskbar': 'bool',
        'borderless': 'text',
        'usekilllist': 'bool',
        'terminateborderlessonexit': 'bool',
        'killlist': 'list',
        'backupsaves': 'bool',
        'maxbackups': 'text',
    },
    'PreLaunch': {
        'app1': 'file',
        'app1options': 'text',
        'app1arguments': 'text',
        'app1wait': 'bool',
        'app2': 'file',
        'app2options': 'text',
        'app2arguments': 'text',
        'app2wait': 'bool',
        'app3': 'file',
        'app3options': 'text',
        'app3arguments': 'text',
        'app3wait': 'bool',
    },
    'PostLaunch': {
        'app1': 'file',
        'app1options': 'text',
        'app1arguments': 'text',
        'app1wait': 'bool',
        'app2': 'file',
        'app2options': 'text',
        'app2arguments': 'text',
        'app2wait': 'bool',
        'app3': 'file',
        'app3options': 'text',
        'app3arguments': 'text',
        'app3wait': 'bool',
        'justafterlaunchapp': 'file',
        'justafterlaunchoptions': 'text',
        'justafterlauncharguments': 'text',
        'justafterlaunchwait': 'bool',
        'justbeforeexitapp': 'file',
        'justbeforeexitoptions': 'text',
        'justbeforeexitarguments': 'text',
        'justbeforeexitwait': 'bool',
    },
    'Sequences': {
        'launchsequence': 'list',
        'exitsequence': 'list',
    },
    'SourcePaths': {
        'player1profile': 'file',
        'player2profile': 'file',
    },
    'SAVE': {},  # Dynamic keys
    'CONFIG': {},  # Dynamic keys
    'SYSTEM': {},  # Dynamic keys
}

# Abbreviated key names for display
KEY_ABBREVIATIONS = {
    'controllermapperapp': 'Ctrl Mapper',
    'controllermapperoptions': 'Ctrl Opts',
    'controllermapperarguments': 'Ctrl Args',
    'borderlesswindowingapp': 'Borderless',
    'borderlesswindowingoptions': 'Border Opts',
    'borderlesswindowingarguments': 'Border Args',
    'monitorapp': 'MonApp',
    'monitorappoptions': 'MonApp Opts',
    'monitorapparguments': 'MonApp Args',
    'monitorgamingcfg': 'Mon Game Cfg',
    'monitordeskcfg': 'Mon Desk Cfg',
    'player1profile': 'P1 Profile',
    'player2profile': 'P2 Profile',
    'deskprofile': 'Desk Profile',
    'cloudapp': 'Cloud App',
    'cloudappoptions': 'Cloud Opts',
    'cloudapparguments': 'Cloud Args',
    'discmountapp': 'Mount App',
    'discmountoptions': 'Mount Opts',
    'discmountarguments': 'Mount Args',
    'discmountwait': 'Mount Wait',
    'discunmountapp': 'Unmount App',
    'discunmountoptions': 'Unmount Opts',
    'discunmountarguments': 'Unmount Args',
    'discunmountwait': 'Unmount Wait',
    'runasadmin': 'Run as Admin',
    'hidetaskbar': 'Hide Taskbar',
    'usekilllist': 'Use Kill List',
    'terminateborderlessonexit': 'Kill Borderless',
    'backupsaves': 'Backup Saves',
    'maxbackups': 'Max Backups',
    'justafterlaunchapp': 'After Launch',
    'justafterlaunchoptions': 'After Opts',
    'justafterlauncharguments': 'After Args',
    'justafterlaunchwait': 'After Wait',
    'justbeforeexitapp': 'Before Exit',
    'justbeforeexitoptions': 'Before Opts',
    'justbeforeexitarguments': 'Before Args',
    'justbeforeexitwait': 'Before Wait',
    'launchsequence': 'Launch Seq',
    'exitsequence': 'Exit Seq',
    'gameexecutablepath': 'Game Exe',
    'launcherexecutable': 'Launcher Exe',
    'launchershortcut': 'Launcher Lnk',
    'profiledirectory': 'Profile Dir',
}


class ListEditWidget(QWidget):
    """Widget for editing comma/pipe-separated lists"""
    
    def __init__(self, value: str, separator: str = ','):
        super().__init__()
        self.separator = separator
        self.setup_ui(value)
    
    def setup_ui(self, value: str):
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # ComboBox for list items
        self.combo = QComboBox()
        self.combo.setEditable(True)
        self.combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        # Populate with existing values
        if value:
            items = [item.strip() for item in value.split(self.separator)]
            self.combo.addItems(items)
        
        # Add button
        add_btn = QPushButton("+")
        add_btn.setMaximumWidth(30)
        add_btn.clicked.connect(self.add_item)
        
        # Remove button
        remove_btn = QPushButton("-")
        remove_btn.setMaximumWidth(30)
        remove_btn.clicked.connect(self.remove_item)
        
        layout.addWidget(self.combo)
        layout.addWidget(add_btn)
        layout.addWidget(remove_btn)
        
        self.setLayout(layout)
    
    def add_item(self):
        """Add a new item above the current selection"""
        current_text = self.combo.currentText().strip()
        if current_text:
            current_index = self.combo.currentIndex()
            self.combo.insertItem(current_index, "")
            self.combo.setCurrentIndex(current_index)
    
    def remove_item(self):
        """Remove the currently selected item"""
        if self.combo.count() > 0:
            self.combo.removeItem(self.combo.currentIndex())
    
    def get_value(self) -> str:
        """Get the list as a separator-delimited string"""
        items = [self.combo.itemText(i).strip() for i in range(self.combo.count())]
        items = [item for item in items if item]  # Remove empty items
        return self.separator.join(items)


class AdvancedConfigEditor(QDialog):
    """Advanced configuration editor with smart widgets"""
    
    def __init__(self, ini_path: str, on_reload=None):
        super().__init__()
        self.ini_path = ini_path
        self.on_reload = on_reload
        self.config = configparser.ConfigParser()
        self.config.optionxform = str  # Preserve case
        self.config.read(ini_path)
        
        self.field_widgets: Dict[str, QWidget] = {}
        
        self.setWindowTitle(f"Edit Configuration")
        self.setFixedSize(650, 440)
        self.setup_ui()
    
    def setup_ui(self):
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(5)
        
        # Existing keys group
        existing_group = QGroupBox("Current Settings")
        existing_layout = QFormLayout()
        existing_layout.setSpacing(3)
        existing_layout.setContentsMargins(5, 5, 5, 5)
        
        # Add existing keys
        for section in self.config.sections():
            for key in self.config.options(section):
                value = self.config.get(section, key)
                widget = self.create_widget_for_key(section, key, value)
                if widget:
                    label_text = self.get_abbreviated_label(section, key)
                    existing_layout.addRow(label_text, widget)
                    self.field_widgets[f"{section}.{key}"] = widget
        
        existing_group.setLayout(existing_layout)
        scroll_layout.addWidget(existing_group)
        
        # Available keys group (collapsed by default)
        available_group = QGroupBox("Available Settings (click to expand)")
        available_group.setCheckable(True)
        available_group.setChecked(False)
        available_layout = QFormLayout()
        available_layout.setSpacing(3)
        available_layout.setContentsMargins(5, 5, 5, 5)
        
        # Add missing keys from schema
        for section, keys in CONFIG_SCHEMA.items():
            if section not in self.config.sections():
                self.config.add_section(section)
            
            for key, key_type in keys.items():
                full_key = f"{section}.{key}"
                if full_key not in self.field_widgets:
                    widget = self.create_widget_for_key(section, key, "", key_type)
                    if widget:
                        label_text = self.get_abbreviated_label(section, key)
                        available_layout.addRow(label_text, widget)
                        self.field_widgets[full_key] = widget
        
        available_group.setLayout(available_layout)
        scroll_layout.addWidget(available_group)
        
        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll)
        
        # Buttons
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_config)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        
        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        
        main_layout.addLayout(button_layout)
        self.setLayout(main_layout)
    
    def get_abbreviated_label(self, section: str, key: str) -> str:
        """Get abbreviated label for a key"""
        key_lower = key.lower()
        if key_lower in KEY_ABBREVIATIONS:
            return KEY_ABBREVIATIONS[key_lower]
        return key[:15] + "..." if len(key) > 15 else key
    
    def create_widget_for_key(self, section: str, key: str, value: str, key_type: str = None) -> Optional[QWidget]:
        """Create appropriate widget based on key type"""
        # Determine type from schema or infer
        if key_type is None:
            key_lower = key.lower()
            if section in CONFIG_SCHEMA and key_lower in CONFIG_SCHEMA[section]:
                key_type = CONFIG_SCHEMA[section][key_lower]
            else:
                # Infer type
                if 'path' in key_lower or 'app' in key_lower or 'profile' in key_lower or 'executable' in key_lower:
                    key_type = 'file'
                elif 'directory' in key_lower or 'folder' in key_lower:
                    key_type = 'folder'
                elif value.lower() in ('true', 'false', '0', '1', 'on', 'off', 'enabled', 'disabled'):
                    key_type = 'bool'
                elif ',' in value or '|' in value:
                    key_type = 'list'
                else:
                    key_type = 'text'
        
        # Create widget based on type
        if key_type == 'bool':
            checkbox = QCheckBox()
            checkbox.setChecked(value.lower() in ('true', '1', 'on', 'enabled'))
            return checkbox
        
        elif key_type == 'list':
            separator = ',' if ',' in value else '|'
            return ListEditWidget(value, separator)
        
        elif key_type in ('file', 'folder'):
            container = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            
            line_edit = QLineEdit(value)
            line_edit.setMaximumWidth(400)
            browse_btn = QPushButton("...")
            browse_btn.setMaximumWidth(30)
            browse_btn.clicked.connect(
                lambda: self.browse_path(line_edit, key_type)
            )
            
            layout.addWidget(line_edit)
            layout.addWidget(browse_btn)
            container.setLayout(layout)
            container.line_edit = line_edit  # Store reference
            return container
        
        else:  # text
            line_edit = QLineEdit(value)
            line_edit.setMaximumWidth(450)
            return line_edit
    
    def browse_path(self, line_edit: QLineEdit, path_type: str):
        """Open file/folder browser"""
        current = line_edit.text()
        
        if path_type == 'folder':
            path = QFileDialog.getExistingDirectory(self, "Select Folder", current)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select File", current)
        
        if path:
            # Normalize to forward slashes
            path = path.replace('\\', '/')
            line_edit.setText(path)
    
    def get_widget_value(self, widget: QWidget) -> str:
        """Get value from widget"""
        if isinstance(widget, QCheckBox):
            return 'True' if widget.isChecked() else 'False'
        elif isinstance(widget, ListEditWidget):
            return widget.get_value()
        elif isinstance(widget, QLineEdit):
            return widget.text()
        elif hasattr(widget, 'line_edit'):  # Path widget container
            return widget.line_edit.text()
        return ""
    
    def save_config(self):
        """Save configuration to file"""
        for full_key, widget in self.field_widgets.items():
            section, key = full_key.split('.', 1)
            value = self.get_widget_value(widget)
            
            # Only save non-empty values
            if value or self.config.has_option(section, key):
                if not self.config.has_section(section):
                    self.config.add_section(section)
                self.config.set(section, key, value)
        
        with open(self.ini_path, 'w') as f:
            self.config.write(f)
        
        if self.on_reload:
            self.on_reload()
        
        self.accept()
