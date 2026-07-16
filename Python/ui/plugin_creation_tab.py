from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QCheckBox, QRadioButton, QButtonGroup, QGroupBox,
    QGridLayout, QSlider, QComboBox, QListWidget, QFileDialog,
    QScrollArea, QMessageBox, QApplication
)
from PyQt6.QtCore import Qt, pyqtSignal
from Python import constants
import os
import sys


class PluginCreationTab(QWidget):
    """Tab for creating plugins with UI component builders."""
    
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.plugin_components = []
        self._populate_ui()
    
    def _populate_ui(self):
        """Create and arrange all widgets for the plugin creation tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        title_label = QLabel("Plugin Creation Mode")
        title_label.setStyleSheet("font-size: 18px; font-weight: bold; color: #FF6666;")
        main_layout.addWidget(title_label)
        
        desc_label = QLabel("Create custom UI components for your plugins. Click 'Add Component' to place items on a grid.")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #AAAAAA;")
        main_layout.addWidget(desc_label)
        
        exit_mode_layout = QHBoxLayout()
        exit_mode_label = QLabel("Exit Plugin Mode:")
        exit_mode_layout.addWidget(exit_mode_label)
        
        self.exit_mode_btn = QPushButton("Return to Normal Mode")
        self.exit_mode_btn.setStyleSheet("background-color: #8B0000; color: white; padding: 8px;")
        self.exit_mode_btn.clicked.connect(self._exit_plugin_mode)
        exit_mode_layout.addWidget(self.exit_mode_btn)
        exit_mode_layout.addStretch()
        main_layout.addLayout(exit_mode_layout)
        
        main_layout.addSpacing(20)
        
        components_group = QGroupBox("UI Components")
        components_layout = QVBoxLayout(components_group)
        
        self.component_buttons = {}
        
        file_picker_btn = self._create_component_button("File Picker", "$file_")
        folder_picker_btn = self._create_component_button("Folder Picker", "$folder_")
        radio_pair_btn = self._create_component_button("Radio Button Pair", "$radio")
        checkbox_btn = self._create_component_button("Checkbox", "$checkbox")
        dropdown_btn = self._create_component_button("Dropdown List", "$dropdown")
        combo_btn = self._create_component_button("Combo Box", "$combo")
        numslider_btn = self._create_component_button("Numerical Slider", "$numslider")
        useredit_btn = self._create_component_button("User Editable Field", "$useredit")
        button_btn = self._create_component_button("Button", "#button")
        listbox_btn = self._create_component_button("Listbox", "$listbox")
        
        components_layout.addWidget(file_picker_btn)
        components_layout.addWidget(folder_picker_btn)
        components_layout.addWidget(radio_pair_btn)
        components_layout.addWidget(checkbox_btn)
        components_layout.addWidget(dropdown_btn)
        components_layout.addWidget(combo_btn)
        components_layout.addWidget(numslider_btn)
        components_layout.addWidget(useredit_btn)
        components_layout.addWidget(button_btn)
        components_layout.addWidget(listbox_btn)
        
        main_layout.addWidget(components_group)
        
        main_layout.addSpacing(10)
        
        placed_components_group = QGroupBox("Placed Components")
        placed_layout = QVBoxLayout(placed_components_group)
        
        self.components_list = QListWidget()
        self.components_list.setMinimumHeight(150)
        placed_layout.addWidget(self.components_list)
        
        clear_btn_layout = QHBoxLayout()
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_components)
        clear_btn_layout.addWidget(clear_btn)
        clear_btn_layout.addStretch()
        
        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        clear_btn_layout.addWidget(remove_btn)
        
        placed_layout.addLayout(clear_btn_layout)
        
        main_layout.addWidget(placed_components_group)
        
        main_layout.addStretch()
        
        export_layout = QHBoxLayout()
        self.export_btn = QPushButton("Export Plugin UI Schema")
        self.export_btn.setStyleSheet("background-color: #006400; color: white; padding: 10px; font-weight: bold;")
        self.export_btn.clicked.connect(self._export_schema)
        export_layout.addWidget(self.export_btn)
        export_layout.addStretch()
        main_layout.addLayout(export_layout)
    
    def _create_component_button(self, label, prefix):
        """Create a button for adding a component type."""
        btn = QPushButton(f"Add {label}")
        btn.setToolTip(f"Click to add a {label} component")
        
        def make_handler(p=prefix, l=label):
            def handler():
                self._add_component(p, l)
            return handler
        
        btn.clicked.connect(make_handler())
        return btn
    
    def _add_component(self, prefix, label):
        """Add a component to the list."""
        from Python.ui.plugin_layout_dialog import PluginLayoutDialog
        
        dialog = PluginLayoutDialog(self)
        if dialog.exec() == dialog.Accepted:
            component = {
                'type': prefix,
                'label': label,
                'grid_row': dialog.selected_row,
                'grid_col': dialog.selected_col,
                'alignment': dialog.selected_alignment,
                'name': dialog.component_name,
                'display_label': dialog.display_label
            }
            self.plugin_components.append(component)
            display_text = f"{label}: {dialog.display_label} (Row {dialog.selected_row+1}, Col {dialog.selected_col+1}) [{dialog.selected_alignment}]"
            self.components_list.addItem(display_text)
    
    def _clear_components(self):
        """Clear all placed components."""
        reply = QMessageBox.question(
            self, "Clear All",
            "Are you sure you want to remove all placed components?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.plugin_components.clear()
            self.components_list.clear()
    
    def _remove_selected(self):
        """Remove the selected component."""
        current_row = self.components_list.currentRow()
        if current_row >= 0:
            self.plugin_components.pop(current_row)
            self.components_list.takeItem(current_row)
    
    def _export_schema(self):
        """Export the plugin UI schema."""
        if not self.plugin_components:
            QMessageBox.warning(self, "No Components", "Please add at least one component before exporting.")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Plugin UI Schema",
            os.path.join(constants.APP_ROOT_DIR, "plugin_ui_schema.json"),
            "JSON Files (*.json)"
        )
        
        if file_path:
            import json
            schema = {
                'version': '1.0',
                'components': self.plugin_components
            }
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(schema, f, indent=2)
                QMessageBox.information(self, "Export Complete", f"Plugin UI schema exported to:\n{file_path}")
            except Exception as e:
                QMessageBox.critical(self, "Export Failed", f"Failed to export schema: {str(e)}")
    
    def _exit_plugin_mode(self):
        """Exit plugin mode and restart in normal mode."""
        reply = QMessageBox.question(
            self, "Exit Plugin Mode",
            "Are you sure you want to exit Plugin Creation Mode?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._restart_normal_mode()
    
    def _restart_normal_mode(self):
        """Restart the application without --plugin-mode."""
        import subprocess
        
        app_path = sys.executable
        script_path = os.path.join(constants.APP_ROOT_DIR, "Python", "main.py")
        
        try:
            subprocess.Popen([app_path, script_path])
            QApplication.quit()
        except Exception as e:
            QMessageBox.critical(self, "Restart Failed", f"Could not restart: {str(e)}")

