"""Plugin Manager Dialog - UI for managing plugins"""

import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QWidget,
    QTableWidget, QTableWidgetItem, QPushButton, QLabel,
    QHeaderView, QMessageBox, QCheckBox, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal

from Python.managers.plugin_manager import PluginManager
from Python.managers.plugin_loader import PluginLoader
from Python.marketplace import PluginMarketplace
from Python import constants


ALL_TOOL_KEYS = [
    ('monitor', 'Monitor Config'),
    ('controller_mapper', 'Controller Mapper'),
    ('borderless_window', 'Borderless Windowing'),
    ('disc_mount', 'Disc Mounting'),
    ('audio', 'Audio'),
    ('local_backup', 'Local Backup'),
    ('cloud_sync', 'Cloud Sync'),
]


class PluginManagerDialog(QDialog):
    """Modal dialog for managing plugins and loading/unloading built-in tools"""

    plugin_changed = pyqtSignal()

    def __init__(self, parent=None, enabled_tools=None):
        super().__init__(parent)
        self.setWindowTitle("Plugin Manager")
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.resize(800, 600)

        self._enabled_tools = set(enabled_tools) if enabled_tools else set()
        self._tool_checkboxes = {}

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

        info_label = QLabel("Manage installed plugins and load/unload built-in tools.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        self._create_tools_section(layout)

        self.manager_widget = self._create_manager_tab()
        layout.addWidget(self.manager_widget)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        layout.addWidget(close_btn)

    def _create_tools_section(self, parent_layout):
        """Create the tool enable/disable checkboxes"""
        group = QGroupBox("Built-in Tools")
        layout = QVBoxLayout(group)

        for key, label in ALL_TOOL_KEYS:
            cb = QCheckBox(label)
            cb.setChecked(key in self._enabled_tools)
            cb.toggled.connect(lambda checked, k=key: self._on_tool_toggle(k, checked))
            self._tool_checkboxes[key] = cb
            layout.addWidget(cb)

        parent_layout.addWidget(group)

    def _on_tool_toggle(self, key, checked):
        if checked:
            self._enabled_tools.add(key)
        else:
            self._enabled_tools.discard(key)

    def get_enabled_tools(self):
        return set(self._enabled_tools)

    def _create_manager_tab(self):
        """Create the manager widget"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        self.plugin_table = QTableWidget()
        self.plugin_table.setColumnCount(4)
        self.plugin_table.setHorizontalHeaderLabels(["Name", "Category", "Description", "Actions"])
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

    def _load_plugins(self):
        """Load and display plugins in the table"""
        self.plugin_table.setRowCount(0)

        if not self.plugin_manager:
            return

        plugins = self.plugin_manager.registry.get_all_plugins()
        self.plugin_table.setRowCount(len(plugins))

        for row, plugin in enumerate(plugins):
            # Name
            self.plugin_table.setItem(row, 0, QTableWidgetItem(plugin.display_name))

            # Category
            self.plugin_table.setItem(row, 1, QTableWidgetItem(plugin.category))

            # Description
            self.plugin_table.setItem(row, 2, QTableWidgetItem(plugin.description))

            # Actions
            actions_widget = QWidget()
            actions_layout = QHBoxLayout(actions_widget)
            actions_layout.setContentsMargins(2, 2, 2, 2)

            reload_btn = QPushButton("Reload")
            reload_btn.clicked.connect(lambda checked, p=plugin: self._reload_plugin(p))
            actions_layout.addWidget(reload_btn)

            self.plugin_table.setCellWidget(row, 3, actions_widget)

    def _reload_selected_plugin(self):
        """Reload the currently selected plugin"""
        current_row = self.plugin_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "No Selection", "Please select a plugin to reload.")
            return

        plugin_name_item = self.plugin_table.item(current_row, 0)
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
