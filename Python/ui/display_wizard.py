import configparser
import json
import logging
import os
import re
import subprocess
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QWidget, QMessageBox, QComboBox, QCheckBox, QGroupBox,
    QGridLayout, QScrollArea, QSizePolicy, QTabWidget, QFileDialog
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

        # Calculate bounding box of all screens to scale them to the widget
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

        # Center the layout
        offset_x = padding + (available_w - (total_width * scale)) / 2
        offset_y = padding + (available_h - (total_height * scale)) / 2

        for i, screen in enumerate(self.screens):
            geom = screen.geometry()
            
            # Calculate scaled rect
            draw_x = int(offset_x + (geom.left() - min_x) * scale)
            draw_y = int(offset_y + (geom.top() - min_y) * scale)
            draw_w = int(geom.width() * scale)
            draw_h = int(geom.height() * scale)
            
            rect = QRect(draw_x, draw_y, draw_w, draw_h)

            # Colors
            is_primary = screen == QGuiApplication.primaryScreen()
            bg_color = QColor(40, 120, 200) if is_primary else QColor(60, 60, 60)
            
            painter.setPen(QPen(Qt.GlobalColor.white, 2))
            painter.setBrush(QBrush(bg_color))
            painter.drawRect(rect)
            
            # Labels
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
        self.resize(900, 325)  # Reduced height by 50%
        self.screens = []
        self._monitor_states = {}
        self._display_mode_cache = self._query_change_screen_resolution_modes()
        self._monitor_names = self._display_mode_cache.get("display_names", {})
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
        return ".ini"

    def _get_filter_string(self):
        return "INI Files (*.ini);;All Files (*)"

    def _init_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel(f"<h2>Configure monitor states for {self.windowing_app_name}</h2>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        tool_name = "ChangeScreenResolution" if "changescreenresolution" in self.tool_path else "the selected monitor tool"
        display_label = self.windowing_app_name or "the selected monitor tool"
        desc_text = (
            f"Use the display modes reported by {tool_name} to choose each monitor's resolution, frequency, and bit depth for {display_label}. "
            "The dropdown values are populated from the current query output."
        )
        desc = QLabel(desc_text)
        desc.setWordWrap(True)
        layout.addWidget(desc)

        self.tab_widget = QTabWidget(self)
        self.tab_widget.addTab(self._build_state_page("Desktop / Exit State"), "Desktop / Exit")
        self.tab_widget.addTab(self._build_state_page("Game / Running State"), "Game / Running")
        layout.addWidget(self.tab_widget, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_button = QPushButton("Save As")
        self.save_button.setMinimumHeight(32)
        self.save_button.clicked.connect(self._save_configuration)
        btn_layout.addWidget(self.save_button)
        layout.addLayout(btn_layout)

    def _get_state_title(self, is_exit):
        return "Desktop / Exit State" if is_exit else "Game / Running State"

    def _save_configuration(self):
        """Save the collected monitor profile settings via a save-as file dialog."""
        # Dynamic filename based on current tab
        current_tab_text = self.tab_widget.tabText(self.tab_widget.currentIndex())
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

        self._save_ini(file_path)

    def _collect_profile_data(self):
        profile_data = {}
        for state_name, state_map in self._monitor_states.items():
            profile_data[state_name] = {}
            for monitor_id, state in state_map.items():
                screen = state.get('screen')
                screen_name = ""
                if screen is not None and hasattr(screen, 'name'):
                    screen_name = screen.name() or ""
                if isinstance(screen, str) and screen:
                    screen_name = screen
                elif screen is not None and hasattr(screen, 'name'):
                    screen_name = screen.name() or ""
                profile_data[state_name][monitor_id] = {
                    'name': screen_name or f'Display {monitor_id}',
                    'enabled': state['enable'].isChecked(),
                    'resolution': state['resolution'].currentText(),
                    'refresh': state['refresh'].currentText(),
                    'bit_depth': state['bit_depth'].currentText(),
                }
        return profile_data

    def _save_ini(self, file_path):
        config = self.setup_tab.main_window.config
        profile_data = self._collect_profile_data()
        try:
            parser = configparser.ConfigParser()
            parser.optionxform = str
            for state_name, state_map in profile_data.items():
                for monitor_id, data in state_map.items():
                    section_name = data.get('name') or f"Display {monitor_id}"
                    parser[section_name] = {
                        'resolution': data.get('resolution', ''),
                        'frequency': data.get('refresh', ''),
                        'bitdepth': data.get('bit_depth', ''),
                    }

            with open(file_path, 'w', encoding='utf-8') as f:
                parser.write(f)
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", f"Could not save file:\n{e}")
            return

        config.monitor_wizard_profiles = profile_data
        config.monitor_wizard_config_path = file_path
        self.setup_tab.main_window.config_manager.save_config(config)
        self._show_saved_message(file_path)


    def _show_saved_message(self, file_path):
        if not self.windowing_app_name:
            QMessageBox.information(self, "Saved", f"Monitor configuration saved to:\n{file_path}")
        else:
            QMessageBox.information(self, "Saved", f"Monitor configuration saved for {self.windowing_app_name} to:\n{file_path}")
        self.accept()

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
        return page

    def _build_monitor_panel(self, index, screen, title):
        panel = QGroupBox(self._get_monitor_label(index, screen))
        panel_layout = QVBoxLayout(panel)
        panel_layout.setSpacing(8)

        enable_cb = QCheckBox("Enable")
        enable_cb.setChecked(True)
        panel_layout.addWidget(enable_cb)

        display_index = index
        resolution_combo = QComboBox()
        resolution_combo.addItems(self._collect_supported_resolutions(screen, display_index))
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

        reset_button = QPushButton("Reset")
        set_current_button = QPushButton("Set as Current")
        button_row = QHBoxLayout()
        button_row.addWidget(reset_button)
        button_row.addWidget(set_current_button)
        panel_layout.addLayout(button_row)

        panel_layout.addStretch()

        self._monitor_states.setdefault(title, {})[index] = {
            'screen': screen,
            'enable': enable_cb,
            'resolution': resolution_combo,
            'refresh': refresh_combo,
            'bit_depth': bit_combo,
            'reset': reset_button,
            'set_current': set_current_button,
            'display_index': index,
            'mode_catalog': self._display_mode_cache.get(index, []),
        }

        resolution_combo.currentTextChanged.connect(lambda _text, state=self._monitor_states[title][index]: self._populate_mode_options(state))
        reset_button.clicked.connect(lambda checked=False, state=self._monitor_states[title][index]: self._reset_monitor_state(state))
        set_current_button.clicked.connect(lambda checked=False, state=self._monitor_states[title][index]: self._set_monitor_state_from_current(state))
        self._set_monitor_state_from_current(self._monitor_states[title][index])
        return panel

    def _get_monitor_label(self, index, screen):
        if isinstance(screen, str) and screen:
            return screen
        if screen is not None:
            name = screen.name() if hasattr(screen, 'name') else ""
            if name:
                return name
        return f"Display {index}"

    @staticmethod
    def _parse_change_screen_resolution_output(output):
        """Parse ChangeScreenResolution /m /l output into display->modes mapping."""
        parsed = {}
        display_names = {}
        if not output:
            return {"display_names": display_names}

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

            monitor_match = re.match(r"^\s*(\\\\\.\\DISPLAY\d+\\Monitor\d+)\s*(.*)$", stripped)
            if monitor_match and current_display is not None:
                display_names[current_display] = monitor_match.group(2).strip() or monitor_match.group(1)
                continue

            if stripped.startswith("Display modes for"):
                if current_display is not None:
                    display_name = stripped.split("for", 1)[1].strip().rstrip(':')
                    display_names[current_display] = display_name
                continue

            mode_patterns = [
                r"^\s*(?P<resolution>\d+x\d+)\s+(?P<bit_depth>\d+(?:bit|bpp))\s+@(?P<refresh>\d+(?:\.\d+)?)Hz(?:\s+.*)?$",
                r"^\s*(?P<resolution>\d+x\d+)\s+(?P<refresh>\d+(?:\.\d+)?)Hz\s+(?P<bit_depth>\d+(?:bit|bpp))(?:\s+.*)?$",
                r"^\s*(?P<resolution>\d+x\d+)\s+@\s*(?P<refresh>\d+(?:\.\d+)?)Hz\s*,\s*(?P<bit_depth>\d+(?:bit|bpp))(?:\s+.*)?$",
            ]
            for pattern in mode_patterns:
                mode_match = re.match(pattern, stripped)
                if mode_match and current_display is not None:
                    parsed.setdefault(current_display, []).append({
                        'resolution': mode_match.group('resolution'),
                        'refresh': mode_match.group('refresh'),
                        'bit_depth': mode_match.group('bit_depth'),
                    })
                    break

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
        state['enable'].setChecked(True)
        state['resolution'].setCurrentIndex(0)
        state['refresh'].setCurrentIndex(0)
        state['bit_depth'].setCurrentIndex(0)

    def _set_monitor_state_from_current(self, state):
        state['enable'].setChecked(True)
        if state['resolution'].count():
            state['resolution'].setCurrentIndex(0)
        if state['refresh'].count():
            state['refresh'].setCurrentIndex(0)
        if state['bit_depth'].count():
            state['bit_depth'].setCurrentIndex(0)
        self._populate_mode_options(state)