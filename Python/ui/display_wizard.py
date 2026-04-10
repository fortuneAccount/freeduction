import os
import logging
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, 
    QFrame, QWidget, QMessageBox
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
        
        padding = 20
        available_w = self.width() - (padding * 2)
        available_h = self.height() - (padding * 2)
        
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
    """Wizard to detect monitors and generate NirSoft MultiMonitorTool configs."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_tab = parent
        self.setWindowTitle("Display Configuration Wizard")
        self.resize(500, 450)
        self.screens = QGuiApplication.screens()
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        
        header = QLabel("<h2>Monitor Layout Detected</h2>")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)
        
        desc = QLabel(
            "This wizard captures your current monitor arrangement, resolutions, and refresh rates. "
            "You can save this state as a configuration file for use with MultiMonitorTool."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Visual representation
        self.canvas = MonitorCanvas(self.screens, self)
        layout.addWidget(self.canvas)

        # List details
        list_frame = QFrame()
        list_frame.setFrameStyle(QFrame.Shape.StyledPanel | QFrame.Shadow.Sunken)
        list_layout = QVBoxLayout(list_frame)
        
        for i, s in enumerate(self.screens):
            g = s.geometry()
            primary = " (Primary)" if s == QGuiApplication.primaryScreen() else ""
            lbl = QLabel(f"Monitor {i+1}: {g.width()}x{g.height()} @ {int(s.refreshRate())}Hz at {g.x()},{g.y()}{primary}")
            list_layout.addWidget(lbl)
        
        layout.addWidget(list_frame)

        # Actions
        btn_layout = QHBoxLayout()
        
        self.save_gaming_btn = QPushButton("Save as Gaming Profile")
        self.save_gaming_btn.clicked.connect(lambda: self._save_config("gaming"))
        
        self.save_desktop_btn = QPushButton("Save as Desktop Profile")
        self.save_desktop_btn.clicked.connect(lambda: self._save_config("desktop"))
        
        cancel_btn = QPushButton("Close")
        cancel_btn.clicked.connect(self.reject)
        
        btn_layout.addWidget(self.save_gaming_btn)
        btn_layout.addWidget(self.save_desktop_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(cancel_btn)
        
        layout.addLayout(btn_layout)

    def _save_config(self, profile_type):
        """Calls MultiMonitorTool to save the current config to a file."""
        mm_tool_path = self.setup_tab.main_window.config.multi_monitor_tool_path
        
        if not mm_tool_path or not os.path.exists(mm_tool_path):
            QMessageBox.critical(self, "Tool Not Found", 
                               "MultiMonitorTool.exe is not configured or missing in /bin.\n"
                               "Please download it from the DISPLAY tab first.")
            return

        # Determine destination
        filename = "GamingDisplay.cfg" if profile_type == "gaming" else "DesktopDisplay.cfg"
        dest_path = os.path.join(constants.APP_ROOT_DIR, filename)

        try:
            # Command: MultiMonitorTool.exe /SaveConfig "path"
            import subprocess
            cmd = [mm_tool_path, "/SaveConfig", dest_path]
            subprocess.run(cmd, check=True, creationflags=0x08000000)
            
            # Update Config
            config = self.setup_tab.main_window.config
            if profile_type == "gaming":
                config.multimonitor_gaming_path = dest_path
                # Ensure the Gaming Profile is enabled in Setup
                config.defaults['multimonitor_gaming_path_enabled'] = True
            else:
                config.multimonitor_media_path = dest_path
                # Ensure the Desktop Profile is enabled in Setup
                config.defaults['multimonitor_media_path_enabled'] = True
            
            # Ensure Multi-Monitor tool itself is enabled
            config.defaults['multi_monitor_tool_path_enabled'] = True
            
            self.setup_tab.main_window.config_manager.save_config(config)
            
            QMessageBox.information(self, "Success", 
                                  f"Configuration saved to:\n{dest_path}\n\n"
                                  f"Path has been assigned to the {profile_type.capitalize()} profile.")
            
            self.accept()
            
        except Exception as e:
            logging.error(f"Failed to create .cfg file: {e}")
            QMessageBox.critical(self, "Error", f"Could not generate config file: {str(e)}")