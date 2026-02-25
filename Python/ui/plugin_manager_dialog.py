"""Plugin Manager Dialog - UI for managing plugins"""

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QHeaderView, QMessageBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from Python.managers.plugin_manager import PluginManager
from Python.managers.plugin_loader import PluginLoader
from Python.marketplace import PluginMarketplace
from Python import constants


class PluginManagerDialog(QDialog):
    """Modal dialog for managing plugins"""
    
    plugin_changed = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Manager")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(800, 600)
        
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
        layout.addWidget(self.tabs)
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

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
        btn_layout.addWidget(self.reload_btn)
        btn_layout.addWidget(self.refresh_btn)
        btn_layout.addStretch()
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
