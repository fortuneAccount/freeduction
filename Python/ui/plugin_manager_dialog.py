"""Plugin Manager Dialog - UI for managing plugins and built-in tools"""

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QHeaderView, QMessageBox, QCheckBox, QLineEdit, QGroupBox,
    QFormLayout, QScrollArea
)
from PyQt6.QtCore import Qt, pyqtSignal

from Python.managers.plugin_manager import PluginManager
from Python.managers.plugin_loader import PluginLoader
from Python.marketplace import PluginMarketplace
from Python import constants


class PluginManagerDialog(QDialog):
    """Modal dialog for managing plugins and built-in tools"""
    
    plugin_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Manager")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(900, 650)
        
        self.logger = logging.getLogger(__name__)
        self._init_plugin_infrastructure()
        self._init_ui()
        self._load_plugins()
    
    def _init_plugin_infrastructure(self):
        """Initialize plugin manager, loader, and marketplace"""
        try:
            bin_dir = os.path.join(constants.APP_ROOT_DIR, "bin")
            self.plugin_manager = PluginManager(bin_directory=bin_dir)
            self.plugin_manager.load_builtin_plugins()
            
            self.plugin_loader = PluginLoader(self.plugin_manager.registry)
            
            cache_dir = os.path.join(constants.APP_ROOT_DIR, "cache", "marketplace")
            plugins_dir = os.path.join(constants.APP_ROOT_DIR, "plugins", "community")
            self.marketplace = PluginMarketplace(cache_dir, plugins_dir)
            
        except Exception as e:
            self.logger.error(f"Failed to initialize plugin infrastructure: {e}", exc_info=True)
    
    def _init_ui(self):
        """Initialize the user interface"""
        layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_manager_tab(), "Manager")
        self.tabs.addTab(self._create_market_tab(), "Market")
        self.tabs.addTab(self._create_tools_tab(), "Tools")
        layout.addWidget(self.tabs)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _make_form_row(self, label, widget):
        """Helper to create a labeled form row with consistent layout."""
        row = QHBoxLayout()
        lbl = QLabel(label)
        lbl.setFixedWidth(140)
        row.addWidget(lbl)
        row.addWidget(widget, 1)
        return row

    def _create_tools_tab(self):
        """Create the Tools tab with sub-tabs for each built-in tool."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info = QLabel("Configure built-in tools. These settings are managed here instead of the Editor grid.")
        info.setWordWrap(True)
        layout.addWidget(info)
        
        tool_tabs = QTabWidget()
        
        # --- Borderless Windowing ---
        bw_tab = QWidget()
        bw_layout = QVBoxLayout(bw_tab)
        bw_scroll = QScrollArea()
        bw_scroll.setWidgetResizable(True)
        bw_content = QWidget()
        bw_form = QFormLayout(bw_content)
        self.bw_path = QLineEdit(); bw_form.addRow("Application Path:", self.bw_path)
        self.bw_opts = QLineEdit(); bw_form.addRow("Options:", self.bw_opts)
        self.bw_args = QLineEdit(); bw_form.addRow("Arguments:", self.bw_args)
        self.bw_unborder = QLineEdit(); bw_form.addRow("UnBorder Config:", self.bw_unborder)
        self.bw_reborder = QLineEdit(); bw_form.addRow("ReBorder Config:", self.bw_reborder)
        bw_scroll.setWidget(bw_content)
        bw_layout.addWidget(bw_scroll)
        tool_tabs.addTab(bw_tab, "Borderless Windowing")
        
        # --- Disc Mounting ---
        dm_tab = QWidget()
        dm_layout = QVBoxLayout(dm_tab)
        dm_scroll = QScrollArea()
        dm_scroll.setWidgetResizable(True)
        dm_content = QWidget()
        dm_form = QFormLayout(dm_content)
        self.dm_iso = QLineEdit(); dm_form.addRow("ISO Path:", self.dm_iso)
        self.dm_path = QLineEdit(); dm_form.addRow("Mount App Path:", self.dm_path)
        self.dm_opts = QLineEdit(); dm_form.addRow("Options:", self.dm_opts)
        self.dm_args = QLineEdit(); dm_form.addRow("Arguments:", self.dm_args)
        self.dm_mount_cfg = QLineEdit(); dm_form.addRow("Mount Config:", self.dm_mount_cfg)
        self.dm_unmount_cfg = QLineEdit(); dm_form.addRow("Unmount Config:", self.dm_unmount_cfg)
        dm_scroll.setWidget(dm_content)
        dm_layout.addWidget(dm_scroll)
        tool_tabs.addTab(dm_tab, "Disc Mounting")
        
        # --- Local Backup ---
        lb_tab = QWidget()
        lb_layout = QVBoxLayout(lb_tab)
        lb_scroll = QScrollArea()
        lb_scroll.setWidgetResizable(True)
        lb_content = QWidget()
        lb_form = QFormLayout(lb_content)
        self.lb_path = QLineEdit(); lb_form.addRow("Backup App Path:", self.lb_path)
        self.lb_opts = QLineEdit(); lb_form.addRow("Options:", self.lb_opts)
        self.lb_args = QLineEdit(); lb_form.addRow("Arguments:", self.lb_args)
        lb_scroll.setWidget(lb_content)
        lb_layout.addWidget(lb_scroll)
        tool_tabs.addTab(lb_tab, "Local Backup")
        
        # --- Cloud-Sync ---
        cs_tab = QWidget()
        cs_layout = QVBoxLayout(cs_tab)
        cs_scroll = QScrollArea()
        cs_scroll.setWidgetResizable(True)
        cs_content = QWidget()
        cs_form = QFormLayout(cs_content)
        self.cs_path = QLineEdit(); cs_form.addRow("Sync App Path:", self.cs_path)
        self.cs_opts = QLineEdit(); cs_form.addRow("Options:", self.cs_opts)
        self.cs_args = QLineEdit(); cs_form.addRow("Arguments:", self.cs_args)
        cs_scroll.setWidget(cs_content)
        cs_layout.addWidget(cs_scroll)
        tool_tabs.addTab(cs_tab, "Cloud-Sync")
        
        # --- Audio ---
        au_tab = QWidget()
        au_layout = QVBoxLayout(au_tab)
        au_scroll = QScrollArea()
        au_scroll.setWidgetResizable(True)
        au_content = QWidget()
        au_form = QFormLayout(au_content)
        self.au_path = QLineEdit(); au_form.addRow("Audio App Path:", self.au_path)
        self.au_opts = QLineEdit(); au_form.addRow("Options:", self.au_opts)
        self.au_args = QLineEdit(); au_form.addRow("Arguments:", self.au_args)
        self.au_game_cfg = QLineEdit(); au_form.addRow("Game Config:", self.au_game_cfg)
        self.au_mc_cfg = QLineEdit(); au_form.addRow("MediaCenter Config:", self.au_mc_cfg)
        au_scroll.setWidget(au_content)
        au_layout.addWidget(au_scroll)
        tool_tabs.addTab(au_tab, "Audio")
        
        layout.addWidget(tool_tabs)
        return widget
    
    def _create_manager_tab(self):
        """Create the Manager tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info_label = QLabel("Manage installed plugins. Enable/disable or reload plugins without restarting.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.plugin_table = QTableWidget()
        self.plugin_table.setColumnCount(5)
        self.plugin_table.setHorizontalHeaderLabels(["Enabled", "Name", "Category", "Description", "Actions"])
        self.plugin_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.plugin_table)
        
        btn_layout = QHBoxLayout()
        self.reload_btn = QPushButton("Reload Selected")
        self.reload_btn.clicked.connect(self._reload_selected_plugin)
        self.refresh_btn = QPushButton("Refresh List")
        self.refresh_btn.clicked.connect(self._load_plugins)
        
        self.plugin_mode_btn = QPushButton("Plugin Creation Mode")
        self.plugin_mode_btn.setStyleSheet("background-color: #8B0000; color: white;")
        self.plugin_mode_btn.setToolTip("Restart in Plugin Creation Mode to design plugin UI")
        self.plugin_mode_btn.clicked.connect(self._enter_plugin_mode)
        
        btn_layout.addWidget(self.reload_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.plugin_mode_btn)
        layout.addLayout(btn_layout)
        
        return widget
    
    def _create_market_tab(self):
        """Create the Market tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        info_label = QLabel("Browse and install community plugins. (Marketplace coming soon)")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        self.market_table = QTableWidget()
        self.market_table.setColumnCount(4)
        self.market_table.setHorizontalHeaderLabels(["Name", "Category", "Description", "Actions"])
        self.market_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.market_table)
        
        return widget

    def _load_plugins(self):
        """Load and display plugins in the table"""
        self.plugin_table.setRowCount(0)
        
        if not self.plugin_manager:
            return
        
        plugins = self.plugin_manager.registry.get_all_plugins()
        self.plugin_table.setRowCount(len(plugins))
        
        for row, plugin in enumerate(plugins):
            # Enabled checkbox
            enabled_cb = QCheckBox()
            enabled_cb.setChecked(True)
            self.plugin_table.setCellWidget(row, 0, enabled_cb)
            
            # Name
            self.plugin_table.setItem(row, 1, QTableWidgetItem(plugin.display_name))
            
            # Category
            self.plugin_table.setItem(row, 2, QTableWidgetItem(plugin.category))
            
            # Description
            self.plugin_table.setItem(row, 3, QTableWidgetItem(plugin.description))
            
            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)
            
            reload_btn = QPushButton("Reload")
            reload_btn.clicked.connect(lambda checked, p=plugin: self._reload_plugin(p))
            actions_layout.addWidget(reload_btn)
            
            self.plugin_table.setCellWidget(row, 4, actions_widget)
    
    def _reload_selected_plugin(self):
        """Reload the currently selected plugin"""
        current_row = self.plugin_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a plugin to reload.")
            return
        
        plugin_name_item = self.plugin_table.item(current_row, 1)
        if not plugin_name_item:
            return
        
        plugin_name = plugin_name_item.text()
        plugins = [p for p in self.plugin_manager.registry.get_all_plugins() if p.display_name == plugin_name]
        
        if plugins:
            self._reload_plugin(plugins[0])
    
    def _reload_plugin(self, plugin):
        """Reload a specific plugin"""
        try:
            if self.plugin_loader:
                reloaded = self.plugin_loader.reload_plugin(plugin.name)
                if reloaded:
                    QMessageBox.information(self, "Success", f"Plugin '{plugin.display_name}' reloaded successfully!")
                    self._load_plugins()
                    self.plugin_changed.emit()
                else:
                    QMessageBox.warning(self, "Failed", f"Failed to reload plugin '{plugin.display_name}'.")
            else:
                QMessageBox.warning(self, "Not Available", "Plugin hot-reloading is not available.")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error reloading plugin: {e}")
            self.logger.error(f"Error reloading plugin {plugin.name}: {e}", exc_info=True)

    def _enter_plugin_mode(self):
        """Restart the application in Plugin Creation Mode."""
        import subprocess
        import sys
        
        reply = QMessageBox.question(
            self, "Enter Plugin Mode",
            "This will restart the application in Plugin Creation Mode.\n\nThe window frame will turn red to indicate you are in development mode.\n\nContinue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            app_path = sys.executable
            script_path = os.path.join(constants.APP_ROOT_DIR, "Python", "main.py")
            
            try:
                subprocess.Popen([app_path, script_path, "--plugin-mode"])
                self.accept()
                from PyQt6.QtWidgets import QApplication
                QApplication.quit()
            except Exception as e:
                QMessageBox.critical(self, "Restart Failed", f"Could not restart in Plugin Mode: {str(e)}")
