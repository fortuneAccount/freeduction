from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, QLabel,
    QPushButton, QHeaderView, QAbstractItemView, QMenu, QCheckBox, QLineEdit,
    QApplication, QFileDialog, QInputDialog, QMessageBox, QSpinBox, QDialog,
    QDialogButtonBox, QComboBox, QProgressDialog, QSizePolicy, QListWidget,
    QListWidgetItem, QProgressBar
)
import os
import json 
import configparser
import copy
import collections
import re
import difflib
import datetime
from PyQt6.QtCore import Qt, pyqtSignal, QItemSelectionModel
from PyQt6.QtGui import QColor, QBrush, QFont
from Python import constants
from Python.managers.index_manager import backup_index

class AppendKillListDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Append to Kill List")
        self.setModal(True)
        self.resize(400, 150)
        layout = QVBoxLayout(self)
        
        layout.addWidget(QLabel("Enter executable name (e.g. notepad.exe) or variable:"))
        
        input_layout = QHBoxLayout()
        self.input_edit = QLineEdit()
        browse_btn = QPushButton("...")
        browse_btn.setMaximumWidth(40)
        browse_btn.clicked.connect(self.browse_file)
        
        input_layout.addWidget(self.input_edit)
        input_layout.addWidget(browse_btn)
        layout.addLayout(input_layout)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def browse_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Executable", "", "Executables (*.exe);;All Files (*)")
        if file_path:
            self.input_edit.setText(os.path.basename(file_path))

    def get_value(self):
        return self.input_edit.text().strip()

class RemoveProfilesDialog(QDialog):
    """Modal dialog to select existing profile folders for removal from index."""
    def __init__(self, profiles_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Cleanup Existing Profiles")
        self.setModal(True)
        self.resize(450, 500)
        
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Profiles Directory: {profiles_dir}"))
        layout.addWidget(QLabel("Select folders to REMOVE from the current editor index:"))

        # Search and Sort Row
        filter_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Filter folders...")
        self.search_edit.textChanged.connect(self.refresh_list)
        
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(["Name (A-Z)", "Name (Z-A)", "Newest First", "Oldest First"])
        self.sort_combo.currentIndexChanged.connect(self.refresh_list)
        
        filter_layout.addWidget(self.search_edit, 3)
        filter_layout.addWidget(QLabel("Sort:"))
        filter_layout.addWidget(self.sort_combo, 2)
        layout.addLayout(filter_layout)

        self.list_widget = QListWidget()
        self.folder_data = []
        if os.path.exists(profiles_dir):
            try:
                for f in os.scandir(profiles_dir):
                    if f.is_dir():
                        self.folder_data.append({'name': f.name, 'mtime': f.stat().st_mtime})
            except Exception: pass
        
        layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        sel_all = QPushButton("Select All")
        sel_all.clicked.connect(lambda: [item.setCheckState(Qt.CheckState.Checked) for i in range(self.list_widget.count()) if (item := self.list_widget.item(i))])
        sel_filtered = QPushButton("Select All Filtered")
        sel_filtered.setToolTip("Only visible items in the current list are affected.")
        sel_filtered.clicked.connect(self.select_all_filtered)
        sel_none = QPushButton("Select None")
        sel_none.clicked.connect(lambda: [item.setCheckState(Qt.CheckState.Unchecked) for i in range(self.list_widget.count()) if (item := self.list_widget.item(i))])
        btn_layout.addWidget(sel_all)
        btn_layout.addWidget(sel_filtered)
        btn_layout.addWidget(sel_none)
        layout.addLayout(btn_layout)
        
        self.delete_physical_checkbox = QCheckBox("Also delete physical profile folders from disk")
        self.delete_physical_checkbox.setChecked(False)
        layout.addWidget(self.delete_physical_checkbox)

        self.refresh_list()

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    def get_selected_folders(self):
        return [item.text() for i in range(self.list_widget.count()) if (item := self.list_widget.item(i)) and item.checkState() == Qt.CheckState.Checked]
    
    def get_delete_physical_state(self):
        return self.delete_physical_checkbox.isChecked()

    def refresh_list(self):
        checked_names = set()
        for i in range(self.list_widget.count()):
            if (it := self.list_widget.item(i)) and it.checkState() == Qt.CheckState.Checked:
                checked_names.add(it.text())

        search_text = self.search_edit.text().lower()
        sort_mode = self.sort_combo.currentIndex()
        
        if sort_mode == 0: self.folder_data.sort(key=lambda x: x['name'].lower())
        elif sort_mode == 1: self.folder_data.sort(key=lambda x: x['name'].lower(), reverse=True)
        elif sort_mode == 2: self.folder_data.sort(key=lambda x: x['mtime'], reverse=True)
        elif sort_mode == 3: self.folder_data.sort(key=lambda x: x['mtime'])

        self.list_widget.clear()
        for folder in self.folder_data:
            name = folder['name']
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if name in checked_names else Qt.CheckState.Unchecked)
            if search_text not in name.lower():
                item.setHidden(True)
            self.list_widget.addItem(item)

    def select_all_filtered(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            if not item.isHidden():
                item.setCheckState(Qt.CheckState.Checked)

class EditorTab(QWidget):
    """Encapsulates the UI and logic for the Editor tab."""

    save_index_requested = pyqtSignal()
    load_index_requested = pyqtSignal()
    delete_indexes_requested = pyqtSignal()
    clear_view_requested = pyqtSignal()
    data_changed = pyqtSignal()

    # Maps setup_tab config_key → (game_data_options_key, game_data_arguments_key)
    CONFIG_KEY_TO_GAME_DATA = {
        'controller_mapper_path': ('controller_mapper_options', 'controller_mapper_arguments'),
        'borderless_gaming_path': ('borderless_windowing_options', 'borderless_windowing_arguments'),
        'monitorapp_path': ('monitorapp_options', 'monitorapp_arguments'),
        'just_after_launch_path': ('just_after_launch_options', 'just_after_launch_arguments'),
        'just_before_exit_path': ('just_before_exit_options', 'just_before_exit_arguments'),
        'pre1_path': ('pre1_options', 'pre1_arguments'),
        'pre2_path': ('pre2_options', 'pre2_arguments'),
        'pre3_path': ('pre3_options', 'pre3_arguments'),
        'post1_path': ('post1_options', 'post1_arguments'),
        'post2_path': ('post2_options', 'post2_arguments'),
        'post3_path': ('post3_options', 'post3_arguments'),
        'p1_profile_path': ('player1_profile_options', 'player1_profile_arguments'),
        'p2_profile_path': ('player2_profile_options', 'player2_profile_arguments'),
        'desk_profile_path': ('desk_profile_options', 'desk_profile_arguments'),
        'monitor_game_path': ('monitor_game_cfg_options', 'monitor_game_cfg_arguments'),
        'monitor_desk_path': ('monitor_desk_cfg_options', 'monitor_desk_cfg_arguments'),
        'launcher_executable': ('launcher_executable_options', 'launcher_executable_arguments'),
        'disc_mount_path': ('disc_mount_options', 'disc_mount_arguments'),
        'disc_mount_cfg': ('disc_mount_cfg_options', 'disc_mount_cfg_arguments'),
        'disc_unmount_cfg': ('disc_unmount_cfg_options', 'disc_unmount_cfg_arguments'),
        'audio_tool_path': ('audio_app_options', 'audio_app_arguments'),
        'audio_game_cfg': ('audio_game_cfg_options', 'audio_game_cfg_arguments'),
        'audio_desk_cfg': ('audio_desk_cfg_options', 'audio_desk_cfg_arguments'),
        'unborder_cfg': ('unborder_cfg_options', 'unborder_cfg_arguments'),
        'reborder_cfg': ('reborder_cfg_options', 'reborder_cfg_arguments'),
    }

    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.table = None
        self.original_data = []
        self.filtered_data = []
        self._enabled_tools = set()
        self.current_page = 0
        self.page_size = self.main_window.config.editor_page_size
        self.undo_stack = []
        self.is_dirty = False
        self.populate_ui()

    def populate_ui(self):
        """Create and arrange widgets for the editor tab."""
        main_layout = QVBoxLayout(self)

        # --- Search Bar ---
        search_layout = QHBoxLayout()
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search games by name...")
        self.search_bar.textChanged.connect(self.filter_table)
        search_layout.addWidget(QLabel("Search:"))
        search_layout.addWidget(self.search_bar)
        
        # Add Game Button
        self.add_game_button = QPushButton("Add Game")
        self.add_game_button.clicked.connect(self.add_game_manually)
        search_layout.addWidget(self.add_game_button)
        main_layout.addLayout(search_layout)

        # --- Tools Row (Above Table) ---
        tools_layout = QHBoxLayout()
        
        self.remove_unchecked_btn = QPushButton("Remove Unchecked")
        self.remove_unchecked_btn.clicked.connect(self.remove_unchecked_items)

        # Select Flyout
        self.select_flyout_btn = QPushButton("Select By... ▼")
        self.select_flyout_menu = QMenu(self)
        self.select_flyout_menu.addAction("Empty Steam ID", lambda: self.select_by_criteria("empty_steamid"))
        self.select_flyout_menu.addAction("Empty Kill List", lambda: self.select_by_criteria("empty_killlist"))
        self.select_flyout_menu.addAction("Invalid/Absent Paths", lambda: self.select_by_criteria("invalid_paths"))
        self.select_flyout_menu.addAction("Large File LC (>10MB)", lambda: self.select_by_criteria("large_lc"))
        self.select_flyout_menu.addAction("By File Name...", lambda: self.select_by_criteria("by_filename"))
        self.select_flyout_btn.setMenu(self.select_flyout_menu)

        # Change Flyout
        self.change_flyout_btn = QPushButton("Change Selected... ▼")
        self.change_flyout_menu = QMenu(self)
        self.change_flyout_menu.addAction("Swap LC/CEN Type", self.swap_lc_cen_selected)
        self.change_flyout_menu.addAction("Restore Defaults", self.restore_defaults_selected)
        self.change_flyout_menu.addAction("Toggle Create Status", self.toggle_create_column)
        self.change_flyout_menu.addAction("Bulk Edit", self.open_bulk_edit_dialog)
        self.change_flyout_btn.setMenu(self.change_flyout_menu)

        # Sort Flyout
        self.sort_flyout_btn = QPushButton("Sort By... ▼")
        self.sort_flyout_menu = QMenu(self)
        self.sort_flyout_menu.addAction("Create Status", lambda: self.sort_data('create'))
        self.sort_flyout_menu.addAction("Name", lambda: self.sort_data('name'))
        self.sort_flyout_menu.addAction("Name Override", lambda: self.sort_data('name_override'))
        self.sort_flyout_menu.addAction("Steam ID", lambda: self.sort_data('steam_id'))
        self.sort_flyout_menu.addAction("Kill List", lambda: self.sort_data('kill_list'))
        self.sort_flyout_menu.addAction("ISO Path", lambda: self.sort_data('iso_path'))
        self.sort_flyout_menu.addAction("As Admin Status", lambda: self.sort_data('run_as_admin'))
        self.sort_flyout_menu.addAction("Date Created", lambda: self.sort_data('date_indexed'))
        self.sort_flyout_menu.addAction("Windowing Enabled", lambda: self.sort_data('borderless_windowing_enabled'))
        self.sort_flyout_menu.addAction("Hide Taskbar", lambda: self.sort_data('hide_taskbar'))
        self.sort_flyout_menu.addAction("Duplicate Name-Override", lambda: self.sort_data('_dup_name_override'))
        self.sort_flyout_menu.addAction("Parent Folder", lambda: self.sort_data('_parent_folder'))
        self.sort_flyout_btn.setMenu(self.sort_flyout_menu)

        # Undo Button
        self.undo_button = QPushButton("Undo")
        self.undo_button.setStyleSheet("font-weight: bold;")
        self.undo_button.setEnabled(False)
        self.undo_button.clicked.connect(self.undo)
        
        # Clear View Button
        self.clear_button = QPushButton("Clear View")
        self.clear_button.clicked.connect(self.clear_view_requested.emit)
        
        # Compact View Checkbox
        self.compact_view_cb = QCheckBox("Compact View")
        self.compact_view_cb.stateChanged.connect(self.update_compact_view)

        # Add to layout in order
        # Left aligned
        tools_layout.addWidget(self.sort_flyout_btn)
        tools_layout.addWidget(self.select_flyout_btn)
        tools_layout.addWidget(self.change_flyout_btn)
        
        tools_layout.addStretch()
        
        # Right aligned
        tools_layout.addWidget(self.undo_button, alignment=Qt.AlignmentFlag.AlignCenter)
        tools_layout.addWidget(self.remove_unchecked_btn)
        tools_layout.addWidget(self.clear_button)
        tools_layout.addWidget(self.compact_view_cb)

        main_layout.addLayout(tools_layout)

        # --- Table ---
        self.table = QTableWidget()
        self.table.setColumnCount(max(c.value for c in constants.EditorCols) + 1)
        
        headers = [
            "Create", "Name", "Dir", "SteamID",
            "NameOverride", "opts", "args", "AsAdmin",
            "Overwrite", "Recreate",
            "Launcher Exe",
            "opts", "args",
            "Monitor-App", "opts", "args", "wait",
            "Windowing", "opts", "args", "wait",
            "UnBorder", "opts", "args",
            "ReBorder", "opts", "args",
            "Mon Game Cfg", "opts", "args",
            "Mon Desk Cfg", "opts", "args",
            "Mapper", "opts", "args", "wait",
            "Player 1", "opts", "args",
            "Player 2", "opts", "args",
            "Desk", "opts", "args",
            "JAL", "opts", "args", "wait",
            "JBE", "opts", "args", "wait",
            "Pre1", "opts", "args", "wait",
            "Post1", "opts", "args", "wait",
            "Pre2", "opts", "args", "wait",
            "Post2", "opts", "args", "wait",
            "Pre3", "opts", "args", "wait",
            "Post3", "opts", "args", "wait",
            "Kill List",
            "Exec Order", "Term Order",
            "ISO Path",
            "Disc-Mount", "opts", "args", "wait",
            "Mount-Cfg", "opts", "args",
            "Unmount-Cfg", "opts", "args",
            "Audio-App", "opts", "args", "wait",
            "Audio Game", "opts", "args",
            "Audio D", "opts", "args",
            "Hide TB",
        ]
        self.table.setHorizontalHeaderLabels(headers)

        tooltips = [
            "Include this game in the creation process",
            "Executable name",
            "Game directory",
            "Steam AppID",
            "Display name for the launcher",
            "Additional command-line options for the game executable",
            "Command-line arguments for the game executable",
            "Run game as administrator",
            "Overwrite Game.ini with all GUI values (including blanks)",
            "Recreate Game.ini from scratch, replacing any existing file",
            "Custom launcher executable path (can differ from the game executable)",
            "Options passed to the custom launcher executable",
            "Arguments passed to the custom launcher executable",
            "Path to the Monitor-Config Application (e.g. multimonitortool.exe)",
            "Options passed to the Monitor-Config App",
            "Arguments passed to the Monitor-Config App",
            "Wait for the Monitor-Config tool to finish before continuing",
            "Path to the Borderless Windowing application (e.g. Borderless Gaming)",
            "Options passed to the Borderless Windowing application",
            "Arguments passed to the Borderless Windowing application",
            "Wait for the Borderless Windowing application to finish before continuing",
            "Path to the UnBorder configuration file",
            "Options for the UnBorder configuration file",
            "Arguments for the UnBorder configuration file",
            "Path to the ReBorder configuration file",
            "Options for the ReBorder configuration file",
            "Arguments for the ReBorder configuration file",
            "Config file path for Monitor Game profile",
            "Options passed to the Monitor Game profile",
            "Arguments passed to the Monitor Game profile",
            "Config file path for Monitor Desktop profile",
            "Options passed to the Monitor Desktop profile",
            "Arguments passed to the Monitor Desktop profile",
            "Path to the Controller Mapper application (e.g. AntimicroX)",
            "Options passed to the Controller Mapper application",
            "Arguments passed to the Controller Mapper application",
            "Wait for the Controller Mapper application to finish before continuing",
            "Controller profile path for Player 1",
            "Options passed to the Player 1 controller profile",
            "Arguments passed to the Player 1 controller profile",
            "Controller profile path for Player 2",
            "Options passed to the Player 2 controller profile",
            "Arguments passed to the Player 2 controller profile",
            "Controller profile path for Desk",
            "Options passed to the Desk controller profile",
            "Arguments passed to the Desk controller profile",
            "Path to the application to run immediately after game launch",
            "Options passed to the Just After Launch application",
            "Arguments passed to the Just After Launch application",
            "Wait for the Just After Launch application to finish before continuing",
            "Path to the application to run just before game exits",
            "Options passed to the Just Before Exit application",
            "Arguments passed to the Just Before Exit application",
            "Wait for the Just Before Exit application to finish before continuing",
            "Path to Pre-Launch script/application 1",
            "Options passed to Pre-Launch App 1",
            "Arguments passed to Pre-Launch App 1",
            "Wait for Pre-Launch App 1 to finish before continuing",
            "Path to Post-Launch script/application 1",
            "Options passed to Post-Launch App 1",
            "Arguments passed to Post-Launch App 1",
            "Wait for Post-Launch App 1 to finish before continuing",
            "Path to Pre-Launch script/application 2",
            "Options passed to Pre-Launch App 2",
            "Arguments passed to Pre-Launch App 2",
            "Wait for Pre-Launch App 2 to finish before continuing",
            "Path to Post-Launch script/application 2",
            "Options passed to Post-Launch App 2",
            "Arguments passed to Post-Launch App 2",
            "Wait for Post-Launch App 2 to finish before continuing",
            "Path to Pre-Launch script/application 3",
            "Options passed to Pre-Launch App 3",
            "Arguments passed to Pre-Launch App 3",
            "Wait for Pre-Launch App 3 to finish before continuing",
            "Path to Post-Launch script/application 3",
            "Options passed to Post-Launch App 3",
            "Arguments passed to Post-Launch App 3",
            "Wait for Post-Launch App 3 to finish before continuing",
            "Comma-separated list of processes to kill when game exits (Checked = Enabled)",
            "Execution sequence order string (read-only list of launch sequence items)",
            "Termination sequence order string (read-only list of exit sequence items)",
            "Path to ISO file to mount before game launch",
            "Path to the Disc-Mount application (e.g. imgdrive, WinCDEmu, OSFMount)",
            "Options passed to the Disc-Mount application",
            "Arguments passed to the Disc-Mount application",
            "Wait for the Disc-Mount application to finish before continuing",
            "Path to the Disc-Mount configuration file (.cfg)",
            "Options for the Disc-Mount configuration file",
            "Arguments for the Disc-Mount configuration file",
            "Path to the Disc-Unmount configuration file (.cfg)",
            "Options for the Disc-Unmount configuration file",
            "Arguments for the Disc-Unmount configuration file",
            "Path to the Audio Tool application (e.g. AudioTool.exe)",
            "Options passed to the Audio Tool application",
            "Arguments passed to the Audio Tool application",
            "Wait for the Audio Tool application to finish before continuing",
            "Path to the Audio Game configuration file",
            "Options for the Audio Game configuration file",
            "Arguments for the Audio Game configuration file",
            "Path to the Audio Desk configuration file",
            "Options for the Audio Desk configuration file",
            "Arguments for the Audio Desk configuration file",
            "Hide the Windows Taskbar while the game is running",
        ]
        for i, tooltip in enumerate(tooltips):
            item = self.table.horizontalHeaderItem(i)
            if item:
                item.setToolTip(tooltip)

        # App column indices (path columns for applications) — bold
        app_header_cols = {
            constants.EditorCols.CM_PATH.value,
            constants.EditorCols.BW_PATH.value,
            constants.EditorCols.JA_PATH.value,
            constants.EditorCols.JB_PATH.value,
            constants.EditorCols.PRE1_PATH.value,
            constants.EditorCols.POST1_PATH.value,
            constants.EditorCols.PRE2_PATH.value,
            constants.EditorCols.POST2_PATH.value,
            constants.EditorCols.PRE3_PATH.value,
            constants.EditorCols.POST3_PATH.value,
            constants.EditorCols.LAUNCHER_EXE.value,
            constants.EditorCols.DM_PATH.value,
            constants.EditorCols.AUDIO_APP_PATH.value,
            constants.EditorCols.MONITORAPP_PATH.value,
        }
        base_font = self.table.font()
        italic_font = QFont(base_font)
        italic_font.setItalic(True)
        italic_font.setPointSize(max(1, base_font.pointSize() - 1))
        for i in range(self.table.columnCount()):
            item = self.table.horizontalHeaderItem(i)
            if not item:
                continue
            text = item.text().lower()
            if i in app_header_cols:
                f = QFont(base_font)
                f.setBold(True)
                item.setFont(f)
            elif text in ("opts", "args", "wait"):
                item.setFont(italic_font)

        header = self.table.horizontalHeader()  # type: ignore[assignment]
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # type: ignore[union-attr]

        # Shorten width for Enabled (En) and Run/Wait (Rw) columns to save space
        try:
            rw_columns = [constants.EditorCols.CM_RUN_WAIT.value, constants.EditorCols.BW_RUN_WAIT.value,
                          constants.EditorCols.MONITORAPP_RUN_WAIT.value, constants.EditorCols.AUDIO_APP_RUN_WAIT.value,
                          constants.EditorCols.JA_RUN_WAIT.value,
                          constants.EditorCols.JB_RUN_WAIT.value, constants.EditorCols.PRE1_RUN_WAIT.value,
                          constants.EditorCols.POST1_RUN_WAIT.value, constants.EditorCols.PRE2_RUN_WAIT.value,
                          constants.EditorCols.POST2_RUN_WAIT.value, constants.EditorCols.PRE3_RUN_WAIT.value,
                          constants.EditorCols.POST3_RUN_WAIT.value, constants.EditorCols.DM_RUN_WAIT.value]

            for col in rw_columns:
                # Automatically resize Wait columns to fit content
                header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)  # type: ignore[union-attr]
            
            self.table.setColumnWidth(constants.EditorCols.RUN_AS_ADMIN.value, 60)

            # Reduce width of opts, args, and Directory by 80%
            shrink_cols = [constants.EditorCols.DIRECTORY.value, constants.EditorCols.OPTIONS.value, constants.EditorCols.ARGUMENTS.value]
            for col in shrink_cols:
                self.table.setColumnWidth(col, 40)
            
            # Shrink opts/args/wait columns
            for col in range(self.table.columnCount()):
                if headers[col].lower() in ("opts", "args", "wait"):
                    self.table.setColumnWidth(col, 40)

            # Apply initial plugin-gated column visibility
            self._apply_tool_visibility()
        except Exception:
            pass
        header.setFirstSectionMovable(False)  # type: ignore[union-attr]
        header.setStretchLastSection(False)  # type: ignore[union-attr]
        header.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)  # type: ignore[union-attr]
        header.customContextMenuRequested.connect(self.on_header_context_menu)  # type: ignore[union-attr]
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.AllEditTriggers)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)

        # --- Frozen Create Column ---
        self.frozen_table = QTableWidget()
        self.frozen_table.setColumnCount(1)
        self.frozen_table.setHorizontalHeaderLabels(["Create"])
        self.frozen_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.frozen_table.horizontalHeader().resizeSection(0, 50)
        self.frozen_table.setFixedWidth(52)
        self.frozen_table.verticalHeader().hide()
        self.frozen_table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen_table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.frozen_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.frozen_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.frozen_table.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.frozen_table.verticalScrollBar().setEnabled(False)
        frozen_header_item = self.frozen_table.horizontalHeaderItem(0)
        if frozen_header_item:
            frozen_header_item.setToolTip("Include this game in the creation process")
        self.table.verticalHeader().hide()
        self.frozen_table.setStyleSheet("QTableWidget { border: 1px solid gray; border-right: none; }")
        self.table.setColumnHidden(0, True)
        self.table.verticalScrollBar().valueChanged.connect(
            lambda v: self.frozen_table.verticalScrollBar().setValue(v))
        self.table.verticalHeader().sectionResized.connect(
            lambda idx, old, new: self.frozen_table.setRowHeight(idx, new))

        table_container = QWidget()
        table_layout = QHBoxLayout(table_container)
        table_layout.setContentsMargins(0, 0, 0, 0)
        table_layout.setSpacing(0)
        table_layout.addWidget(self.frozen_table)
        table_layout.addWidget(self.table, 1)

        main_layout.addWidget(table_container, 1)

        # --- Pagination ---
        pagination_layout = QHBoxLayout()
        self.prev_page_button = QPushButton("< Prev")
        self.prev_page_button.clicked.connect(self.prev_page)
        
        self.page_input = QSpinBox()
        self.page_input.setMinimum(1)
        self.page_input.setKeyboardTracking(False)
        self.page_input.valueChanged.connect(self.go_to_page)
        
        self.next_page_button = QPushButton("Next >")
        self.next_page_button.clicked.connect(self.next_page)
        self.page_label = QLabel("of 1")
        pagination_layout.addWidget(self.prev_page_button)
        pagination_layout.addWidget(QLabel("Page:"))
        pagination_layout.addWidget(self.page_input)
        pagination_layout.addWidget(self.page_label)
        pagination_layout.addWidget(self.next_page_button)
        main_layout.addLayout(pagination_layout)

        # --- Buttons ---
        buttons_layout = QHBoxLayout()
        # Index Flyout (Lower Left)
        self.index_flyout_btn = QPushButton("Indexes ▼")
        self.index_flyout_menu = QMenu(self)
        self.index_flyout_menu.addAction("Save Index", self.save_index_requested.emit)
        self.index_flyout_menu.addAction("Load Index", self.load_index_requested.emit)
        self.index_flyout_menu.addAction("Delete Indexes", self.delete_indexes_requested.emit)
        self.index_flyout_btn.setMenu(self.index_flyout_menu)
        buttons_layout.addWidget(self.index_flyout_btn)
        
        # Profiles Flyout
        self.profiles_flyout_btn = QPushButton("Profiles... ▼")
        self.profiles_flyout_menu = QMenu(self)
        
        self.import_profiles_action = self.profiles_flyout_menu.addAction("Import")  # type: ignore[assignment]
        self.import_profiles_action.triggered.connect(self.import_profiles)
        
        self.cleanup_profiles_action = self.profiles_flyout_menu.addAction("Cleanup")  # type: ignore[assignment]
        self.cleanup_profiles_action.triggered.connect(self.remove_items_matching_profiles)
        self.profiles_flyout_btn.setMenu(self.profiles_flyout_menu)
        buttons_layout.addWidget(self.profiles_flyout_btn)
        self.validate_btn = QPushButton("Validate Paths")
        self.validate_btn.clicked.connect(self.validate_paths)
        buttons_layout.addWidget(self.validate_btn)
        
        buttons_layout.addStretch()

        # Editor Page Size (Lower Right)
        buttons_layout.addWidget(QLabel("Page Size:"))
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(1, 2000)
        self.page_size_spin.setValue(self.main_window.config.editor_page_size)
        self.page_size_spin.setToolTip("Number of rows per page in the Editor tab (1-2000)")
        self.page_size_spin.valueChanged.connect(self.update_page_size)
        buttons_layout.addWidget(self.page_size_spin)
        
        main_layout.addLayout(buttons_layout)

        # --- Connect Signals ---
        self.table.customContextMenuRequested.connect(self.on_context_menu)
        self.table.cellClicked.connect(self.on_cell_clicked)
        self.table.itemChanged.connect(self.on_item_changed)

    def showEvent(self, event):  # type: ignore[override]
        super().showEvent(event)
        if self.is_dirty:
            self.refresh_view()

    def push_undo(self):
        """Save current state to undo stack."""
        if len(self.undo_stack) >= 10:
            self.undo_stack.pop(0)
        self.undo_stack.append(copy.deepcopy(self.original_data))
        self.undo_button.setEnabled(True)

    def undo(self):
        """Restore last state."""
        if not self.undo_stack: return
        self.original_data = self.undo_stack.pop()
        self.filter_table(self.search_bar.text())
        self.undo_button.setEnabled(len(self.undo_stack) > 0)
        self.main_window._on_editor_table_edited(None)

    def update_page_size(self, value):
        """Update page size and refresh view."""
        self.page_size = value
        self.main_window.config.editor_page_size = value
        self.main_window.config_manager.save_config(self.main_window.config)
        self.refresh_view()

    def remove_unchecked_items(self):
        """Remove items where 'create' is False."""
        self.push_undo()
        self.original_data = [g for g in self.original_data if g.get('create', False)]
        self.filter_table(self.search_bar.text())
        self.main_window._on_editor_table_edited(None)

    def remove_items_matching_profiles(self):
        """Compare indexed items with physical profile folders and remove matches."""
        profiles_dir = self.main_window.config.profiles_dir
        if not profiles_dir or not os.path.exists(profiles_dir):
            QMessageBox.warning(self, "Profiles Not Found", "Profiles directory is not configured or missing.")
            return

        dialog = RemoveProfilesDialog(profiles_dir, self)
        if dialog.exec():
            selected_folders = set(dialog.get_selected_folders())
            delete_physical = dialog.get_delete_physical_state()
            if not selected_folders: return

            # Confirmation dialog
            confirm = QMessageBox.question(
                self, "Confirm Cleanup",
                f"Are you sure you want to remove all items in the editor's index matching the {len(selected_folders)} selected folders?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if confirm != QMessageBox.StandardButton.Yes:
                return
            
            if delete_physical:
                physical_confirm = QMessageBox.question(
                    self, "Confirm Physical Deletion",
                    f"WARNING: You are about to permanently delete {len(selected_folders)} physical profile folders from '{profiles_dir}'.\nThis action cannot be undone.\n\nAre you absolutely sure you want to proceed?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                if physical_confirm != QMessageBox.StandardButton.Yes:
                    return
                
                # Perform physical deletion
                import shutil
                for folder_name in selected_folders:
                    folder_path = os.path.join(profiles_dir, folder_name)
                    if os.path.exists(folder_path):
                        shutil.rmtree(folder_path)
                        print(f"Deleted physical folder: {folder_path}")

            self.push_undo()
            from Python.ui.name_utils import make_safe_filename
            
            initial_count = len(self.original_data)
            self.original_data = [
                g for g in self.original_data 
                if make_safe_filename(g.get('name_override') or g.get('name') or "") not in selected_folders
            ]
            
            removed = initial_count - len(self.original_data)
            self.filter_table(self.search_bar.text())
            self.main_window._on_editor_table_edited(None)
            QMessageBox.information(self, "Cleanup Complete", f"Removed {removed} items from the index matching selected profile folders.")

    def sort_data(self, key):
        """Sort the game list by the specified key."""
        self.push_undo()

        # Build duplicate name-override counts for the special sort
        if key == '_dup_name_override':
            import collections as _c
            name_counts = _c.Counter(
                g.get('name_override', '').strip().lower()
                for g in self.original_data
                if g.get('name_override', '').strip()
            )
        if key == '_dup_name_override':
            import collections as _c
            _name_counts = _c.Counter(
                g.get('name_override', '').strip().lower()
                for g in self.original_data
                if g.get('name_override', '').strip()
            )
        else:
            _name_counts = None

        def sort_key(item):
            if key == '_dup_name_override' and _name_counts:
                no = item.get('name_override', '').strip().lower()
                count = _name_counts.get(no, 0)
                return (0 if count > 1 else 1, no)
            elif key == '_parent_folder':
                directory = item.get('directory', '')
                parent = os.path.basename(os.path.normpath(directory)).lower() if directory else ''
                return parent
            else:
                val = item.get(key)
                if val is None:
                    return ""
                return str(val).lower()

        # Check if already sorted ascending to toggle
        is_sorted_asc = all(sort_key(self.original_data[i]) <= sort_key(self.original_data[i+1]) for i in range(len(self.original_data)-1))
        
        self.original_data.sort(key=sort_key, reverse=is_sorted_asc)
        
        self.filter_table(self.search_bar.text())
        self.main_window._on_editor_table_edited(None)

    def select_by_criteria(self, criteria):
        """Select rows matching specific criteria."""
        self.table.clearSelection()
        
        path_cols = [
            constants.EditorCols.CM_PATH, constants.EditorCols.BW_PATH,
            constants.EditorCols.UNBORDER_CFG, constants.EditorCols.UNBORDER_CFG_OPTIONS, constants.EditorCols.UNBORDER_CFG_ARGUMENTS,
            constants.EditorCols.REBORDER_CFG, constants.EditorCols.REBORDER_CFG_OPTIONS, constants.EditorCols.REBORDER_CFG_ARGUMENTS,
            constants.EditorCols.MONITOR_GAME_CFG, constants.EditorCols.MONITOR_GAME_CFG_OPTIONS, constants.EditorCols.MONITOR_GAME_CFG_ARGUMENTS,
            constants.EditorCols.MONITOR_DESK_CFG, constants.EditorCols.MONITOR_DESK_CFG_OPTIONS, constants.EditorCols.MONITOR_DESK_CFG_ARGUMENTS,
            constants.EditorCols.PLAYER1_PROFILE, constants.EditorCols.PLAYER1_PROFILE_OPTIONS, constants.EditorCols.PLAYER1_PROFILE_ARGUMENTS,
            constants.EditorCols.PLAYER2_PROFILE, constants.EditorCols.PLAYER2_PROFILE_OPTIONS, constants.EditorCols.PLAYER2_PROFILE_ARGUMENTS,
            constants.EditorCols.DESK_PROFILE, constants.EditorCols.DESK_PROFILE_OPTIONS, constants.EditorCols.DESK_PROFILE_ARGUMENTS,
            constants.EditorCols.JA_PATH, constants.EditorCols.JB_PATH,
            constants.EditorCols.PRE1_PATH, constants.EditorCols.POST1_PATH,
            constants.EditorCols.PRE2_PATH, constants.EditorCols.POST2_PATH,
            constants.EditorCols.PRE3_PATH, constants.EditorCols.POST3_PATH,
            constants.EditorCols.LAUNCHER_EXE,
            constants.EditorCols.ISO_PATH,
            constants.EditorCols.DM_MOUNT_CFG, constants.EditorCols.DM_UNMOUNT_CFG,
            constants.EditorCols.AUDIO_APP_PATH,
            constants.EditorCols.MONITORAPP_PATH
        ]
 
        # For "by_filename", prompt the user for a substring before iterating
        filename_filter = None
        if criteria == "by_filename":
            text, ok = QInputDialog.getText(self, "Select by File Name", "Enter filename substring (case-insensitive):")
            if not ok or not text.strip():
                return
            filename_filter = text.strip().lower()

        for row in range(self.table.rowCount()):
            real_index = (self.current_page * self.page_size) + row
            if real_index >= len(self.filtered_data): continue
            game = self.filtered_data[real_index]
            
            match = False
            if criteria == "empty_steamid":
                sid = str(game.get('steam_id', ''))
                if not sid or sid == 'NOT_FOUND_IN_DATA': match = True
            elif criteria == "empty_killlist":
                if not game.get('kill_list', '').strip(): match = True
            elif criteria == "invalid_paths":
                # Check logic similar to validate_paths
                for col_enum in path_cols:
                    widget = self.table.cellWidget(row, col_enum.value)
                    if widget:
                        le = widget.findChild(QLineEdit)
                        path = le.text().strip() if le else ""
                        clean_path = path[2:] if path.startswith("> ") or path.startswith("< ") else path
                        if clean_path and not os.path.exists(clean_path):
                            match = True; break
            elif criteria == "large_lc":
                for col_enum in path_cols:
                    widget = self.table.cellWidget(row, col_enum.value)
                    if widget and self._check_widget_large_lc(widget):
                        match = True; break
            elif criteria == "by_filename" and filename_filter is not None:
                game_name = game.get('name', '').lower()
                name_override = game.get('name_override', '').lower()
                if filename_filter in game_name or filename_filter in name_override:
                    match = True
            
            if match:
                self.table.selectRow(row)

    def update_from_config(self):
        """Update settings from main window config."""
        self.page_size = self.main_window.config.editor_page_size
        if hasattr(self, 'page_size_spin'):
            self.page_size_spin.blockSignals(True)
            self.page_size_spin.setValue(self.page_size)
            self.page_size_spin.blockSignals(False)
        self.refresh_view()

    def propagate_config_options(self, config_key, options, arguments):
        """Propagate non-blank config options/arguments to all game entries in original_data."""
        mapping = self.CONFIG_KEY_TO_GAME_DATA.get(config_key)
        if not mapping:
            return
        game_opts_key, game_args_key = mapping
        for game in self.original_data:
            if options:
                game[game_opts_key] = options
            if arguments:
                game[game_args_key] = arguments
        self.refresh_view()

    def prev_page(self):
        if self.current_page > 0:
            self.current_page -= 1
            self.refresh_view()

    def next_page(self):
        max_page = max(0, (len(self.filtered_data) - 1) // self.page_size)
        if self.current_page < max_page:
            self.current_page += 1
            self.refresh_view()

    def go_to_page(self, value):
        new_page = value - 1
        max_page = max(0, (len(self.filtered_data) - 1) // self.page_size)
        if 0 <= new_page <= max_page:
            self.current_page = new_page
            self.refresh_view()
            self.page_input.setValue(self.current_page + 1)

    def refresh_view(self):
        """Refresh the table to show the current page of data."""
        if not self.isVisible():
            self.is_dirty = True
            self.data_changed.emit()
            return

        self.is_dirty = False
        self.table.setUpdatesEnabled(False)
        self.table.blockSignals(True)
        self.frozen_table.setUpdatesEnabled(False)
        self.frozen_table.blockSignals(True)
        self.table.setRowCount(0)
        self.frozen_table.setRowCount(0)
        
        # Calculate duplicates for styling
        all_names = [g.get('name_override', '').strip() for g in self.original_data if g.get('name_override', '').strip() and g.get('create', False)]
        counts = collections.Counter(all_names)
        duplicates = {name for name, count in counts.items() if count > 1}
        
        start_index = self.current_page * self.page_size
        end_index = min(start_index + self.page_size, len(self.filtered_data))
        
        for i in range(start_index, end_index):
            row_num = self.table.rowCount()
            self.table.insertRow(row_num)
            self.frozen_table.insertRow(row_num)
            self._populate_row(row_num, self.filtered_data[i], duplicates)
            
        self.frozen_table.blockSignals(False)
        self.frozen_table.setUpdatesEnabled(True)
        self.table.blockSignals(False)
        self.table.setUpdatesEnabled(True)
        
        # Update pagination controls
        total_pages = max(1, (len(self.filtered_data) + self.page_size - 1) // self.page_size)
        
        self.page_input.blockSignals(True)
        self.page_input.setMaximum(total_pages)
        self.page_input.setValue(self.current_page + 1)
        self.page_input.blockSignals(False)
        
        self.page_label.setText(f"of {total_pages} (Total: {len(self.filtered_data)}) <font color='green'>{end_index - start_index}</font>")
        self.page_label.setText(f"of {total_pages} (Total: {len(self.original_data)}) <font color='green'>{len(self.filtered_data)}</font>")
        self.prev_page_button.setEnabled(self.current_page > 0)
        self.next_page_button.setEnabled(self.current_page < total_pages - 1)
        self.data_changed.emit()
        self.update_compact_view()

    def filter_table(self, text):
        """Filter table rows based on game name."""
        text = text.lower()
        if not text:
            self.filtered_data = self.original_data
        else:
            self.filtered_data = [g for g in self.original_data if text in g.get('name', '').lower() or text in g.get('name_override', '').lower()]
        
        self.current_page = 0
        self.refresh_view()

    def toggle_create_column(self):
        """Swap the 'create' status for selected rows."""
        self.push_undo()
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        if not selected_rows:
            return

        for row in selected_rows:
            real_index = (self.current_page * self.page_size) + row
            if real_index < len(self.filtered_data):
                new_state = not self.filtered_data[real_index].get('create', False)
                self.filtered_data[real_index]['create'] = new_state
                self._update_widget_state(row, constants.EditorCols.INCLUDE.value, new_state)
                self._apply_styling(row, self.filtered_data[real_index], set())
                self._apply_styling(row, self.filtered_data[real_index])
        self.data_changed.emit()

    def add_game_manually(self):
        """Open file dialog to add a game manually."""
        self.push_undo()
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Game Executable", "", "Executables (*.exe);;All Files (*)"
        )
        if not file_path:
            return

        # Normalize path to use forward slashes
        file_path = file_path.replace('\\', '/')
        filename = os.path.basename(file_path)
        directory = os.path.dirname(file_path)
        
        # Default values
        name_override = os.path.splitext(filename)[0]
        steam_id = 'NOT_FOUND_IN_DATA'

        # Attempt to detect Steam AppID
        try:
            from Python.ui.name_processor import NameProcessor
            from Python.ui.name_utils import replace_illegal_chars

            # Ensure steam index is loaded
            if not self.main_window.steam_cache_manager.normalized_steam_index:
                self.main_window.steam_cache_manager.load_normalized_steam_index()

            # Initialize NameProcessor
            release_groups = getattr(self.main_window, 'release_groups_set', set())
            exclude_exe = getattr(self.main_window, 'exclude_exe_set', set())
            name_processor = NameProcessor(release_groups, exclude_exe)

            # Process name
            clean_name = name_processor.get_display_name(name_override)
            match_name = name_processor.get_match_name(clean_name)
            
            # Lookup
            if self.main_window.config.enable_name_matching:
                match_data = self.main_window.steam_cache_manager.normalized_steam_index.get(match_name)
                if match_data:
                    steam_name = match_data.get("name", "")
                    found_id = match_data.get("id", "")
                    
                    if found_id:
                        steam_id = found_id
                    
                    if steam_name:
                        # Clean steam name for override
                        clean_steam_name = replace_illegal_chars(steam_name, " - ")
                        while "  " in clean_steam_name: clean_steam_name = clean_steam_name.replace("  ", " ")
                        while "- -" in clean_steam_name: clean_steam_name = clean_steam_name.replace("- -", " - ")
                        name_override = clean_steam_name.strip()
                    else:
                        name_override = clean_name
                else:
                    name_override = clean_name
            else:
                name_override = clean_name

        except Exception as e:
            print(f"Error detecting Steam AppID: {e}")

        # Check for ISO file in directory
        iso_path = ""
        try:
            for f in os.listdir(directory):
                if f.lower().endswith('.iso'):
                    iso_path = os.path.join(directory, f)
                    break
        except Exception:
            pass

        # Populate Kill List with all executables in directory
        kill_list_items = []
        try:
            for root, dirs, files in os.walk(directory):
                for f in files:
                    if f.lower().endswith('.exe'):
                        if f not in kill_list_items:
                            kill_list_items.append(f)
        except Exception:
            pass
        
        kill_list_str = ",".join(kill_list_items)

        config = self.main_window.config

        game_data = {
            'create': True,
            'name': filename,
            'directory': directory,
            'name_override': name_override,
            'steam_id': steam_id,
            'iso_path': iso_path,
            'kill_list': kill_list_str,
            'kill_list_enabled': bool(kill_list_str),

            # Populate from config
            'run_as_admin': config.run_as_admin,
            'hide_taskbar': config.hide_taskbar,
            'overwrite_game_ini': config.overwrite_game_ini,
            'recreate_game_ini': config.recreate_game_ini,
            'kill_list_enabled': config.use_kill_list,
            'controller_mapper_path': config.controller_mapper_path if config.defaults.get('controller_mapper_path_enabled', True) else "",
            'controller_mapper_enabled': config.defaults.get('controller_mapper_path_enabled', True),
            'controller_mapper_overwrite': config.overwrite_states.get('controller_mapper_path', True),
            'controller_mapper_run_wait': config.run_wait_states.get('controller_mapper_path_run_wait', False),
            'controller_mapper_options': config.controller_mapper_path_options,
            'controller_mapper_arguments': config.controller_mapper_path_arguments,

            # Borderless
            'borderless_windowing_path': config.borderless_gaming_path if config.defaults.get('borderless_gaming_path_enabled', True) else "",
            'borderless_windowing_enabled': config.defaults.get('borderless_gaming_path_enabled', True),
            'borderless_windowing_overwrite': config.overwrite_states.get('borderless_gaming_path', True),
            'borderless_windowing_run_wait': config.run_wait_states.get('borderless_gaming_path_run_wait', False),
            'borderless_windowing_options': config.borderless_gaming_path_options,
            'borderless_windowing_arguments': config.borderless_gaming_path_arguments,

            # Monitor
            'monitorapp_path': config.monitorapp_path if config.defaults.get('monitorapp_path_enabled', True) else "",
            'monitorapp_enabled': config.defaults.get('monitorapp_path_enabled', True),
            'monitorapp_overwrite': config.overwrite_states.get('monitorapp_path', True),
            'monitorapp_run_wait': config.run_wait_states.get('monitorapp_path_run_wait', False),
            'monitorapp_options': config.monitorapp_options,
            'monitorapp_arguments': config.monitorapp_arguments,

            # Just After Launch
            'just_after_launch_path': config.just_after_launch_path if config.defaults.get('just_after_launch_path_enabled', True) else "",
            'just_after_launch_enabled': config.defaults.get('just_after_launch_path_enabled', True),
            'just_after_launch_overwrite': config.overwrite_states.get('just_after_launch_path', True),
            'just_after_launch_run_wait': config.run_wait_states.get('just_after_launch_path_run_wait', False),
            'just_after_launch_options': config.just_after_launch_path_options,
            'just_after_launch_arguments': config.just_after_launch_path_arguments,

            # Just Before Exit
            'just_before_exit_path': config.just_before_exit_path if config.defaults.get('just_before_exit_path_enabled', True) else "",
            'just_before_exit_enabled': config.defaults.get('just_before_exit_path_enabled', True),
            'just_before_exit_overwrite': config.overwrite_states.get('just_before_exit_path', True),
            'just_before_exit_run_wait': config.run_wait_states.get('just_before_exit_path_run_wait', False),
            'just_before_exit_options': config.just_before_exit_path_options,
            'just_before_exit_arguments': config.just_before_exit_path_arguments,

            # Pre/Post Scripts
            'pre1_path': config.pre1_path if config.defaults.get('pre1_path_enabled', True) else "",
            'pre_1_enabled': config.defaults.get('pre1_path_enabled', True),
            'pre_1_overwrite': config.overwrite_states.get('pre1_path', True),
            'pre_1_run_wait': config.run_wait_states.get('pre1_path_run_wait', False),
            'pre1_options': config.pre1_path_options,
            'pre1_arguments': config.pre1_path_arguments,

            'pre2_path': config.pre2_path if config.defaults.get('pre2_path_enabled', True) else "",
            'pre_2_enabled': config.defaults.get('pre2_path_enabled', True),
            'pre_2_overwrite': config.overwrite_states.get('pre2_path', True),
            'pre_2_run_wait': config.run_wait_states.get('pre2_path_run_wait', False),
            'pre2_options': config.pre2_path_options,
            'pre2_arguments': config.pre2_path_arguments,

            'pre3_path': config.pre3_path if config.defaults.get('pre3_path_enabled', True) else "",
            'pre_3_enabled': config.defaults.get('pre3_path_enabled', True),
            'pre_3_overwrite': config.overwrite_states.get('pre3_path', True),
            'pre_3_run_wait': config.run_wait_states.get('pre3_path_run_wait', False),
            'pre3_options': config.pre3_path_options,
            'pre3_arguments': config.pre3_path_arguments,

            'post1_path': config.post1_path if config.defaults.get('post1_path_enabled', True) else "",
            'post_1_enabled': config.defaults.get('post1_path_enabled', True),
            'post_1_overwrite': config.overwrite_states.get('post1_path', True),
            'post_1_run_wait': config.run_wait_states.get('post1_path_run_wait', False),
            'post1_options': config.post1_path_options,
            'post1_arguments': config.post1_path_arguments,

            'post2_path': config.post2_path if config.defaults.get('post2_path_enabled', True) else "",
            'post_2_enabled': config.defaults.get('post2_path_enabled', True),
            'post_2_overwrite': config.overwrite_states.get('post2_path', True),
            'post_2_run_wait': config.run_wait_states.get('post2_path_run_wait', False),
            'post2_options': config.post2_path_options,
            'post2_arguments': config.post2_path_arguments,

            'post3_path': config.post3_path if config.defaults.get('post3_path_enabled', True) else "",
            'post_3_enabled': config.defaults.get('post3_path_enabled', True),
            'post_3_overwrite': config.overwrite_states.get('post3_path', True),
            'post_3_run_wait': config.run_wait_states.get('post3_path_run_wait', False),
            'post3_options': config.post3_path_options,
            'post3_arguments': config.post3_path_arguments,


            'monitor_desk_cfg': config.monitor_desk_path if config.defaults.get('monitor_desk_path_enabled', False) else "", 'monitor_desk_cfg_enabled': config.defaults.get('monitor_desk_path_enabled', False), 'monitor_desk_cfg_overwrite': config.overwrite_states.get('monitor_desk_path', True),

            # Launcher Executable
            'launcher_executable': (config.launcher_executable if config.launcher_executable else constants.LAUNCHER_EXECUTABLE) if config.defaults.get('launcher_executable_enabled', True) else "", 'launcher_executable_enabled': config.defaults.get('launcher_executable_enabled', True), 'launcher_executable_overwrite': config.overwrite_states.get('launcher_executable', True),
            'launcher_executable_options': config.launcher_executable_options, 'launcher_executable_arguments': config.launcher_executable_arguments,

            # Disc Mount
            'disc_mount_path': config.disc_mount_path if config.defaults.get('disc_mount_path_enabled', True) else "", 'disc_mount_enabled': config.defaults.get('disc_mount_path_enabled', True), 'disc_mount_overwrite': config.overwrite_states.get('disc_mount_path', True),
            'disc_mount_options': config.disc_mount_path_options, 'disc_mount_arguments': config.disc_mount_path_arguments, 'disc_mount_run_wait': config.run_wait_states.get('disc_mount_path_run_wait', False),
            
            # Disc Mount Config
            'disc_mount_cfg': '', 'disc_mount_cfg_enabled': True, 'disc_mount_cfg_overwrite': True,
            'disc_unmount_cfg': '', 'disc_unmount_cfg_enabled': True, 'disc_unmount_cfg_overwrite': True,
            
            # Audio App
            'audio_app_path': '', 'audio_app_enabled': True, 'audio_app_overwrite': True,
            'audio_app_options': '', 'audio_app_arguments': '', 'audio_app_run_wait': False,
            'unborder_cfg': '', 'unborder_cfg_enabled': True, 'unborder_cfg_overwrite': True,
            'reborder_cfg': '', 'reborder_cfg_enabled': True, 'reborder_cfg_overwrite': True,

            # Monitor Config App
            'monitorapp_path': config.monitorapp_path if config.defaults.get('monitorapp_path_enabled', True) else "",
            'monitorapp_enabled': config.defaults.get('monitorapp_path_enabled', True),
            'monitorapp_overwrite': config.overwrite_states.get('monitorapp_path', True),
            'monitorapp_options': config.monitorapp_options,
            'monitorapp_arguments': config.monitorapp_arguments,
            'monitorapp_run_wait': config.run_wait_states.get('monitorapp_path_run_wait', False),
        }
        
        self.original_data.append(copy.deepcopy(game_data))
        self.filter_table(self.search_bar.text()) # Re-filter and refresh
        # Scroll to bottom of current view if added
        row = self.table.rowCount() - 1
        self.table.scrollToItem(self.table.item(row, 0))
        self.main_window._on_editor_table_edited(None)

    def on_header_context_menu(self, position):
        """Handle context menu for column headers."""
        index = self.table.horizontalHeader().logicalIndexAt(position)  # type: ignore[union-attr]
        if index < 0:
            return

        menu = QMenu(self)
        select_col_action = menu.addAction("Select Column")
        resize_col_action = menu.addAction("Resize to Contents")
        
        action = menu.exec(self.table.horizontalHeader().mapToGlobal(position))  # type: ignore[union-attr]
        
        if action == select_col_action:
            self.table.selectColumn(index)
        elif action == resize_col_action:
            self.table.resizeColumnToContents(index)

    def on_context_menu(self, position):
        """Create and display custom context menu for the table."""
        row = self.table.rowAt(position.y())
        col = self.table.columnAt(position.x())
        
        if row < 0 or col < 0:
            return

        # Ensure the right-clicked row is part of the selection so that
        # propagation and other selection-based actions have a target.
        sel_model = self.table.selectionModel()
        idx = self.table.model().index(row, 0)
        if not sel_model.isSelected(idx):
            sel_model.select(idx, QItemSelectionModel.Select | QItemSelectionModel.Rows)

        menu = QMenu(self)
        
        # Toggle Create Action
        toggle_create_action = menu.addAction("Toggle 'Create' for Selected")
        toggle_create_action.triggered.connect(self.toggle_create_for_selection)
        
        # Clone Game Action
        clone_action = menu.addAction("Clone Game")
        clone_action.triggered.connect(lambda: self.clone_game(row))

        # Remove from List Action
        remove_action = menu.addAction("Remove from List")
        remove_action.triggered.connect(lambda: self.remove_selected_rows(row))

        # Open Game.ini Action
        open_ini_action = menu.addAction("Open Game.ini")
        open_ini_action.triggered.connect(lambda: self.open_game_ini(row))

        # Open Profile Folder Action
        open_profile_action = menu.addAction("Open Profile Folder")
        open_profile_action.triggered.connect(lambda: self.open_profile_folder(row))

        # Download Artwork Action
        download_artwork_action = menu.addAction("Download Artwork")
        download_artwork_action.triggered.connect(lambda: self.download_artwork_selected(row))

        # Auto-Match Steam ID Action
        auto_match_action = menu.addAction("Auto-Match Steam ID")
        auto_match_action.triggered.connect(lambda: self.auto_match_steam_id_selected(row))

        # Regenerate Names Action
        regenerate_names_action = menu.addAction("Regenerate Names")
        regenerate_names_action.triggered.connect(lambda: self.regenerate_names_selected(row))

        menu.addSeparator()

        # Browse Action
        path_cols = {
            constants.EditorCols.CM_PATH.value, constants.EditorCols.BW_PATH.value,
            constants.EditorCols.UNBORDER_CFG.value, constants.EditorCols.UNBORDER_CFG_OPTIONS.value, constants.EditorCols.UNBORDER_CFG_ARGUMENTS.value,
            constants.EditorCols.REBORDER_CFG.value, constants.EditorCols.REBORDER_CFG_OPTIONS.value, constants.EditorCols.REBORDER_CFG_ARGUMENTS.value,
            constants.EditorCols.MONITOR_GAME_CFG.value, constants.EditorCols.MONITOR_GAME_CFG_OPTIONS.value, constants.EditorCols.MONITOR_GAME_CFG_ARGUMENTS.value,
            constants.EditorCols.MONITOR_DESK_CFG.value, constants.EditorCols.MONITOR_DESK_CFG_OPTIONS.value, constants.EditorCols.MONITOR_DESK_CFG_ARGUMENTS.value,
            constants.EditorCols.PLAYER1_PROFILE.value, constants.EditorCols.PLAYER1_PROFILE_OPTIONS.value, constants.EditorCols.PLAYER1_PROFILE_ARGUMENTS.value,
            constants.EditorCols.PLAYER2_PROFILE.value, constants.EditorCols.PLAYER2_PROFILE_OPTIONS.value, constants.EditorCols.PLAYER2_PROFILE_ARGUMENTS.value,
            constants.EditorCols.DESK_PROFILE.value, constants.EditorCols.DESK_PROFILE_OPTIONS.value, constants.EditorCols.DESK_PROFILE_ARGUMENTS.value,
            constants.EditorCols.JA_PATH.value, constants.EditorCols.JB_PATH.value,
            constants.EditorCols.PRE1_PATH.value, constants.EditorCols.POST1_PATH.value,
            constants.EditorCols.PRE2_PATH.value, constants.EditorCols.POST2_PATH.value,
            constants.EditorCols.PRE3_PATH.value, constants.EditorCols.POST3_PATH.value,
            constants.EditorCols.LAUNCHER_EXE.value,
            constants.EditorCols.ISO_PATH.value,
            constants.EditorCols.DM_MOUNT_CFG.value, constants.EditorCols.DM_UNMOUNT_CFG.value,
            constants.EditorCols.AUDIO_APP_PATH.value, constants.EditorCols.UNBORDER_CFG.value,
            constants.EditorCols.REBORDER_CFG.value
        }
        
        if col in path_cols:
            browse_action = menu.addAction("Browse...")
            browse_action.triggered.connect(lambda: self.browse_for_cell(row, col))
            menu.addSeparator()

        # Edit
        edit_action = menu.addAction("Edit this Field")
        edit_action.triggered.connect(lambda: self.edit_cell(row, col))
        
        # Select Row
        select_row_action = menu.addAction("Select Row")
        select_row_action.triggered.connect(lambda: self.table.selectRow(row))
        
        menu.addSeparator()
        select_all_action = menu.addAction("Select All")
        select_all_action.triggered.connect(self.table.selectAll)
        deselect_all_action = menu.addAction("Deselect All")
        deselect_all_action.triggered.connect(self.table.clearSelection)
        
        menu.addSeparator()
        
        # Copy/Paste
        copy_action = menu.addAction("Copy")
        copy_action.triggered.connect(lambda: self.copy_cell(row, col))
        
        paste_action = menu.addAction("Paste")
        paste_action.triggered.connect(lambda: self.paste_cell(row, col))
        
        if col == constants.EditorCols.STEAMID.value:
            search_steam_action = menu.addAction("Search Steam AppID")
            search_steam_action.triggered.connect(lambda: self.search_steam_id(row))
            
        if col == constants.EditorCols.KILL_LIST.value:
            self._add_kill_list_menu(menu, row)

        if col == constants.EditorCols.ISO_PATH.value:
            search_iso_action = menu.addAction("Search for disc images")
            search_iso_action.triggered.connect(lambda: self.search_disc_images_selected(row))

        # Append to Kill List Action (for selection)
        selected_rows = self.table.selectionModel().selectedRows()  # type: ignore[union-attr]
        if len(selected_rows) > 0:
             append_kill_action = menu.addAction(f"Append to Kill List ({len(selected_rows)} items)")
             append_kill_action.triggered.connect(self.open_append_kill_list_dialog)

        menu.addSeparator()

        reset_row_action = menu.addAction("Reset Row")
        reset_row_action.triggered.connect(lambda: self.reset_row(row))

        menu.addSeparator()
        
        # Check column range for "Apply to Selected"
        # Include all settings columns from RUN_AS_ADMIN through HIDE_TASKBAR, excluding KILL_LIST
        if (constants.EditorCols.ARGUMENTS.value < col <= constants.EditorCols.HIDE_TASKBAR.value
                and col != constants.EditorCols.KILL_LIST.value):
            apply_action = menu.addAction("Propagate to column")
            apply_action.triggered.connect(lambda: self.apply_cell_value_to_selection(row, col))

        # "Propagate to selected" — copy ALL values from the source row to other selected rows
        num_selected = len(self.table.selectionModel().selectedRows())  # type: ignore[union-attr]
        if num_selected > 1:
            propagate_row_action = menu.addAction(f"Propagate to selected ({num_selected} rows)")
            propagate_row_action.triggered.connect(lambda: self.propagate_row_to_selection(row))
            
        if not menu.isEmpty():
            menu.exec(self.table.viewport().mapToGlobal(position))

    def open_append_kill_list_dialog(self):
        self.push_undo()
        dialog = AppendKillListDialog(self)
        if dialog.exec():
            value = dialog.get_value()
            if value:
                self.append_to_kill_list_selection(value)

    def append_to_kill_list_selection(self, value):
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        if not selected_rows:
            return

        for row in selected_rows:
            real_index = (self.current_page * self.page_size) + row
            if real_index < len(self.filtered_data):
                game = self.filtered_data[real_index]
                current_list = game.get('kill_list', '')
                items = [x.strip() for x in current_list.split(',') if x.strip()]
                if value not in items:
                    items.append(value)
                    game['kill_list'] = ",".join(items)
                    # Update UI
                    item = self.table.item(row, constants.EditorCols.KILL_LIST.value)
                    if not item:
                        item = QTableWidgetItem()
                        self.table.setItem(row, constants.EditorCols.KILL_LIST.value, item)
                    item.setText(game['kill_list'])
        
        self.main_window._on_editor_table_edited(None)

    def open_bulk_edit_dialog(self):
        """Open a dialog to edit a specific field for all selected rows."""
        self.push_undo()
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        if not selected_rows:
            QMessageBox.information(self, "Bulk Edit", "Please select rows to edit.")
            return

        dialog = QDialog(self)
        dialog.setWindowTitle(f"Bulk Edit ({len(selected_rows)} items)")
        layout = QVBoxLayout(dialog)
        
        # Field selection
        layout.addWidget(QLabel("Select Field to Edit:"))
        field_combo = QComboBox()
        
        # Define editable fields and their types
        fields = [
            ("Run As Admin", constants.EditorCols.RUN_AS_ADMIN, "bool"),
            ("Hide Taskbar", constants.EditorCols.HIDE_TASKBAR, "bool"),
            ("Kill List Enabled", constants.EditorCols.KILL_LIST, "bool_special"),
            ("Controller Mapper Enabled", constants.EditorCols.CM_PATH, "bool_merged"),
            ("Borderless Windowing Enabled", constants.EditorCols.BW_PATH, "bool_merged"),
            ("Just After Launch Enabled", constants.EditorCols.JA_PATH, "bool_merged"),
            ("Just Before Exit Enabled", constants.EditorCols.JB_PATH, "bool_merged"),
            ("Wait for Mapper", constants.EditorCols.CM_RUN_WAIT, "bool"),
            ("Wait for Borderless", constants.EditorCols.BW_RUN_WAIT, "bool"),
        ]
        
        for name, col, type_ in fields:
            field_combo.addItem(name, (col, type_))
            
        layout.addWidget(field_combo)
        
        # Value input
        layout.addWidget(QLabel("New Value:"))
        value_check = QCheckBox("Enable / True")
        layout.addWidget(value_check)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        
        if dialog.exec():
            col_enum, type_ = field_combo.currentData()
            new_value = value_check.isChecked()
            
            for row in selected_rows:
                # Update the cell widget/item
                if type_ == "bool":
                    widget = self.table.cellWidget(row, col_enum.value)
                    if widget:
                        cbs = widget.findChildren(QCheckBox)
                        if cbs: cbs[0].setChecked(new_value)
                elif type_ == "bool_merged":
                    # Need to update the enabled checkbox of the merged widget
                    widget = self.table.cellWidget(row, col_enum.value)
                    if widget:
                        cbs = widget.findChildren(QCheckBox)
                        if cbs: cbs[0].setChecked(new_value)
                elif type_ == "bool_special":
                    # Kill list enabled state
                    item = self.table.item(row, col_enum.value)
                    if item:
                        item.setCheckState(Qt.CheckState.Checked if new_value else Qt.CheckState.Unchecked)
                
                # Sync to data model
                self._sync_cell_to_data(row, col_enum.value)
            
            self.main_window._on_editor_table_edited(None)

    def validate_paths(self):
        """Check if paths in the table exist on disk and highlight invalid ones in green."""
        path_cols = [
            constants.EditorCols.DIRECTORY,
            constants.EditorCols.CM_PATH, constants.EditorCols.BW_PATH,
            constants.EditorCols.JA_PATH, constants.EditorCols.JB_PATH,
            constants.EditorCols.PRE1_PATH, constants.EditorCols.PRE2_PATH, constants.EditorCols.PRE3_PATH,
            constants.EditorCols.POST1_PATH, constants.EditorCols.POST2_PATH, constants.EditorCols.POST3_PATH,
            constants.EditorCols.LAUNCHER_EXE,
            constants.EditorCols.MONITOR_GAME_CFG, constants.EditorCols.MONITOR_GAME_CFG_OPTIONS, constants.EditorCols.MONITOR_GAME_CFG_ARGUMENTS,
            constants.EditorCols.MONITOR_DESK_CFG, constants.EditorCols.MONITOR_DESK_CFG_OPTIONS, constants.EditorCols.MONITOR_DESK_CFG_ARGUMENTS,
            constants.EditorCols.PLAYER1_PROFILE, constants.EditorCols.PLAYER1_PROFILE_OPTIONS, constants.EditorCols.PLAYER1_PROFILE_ARGUMENTS,
            constants.EditorCols.PLAYER2_PROFILE, constants.EditorCols.PLAYER2_PROFILE_OPTIONS, constants.EditorCols.PLAYER2_PROFILE_ARGUMENTS,
            constants.EditorCols.DESK_PROFILE, constants.EditorCols.DESK_PROFILE_OPTIONS, constants.EditorCols.DESK_PROFILE_ARGUMENTS,
            constants.EditorCols.ISO_PATH,
            constants.EditorCols.DM_MOUNT_CFG, constants.EditorCols.DM_UNMOUNT_CFG,
            constants.EditorCols.AUDIO_APP_PATH, constants.EditorCols.UNBORDER_CFG, constants.EditorCols.UNBORDER_CFG_OPTIONS, constants.EditorCols.UNBORDER_CFG_ARGUMENTS,
            constants.EditorCols.REBORDER_CFG, constants.EditorCols.REBORDER_CFG_OPTIONS, constants.EditorCols.REBORDER_CFG_ARGUMENTS,
            constants.EditorCols.MONITORAPP_PATH
        ]
        
        for row in range(self.table.rowCount()):
            for col_enum in path_cols:
                col = col_enum.value
                path = ""
                
                # Get path from widget or item
                widget = self.table.cellWidget(row, col)  # type: ignore[union-attr]
                if widget:
                    le = widget.findChild(QLineEdit)
                    if le: path = le.text()
                else:
                    item = self.table.item(row, col)
                    if item: path = item.text()
                
                # Clean path (remove propagation symbols)
                clean_path = path
                if path.startswith("< ") or path.startswith("> "):
                    clean_path = path[2:]
                
                if clean_path and not os.path.exists(clean_path):
                    # Path is invalid but no visual highlighting
                    pass

    def clone_game(self, row):
        """Clone the game at the specified row or selected rows."""
        # Get selected rows
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        # Determine which rows to clone
        rows_to_clone = []
        if row in selected_rows:
            rows_to_clone = sorted(list(selected_rows))
        else:
            rows_to_clone = [row]
            
        if not rows_to_clone:
            return

        # Confirmation for multiple rows
        if len(rows_to_clone) > 1:
            reply = QMessageBox.question(
                self, "Confirm Clone",
                f"Are you sure you want to clone {len(rows_to_clone)} games?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.push_undo()
        
        # Collect existing names for collision detection
        existing_names = set(g.get('name_override', '') for g in self.original_data)
        
        # Collect items to clone first to avoid index shifting issues during iteration
        items_to_clone = []
        for r in rows_to_clone:
            real_index = (self.current_page * self.page_size) + r
            if real_index < len(self.filtered_data):
                items_to_clone.append(self.filtered_data[real_index])
        
        for game_to_clone in items_to_clone:
            new_game = copy.deepcopy(game_to_clone)
            original_name = game_to_clone.get('name_override', '')
            
            # Determine base name and next number for enumeration
            match = re.search(r'_(\d+)_$', original_name)
            if match:
                base_name = original_name[:match.start()]
                number = int(match.group(1))
            else:
                base_name = original_name
                number = 0
            
            # Find next available number
            next_number = number + 1
            while True:
                new_name = f"{base_name}_{next_number}_"
                if new_name not in existing_names:
                    new_game['name_override'] = new_name
                    existing_names.add(new_name)
                    break
                next_number += 1
            
            # Insert after the original item in original_data
            try:
                original_index = self.original_data.index(game_to_clone)
                self.original_data.insert(original_index + 1, new_game)
            except ValueError:
                self.original_data.append(new_game)
                
        # Refresh view
        self.filter_table(self.search_bar.text())
        self.main_window._on_editor_table_edited(None)

    def remove_selected_rows(self, row=None):
        """Remove selected rows from the list without deleting files."""
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        # Handle context menu click on unselected row
        if row is not None and row >= 0:
            if row not in selected_rows:
                selected_rows = {row}
        
        if not selected_rows:
            return

        reply = QMessageBox.question(
            self, "Confirm Remove",
            f"Are you sure you want to remove {len(selected_rows)} items from the list?\nThis will NOT delete any files.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self.push_undo()
        
        # Identify items to remove
        items_to_remove = []
        for r in selected_rows:
            real_index = (self.current_page * self.page_size) + r
            if real_index < len(self.filtered_data):
                items_to_remove.append(self.filtered_data[real_index])
        
        # Rebuild original_data excluding items to remove
        ids_to_remove = {id(item) for item in items_to_remove}
        self.original_data = [item for item in self.original_data if id(item) not in ids_to_remove]
            
        # Refresh view
        self.filter_table(self.search_bar.text())
        self.main_window._on_editor_table_edited(None)

    def open_game_ini(self, row):
        """Open the Game.ini file for the selected game."""
        real_index = (self.current_page * self.page_size) + row
        if real_index < len(self.filtered_data):
            game_data = self.filtered_data[real_index]
            
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_data.get('name_override', ''))
            if not safe_name:
                 safe_name = make_safe_filename(game_data.get('name', ''))
            
            profiles_dir = self.main_window.config.profiles_dir
            ini_path = os.path.join(profiles_dir, safe_name, "Game.ini")
            
            if os.path.exists(ini_path):
                os.startfile(ini_path)
            else:
                QMessageBox.warning(self, "File Not Found", f"Game.ini not found at:\n{ini_path}\n\nHas the game been created yet?")

    def open_profile_folder(self, row):
        """Open the profile folder for the selected game."""
        real_index = (self.current_page * self.page_size) + row
        if real_index < len(self.filtered_data):
            game_data = self.filtered_data[real_index]
            
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_data.get('name_override', ''))
            if not safe_name:
                 safe_name = make_safe_filename(game_data.get('name', ''))
            
            profiles_dir = self.main_window.config.profiles_dir
            profile_path = os.path.join(profiles_dir, safe_name)
            
            if os.path.exists(profile_path):
                os.startfile(profile_path)
            else:
                QMessageBox.warning(self, "Folder Not Found", f"Profile folder not found at:\n{profile_path}\n\nHas the game been created yet?")

    def regenerate_names_selected(self, row):
        """Regenerate names for selected rows using NameProcessor."""
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        if row is not None and row >= 0 and row not in selected_rows:
            selected_rows.add(row)
            
        if not selected_rows:
            return

        self.push_undo()
        
        # Ensure dependencies are loaded
        if not self.main_window.steam_cache_manager.normalized_steam_index:
            self.main_window.steam_cache_manager.load_normalized_steam_index()
            
        from Python.ui.name_processor import NameProcessor
        from Python.ui.game_indexer import get_filtered_directory_name, _get_steam_match
        
        release_groups = getattr(self.main_window, 'release_groups_set', set())
        exclude_exe = getattr(self.main_window, 'exclude_exe_set', set())
        folder_exclude = getattr(self.main_window, 'folder_exclude_set', set())
        
        name_processor = NameProcessor(release_groups, exclude_exe)
        
        count = 0
        for r in selected_rows:
            real_index = (self.current_page * self.page_size) + r
            if real_index < len(self.filtered_data):
                game = self.filtered_data[real_index]
                
                # Get paths
                directory = game.get('directory', '')
                filename = game.get('name', '')
                full_path = os.path.join(directory, filename)
                
                # Recalculate name override based on directory structure
                dir_name = get_filtered_directory_name(full_path, folder_exclude)
                name_override = name_processor.get_display_name(dir_name)
                
                # Re-run Steam matching
                steam_name, steam_id, name_override = _get_steam_match(
                    name_override, 
                    self.main_window.config, 
                    self.main_window.steam_cache_manager.normalized_steam_index, 
                    name_processor
                )
                
                # Update data
                game['name_override'] = name_override
                game['steam_id'] = steam_id
                count += 1
        
        self.main_window._on_editor_table_edited(None)
        self.main_window.statusBar().showMessage(f"Regenerated names for {count} items", 3000)

    def _on_fuzzy_combo_changed(self, combo, row):
        steam_id = combo.currentData()
        
        # Update Steam ID if valid ID selected
        item_id = self.table.item(row, constants.EditorCols.STEAMID.value)
        if not item_id:
            item_id = QTableWidgetItem()
            self.table.setItem(row, constants.EditorCols.STEAMID.value, item_id)
        item_id.setText(str(steam_id))
        
        # Clear background if it was highlighted as empty
        item_id.setData(Qt.ItemDataRole.BackgroundRole, None)
        item_id.setData(Qt.ItemDataRole.ForegroundRole, None)
        self._sync_cell_to_data(row, constants.EditorCols.STEAMID.value)
        self._sync_cell_to_data(row, constants.EditorCols.NAME_OVERRIDE.value)        
        self.main_window._on_editor_table_edited(None)

    def auto_match_steam_id_selected(self, row):
        """Attempt to auto-match Steam ID for selected rows using the cache."""
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        if row is not None and row >= 0 and row not in selected_rows:
            selected_rows.add(row)
            
        if not selected_rows:
            return

        self.push_undo()
        
        # Ensure cache is loaded
        if not self.main_window.steam_cache_manager.normalized_steam_index:
            self.main_window.steam_cache_manager.load_normalized_steam_index()
            
        if not self.main_window.steam_cache_manager.normalized_steam_index:
            QMessageBox.warning(self, "Cache Empty", "Steam index cache is empty or not loaded.")
            return

        from Python.ui.name_processor import NameProcessor
        release_groups = getattr(self.main_window, 'release_groups_set', set())
        exclude_exe = getattr(self.main_window, 'exclude_exe_set', set())
        name_processor = NameProcessor(release_groups, exclude_exe)
        
        matched_count = 0
        fuzzy_count = 0
        
        all_keys = []
        if self.main_window.steam_cache_manager.normalized_steam_index:
             all_keys = list(self.main_window.steam_cache_manager.normalized_steam_index.keys())
        
        for r in selected_rows:
            real_index = (self.current_page * self.page_size) + r
            if real_index < len(self.filtered_data):
                game = self.filtered_data[real_index]
                
                # Determine name to use
                name_to_use = game.get('name_override', '')
                if not name_to_use:
                    # Fallback to filename without extension
                    filename = game.get('name', '')
                    name_to_use = os.path.splitext(filename)[0]
                
                # Normalize
                clean_name = name_processor.get_display_name(name_to_use)
                match_name = name_processor.get_match_name(clean_name)
                
                match_data = self.main_window.steam_cache_manager.normalized_steam_index.get(match_name)
                
                if match_data:
                    steam_id = match_data.get("id")
                    if steam_id:
                        game['steam_id'] = steam_id
                        # Update UI
                        item = self.table.item(r, constants.EditorCols.STEAMID.value)
                        if not item:
                            item = QTableWidgetItem()
                            self.table.setItem(r, constants.EditorCols.STEAMID.value, item)
                        item.setText(str(steam_id))
                        
                        # Clear background if it was highlighted as empty
                        item.setData(Qt.ItemDataRole.BackgroundRole, None)
                        item.setData(Qt.ItemDataRole.ForegroundRole, None)
                        
                        matched_count += 1
                elif all_keys:
                    # Fuzzy match
                    cutoff = getattr(self.main_window.config, 'fuzzy_match_cutoff', 0.6)
                    matches = difflib.get_close_matches(match_name, all_keys, n=5, cutoff=cutoff)
                    if matches:
                        combo = QComboBox()
                        combo.setEditable(True)
                        combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
                        # Add original as first item
                        combo.addItem(name_to_use, None)
                        
                        for m in matches:
                            data = self.main_window.steam_cache_manager.normalized_steam_index[m]
                            combo.addItem(f"{data['name']}", data['id'])
                        
                        combo.currentIndexChanged.connect(lambda _, c=combo, r_idx=r: self._on_fuzzy_combo_changed(c, r_idx))
                        combo.editTextChanged.connect(lambda _, c=combo, r_idx=r: self._on_fuzzy_combo_changed(c, r_idx))
                        self.table.setCellWidget(r, constants.EditorCols.NAME_OVERRIDE.value, combo)
                        fuzzy_count += 1
        
        if matched_count > 0 or fuzzy_count > 0:
            self.main_window._on_editor_table_edited(None)
            msg = f"Auto-matched {matched_count} Steam IDs"
            if fuzzy_count > 0:
                msg += f" and found {fuzzy_count} fuzzy matches"
            self.main_window.statusBar().showMessage(msg, 3000)
        else:
            QMessageBox.information(self, "Auto-Match", "No matches found in cache for selected items.")

    def download_artwork_selected(self, row):
        """Download artwork for selected games."""
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        if row is not None and row >= 0 and row not in selected_rows:
            selected_rows.add(row)
            
        if not selected_rows:
            return

        # Confirmation for multiple items
        if len(selected_rows) > 1:
            reply = QMessageBox.question(
                self, "Confirm Download",
                f"Are you sure you want to download artwork for {len(selected_rows)} games?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        # Progress Dialog setup
        progress = None
        if len(selected_rows) > 1:
            progress = QProgressDialog("Downloading artwork...", "Cancel", 0, len(selected_rows), self)
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.setMinimumDuration(0)
            progress.setValue(0)

        count = 0
        canceled = False
        rows_list = list(selected_rows)

        for i, r in enumerate(rows_list):
            if progress:
                if progress.wasCanceled():
                    canceled = True
                    break
                progress.setValue(i)

            real_index = (self.current_page * self.page_size) + r
            if real_index < len(self.filtered_data):
                game_data = self.filtered_data[real_index]
                
                if progress:
                    game_name = game_data.get('name_override') or game_data.get('name') or "Unknown"
                    progress.setLabelText(f"Downloading artwork for: {game_name}")
                    QApplication.processEvents()
                
                # Determine profile directory
                from Python.ui.name_utils import make_safe_filename
                safe_name = make_safe_filename(game_data.get('name_override', ''))
                if not safe_name:
                     safe_name = make_safe_filename(game_data.get('name', ''))
                
                profiles_dir = self.main_window.config.profiles_dir
                profile_path = os.path.join(profiles_dir, safe_name)
                
                if not os.path.exists(profile_path):
                    try:
                        os.makedirs(profile_path)
                    except Exception as e:
                        print(f"Could not create profile dir: {e}")
                        continue

                self.main_window.creation_controller.download_artwork(game_data, profile_path)
                count += 1
        
        if progress:
            progress.setValue(len(selected_rows))

        if canceled:
            QMessageBox.information(self, "Artwork Download", f"Download cancelled. Processed {count} games.")
        else:
            QMessageBox.information(self, "Artwork Download", f"Attempted to download artwork for {count} games.")

    def toggle_create_for_selection(self):
        """Toggle the 'create' status for all selected rows."""
        self.toggle_create_column()

    def browse_for_cell(self, row, col):
        """Open file dialog for a specific cell."""
        # Get current path to set initial directory
        current_path = ""
        widget = self.table.cellWidget(row, col)  # type: ignore[union-attr]
        if widget:
            le = widget.findChild(QLineEdit)
            if le:
                current_path = le.text()
                if current_path.startswith("< ") or current_path.startswith("> "):
                    current_path = current_path[2:]
        else:
            item = self.table.item(row, col)
            if item:
                current_path = item.text()

        start_dir = ""
        if current_path and os.path.exists(current_path):
            if os.path.isfile(current_path):
                start_dir = os.path.dirname(current_path)
            else:
                start_dir = current_path
        
        file_path, _ = QFileDialog.getOpenFileName(self, "Select File", start_dir, "All Files (*.*)")
        
        if file_path:
            # Normalize path to use forward slashes
            file_path = file_path.replace('\\', '/')
            self.push_undo()
            if widget:
                le = widget.findChild(QLineEdit)
                if le:
                    text = le.text()
                    prefix = ""
                    if text.startswith("< "): prefix = "< "
                    elif text.startswith("> "): prefix = "> "
                    le.setText(prefix + file_path)
            else:
                item = self.table.item(row, col)
                if not item:
                    item = QTableWidgetItem()
                    self.table.setItem(row, col, item)
                item.setText(file_path)

    def edit_cell(self, row, col):
        item = self.table.item(row, col)
        if item:
            self.table.editItem(item)

    def copy_cell(self, row, col):
        # No undo needed for copy
        state = self._get_cell_state(row, col)
        if state:
            try:
                QApplication.clipboard().setText(json.dumps(state))
            except Exception:
                pass

    def paste_cell(self, row, col):
        self.push_undo()
        text = QApplication.clipboard().text()
        if not text: return
        
        try:
            # Try to parse as state JSON
            state = json.loads(text)
            if isinstance(state, dict) and 'type' in state:
                self._set_cell_state(row, col, state)
                self.main_window._on_editor_table_edited(None)
                return
        except Exception:
            pass
            
        # Fallback: Paste as text if cell supports it
        item = self.table.item(row, col)
        if item:
            item.setText(text)
            self.main_window._on_editor_table_edited(None)

    def search_steam_id(self, row):
        """Manually search for a Steam AppID."""
        self.push_undo()
        name_item = self.table.item(row, constants.EditorCols.NAME_OVERRIDE.value)
        if not name_item or not name_item.text():
            name_item = self.table.item(row, constants.EditorCols.NAME.value)
        
        current_name = name_item.text() if name_item else ""
        
        search_term, ok = QInputDialog.getText(self, "Search Steam AppID", "Enter game name:", text=current_name)
        
        if ok and search_term:
            if not self.main_window.steam_cache_manager.normalized_steam_index:
                self.main_window.steam_cache_manager.load_normalized_steam_index()
            
            try:
                from Python.ui.name_processor import NameProcessor
                release_groups = getattr(self.main_window, 'release_groups_set', set())
                exclude_exe = getattr(self.main_window, 'exclude_exe_set', set())
                name_processor = NameProcessor(release_groups, exclude_exe)
                
                match_name = name_processor.get_match_name(search_term)
                match_data = self.main_window.steam_cache_manager.normalized_steam_index.get(match_name)
                
                if match_data:
                    steam_id = match_data.get("id")
                    steam_name = match_data.get("name")
                    confirm = QMessageBox.question(self, "Steam AppID Found", f"Found: {steam_name}\nAppID: {steam_id}\n\nApply this ID?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
                    if confirm == QMessageBox.StandardButton.Yes:
                        self.table.setItem(row, constants.EditorCols.STEAMID.value, QTableWidgetItem(str(steam_id)))
                        self.main_window._on_editor_table_edited(None)
                else:
                    QMessageBox.information(self, "Not Found", f"No Steam game found matching '{search_term}'")
            except Exception as e:
                print(f"Error searching Steam ID: {e}")

    def search_disc_images_selected(self, row):
        """Search for disc images in the game directory for selected rows."""
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        if row is not None and row >= 0 and row not in selected_rows:
            selected_rows.add(row)
            
        if not selected_rows:
            return

        self.push_undo()
        
        disc_extensions = {'.iso', '.cue', '.bin', '.img', '.mdf', '.nrg', '.gdi', '.cdi', '.vhd', '.vhdx', '.vmdk', '.wbfs', '.cso', '.chd'}
        
        count = 0
        for r in selected_rows:
            real_index = (self.current_page * self.page_size) + r
            if real_index < len(self.filtered_data):
                game = self.filtered_data[real_index]
                directory = game.get('directory', '')
                
                if not directory or not os.path.exists(directory):
                    continue
                
                found_images = []
                try:
                    for root, dirs, files in os.walk(directory):
                        for f in files:
                            if os.path.splitext(f)[1].lower() in disc_extensions:
                                found_images.append(os.path.join(root, f))
                except Exception as e:
                    print(f"Error searching for ISOs in {directory}: {e}")
                    continue
                
                if found_images:
                    game['_found_isos'] = found_images
                    self.table.setCellWidget(r, constants.EditorCols.ISO_PATH.value, 
                        self._create_iso_combo_widget(game.get('iso_path', ''), found_images, r, constants.EditorCols.ISO_PATH.value))
                    count += 1
        
        if count > 0:
            self.main_window.statusBar().showMessage(f"Found disc images for {count} games", 3000)
        else:
            QMessageBox.information(self, "Search Complete", "No disc images found in the scanned directories.")

    def _add_kill_list_menu(self, menu, row):
        """Add context menu items for Kill List."""
        kp_menu = menu.addMenu("Add Common Process")
        
        procs = []
        if os.path.exists(constants.KILLPROCS_SET):
            try:
                with open(constants.KILLPROCS_SET, 'r') as f:
                    procs = [line.strip() for line in f if line.strip()]
            except Exception:
                pass
        
        if not procs:
            kp_menu.addAction("No processes found").setEnabled(False)
        else:
            for proc in procs:
                action = kp_menu.addAction(proc)
                action.triggered.connect(lambda _, p=proc, r=row: self.append_kill_proc(r, p))

        # Governed Executables
        gov_menu = menu.addMenu("Add Governed Executable")
        gov_exes = []
        if os.path.exists(constants.GOVERNED_EXECUTABLES_SET):
            try:
                with open(constants.GOVERNED_EXECUTABLES_SET, 'r') as f:
                    gov_exes = [line.strip() for line in f if line.strip() and not line.startswith('#')]
            except Exception:
                pass
        
        if not gov_exes:
            gov_menu.addAction("No governed executables found").setEnabled(False)
        else:
            gov_exes.sort()
            for exe in gov_exes:
                action = gov_menu.addAction(exe)
                action.triggered.connect(lambda _, p=exe, r=row: self.append_kill_proc(r, p))

        # Add Game Executables from directory
        real_index = (self.current_page * self.page_size) + row
        if real_index < len(self.filtered_data):
            game_data = self.filtered_data[real_index]
            directory = game_data.get('directory', '')
            
            if directory and os.path.exists(directory):
                exe_menu = menu.addMenu("Add Game Executable")
                found_exes = []
                try:
                    for root, dirs, files in os.walk(directory):
                        for f in files:
                            if f.lower().endswith('.exe'):
                                if f not in found_exes:
                                    found_exes.append(f)
                except Exception:
                    pass
                
                if not found_exes:
                    exe_menu.addAction("No executables found").setEnabled(False)
                else:
                    found_exes.sort()
                    for exe in found_exes:
                        action = exe_menu.addAction(exe)
                        action.triggered.connect(lambda _, p=exe, r=row: self.append_kill_proc(r, p))
        
        # Add Clear Kill List option
        menu.addSeparator()
        clear_action = menu.addAction("Clear Kill List")
        clear_action.triggered.connect(lambda: self.clear_kill_list(row))

    def append_kill_proc(self, row, proc):
        """Append a process to the kill list."""
        self.push_undo()
        item = self.table.item(row, constants.EditorCols.KILL_LIST.value)
        current_text = item.text() if item else ""
        
        # Avoid duplicates if possible, or just append
        current_list = [p.strip() for p in current_text.split(',')] if current_text else []
        if proc not in current_list:
            current_list.append(proc)
            new_text = ",".join(current_list)
            if not item:
                item = QTableWidgetItem()
                self.table.setItem(row, constants.EditorCols.KILL_LIST.value, item)
            item.setText(new_text)
            self.main_window._on_editor_table_edited(None)

    def clear_kill_list(self, row):
        """Clear the kill list for the specified row."""
        self.push_undo()
        item = self.table.item(row, constants.EditorCols.KILL_LIST.value)
        if item:
            item.setText("")
            item.setCheckState(Qt.CheckState.Unchecked)
            self._sync_cell_to_data(row, constants.EditorCols.KILL_LIST.value)
            self.main_window._on_editor_table_edited(None)

    def reset_row(self, row):
        """Reset the row to its original state."""
        self.push_undo()
        if 0 <= row < len(self.original_data):
            reply = QMessageBox.question(
                self, "Confirm Reset",
                "Are you sure you want to reset this row to its original state?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

            game_data = self.original_data[row]
            # Recalculate duplicates for this single row update
            all_names = [g.get('name_override', '').strip() for g in self.original_data if g.get('name_override', '').strip() and g.get('create', False)]
            counts = collections.Counter(all_names)
            duplicates = {name for name, count in counts.items() if count > 1}
            
            self._populate_row(row, copy.deepcopy(game_data), duplicates)
            self.main_window._on_editor_table_edited(None)

    def on_cell_clicked(self, row, column):
        """Handle left click on a cell."""
        self.main_window._on_editor_table_cell_left_click(row, column)

    def on_item_changed(self, item):
        """Handle changes to table items."""
        if item.column() == constants.EditorCols.ISO_PATH.value:
            text = item.text()
            sanitized = self._sanitize_path_string(text, allow_prefix=False)
            if text != sanitized:
                self.table.blockSignals(True)
                item.setText(sanitized)
                self.table.blockSignals(False)

        if not self.table.signalsBlocked():
            self._sync_cell_to_data(item.row(), item.column())
            # Trigger styling update
            real_index = (self.current_page * self.page_size) + item.row()
            if real_index < len(self.filtered_data):
                self._apply_styling(item.row(), self.filtered_data[real_index])
        self.main_window._on_editor_table_edited(item)
        self.data_changed.emit()

    def _create_checkbox_widget(self, checked: bool, row: int, col: int) -> QWidget:
        """Create a centered checkbox widget for table cells."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        checkbox = QCheckBox()
        checkbox.setChecked(checked)
        checkbox.stateChanged.connect(lambda state: self._on_checkbox_changed(row, col, state))
        layout.addWidget(checkbox)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        return widget

    def _create_merged_path_widget(self, enabled: bool, path_text: str, overwrite: bool, row: int, col: int) -> QWidget:
        """Create a merged widget with Enabled checkbox, Path label, and Overwrite checkbox."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(6)
        
        cb_enabled = QCheckBox()
        cb_enabled.setChecked(enabled)
        cb_enabled.setToolTip("Enable")
        
        line_edit = QLineEdit(path_text if enabled else "")  # Show empty if disabled
        line_edit.setToolTip(path_text if enabled else "")
        line_edit.setEnabled(enabled)  # Disable line edit when checkbox is unchecked
        line_edit.textChanged.connect(lambda: self._sanitize_widget_text(line_edit))
        line_edit.textChanged.connect(lambda text: self._on_merged_widget_changed(row, col))
        line_edit.textChanged.connect(lambda: self._apply_merged_widget_styling(line_edit))
        
        cb_overwrite = QCheckBox()
        cb_overwrite.setChecked(overwrite)
        cb_overwrite.setToolTip("Overwrite")
        cb_overwrite.setEnabled(enabled)  # Disable overwrite checkbox when main checkbox is unchecked
        cb_overwrite.stateChanged.connect(lambda state: self._on_merged_widget_changed(row, col))
        
        # Store original path in widget property for restoration
        widget.setProperty('original_path', path_text)
        
        # Connect enabled checkbox with special handler
        def on_enabled_changed(state):
            is_enabled = state == Qt.CheckState.Checked.value
            line_edit.setEnabled(is_enabled)
            cb_overwrite.setEnabled(is_enabled)
            
            if is_enabled:
                # Restore original path when re-enabled
                original = widget.property('original_path')
                if original:
                    line_edit.setText(original)
            else:
                # Clear path when disabled
                line_edit.setText("")
            
            self._on_merged_widget_changed(row, col)
        
        cb_enabled.stateChanged.connect(on_enabled_changed)
        
        layout.addWidget(cb_enabled)
        layout.addWidget(line_edit, 1)
        layout.addWidget(cb_overwrite)

        # Initial styling check
        self._apply_merged_widget_styling(line_edit)
        
        return widget
    
    def _create_save_path_combo_widget(self, current_value: str, game_data: dict, row: int, col: int) -> QComboBox:
        """Create a combobox populated with discovered save paths from Game.ini."""
        from PyQt6.QtWidgets import QComboBox
        
        combo = QComboBox()
        combo.setEditable(True)
        
        # Get discovered save paths from game data (if available)
        discovered_saves = []
        
        # Try to get from pcgw_data if available
        pcgw_data = game_data.get('pcgw_data', {})
        if pcgw_data:
            save_locations = pcgw_data.get('save_locations', {})
            # Get Windows saves (could be extended to other platforms)
            windows_saves = save_locations.get('Windows', [])
            for save_entry in windows_saves:
                if isinstance(save_entry, dict):
                    path = save_entry.get('path', '')
                    if path:
                        discovered_saves.append(path)
        
        # Add empty option first
        combo.addItem("")
        
        # Add discovered paths
        for save_path in discovered_saves:
            combo.addItem(save_path)
        
        # Set current value
        if current_value:
            # Try to find exact match
            index = combo.findText(current_value)
            if index >= 0:
                combo.setCurrentIndex(index)
            else:
                # Set as custom value
                combo.setEditText(current_value)
        
        # Connect change signal
        combo.currentTextChanged.connect(lambda: self._on_merged_widget_changed(row, col))
        
        return combo

    def _apply_merged_widget_styling(self, line_edit):
        """Apply styling removed - no visual indicators."""
        pass

    def _on_checkbox_changed(self, row, col, state):
        self._sync_cell_to_data(row, col)
        # Trigger styling update
        real_index = (self.current_page * self.page_size) + row
        if real_index < len(self.filtered_data):
            self._apply_styling(row, self.filtered_data[real_index])
        self.data_changed.emit()

    def _on_merged_widget_changed(self, row, col):
        self._sync_cell_to_data(row, col)
        # Trigger styling update
        real_index = (self.current_page * self.page_size) + row
        if real_index < len(self.filtered_data):
            self._apply_styling(row, self.filtered_data[real_index])
        self.data_changed.emit()

    def update_compact_view(self):
        """Hides or shows columns based on the Compact View checkbox."""
        compact = self.compact_view_cb.isChecked()
        
        # Build set of column indices that should stay hidden because
        # their corresponding tool plugin is not enabled.
        tool_hidden_cols = set()
        for tool, col_enums in self.TOOL_COLUMN_MAP.items():
            if tool not in self._enabled_tools:
                for col_enum in col_enums:
                    tool_hidden_cols.add(col_enum.value)
        
        # Groups of columns: (Path Column, [List of columns to hide if Path is empty OR Compact is on])
        # For Compact mode, we hide the extra columns regardless.
        # We also hide the Path column if it's empty for ALL visible rows.
        # Columns for disabled tools are always hidden regardless of compact state.
        
        groups = [
            (constants.EditorCols.CM_PATH, [constants.EditorCols.CM_OPTIONS, constants.EditorCols.CM_ARGUMENTS, constants.EditorCols.CM_RUN_WAIT]),
            (constants.EditorCols.BW_PATH, [constants.EditorCols.BW_OPTIONS, constants.EditorCols.BW_ARGUMENTS, constants.EditorCols.BW_RUN_WAIT]),
            (constants.EditorCols.JA_PATH, [constants.EditorCols.JA_OPTIONS, constants.EditorCols.JA_ARGUMENTS, constants.EditorCols.JA_RUN_WAIT]),
            (constants.EditorCols.JB_PATH, [constants.EditorCols.JB_OPTIONS, constants.EditorCols.JB_ARGUMENTS, constants.EditorCols.JB_RUN_WAIT]),
            (constants.EditorCols.PRE1_PATH, [constants.EditorCols.PRE1_OPTIONS, constants.EditorCols.PRE1_ARGUMENTS, constants.EditorCols.PRE1_RUN_WAIT]),
            (constants.EditorCols.POST1_PATH, [constants.EditorCols.POST1_OPTIONS, constants.EditorCols.POST1_ARGUMENTS, constants.EditorCols.POST1_RUN_WAIT]),
            (constants.EditorCols.PRE2_PATH, [constants.EditorCols.PRE2_OPTIONS, constants.EditorCols.PRE2_ARGUMENTS, constants.EditorCols.PRE2_RUN_WAIT]),
            (constants.EditorCols.POST2_PATH, [constants.EditorCols.POST2_OPTIONS, constants.EditorCols.POST2_ARGUMENTS, constants.EditorCols.POST2_RUN_WAIT]),
            (constants.EditorCols.PRE3_PATH, [constants.EditorCols.PRE3_OPTIONS, constants.EditorCols.PRE3_ARGUMENTS, constants.EditorCols.PRE3_RUN_WAIT]),
            (constants.EditorCols.POST3_PATH, [constants.EditorCols.POST3_OPTIONS, constants.EditorCols.POST3_ARGUMENTS, constants.EditorCols.POST3_RUN_WAIT]),
            (constants.EditorCols.DM_PATH, [constants.EditorCols.DM_OPTIONS, constants.EditorCols.DM_ARGUMENTS, constants.EditorCols.DM_RUN_WAIT]),
            (constants.EditorCols.AUDIO_APP_PATH, [constants.EditorCols.AUDIO_APP_OPTIONS, constants.EditorCols.AUDIO_APP_ARGUMENTS, constants.EditorCols.AUDIO_APP_RUN_WAIT]),
            (constants.EditorCols.MONITORAPP_PATH, [constants.EditorCols.MONITORAPP_OPTIONS, constants.EditorCols.MONITORAPP_ARGUMENTS, constants.EditorCols.MONITORAPP_RUN_WAIT]),
        ]
        # Launcher Executable group
        groups.append((constants.EditorCols.LAUNCHER_EXE, [constants.EditorCols.LAUNCHER_EXE_OPTIONS, constants.EditorCols.LAUNCHER_EXE_ARGUMENTS]))
        # Config file groups (no run_wait columns)
        groups.append((constants.EditorCols.DM_MOUNT_CFG, [constants.EditorCols.DM_MOUNT_CFG_OPTIONS, constants.EditorCols.DM_MOUNT_CFG_ARGUMENTS]))
        groups.append((constants.EditorCols.DM_UNMOUNT_CFG, [constants.EditorCols.DM_UNMOUNT_CFG_OPTIONS, constants.EditorCols.DM_UNMOUNT_CFG_ARGUMENTS]))
        groups.append((constants.EditorCols.UNBORDER_CFG, [constants.EditorCols.UNBORDER_CFG_OPTIONS, constants.EditorCols.UNBORDER_CFG_ARGUMENTS]))
        groups.append((constants.EditorCols.REBORDER_CFG, [constants.EditorCols.REBORDER_CFG_OPTIONS, constants.EditorCols.REBORDER_CFG_ARGUMENTS]))
        groups.append((constants.EditorCols.MONITOR_GAME_CFG, [constants.EditorCols.MONITOR_GAME_CFG_OPTIONS, constants.EditorCols.MONITOR_GAME_CFG_ARGUMENTS]))
        groups.append((constants.EditorCols.MONITOR_DESK_CFG, [constants.EditorCols.MONITOR_DESK_CFG_OPTIONS, constants.EditorCols.MONITOR_DESK_CFG_ARGUMENTS]))
        groups.append((constants.EditorCols.PLAYER1_PROFILE, [constants.EditorCols.PLAYER1_PROFILE_OPTIONS, constants.EditorCols.PLAYER1_PROFILE_ARGUMENTS]))
        groups.append((constants.EditorCols.PLAYER2_PROFILE, [constants.EditorCols.PLAYER2_PROFILE_OPTIONS, constants.EditorCols.PLAYER2_PROFILE_ARGUMENTS]))
        groups.append((constants.EditorCols.DESK_PROFILE, [constants.EditorCols.DESK_PROFILE_OPTIONS, constants.EditorCols.DESK_PROFILE_ARGUMENTS]))
        groups.append((constants.EditorCols.AUDIO_GAME_CFG, [constants.EditorCols.AUDIO_GAME_CFG_OPTIONS, constants.EditorCols.AUDIO_GAME_CFG_ARGUMENTS]))
        groups.append((constants.EditorCols.AUDIO_DESK_CFG, [constants.EditorCols.AUDIO_DESK_CFG_OPTIONS, constants.EditorCols.AUDIO_DESK_CFG_ARGUMENTS]))

        for path_col_enum, extra_cols_enums in groups:
            path_col = path_col_enum.value
            extra_cols = [c.value for c in extra_cols_enums]
            
            # Check if path column is empty for all visible rows
            is_empty = True
            if compact:
                for row in range(self.table.rowCount()):
                    widget = self.table.cellWidget(row, path_col)
                    if widget:
                        le = widget.findChild(QLineEdit)
                        if le and le.text().strip().lstrip('<> '):
                            is_empty = False
                            break
            
            # Hide extras if compact (unless tool-disabled)
            for col in extra_cols:
                if col in tool_hidden_cols:
                    self.table.setColumnHidden(col, True)
                else:
                    self.table.setColumnHidden(col, compact)
            
            # Hide path if compact AND empty (unless tool-disabled)
            if path_col in tool_hidden_cols:
                self.table.setColumnHidden(path_col, True)
            else:
                self.table.setColumnHidden(path_col, compact and is_empty)

    # ── Tool (plugin) gated column visibility ────────────────────── #
    TOOL_COLUMN_MAP = {
        'monitor': [
            constants.EditorCols.MONITORAPP_PATH, constants.EditorCols.MONITORAPP_OPTIONS,
            constants.EditorCols.MONITORAPP_ARGUMENTS, constants.EditorCols.MONITORAPP_RUN_WAIT,
        ],
        'controller_mapper': [
            constants.EditorCols.CM_PATH, constants.EditorCols.CM_OPTIONS,
            constants.EditorCols.CM_ARGUMENTS, constants.EditorCols.CM_RUN_WAIT,
        ],
        'borderless_window': [
            constants.EditorCols.BW_PATH, constants.EditorCols.BW_OPTIONS,
            constants.EditorCols.BW_ARGUMENTS, constants.EditorCols.BW_RUN_WAIT,
            constants.EditorCols.UNBORDER_CFG, constants.EditorCols.UNBORDER_CFG_OPTIONS,
            constants.EditorCols.UNBORDER_CFG_ARGUMENTS,
            constants.EditorCols.REBORDER_CFG, constants.EditorCols.REBORDER_CFG_OPTIONS,
            constants.EditorCols.REBORDER_CFG_ARGUMENTS,
        ],
        'disc_mount': [
            constants.EditorCols.ISO_PATH,
            constants.EditorCols.DM_PATH, constants.EditorCols.DM_OPTIONS,
            constants.EditorCols.DM_ARGUMENTS, constants.EditorCols.DM_RUN_WAIT,
            constants.EditorCols.DM_MOUNT_CFG, constants.EditorCols.DM_MOUNT_CFG_OPTIONS,
            constants.EditorCols.DM_MOUNT_CFG_ARGUMENTS,
            constants.EditorCols.DM_UNMOUNT_CFG, constants.EditorCols.DM_UNMOUNT_CFG_OPTIONS,
            constants.EditorCols.DM_UNMOUNT_CFG_ARGUMENTS,
        ],
        'audio': [
            constants.EditorCols.AUDIO_APP_PATH, constants.EditorCols.AUDIO_APP_OPTIONS,
            constants.EditorCols.AUDIO_APP_ARGUMENTS, constants.EditorCols.AUDIO_APP_RUN_WAIT,
            constants.EditorCols.AUDIO_GAME_CFG, constants.EditorCols.AUDIO_GAME_CFG_OPTIONS,
            constants.EditorCols.AUDIO_GAME_CFG_ARGUMENTS,
            constants.EditorCols.AUDIO_DESK_CFG, constants.EditorCols.AUDIO_DESK_CFG_OPTIONS,
            constants.EditorCols.AUDIO_DESK_CFG_ARGUMENTS,
        ],
    }

    def set_enabled_tools(self, enabled_tools: set):
        self._enabled_tools = set(enabled_tools)
        self._apply_tool_visibility()

    def _apply_tool_visibility(self):
        """Show/hide columns gated by tool plugin state."""
        for tool, col_enums in self.TOOL_COLUMN_MAP.items():
            visible = tool in self._enabled_tools
            for col_enum in col_enums:
                col = col_enum.value
                self.table.setColumnHidden(col, not visible)
                if not visible:
                    self.table.setColumnWidth(col, 0)
                else:
                    self.table.resizeColumnToContents(col)

    def _sync_cell_to_data(self, row, col):
        """Update the underlying data model from the table widget."""
        real_index = (self.current_page * self.page_size) + row
        if real_index >= len(self.filtered_data):
            return

        game = self.filtered_data[real_index]
        
        # Map column to data key
        if col == constants.EditorCols.INCLUDE.value:
            game['create'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.NAME.value:
            item = self.table.item(row, col)
            game['name'] = item.text() if item else ""
        elif col == constants.EditorCols.DIRECTORY.value:
            item = self.table.item(row, col)
            game['directory'] = item.text() if item else ""
        elif col == constants.EditorCols.STEAMID.value:
            item = self.table.item(row, col)
            game['steam_id'] = item.text() if item else ""
        elif col == constants.EditorCols.NAME_OVERRIDE.value:
            widget = self.table.cellWidget(row, col)  # type: ignore[union-attr]
            if isinstance(widget, QComboBox):
                game['name_override'] = widget.currentText()
            else:
                item = self.table.item(row, col)
                game['name_override'] = item.text() if item else ""
        elif col == constants.EditorCols.OPTIONS.value:
            item = self.table.item(row, col)
            game['options'] = item.text() if item else ""
        elif col == constants.EditorCols.ARGUMENTS.value:
            item = self.table.item(row, col)
            game['arguments'] = item.text() if item else ""
        elif col == constants.EditorCols.RUN_AS_ADMIN.value:
            game['run_as_admin'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.OVERWRITE_INI.value:
            game['overwrite_game_ini'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.RECREATE_INI.value:
            game['recreate_game_ini'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.CM_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['controller_mapper_enabled'] = en
            game['controller_mapper_path'] = path
            game['controller_mapper_overwrite'] = ov
        elif col == constants.EditorCols.CM_OPTIONS.value:
            game['controller_mapper_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.CM_ARGUMENTS.value:
            game['controller_mapper_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.CM_RUN_WAIT.value:
            game['controller_mapper_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.BW_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['borderless_windowing_enabled'] = en
            game['borderless_windowing_path'] = path
            game['borderless_windowing_overwrite'] = ov
        elif col == constants.EditorCols.BW_OPTIONS.value:
            game['borderless_windowing_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.BW_ARGUMENTS.value:
            game['borderless_windowing_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.BW_RUN_WAIT.value:
            game['borderless_windowing_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.HIDE_TASKBAR.value:
            game['hide_taskbar'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.MONITORAPP_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['monitorapp_enabled'] = en
            game['monitorapp_path'] = path
            game['monitorapp_overwrite'] = ov
        elif col == constants.EditorCols.MONITORAPP_OPTIONS.value:
            game['monitorapp_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.MONITORAPP_ARGUMENTS.value:
            game['monitorapp_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.MONITORAPP_RUN_WAIT.value:
            game['monitorapp_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.MONITOR_GAME_CFG.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['monitor_game_cfg_enabled'] = en
            game['monitor_game_cfg'] = path
            game['monitor_game_cfg_overwrite'] = ov
        elif col == constants.EditorCols.MONITOR_DESK_CFG.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['monitor_desk_cfg_enabled'] = en
            game['monitor_desk_cfg'] = path
            game['monitor_desk_cfg_overwrite'] = ov
        elif col == constants.EditorCols.PLAYER1_PROFILE.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['player1_profile_enabled'] = en
            game['player1_profile'] = path
            game['player1_profile_overwrite'] = ov
        elif col == constants.EditorCols.PLAYER2_PROFILE.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['player2_profile_enabled'] = en
            game['player2_profile'] = path
            game['player2_profile_overwrite'] = ov
        elif col == constants.EditorCols.DESK_PROFILE.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['desk_profile_enabled'] = en
            game['desk_profile'] = path
            game['desk_profile_overwrite'] = ov
        elif col == constants.EditorCols.DESK_PROFILE_OPTIONS.value:
            game['desk_profile_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.DESK_PROFILE_ARGUMENTS.value:
            game['desk_profile_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.MONITOR_GAME_CFG_OPTIONS.value:
            game['monitor_game_cfg_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.MONITOR_GAME_CFG_ARGUMENTS.value:
            game['monitor_game_cfg_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.MONITOR_DESK_CFG_OPTIONS.value:
            game['monitor_desk_cfg_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.MONITOR_DESK_CFG_ARGUMENTS.value:
            game['monitor_desk_cfg_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PLAYER1_PROFILE_OPTIONS.value:
            game['player1_profile_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PLAYER1_PROFILE_ARGUMENTS.value:
            game['player1_profile_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PLAYER2_PROFILE_OPTIONS.value:
            game['player2_profile_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PLAYER2_PROFILE_ARGUMENTS.value:
            game['player2_profile_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.JA_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['just_after_launch_enabled'] = en
            game['just_after_launch_path'] = path
            game['just_after_launch_overwrite'] = ov
        elif col == constants.EditorCols.JA_OPTIONS.value:
            game['just_after_launch_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.JA_ARGUMENTS.value:
            game['just_after_launch_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.JA_RUN_WAIT.value:
            game['just_after_launch_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.JB_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['just_before_exit_enabled'] = en
            game['just_before_exit_path'] = path
            game['just_before_exit_overwrite'] = ov
        elif col == constants.EditorCols.JB_OPTIONS.value:
            game['just_before_exit_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.JB_ARGUMENTS.value:
            game['just_before_exit_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.JB_RUN_WAIT.value:
            game['just_before_exit_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.PRE1_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['pre_1_enabled'] = en
            game['pre1_path'] = path
            game['pre_1_overwrite'] = ov
        elif col == constants.EditorCols.PRE1_OPTIONS.value:
            game['pre1_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PRE1_ARGUMENTS.value:
            game['pre1_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PRE1_RUN_WAIT.value:
            game['pre_1_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.POST1_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['post_1_enabled'] = en
            game['post1_path'] = path
            game['post_1_overwrite'] = ov
        elif col == constants.EditorCols.POST1_OPTIONS.value:
            game['post1_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.POST1_ARGUMENTS.value:
            game['post1_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.POST1_RUN_WAIT.value:
            game['post_1_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.PRE2_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['pre_2_enabled'] = en
            game['pre2_path'] = path
            game['pre_2_overwrite'] = ov
        elif col == constants.EditorCols.PRE2_OPTIONS.value:
            game['pre2_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PRE2_ARGUMENTS.value:
            game['pre2_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PRE2_RUN_WAIT.value:
            game['pre_2_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.POST2_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['post_2_enabled'] = en
            game['post2_path'] = path
            game['post_2_overwrite'] = ov
        elif col == constants.EditorCols.POST2_OPTIONS.value:
            game['post2_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.POST2_ARGUMENTS.value:
            game['post2_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.POST2_RUN_WAIT.value:
            game['post_2_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.PRE3_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['pre_3_enabled'] = en
            game['pre3_path'] = path
            game['pre_3_overwrite'] = ov
        elif col == constants.EditorCols.PRE3_OPTIONS.value:
            game['pre3_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PRE3_ARGUMENTS.value:
            game['pre3_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.PRE3_RUN_WAIT.value:
            game['pre_3_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.POST3_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['post_3_enabled'] = en
            game['post3_path'] = path
            game['post_3_overwrite'] = ov
        elif col == constants.EditorCols.POST3_OPTIONS.value:
            game['post3_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.POST3_ARGUMENTS.value:
            game['post3_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.POST3_RUN_WAIT.value:
            game['post_3_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.KILL_LIST.value:
            item = self.table.item(row, col)
            if item:
                game['kill_list_enabled'] = (item.checkState() == Qt.CheckState.Checked)
                game['kill_list'] = item.text()
        elif col == constants.EditorCols.LAUNCHER_EXE.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['launcher_executable_enabled'] = en
            game['launcher_executable'] = path
            game['launcher_executable_overwrite'] = ov
        elif col == constants.EditorCols.LAUNCHER_EXE_OPTIONS.value:
            game['launcher_executable_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.LAUNCHER_EXE_ARGUMENTS.value:
            game['launcher_executable_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.ISO_PATH.value:
            widget = self.table.cellWidget(row, col)  # type: ignore[union-attr]
            if widget:
                combo = widget.findChild(QComboBox)
                if combo:
                    game['iso_path'] = combo.currentText()
                else:
                    le = widget.findChild(QLineEdit)
                    if le: game['iso_path'] = le.text()
            else:
                item = self.table.item(row, col)
                if item: game['iso_path'] = item.text()
        
        # Audio App columns
        elif col == constants.EditorCols.AUDIO_APP_PATH.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['audio_app_enabled'] = en
            game['audio_app_path'] = path
            game['audio_app_overwrite'] = ov
        elif col == constants.EditorCols.AUDIO_APP_OPTIONS.value:
            item = self.table.item(row, col)
            game['audio_app_options'] = item.text() if item else ""
        elif col == constants.EditorCols.AUDIO_APP_ARGUMENTS.value:
            item = self.table.item(row, col)
            game['audio_app_arguments'] = item.text() if item else ""
        elif col == constants.EditorCols.AUDIO_APP_RUN_WAIT.value:
            game['audio_app_run_wait'] = self._get_checkbox_value(row, col)
        elif col == constants.EditorCols.UNBORDER_CFG.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['unborder_cfg_enabled'] = en
            game['unborder_cfg'] = path
            game['unborder_cfg_overwrite'] = ov
        elif col == constants.EditorCols.UNBORDER_CFG_OPTIONS.value:
            game['unborder_cfg_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.UNBORDER_CFG_ARGUMENTS.value:
            game['unborder_cfg_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.REBORDER_CFG.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['reborder_cfg_enabled'] = en
            game['reborder_cfg'] = path
            game['reborder_cfg_overwrite'] = ov
        elif col == constants.EditorCols.REBORDER_CFG_OPTIONS.value:
            game['reborder_cfg_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.REBORDER_CFG_ARGUMENTS.value:
            game['reborder_cfg_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.AUDIO_GAME_CFG.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['audio_game_cfg_enabled'] = en
            game['audio_game_cfg'] = path
            game['audio_game_cfg_overwrite'] = ov
        elif col == constants.EditorCols.AUDIO_GAME_CFG_OPTIONS.value:
            game['audio_game_cfg_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.AUDIO_GAME_CFG_ARGUMENTS.value:
            game['audio_game_cfg_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.AUDIO_DESK_CFG.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['audio_desk_cfg_enabled'] = en
            game['audio_desk_cfg'] = path
            game['audio_desk_cfg_overwrite'] = ov
        elif col == constants.EditorCols.AUDIO_DESK_CFG_OPTIONS.value:
            game['audio_desk_cfg_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.AUDIO_DESK_CFG_ARGUMENTS.value:
            game['audio_desk_cfg_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.DM_MOUNT_CFG.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['disc_mount_cfg_enabled'] = en
            game['disc_mount_cfg'] = path
            game['disc_mount_cfg_overwrite'] = ov
        elif col == constants.EditorCols.DM_MOUNT_CFG_OPTIONS.value:
            game['disc_mount_cfg_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.DM_MOUNT_CFG_ARGUMENTS.value:
            game['disc_mount_cfg_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.DM_UNMOUNT_CFG.value:
            en, path, ov = self._get_merged_path_data(row, col)
            game['disc_unmount_cfg_enabled'] = en
            game['disc_unmount_cfg'] = path
            game['disc_unmount_cfg_overwrite'] = ov
        elif col == constants.EditorCols.DM_UNMOUNT_CFG_OPTIONS.value:
            game['disc_unmount_cfg_options'] = self.table.item(row, col).text()  # type: ignore[union-attr]
        elif col == constants.EditorCols.DM_UNMOUNT_CFG_ARGUMENTS.value:
            game['disc_unmount_cfg_arguments'] = self.table.item(row, col).text()  # type: ignore[union-attr]

    def swap_lc_cen_selected(self):
        """Swap between LC (>) and CEN (<) for selected path cells."""
        self.push_undo()
        path_cols = [
            constants.EditorCols.CM_PATH, constants.EditorCols.BW_PATH,
            constants.EditorCols.UNBORDER_CFG, constants.EditorCols.UNBORDER_CFG_OPTIONS, constants.EditorCols.UNBORDER_CFG_ARGUMENTS,
            constants.EditorCols.REBORDER_CFG, constants.EditorCols.REBORDER_CFG_OPTIONS, constants.EditorCols.REBORDER_CFG_ARGUMENTS,
            constants.EditorCols.MONITOR_GAME_CFG, constants.EditorCols.MONITOR_GAME_CFG_OPTIONS, constants.EditorCols.MONITOR_GAME_CFG_ARGUMENTS,
            constants.EditorCols.MONITOR_DESK_CFG, constants.EditorCols.MONITOR_DESK_CFG_OPTIONS, constants.EditorCols.MONITOR_DESK_CFG_ARGUMENTS,
            constants.EditorCols.PLAYER1_PROFILE, constants.EditorCols.PLAYER1_PROFILE_OPTIONS, constants.EditorCols.PLAYER1_PROFILE_ARGUMENTS,
            constants.EditorCols.PLAYER2_PROFILE, constants.EditorCols.PLAYER2_PROFILE_OPTIONS, constants.EditorCols.PLAYER2_PROFILE_ARGUMENTS,
            constants.EditorCols.DESK_PROFILE, constants.EditorCols.DESK_PROFILE_OPTIONS, constants.EditorCols.DESK_PROFILE_ARGUMENTS,
            constants.EditorCols.JA_PATH, constants.EditorCols.JB_PATH,
            constants.EditorCols.PRE1_PATH, constants.EditorCols.POST1_PATH,
            constants.EditorCols.PRE2_PATH, constants.EditorCols.POST2_PATH,
            constants.EditorCols.PRE3_PATH, constants.EditorCols.POST3_PATH,
            constants.EditorCols.LAUNCHER_EXE,
            constants.EditorCols.DM_MOUNT_CFG, constants.EditorCols.DM_UNMOUNT_CFG,
            constants.EditorCols.AUDIO_APP_PATH,
            constants.EditorCols.MONITORAPP_PATH
        ]
        
        for row in range(self.table.rowCount()):
            for col_enum in path_cols:
                if self.table.item(row, col_enum.value) and self.table.item(row, col_enum.value).isSelected():
                    # Item based selection not applicable for widgets, check cell widget focus or selection model
                    pass
        
        # Better approach: Iterate selected ranges
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                for c in range(range_.leftColumn(), range_.rightColumn() + 1):
                    if any(c == pc.value for pc in path_cols):
                        self._swap_lc_cen_cell(r, c)
        self.main_window._on_editor_table_edited(None)

    def restore_defaults_selected(self):
        """Restore default options and arguments for selected rows."""
        self.push_undo()
        selected_rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                selected_rows.add(r)
        
        if not selected_rows:
            return

        config = self.main_window.config
        
        # Map of data keys to config attributes
        defaults_map = {
            'controller_mapper_options': 'controller_mapper_path_options',
            'controller_mapper_arguments': 'controller_mapper_path_arguments',
            'borderless_windowing_options': 'borderless_gaming_path_options',
            'borderless_windowing_arguments': 'borderless_gaming_path_arguments',
            'monitorapp_options': 'monitorapp_options',
            'monitorapp_arguments': 'monitorapp_arguments',
            'just_after_launch_options': 'just_after_launch_path_options',
            'just_after_launch_arguments': 'just_after_launch_path_arguments',
            'just_before_exit_options': 'just_before_exit_path_options',
            'just_before_exit_arguments': 'just_before_exit_path_arguments',
            'pre1_options': 'pre1_path_options', 'pre1_arguments': 'pre1_path_arguments',
            'pre2_options': 'pre2_path_options', 'pre2_arguments': 'pre2_path_arguments',
            'pre3_options': 'pre3_path_options', 'pre3_arguments': 'pre3_path_arguments',
            'post1_options': 'post1_path_options', 'post1_arguments': 'post1_path_arguments',
            'post2_options': 'post2_path_options', 'post2_arguments': 'post2_path_arguments',
            'post3_options': 'post3_path_options', 'post3_arguments': 'post3_path_arguments',
            'launcher_executable_options': 'launcher_executable_options',
            'launcher_executable_arguments': 'launcher_executable_arguments',
            'audio_app_options': 'audio_app_path_options',
            'audio_app_arguments': 'audio_app_path_arguments'
        }

        for row in selected_rows:
            real_index = (self.current_page * self.page_size) + row
            if real_index < len(self.filtered_data):
                game = self.filtered_data[real_index]
                for game_key, config_attr in defaults_map.items():
                    # Reset to default value from config
                    game[game_key] = getattr(config, config_attr, "")
                
                # Refresh the row in the table
                self._populate_row(row, game, set()) # Duplicates set empty for speed, styling might be slightly off until refresh
        self.main_window._on_editor_table_edited(None)

    def _sanitize_path_string(self, text, allow_prefix=True):
        """Removes invalid characters from path string."""
        prefix = ""
        content = text
        
        if allow_prefix:
            if text.startswith("< "):
                prefix = "< "
                content = text[2:]
            elif text.startswith("> "):
                prefix = "> "
                content = text[2:]
        
        for char in ['?', '*', '<', '>', '|', '"']:
            content = content.replace(char, '')
            
        return prefix + content

    def _sanitize_widget_text(self, line_edit):
        """Sanitizes text in a QLineEdit."""
        text = line_edit.text()
        sanitized = self._sanitize_path_string(text, allow_prefix=True)
        if text != sanitized:
            cursor = line_edit.cursorPosition()
            line_edit.setText(sanitized)
            line_edit.setCursorPosition(max(0, cursor - (len(text) - len(sanitized))))

    def _update_widget_state(self, row, col, value):
        """Update a widget's visual state without triggering data sync."""
        self.table.blockSignals(True)
        self.frozen_table.blockSignals(True)
        if col == constants.EditorCols.INCLUDE.value:
            widget = self.frozen_table.cellWidget(row, 0)  # type: ignore[union-attr]
            if widget:
                cb = widget.findChild(QCheckBox)
                if cb: cb.setChecked(value)
        self.frozen_table.blockSignals(False)
        self.table.blockSignals(False)

    def _get_checkbox_value(self, row: int, col: int) -> bool:
        """Get checkbox value from a cell widget."""
        target_table = self.frozen_table if col == constants.EditorCols.INCLUDE.value else self.table
        widget = target_table.cellWidget(row, col if col != constants.EditorCols.INCLUDE.value else 0)  # type: ignore[union-attr]
        if widget:
            checkbox = widget.findChild(QCheckBox)
            if checkbox:
                return checkbox.isChecked()
        return False

    def _get_merged_path_data(self, row: int, col: int):
        """Extract enabled, path, and overwrite from a merged widget."""
        widget = self.table.cellWidget(row, col)  # type: ignore[union-attr]
        if widget:
            cbs = widget.findChildren(QCheckBox)
            enabled = cbs[0].isChecked() if len(cbs) > 0 else False
            overwrite = cbs[1].isChecked() if len(cbs) > 1 else False
            le = widget.findChild(QLineEdit)
            path = le.text() if le else ""
            
            # If checkbox is unchecked, return empty path to prevent propagation
            if not enabled:
                path = ""
            
            return enabled, path, overwrite
        return False, "", False

    def _swap_lc_cen_cell(self, row, col):
        widget = self.table.cellWidget(row, col)  # type: ignore[union-attr]
        if widget:
            le = widget.findChild(QLineEdit)
            if le:
                text = le.text()
                if text.startswith("> "):
                    le.setText("< " + text[2:])
                elif text.startswith("< "):
                    le.setText("> " + text[2:])
                self._sync_cell_to_data(row, col)

    def _check_widget_large_lc(self, widget):
        le = widget.findChild(QLineEdit)
        if le:
            text = le.text()
            if text.startswith("> "):
                path = text[2:]
                return path and os.path.exists(path) and os.path.isfile(path) and os.path.getsize(path) > 10 * 1024 * 1024
        return False

    def _get_propagation_symbol_and_run_wait(self, config_key):
        """Get propagation status symbol (< or >) and default run_wait state from config"""
        config = self.main_window.config
        # Get the propagation mode (CEN or LC)
        mode = config.deployment_path_modes.get(config_key, 'CEN')
        symbol = '<' if mode == 'CEN' else '>'
        
        # Get the run_wait default state
        run_wait_key = f"{config_key}_run_wait"
        run_wait = config.run_wait_states.get(run_wait_key, False)
        
        return symbol, run_wait

    def populate_from_data(self, data):
        """Populate the table with data."""
        if not data:
            return

        # Incremental Update: Merge with existing data based on path
        existing_paths = {os.path.normpath(os.path.join(g.get('directory', ''), g.get('name', ''))).lower() 
                          for g in self.original_data}
        
        new_entries = []
        sanitized_data = self._sanitize_data_for_display(data)
        for game in sanitized_data:
            path = os.path.normpath(os.path.join(game.get('directory', ''), game.get('name', ''))).lower()
            if path not in existing_paths:
                new_entries.append(copy.deepcopy(game))
                existing_paths.add(path)
        
        if new_entries:
            self.original_data.extend(new_entries)
            
        self.filtered_data = self.original_data
        self.refresh_view()
    
    def _sanitize_data_for_display(self, data):
        """Sanitize data by clearing paths for disabled items."""
        sanitized = copy.deepcopy(data)
        
        path_enabled_pairs = [
            ('controller_mapper_path', 'controller_mapper_enabled'),
            ('borderless_windowing_path', 'borderless_windowing_enabled'),
            ('monitorapp_path', 'monitorapp_enabled'),
            ('just_after_launch_path', 'just_after_launch_enabled'),
            ('just_before_exit_path', 'just_before_exit_enabled'),
            ('pre1_path', 'pre_1_enabled'),
            ('pre2_path', 'pre_2_enabled'),
            ('pre3_path', 'pre_3_enabled'),
            ('post1_path', 'post_1_enabled'),
            ('post2_path', 'post_2_enabled'),
            ('post3_path', 'post_3_enabled'),
            ('player1_profile', 'player1_profile_enabled'),
            ('player2_profile', 'player2_profile_enabled'),
            ('desk_profile', 'desk_profile_enabled'),
            ('monitor_game_cfg', 'monitor_game_cfg_enabled'),
            ('monitor_desk_cfg', 'monitor_desk_cfg_enabled'),
            ('launcher_executable', 'launcher_executable_enabled'),
            ('disc_mount_path', 'disc_mount_enabled'),
            ('audio_app_path', 'audio_app_enabled'),
            ('unborder_cfg', 'unborder_cfg_enabled'),
            ('reborder_cfg', 'reborder_cfg_enabled'),
        ]
        
        for game in sanitized:
            for path_key, enabled_key in path_enabled_pairs:
                if not game.get(enabled_key, True):
                    game[path_key] = ""
        
        return sanitized

    def _populate_row(self, row_num, game, duplicates):
        """Populate a single row with game data."""
        self.table.blockSignals(True) # Block signals during population
        
        def get_path_display(key, config_key):
            val = game.get(key, '')
            if not val: return ""
            if val.startswith('> ') or val.startswith('< '):
                return val
            symbol, _ = self._get_propagation_symbol_and_run_wait(config_key)
            return f"{symbol} {val.lstrip('<> ')}"

        # Create (CheckBox) - col INCLUDE (frozen column)
        self.frozen_table.setCellWidget(row_num, 0, self._create_checkbox_widget(game.get('create', False), row_num, constants.EditorCols.INCLUDE.value))

        # Name (uneditable) - col NAME
        name_item = QTableWidgetItem(game.get('name', ''))
        name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        
        # Tooltip for file size, date modified, file version, and index date
        try:
            full_path = os.path.join(game.get('directory', ''), game.get('name', ''))
            tooltip_parts = []
            if os.path.exists(full_path):
                size = os.path.getsize(full_path)
                for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
                    if size < 1024:
                        break
                    size /= 1024
                tooltip_parts.append(f"File Size: {size:.2f} {unit}")

                # Date modified
                try:
                    mtime = os.path.getmtime(full_path)
                    mtime_str = datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
                    tooltip_parts.append(f"Date Modified: {mtime_str}")
                except Exception:
                    pass

                # File version (Windows PE resources)
                if full_path.lower().endswith('.exe'):
                    try:
                        import win32api
                        info = win32api.GetFileVersionInfo(full_path, '\\')
                        ms = info['FileVersionMS']
                        ls = info['FileVersionLS']
                        version_str = f"{ms >> 16}.{ms & 0xFFFF}.{ls >> 16}.{ls & 0xFFFF}"
                        tooltip_parts.append(f"File Version: {version_str}")
                    except ImportError:
                        pass  # pywin32 not available
                    except Exception:
                        pass  # Version info not present in this exe
            else:
                tooltip_parts.append("File not found")
            
            date_indexed = game.get('date_indexed', 'Unknown')
            if date_indexed != 'Unknown':
                try:
                    # Format: YYYY-MM-DD HH:MM
                    dt = datetime.datetime.fromisoformat(date_indexed)
                    display_date = dt.strftime("%Y-%m-%d %H:%M")
                    tooltip_parts.append(f"Indexed: {display_date}")
                except Exception:
                    tooltip_parts.append(f"Indexed: {date_indexed}")
                
            name_item.setToolTip("\n".join(tooltip_parts))
        except Exception:
            pass
            
        self.table.setItem(row_num, constants.EditorCols.NAME.value, name_item)

        # Directory (uneditable) - col DIRECTORY
        directory_path = game.get('directory', '')
        dir_item = QTableWidgetItem(directory_path)
        dir_item.setFlags(dir_item.flags() & ~Qt.ItemFlag.ItemIsEditable)  # Make it uneditable
        dir_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.table.setItem(row_num, constants.EditorCols.DIRECTORY.value, dir_item)

        # SteamID - col STEAMID
        steam_id_value = game.get('steam_id', 'NOT_FOUND_IN_DATA')
        self.table.setItem(row_num, constants.EditorCols.STEAMID.value, QTableWidgetItem(str(steam_id_value)))

        # NameOverride - col NAME_OVERRIDE
        fuzzy_matches = game.get('_fuzzy_matches')
        if fuzzy_matches:
            combo = QComboBox()
            combo.setEditable(True)
            combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
            
            # Add original name as first item
            original_name = game.get('name_override', '')
            combo.addItem(original_name, None)
            
            # Add fuzzy matches
            for match_key in fuzzy_matches:
                match_data = self.main_window.steam_cache_manager.normalized_steam_index.get(match_key)
                if match_data:
                    combo.addItem(f"{match_data['name']}", match_data.get('id'))
            
            combo.currentIndexChanged.connect(lambda _, c=combo, r_idx=row_num: self._on_fuzzy_combo_changed(c, r_idx))
            combo.editTextChanged.connect(lambda _, c=combo, r_idx=row_num: self._on_fuzzy_combo_changed(c, r_idx))
            self.table.setCellWidget(row_num, constants.EditorCols.NAME_OVERRIDE.value, combo)
        else:
            self.table.setItem(row_num, constants.EditorCols.NAME_OVERRIDE.value, QTableWidgetItem(game.get('name_override', '')))

        # Options - col OPTIONS
        self.table.setItem(row_num, constants.EditorCols.OPTIONS.value, QTableWidgetItem(game.get('options', '')))

        # Arguments - col ARGUMENTS
        self.table.setItem(row_num, constants.EditorCols.ARGUMENTS.value, QTableWidgetItem(game.get('arguments', '')))

        # RunAsAdmin (CheckBox) - col RUN_AS_ADMIN
        self.table.setCellWidget(row_num, constants.EditorCols.RUN_AS_ADMIN.value, self._create_checkbox_widget(game.get('run_as_admin', False), row_num, constants.EditorCols.RUN_AS_ADMIN.value))

        # Overwrite Game.ini (CheckBox) - col OVERWRITE_INI
        self.table.setCellWidget(row_num, constants.EditorCols.OVERWRITE_INI.value, self._create_checkbox_widget(game.get('overwrite_game_ini', True), row_num, constants.EditorCols.OVERWRITE_INI.value))

        # Recreate Game.ini (CheckBox) - col RECREATE_INI
        self.table.setCellWidget(row_num, constants.EditorCols.RECREATE_INI.value, self._create_checkbox_widget(game.get('recreate_game_ini', True), row_num, constants.EditorCols.RECREATE_INI.value))

        # Controller Mapper (CheckBox, Path with symbol, RunWait)
        # Merged widget for Path column
        cm_symbol, cm_run_wait = self._get_propagation_symbol_and_run_wait('controller_mapper_path')
        cm_path = f"{cm_symbol} {game.get('controller_mapper_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.CM_PATH.value, self._create_merged_path_widget(game.get('controller_mapper_enabled', True), cm_path, game.get('controller_mapper_overwrite', True), row_num, constants.EditorCols.CM_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.CM_OPTIONS.value, QTableWidgetItem(game.get('controller_mapper_options', '')))
        self.table.setItem(row_num, constants.EditorCols.CM_ARGUMENTS.value, QTableWidgetItem(game.get('controller_mapper_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.CM_RUN_WAIT.value, self._create_checkbox_widget(game.get('controller_mapper_run_wait', cm_run_wait), row_num, constants.EditorCols.CM_RUN_WAIT.value))

        # Borderless Windowing (CheckBox, Path with symbol, RunWait)
        bw_symbol, bw_run_wait = self._get_propagation_symbol_and_run_wait('borderless_gaming_path')
        bw_path = f"{bw_symbol} {game.get('borderless_windowing_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.BW_PATH.value, self._create_merged_path_widget(game.get('borderless_windowing_enabled', True), bw_path, game.get('borderless_windowing_overwrite', True), row_num, constants.EditorCols.BW_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.BW_OPTIONS.value, QTableWidgetItem(game.get('borderless_windowing_options', '')))
        self.table.setItem(row_num, constants.EditorCols.BW_ARGUMENTS.value, QTableWidgetItem(game.get('borderless_windowing_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.BW_RUN_WAIT.value, self._create_checkbox_widget(game.get('borderless_windowing_run_wait', bw_run_wait), row_num, constants.EditorCols.BW_RUN_WAIT.value))
        
        # Hide Taskbar (CheckBox)
        self.table.setCellWidget(row_num, constants.EditorCols.HIDE_TASKBAR.value, self._create_checkbox_widget(game.get('hide_taskbar', False), row_num, constants.EditorCols.HIDE_TASKBAR.value))

        # Monitor-Config App (merged path, opts, args, run_wait)
        monitor_symbol, monitor_run_wait = self._get_propagation_symbol_and_run_wait('monitorapp_path')
        monitorapp_path = f"{monitor_symbol} {game.get('monitorapp_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.MONITORAPP_PATH.value, self._create_merged_path_widget(game.get('monitorapp_enabled', True), monitorapp_path, game.get('monitorapp_overwrite', True), row_num, constants.EditorCols.MONITORAPP_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.MONITORAPP_OPTIONS.value, QTableWidgetItem(game.get('monitorapp_options', '')))
        self.table.setItem(row_num, constants.EditorCols.MONITORAPP_ARGUMENTS.value, QTableWidgetItem(game.get('monitorapp_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.MONITORAPP_RUN_WAIT.value, self._create_checkbox_widget(game.get('monitorapp_run_wait', monitor_run_wait), row_num, constants.EditorCols.MONITORAPP_RUN_WAIT.value))

        # Profiles with propagation symbols
        monitor_game_cfg = get_path_display('monitor_game_cfg', 'monitor_game_path')
        self.table.setCellWidget(row_num, constants.EditorCols.MONITOR_GAME_CFG.value, self._create_merged_path_widget(game.get('monitor_game_cfg_enabled', True), monitor_game_cfg, game.get('monitor_game_cfg_overwrite', True), row_num, constants.EditorCols.MONITOR_GAME_CFG.value))
        self.table.setItem(row_num, constants.EditorCols.MONITOR_GAME_CFG_OPTIONS.value, QTableWidgetItem(game.get('monitor_game_cfg_options', '')))
        self.table.setItem(row_num, constants.EditorCols.MONITOR_GAME_CFG_ARGUMENTS.value, QTableWidgetItem(game.get('monitor_game_cfg_arguments', '')))
        
        monitor_desk_cfg = get_path_display('monitor_desk_cfg', 'monitor_desk_path')
        self.table.setCellWidget(row_num, constants.EditorCols.MONITOR_DESK_CFG.value, self._create_merged_path_widget(game.get('monitor_desk_cfg_enabled', True), monitor_desk_cfg, game.get('monitor_desk_cfg_overwrite', True), row_num, constants.EditorCols.MONITOR_DESK_CFG.value))
        self.table.setItem(row_num, constants.EditorCols.MONITOR_DESK_CFG_OPTIONS.value, QTableWidgetItem(game.get('monitor_desk_cfg_options', '')))
        self.table.setItem(row_num, constants.EditorCols.MONITOR_DESK_CFG_ARGUMENTS.value, QTableWidgetItem(game.get('monitor_desk_cfg_arguments', '')))
        
        player1_profile = get_path_display('player1_profile', 'p1_profile_path')
        self.table.setCellWidget(row_num, constants.EditorCols.PLAYER1_PROFILE.value, self._create_merged_path_widget(game.get('player1_profile_enabled', True), player1_profile, game.get('player1_profile_overwrite', True), row_num, constants.EditorCols.PLAYER1_PROFILE.value))
        self.table.setItem(row_num, constants.EditorCols.PLAYER1_PROFILE_OPTIONS.value, QTableWidgetItem(game.get('player1_profile_options', '')))
        self.table.setItem(row_num, constants.EditorCols.PLAYER1_PROFILE_ARGUMENTS.value, QTableWidgetItem(game.get('player1_profile_arguments', '')))
        
        player2_profile = get_path_display('player2_profile', 'p2_profile_path')
        self.table.setCellWidget(row_num, constants.EditorCols.PLAYER2_PROFILE.value, self._create_merged_path_widget(game.get('player2_profile_enabled', True), player2_profile, game.get('player2_profile_overwrite', True), row_num, constants.EditorCols.PLAYER2_PROFILE.value))
        self.table.setItem(row_num, constants.EditorCols.PLAYER2_PROFILE_OPTIONS.value, QTableWidgetItem(game.get('player2_profile_options', '')))
        self.table.setItem(row_num, constants.EditorCols.PLAYER2_PROFILE_ARGUMENTS.value, QTableWidgetItem(game.get('player2_profile_arguments', '')))
        
        desk_profile = get_path_display('desk_profile', 'desk_profile_path')
        self.table.setCellWidget(row_num, constants.EditorCols.DESK_PROFILE.value, self._create_merged_path_widget(game.get('desk_profile_enabled', True), desk_profile, game.get('desk_profile_overwrite', True), row_num, constants.EditorCols.DESK_PROFILE.value))
        self.table.setItem(row_num, constants.EditorCols.DESK_PROFILE_OPTIONS.value, QTableWidgetItem(game.get('desk_profile_options', '')))
        self.table.setItem(row_num, constants.EditorCols.DESK_PROFILE_ARGUMENTS.value, QTableWidgetItem(game.get('desk_profile_arguments', '')))

        # Just After Launch (CheckBox, Path with symbol, RunWait)
        ja_symbol, ja_run_wait = self._get_propagation_symbol_and_run_wait('just_after_launch_path')
        ja_path = f"{ja_symbol} {game.get('just_after_launch_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.JA_PATH.value, self._create_merged_path_widget(game.get('just_after_launch_enabled', True), ja_path, game.get('just_after_launch_overwrite', True), row_num, constants.EditorCols.JA_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.JA_OPTIONS.value, QTableWidgetItem(game.get('just_after_launch_options', '')))
        self.table.setItem(row_num, constants.EditorCols.JA_ARGUMENTS.value, QTableWidgetItem(game.get('just_after_launch_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.JA_RUN_WAIT.value, self._create_checkbox_widget(game.get('just_after_launch_run_wait', ja_run_wait), row_num, constants.EditorCols.JA_RUN_WAIT.value))

        # Just Before Exit (CheckBox, Path with symbol, RunWait)
        jb_symbol, jb_run_wait = self._get_propagation_symbol_and_run_wait('just_before_exit_path')
        jb_path = f"{jb_symbol} {game.get('just_before_exit_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.JB_PATH.value, self._create_merged_path_widget(game.get('just_before_exit_enabled', True), jb_path, game.get('just_before_exit_overwrite', True), row_num, constants.EditorCols.JB_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.JB_OPTIONS.value, QTableWidgetItem(game.get('just_before_exit_options', '')))
        self.table.setItem(row_num, constants.EditorCols.JB_ARGUMENTS.value, QTableWidgetItem(game.get('just_before_exit_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.JB_RUN_WAIT.value, self._create_checkbox_widget(game.get('just_before_exit_run_wait', jb_run_wait), row_num, constants.EditorCols.JB_RUN_WAIT.value))

        # Pre/Post Scripts with Enabled Checkboxes and RunWait toggles
        pre1_symbol, pre1_run_wait = self._get_propagation_symbol_and_run_wait('pre1_path')
        pre1_path = f"{pre1_symbol} {game.get('pre1_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.PRE1_PATH.value, self._create_merged_path_widget(game.get('pre_1_enabled', True), pre1_path, game.get('pre_1_overwrite', True), row_num, constants.EditorCols.PRE1_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.PRE1_OPTIONS.value, QTableWidgetItem(game.get('pre1_options', '')))
        self.table.setItem(row_num, constants.EditorCols.PRE1_ARGUMENTS.value, QTableWidgetItem(game.get('pre1_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.PRE1_RUN_WAIT.value, self._create_checkbox_widget(game.get('pre_1_run_wait', pre1_run_wait), row_num, constants.EditorCols.PRE1_RUN_WAIT.value))

        post1_symbol, post1_run_wait = self._get_propagation_symbol_and_run_wait('post1_path')
        post1_path = f"{post1_symbol} {game.get('post1_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.POST1_PATH.value, self._create_merged_path_widget(game.get('post_1_enabled', True), post1_path, game.get('post_1_overwrite', True), row_num, constants.EditorCols.POST1_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.POST1_OPTIONS.value, QTableWidgetItem(game.get('post1_options', '')))
        self.table.setItem(row_num, constants.EditorCols.POST1_ARGUMENTS.value, QTableWidgetItem(game.get('post1_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.POST1_RUN_WAIT.value, self._create_checkbox_widget(game.get('post_1_run_wait', post1_run_wait), row_num, constants.EditorCols.POST1_RUN_WAIT.value))

        pre2_symbol, pre2_run_wait = self._get_propagation_symbol_and_run_wait('pre2_path')
        pre2_path = f"{pre2_symbol} {game.get('pre2_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.PRE2_PATH.value, self._create_merged_path_widget(game.get('pre_2_enabled', True), pre2_path, game.get('pre_2_overwrite', True), row_num, constants.EditorCols.PRE2_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.PRE2_OPTIONS.value, QTableWidgetItem(game.get('pre2_options', '')))
        self.table.setItem(row_num, constants.EditorCols.PRE2_ARGUMENTS.value, QTableWidgetItem(game.get('pre2_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.PRE2_RUN_WAIT.value, self._create_checkbox_widget(game.get('pre_2_run_wait', pre2_run_wait), row_num, constants.EditorCols.PRE2_RUN_WAIT.value))

        post2_symbol, post2_run_wait = self._get_propagation_symbol_and_run_wait('post2_path')
        post2_path = f"{post2_symbol} {game.get('post2_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.POST2_PATH.value, self._create_merged_path_widget(game.get('post_2_enabled', True), post2_path, game.get('post_2_overwrite', True), row_num, constants.EditorCols.POST2_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.POST2_OPTIONS.value, QTableWidgetItem(game.get('post2_options', '')))
        self.table.setItem(row_num, constants.EditorCols.POST2_ARGUMENTS.value, QTableWidgetItem(game.get('post2_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.POST2_RUN_WAIT.value, self._create_checkbox_widget(game.get('post_2_run_wait', post2_run_wait), row_num, constants.EditorCols.POST2_RUN_WAIT.value))

        pre3_symbol, pre3_run_wait = self._get_propagation_symbol_and_run_wait('pre3_path')
        pre3_path = f"{pre3_symbol} {game.get('pre3_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.PRE3_PATH.value, self._create_merged_path_widget(game.get('pre_3_enabled', True), pre3_path, game.get('pre_3_overwrite', True), row_num, constants.EditorCols.PRE3_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.PRE3_OPTIONS.value, QTableWidgetItem(game.get('pre3_options', '')))
        self.table.setItem(row_num, constants.EditorCols.PRE3_ARGUMENTS.value, QTableWidgetItem(game.get('pre3_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.PRE3_RUN_WAIT.value, self._create_checkbox_widget(game.get('pre_3_run_wait', pre3_run_wait), row_num, constants.EditorCols.PRE3_RUN_WAIT.value))

        post3_symbol, post3_run_wait = self._get_propagation_symbol_and_run_wait('post3_path')
        post3_path = f"{post3_symbol} {game.get('post3_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.POST3_PATH.value, self._create_merged_path_widget(game.get('post_3_enabled', True), post3_path, game.get('post_3_overwrite', True), row_num, constants.EditorCols.POST3_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.POST3_OPTIONS.value, QTableWidgetItem(game.get('post3_options', '')))
        self.table.setItem(row_num, constants.EditorCols.POST3_ARGUMENTS.value, QTableWidgetItem(game.get('post3_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.POST3_RUN_WAIT.value, self._create_checkbox_widget(game.get('post_3_run_wait', post3_run_wait), row_num, constants.EditorCols.POST3_RUN_WAIT.value))

        # Kill List (Merged: CheckBox + Text)
        kl_item = QTableWidgetItem(game.get('kill_list', ''))
        kl_enabled = game.get('kill_list_enabled', False)
        kl_item.setCheckState(Qt.CheckState.Checked if kl_enabled else Qt.CheckState.Unchecked)
        self.table.setItem(row_num, constants.EditorCols.KILL_LIST.value, kl_item)

        # Launcher Executable (Merged: CheckBox + Path + Overwrite)
        le_symbol, _ = self._get_propagation_symbol_and_run_wait('launcher_executable')
        le_path = f"{le_symbol} {game.get('launcher_executable', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.LAUNCHER_EXE.value, self._create_merged_path_widget(game.get('launcher_executable_enabled', True), le_path, game.get('launcher_executable_overwrite', True), row_num, constants.EditorCols.LAUNCHER_EXE.value))
        self.table.setItem(row_num, constants.EditorCols.LAUNCHER_EXE_OPTIONS.value, QTableWidgetItem(game.get('launcher_executable_options', '')))
        self.table.setItem(row_num, constants.EditorCols.LAUNCHER_EXE_ARGUMENTS.value, QTableWidgetItem(game.get('launcher_executable_arguments', '')))

        # Execution Order
        self.table.setItem(row_num, constants.EditorCols.EXEC_ORDER.value, QTableWidgetItem(", ".join(self.main_window.config.launch_sequence)))

        # Termination Order
        self.table.setItem(row_num, constants.EditorCols.TERM_ORDER.value, QTableWidgetItem(", ".join(self.main_window.config.exit_sequence)))

        # ISO Path
        found_isos = game.get('_found_isos')
        if found_isos:
            self.table.setCellWidget(row_num, constants.EditorCols.ISO_PATH.value, self._create_iso_combo_widget(game.get('iso_path', ''), found_isos, row_num, constants.EditorCols.ISO_PATH.value))
        else:
            self.table.setCellWidget(row_num, constants.EditorCols.ISO_PATH.value, self._create_iso_path_widget(game.get('iso_path', ''), row_num, constants.EditorCols.ISO_PATH.value))

        # Disc-Mount (CheckBox, Path with symbol, RunWait)
        dm_symbol, dm_run_wait = self._get_propagation_symbol_and_run_wait('disc_mount_path')
        dm_path = f"{dm_symbol} {game.get('disc_mount_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.DM_PATH.value, self._create_merged_path_widget(game.get('disc_mount_enabled', True), dm_path, game.get('disc_mount_overwrite', True), row_num, constants.EditorCols.DM_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.DM_OPTIONS.value, QTableWidgetItem(game.get('disc_mount_options', '')))
        self.table.setItem(row_num, constants.EditorCols.DM_ARGUMENTS.value, QTableWidgetItem(game.get('disc_mount_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.DM_RUN_WAIT.value, self._create_checkbox_widget(game.get('disc_mount_run_wait', dm_run_wait), row_num, constants.EditorCols.DM_RUN_WAIT.value))

        dm_mount_cfg = get_path_display('disc_mount_cfg', 'disc_mount_path')
        self.table.setCellWidget(row_num, constants.EditorCols.DM_MOUNT_CFG.value, self._create_merged_path_widget(game.get('disc_mount_cfg_enabled', True), dm_mount_cfg, game.get('disc_mount_cfg_overwrite', True), row_num, constants.EditorCols.DM_MOUNT_CFG.value))
        self.table.setItem(row_num, constants.EditorCols.DM_MOUNT_CFG_OPTIONS.value, QTableWidgetItem(game.get('disc_mount_cfg_options', '')))
        self.table.setItem(row_num, constants.EditorCols.DM_MOUNT_CFG_ARGUMENTS.value, QTableWidgetItem(game.get('disc_mount_cfg_arguments', '')))
        
        dm_unmount_cfg = get_path_display('disc_unmount_cfg', 'disc_mount_path')
        self.table.setCellWidget(row_num, constants.EditorCols.DM_UNMOUNT_CFG.value, self._create_merged_path_widget(game.get('disc_unmount_cfg_enabled', True), dm_unmount_cfg, game.get('disc_unmount_cfg_overwrite', True), row_num, constants.EditorCols.DM_UNMOUNT_CFG.value))
        self.table.setItem(row_num, constants.EditorCols.DM_UNMOUNT_CFG_OPTIONS.value, QTableWidgetItem(game.get('disc_unmount_cfg_options', '')))
        self.table.setItem(row_num, constants.EditorCols.DM_UNMOUNT_CFG_ARGUMENTS.value, QTableWidgetItem(game.get('disc_unmount_cfg_arguments', '')))
        
        audio_symbol, audio_run_wait = self._get_propagation_symbol_and_run_wait('audio_app_path')
        audio_path = f"{audio_symbol} {game.get('audio_app_path', '').lstrip('<> ')}"
        self.table.setCellWidget(row_num, constants.EditorCols.AUDIO_APP_PATH.value, self._create_merged_path_widget(game.get('audio_app_enabled', True), audio_path, game.get('audio_app_overwrite', True), row_num, constants.EditorCols.AUDIO_APP_PATH.value))
        self.table.setItem(row_num, constants.EditorCols.AUDIO_APP_OPTIONS.value, QTableWidgetItem(game.get('audio_app_options', '')))
        self.table.setItem(row_num, constants.EditorCols.AUDIO_APP_ARGUMENTS.value, QTableWidgetItem(game.get('audio_app_arguments', '')))
        self.table.setCellWidget(row_num, constants.EditorCols.AUDIO_APP_RUN_WAIT.value, self._create_checkbox_widget(game.get('audio_app_run_wait', audio_run_wait), row_num, constants.EditorCols.AUDIO_APP_RUN_WAIT.value))
        
        # UnBorder Config
        unborder_cfg = get_path_display('unborder_cfg', 'audio_app_path')
        self.table.setCellWidget(row_num, constants.EditorCols.UNBORDER_CFG.value, self._create_merged_path_widget(game.get('unborder_cfg_enabled', True), unborder_cfg, game.get('unborder_cfg_overwrite', True), row_num, constants.EditorCols.UNBORDER_CFG.value))
        self.table.setItem(row_num, constants.EditorCols.UNBORDER_CFG_OPTIONS.value, QTableWidgetItem(game.get('unborder_cfg_options', '')))
        self.table.setItem(row_num, constants.EditorCols.UNBORDER_CFG_ARGUMENTS.value, QTableWidgetItem(game.get('unborder_cfg_arguments', '')))
        
        # ReBorder Config
        reborder_cfg = get_path_display('reborder_cfg', 'audio_app_path')
        self.table.setCellWidget(row_num, constants.EditorCols.REBORDER_CFG.value, self._create_merged_path_widget(game.get('reborder_cfg_enabled', True), reborder_cfg, game.get('reborder_cfg_overwrite', True), row_num, constants.EditorCols.REBORDER_CFG.value))
        self.table.setItem(row_num, constants.EditorCols.REBORDER_CFG_OPTIONS.value, QTableWidgetItem(game.get('reborder_cfg_options', '')))
        self.table.setItem(row_num, constants.EditorCols.REBORDER_CFG_ARGUMENTS.value, QTableWidgetItem(game.get('reborder_cfg_arguments', '')))
        
        # Audio Game Config
        audio_game_cfg = get_path_display('audio_game_cfg', 'audio_tool_path')
        self.table.setCellWidget(row_num, constants.EditorCols.AUDIO_GAME_CFG.value, self._create_merged_path_widget(game.get('audio_game_cfg_enabled', True), audio_game_cfg, game.get('audio_game_cfg_overwrite', True), row_num, constants.EditorCols.AUDIO_GAME_CFG.value))
        self.table.setItem(row_num, constants.EditorCols.AUDIO_GAME_CFG_OPTIONS.value, QTableWidgetItem(game.get('audio_game_cfg_options', '')))
        self.table.setItem(row_num, constants.EditorCols.AUDIO_GAME_CFG_ARGUMENTS.value, QTableWidgetItem(game.get('audio_game_cfg_arguments', '')))
        
        # Audio Desk Config
        audio_desk_cfg = get_path_display('audio_desk_cfg', 'audio_tool_path')
        self.table.setCellWidget(row_num, constants.EditorCols.AUDIO_DESK_CFG.value, self._create_merged_path_widget(game.get('audio_desk_cfg_enabled', True), audio_desk_cfg, game.get('audio_desk_cfg_overwrite', True), row_num, constants.EditorCols.AUDIO_DESK_CFG.value))
        self.table.setItem(row_num, constants.EditorCols.AUDIO_DESK_CFG_OPTIONS.value, QTableWidgetItem(game.get('audio_desk_cfg_options', '')))
        self.table.setItem(row_num, constants.EditorCols.AUDIO_DESK_CFG_ARGUMENTS.value, QTableWidgetItem(game.get('audio_desk_cfg_arguments', '')))
        
        # Rich tooltip for Create checkbox — shows Name-Override + executable name
        create_widget = self.frozen_table.cellWidget(row_num, 0)
        if create_widget:
            cb = create_widget.findChild(QCheckBox)
            if cb:
                name_ov = game.get('name_override', '') or ''
                exe_name = game.get('name', '') or ''
                no_item = self.table.item(row_num, constants.EditorCols.NAME_OVERRIDE.value)
                no_widget = self.table.cellWidget(row_num, constants.EditorCols.NAME_OVERRIDE.value)
                bg = QColor(Qt.GlobalColor.white)
                if no_item and no_item.background().color().isValid():
                    bg = no_item.background().color()
                elif isinstance(no_widget, QComboBox):
                    bg = no_widget.palette().color(no_widget.backgroundRole())
                r, g, b = bg.red(), bg.green(), bg.blue()
                comp = QColor(255 - r, 255 - g, 255 - b)
                cb.setToolTip(
                    f'<div style="background-color: rgba({r},{g},{b},128); '
                    f'color: rgb({comp.red()},{comp.green()},{comp.blue()}); '
                    f'font-weight: bold; padding: 4px;">'
                    f'Name Override: {name_ov}<br>'
                    f'Executable: {exe_name}'
                    f'</div>'
                )

        # Apply styling
        self._apply_styling(row_num, game, duplicates)

        self.table.blockSignals(False) # Unblock signals

    def _apply_styling(self, row, game_data, duplicates=None):
        """Apply background colors based on game state."""
        if duplicates is None:
            # Recalculate duplicates if not provided
            all_names = [g.get('name_override', '').strip() for g in self.original_data 
                         if g.get('name_override', '').strip() and g.get('create', True)]
            counts = collections.Counter(all_names)
            duplicates = {name for name, count in counts.items() if count > 1}

        # Colors
        dark_red = QColor(139, 0, 0)
        white = QColor(Qt.GlobalColor.white)
        yellow = QColor(Qt.GlobalColor.yellow)
        purple = QColor(128, 0, 128)
        orange = QColor(255, 165, 0)
        blue = QColor(Qt.GlobalColor.blue)

        # 1. Duplicate Name Overrides and Empty SteamID
        name_override = game_data.get('name_override', '').strip()
        steam_id = str(game_data.get('steam_id', ''))
        
        bg_color = None
        fg_color = None
        
        if name_override in duplicates:
            bg_color = dark_red
            fg_color = white
            tooltip_text = "Duplicate Name Override"
        elif not steam_id or steam_id == 'NOT_FOUND_IN_DATA' or steam_id == '':
            bg_color = yellow
            fg_color = purple
            tooltip_text = "Empty Steam ID"
        else:
            tooltip_text = ""
            
        col_override = constants.EditorCols.NAME_OVERRIDE.value
        item_override = self.table.item(row, col_override)
        widget_override = self.table.cellWidget(row, col_override)
        
        if item_override:
            if bg_color:
                item_override.setBackground(QBrush(bg_color))
                item_override.setForeground(QBrush(fg_color))
                item_override.setToolTip(tooltip_text)
            else:
                item_override.setData(Qt.ItemDataRole.BackgroundRole, None)
                item_override.setData(Qt.ItemDataRole.ForegroundRole, None)
                item_override.setToolTip("")
        
        if widget_override:
            if bg_color:
                bg_css = f"rgb({bg_color.red()}, {bg_color.green()}, {bg_color.blue()})"
                fg_css = "white" if fg_color == white else f"rgb({fg_color.red()}, {fg_color.green()}, {fg_color.blue()})"
                widget_override.setStyleSheet(f"background-color: {bg_css}; color: {fg_css};")
                widget_override.setToolTip(tooltip_text)
            else:
                widget_override.setStyleSheet("")
                widget_override.setToolTip("")

        # 2. Missing Sequence Entry
        config = self.main_window.config
        combined_seq = set(config.launch_sequence + config.exit_sequence)
        
        # Element mapping: (Key in sequence, Path Key in data, List of associated columns)
        element_styles = [
            ('Controller-Mapper', 'controller_mapper_path', [
                constants.EditorCols.CM_PATH, constants.EditorCols.CM_OPTIONS, 
                constants.EditorCols.CM_ARGUMENTS, constants.EditorCols.CM_RUN_WAIT,
                constants.EditorCols.PLAYER1_PROFILE, constants.EditorCols.PLAYER2_PROFILE, 
                constants.EditorCols.DESK_PROFILE
            ]),
            ('Borderless', 'borderless_windowing_path', [
                constants.EditorCols.BW_PATH, constants.EditorCols.BW_OPTIONS, 
                constants.EditorCols.BW_ARGUMENTS, constants.EditorCols.BW_RUN_WAIT
            ]),
            ('Monitor-Config', 'monitorapp_path', [
                constants.EditorCols.MONITORAPP_PATH, constants.EditorCols.MONITORAPP_OPTIONS,
                constants.EditorCols.MONITORAPP_ARGUMENTS, constants.EditorCols.MONITORAPP_RUN_WAIT,
                constants.EditorCols.MONITOR_GAME_CFG, constants.EditorCols.MONITOR_GAME_CFG_OPTIONS,
                constants.EditorCols.MONITOR_GAME_CFG_ARGUMENTS,
                constants.EditorCols.MONITOR_DESK_CFG, constants.EditorCols.MONITOR_DESK_CFG_OPTIONS,
                constants.EditorCols.MONITOR_DESK_CFG_ARGUMENTS,
                constants.EditorCols.PLAYER1_PROFILE, constants.EditorCols.PLAYER1_PROFILE_OPTIONS,
                constants.EditorCols.PLAYER1_PROFILE_ARGUMENTS,
                constants.EditorCols.PLAYER2_PROFILE, constants.EditorCols.PLAYER2_PROFILE_OPTIONS,
                constants.EditorCols.PLAYER2_PROFILE_ARGUMENTS,
                constants.EditorCols.DESK_PROFILE, constants.EditorCols.DESK_PROFILE_OPTIONS,
                constants.EditorCols.DESK_PROFILE_ARGUMENTS
            ]),
            ('JustAfterLaunch', 'just_after_launch_path', [
                constants.EditorCols.JA_PATH, constants.EditorCols.JA_OPTIONS, 
                constants.EditorCols.JA_ARGUMENTS, constants.EditorCols.JA_RUN_WAIT
            ]),
            ('JustBeforeExit', 'just_before_exit_path', [
                constants.EditorCols.JB_PATH, constants.EditorCols.JB_OPTIONS, 
                constants.EditorCols.JB_ARGUMENTS, constants.EditorCols.JB_RUN_WAIT
            ]),
            ('Pre1', 'pre1_path', [
                constants.EditorCols.PRE1_PATH, constants.EditorCols.PRE1_OPTIONS, 
                constants.EditorCols.PRE1_ARGUMENTS, constants.EditorCols.PRE1_RUN_WAIT
            ]),
            ('Pre2', 'pre2_path', [
                constants.EditorCols.PRE2_PATH, constants.EditorCols.PRE2_OPTIONS, 
                constants.EditorCols.PRE2_ARGUMENTS, constants.EditorCols.PRE2_RUN_WAIT
            ]),
            ('Pre3', 'pre3_path', [
                constants.EditorCols.PRE3_PATH, constants.EditorCols.PRE3_OPTIONS, 
                constants.EditorCols.PRE3_ARGUMENTS, constants.EditorCols.PRE3_RUN_WAIT
            ]),
            ('Post1', 'post1_path', [
                constants.EditorCols.POST1_PATH, constants.EditorCols.POST1_OPTIONS, 
                constants.EditorCols.POST1_ARGUMENTS, constants.EditorCols.POST1_RUN_WAIT
            ]),
            ('Post2', 'post2_path', [
                constants.EditorCols.POST2_PATH, constants.EditorCols.POST2_OPTIONS, 
                constants.EditorCols.POST2_ARGUMENTS, constants.EditorCols.POST2_RUN_WAIT
            ]),
            ('Post3', 'post3_path', [
                constants.EditorCols.POST3_PATH, constants.EditorCols.POST3_OPTIONS, 
                constants.EditorCols.POST3_ARGUMENTS, constants.EditorCols.POST3_RUN_WAIT
            ]),
            ('mount-disc', 'iso_path', [
                constants.EditorCols.ISO_PATH, constants.EditorCols.DM_PATH, 
                constants.EditorCols.DM_OPTIONS, constants.EditorCols.DM_ARGUMENTS, 
                constants.EditorCols.DM_RUN_WAIT,
                constants.EditorCols.DM_MOUNT_CFG, constants.EditorCols.DM_UNMOUNT_CFG
            ]),
            ('RunAudio', 'audio_app_path', [
                constants.EditorCols.AUDIO_APP_PATH, constants.EditorCols.AUDIO_APP_OPTIONS, 
                constants.EditorCols.AUDIO_APP_ARGUMENTS, constants.EditorCols.AUDIO_APP_RUN_WAIT,
            ]),
            ('Borderless', 'borderless_windowing_path', [
                constants.EditorCols.BW_PATH, constants.EditorCols.BW_OPTIONS, 
                constants.EditorCols.BW_ARGUMENTS, constants.EditorCols.BW_RUN_WAIT,
                constants.EditorCols.UNBORDER_CFG, constants.EditorCols.REBORDER_CFG
            ]),
        ]
        
        for seq_key, path_key, cols in element_styles:
            path_val = game_data.get(path_key, '')
            if path_val and seq_key not in combined_seq:
                for col_enum in cols:
                    col = col_enum.value
                    it = self.table.item(row, col)
                    if it:
                        it.setBackground(QBrush(orange))
                        it.setForeground(QBrush(blue))
                        it.setToolTip(f"Missing from Launch/Exit Sequence: {seq_key}")
                    
                    wdg = self.table.cellWidget(row, col)
                    if wdg:
                        wdg.setStyleSheet(f"background-color: rgb(255, 165, 0); color: blue;")
                        wdg.setToolTip(f"Missing from Launch/Exit Sequence: {seq_key}")
            else:
                # Clear styling for these columns if they were orange
                for col_enum in cols:
                    col = col_enum.value
                    it = self.table.item(row, col)
                    if it and it.background().color() == orange and "Missing from Launch/Exit Sequence" in it.toolTip():
                        it.setData(Qt.ItemDataRole.BackgroundRole, None)
                        it.setData(Qt.ItemDataRole.ForegroundRole, None)
                        it.setToolTip("")
                    wdg = self.table.cellWidget(row, col)
                    if wdg and "background-color: rgb(255, 165, 0)" in wdg.styleSheet() and "Missing from Launch/Exit Sequence" in wdg.toolTip():
                        wdg.setStyleSheet("")
                        wdg.setToolTip("")

    def get_all_game_data(self):
        """Extract all game data from the table, sanitizing disabled paths."""
        # Deep copy to avoid modifying original_data
        import copy
        sanitized_data = copy.deepcopy(self.original_data)
        
        path_enabled_pairs = [
            ('controller_mapper_path', 'controller_mapper_enabled'),
            ('borderless_windowing_path', 'borderless_windowing_enabled'),
            ('monitorapp_path', 'monitorapp_enabled'),
            ('just_after_launch_path', 'just_after_launch_enabled'),
            ('just_before_exit_path', 'just_before_exit_enabled'),
            ('pre1_path', 'pre_1_enabled'),
            ('pre2_path', 'pre_2_enabled'),
            ('pre3_path', 'pre_3_enabled'),
            ('post1_path', 'post_1_enabled'),
            ('post2_path', 'post_2_enabled'),
            ('post3_path', 'post_3_enabled'),
            ('player1_profile', 'player1_profile_enabled'),
            ('player2_profile', 'player2_profile_enabled'),
            ('desk_profile', 'desk_profile_enabled'),
            ('monitor_game_cfg', 'monitor_game_cfg_enabled'),
            ('monitor_desk_cfg', 'monitor_desk_cfg_enabled'),
            ('launcher_executable', 'launcher_executable_enabled'),
            ('disc_mount_path', 'disc_mount_enabled'),
            ('audio_app_path', 'audio_app_enabled'),
            ('unborder_cfg', 'unborder_cfg_enabled'),
            ('reborder_cfg', 'reborder_cfg_enabled'),
        ]
        
        for game in sanitized_data:
            for path_key, enabled_key in path_enabled_pairs:
                # If the enabled flag is False, clear the path
                if not game.get(enabled_key, True):
                    game[path_key] = ""
        
        return sanitized_data

    def get_selected_game_data(self):
        """Extract data for selected games in the table."""
        selected_games = []
        for item in self.table.selectedItems():
            if item.column() == constants.EditorCols.NAME.value: # NAME column (column 1) contains the executable name
                row = item.row()
                real_index = (self.current_page * self.page_size) + row
                if real_index < len(self.filtered_data):
                    game_data = self.filtered_data[real_index]
                    selected_games.append(game_data)
        return selected_games

    def get_create_count(self):
        """Return the number of items marked for creation in the full dataset."""
        return sum(1 for g in self.original_data if g.get('create', False))

    def apply_cell_value_to_selection(self, src_row, col):
        state = self._get_cell_state(src_row, col)
        self.push_undo()
        if state is None:
            return

        rows = set()
        # Get rows from selected ranges
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                rows.add(r)
        
        # Fallback to selected indexes if ranges are empty
        if not rows:
            for index in self.table.selectedIndexes():
                rows.add(index.row())
        
        # Apply to all unique rows
        for r in rows:
            if r == src_row: continue
            self._set_cell_state(r, col, state)
            self._sync_cell_to_data(r, col)
            
        # Notify change
        self.main_window._on_editor_table_edited(None)

    def propagate_row_to_selection(self, src_row):
        """Copy ALL column values from the source row to every other selected row."""
        self.push_undo()

        # Collect target rows from the current selection
        rows = set()
        for range_ in self.table.selectedRanges():
            for r in range(range_.topRow(), range_.bottomRow() + 1):
                rows.add(r)
        if not rows:
            for index in self.table.selectedIndexes():
                rows.add(index.row())

        if not rows:
            return

        # Iterate every column and propagate the cell state
        for col_idx in range(self.table.columnCount()):
            state = self._get_cell_state(src_row, col_idx)
            if state is None:
                continue
            for r in rows:
                if r == src_row:
                    continue
                self._set_cell_state(r, col_idx, state)
                self._sync_cell_to_data(r, col_idx)

        self.main_window._on_editor_table_edited(None)

    def _get_cell_state(self, row, col):
        widget = self.table.cellWidget(row, col)  # type: ignore[union-attr]
        if widget:
            cbs = widget.findChildren(QCheckBox)
            if len(cbs) >= 2: # Merged
                enabled = cbs[0].isChecked()
                overwrite = cbs[1].isChecked()
                le = widget.findChild(QLineEdit)
                path = le.text() if le else ""
                return {'type': 'merged', 'enabled': enabled, 'path': path, 'overwrite': overwrite}
            elif len(cbs) == 1: # Simple Checkbox
                return {'type': 'checkbox', 'checked': cbs[0].isChecked()}
        
        item = self.table.item(row, col)
        if item:
            state = {'type': 'text', 'text': item.text()}
            # Handle merged Kill List (checkable text)
            if col == constants.EditorCols.KILL_LIST.value:
                state['checked'] = (item.checkState() == Qt.CheckState.Checked)
                state['type'] = 'checkable_text'
            return state
        return None

    def _set_cell_state(self, row, col, state):
        if not state: return
        
        if state['type'] == 'merged':
            widget = self.table.cellWidget(row, col)  # type: ignore[union-attr]
            if widget:
                cbs = widget.findChildren(QCheckBox)
                if len(cbs) >= 2:
                    cbs[0].setChecked(state['enabled'])
                    cbs[1].setChecked(state['overwrite'])
                    le = widget.findChild(QLineEdit)
                    if le: le.setText(state['path'])
        
        elif state['type'] == 'checkbox':
            widget = self.table.cellWidget(row, col)  # type: ignore[union-attr]
            if widget:
                cbs = widget.findChildren(QCheckBox)
                if cbs:
                    cbs[0].setChecked(state['checked'])
                    
        elif state['type'] == 'checkable_text':
            item = self.table.item(row, col)
            if not item:
                item = QTableWidgetItem()
                self.table.setItem(row, col, item)
            item.setText(state['text'])
            item.setCheckState(Qt.CheckState.Checked if state.get('checked') else Qt.CheckState.Unchecked)

        elif state['type'] == 'text':
            item = self.table.item(row, col)
            if not item:
                item = QTableWidgetItem()
                self.table.setItem(row, col, item)
            item.setText(state['text'])

    def _create_iso_path_widget(self, path_text, row, col):
        """Create a widget with line edit and browse button for ISO path."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)
        
        line_edit = QLineEdit(path_text)
        line_edit.setToolTip(path_text)
        line_edit.textChanged.connect(lambda: self._sync_cell_to_data(row, col))
        
        browse_btn = QPushButton("...")
        browse_btn.setMaximumWidth(30)
        browse_btn.clicked.connect(lambda: self._browse_iso_path(line_edit))
        
        layout.addWidget(line_edit)
        layout.addWidget(browse_btn)
        return widget

    def _browse_iso_path(self, line_edit):
        current_path = line_edit.text()
        start_dir = os.path.dirname(current_path) if current_path and os.path.exists(current_path) else ""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Disc Image", start_dir, 
            "Disc Images (*.iso *.cue *.bin *.img *.mdf *.nrg *.gdi *.cdi *.vhd *.vhdx *.vmdk *.wbfs *.cso *.chd);;All Files (*.*)"
        )
        
        if file_path:
            # Normalize path to use forward slashes
            file_path = file_path.replace('\\', '/')
            self.push_undo()
            line_edit.setText(file_path)

    def _create_iso_combo_widget(self, path_text, items, row, col):
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(4, 0, 4, 0)
        layout.setSpacing(2)
        
        combo = QComboBox()
        combo.setEditable(True)
        combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        
        combo_items = [""] + sorted(items)
        if path_text and path_text not in combo_items:
            combo_items.insert(1, path_text)
        combo.addItems(combo_items)
        
        combo.setCurrentText(path_text)
        combo.setToolTip(path_text)
        combo.currentTextChanged.connect(lambda: self._sync_cell_to_data(row, col))
        
        browse_btn = QPushButton("...")
        browse_btn.setMaximumWidth(30)
        browse_btn.clicked.connect(lambda: self._browse_iso_path_combo(combo))
        
        layout.addWidget(combo)
        layout.addWidget(browse_btn)
        return widget

    def _browse_iso_path_combo(self, combo):
        current_path = combo.currentText()
        start_dir = os.path.dirname(current_path) if current_path and os.path.exists(current_path) else ""
        
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Disc Image", start_dir, 
            "Disc Images (*.iso *.cue *.bin *.img *.mdf *.nrg *.gdi *.cdi *.vhd *.vhdx *.vmdk *.wbfs *.cso *.chd);;All Files (*.*)"
        )
        
        if file_path:
            # Normalize path to use forward slashes
            file_path = file_path.replace('\\', '/')
            self.push_undo()
            combo.setCurrentText(file_path)

    def clear_table(self):
        """Clear the table and reset original data."""
        self.table.setRowCount(0)
        self.original_data = []
        self.filtered_data = []
        self.current_page = 0
        self.data_changed.emit()

    def import_profiles(self):
        """Import games from a profile directory."""
        directory = QFileDialog.getExistingDirectory(self, "Select Profiles Directory")
        if not directory:
            return
        
        # Normalize path to use forward slashes
        directory = directory.replace('\\', '/')

        # Backup index
        try:
            backup_index(constants.APP_ROOT_DIR)
        except Exception as e:
            print(f"Failed to backup index: {e}")

        self.push_undo()
        existing_paths = {os.path.normpath(os.path.join(g.get('directory', ''), g.get('name', ''))).lower() 
                          for g in self.original_data}
        imported_count = 0
        
        for entry in os.scandir(directory):
            if entry.is_dir():
                ini_path = os.path.join(entry.path, "Game.ini")
                if os.path.exists(ini_path):
                    try:
                        game_data = self._parse_game_ini(ini_path, entry.path)
                        # Check if already in index
                        path = os.path.normpath(os.path.join(game_data.get('directory', ''), game_data.get('name', ''))).lower()
                        if path in existing_paths:
                            continue
                            
                        self.original_data.append(game_data)
                        existing_paths.add(path)
                        imported_count += 1
                    except Exception as e:
                        print(f"Failed to import {entry.name}: {e}")
        
        if imported_count > 0:
            self.filter_table(self.search_bar.text())
            self.main_window._on_editor_table_edited(None)
            QMessageBox.information(self, "Import Complete", f"Imported {imported_count} profiles.")
        else:
            QMessageBox.information(self, "Import", "No valid profiles found.")

    def _parse_game_ini(self, ini_path, profile_path):
        """Parse a Game.ini file and return a game data dictionary."""
        config = configparser.ConfigParser()
        config.read(ini_path)
        
        game_data = {}
        
        # [Game]
        game_data['create'] = True
        game_data['name'] = config.get('Game', 'Executable', fallback='')
        game_data['directory'] = config.get('Game', 'Directory', fallback='')
        game_data['name_override'] = config.get('Game', 'Name', fallback=os.path.basename(profile_path))
        game_data['iso_path'] = config.get('Game', 'IsoPath', fallback='')
        
        # Try to find Steam ID from Game.json
        json_path = os.path.join(profile_path, "Game.json")
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    if data:
                        key = next(iter(data))
                        game_data['steam_id'] = key
            except:
                pass
        
        # [Options]
        game_data['run_as_admin'] = config.getboolean('Options', 'RunAsAdmin', fallback=False)
        game_data['hide_taskbar'] = config.getboolean('Options', 'HideTaskbar', fallback=False)
        game_data['options'] = config.get('Options', 'Borderless', fallback='0')
        game_data['kill_list_enabled'] = config.getboolean('Options', 'UseKillList', fallback=False)
        game_data['kill_list'] = config.get('Options', 'KillList', fallback='')
        
        # Helper for paths
        def get_path(section, key, source_key=None):
            if source_key and config.has_option('SourcePaths', source_key):
                return "> " + config.get('SourcePaths', source_key)
            val = config.get(section, key, fallback='')
            return val

        # [mapperprofiles] (with [Paths] fallback)
        game_data['player1_profile'] = config.get('mapperprofiles', 'player1profile', fallback=get_path('Paths', 'Player1Profile', 'Player1Profile'))
        game_data['player1_profile_enabled'] = bool(game_data['player1_profile'])
        game_data['player1_profile_options'] = config.get('mapperprofiles', 'player1profileoptions', fallback='')
        game_data['player1_profile_arguments'] = config.get('mapperprofiles', 'player1profilearguments', fallback='')
        game_data['player2_profile'] = config.get('mapperprofiles', 'player2profile', fallback=get_path('Paths', 'Player2Profile', 'Player2Profile'))
        game_data['player2_profile_enabled'] = bool(game_data['player2_profile'])
        game_data['player2_profile_options'] = config.get('mapperprofiles', 'player2profileoptions', fallback='')
        game_data['player2_profile_arguments'] = config.get('mapperprofiles', 'player2profilearguments', fallback='')
        game_data['desk_profile'] = config.get('mapperprofiles', 'deskprofile', fallback=get_path('Paths', 'DeskProfile', 'DeskProfile'))
        game_data['desk_profile_enabled'] = bool(game_data['desk_profile'])
        game_data['desk_profile_options'] = config.get('mapperprofiles', 'deskprofileoptions', fallback='')
        game_data['desk_profile_arguments'] = config.get('mapperprofiles', 'deskprofilearguments', fallback='')
        
        # [MonitorLayouts] (with [Paths] fallback)
        game_data['monitor_game_cfg'] = config.get('MonitorLayouts', 'monitorgamecfg', fallback=get_path('Paths', 'MonitorGameConfig', 'MonitorGameConfig'))
        game_data['monitor_game_cfg_enabled'] = bool(game_data['monitor_game_cfg'])
        game_data['monitor_game_cfg_options'] = config.get('MonitorLayouts', 'monitorgamecfgoptions', fallback='')
        game_data['monitor_game_cfg_arguments'] = config.get('MonitorLayouts', 'monitorgamecfgarguments', fallback='')
        game_data['monitor_desk_cfg'] = config.get('MonitorLayouts', 'monitordeskcfg', fallback=get_path('Paths', 'MonitorDesktopConfig', 'MonitorDesktopConfig'))
        game_data['monitor_desk_cfg_enabled'] = bool(game_data['monitor_desk_cfg'])
        game_data['monitor_desk_cfg_options'] = config.get('MonitorLayouts', 'monitordeskcfgoptions', fallback='')
        game_data['monitor_desk_cfg_arguments'] = config.get('MonitorLayouts', 'monitordeskcfgarguments', fallback='')
        
        # [Monitor] (with [Paths] fallback)
        game_data['monitorapp_path'] = config.get('Monitor', 'monitorapppath', fallback=get_path('Paths', 'MonitorApp', 'MonitorApp'))
        game_data['monitorapp_options'] = config.get('Monitor', 'monitorapppathoptions', fallback=config.get('Paths', 'MonitorAppOptions', fallback=''))
        game_data['monitorapp_arguments'] = config.get('Monitor', 'monitorapppatharguments', fallback=config.get('Paths', 'MonitorAppArguments', fallback=''))
        game_data['monitorapp_enabled'] = config.getboolean('Monitor', 'enablemonitorapp', fallback=bool(game_data['monitorapp_path']))
        
        # [BorderlessProfiles]
        game_data['unborder_cfg'] = config.get('BorderlessProfiles', 'unbordercfgpath', fallback='')
        game_data['unborder_cfg_options'] = config.get('BorderlessProfiles', 'unbordercfgpathoptions', fallback='')
        game_data['unborder_cfg_arguments'] = config.get('BorderlessProfiles', 'unbordercfgpatharguments', fallback='')
        game_data['unborder_cfg_enabled'] = config.getboolean('BorderlessProfiles', 'enableunbordercfg', fallback=True)
        game_data['reborder_cfg'] = config.get('BorderlessProfiles', 'rebordercfgpath', fallback='')
        game_data['reborder_cfg_options'] = config.get('BorderlessProfiles', 'rebordercfgpathoptions', fallback='')
        game_data['reborder_cfg_arguments'] = config.get('BorderlessProfiles', 'rebordercfgpatharguments', fallback='')
        game_data['reborder_cfg_enabled'] = config.getboolean('BorderlessProfiles', 'enablerebordercfg', fallback=True)
        
        game_data['launcher_executable'] = config.get('Paths', 'LauncherExecutable', fallback='')
        game_data['launcher_executable_enabled'] = bool(game_data['launcher_executable'])
        
        # [PreLaunch]
        for i in range(1, 4):
            app_key = f'App{i}'
            game_data[f'pre{i}_path'] = get_path('PreLaunch', app_key, f'PreLaunchApp{i}')
            game_data[f'pre{i}_options'] = config.get('PreLaunch', f'{app_key}Options', fallback='')
            game_data[f'pre{i}_arguments'] = config.get('PreLaunch', f'{app_key}Arguments', fallback='')
            game_data[f'pre_{i}_run_wait'] = config.getboolean('PreLaunch', f'{app_key}Wait', fallback=False)
            game_data[f'pre_{i}_enabled'] = bool(game_data[f'pre{i}_path'])

        # [PostLaunch]
        for i in range(1, 4):
            app_key = f'App{i}'
            game_data[f'post{i}_path'] = get_path('PostLaunch', app_key, f'PostLaunchApp{i}')
            game_data[f'post{i}_options'] = config.get('PostLaunch', f'{app_key}Options', fallback='')
            game_data[f'post{i}_arguments'] = config.get('PostLaunch', f'{app_key}Arguments', fallback='')
            game_data[f'post_{i}_run_wait'] = config.getboolean('PostLaunch', f'{app_key}Wait', fallback=False)
            game_data[f'post_{i}_enabled'] = bool(game_data[f'post{i}_path'])
            
        game_data['just_after_launch_path'] = get_path('PostLaunch', 'JustAfterLaunchApp', 'JustAfterLaunchApp')
        game_data['just_after_launch_options'] = config.get('PostLaunch', 'JustAfterLaunchOptions', fallback='')
        game_data['just_after_launch_arguments'] = config.get('PostLaunch', 'JustAfterLaunchArguments', fallback='')
        game_data['just_after_launch_run_wait'] = config.getboolean('PostLaunch', 'JustAfterLaunchWait', fallback=False)
        game_data['just_after_launch_enabled'] = bool(game_data['just_after_launch_path'])
        
        game_data['just_before_exit_path'] = get_path('PostLaunch', 'JustBeforeExitApp', 'JustBeforeExitApp')
        game_data['just_before_exit_options'] = config.get('PostLaunch', 'JustBeforeExitOptions', fallback='')
        game_data['just_before_exit_arguments'] = config.get('PostLaunch', 'JustBeforeExitArguments', fallback='')
        game_data['just_before_exit_run_wait'] = config.getboolean('PostLaunch', 'JustBeforeExitWait', fallback=False)
        game_data['just_before_exit_enabled'] = bool(game_data['just_before_exit_path'])

        return game_data
