from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QGridLayout, QRadioButton, QButtonGroup, QPushButton,
    QGroupBox, QComboBox
)
from PyQt6.QtCore import Qt


ALIGNMENT_OPTIONS = [
    ("top-left", "Top Left"),
    ("top", "Top"),
    ("top-right", "Top Right"),
    ("left", "Left"),
    ("center", "Center"),
    ("right", "Right"),
    ("bottom-left", "Bottom Left"),
    ("bottom", "Bottom"),
    ("bottom-right", "Bottom Right"),
]


class PluginLayoutDialog(QDialog):
    """Modal dialog for placing a component on the grid with alignment options."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Place Component on Grid")
        self.setMinimumWidth(350)
        
        self.selected_row = 0
        self.selected_col = 0
        self.selected_alignment = "top-left"
        self.component_name = ""
        self.display_label = ""
        
        self._populate_ui()
    
    def _populate_ui(self):
        """Create and arrange all widgets."""
        layout = QVBoxLayout(self)
        
        name_layout = QHBoxLayout()
        name_label = QLabel("Component Name:")
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g., config_file_path")
        self.name_edit.textChanged.connect(self._on_name_changed)
        name_layout.addWidget(name_label)
        name_layout.addWidget(self.name_edit)
        layout.addLayout(name_layout)
        
        display_layout = QHBoxLayout()
        display_label = QLabel("Display Label:")
        self.display_edit = QLineEdit()
        self.display_edit.setPlaceholderText("e.g., Configuration File")
        self.display_edit.textChanged.connect(self._on_display_changed)
        display_layout.addWidget(display_label)
        display_layout.addWidget(self.display_edit)
        layout.addLayout(display_layout)
        
        grid_group = QGroupBox("Grid Position (3-wide grid)")
        grid_layout = QGridLayout(grid_group)
        
        row_label = QLabel("Row:")
        grid_layout.addWidget(row_label, 0, 0)
        
        self.row_combo = QComboBox()
        for i in range(10):
            self.row_combo.addItem(str(i + 1), i)
        self.row_combo.setCurrentIndex(0)
        self.row_combo.currentIndexChanged.connect(self._on_row_changed)
        grid_layout.addWidget(self.row_combo, 0, 1)
        
        col_label = QLabel("Column:")
        grid_layout.addWidget(col_label, 1, 0)
        
        self.col_combo = QComboBox()
        for i in range(3):
            self.col_combo.addItem(str(i + 1), i)
        self.col_combo.setCurrentIndex(0)
        self.col_combo.currentIndexChanged.connect(self._on_col_changed)
        grid_layout.addWidget(self.col_combo, 1, 1)
        
        layout.addWidget(grid_group)
        
        align_group = QGroupBox("Alignment (relative to surrounding items)")
        align_layout = QGridLayout(align_group)
        
        self.alignment_group = QButtonGroup(self)
        
        row = 0
        col = 0
        for value, label in ALIGNMENT_OPTIONS:
            radio = QRadioButton(label)
            radio.setChecked(value == "top-left")
            radio.toggled.connect(lambda checked, v=value: self._on_alignment_changed(v) if checked else None)
            self.alignment_group.addButton(radio)
            align_layout.addWidget(radio, row, col)
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        layout.addWidget(align_group)
        
        button_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("Place")
        self.ok_btn.setEnabled(False)
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
    
    def _on_name_changed(self, text):
        """Handle name field changes."""
        self.component_name = text
        self._update_ok_button()
    
    def _on_display_changed(self, text):
        """Handle display label changes."""
        self.display_label = text
        self._update_ok_button()
    
    def _on_row_changed(self, index):
        """Handle row selection changes."""
        self.selected_row = index
    
    def _on_col_changed(self, index):
        """Handle column selection changes."""
        self.selected_col = index
    
    def _on_alignment_changed(self, value):
        """Handle alignment selection changes."""
        self.selected_alignment = value
    
    def _update_ok_button(self):
        """Enable OK button only if both name and display label are filled."""
        self.ok_btn.setEnabled(bool(self.component_name and self.display_label))
