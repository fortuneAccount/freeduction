from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QScrollArea,
    QPushButton, QCheckBox, QGroupBox, QRadioButton, QButtonGroup, QGridLayout,
    QLineEdit, QTextEdit, QProgressBar, QDialog, QDialogButtonBox, QFileDialog,
    QMenu, QToolButton
)
from PyQt6.QtCore import pyqtSignal, Qt
from Python.ui.accordion import AccordionSection
from Python.models import AppConfig
from Python import constants
import os
import datetime



PATH_KEYS = [
    "profiles_dir", "launchers_dir", "launcher_executable",
    "controller_mapper_path", "multimonitortool_path",
    "just_after_launch_path", "just_before_exit_path",
    "p1_profile_path", "p2_profile_path", "mediacenter_profile_path",
    "multimonitor_gaming_path", "multimonitor_media_path",
    "pre1_path", "post1_path", "pre2_path", "post2_path", "pre3_path", 
    "post3_path",
]

PATH_LABELS = {
    "profiles_dir": "Overwrite Profile Folders",
    "launchers_dir": "Overwrite Launcher",
    "launcher_executable": "Overwrite Launcher Executable",
    "controller_mapper_path": "Overwrite Controller Mapper",
    "multimonitortool_path": "Overwrite Multi-Monitor Tool",
    "just_after_launch_path": "Overwrite Just After Launch",
    "just_before_exit_path": "Overwrite Just Before Exit",
    "p1_profile_path": "Overwrite Player 1 Profile",
    "p2_profile_path": "Overwrite Player 2 Profile",
    "mediacenter_profile_path": "Overwrite Media Center Profile",
    "multimonitor_gaming_path": "Overwrite MM Gaming Config",
    "multimonitor_media_path": "Overwrite MM Media Config",
    "pre1_path": "Overwrite Pre-Launch App 1",
    "post1_path": "Overwrite Post-Launch App 1",
    "pre2_path": "Overwrite Pre-Launch App 2",
    "post2_path": "Overwrite Post-Launch App 2",
    "pre3_path": "Overwrite Pre-Launch App 3",
    "post3_path": "Overwrite Post-Launch App 3",
}

class LogViewerDialog(QDialog):
    """Modal dialog to display process logs."""
    def __init__(self, text, parent=None, clear_callback=None):
        super().__init__(parent)
        self.setWindowTitle("Process Log")
        self.resize(600, 400)
        self.clear_callback = clear_callback
        
        layout = QVBoxLayout(self)
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setHtml(text)
        layout.addWidget(self.text_edit)
        
        # Buttons Layout
        btn_layout = QHBoxLayout()
        
        save_btn = QPushButton("Save")
        save_btn.clicked.connect(self.save_log)
        btn_layout.addWidget(save_btn)
        
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(self.clear_log)
        btn_layout.addWidget(clear_btn)
        
        btn_layout.addStretch()
        
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)
        
        layout.addLayout(btn_layout)

    def append_text(self, text):
        self.text_edit.append(text)

    def save_log(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "Save Log", "", "Text Files (*.txt);;All Files (*)")
        if file_path:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(self.text_edit.toPlainText())
            except Exception as e:
                pass

    def clear_log(self):
        self.text_edit.clear()
        if self.clear_callback:
            self.clear_callback()

class DeploymentTab(QWidget):
    """A QWidget that encapsulates all UI and logic for the Deployment tab."""

    config_changed = pyqtSignal()
    index_sources_requested = pyqtSignal()
    cancel_indexing_requested = pyqtSignal()
    create_selected_requested = pyqtSignal()
    download_steam_json_requested = pyqtSignal(int)
    delete_steam_json_requested = pyqtSignal()
    delete_steam_cache_requested = pyqtSignal()
    process_steam_json_requested = pyqtSignal()
    
    def __init__(self, main_window):
        super().__init__(main_window)
        self.main_window = main_window
        self.overwrite_checkboxes = {}
        self.is_indexing = False
        self.log_buffer = []
        self.current_log_dialog = None
        self._populate_ui()

    def _populate_ui(self):
        """Create and arrange all widgets for the Deployment tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- General Options Section ---
        # Renamed to Database Indexing and split into 2 columns
        database_indexing_widget = QWidget()
        database_indexing_layout = QHBoxLayout(database_indexing_widget)

        # --- Left Column: Acquisition & File Handling ---
        left_col = QWidget()
        left_layout = QVBoxLayout(left_col)
        left_layout.setContentsMargins(0, 0, 0, 0)

        # Steam update action
        steam_actions_layout = QHBoxLayout()
        self.update_steam_button = QPushButton("Update")
        self.update_steam_button.setToolTip("Check for a newer Steam database and rebuild the caches if needed")
        self.update_steam_button.setMinimumHeight(30)
        steam_actions_layout.addWidget(self.update_steam_button)
        steam_actions_layout.addStretch()
        left_layout.addLayout(steam_actions_layout)

        # Steam Status Textbox (removed refresh button - now in menu)
        self.steam_status_textbox = QTextEdit()
        self.steam_status_textbox.setReadOnly(True)
        self.steam_status_textbox.setFixedHeight(65)
        left_layout.addWidget(self.steam_status_textbox)
        
        left_layout.addStretch()

        # --- Right Column: Deployment Options ---
        right_col = QWidget()
        right_layout = QVBoxLayout(right_col)
        right_layout.setContentsMargins(0, 0, 0, 0)

        # Enable Steam Name Matching
        self.name_check_checkbox = QCheckBox("Enable Steam Name Matching")
        self.name_check_checkbox.setToolTip("Attempt to match indexed games with Steam titles for better naming. Requires steam.json.")
        right_layout.addWidget(self.name_check_checkbox)

        self.auto_flag_checkbox = QCheckBox("Demote current library")
        self.auto_flag_checkbox.setToolTip("Flag items as 'Do not create' if profile folder exists")
        right_layout.addWidget(self.auto_flag_checkbox, alignment=Qt.AlignmentFlag.AlignRight)
        
        self.indexing_progress = QProgressBar()
        self.indexing_progress.setRange(0, 0) # Indeterminate
        self.indexing_progress.setVisible(False)

        self.index_sources_button = QPushButton("INDEX SOURCES")
        self.index_sources_button.clicked.connect(self.index_sources_requested.emit)
        self.index_sources_button.setMinimumHeight(40)

        self.view_log_button = QPushButton("Log")
        self.view_log_button.clicked.connect(self.show_log_viewer)

        right_layout.addWidget(self.index_sources_button)
        right_layout.addWidget(self.indexing_progress)
        right_layout.addStretch()

        # Add columns to main layout
        database_indexing_layout.addWidget(left_col, 1)
        database_indexing_layout.addWidget(right_col, 1)

        # --- Creation Options Section ---
        creation_options_widget = QWidget()
        creation_options_layout = QVBoxLayout(creation_options_widget)

        # Consolidated creation options group
        creation_group = QGroupBox("Creation Options ▼")
        creation_group_layout = QVBoxLayout(creation_group)

        # Scroll area for all checkboxes
        options_scroll = QScrollArea()
        options_scroll.setWidgetResizable(True)
        options_widget = QWidget()
        options_layout = QVBoxLayout(options_widget)

        # Metadata & Artwork Options
        meta_group = QGroupBox("Metadata & Artwork ▼")
        meta_layout = QGridLayout(meta_group)

        self.download_game_json_checkbox = QCheckBox("Download Steam's Game.json")
        self.download_game_json_checkbox.setToolTip("If checked, attempts to download game metadata from Steam using the Steam ID during creation.")

        self.download_pcgw_checkbox = QCheckBox("Download PcGamingWiki")

        self.download_artwork_checkbox = QCheckBox("Download Artwork")
        self.download_artwork_checkbox.setToolTip("Downloads header and background images to the profile folder.")

        # Layout the checkboxes
        meta_layout.addWidget(self.download_game_json_checkbox, 0, 0)
        meta_layout.addWidget(self.download_pcgw_checkbox, 1, 0)
        meta_layout.addWidget(self.download_artwork_checkbox, 2, 0)

        options_layout.addWidget(meta_group)

        # Overwrite checkboxes for all items in a grid
        overwrite_group = QGroupBox("File Overwrite Options ▼")
        overwrite_group.setToolTip("Right-click for bulk options")
        overwrite_group.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        overwrite_group.customContextMenuRequested.connect(self.on_overwrite_options_context_menu)

        overwrite_layout = QGridLayout(overwrite_group)
        overwrite_layout.setContentsMargins(5, 5, 5, 5)

        # Added specific metadata overwrite checkboxes to this group
        self.overwrite_game_json_checkbox = QCheckBox("Overwrite Game.json")
        self.overwrite_pcgw_checkbox = QCheckBox("Overwrite PcGamingWiki")
        self.overwrite_artwork_checkbox = QCheckBox("Overwrite Artwork")

        for i, key in enumerate(PATH_KEYS):
            label = PATH_LABELS.get(key, f"Overwrite {key}")
            cb = QCheckBox(f"{label}")
            # Only check by default for profiles_dir and launchers_dir
            if key in ["profiles_dir", "launchers_dir"]:
                cb.setChecked(True)
            else:
                cb.setChecked(False)
            cb.stateChanged.connect(self.config_changed.emit)
            self.overwrite_checkboxes[key] = cb
            overwrite_layout.addWidget(cb, i // 2, i % 2)
            
        # Append metadata overwrites to the end of the grid
        overwrite_layout.addWidget(self.overwrite_game_json_checkbox, (len(PATH_KEYS) + 1) // 2, 0)
        overwrite_layout.addWidget(self.overwrite_pcgw_checkbox, (len(PATH_KEYS) + 1) // 2, 1)
        overwrite_layout.addWidget(self.overwrite_artwork_checkbox, (len(PATH_KEYS) + 3) // 2, 0)

        options_layout.addWidget(overwrite_group)
        options_layout.addStretch()

        options_scroll.setWidget(options_widget)
        creation_group_layout.addWidget(options_scroll)

        creation_options_layout.addWidget(creation_group)

        # Create button shows dynamic count of selected items
        self.create_button = QPushButton()
        self.create_button.setMinimumHeight(68) # 40px base + 70% increase
        creation_options_layout.addWidget(self.create_button)

        # --- Accordion Setup ---
        # Rename General Options to Database Indexing
        general_options_section = AccordionSection("DATABASE INDEXING", database_indexing_widget, start_expanded=True)
        general_options_section.content_height += 75
        creation_section = AccordionSection("CREATION", creation_options_widget)
        creation_section.content_height += 150

        main_layout.addWidget(general_options_section)
        main_layout.addWidget(creation_section, 1)
        main_layout.addWidget(self.create_button)

        # Bottom-aligned View Log button
        log_btn_layout = QHBoxLayout()
        log_btn_layout.addStretch()
        log_btn_layout.addWidget(self.view_log_button)
        main_layout.addLayout(log_btn_layout)

        # --- Connect Signals ---
        self.name_check_checkbox.stateChanged.connect(self.config_changed.emit)
        self.auto_flag_checkbox.stateChanged.connect(self.config_changed.emit)
        self.download_game_json_checkbox.stateChanged.connect(self.config_changed.emit)
        self.overwrite_game_json_checkbox.stateChanged.connect(self.config_changed.emit)
        self.download_pcgw_checkbox.stateChanged.connect(self.config_changed.emit)
        self.overwrite_pcgw_checkbox.stateChanged.connect(self.config_changed.emit)
        self.download_artwork_checkbox.stateChanged.connect(self.config_changed.emit)
        self.overwrite_artwork_checkbox.stateChanged.connect(self.config_changed.emit)

        self.create_button.clicked.connect(self.create_selected_requested.emit)
        
        self.update_steam_button.clicked.connect(self._on_update_steam_clicked)
        
        # Connect name matching checkbox to update index button state
        self.name_check_checkbox.stateChanged.connect(self._update_index_button_state)
        self.name_check_checkbox.stateChanged.connect(self._on_name_matching_changed)

        # Initialize and connect to editor tab data changes
        self.update_create_button_count()
        self.update_steam_status()

    def on_overwrite_options_context_menu(self, position):
        """Show a context menu for the overwrite options group box."""
        menu = QMenu(self)

        check_all_action = menu.addAction("Check All")
        uncheck_all_action = menu.addAction("Uncheck All")
        toggle_checked_action = menu.addAction("Toggle Checked")
        menu.addSeparator()
        enable_active_action = menu.addAction("Enable Overwrite for Active Options")
        disable_inactive_action = menu.addAction("Disable Overwrite for Inactive Options")

        # The `mapToGlobal` is needed to show the menu at the cursor position
        # The sender() is the overwrite_group QGroupBox
        action = menu.exec(self.sender().mapToGlobal(position))

        if action == check_all_action:
            self._set_all_overwrite_checkboxes(True)
        elif action == uncheck_all_action:
            self._set_all_overwrite_checkboxes(False)
        elif action == toggle_checked_action:
            self._toggle_all_overwrite_checkboxes()
        elif action == enable_active_action:
            self._set_overwrite_for_active_options(True)
        elif action == disable_inactive_action:
            self._set_overwrite_for_active_options(False)

    def _set_all_overwrite_checkboxes(self, checked):
        """Check or uncheck all overwrite checkboxes."""
        for cb in self.overwrite_checkboxes.values():
            cb.setChecked(checked)

    def _toggle_all_overwrite_checkboxes(self):
        """Toggle the state of all overwrite checkboxes."""
        for cb in self.overwrite_checkboxes.values():
            cb.setChecked(not cb.isChecked())

    def _set_overwrite_for_active_options(self, enable_for_active):
        """Enable or disable overwrite checkboxes based on whether their corresponding option in the Setup tab is active."""
        config = self.main_window.config
        for key, cb in self.overwrite_checkboxes.items():
            is_active = False
            path_value = getattr(config, key, "")
            enabled_key = f"{key}_enabled"
            is_enabled = True if key == "launcher_executable" else config.defaults.get(enabled_key, True)
            is_active = is_enabled if key in ["profiles_dir", "launchers_dir"] else bool(path_value) and is_enabled
            if enable_for_active and is_active:
                cb.setChecked(True)
            elif not enable_for_active and not is_active:
                cb.setChecked(False)

    def set_indexing_state(self, active):
        """Update UI state based on indexing status."""
        self.is_indexing = active
        self.indexing_progress.setVisible(active)
        if active:
            self.index_sources_button.setText("CANCEL")
        else:
            self.index_sources_button.setText("INDEX SOURCES")

    def show_log_viewer(self):
        """Open the modal log viewer dialog."""
        log_text = "<br>".join(self.log_buffer)
        self.current_log_dialog = LogViewerDialog(log_text, self, clear_callback=self.clear_log_buffer)
        self.current_log_dialog.exec()
        self.current_log_dialog = None

    def clear_log_buffer(self):
        self.log_buffer = []

    def append_log_message(self, message, timeout=0):
        """Append a message to the log buffer and update dialog if open."""
        # timeout arg is accepted to be compatible with status_updated signal signature (str, int)
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        
        if "error" in message.lower() or "failed" in message.lower():
            entry = f'<font color="red">[{timestamp}] {message}</font>'
        else:
            entry = f"[{timestamp}] {message}"
            
        self.log_buffer.append(entry)
        if self.current_log_dialog and self.current_log_dialog.isVisible():
            self.current_log_dialog.append_text(entry)

    def update_create_button_count(self):
        """Update the create button text with the number of items marked for creation."""
        count = 0
        try:
            if hasattr(self.main_window, 'editor_tab'):
                count = self.main_window.editor_tab.get_create_count()
        except Exception:
            pass
        self.create_button.setText(f"CREATE {count} ITEMS")
        self.create_button.setEnabled(count > 0)

    def update_steam_status(self):
        """Update the status textbox for Steam files."""
        files = [
            ("steam.json", constants.STEAM_JSON_FILE),
            ("steam_filtered.txt", os.path.join(constants.APP_ROOT_DIR, "steam_filtered.txt")),
            ("normalized_steam_games.cache", os.path.join(constants.APP_ROOT_DIR, "normalized_steam_games.cache"))
        ]
        
        status_parts = []
        alert = False
        
        for name, path in files:
            if os.path.exists(path):
                size = os.path.getsize(path)
                mtime = os.path.getmtime(path)
                date_str = datetime.datetime.fromtimestamp(mtime).strftime('%y/%m/%d %H:%M')
                
                size_str = f"{size/1024:.1f}KB"
                if size > 1024*1024:
                    size_str = f"{size/(1024*1024):.2f}MB"
                
                status_parts.append(f"{name}: {size_str} ({date_str})")
                
                if size < 500 * 1024: # 500k
                    alert = True
            else:
                status_parts.append(f"{name}: MISSING")
                alert = True
        
        self.steam_status_textbox.setText("\n".join(status_parts))
        
        # Update index button state after status update
        self._update_index_button_state()
    
    def _update_index_button_state(self):
        """Enable/disable index button based on Steam matching state and cache availability."""
        if not self.name_check_checkbox.isChecked():
            # Steam matching disabled, always enable index button
            self.index_sources_button.setEnabled(True)
            return
        
        # Steam matching enabled, check for required cache files
        filtered_path = os.path.join(constants.APP_ROOT_DIR, "steam_filtered.txt")
        normalized_path = os.path.join(constants.APP_ROOT_DIR, "normalized_steam_games.cache")
        
        caches_exist = os.path.exists(filtered_path) and os.path.exists(normalized_path)
        self.index_sources_button.setEnabled(caches_exist)
        
        if not caches_exist and self.name_check_checkbox.isChecked():
            self.index_sources_button.setToolTip("Steam caches missing. Process steam.json first.")
        else:
            self.index_sources_button.setToolTip("Index game sources")
    
    def _on_name_matching_changed(self, state):
        """Handle changes to Steam Name Matching checkbox."""
        if not self.name_check_checkbox.isChecked():
            # When disabled, uncheck the download checkboxes
            self.download_game_json_checkbox.setChecked(False)
            self.download_pcgw_checkbox.setChecked(False)
            self.download_artwork_checkbox.setChecked(False)

    def update_overwrite_checkboxes(self, config: AppConfig, specific_key: str = None):
        """Update overwrite boxes based on propagation mode and path status."""
        self.blockSignals(True)
        
        keys_to_update = [specific_key] if specific_key else self.overwrite_checkboxes.keys()
        
        for key in keys_to_update:
            if key not in self.overwrite_checkboxes:
                continue
            cb = self.overwrite_checkboxes[key]
            # Check if path is empty
            path_val = getattr(config, key, "")
            
            # Check if enabled (if applicable)
            enabled_key = f"{key}_enabled"
            is_enabled = config.defaults.get(enabled_key, True)
            
            # Check propagation mode
            mode = config.deployment_path_modes.get(key, "CEN")
            
            # If path is empty or explicitly disabled, uncheck overwrite
            if not path_val or not is_enabled:
                cb.setChecked(False)
                config.overwrite_states[key] = False
            elif mode == "LC":
                # When mode is LC, check the overwrite box
                cb.setChecked(True)
                config.overwrite_states[key] = True
            elif key in ["profiles_dir", "launchers_dir"]:
                # Keep profiles_dir and launchers_dir checked by default
                cb.setChecked(True)
                config.overwrite_states[key] = True
            else:
                # For CEN mode, uncheck unless it's a default-checked item
                cb.setChecked(False)
                config.overwrite_states[key] = False
        self.blockSignals(False)

    def _on_update_steam_clicked(self):
        """Trigger the Steam update workflow."""
        self.download_steam_json_requested.emit(2)

    def highlight_unpopulated_items(self, main_window):
        """Highlight enable checkboxes in red if their corresponding setup items are not populated."""
        pass

    def sync_ui_from_config(self, config: AppConfig):
        """Updates the UI widgets with values from the AppConfig model."""
        self.blockSignals(True)

        self.name_check_checkbox.setChecked(config.enable_name_matching)
        self.auto_flag_checkbox.setChecked(config.auto_flag_existing)

        self.download_game_json_checkbox.setChecked(config.download_game_json)
        self.overwrite_game_json_checkbox.setChecked(config.overwrite_game_json)
        self.download_pcgw_checkbox.setChecked(config.download_pcgw_metadata)
        self.overwrite_pcgw_checkbox.setChecked(config.overwrite_pcgw_metadata)
        self.download_artwork_checkbox.setChecked(config.download_artwork)
        self.overwrite_artwork_checkbox.setChecked(config.overwrite_artwork)
        
        # Sync overwrite checkboxes with proper defaults
        for key, cb in self.overwrite_checkboxes.items():
            # Get the mode for this key
            mode = config.deployment_path_modes.get(key, "CEN")
            # Default to checked only for profiles_dir and launchers_dir, or when mode is LC
            if key in ["profiles_dir", "launchers_dir"]:
                default_state = True
            elif mode == "LC":
                default_state = True
            else:
                default_state = False
            cb.setChecked(config.overwrite_states.get(key, default_state))

        self.blockSignals(False)

    def sync_config_from_ui(self, config: AppConfig):
        """Updates the AppConfig model with values from the UI widgets."""
        config.enable_name_matching = self.name_check_checkbox.isChecked()
        config.auto_flag_existing = self.auto_flag_checkbox.isChecked()

        config.download_game_json = self.download_game_json_checkbox.isChecked()
        config.overwrite_game_json = self.overwrite_game_json_checkbox.isChecked()
        config.download_pcgw_metadata = self.download_pcgw_checkbox.isChecked()
        config.overwrite_pcgw_metadata = self.overwrite_pcgw_checkbox.isChecked()
        config.download_artwork = self.download_artwork_checkbox.isChecked()
        config.overwrite_artwork = self.overwrite_artwork_checkbox.isChecked()
        
        # Sync overwrite states
        for key, cb in self.overwrite_checkboxes.items():
            config.overwrite_states[key] = cb.isChecked()
