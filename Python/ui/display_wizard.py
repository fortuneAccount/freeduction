import configparser
import json
import logging
import os
import re
import subprocess
import tempfile
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QMessageBox, QComboBox, QCheckBox, QGroupBox,
    QGridLayout, QScrollArea, QSizePolicy, QTabWidget, QFileDialog,
    QSpinBox, QButtonGroup, QRadioButton
)
from PyQt6.QtCore import Qt, QRect
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QGuiApplication
from Python import constants

class MonitorCanvas(QWidget):
    """Visual representation of the monitor layout."""
    def __init__(self, screens, parent=None):
        super().__init__(parent)
        self.screens = screens
        self.setMinimumHeight(200)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self.screens:
            return

        all_geoms = [s.geometry() for s in self.screens]
        min_x = min(g.left() for g in all_geoms)
        min_y = min(g.top() for g in all_geoms)
        max_x = max(g.right() for g in all_geoms)
        max_y = max(g.bottom() for g in all_geoms)
        
        total_width = max_x - min_x
        total_height = max_y - min_y
        
        if total_width <= 0 or total_height <= 0:
            return
        
        padding = 20
        available_w = self.width() - (padding * 2)
        available_h = self.height() - (padding * 2)
        
        if available_w <= 0 or available_h <= 0:
            return
        
        scale = min(available_w / total_width, available_h / total_height)

        offset_x = padding + (available_w - (total_width * scale)) / 2
        offset_y = padding + (available_h - (total_height * scale)) / 2

        for i, screen in enumerate(self.screens):
            geom = screen.geometry()
            
            draw_x = int(offset_x + (geom.left() - min_x) * scale)
            draw_y = int(offset_y + (geom.top() - min_y) * scale)
            draw_w = int(geom.width() * scale)
            draw_h = int(geom.height() * scale)
            
            rect = QRect(draw_x, draw_y, draw_w, draw_h)

            is_primary = screen == QGuiApplication.primaryScreen()
            bg_color = QColor(40, 120, 200) if is_primary else QColor(60, 60, 60)
            
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.setBrush(QBrush(bg_color))
            painter.drawRect(rect)
            
            painter.setPen(Qt.GlobalColor.white)
            info_text = f"{i+1}\n{geom.width()}x{geom.height()}\n{int(screen.refreshRate())}Hz"
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, info_text)
            
            if is_primary:
                painter.drawText(rect.adjusted(5, 5, 0, 0), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop, "Primary")

class DisplayWizard(QDialog):
    """Wizard to capture monitor profile settings for the selected display tool."""
    def __init__(self, parent=None, windowing_app_name="", tool_path=""):
        super().__init__(parent)
        self.setup_tab = parent
        self.windowing_app_name = windowing_app_name or "supported display tool"
        self.tool_path = (tool_path or "").lower()
        self.save_format = "ini"
        self.setWindowTitle("Display Configuration Wizard")
        self.resize(900, 400)
        self.screens = []
        self._monitor_states = {}
        self._display_mode_cache = self._query_change_screen_resolution_modes()
        self._monitor_names = self._display_mode_cache.get("display_names", {})
        self._current_monitor_config = self._query_current_multimonitortool_config()
        self._init_ui()

    @staticmethod
    def _detect_save_format(tool_path):
        path = tool_path.lower()
        if "multimonitor" in path:
            return "multimonitor"
        if "displaychanger" in path:
            return "displaychanger"
        return "json"

    def _get_default_extension(self):
        path = (self.tool_path or "").lower()
        if "multimonitor" in path:
            return ".cfg"
        if "displaychanger" in path:
            return ".xml"
        if "changescreenresolution" in path:
            return ".cfg"
        return ".cfg"

    def _get_filter_string(self):
        ext = self._get_default_extension()
        if ext == ".cfg":
            return "Config Files (*.cfg);;All Files (*)"
        if ext == ".xml":
            return "XML Files (*.xml);;All Files (*)"
        return "Config Files (*.cfg);;All Files (*)"

    def _query_current_multimonitortool_config(self):
        """Query current monitor settings from MultiMonitorTool /saveconfig."""
        repo_root = Path(__file__).resolve().parents[2]
        for exe_name in ["MultiMonitorTool.exe", "multimonitortool.exe"]:
            exe_path = repo_root / "bin" / "multimonitortool" / exe_name
            if not exe_path.exists():
                continue
            try:
                tmp_path = os.path.join(tempfile.gettempdir(), "ccfg.cfg")
                kwargs = {
                    'capture_output': True,
                    'text': True,
                    'encoding': 'utf-8',
                    'errors': 'ignore',
                    'timeout': 10,
                }
                if os.name == 'nt':
                    kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                result = subprocess.run(
                    [str(exe_path), "/saveconfig", tmp_path],
                    **kwargs
                )
                if result.returncode == 0 and os.path.exists(tmp_path):
                    config = self._parse_multimonitortool_config(tmp_path)
                    os.unlink(tmp_path)
                    return config
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
            except (OSError, subprocess.SubprocessError, ValueError):
                pass
        return {}

    @staticmethod
    def _parse_multimonitortool_config(config_path):
        """Parse a MultiMonitorTool /saveconfig INI file."""
        config = {}
        try:
            parser = configparser.ConfigParser()
            parser.optionxform = str
            parser.read(config_path, encoding='utf-8')
            for section in parser.sections():
                config[section] = dict(parser[section])
        except Exception:
            pass
        return config

    def _get_current_monitor_settings(self, monitor_id):
        """Get current settings for a specific monitor from the queried config."""
        settings = {}
        if not self._current_monitor_config:
            return settings
        display_name = self._monitor_names.get(monitor_id, "")
        for section_name, section_data in self._current_monitor_config.items():
            name_val = section_data.get('Name', section_data.get('name', ''))
            if name_val:
                if display_name and display_name.lower() == name_val.lower():
                    settings = section_data
                    break
            elif f"DISPLAY{monitor_id}" in section_name.upper():
                settings = section_data
                break
        return settings

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.addTab(self._build_state_page("Desktop / Exit State"), "Desktop / Exit")
        self.tab_widget.addTab(self._build_state_page("Game / Running State"), "Game / Running")
        layout.addWidget(self.tab_widget, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addWidget(QFrame())
        self.save_button = QPushButton("Save As")
        self.save_button.setMinimumHeight(32)
        self.save_button.clicked.connect(self._save_configuration)
        btn_layout.addWidget(self.save_button)
        layout.addLayout(btn_layout)

    def _get_state_title(self, is_exit):
        return "Desktop / Exit State" if is_exit else "Game / Running State"

    def _get_state_title_from_tab(self, tab_text):
        if "Desktop" in tab_text or "Exit" in tab_text:
            return "Desktop / Exit State"
        elif "Game" in tab_text:
            return "Game / Running State"
        return tab_text

    def _save_configuration(self):
        """Save the collected monitor profile settings via a save-as file dialog."""
        current_tab_text = self.tab_widget.tabText(self.tab_widget.currentIndex())
        state_title = self._get_state_title_from_tab(current_tab_text)
        if "Desktop" in current_tab_text or "Exit" in current_tab_text:
            default_name = "DT_MC" + self._get_default_extension()
        elif "Game" in current_tab_text:
            default_name = "G_MON" + self._get_default_extension()
        else:
            default_name = current_tab_text.replace(" ", "_").replace("/", "_") + self._get_default_extension()
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Monitor Configuration", default_name,
            self._get_filter_string()
        )
        if not file_path:
            return
        ext = self._get_default_extension()
        if not file_path.endswith(ext) and not file_path.endswith(".json"):
            file_path += ext

        self._save_ini(file_path, state_title)

    def _collect_profile_data(self):
        profile_data = {}
        for state_name, state_map in self._monitor_states.items():
            profile_data[state_name] = {}
            for monitor_id, state in state_map.items():
                name_combo = state.get('name_combo')
                screen_name = name_combo.currentText() if name_combo else f'Display {monitor_id}'
                is_enabled = state['enable'].isChecked()
                if is_enabled:
                    profile_data[state_name][monitor_id] = {
                        'name': screen_name or f'Display {monitor_id}',
                        'enabled': True,
                        'resolution': state['resolution'].currentText(),
                        'refresh': state['refresh'].currentText(),
                        'bit_depth': state['bit_depth'].currentText(),
                        'position_x': state.get('position_x').value() if state.get('position_x') else 0,
                        'position_y': state.get('position_y').value() if state.get('position_y') else 0,
                        'orientation': state.get('orientation').currentText() if state.get('orientation') else 'Default',
                        'primary': state.get('primary').isChecked() if state.get('primary') else False,
                        'display_flags': '1' if state.get('display_flags_1') and state['display_flags_1'].isChecked() else '0',
                    }
                else:
                    resolution_text = state['resolution'].currentText()
                    width = height = '0'
                    if 'x' in resolution_text:
                        parts = resolution_text.split('x', 1)
                        width = parts[0] if parts[0] else '0'
                        height = parts[1] if len(parts) > 1 and parts[1] else '0'
                    profile_data[state_name][monitor_id] = {
                        'name': screen_name or f'Display {monitor_id}',
                        'enabled': False,
                        'resolution': '0x0',
                        'refresh': '0',
                        'bit_depth': '0',
                        'position_x': 0,
                        'position_y': 0,
                        'orientation': '0',
                        'primary': False,
                        'display_flags': '0',
                    }
        return profile_data

    def _save_ini(self, file_path, current_state_title=None):
        config = self.setup_tab.main_window.config
        profile_data = self._collect_profile_data()
        try:
            parser = configparser.ConfigParser()
            parser.optionxform = str

            if 'multimonitor' in (self.tool_path or '').lower():
                monitor_state_key = current_state_title or "Desktop / Exit State"
                sorted_monitors = sorted(profile_data.get(monitor_state_key, {}).items())
                for count, (monitor_id, data) in enumerate(sorted_monitors):
                    section_name = f"Monitor{count}"
                    name_val = data.get('name') or f'Display {monitor_id}'
                    monitor_id_val = ''
                    serial_val = ''
                    for section_data in self._current_monitor_config.values():
                        if section_data.get('Name', '').lower() == name_val.lower():
                            monitor_id_val = section_data.get('MonitorID', '')
                            serial_val = section_data.get('SerialNumber', '')
                            break
                    if not data.get('enabled', True):
                        parser[section_name] = {
                            'Name': name_val,
                            'MonitorID': monitor_id_val,
                            'SerialNumber': serial_val,
                            'BitsPerPixel': '0',
                            'Width': '0',
                            'Height': '0',
                            'DisplayFlags': '0',
                            'DisplayFrequency': '0',
                            'DisplayOrientation': '0',
                            'PositionX': '',
                            'PositionY': '0',
                        }
                    else:
                        resolution = data.get('resolution', '')
                        width = height = ''
                        if 'x' in resolution:
                            width, height = resolution.split('x', 1)
                        bit_depth = data.get('bit_depth', '32')
                        for strip_suffix in ('bit', 'bpp', 'bits'):
                            if bit_depth.lower().endswith(strip_suffix):
                                bit_depth = bit_depth[:-len(strip_suffix)]
                                break
                        parser[section_name] = {
                            'Name': name_val,
                            'MonitorID': monitor_id_val,
                            'SerialNumber': serial_val,
                            'BitsPerPixel': bit_depth,
                            'Width': width,
                            'Height': height,
                            'DisplayFlags': data.get('display_flags', '0'),
                            'DisplayFrequency': data.get('refresh', ''),
                            'DisplayOrientation': data.get('orientation', '0'),
                            'PositionX': str(data.get('position_x', '')),
                            'PositionY': str(data.get('position_y', '')),
                        }
            else:
                monitor_state_key = current_state_title or "Desktop / Exit State"
                state_map = profile_data.get(monitor_state_key, {})
                for monitor_id, data in state_map.items():
                    section_name = data.get('name') or f"Display {monitor_id}"
                    parser[section_name] = {
                        'resolution': data.get('resolution', ''),
                        'frequency': data.get('refresh', ''),
                        'bitdepth': data.get('bit_depth', ''),
                        'position_x': str(data.get('position_x', '')),
                        'position_y': str(data.get('position_y', '')),
                        'orientation': data.get('orientation', 'Default'),
                        'primary': 'Yes' if data.get('primary') else 'No',
                        'display_flags': data.get('display_flags', '0'),
                    }

            with open(file_path, 'w', encoding='utf-8') as f:
                parser.write(f)
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save file:\n{e}")
            return

        config.monitor_wizard_profiles = profile_data
        if current_state_title == "Game / Running State":
            config.multimonitor_gaming_path = file_path
        elif current_state_title == "Desktop / Exit State":
            config.multimonitor_media_path = file_path
        else:
            config.monitor_wizard_config_path = file_path
        self.setup_tab.main_window.config_manager.save_config(config)
        self._show_saved_message(file_path)


    def _show_saved_message(self, file_path):
        if not self.windowing_app_name:
            QMessageBox.information(self, "Saved", f"Monitor configuration saved to:\n{file_path}")
        else:
            QMessageBox.information(self, "Saved", f"Monitor configuration saved for {self.windowing_app_name} to:\n{file_path}")

    def _build_state_page(self, title):
        page = QWidget(self)
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(0, 0, 0, 0)

        info_label = QLabel(f"{title}: choose the monitor configuration that should be applied when the app is {('running' if 'Game' in title else 'not running')}.")
        info_label.setWordWrap(True)
        page_layout.addWidget(info_label)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container_layout = QGridLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setHorizontalSpacing(12)
        container_layout.setVerticalSpacing(12)

        display_indices = []
        if self._display_mode_cache and isinstance(self._display_mode_cache, dict):
            display_indices = [key for key in self._display_mode_cache.keys() if isinstance(key, int)]
        if not display_indices:
            display_indices = list(range(1, len(self.screens) + 1))
        display_indices = sorted(display_indices)

        monitor_columns = []
        for display_index in display_indices:
            screen_name = self._monitor_names.get(display_index, "")
            monitor_columns.append(self._build_monitor_panel(display_index, screen_name, title))

        for column_index, panel in enumerate(monitor_columns):
            container_layout.addWidget(panel, 0, column_index)

        scroll.setWidget(container)
        page_layout.addWidget(scroll, 1)
        self._update_primary_by_position(title)
        return page

    def _build_monitor_panel(self, index, screen, title):
        panel = QGroupBox()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(8)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Display:"))
        name_combo = QComboBox()
        name_combo.setEditable(True)
        monitor_names_for_this_display = self._get_monitor_names_for_display(index)
        name_combo.addItems(monitor_names_for_this_display)
        name_combo.setCurrentText(self._get_monitor_label(index, screen))
        name_layout.addWidget(name_combo, 1)
        panel_layout.addLayout(name_layout)

        enable_cb = QCheckBox("Enable")
        enable_cb.setChecked(True)
        panel_layout.addWidget(enable_cb)

        resolution_combo = QComboBox()
        resolution_combo.addItems(self._collect_supported_resolutions(screen, index))
        panel_layout.addWidget(QLabel("Resolution"))
        panel_layout.addWidget(resolution_combo)

        refresh_combo = QComboBox()
        refresh_combo.addItems([""])
        panel_layout.addWidget(QLabel("Hz"))
        panel_layout.addWidget(refresh_combo)

        bit_combo = QComboBox()
        bit_combo.addItems([""])
        panel_layout.addWidget(QLabel("Bit Depth"))
        panel_layout.addWidget(bit_combo)

        position_x_spin = QSpinBox()
        position_x_spin.setRange(-2147483648, 2147483647)
        position_x_spin.setPrefix("X: ")
        panel_layout.addWidget(position_x_spin)

        position_y_spin = QSpinBox()
        position_y_spin.setRange(-2147483648, 2147483647)
        position_y_spin.setPrefix("Y: ")
        panel_layout.addWidget(position_y_spin)

        display_flags_group = QButtonGroup(panel)
        display_flags_0 = QRadioButton("extend")
        display_flags_1 = QRadioButton("clone")
        display_flags_0.setChecked(True)
        display_flags_group.addButton(display_flags_0, 0)
        display_flags_group.addButton(display_flags_1, 1)
        display_flags_row = QHBoxLayout()
        display_flags_row.addWidget(QLabel("DisplayFlags"))
        display_flags_row.addWidget(display_flags_0)
        display_flags_row.addWidget(display_flags_1)
        panel_layout.addLayout(display_flags_row)

        orientation_combo = QComboBox()
        orientation_combo.addItems(["0", "90", "180", "270"])
        orientation_row = QHBoxLayout()
        orientation_row.addWidget(QLabel("Orientation"))
        orientation_row.addWidget(orientation_combo)
        panel_layout.addLayout(orientation_row)

        primary_cb = QCheckBox("Primary")
        primary_cb.setChecked(False)
        primary_cb.setEnabled(True)
        panel_layout.addWidget(primary_cb)

        reset_button = QPushButton("Reset")
        button_row = QHBoxLayout()
        button_row.addWidget(reset_button)
        button_row.addStretch()
        panel_layout.addLayout(button_row)

        panel_layout.addStretch()

        state = {
            'screen': screen,
            'enable': enable_cb,
            'resolution': resolution_combo,
            'refresh': refresh_combo,
            'bit_depth': bit_combo,
            'position_x': position_x_spin,
            'position_y': position_y_spin,
            'display_flags_0': display_flags_0,
            'display_flags_1': display_flags_1,
            'orientation': orientation_combo,
            'primary': primary_cb,
            'reset': reset_button,
            'display_index': index,
            'mode_catalog': self._display_mode_cache.get(index, []),
            'name_combo': name_combo,
        }
        self._monitor_states.setdefault(title, {})[index] = state

        resolution_combo.currentTextChanged.connect(lambda _text, s=state: self._populate_mode_options(s))
        reset_button.clicked.connect(lambda checked=False, s=state: self._reset_monitor_state(s))
        enable_cb.toggled.connect(lambda checked, idx=index, ttl=title: self._on_enable_toggled(idx, ttl, checked))
        self._set_monitor_state_from_current(state)
        return panel

    def _set_monitor_fields_enabled(self, state, enabled):
        for key in ('resolution', 'refresh', 'bit_depth', 'position_x', 'position_y',
                    'display_flags_0', 'display_flags_1', 'orientation', 'primary',
                    'reset', 'name_combo'):
            widget = state.get(key)
            if widget is not None:
                widget.setEnabled(enabled)

    def _on_enable_toggled(self, display_index, title, checked):
        state = self._monitor_states.get(title, {}).get(display_index)
        if not state:
            return
        self._set_monitor_fields_enabled(state, checked)
        if checked:
            self._set_monitor_state_from_current(state)
        else:
            idx = state['resolution'].findText("0x0")
            if idx >= 0:
                state['resolution'].setCurrentIndex(idx)
            else:
                state['resolution'].setCurrentText("0x0")
            state['refresh'].setCurrentText("0")
            state['bit_depth'].setCurrentText("0")
            state['position_x'].setValue(0)
            state['position_y'].setValue(0)
            state['orientation'].setCurrentText("0")
            state['display_flags_0'].setChecked(True)
            if state['primary'].isChecked():
                state['primary'].setChecked(False)
                state['primary'].setEnabled(True)
                for idx, s in self._monitor_states.get(title, {}).items():
                    if idx != display_index and s['enable'].isChecked() and not s['primary'].isChecked():
                        s['primary'].setChecked(True)
                        s['primary'].setEnabled(False)
                        break

    def _update_primary_by_position(self, title):
        states = self._monitor_states.get(title, {})
        primary_index = None
        for idx, state in states.items():
            if not state['enable'].isChecked():
                continue
            pos_x = state['position_x'].value()
            pos_y = state['position_y'].value()
            if pos_x == 0 and pos_y == 0:
                primary_index = idx
                break
        for idx, state in states.items():
            if idx == primary_index:
                state['primary'].blockSignals(True)
                state['primary'].setChecked(True)
                state['primary'].setEnabled(False)
                state['primary'].blockSignals(False)
            else:
                state['primary'].blockSignals(True)
                state['primary'].setChecked(False)
                state['primary'].setEnabled(True)
                state['primary'].blockSignals(False)

    def _on_primary_toggled(self, display_index, title, checked):
        if checked:
            for idx, state in self._monitor_states.get(title, {}).items():
                if idx != display_index:
                    state['primary'].blockSignals(True)
                    state['primary'].setChecked(False)
                    state['primary'].setEnabled(True)
                    state['primary'].blockSignals(False)
            self._monitor_states[title][display_index]['primary'].setEnabled(False)
        else:
            for idx, state in self._monitor_states.get(title, {}).items():
                if idx != display_index and not state['primary'].isChecked():
                    state['primary'].setEnabled(True)

    def _get_monitor_label(self, index, screen):
        if isinstance(screen, str) and screen:
            return screen
        if screen is not None:
            name = screen.name() if hasattr(screen, 'name') else ""
            if name:
                return name
        return f"Display {index}"

    def _get_monitor_names_for_display(self, index):
        names = []
        if isinstance(self._monitor_names, dict) and index in self._monitor_names:
            names.append(self._monitor_names[index])
        all_names = set()
        for idx, name in self._monitor_names.items():
            if name and name not in all_names:
                all_names.add(name)
        for name in sorted(all_names):
            if name not in names:
                names.append(name)
        if not names:
            names = [f"Display {index}"]
        return names

    def _remove_display(self, display_index, title):
        if title in self._monitor_states and display_index in self._monitor_states[title]:
            del self._monitor_states[title][display_index]
            current_widget = self.tab_widget.currentWidget()
            if current_widget:
                self._rebuild_state_page(title, current_widget)

    def _rebuild_state_page(self, title, page_widget):
        layout = page_widget.layout()
        if layout is None:
            return
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
        self._rebuild_state_page_content(page_widget, title)

    def _rebuild_state_page_content(self, page, title):
        page_layout = page.layout()
        page_layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        container = QWidget()
        container_layout = QGridLayout(container)
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setHorizontalSpacing(12)
        container_layout.setVerticalSpacing(12)

        display_indices = sorted(self._monitor_states.get(title, {}).keys())

        monitor_columns = []
        for display_index in display_indices:
            state = self._monitor_states[title][display_index]
            monitor_columns.append(self._rebuild_monitor_panel(display_index, state.get('screen', ''), title))

        for column_index, panel in enumerate(monitor_columns):
            container_layout.addWidget(panel, 0, column_index)

        scroll.setWidget(container)
        page_layout.addWidget(scroll, 1)
        self._update_primary_by_position(title)

    def _rebuild_monitor_panel(self, index, screen, title):
        panel = QGroupBox()
        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(8)

        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Display:"))
        name_combo = QComboBox()
        name_combo.setEditable(True)
        monitor_names_for_this_display = self._get_monitor_names_for_display(index)
        name_combo.addItems(monitor_names_for_this_display)
        name_combo.setCurrentText(self._get_monitor_label(index, screen))
        name_layout.addWidget(name_combo, 1)
        panel_layout.addLayout(name_layout)

        enable_cb = QCheckBox("Enable")
        enable_cb.setChecked(True)
        panel_layout.addWidget(enable_cb)

        resolution_combo = QComboBox()
        resolution_combo.addItems(self._collect_supported_resolutions(screen, index))
        panel_layout.addWidget(QLabel("Resolution"))
        panel_layout.addWidget(resolution_combo)

        refresh_combo = QComboBox()
        refresh_combo.addItems([""])
        panel_layout.addWidget(QLabel("Hz"))
        panel_layout.addWidget(refresh_combo)

        bit_combo = QComboBox()
        bit_combo.addItems([""])
        panel_layout.addWidget(QLabel("Bit Depth"))
        panel_layout.addWidget(bit_combo)

        position_x_spin = QSpinBox()
        position_x_spin.setRange(-2147483648, 2147483647)
        position_x_spin.setPrefix("X: ")
        panel_layout.addWidget(position_x_spin)

        position_y_spin = QSpinBox()
        position_y_spin.setRange(-2147483648, 2147483647)
        position_y_spin.setPrefix("Y: ")
        panel_layout.addWidget(position_y_spin)

        display_flags_group = QButtonGroup(panel)
        display_flags_0 = QRadioButton("extend")
        display_flags_1 = QRadioButton("clone")
        display_flags_0.setChecked(True)
        display_flags_group.addButton(display_flags_0, 0)
        display_flags_group.addButton(display_flags_1, 1)
        display_flags_row = QHBoxLayout()
        display_flags_row.addWidget(QLabel("DisplayFlags"))
        display_flags_row.addWidget(display_flags_0)
        display_flags_row.addWidget(display_flags_1)
        panel_layout.addLayout(display_flags_row)

        orientation_combo = QComboBox()
        orientation_combo.addItems(["0", "90", "180", "270"])
        orientation_row = QHBoxLayout()
        orientation_row.addWidget(QLabel("Orientation"))
        orientation_row.addWidget(orientation_combo)
        panel_layout.addLayout(orientation_row)

        primary_cb = QCheckBox("Primary")
        primary_cb.setChecked(False)
        primary_cb.setEnabled(True)
        primary_cb.toggled.connect(lambda checked, idx=index, ttl=title: self._on_primary_toggled(idx, ttl, checked))
        panel_layout.addWidget(primary_cb)

        reset_button = QPushButton("Reset")
        button_row = QHBoxLayout()
        button_row.addWidget(reset_button)
        button_row.addStretch()
        panel_layout.addLayout(button_row)

        panel_layout.addStretch()

        state = self._monitor_states[title][index]
        state.update({
            'enable': enable_cb,
            'resolution': resolution_combo,
            'refresh': refresh_combo,
            'bit_depth': bit_combo,
            'position_x': position_x_spin,
            'position_y': position_y_spin,
            'display_flags_0': display_flags_0,
            'display_flags_1': display_flags_1,
            'orientation': orientation_combo,
            'primary': primary_cb,
            'reset': reset_button,
            'name_combo': name_combo,
        })

        resolution_combo.currentTextChanged.connect(lambda _text, s=state: self._populate_mode_options(s))
        reset_button.clicked.connect(lambda checked=False, s=state: self._reset_monitor_state(s))
        enable_cb.toggled.connect(lambda checked, idx=index, ttl=title: self._on_enable_toggled(idx, ttl, checked))
        self._set_monitor_state_from_current(state)
        return panel

    @staticmethod
    def _parse_change_screen_resolution_output(output):
        """Parse ChangeScreenResolution /m /l output into display->modes mapping."""
        parsed = {}
        display_names = {}
        if not output:
            return {"display_names": display_names}

        mode_patterns = [
            r"^\s*(?P<resolution>\d+x\d+)\s+(?P<bit_depth>\d+(?:bit|bpp))\s+@(?P<refresh>\d+(?:\.\d+)?)Hz(?:\s+.*)?$",
            r"^\s*(?P<resolution>\d+x\d+)\s+(?P<refresh>\d+(?:\.\d+)?)Hz\s+(?P<bit_depth>\d+(?:bit|bpp))(?:\s+.*)?$",
            r"^\s*(?P<resolution>\d+x\d+)\s+@\s*(?P<refresh>\d+(?:\.\d+)?)Hz\s*,\s*(?P<bit_depth>\d+(?:bit|bpp))(?:\s+.*)?$",
        ]

        current_display = None
        for raw_line in output.splitlines():
            line = raw_line.rstrip()
            if not line:
                continue

            stripped = line.strip()
            if stripped.startswith("Connected display devices"):
                continue

            display_match = re.match(r"^\s*\[(\d+)\]\s+(.+?)(?:\s{2,}(.*))?$", stripped)
            if display_match:
                current_display = int(display_match.group(1))
                display_device = display_match.group(2).strip().rstrip(':')
                display_device = display_device.rstrip('\\').rstrip(':')
                display_name = display_match.group(3).strip() if display_match.group(3) else display_device
                display_names[current_display] = display_name
                parsed[current_display] = []
                continue

            legacy_display_match = re.match(r"^Display\s*:?\s*(\d+)$", stripped, flags=re.IGNORECASE)
            if legacy_display_match:
                current_display = int(legacy_display_match.group(1))
                display_names[current_display] = f"Display {current_display}"
                parsed[current_display] = []
                continue

            monitor_match = re.match(r"^\s*(\\\\.\\DISPLAY\d+\\Monitor\d+)\s*(.*)$", stripped)
            if monitor_match and current_display is not None:
                display_names[current_display] = monitor_match.group(2).strip() or monitor_match.group(1)
                continue

            if stripped.startswith("Display modes for"):
                display_name = stripped.split("for", 1)[1].strip().rstrip(':')
                mode_display_match = re.match(r"^\s*Display modes for.*?DISPLAY(\d+)\s*:", stripped)
                if mode_display_match:
                    current_display = int(mode_display_match.group(1))
                    display_names[current_display] = rf"\\.\DISPLAY{current_display}"
                    parsed.setdefault(current_display, [])
                    remainder = stripped.split(":", 1)[1] if ":" in stripped else ""
                    for pattern in mode_patterns:
                        mode_match = re.match(pattern, remainder)
                        if mode_match and current_display is not None:
                            parsed[current_display].append({
                                'resolution': mode_match.group('resolution'),
                                'refresh': mode_match.group('refresh'),
                                'bit_depth': mode_match.group('bit_depth'),
                            })
                            break
                elif current_display is not None:
                    display_names[current_display] = display_name
                continue

            for pattern in mode_patterns:
                mode_match = re.match(pattern, stripped)
                if mode_match and current_display is not None:
                    parsed.setdefault(current_display, []).append({
                        'resolution': mode_match.group('resolution'),
                        'refresh': mode_match.group('refresh'),
                        'bit_depth': mode_match.group('bit_depth'),
                    })
                    break

        valid_displays = {key for key, value in parsed.items() if value}
        parsed = {key: value for key, value in parsed.items() if value}
        display_names = {key: value for key, value in display_names.items() if key in valid_displays}

        return {"display_names": display_names, **parsed}

    def _query_change_screen_resolution_modes(self):
        """Query supported display modes through the bundled ChangeScreenResolution utility."""
        repo_root = Path(__file__).resolve().parents[2]
        for exe_name in ["ChangeScreenResolution.exe", "changescreenresolution.exe"]:
            exe_path = repo_root / "bin" / exe_name
            if not exe_path.exists():
                continue

            cmd = [str(exe_path), "/m", "/l"]
            try:
                kwargs = {
                    'capture_output': True,
                    'text': True,
                    'encoding': 'utf-8',
                    'errors': 'ignore',
                    'timeout': 10,
                }
                if os.name == 'nt':
                    kwargs['creationflags'] = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
                result = subprocess.run(cmd, **kwargs)
            except (OSError, subprocess.SubprocessError, ValueError):
                continue

            if result.stdout:
                return self._parse_change_screen_resolution_output(result.stdout)

        return {"display_names": {}}

    def _collect_supported_resolutions(self, screen, display_index=None):
        """Return display resolutions from ChangeScreenResolution when available, otherwise fall back to common values."""
        if display_index is not None and isinstance(self._display_mode_cache, dict) and display_index in self._display_mode_cache:
            seen = set()
            resolutions = []
            for mode in self._display_mode_cache[display_index]:
                resolution = mode.get('resolution', '')
                if resolution and resolution not in seen:
                    seen.add(resolution)
                    resolutions.append(resolution)
            if resolutions:
                return resolutions
        return ["1920x1080", "2560x1440", "3840x2160", "1280x720", "1600x900", "1366x768", "1280x1024"]

    def _populate_mode_options(self, state):
        """Populate Hz and bit depth lists from the selected resolution using the queried display modes when available."""
        resolution = state['resolution'].currentText()
        if not resolution:
            state['refresh'].clear()
            state['bit_depth'].clear()
            state['refresh'].addItems([""])
            state['bit_depth'].addItems([""])
            return

        mode_catalog = state.get('mode_catalog', [])
        matching_modes = [mode for mode in mode_catalog if mode.get('resolution') == resolution]
        if matching_modes:
            refreshes = []
            bit_depths = []
            for mode in matching_modes:
                refresh = mode.get('refresh', '')
                bit_depth = mode.get('bit_depth', '')
                if refresh and refresh not in refreshes:
                    refreshes.append(refresh)
                if bit_depth and bit_depth not in bit_depths:
                    bit_depths.append(bit_depth)
            refreshes = refreshes or ["60"]
            bit_depths = bit_depths or ["32bpp"]
        else:
            refreshes = ["60", "75", "120", "144", "165", "240"]
            bit_depths = ["8-bit", "10-bit", "12-bit"]

        state['refresh'].clear()
        state['bit_depth'].clear()
        state['refresh'].addItems(refreshes)
        state['bit_depth'].addItems(bit_depths)

    def _reset_monitor_state(self, state):
        self._set_monitor_state_from_current(state)

    def _set_monitor_state_from_current(self, state):
        monitor_id = state.get('display_index')
        current = self._get_current_monitor_settings(monitor_id)
        if current:
            state['enable'].setChecked(True)
            width = current.get('Width', '')
            height = current.get('Height', '')
            if width and height:
                resolution = f"{width}x{height}"
                idx = state['resolution'].findText(resolution)
                if idx >= 0:
                    state['resolution'].setCurrentIndex(idx)
                else:
                    state['resolution'].setCurrentText(resolution)
            refresh = current.get('DisplayFrequency', current.get('frequency', ''))
            if refresh:
                state['refresh'].setCurrentText(refresh)
            bit_depth = current.get('BitsPerPixel', current.get('bitdepth', ''))
            if bit_depth:
                bpp_text = f"{bit_depth}bit"
                if bit_depth == '32':
                    bpp_text = '32bit'
                state['bit_depth'].setCurrentText(bpp_text)
            try:
                pos_x = int(current.get('PositionX', 0))
            except (ValueError, TypeError):
                pos_x = 0
            try:
                pos_y = int(current.get('PositionY', 0))
            except (ValueError, TypeError):
                pos_y = 0
            state['position_x'].setValue(pos_x)
            state['position_y'].setValue(pos_y)
            orientation = current.get('DisplayOrientation', 'Default')
            if orientation in ["0", "90", "180", "270"]:
                state['orientation'].setCurrentText(orientation)
            else:
                state['orientation'].setCurrentText("0")
            is_primary = current.get('primary', 'No').lower() in ('yes', 'true', '1')
            if not is_primary:
                is_primary = current.get('primary', '').lower() in ('yes', 'true', '1')
            state['primary'].setChecked(is_primary)
            display_flags = current.get('DisplayFlags', '0')
            if display_flags == '1':
                state['display_flags_1'].setChecked(True)
            else:
                state['display_flags_0'].setChecked(True)
