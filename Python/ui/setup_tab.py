import logging
import os
from pathlib import Path
import configparser
import requests
import zipfile
import shutil
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel, QFormLayout, QPushButton,
    QComboBox, QHBoxLayout, QCheckBox, QTabWidget, QSizePolicy,
    QFileDialog, QApplication, QSpinBox, QMessageBox, QMenu, QInputDialog,
    QDialog, QDialogButtonBox, QLineEdit, QProgressDialog, QGridLayout, QDoubleSpinBox,
    QStyle, QFontComboBox, QStackedWidget, QScrollArea, QFrame, QRadioButton,
    QButtonGroup
)
import re
from PyQt6.QtCore import pyqtSignal, Qt, QThread, pyqtSlot
from PyQt6.QtGui import QFont, QColor, QBrush
from Python.models import AppConfig
from Python.ui.widgets import DragDropListWidget, PathConfigRow
from Python.ui.slide_menu_panel import SlideMenuPanel, section_icon
from Python.ui.theme_manager import ThemeManager
from Python.ui.display_wizard import DisplayWizard
from Python.ui.config_preset_manager import (
    ConfigPresetManager, LOCAL_PRESET_MARKER, DEFAULT_CONFIG_JSON,
)
from Python import constants
    
class DownloadThread(QThread):
    """Thread for downloading and extracting tools."""
    progress = pyqtSignal(int)
    finished = pyqtSignal(bool, str, str) # success, message, result_path

    def __init__(self, url, extract_dir, exe_name):
        super().__init__()
        self.urls = url.split('<')
        self.extract_dir = extract_dir
        self.exe_name = exe_name

    def _extract_with_7z(self, archive_path):
        """Fallback extraction using 7z.exe."""
        seven_z_exe = os.path.join(constants.APP_ROOT_DIR, "bin", "7z.exe")
        if os.path.exists(seven_z_exe):
            cmd = [
                seven_z_exe, 
                "x", 
                archive_path, 
                f"-o{self.extract_dir}", 
                "-y"
            ]
            subprocess.run(cmd, check=True, creationflags=0x08000000) # CREATE_NO_WINDOW
            os.remove(archive_path)
        else:
            raise FileNotFoundError(f"7z.exe not found at {seven_z_exe} and py7zr module not installed.")

    def run(self):
        try:
            success = False
            last_error = ""
            
            # Suppress SSL warnings for the fallback strategy
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except ImportError:
                pass

            # Define retry strategies
            strategies = [
                # 1. Standard request
                {'headers': {}, 'verify': True},
                # 2. User-Agent spoofing (common fix for 403 Forbidden on some hosts)
                {'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}, 'verify': True},
                # 3. No SSL verify (fix for certificate errors) + User-Agent
                {'headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}, 'verify': False}
            ]

            for url in self.urls:
                try:
                    url = url.strip()
                    if not url: 
                        continue
                    
                    download_success = False
                    last_strategy_error = ""
                    
                    # Try each strategy until one works
                    for strategy in strategies:
                        try:
                            # Create extract directory
                            os.makedirs(self.extract_dir, exist_ok=True)
                            
                            # Determine filename from URL
                            filename = url.split('/')[-1]
                            save_path = os.path.join(self.extract_dir, filename)
                            
                            # Download with current strategy
                            response = requests.get(
                                url, 
                                stream=True, 
                                timeout=30, 
                                headers=strategy['headers'], 
                                verify=strategy['verify']
                            )
                            response.raise_for_status()
                            total_length = response.headers.get('content-length')

                            with open(save_path, 'wb') as f:
                                if total_length is None: # no content length header
                                    f.write(response.content)
                                else:
                                    dl = 0
                                    total_length = int(total_length)
                                    for data in response.iter_content(chunk_size=4096):
                                        dl += len(data)
                                        f.write(data)
                                        self.progress.emit(int(100 * dl / total_length))
                            
                            # Validate file size (prevent processing of 404 pages or small error files)
                            file_size = os.path.getsize(save_path)
                            if file_size < 1024:
                                with open(save_path, 'r', errors='ignore') as f:
                                    preview = f.read(100).strip()
                                os.remove(save_path)
                                raise Exception(f"Downloaded file is too small ({file_size} bytes). Likely an error page: {preview}")
                            
                            download_success = True
                            break  # Success, break out of strategy loop
                            
                        except Exception as e:
                            last_strategy_error = str(e)
                            continue  # Try next strategy
                    
                    if not download_success:
                        raise Exception(f"All download strategies failed for {url}. Last error: {last_strategy_error}")
                    
                    # Extract if it's a zip
                    if filename.lower().endswith('.zip'):
                        with zipfile.ZipFile(save_path, 'r') as zip_ref:
                            zip_ref.extractall(self.extract_dir)
                        os.remove(save_path) # Clean up zip
                    elif filename.lower().endswith('.7z'):
                        # Try py7zr first (Pure Python)
                        try:
                            import py7zr
                            with py7zr.SevenZipFile(save_path, mode='r') as z:
                                z.extractall(path=self.extract_dir)
                            os.remove(save_path)
                        except ImportError:
                            # Fall back to 7z.exe
                            self._extract_with_7z(save_path)
                    
                    success = True
                    
                    # If the file was extracted, try to find the specific executable
                    # Otherwise return the path to the downloaded file (useful for installers)
                    if filename.lower().endswith(('.zip', '.7z')):
                        # Check if the exe exists in the extraction dir
                        potential_exe = os.path.join(self.extract_dir, self.exe_name)
                        if os.path.exists(potential_exe):
                            save_path = potential_exe
                        else:
                            # Scan one level deep for common folder nesting in zips
                            found_nested = False
                            if os.path.exists(self.extract_dir):
                                for item in os.listdir(self.extract_dir):
                                    sub_path = os.path.join(self.extract_dir, item)
                                    if os.path.isdir(sub_path):
                                        check_path = os.path.join(sub_path, self.exe_name)
                                        if os.path.exists(check_path):
                                            save_path = check_path
                                            found_nested = True
                                            break
                            if not found_nested:
                                # Fall back to directory — caller will do a deep scan
                                save_path = self.extract_dir
                    
                    break  # Download + extraction succeeded — stop trying fallback URLs
                    
                except Exception as e:
                    last_error = str(e)
                    continue  # Try next URL
            
            if success:
                self.finished.emit(True, "Download completed successfully", save_path)
            else:
                self.finished.emit(False, f"All downloads failed. Last error: {last_error}", "")
                
        except Exception as e:
            self.finished.emit(False, f"Unexpected error: {str(e)}", "")

class SetupTab(QWidget):
    """A QWidget that encapsulates all UI and logic for the Setup tab."""
    
    config_changed = pyqtSignal()
    setting_changed = pyqtSignal(str)
    
    PATH_ATTRIBUTES = [
        "profiles_dir", "launchers_dir", "launcher_executable", "controller_mapper_path",
        "borderless_gaming_path", "disc_mount_path", "p1_profile_path",
        "p2_profile_path", "desk_profile_path",
        "monitorapp_path", "monitor_game_path",
        "monitor_desk_path", "pre1_path", "pre2_path", "pre3_path",
        "just_after_launch_path", "just_before_exit_path",
        "post1_path", "post2_path", "post3_path",
        "cloud_sync_path", "local_backup_path", "audio_tool_path",
        "disc_mount_cfg", "disc_unmount_cfg", "audio_game_cfg", "audio_desk_cfg",
        "unborder_cfg", "reborder_cfg"
    ]

    SEQUENCE_TOOLTIPS = {
        "Kill-Game": "Terminates the game process if it's running.",
        "Kill-List": "Terminates processes specified in the Kill List.",
        "mount-disc": "Mounts the game ISO if configured.",
        "Unmount-disc": "Unmounts the game ISO.",
        "Controller-Mapper": "Starts/Stops the controller mapper (e.g. AntimicroX).",
        "Monitor-Config": "Applies monitor configuration (Game/Desktop).",
        "No-TB": "Hides the Windows Taskbar.",
        "Taskbar": "Restores the Windows Taskbar.",
        "Pre1": "Runs Pre-Launch Script 1.",
        "Pre2": "Runs Pre-Launch Script 2.",
        "Pre3": "Runs Pre-Launch Script 3.",
        "Post1": "Runs Post-Launch Script 1.",
        "Post2": "Runs Post-Launch Script 2.",
        "Post3": "Runs Post-Launch Script 3.",
        "Borderless": "Starts/Stops Borderless Gaming.",
        "Cloud-Sync": "Runs the Cloud Sync application.",
        "JustAfterLaunch": "Runs immediately after game launches.",
        "JustBeforeExit": "Runs immediately before game exits.",
        "RunAudio": "Runs the game audio application (pre-run).",
        "ReturnAudio": "Runs the return audio application (post-run).",
        "Backup": "Runs the local backup application.",
    }
    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.path_rows = {}
        
        # Get plugin manager from main window if available
        self.plugin_manager = getattr(parent, 'plugin_manager', None)
        
        # Parse repos.set
        self.repos = self._parse_repos_set()
        
        self.last_detected_tools = {}
        self.options_args_map = self._parse_options_arguments_set()
        
        self.mounting_tools = {
            "Native (Windows 8+)": {"special": "mount_native"}
        }
        
        # Populate mounting tools from repos.set
        if "DISCS" in self.repos:
            for key, data in self.repos["DISCS"].items():
                tool_data = data.copy()
                if key.lower() == "wincdemu":
                    tool_data["special"] = "mount_wincdemu"
                    self.mounting_tools["wincdemu"] = tool_data
                elif key.lower() == "osf":
                    tool_data["special"] = "mount_osf"
                    self.mounting_tools["osf"] = tool_data
                elif key.lower() == "cdmage":
                    tool_data["special"] = "mount_cdmage"
                    self.mounting_tools["cdmage"] = tool_data
                elif key.lower() == "imgdrive":
                    tool_data["special"] = "mount_imgdrive"
                    self.mounting_tools["imgdrive"] = tool_data

        self.download_thread = None
        
        self._setup_ui()

    def _add_path_row(self, layout, label_text, config_key, row_widget, tooltip_prefix=None):
        formatted_text = f"`^ {label_text}"
        label = QLabel(formatted_text)
        label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        base_tip = "Right-click to configure Options & Arguments"
        label.setToolTip(f"{tooltip_prefix} — {base_tip}" if tooltip_prefix else base_tip)
        label.customContextMenuRequested.connect(
            lambda pos: self._show_options_args_dialog(pos, config_key, label_text)
        )
        layout.addRow(label, row_widget)

    def _setup_ui(self):
        """Create and arrange all widgets for the Setup tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 0, 5)

        # --- Section 1: Sources & Indexing (5-col × 3-row grid) ---
        source_config_widget = QWidget()
        source_config_layout = QGridLayout(source_config_widget)
        source_config_layout.setSpacing(10)

        # Row stretch: 10% header / 55% content / 10% footer / 25% directories
        source_config_layout.setRowStretch(0, 10)
        source_config_layout.setRowStretch(1, 55)
        source_config_layout.setRowStretch(2, 10)
        source_config_layout.setRowStretch(3, 25)

        # Column stretch: A=3, B=3, C=1, D=2, E=2
        source_config_layout.setColumnStretch(0, 3)
        source_config_layout.setColumnStretch(1, 3)
        source_config_layout.setColumnStretch(2, 1)
        source_config_layout.setColumnStretch(3, 2)
        source_config_layout.setColumnStretch(4, 2)

        # ── a1 (row 0, col 0): Source Directories header ──
        source_label = QLabel("<b>Source Directories</b>")
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        source_config_layout.addWidget(source_label, 0, 0)

        # ── b1 (row 0, col 1): Add/Remove buttons for Source Dirs ──
        source_btn_widget = QWidget()
        source_btn_layout = QHBoxLayout(source_btn_widget)
        source_btn_layout.setContentsMargins(0, 0, 0, 0)
        add_source_button = QPushButton()
        add_source_button.setToolTip("Add a directory to scan for games.")
        add_source_button.setFixedWidth(30)
        add_source_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        remove_source_button = QPushButton()
        remove_source_button.setToolTip("Remove the selected directory from scanning.")
        remove_source_button.setFixedWidth(30)
        remove_source_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
        source_btn_layout.addWidget(add_source_button)
        source_btn_layout.addWidget(remove_source_button)
        source_btn_layout.addStretch()
        source_config_layout.addWidget(source_btn_widget, 0, 1, Qt.AlignmentFlag.AlignTop)

        self.add_source_dir_button = add_source_button
        self.remove_source_dir_button = remove_source_button

        # ── a2 (row 1, col 0): Source Directories listbox ──
        self.source_dirs_list = DragDropListWidget()
        source_config_layout.addWidget(self.source_dirs_list, 1, 0, Qt.AlignmentFlag.AlignTop)

        # ── b2 (row 1, col 1): Exclude Directories header + listbox ──
        excluded_col_widget = QWidget()
        excluded_col_layout = QVBoxLayout(excluded_col_widget)
        excluded_col_layout.setContentsMargins(0, 0, 0, 0)
        excluded_col_layout.setSpacing(2)
        excluded_col_layout.addStretch(4)  # push header 40% down
        excluded_col_layout.addSpacing(50)  # move header down an extra 50px
        excluded_label = QLabel("<b>Exclude Directories</b>")
        excluded_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        excluded_col_layout.addWidget(excluded_label)
        self.excluded_dirs_list = DragDropListWidget()
        excluded_col_layout.addWidget(self.excluded_dirs_list)
        source_config_layout.addWidget(excluded_col_widget, 1, 1, Qt.AlignmentFlag.AlignTop)

        # ── c2 (row 1, col 2): Add/Remove buttons for Excluded Dirs ──
        excluded_btn_widget = QWidget()
        excluded_btn_layout = QVBoxLayout(excluded_btn_widget)
        excluded_btn_layout.setContentsMargins(0, 0, 0, 0)
        add_excluded_button = QPushButton()
        add_excluded_button.setToolTip("Add a directory to exclude from scanning.")
        add_excluded_button.setFixedWidth(30)
        add_excluded_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        remove_excluded_button = QPushButton()
        remove_excluded_button.setToolTip("Remove the selected directory from exclusion.")
        remove_excluded_button.setFixedWidth(30)
        remove_excluded_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
        excluded_btn_layout.addWidget(add_excluded_button)
        excluded_btn_layout.addWidget(remove_excluded_button)
        excluded_btn_layout.addStretch()
        source_config_layout.addWidget(excluded_btn_widget, 1, 2, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

        self.add_excluded_dir_button = add_excluded_button
        self.remove_excluded_dir_button = remove_excluded_button

        # ── d1 (row 0, col 3): Config-file-history combobox ──
        # (preset_combo created in _setup_config_presets_ui, placed here later)

        # ── e1 (row 0, col 4): Config-file icon buttons ──
        # (preset_load/save/remove/browse_btn created in _setup_config_presets_ui, placed here later)

        # ── a3 (row 2, col 0): Exclude Manager checkbox ──
        self.exclude_manager_checkbox = QCheckBox("Exclude Selected Manager's Games")
        self.exclude_manager_checkbox.setToolTip("Exclude games belonging to the selected game manager from the source directory scan.")
        source_config_layout.addWidget(self.exclude_manager_checkbox, 2, 0, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft)

        # ── b3 (row 2, col 1): Game Managers dropdown ──
        self.other_managers_combo = QComboBox()
        self.other_managers_combo.addItems(["None", "Steam", "Epic", "GOG", "Origin", "Ubisoft Connect", "Battle.net", "Xbox"])
        self.other_managers_combo.setToolTip("Select which game manager is installed. Games managed by this platform will be excluded when the checkbox is enabled.")
        source_config_layout.addWidget(self.other_managers_combo, 2, 1, Qt.AlignmentFlag.AlignBottom)

        # Store reference for _setup_config_presets_ui to place combo + buttons
        self._sources_grid = source_config_layout

        # ── row 3 (spanning all cols): Directories ──
        directories_group = QGroupBox("Directories")
        directories_layout = QFormLayout(directories_group)
        self.path_rows["profiles_dir"] = PathConfigRow("profiles_dir", is_directory=True, add_enabled=True, add_cen_lc=True, use_combobox=False)
        self.path_rows["profiles_dir"].enabled_cb.setToolTip("Create Profile Folders")
        self.path_rows["profiles_dir"].cen_radio.setToolTip("Creates a centralized location for Profiles")
        self.path_rows["profiles_dir"].lc_radio.setToolTip("Creates Profiles in the Game Directory folder")
        self.path_rows["profiles_dir"].lc_radio.toggled.connect(self.path_rows["profiles_dir"]._on_lc_toggled)
        directories_layout.addRow("Profiles Directory:", self.path_rows["profiles_dir"])
        self.path_rows["launchers_dir"] = PathConfigRow("launchers_dir", is_directory=True, add_enabled=True, add_cen_lc=True, use_combobox=False)
        self.path_rows["launchers_dir"].enabled_cb.setToolTip("Create Launcher")
        self.path_rows["launchers_dir"].cen_radio.setToolTip("Creates a centralized location for Launchers")
        self.path_rows["launchers_dir"].lc_radio.setToolTip("Creates Launchers in the Game Directory folder")
        self.path_rows["launchers_dir"].lc_radio.toggled.connect(self.path_rows["launchers_dir"]._on_lc_toggled)
        directories_layout.addRow("Launchers Directory:", self.path_rows["launchers_dir"])
        source_config_layout.addWidget(directories_group, 3, 0, 1, 5)

        # --- Section 2: Paths & Profiles (9 plugin sub-tabs) ---
        paths_widget = QWidget()
        paths_layout = QVBoxLayout(paths_widget)
        paths_layout.setContentsMargins(0, 0, 0, 0)
        self.paths_tabs = QTabWidget()
        paths_layout.addWidget(self.paths_tabs)

        # Prepare repo items for generic lists (All except GLOBAL)
        all_tools = {}
        all_tools["Mount DISC"] = {"special": "mount_disc"}
        for section, items in self.repos.items():
            if section != "GLOBAL":
                all_tools.update(items)

        # Shared checkboxes
        self.run_as_admin_checkbox = QCheckBox("Run As Admin")
        self.run_as_admin_checkbox.setToolTip("Run the launcher with administrator privileges")
        self.use_kill_list_checkbox = QCheckBox("Use Kill List")
        self.use_kill_list_checkbox.setToolTip("Kill specific processes before launching")
        self.hide_taskbar_checkbox = QCheckBox("Hide Taskbar")
        self.hide_taskbar_checkbox.setToolTip("Hide the taskbar while the game is running")
        self.terminate_bw_on_exit_checkbox = QCheckBox("Terminate Borderless on Exit")
        self.terminate_bw_on_exit_checkbox.setToolTip("Terminate Borderless Gaming when game exits")

        # ── Tab 1: LAUNCHER ──────────────────────────────────────────────────
        launcher_tab = QWidget()
        launcher_tab_layout = QVBoxLayout(launcher_tab)
        launcher_group = QGroupBox("Launcher Configuration")
        launcher_layout = QFormLayout(launcher_group)
        self.path_rows["launcher_executable"] = PathConfigRow(
            "launcher_executable", is_directory=False, add_enabled=False, add_cen_lc=True, use_combobox=True)
        self._add_path_row(launcher_layout, "Launcher Executable:", "launcher_executable",
                           self.path_rows["launcher_executable"], tooltip_prefix="Set the path to the game's launcher executable")
        cb_container = QWidget()
        cb_layout = QGridLayout(cb_container)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        cb_layout.addWidget(self.run_as_admin_checkbox, 0, 0)
        cb_layout.addWidget(self.use_kill_list_checkbox, 0, 1)
        cb_layout.addWidget(self.hide_taskbar_checkbox, 1, 0)
        cb_layout.addWidget(self.terminate_bw_on_exit_checkbox, 1, 1)
        launcher_layout.addRow(cb_container)
        launcher_tab_layout.addWidget(launcher_group)
        launcher_tab_layout.addStretch()
        self.paths_tabs.addTab(launcher_tab, "LAUNCHER")

        # ── Tab 2: MAPPING ───────────────────────────────────────────────────
        mapping_tab = QWidget()
        mapping_tab_layout = QVBoxLayout(mapping_tab)
        mapper_group = QGroupBox("Controller Mapper")
        mapper_layout = QFormLayout(mapper_group)
        self.path_rows["controller_mapper_path"] = PathConfigRow(
            "controller_mapper_path", add_run_wait=True, repo_items=self.repos.get("MAPPERS"))
        self.path_rows["controller_mapper_path"].enabled_cb.setToolTip("Enable Controller Mapper")
        self._add_path_row(mapper_layout, "Controller Mapper:", "controller_mapper_path",
                           self.path_rows["controller_mapper_path"], tooltip_prefix="Set the path to the controller mapper tool")
        self.path_rows["p1_profile_path"] = PathConfigRow("p1_profile_path", add_enabled=True)
        self._add_path_row(mapper_layout, "    Player 1 Profile:", "p1_profile_path", self.path_rows["p1_profile_path"],
                           tooltip_prefix="Set the path to Player 1's controller profile")
        self.path_rows["p2_profile_path"] = PathConfigRow("p2_profile_path", add_enabled=True)
        self._add_path_row(mapper_layout, "    Player 2 Profile:", "p2_profile_path", self.path_rows["p2_profile_path"],
                           tooltip_prefix="Set the path to Player 2's controller profile")
        self.path_rows["desk_profile_path"] = PathConfigRow("desk_profile_path", add_enabled=True)
        self._add_path_row(mapper_layout, "    Desk Profile:", "desk_profile_path", self.path_rows["desk_profile_path"],
                           tooltip_prefix="Set the path to the desktop controller profile")
        mapping_tab_layout.addWidget(mapper_group)
        mapping_tab_layout.addStretch()
        self.paths_tabs.addTab(mapping_tab, "MAPPING")

        # ── Tab 3: DISPLAY ───────────────────────────────────────────────────
        display_tab = QWidget()
        display_tab_layout = QVBoxLayout(display_tab)
        display_group = QGroupBox("Monitor Configuration Tool")
        display_layout = QFormLayout(display_group)
        self.path_rows["monitorapp_path"] = PathConfigRow(
            "monitorapp_path", add_run_wait=True, repo_items=self.repos.get("DISPLAY"), empty_combo=True)
        self.path_rows["monitorapp_path"].enabled_cb.setToolTip("Enable monitor app")
        self.path_rows["monitorapp_path"].enabled_cb.stateChanged.connect(
            self._on_monitorapp_enabled_changed)
        
        # Prioritize multimonitortool.exe from the freeduction bin directory
        repo_root = Path(__file__).resolve().parents[2]
        for subdir, exe in [("multimonitortool", "multimonitortool.exe"), ("multimonitortool", "MultiMonitorTool.exe")]:
            native_path = str(repo_root / "bin" / subdir / exe)
            if os.path.exists(native_path):
                combo = self.path_rows["monitorapp_path"].combo
                if combo.findText(native_path) == -1:
                    combo.insertItem(0, native_path)
                combo.setCurrentIndex(0)
                self.path_rows["monitorapp_path"].combo.setEnabled(True)
                self.path_rows["monitorapp_path"].combo.lineEdit().setReadOnly(True)
                break

        self.wizard_btn = QPushButton("Open Monitor Wizard")
        self.wizard_btn.setToolTip("Open the monitor wizard to query supported resolutions, refresh rates, and bit depths")
        self.wizard_btn.clicked.connect(self._on_wizard_button_clicked)
        self.wizard_btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        wizard_button_row = QWidget()
        wizard_button_layout = QHBoxLayout(wizard_button_row)
        wizard_button_layout.setContentsMargins(0, 0, 0, 0)
        wizard_button_layout.addWidget(self.wizard_btn)
        display_layout.addRow(wizard_button_row)

        display_note = QLabel(
            "Choose a display tool that can report supported resolutions, refresh rates, and bit depths for monitor presets."
        )
        display_note.setWordWrap(True)
        display_layout.addRow(display_note)

        self._add_path_row(display_layout, "Monitor-Config App:", "monitorapp_path",
                           self.path_rows["monitorapp_path"], tooltip_prefix="Set the path to the monitor configuration tool")
        self.path_rows["monitor_game_path"] = PathConfigRow("monitor_game_path", add_enabled=True)
        self._add_path_row(display_layout, "    Monitor Game Config:", "monitor_game_path", self.path_rows["monitor_game_path"],
                           tooltip_prefix="Set the path to the game's monitor configuration")
        self.path_rows["monitor_desk_path"] = PathConfigRow("monitor_desk_path", add_enabled=True)
        self._add_path_row(display_layout, "    Monitor Desk Config:", "monitor_desk_path", self.path_rows["monitor_desk_path"],
                           tooltip_prefix="Set the path to the desktop monitor configuration")
        display_tab_layout.addWidget(display_group)
        display_tab_layout.addStretch()
        self.paths_tabs.addTab(display_tab, "DISPLAY")

        # ── Tab 4: WINDOWING ─────────────────────────────────────────────────
        windowing_tab = QWidget()
        windowing_tab_layout = QVBoxLayout(windowing_tab)
        windowing_group = QGroupBox("Borderless Windowing")
        windowing_layout = QFormLayout(windowing_group)
        self.path_rows["borderless_gaming_path"] = PathConfigRow(
            "borderless_gaming_path", add_run_wait=True, repo_items=self.repos.get("WINDOWING"))
        self.path_rows["borderless_gaming_path"].enabled_cb.setToolTip("Enable Borderless Windowing")
        self._add_path_row(windowing_layout, "Borderless Windowing:", "borderless_gaming_path",
                           self.path_rows["borderless_gaming_path"], tooltip_prefix="Set the path to the borderless windowing tool")
        self.path_rows["unborder_cfg"] = PathConfigRow(
            "unborder_cfg", add_enabled=True, add_cen_lc=True, use_combobox=True)
        self.path_rows["unborder_cfg"].enabled_cb.setToolTip("Enable UnBorder Config")
        self._add_path_row(windowing_layout, "UnBorder Config:", "unborder_cfg",
                           self.path_rows["unborder_cfg"], tooltip_prefix="Set the path to the unborder configuration file")
        self.path_rows["reborder_cfg"] = PathConfigRow(
            "reborder_cfg", add_enabled=True, add_cen_lc=True, use_combobox=True)
        self.path_rows["reborder_cfg"].enabled_cb.setToolTip("Enable ReBorder Config")
        self._add_path_row(windowing_layout, "ReBorder Config:", "reborder_cfg",
                           self.path_rows["reborder_cfg"], tooltip_prefix="Set the path to the reborder configuration file")
        windowing_tab_layout.addWidget(windowing_group)
        windowing_tab_layout.addStretch()
        self.paths_tabs.addTab(windowing_tab, "WINDOWING")

        # ── Tab 5: DISC-MOUNTING ─────────────────────────────────────────────
        disc_tab = QWidget()
        disc_tab_layout = QVBoxLayout(disc_tab)
        disc_group = QGroupBox("Disc Mount / Unmount")
        disc_layout = QFormLayout(disc_group)
        self.path_rows["disc_mount_path"] = PathConfigRow(
            "disc_mount_path", add_run_wait=True, repo_items=self.mounting_tools, add_cen_lc=True, add_enabled=True)
        self.path_rows["disc_mount_path"].enabled_cb.setToolTip("Overwrite Mounting")
        self._add_path_row(disc_layout, "Disc-Mount:", "disc_mount_path", self.path_rows["disc_mount_path"],
                           tooltip_prefix="Set the path to the disc mounting tool")
        self.path_rows["disc_mount_cfg"] = PathConfigRow(
            "disc_mount_cfg", add_enabled=True, add_cen_lc=True, use_combobox=True)
        self.path_rows["disc_mount_cfg"].enabled_cb.setToolTip("Enable Disc Mount Config File")
        self._add_path_row(disc_layout, "    Mount Config:", "disc_mount_cfg",
                           self.path_rows["disc_mount_cfg"], tooltip_prefix="Set the path to the mount configuration file")
        self.path_rows["disc_unmount_cfg"] = PathConfigRow(
            "disc_unmount_cfg", add_enabled=True, add_cen_lc=True, use_combobox=True)
        self.path_rows["disc_unmount_cfg"].enabled_cb.setToolTip("Enable Disc Unmount Config File")
        self._add_path_row(disc_layout, "    Unmount Config:", "disc_unmount_cfg",
                           self.path_rows["disc_unmount_cfg"], tooltip_prefix="Set the path to the unmount configuration file")
        disc_tab_layout.addWidget(disc_group)
        disc_tab_layout.addStretch()
        self.paths_tabs.addTab(disc_tab, "DISC-MOUNTING")

        # ── Tab 6: LOCAL-BACKUP ──────────────────────────────────────────────
        local_backup_tab = QWidget()
        local_backup_tab_layout = QVBoxLayout(local_backup_tab)
        local_backup_group = QGroupBox("Local Backup")
        local_backup_form = QFormLayout(local_backup_group)
        local_backup_tools = {}
        if "LOCAL_BACKUP" in self.repos:
            local_backup_tools.update(self.repos["LOCAL_BACKUP"])
        self.path_rows["local_backup_path"] = PathConfigRow(
            "local_backup_path", add_run_wait=True, add_cen_lc=True, add_enabled=True,
            repo_items=local_backup_tools)
        self.path_rows["local_backup_path"].enabled_cb.setToolTip("Enable Local Backup")
        self._add_path_row(local_backup_form, "Local Backup:", "local_backup_path",
                           self.path_rows["local_backup_path"], tooltip_prefix="Set the path to the local backup tool")

        # Tool-specific settings via QStackedWidget
        self.local_backup_tool_combo = QComboBox()
        self.local_backup_tool_combo.addItems(["Save State", "Game Save Manager", "Game Backup Monitor"])
        self.local_backup_tool_combo.currentIndexChanged.connect(self._on_local_backup_tool_changed)

        self.local_backup_stack = QStackedWidget()

        # Page 0: Save State
        savestate_page = QWidget()
        savestate_layout = QFormLayout(savestate_page)
        self.savestate_backup_path_row = PathConfigRow("savestate_backup_path", is_directory=True, add_enabled=False)
        savestate_layout.addRow("Backup Directory:", self.savestate_backup_path_row)
        self.savestate_auto_backup_cb = QCheckBox("Auto Backup")
        self.savestate_auto_backup_cb.setChecked(True)
        self.savestate_auto_backup_cb.setToolTip("Automatically backup save states when the game exits")
        savestate_layout.addRow("", self.savestate_auto_backup_cb)
        self.local_backup_stack.addWidget(savestate_page)

        # Page 1: Game Save Manager
        gsm_page = QWidget()
        gsm_layout = QFormLayout(gsm_page)
        self.gsm_backup_path_row = PathConfigRow("gsm_backup_path", is_directory=True, add_enabled=False)
        gsm_layout.addRow("Backup Directory:", self.gsm_backup_path_row)
        self.gsm_backup_on_exit_cb = QCheckBox("Backup on Exit")
        self.gsm_backup_on_exit_cb.setChecked(True)
        self.gsm_backup_on_exit_cb.setToolTip("Backup game saves when the game exits")
        gsm_layout.addRow("", self.gsm_backup_on_exit_cb)
        self.local_backup_stack.addWidget(gsm_page)

        # Page 2: Game Backup Monitor
        gbm_page = QWidget()
        gbm_layout = QFormLayout(gbm_page)
        self.gbm_backup_path_row = PathConfigRow("gbm_backup_path", is_directory=True, add_enabled=False)
        gbm_layout.addRow("Backup Directory:", self.gbm_backup_path_row)
        self.gbm_monitor_on_launch_cb = QCheckBox("Monitor on Launch")
        self.gbm_monitor_on_launch_cb.setChecked(True)
        self.gbm_monitor_on_launch_cb.setToolTip("Start monitoring for save changes when the game launches")
        gbm_layout.addRow("", self.gbm_monitor_on_launch_cb)
        self.local_backup_stack.addWidget(gbm_page)

        local_backup_form.addRow("Tool:", self.local_backup_tool_combo)
        local_backup_form.addRow(self.local_backup_stack)
        local_backup_tab_layout.addWidget(local_backup_group)
        local_backup_tab_layout.addStretch()
        self.paths_tabs.addTab(local_backup_tab, "LOCAL-BACKUP")

        # ── Tab 7: CLOUD-SYNC ────────────────────────────────────────────────
        cloud_sync_tab = QWidget()
        cloud_sync_tab_layout = QVBoxLayout(cloud_sync_tab)
        cloud_sync_group = QGroupBox("Cloud Sync / Backup")
        cloud_sync_form = QFormLayout(cloud_sync_group)
        cloud_sync_tools = {}
        if "SYNC" in self.repos:
            cloud_sync_tools.update(self.repos["SYNC"])
        self.path_rows["cloud_sync_path"] = PathConfigRow(
            "cloud_sync_path", add_run_wait=True, add_cen_lc=True, add_enabled=True,
            repo_items=cloud_sync_tools)
        self.path_rows["cloud_sync_path"].enabled_cb.setToolTip("Enable Cloud Sync/Backup")
        self._add_path_row(cloud_sync_form, "Cloud Sync:", "cloud_sync_path",
                           self.path_rows["cloud_sync_path"], tooltip_prefix="Set the path to the cloud sync tool")

        # Tool-specific settings via QStackedWidget
        self.cloud_sync_tool_combo = QComboBox()
        self.cloud_sync_tool_combo.addItems(["Rclone", "Ludusavi", "Syncthing", "EmuSync"])
        self.cloud_sync_tool_combo.currentIndexChanged.connect(self._on_cloud_sync_tool_changed)

        self.cloud_sync_stack = QStackedWidget()

        # Page 0: Rclone
        rclone_page = QWidget()
        rclone_layout = QFormLayout(rclone_page)
        self.rclone_remote_name_edit = QLineEdit()
        self.rclone_remote_name_edit.setPlaceholderText("e.g., gdrive:")
        rclone_layout.addRow("Remote Name:", self.rclone_remote_name_edit)
        self.rclone_local_path_row = PathConfigRow("rclone_local_path", is_directory=True, add_enabled=False)
        rclone_layout.addRow("Local Save Path:", self.rclone_local_path_row)
        self.rclone_remote_path_edit = QLineEdit()
        self.rclone_remote_path_edit.setPlaceholderText("e.g., GameSaves/MyGame")
        rclone_layout.addRow("Remote Path:", self.rclone_remote_path_edit)
        self.rclone_sync_mode_combo = QComboBox()
        self.rclone_sync_mode_combo.addItems(["sync", "copy", "copyto"])
        self.rclone_sync_mode_combo.setToolTip("sync=bidirectional, copy=upload only, copyto=download only")
        rclone_layout.addRow("Sync Mode:", self.rclone_sync_mode_combo)
        self.rclone_backup_on_launch_cb = QCheckBox("Backup on Launch (download saves)")
        self.rclone_backup_on_launch_cb.setToolTip("Download saves from cloud when the game launches")
        rclone_layout.addRow("", self.rclone_backup_on_launch_cb)
        self.rclone_backup_on_exit_cb = QCheckBox("Backup on Exit (upload saves)")
        self.rclone_backup_on_exit_cb.setChecked(True)
        self.rclone_backup_on_exit_cb.setToolTip("Upload saves to cloud when the game exits")
        rclone_layout.addRow("", self.rclone_backup_on_exit_cb)
        self.cloud_sync_stack.addWidget(rclone_page)

        # Page 1: Ludusavi
        ludusavi_page = QWidget()
        ludusavi_layout = QFormLayout(ludusavi_page)
        self.ludusavi_backup_path_row = PathConfigRow("ludusavi_backup_path", is_directory=True, add_enabled=False)
        ludusavi_layout.addRow("Backup Directory:", self.ludusavi_backup_path_row)
        self.ludusavi_game_name_edit = QLineEdit()
        self.ludusavi_game_name_edit.setPlaceholderText("Leave empty for auto-detection")
        ludusavi_layout.addRow("Game Name:", self.ludusavi_game_name_edit)
        self.ludusavi_backup_on_launch_cb = QCheckBox("Restore on Launch")
        self.ludusavi_backup_on_launch_cb.setToolTip("Restore game saves from backup when the game launches")
        ludusavi_layout.addRow("", self.ludusavi_backup_on_launch_cb)
        self.ludusavi_backup_on_exit_cb = QCheckBox("Backup on Exit")
        self.ludusavi_backup_on_exit_cb.setChecked(True)
        self.ludusavi_backup_on_exit_cb.setToolTip("Backup game saves when the game exits")
        ludusavi_layout.addRow("", self.ludusavi_backup_on_exit_cb)
        self.cloud_sync_stack.addWidget(ludusavi_page)

        # Page 2: Syncthing
        syncthing_page = QWidget()
        syncthing_layout = QFormLayout(syncthing_page)
        self.syncthing_sync_folder_row = PathConfigRow("syncthing_sync_folder", is_directory=True, add_enabled=False)
        syncthing_layout.addRow("Sync Folder:", self.syncthing_sync_folder_row)
        self.syncthing_auto_start_cb = QCheckBox("Auto Start with Game")
        self.syncthing_auto_start_cb.setChecked(True)
        self.syncthing_auto_start_cb.setToolTip("Automatically start Syncthing when the game launches")
        syncthing_layout.addRow("", self.syncthing_auto_start_cb)
        self.cloud_sync_stack.addWidget(syncthing_page)

        # Page 3: EmuSync
        emusync_page = QWidget()
        emusync_layout = QFormLayout(emusync_page)
        self.emusync_emulator_path_row = PathConfigRow("emusync_emulator_path", is_directory=True, add_enabled=False)
        emusync_layout.addRow("Emulator Directory:", self.emusync_emulator_path_row)
        self.emusync_sync_on_launch_cb = QCheckBox("Sync on Launch")
        self.emusync_sync_on_launch_cb.setChecked(True)
        self.emusync_sync_on_launch_cb.setToolTip("Sync emulator saves when the game launches")
        emusync_layout.addRow("", self.emusync_sync_on_launch_cb)
        self.emusync_sync_on_exit_cb = QCheckBox("Sync on Exit")
        self.emusync_sync_on_exit_cb.setChecked(True)
        self.emusync_sync_on_exit_cb.setToolTip("Sync emulator saves when the game exits")
        emusync_layout.addRow("", self.emusync_sync_on_exit_cb)
        self.cloud_sync_stack.addWidget(emusync_page)

        cloud_sync_form.addRow("Tool:", self.cloud_sync_tool_combo)
        cloud_sync_form.addRow(self.cloud_sync_stack)
        cloud_sync_tab_layout.addWidget(cloud_sync_group)
        cloud_sync_tab_layout.addStretch()
        self.paths_tabs.addTab(cloud_sync_tab, "CLOUD-SYNC")

        # ── Tab 8: AUDIO ─────────────────────────────────────────────────────
        audio_tab = QWidget()
        audio_tab_layout = QVBoxLayout(audio_tab)
        audio_group = QGroupBox("Audio Configuration")
        audio_layout = QFormLayout(audio_group)
        audio_tools = {}
        if "AUDIO" in self.repos:
            audio_tools.update(self.repos["AUDIO"])
        self.path_rows["audio_tool_path"] = PathConfigRow(
            "audio_tool_path", add_run_wait=True, add_enabled=True,
            repo_items=audio_tools if audio_tools else None)
        self.path_rows["audio_tool_path"].enabled_cb.setToolTip("Enable Audio Tool")
        self._add_path_row(audio_layout, "Audio Tool:", "audio_tool_path",
                           self.path_rows["audio_tool_path"], tooltip_prefix="Set the path to the audio configuration tool")
        self.path_rows["audio_game_cfg"] = PathConfigRow(
            "audio_game_cfg", add_enabled=True, add_cen_lc=True, use_combobox=True)
        self.path_rows["audio_game_cfg"].enabled_cb.setToolTip("Enable Game Audio Config")
        self._add_path_row(audio_layout, "    Game-Audio:", "audio_game_cfg",
                           self.path_rows["audio_game_cfg"], tooltip_prefix="Set the path to the game's audio configuration")
        self.path_rows["audio_desk_cfg"] = PathConfigRow(
            "audio_desk_cfg", add_enabled=True, add_cen_lc=True, use_combobox=True)
        self.path_rows["audio_desk_cfg"].enabled_cb.setToolTip("Enable Desk Audio Config")
        self._add_path_row(audio_layout, "    Desk/OS-Audio:", "audio_desk_cfg",
                           self.path_rows["audio_desk_cfg"], tooltip_prefix="Set the path to the desktop audio configuration")
        audio_tab_layout.addWidget(audio_group)
        audio_tab_layout.addStretch()
        self.paths_tabs.addTab(audio_tab, "AUDIO")

        # ── Tab 9: PRE/POST SCRIPTS ──────────────────────────────────────────
        scripts_tab = QWidget()
        scripts_tab_layout = QVBoxLayout(scripts_tab)
        scripts_group = QGroupBox("Pre / Post Launch Scripts")
        scripts_layout = QFormLayout(scripts_group)
        for i in range(1, 4):
            key = f"pre{i}_path"
            self.path_rows[key] = PathConfigRow(key, add_run_wait=True, repo_items=all_tools)
            self.path_rows[key].enabled_cb.setToolTip(f"Enable Pre-Launch App {i}")
            self._add_path_row(scripts_layout, f"Pre-Launch App {i}:", key, self.path_rows[key],
                               tooltip_prefix=f"Set the path to pre-launch application {i}")
        self.path_rows["just_after_launch_path"] = PathConfigRow(
            "just_after_launch_path", add_run_wait=True, repo_items=all_tools)
        self.path_rows["just_after_launch_path"].enabled_cb.setToolTip("Enable Just After Launch App")
        self._add_path_row(scripts_layout, "    Just After Launch:", "just_after_launch_path",
                           self.path_rows["just_after_launch_path"], tooltip_prefix="Set the path to the application that runs just after launch")
        self.path_rows["just_before_exit_path"] = PathConfigRow(
            "just_before_exit_path", add_run_wait=True, repo_items=all_tools)
        self.path_rows["just_before_exit_path"].enabled_cb.setToolTip("Enable Just Before Exit App")
        self._add_path_row(scripts_layout, "    Just Before Exit:", "just_before_exit_path",
                           self.path_rows["just_before_exit_path"], tooltip_prefix="Set the path to the application that runs just before exit")
        for i in range(1, 4):
            key = f"post{i}_path"
            self.path_rows[key] = PathConfigRow(key, add_run_wait=True, repo_items=all_tools)
            self.path_rows[key].enabled_cb.setToolTip(f"Enable Post-Launch App {i}")
            self._add_path_row(scripts_layout, f"Post-Launch App {i}:", key, self.path_rows[key],
                               tooltip_prefix=f"Set the path to post-launch application {i}")
        scripts_tab_layout.addWidget(scripts_group)
        scripts_tab_layout.addStretch()
        self.paths_tabs.addTab(scripts_tab, "PRE/POST SCRIPTS")

        # --- Section 3: Execution Sequence ---
        sequences_widget = QWidget()
        sequences_layout = QHBoxLayout(sequences_widget)

        # Launch Sequence
        launch_sequence_group = QGroupBox("LAUNCH ORDER")
        launch_sequence_layout = QVBoxLayout(launch_sequence_group)
        self.launch_sequence_list = DragDropListWidget()
        self.launch_sequence_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.launch_sequence_list.customContextMenuRequested.connect(lambda pos: self._on_sequence_context_menu(pos, self.launch_sequence_list, "launch"))
        self.reset_launch_btn = QPushButton("Reset")
        launch_sequence_layout.addWidget(self.launch_sequence_list)
        launch_sequence_layout.addWidget(self.reset_launch_btn)
        sequences_layout.addWidget(launch_sequence_group)

        # Exit Sequence
        exit_sequence_group = QGroupBox("EXIT ORDER")
        exit_sequence_layout = QVBoxLayout(exit_sequence_group)
        self.exit_sequence_list = DragDropListWidget()
        self.exit_sequence_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.exit_sequence_list.customContextMenuRequested.connect(lambda pos: self._on_sequence_context_menu(pos, self.exit_sequence_list, "exit"))
        self.reset_exit_btn = QPushButton("Reset")
        exit_sequence_layout.addWidget(self.exit_sequence_list)
        exit_sequence_layout.addWidget(self.reset_exit_btn)
        sequences_layout.addWidget(exit_sequence_group)

        # --- Section 4: Behavior ---
        behavior_widget = QWidget()
        behavior_layout = QFormLayout(behavior_widget)
        # Logging Verbosity
        self.logging_verbosity_combo = QComboBox()
        self.logging_verbosity_combo.addItems(["None", "Low", "Medium", "High", "Debug"])
        behavior_layout.addRow("LOGGING VERBOSITY:", self.logging_verbosity_combo)
        
        # Fuzzy Match Cutoff
        self.fuzzy_match_spin = QDoubleSpinBox()
        self.fuzzy_match_spin.setRange(0.1, 1.0)
        self.fuzzy_match_spin.setSingleStep(0.05)
        self.fuzzy_match_spin.setToolTip("Sensitivity for fuzzy name matching (0.1 = loose, 1.0 = exact). Default: 0.6")
        behavior_layout.addRow("Fuzzy Match Sensitivity:", self.fuzzy_match_spin)

        # Plugin Manager Button
        self.plugin_manager_btn = QPushButton("Plugin Manager")
        self.plugin_manager_btn.setToolTip("Open Plugin Manager to view, enable/disable, and manage plugins")
        self.plugin_manager_btn.clicked.connect(self._open_plugin_manager)
        behavior_layout.addRow("Plugins:", self.plugin_manager_btn)
        
        # Restart Button
        self.restart_btn = QPushButton("Reset to Defaults")
        self.restart_btn.setToolTip("Reset all application configuration to defaults")
        behavior_layout.addRow(self.restart_btn)

        # --- Section 5: Appearance ---
        appearance_widget = QWidget()
        appearance_layout = QFormLayout(appearance_widget)

        self.theme_selector = QComboBox()
        theme_manager = ThemeManager()
        available_themes = dict(theme_manager.list_available_themes())
        for theme_id in ThemeManager.THEME_IDS:
            if theme_id in available_themes:
                display_name = available_themes[theme_id]
                self.theme_selector.addItem(display_name)
                self.theme_selector.setItemData(self.theme_selector.count() - 1, theme_id)
            else:
                # Determine display name from a temporary provider instance
                provider = theme_manager._registry.get(theme_id)
                display_name = provider.name if provider else theme_id
                self.theme_selector.addItem(display_name)
                idx = self.theme_selector.count() - 1
                self.theme_selector.setItemData(idx, theme_id)
                # Disable the item
                model = self.theme_selector.model()
                item = model.item(idx)
                if item:
                    item.setEnabled(False)
                    item.setToolTip("Library not installed")

        # UI Theme Row
        theme_row = QHBoxLayout()
        theme_row.addWidget(self.theme_selector)
        self.reset_theme_btn = QPushButton("Reset")
        self.reset_theme_btn.setFixedWidth(50)
        self.reset_theme_btn.clicked.connect(self._reset_theme)
        theme_row.addWidget(self.reset_theme_btn)
        appearance_layout.addRow("UI THEME:", theme_row)

        # UI Font Row
        ui_font_row = QHBoxLayout()
        self.font_selector = QFontComboBox()
        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 24)
        self.font_size_spin.setSuffix(" pt")
        self.reset_ui_font_btn = QPushButton("Reset")
        self.reset_ui_font_btn.setFixedWidth(50)
        self.reset_ui_font_btn.clicked.connect(self._reset_ui_font)
        
        ui_font_row.addWidget(self.font_selector, 2)
        ui_font_row.addWidget(self.font_size_spin, 1)
        ui_font_row.addWidget(self.reset_ui_font_btn)
        appearance_layout.addRow("UI FONT:", ui_font_row)

        # Editor Font Row
        editor_font_row = QHBoxLayout()
        self.editor_font_selector = QFontComboBox()
        self.editor_font_size_spin = QSpinBox()
        self.editor_font_size_spin.setRange(6, 24)
        self.editor_font_size_spin.setSuffix(" pt")
        self.reset_editor_font_btn = QPushButton("Reset")
        self.reset_editor_font_btn.setFixedWidth(50)
        self.reset_editor_font_btn.clicked.connect(self._reset_editor_font)

        editor_font_row.addWidget(self.editor_font_selector, 2)
        editor_font_row.addWidget(self.editor_font_size_spin, 1)
        editor_font_row.addWidget(self.reset_editor_font_btn)
        appearance_layout.addRow("EDITOR FONT:", editor_font_row)

        # --- Section 6: Configuration Presets (rows within BEHAVIOR) ---
        # The preset control widgets are built here and later injected into the
        # BEHAVIOR section's form layout (see _setup_config_presets_ui).
        self._setup_config_presets_ui(behavior_layout)

        # --- Slide-menu navigation with one content page per section ---
        self._slide_panel = SlideMenuPanel(self)
        self._slide_panel.add_section(
            "SOURCES AND INDEXING", source_config_widget,
            icon=section_icon("folder"),
        )
        self._slide_panel.add_section(
            "PATHS AND PROFILES", paths_widget,
            icon=section_icon("folder_arrow"),
        )
        self._slide_panel.add_section(
            "EXECUTION SEQUENCES", sequences_widget,
            icon=section_icon("play"),
        )
        self._slide_panel.add_section(
            "BEHAVIOR", behavior_widget,
            icon=section_icon("sliders"),
        )
        self._slide_panel.add_section(
            "APPEARANCE", appearance_widget,
            icon=section_icon("monitor"),
        )
        self._slide_panel.set_current_index(0)
        main_layout.addWidget(self._slide_panel)
        self._connect_signals()

        # Populate Launcher Executable Combobox
        self._populate_launcher_combo()

        # Build the preset manager + populate the presets combobox
        self._init_config_preset_manager()

    def _populate_launcher_combo(self):
        """Populate the launcher executable combobox with valid files from bin."""
        # If launcher_executable is not a combobox, skip population
        if not self.path_rows["launcher_executable"].use_combobox:
            return
        
        combo = self.path_rows["launcher_executable"].combo
        
        # Clear any existing items first
        combo.clear()
        
        # The preferred default launcher
        default_launcher = constants.LAUNCHER_EXECUTABLE  # bin/Launcher.exe
        
        # Scan bin directory for launcher-related files
        bin_dir = os.path.join(constants.APP_ROOT_DIR, "bin")
        launcher_files = []
        
        if os.path.exists(bin_dir):
            # Valid extensions for executables, shortcuts, and scripts
            valid_extensions = {'.exe', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.lnk', '.url'}
            
            for f in os.listdir(bin_dir):
                name, ext = os.path.splitext(f)
                # Check if filename contains "launcher" (case-insensitive) and has valid extension
                if "launcher" in name.lower() and ext.lower() in valid_extensions:
                    full_path = os.path.join(bin_dir, f)
                    launcher_files.append((f, full_path))
        
        # Sort launcher files, but prioritize Launcher.exe first
        def sort_key(item):
            filename, _ = item
            # Launcher.exe gets priority 0, everything else gets priority 1
            if filename.lower() == "launcher.exe":
                return (0, filename.lower())
            else:
                return (1, filename.lower())
        
        launcher_files.sort(key=sort_key)
        
        # Add all launcher files to combo
        for filename, full_path in launcher_files:
            combo.addItem(full_path)
        
        # Set the default launcher as the current selection if it exists
        if os.path.exists(default_launcher):
            idx = combo.findText(default_launcher)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            else:
                # If somehow not in list, add it and select it
                combo.insertItem(0, default_launcher)
                combo.setCurrentIndex(0)
        
        # Set placeholder text for the combo's line edit
        if combo.lineEdit():
            combo.lineEdit().setPlaceholderText(default_launcher)

    # ──────────────────────────────────────────────────────────────────
    # Configuration Presets section
    # ──────────────────────────────────────────────────────────────────
    def _setup_config_presets_ui(self, behavior_layout: QFormLayout):
        """Build the Configuration Presets UI.

        The current-config combobox is placed in cell d1 (row 0, col 3) and
        the action buttons in cell e1 (row 0, col 4) of the SOURCES AND
        INDEXING grid.  The Ovr/Add radios, Index button and search-roots
        field (plus a header) are added as rows to the BEHAVIOR form layout.
        """
        # ── d1 (row 0, col 3): Config-file-history combobox ──
        self.preset_combo = QComboBox()
        self.preset_combo.setEditable(True)
        self.preset_combo.setToolTip("Currently loaded configuration file (or the LOCAL default preset)")
        self.preset_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if hasattr(self, "_sources_grid"):
            self._sources_grid.addWidget(self.preset_combo, 0, 3, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        # ── e1 (row 0, col 4): Config-file action buttons ──
        preset_btn_widget = QWidget()
        preset_btn_layout = QHBoxLayout(preset_btn_widget)
        preset_btn_layout.setContentsMargins(0, 0, 0, 0)
        preset_btn_layout.setSpacing(4)

        # <Ld  - Load a json file's settings (adopting the current ${approot})
        self.preset_load_btn = QPushButton()
        self.preset_load_btn.setFixedWidth(36)
        self.preset_load_btn.setToolTip("Load a json file's settings (adopting the current ${approot}).")
        self.preset_load_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogOpenButton))
        self.preset_load_btn.clicked.connect(self._on_preset_load)
        preset_btn_layout.addWidget(self.preset_load_btn)

        # As>  - Create a config using the current settings
        self.preset_save_btn = QPushButton()
        self.preset_save_btn.setFixedWidth(36)
        self.preset_save_btn.setToolTip("Create a config using the current settings.")
        self.preset_save_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogSaveButton))
        self.preset_save_btn.clicked.connect(self._on_preset_save)
        preset_btn_layout.addWidget(self.preset_save_btn)

        # -x  - Remove the visible path from history (right-click resets history)
        self.preset_remove_btn = QPushButton()
        self.preset_remove_btn.setFixedWidth(36)
        self.preset_remove_btn.setToolTip("Remove the file path currently visible in the combobox from the history.")
        self.preset_remove_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.preset_remove_btn.clicked.connect(self._on_preset_remove)
        self.preset_remove_menu = QMenu(self.preset_remove_btn)
        self.preset_remove_menu.addAction(
            "Reset history", self._on_preset_reset_history
        )
        self.preset_remove_btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.preset_remove_btn.customContextMenuRequested.connect(
            lambda pos: self.preset_remove_menu.exec(self.preset_remove_btn.mapToGlobal(pos))
        )
        preset_btn_layout.addWidget(self.preset_remove_btn)

        # ...  - Set the location/name of the current settings to load on startup
        self.preset_browse_btn = QPushButton()
        self.preset_browse_btn.setFixedWidth(36)
        self.preset_browse_btn.setToolTip(
            "Set the location and name for the current settings to load upon startup "
            f"(defaults to {constants.APP_ROOT_DIR}/{DEFAULT_CONFIG_JSON})."
        )
        self.preset_browse_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.preset_browse_btn.clicked.connect(self._on_preset_browse)
        preset_btn_layout.addWidget(self.preset_browse_btn)

        if hasattr(self, "_sources_grid"):
            self._sources_grid.addWidget(preset_btn_widget, 0, 4, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        # ── BEHAVIOR section rows: radios + Index button + search roots ──
        header = QLabel("<b>Configuration Presets</b>")
        header.setAlignment(Qt.AlignmentFlag.AlignLeft)
        behavior_layout.addRow(header)

        # Row 2: Ovr / Add radio pair + Index button + search roots
        mid_row = QWidget()
        mid_layout = QHBoxLayout(mid_row)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(6)

        self.preset_mode_group = QButtonGroup(self)
        self.preset_overwrite_rb = QRadioButton("Ovr")
        self.preset_overwrite_rb.setToolTip("Overwrite current values with those in the selected json-config file.")
        self.preset_overwrite_rb.setChecked(True)
        self.preset_append_rb = QRadioButton("Add")
        self.preset_append_rb.setToolTip("Append values found in the selected json-config file.")
        self.preset_mode_group.addButton(self.preset_overwrite_rb)
        self.preset_mode_group.addButton(self.preset_append_rb)
        mid_layout.addWidget(self.preset_overwrite_rb)
        mid_layout.addWidget(self.preset_append_rb)

        mid_layout.addSpacing(10)

        # I  - Index the specified directories for json-config files
        self.preset_index_btn = QPushButton("I")
        self.preset_index_btn.setFixedWidth(30)
        self.preset_index_btn.setToolTip("Index the specified directories for json-config files.")
        self.preset_index_btn.clicked.connect(self._on_preset_index)
        mid_layout.addWidget(self.preset_index_btn)

        self.preset_search_roots_edit = QLineEdit()
        self.preset_search_roots_edit.setPlaceholderText(
            "Pipe-delimited search paths (e.g. C:/Games|K:/Profiles); "
            f"{constants.APP_ROOT_DIR} and each path's parent are always included."
        )
        self.preset_search_roots_edit.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        mid_layout.addWidget(self.preset_search_roots_edit, 1)

        behavior_layout.addRow(mid_row)

    def _init_config_preset_manager(self):
        """Create the preset manager and populate the presets combobox."""
        self.config_preset_manager = ConfigPresetManager(
            self.main_window.config, self.main_window.config_manager.config_file
        )

        # Ensure app_directory is recorded in config.json.
        raw = self._read_config_json()
        if raw.get("app_directory") != self.config_preset_manager.app_directory:
            raw["app_directory"] = self.config_preset_manager.app_directory
            self._write_config_json(raw)

        self._populate_preset_combo()
        # Select the currently active settings path (or LOCAL if none).
        current = self.config_preset_manager.current_settings_path()
        idx = self.preset_combo.findData(current)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        else:
            idx = self.preset_combo.findText(os.path.normpath(current), Qt.MatchFlag.MatchExactly)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            else:
                # Fall back to the LOCAL preset (default element).
                local_idx = self.preset_combo.findData(LOCAL_PRESET_MARKER)
                if local_idx >= 0:
                    self.preset_combo.setCurrentIndex(local_idx)

    def _read_config_json(self) -> dict:
        import json as _json
        try:
            with open(self.main_window.config_manager.config_file, "r", encoding="utf-8") as f:
                return _json.load(f)
        except Exception:
            return {}

    def _write_config_json(self, data: dict):
        import json as _json
        try:
            with open(self.main_window.config_manager.config_file, "w", encoding="utf-8") as f:
                _json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to write config.json: {e}")

    def _populate_preset_combo(self):
        """Populate the preset combobox with LOCAL, history files and asset presets."""
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()

        # LOCAL preset (default element, edit field shows its windows path).
        python_root = os.path.join(self.config_preset_manager.app_directory, "Python")
        self.preset_combo.addItem("LOCAL", LOCAL_PRESET_MARKER)

        # Recorded history + asset presets (de-duplicated).
        recorded = list(self.config_preset_manager.get_history())
        asset_presets = self.config_preset_manager.list_asset_presets()
        all_paths = recorded + [p for p in asset_presets if os.path.normpath(p) not in
                                {os.path.normpath(r) for r in recorded}]
        for path in all_paths:
            self.preset_combo.addItem(os.path.normpath(path), path)

        self.preset_combo.blockSignals(False)

    def _current_preset_selection(self):
        """Return (display_text, data) for the current combobox selection."""
        idx = self.preset_combo.currentIndex()
        if idx < 0:
            return "", None
        return self.preset_combo.currentText(), self.preset_combo.itemData(idx)

    def _on_preset_combo_edited(self, text: str):
        """When the user types a path directly, record it as current_settings."""
        if not hasattr(self, 'config_preset_manager'):
            return
        idx = self.preset_combo.currentIndex()
        if idx >= 0 and self.preset_combo.itemData(idx) == LOCAL_PRESET_MARKER:
            return
        path = text.strip()
        if path and os.path.isfile(path):
            self.main_window.config.current_settings = path
            self.config_changed.emit()

    def _on_preset_load(self):
        """Load the selected json-config (or LOCAL preset) into the running config."""
        text, data = self._current_preset_selection()
        mode = "append" if self.preset_append_rb.isChecked() else "overwrite"

        if data == LOCAL_PRESET_MARKER:
            local = self.config_preset_manager.build_local_preset()
            if mode == "append":
                for k, v in local.items():
                    cur = getattr(self.main_window.config, k, None)
                    if cur in (None, "", [], {}):
                        setattr(self.main_window.config, k, v)
            else:
                for k, v in local.items():
                    setattr(self.main_window.config, k, v)
            self.main_window.config.current_settings = os.path.join(
                self.config_preset_manager.app_directory, "Python", DEFAULT_CONFIG_JSON
            )
            self.status_message("Loaded LOCAL default preset.")
        else:
            path = data or text
            if not path or not os.path.isfile(path):
                QMessageBox.warning(self, "Load Config", f"Config file not found:\n{path}")
                return
            try:
                self.config_preset_manager.load_json_config(path, mode=mode)
            except Exception as e:
                QMessageBox.critical(self, "Load Config", f"Failed to load {path}:\n{e}")
                return
            # Adopt the current ${approot} for any app-relative paths.
            self.config_preset_manager.set_current_settings(path)
            self.status_message(f"Loaded settings from {path}.")

        self.main_window.sync_ui_from_config()
        self.config_changed.emit()
        self._populate_preset_combo()

    def _on_preset_save(self):
        """Create a json-config file using the current settings."""
        text, data = self._current_preset_selection()
        # Determine the target path.
        if data == LOCAL_PRESET_MARKER:
            default_name = os.path.join(
                self.config_preset_manager.app_directory, "Python", DEFAULT_CONFIG_JSON
            )
        else:
            default_name = data or text or self.config_preset_manager.default_settings_path

        path, _ = QFileDialog.getSaveFileName(
            self, "Create Config Using Current Settings",
            default_name, "JSON Config Files (*.json)"
        )
        if not path:
            return
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self.config_preset_manager.create_config_from_current(path)
        except Exception as e:
            QMessageBox.critical(self, "Create Config", f"Failed to write {path}:\n{e}")
            return
        self.config_preset_manager.set_current_settings(path)
        self.status_message(f"Created config at {path}.")
        self._populate_preset_combo()
        # Select the newly created file.
        idx = self.preset_combo.findData(path)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)

    def _on_preset_remove(self):
        """Remove the visible path from the history (LOCAL is never removed)."""
        text, data = self._current_preset_selection()
        if data == LOCAL_PRESET_MARKER:
            self.status_message("The LOCAL preset cannot be removed from history.")
            return
        path = data or text
        if not path:
            return
        self.config_preset_manager.remove_from_history(path)
        self._populate_preset_combo()
        self.status_message(f"Removed {path} from history.")

    def _on_preset_reset_history(self):
        """Reset (clear) the recorded config-file history."""
        reply = QMessageBox.question(
            self, "Reset History",
            "Remove all recorded config files from the history? "
            "The LOCAL preset will remain available.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self.config_preset_manager.reset_history()
        self._populate_preset_combo()
        self.status_message("Config history reset.")

    def _on_preset_browse(self):
        """Choose the location/name of the current settings to load on startup."""
        current = self.config_preset_manager.current_settings_path()
        path, _ = QFileDialog.getOpenFileName(
            self, "Select Current Settings File",
            current, "JSON Config Files (*.json)"
        )
        if not path:
            return
        self.config_preset_manager.set_current_settings(path)
        self._populate_preset_combo()
        idx = self.preset_combo.findData(path)
        if idx >= 0:
            self.preset_combo.setCurrentIndex(idx)
        self.status_message(f"Startup settings set to {path}.")

    def _on_preset_index(self):
        """Index the specified directories (and ${approot}) for json-config files."""
        roots = self.config_preset_manager.resolve_search_roots(
            self.preset_search_roots_edit.text()
        )
        found = self.config_preset_manager.index_json_configs(roots)
        if not found:
            self.status_message("No json-config files found in the search paths.")
            return
        for p in found:
            self.config_preset_manager.add_to_history(p)
        self._populate_preset_combo()
        self.status_message(f"Indexed {len(found)} json-config file(s).")

    def status_message(self, msg: str):
        """Show a transient message in the main window status bar if available."""
        mw = self.main_window
        if hasattr(mw, "statusBar"):
            try:
                mw.statusBar().showMessage(msg, 4000)
            except Exception:
                pass

    def _show_options_args_dialog(self, pos, config_key, label_text):
        """Show a modal dialog to edit options and arguments for the selected app."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Options & Arguments - {label_text.strip(':')}")
        dialog.setMaximumSize(665, 460)
        layout = QFormLayout(dialog)
        
        # Determine defaults based on the current executable path or config key
        current_path = getattr(self.main_window.config, config_key, "")
        exe_name = os.path.basename(current_path).lower() if current_path else ""
        
        # Mutable container for defaults
        defaults_state = {
            'opts': "",
            'args': "",
            'has_defaults': False
        }
        
        # Lookup order: exe basename first, then config_key for profiles/configs
        if exe_name in self.options_args_map:
            defaults_state['opts'], defaults_state['args'] = self.options_args_map[exe_name]
            defaults_state['has_defaults'] = True
        elif config_key in self.options_args_map:
            defaults_state['opts'], defaults_state['args'] = self.options_args_map[config_key]
            defaults_state['has_defaults'] = True

        def _first_effective_token(pipe_delimited_str):
            """Return the first EFFECTIVE token of a pipe-delimited preset string.
            Empty-priority (leading '|' or empty) resolves to '' (parameter omitted).
            Non-pipe values pass through unchanged."""
            if not pipe_delimited_str:
                return ""
            s = pipe_delimited_str.strip()
            if s.startswith('|'):
                return ""
            if '|' not in s:
                return s
            return s.split('|', 1)[0].strip()

        def _populate_combo(combo, pipe_delimited_str, current_value):
            """Fill a QComboBox from a pipe-delimited string and select the
            current value (compared against the first-effective token)."""
            choices = list(dict.fromkeys(pipe_delimited_str.split('|'))) if pipe_delimited_str else ['']
            for choice in choices:
                combo.addItem(choice)
            # Compare the current value against the first effective token so that a
            # pipe-delimited preset (e.g. '|-vvv|--debug|') selects '-vvv' and an
            # empty-priority (leading '|') selects the empty entry.
            effective = _first_effective_token(current_value)
            idx = combo.findText(effective)
            if idx >= 0:
                combo.setCurrentIndex(idx)
            elif effective:
                combo.insertItem(0, effective)
                combo.setCurrentIndex(0)

        options_combo = QComboBox()
        options_combo.setEditable(True)
        _populate_combo(options_combo, defaults_state['opts'],
                        getattr(self.main_window.config, f"{config_key}_options", ""))
        layout.addRow("Options:", options_combo)
        
        args_combo = QComboBox()
        args_combo.setEditable(True)
        _populate_combo(args_combo, defaults_state['args'],
                        getattr(self.main_window.config, f"{config_key}_arguments", ""))
        layout.addRow("Arguments:", args_combo)
        
        # Visual indicator for defaults match
        status_label = QLabel()
        layout.addRow("", status_label)

        def check_defaults():
            if not defaults_state['has_defaults']:
                status_label.setText("")
                return
            
            # Compare against the first effect token (honoring empty-priority), not
            # the raw pipe-delimited default string.
            is_match = (_first_effective_token(options_combo.currentText()) ==
                        _first_effective_token(defaults_state['opts']) and
                        _first_effective_token(args_combo.currentText()) ==
                        _first_effective_token(defaults_state['args']))
            
            if is_match:
                status_label.setText("✓ Matches defaults")
            else:
                status_label.setText("⚠ Custom values")

        options_combo.currentTextChanged.connect(check_defaults)
        args_combo.currentTextChanged.connect(check_defaults)
        
        # Initial check
        check_defaults()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        
        # Add Reset button
        reset_btn = buttons.addButton("Reset to Defaults", QDialogButtonBox.ButtonRole.ResetRole)
        reset_btn.setVisible(defaults_state['has_defaults'])
        
        def reset_values():
            if defaults_state['has_defaults']:
                # Reset selects the first effective token of the default preset.
                eff_opts = _first_effective_token(defaults_state['opts'])
                idx = options_combo.findText(eff_opts)
                options_combo.setCurrentIndex(idx if idx >= 0 else 0)
                eff_args = _first_effective_token(defaults_state['args'])
                idx = args_combo.findText(eff_args)
                args_combo.setCurrentIndex(idx if idx >= 0 else 0)
        reset_btn.clicked.connect(reset_values)

        # Function to update defaults if path changes while dialog is open
        def update_defaults_from_path():
            if config_key in self.path_rows:
                curr_path = self.path_rows[config_key].path
            else:
                curr_path = ""
            
            curr_exe = os.path.basename(curr_path).lower() if curr_path else ""
            
            # Lookup order: exe basename first, then config_key
            if curr_exe in self.options_args_map:
                defaults_state['opts'], defaults_state['args'] = self.options_args_map[curr_exe]
                defaults_state['has_defaults'] = True
            elif config_key in self.options_args_map:
                defaults_state['opts'], defaults_state['args'] = self.options_args_map[config_key]
                defaults_state['has_defaults'] = True
            else:
                defaults_state['opts'], defaults_state['args'] = "", ""
                defaults_state['has_defaults'] = False
            
            check_defaults()
            reset_btn.setVisible(defaults_state['has_defaults'])

        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addRow(buttons)
        
        self._current_dialog_key = config_key
        self._current_dialog_updater = update_defaults_from_path
        
        try:
            if dialog.exec():
                opts = options_combo.currentText()
                args = args_combo.currentText()
                setattr(self.main_window.config, f"{config_key}_options", opts)
                setattr(self.main_window.config, f"{config_key}_arguments", args)
                self.config_changed.emit()
                if opts or args:
                    self.main_window.editor_tab.propagate_config_options(config_key, opts, args)
        finally:
            self._current_dialog_key = None
            self._current_dialog_updater = None

    def _connect_signals(self):
        self.add_source_dir_button.clicked.connect(self._add_source_dir)
        self.remove_source_dir_button.clicked.connect(self._remove_source_dir)
        self.add_excluded_dir_button.clicked.connect(self._add_excluded_dir)
        self.remove_excluded_dir_button.clicked.connect(self._remove_excluded_dir)
        self.reset_launch_btn.clicked.connect(self._reset_launch_sequence)
        self.reset_exit_btn.clicked.connect(self._reset_exit_sequence)

        self.run_as_admin_checkbox.stateChanged.connect(self.config_changed.emit)
        self.use_kill_list_checkbox.stateChanged.connect(self.config_changed.emit)
        self.hide_taskbar_checkbox.stateChanged.connect(self.config_changed.emit)
        self.terminate_bw_on_exit_checkbox.stateChanged.connect(self.config_changed.emit)

        # Update sequence item colours when relevant toggles change
        self.hide_taskbar_checkbox.stateChanged.connect(lambda _: self._update_sequence_item_colors())
        self.use_kill_list_checkbox.stateChanged.connect(lambda _: self._update_sequence_item_colors())

        self.source_dirs_list.model().rowsMoved.connect(self.config_changed.emit)
        self.source_dirs_list.model().rowsInserted.connect(self.config_changed.emit)
        self.source_dirs_list.model().rowsRemoved.connect(self.config_changed.emit)
        self.excluded_dirs_list.model().rowsMoved.connect(self.config_changed.emit)
        self.excluded_dirs_list.model().rowsInserted.connect(lambda: self.config_changed.emit())
        self.excluded_dirs_list.model().rowsRemoved.connect(self.config_changed.emit)

        # Path rows
        for key, row in self.path_rows.items():
            row.valueChanged.connect(self.config_changed.emit)
            row.valueChanged.connect(lambda k=key: self.setting_changed.emit(k))
            row.valueChanged.connect(self._update_sequence_item_colors)
            row.downloadRequested.connect(self._on_download_requested)

        for key, row in self.path_rows.items():
            if row.use_combobox:
                row.combo.lineEdit().textChanged.connect(lambda text, k=key: self._on_path_text_changed(k, text))
            else:
                row.line_edit.textChanged.connect(lambda text, k=key: self._on_path_text_changed(k, text))

        # Sequences
        self.launch_sequence_list.model().layoutChanged.connect(self.config_changed.emit)
        self.exit_sequence_list.model().layoutChanged.connect(self.config_changed.emit)

        # Logging
        self.logging_verbosity_combo.currentTextChanged.connect(self.main_window._on_logging_verbosity_changed)
        self.fuzzy_match_spin.valueChanged.connect(self.config_changed.emit)
        
        # Behavior
        self.restart_btn.clicked.connect(self._reset_to_defaults)

        # Appearance: theme selector
        self.theme_selector.currentIndexChanged.connect(self._on_theme_changed)
        self.preset_combo.currentTextChanged.connect(self._on_preset_combo_edited)
        self.font_selector.currentFontChanged.connect(self._on_font_changed)
        self.font_size_spin.valueChanged.connect(self._on_font_size_changed)
        self.editor_font_selector.currentFontChanged.connect(self._on_editor_font_changed)
        self.editor_font_size_spin.valueChanged.connect(self._on_editor_font_size_changed)

        # Connect Cloud/Backup enable signals to update sub-tab state
        if "cloud_sync_path" in self.path_rows:
            self.path_rows["cloud_sync_path"].enabled_cb.stateChanged.connect(self._update_cloud_backup_state)
        if "local_backup_path" in self.path_rows:
            self.path_rows["local_backup_path"].enabled_cb.stateChanged.connect(self._update_local_backup_state)

    def _on_monitorapp_enabled_changed(self, state):
        """When the monitor config app is enabled, auto-select multimonitortool.exe
        from the combobox if it is present."""
        if not self.path_rows["monitorapp_path"].enabled_cb.isChecked():
            return
        combo = self.path_rows["monitorapp_path"].combo
        for i in range(combo.count()):
            text = combo.itemText(i).lower()
            if "multimonitortool" in text:
                combo.setCurrentIndex(i)
                return

    def _update_cloud_backup_state(self):
        """Enable/Disable Cloud-Sync tab widgets based on the cloud sync enable checkbox."""
        enabled = self.path_rows["cloud_sync_path"].enabled
        
        for widget in [
            self.rclone_remote_name_edit, self.rclone_local_path_row,
            self.rclone_remote_path_edit, self.rclone_sync_mode_combo,
            self.rclone_backup_on_launch_cb, self.rclone_backup_on_exit_cb,
            self.ludusavi_backup_path_row, self.ludusavi_game_name_edit,
            self.ludusavi_backup_on_launch_cb, self.ludusavi_backup_on_exit_cb,
            self.syncthing_sync_folder_row, self.syncthing_auto_start_cb,
            self.emusync_emulator_path_row, self.emusync_sync_on_launch_cb,
            self.emusync_sync_on_exit_cb,
        ]:
            widget.setEnabled(enabled)

    def _update_local_backup_state(self):
        """Enable/Disable Local Backup tab widgets based on main local backup enable state."""
        # Currently Local Backup tab doesn't exist separately or share widgets in a way that needs distinct handling
        # from Cloud Backup tab in the current UI layout (all in CLOUD BACKUP tab).
        # If there were specific local backup widgets mixed in, we would handle them here.
        # For now, assuming Cloud Backup tab handles all these tools.
        pass

    def _parse_repos_set(self):
        """Parses the repos.set file and returns a dictionary of tools."""
        repos = {}
        if not os.path.exists(constants.REPOS_SET):
            return repos

        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        config.read(constants.REPOS_SET)

        global_vars = {}
        if "GLOBAL" in config:
            global_vars = dict(config["GLOBAL"])
            # Pre-resolve common variables
            global_vars["app_directory"] = constants.APP_ROOT_DIR

        for section in config.sections():
            repos[section.upper()] = {}
            for key, value in config[section].items():
                if section == "GLOBAL": continue
                
                # Skip comment lines
                if key.startswith('#'):
                    continue
                
                # Basic variable substitution
                val = value
                for var_name, var_val in global_vars.items():
                    val = val.replace(f"${var_name.upper()}", var_val)
                    val = val.replace(f"${var_name}", var_val)
                
                # Item specific substitution
                val = val.replace("$ITEMNAME", key)
                
                parts = val.split('|')
                if len(parts) >= 3:
                    url = parts[0]
                    # Fix common GitHub URL malformation where refs/heads/ is included in raw link
                    if "github.com" in url and "/raw/refs/heads/" in url:
                        url = url.replace("/raw/refs/heads/", "/raw/")

                    tool_data = {
                        'url': url,
                        'extract_dir': parts[1],
                        'exe_name': parts[2]
                    }
                    
                    # Parse flags (4th field)
                    if len(parts) >= 4:
                        flags = parts[3].strip()
                        
                        # Check for INSTALLER flag
                        if flags.startswith('INSTALLER'):
                            tool_data['is_installer'] = True
                            
                            # Check for specific installed path
                            if ':' in flags:
                                installed_path = flags.split(':', 1)[1].strip()
                                tool_data['installed_path'] = installed_path
                            else:
                                tool_data['installed_path'] = None
                        
                        # Check for SILENT flag
                        if 'SILENT' in flags:
                            tool_data['silent_install'] = True
                        else:
                            tool_data['silent_install'] = False
                    else:
                        tool_data['is_installer'] = False
                        tool_data['silent_install'] = False
                    
                    repos[section.upper()][key] = tool_data
        return repos

    def _parse_options_arguments_set(self):
        """Parses the options_arguments.set file and returns a dictionary."""
        mapping = {}
        if not os.path.exists(constants.OPTIONS_ARGUMENTS_SET):
            return mapping
        
        config = configparser.ConfigParser()
        try:
            with open(constants.OPTIONS_ARGUMENTS_SET, 'r', encoding='utf-8-sig') as f:
                config.read_file(f)
            for section in config.sections():
                options = config.get(section, 'options', fallback="").strip()
                arguments = config.get(section, 'arguments', fallback="").strip()
                key = section.lower()
                mapping[key] = (options, arguments)
                config_key = constants.SECTION_TO_CONFIG_KEY.get(key)
                if config_key:
                    mapping[config_key] = (options, arguments)
        except Exception as e:
            logging.error(f"Error parsing options_arguments.set: {e}")
        return mapping

    def _on_wizard_button_clicked(self):
        """Open the monitor configuration wizard from the wizard button."""
        row = self.path_rows.get("monitorapp_path")
        if not row or not row.path:
            QMessageBox.information(self, "Display Wizard", "Please select a display tool first.")
            return

        selected_path = (row.path or "").strip()
        tool_name = os.path.basename(selected_path)
        if tool_name and "." in tool_name:
            tool_name = tool_name.rsplit(".", 1)[0]
        if not tool_name:
            tool_name = "MultiMonitorTool"

        wizard = DisplayWizard(self, windowing_app_name=tool_name, tool_path=selected_path)
        wizard.exec()
        # Refresh UI after wizard may have saved new config paths
        if hasattr(self.main_window, 'config'):
            self.sync_ui_from_config(self.main_window.config)

    def _on_download_requested(self, tool_name, tool_data):
        if tool_data.get("special") == "mount_disc":
            self._generate_mount_scripts()
            # Script generation complete - no auto-assignment
            return
        
        if tool_data.get("special") in ["mount_native", "mount_wincdemu", "mount_imgdrive", "mount_cdmage", "mount_osf"]:
            self._handle_mount_tool_setup(tool_name, tool_data)
            return

        if self.download_thread and self.download_thread.isRunning():
            QMessageBox.warning(self, "Download in Progress", "Please wait for the current download to finish.")
            return

        # Check if files exist - use case-insensitive directory resolution
        extract_dir_raw = tool_data['extract_dir']
        
        # Resolve extract_dir case-insensitively by checking each path component
        # Handle both absolute and relative paths
        path_parts = extract_dir_raw.replace('\\', '/').split('/')
        resolved_path = ""
        
        for i, part in enumerate(path_parts):
            if not part:  # Skip empty parts (from leading slash or double slashes)
                continue
            
            if i == 0:
                # First part - could be drive letter (C:) or relative path start
                resolved_path = part
                # For Windows drive letters, ensure we have the backslash
                if len(part) == 2 and part[1] == ':':
                    resolved_path = part + '\\'
            else:
                parent = resolved_path
                resolved_path = self._find_dir_case_insensitive(parent, part)
        
        extract_dir = resolved_path
        exe_name = tool_data['exe_name']
        url = tool_data['url'].split('<')[0] # Use first URL for filename determination
        
        exe_path = os.path.join(extract_dir, exe_name)
        zip_name = url.split('/')[-1]
        zip_path = os.path.join(extract_dir, zip_name)
        
        if os.path.exists(exe_path) or os.path.exists(zip_path):
            reply = QMessageBox.question(
                self, "File Exists",
                f"The tool '{tool_name}' appears to be already downloaded.\n"
                "Do you want to download and overwrite it?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        self.active_download_row = self.sender() # Store the row that requested the download
        self._current_download_tool_name = tool_name  # Store the tool name for config writing
        self._current_download_tool_data = tool_data  # Store tool data for installer detection
        
        # Use QProgressDialog instead of embedded bar
        self.progress_dialog = QProgressDialog(f"Downloading {tool_name}...", "Cancel", 0, 100, self)
        self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        self.progress_dialog.setMinimumDuration(0)
        self.progress_dialog.setAutoClose(False)
        self.progress_dialog.show()

        self.download_thread = DownloadThread(tool_data['url'], extract_dir, tool_data['exe_name'])
        self.download_thread.progress.connect(self.progress_dialog.setValue)
        self.download_thread.finished.connect(self._on_download_finished_slot)
        self.download_thread.start()
    
    def _handle_mount_tool_setup(self, tool_name, tool_data):
        special_type = tool_data.get("special")
        bin_dir = os.path.join(constants.APP_ROOT_DIR, "bin")
        os.makedirs(bin_dir, exist_ok=True)
        
        sender_row = self.sender()
        
        if special_type == "mount_native":
            # Generate native scripts
            self._generate_mount_scripts_files(bin_dir, "native")
            # Script generation complete - no auto-assignment
                
        elif special_type == "mount_wincdemu":
            # Check if already downloaded (case-insensitive)
            exe_name = tool_data['exe_name']
            exe_path = self._find_exe_case_insensitive(bin_dir, exe_name)
            
            if not exe_path:
                # Trigger download
                self.active_download_row = sender_row
                self.progress_dialog = QProgressDialog(f"Downloading {tool_name}...", "Cancel", 0, 100, self)
                self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                self.progress_dialog.setMinimumDuration(0)
                self.progress_dialog.setAutoClose(False)
                self.progress_dialog.show()

                self.download_thread = DownloadThread(tool_data['url'], bin_dir, exe_name)
                self.download_thread.progress.connect(self.progress_dialog.setValue)
                
                # Connect finished signal to a lambda that also generates scripts
                self.download_thread.finished.connect(lambda s, m, p: self._on_wincdemu_download_finished(s, m, p, bin_dir))
                self.download_thread.start()
            else:
                # Just generate scripts - no auto-assignment
                self._write_exe_path_to_config("wincdemu", exe_path)
                self._generate_mount_scripts_files(bin_dir, "wincdemu")
        
        elif special_type == "mount_cdmage":
            # Check if already downloaded (case-insensitive)
            exe_name = tool_data['exe_name']
            exe_path = self._find_exe_case_insensitive(bin_dir, exe_name)
            
            if not exe_path:
                # Trigger download
                self.active_download_row = sender_row
                self.progress_dialog = QProgressDialog(f"Downloading {tool_name}...", "Cancel", 0, 100, self)
                self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                self.progress_dialog.setMinimumDuration(0)
                self.progress_dialog.setAutoClose(False)
                self.progress_dialog.show()

                self.download_thread = DownloadThread(tool_data['url'], bin_dir, exe_name)
                self.download_thread.progress.connect(self.progress_dialog.setValue)
                self.download_thread.finished.connect(lambda s, m, p: self._on_cdmage_download_finished(s, m, p, bin_dir))
                self.download_thread.start()
            else:
                # Just generate scripts - no auto-assignment
                self._write_exe_path_to_config("cdmage", exe_path)
                self._generate_mount_scripts_files(bin_dir, "cdmage")
        
        elif special_type == "mount_osf":
            # Check if already downloaded (case-insensitive)
            exe_name = tool_data['exe_name']
            exe_path = self._find_exe_case_insensitive(bin_dir, exe_name)
            
            if not exe_path:
                # Trigger download
                self.active_download_row = sender_row
                self.progress_dialog = QProgressDialog(f"Downloading {tool_name}...", "Cancel", 0, 100, self)
                self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                self.progress_dialog.setMinimumDuration(0)
                self.progress_dialog.setAutoClose(False)
                self.progress_dialog.show()

                self.download_thread = DownloadThread(tool_data['url'], bin_dir, exe_name)
                self.download_thread.progress.connect(self.progress_dialog.setValue)
                self.download_thread.finished.connect(lambda s, m, p: self._on_osf_download_finished(s, m, p, bin_dir))
                self.download_thread.start()
            else:
                # Just generate scripts - no auto-assignment
                self._write_exe_path_to_config("osf", exe_path)
                self._generate_mount_scripts_files(bin_dir, "osf")
        
        elif special_type == "mount_imgdrive":
            # Check if already downloaded (case-insensitive)
            exe_name = tool_data['exe_name']
            exe_path = self._find_exe_case_insensitive(bin_dir, exe_name)
            
            if not exe_path:
                # Trigger download
                self.active_download_row = sender_row
                self.progress_dialog = QProgressDialog(f"Downloading {tool_name}...", "Cancel", 0, 100, self)
                self.progress_dialog.setWindowModality(Qt.WindowModality.WindowModal)
                self.progress_dialog.setMinimumDuration(0)
                self.progress_dialog.setAutoClose(False)
                self.progress_dialog.show()

                self.download_thread = DownloadThread(tool_data['url'], bin_dir, exe_name)
                self.download_thread.progress.connect(self.progress_dialog.setValue)
                self.download_thread.finished.connect(lambda s, m, p: self._on_imgdrive_download_finished(s, m, p, bin_dir))
                self.download_thread.start()
            else:
                # Just generate scripts - no auto-assignment
                self._write_exe_path_to_config("imgdrive", exe_path)
                self._generate_mount_scripts_files(bin_dir, "imgdrive")
    
    def _find_exe_case_insensitive(self, directory, exe_name):
        """Find an executable in a directory with case-insensitive matching."""
        if not os.path.exists(directory):
            return None
        
        exe_name_lower = exe_name.lower()
        for file in os.listdir(directory):
            if file.lower() == exe_name_lower:
                full_path = os.path.join(directory, file)
                if os.path.isfile(full_path):
                    return full_path
        return None
    
    def _find_dir_case_insensitive(self, parent_dir, dir_name):
        """Find a directory with case-insensitive matching.
        
        Args:
            parent_dir: Parent directory to search in
            dir_name: Directory name to find (case-insensitive)
            
        Returns:
            Full path to the directory if found, otherwise the original path
        """
        if not os.path.exists(parent_dir):
            return os.path.join(parent_dir, dir_name)
        
        dir_name_lower = dir_name.lower()
        for item in os.listdir(parent_dir):
            if item.lower() == dir_name_lower:
                full_path = os.path.join(parent_dir, item)
                if os.path.isdir(full_path):
                    return full_path
        
        # If not found, return the original path
        return os.path.join(parent_dir, dir_name)

    def _write_exe_path_to_config(self, exe_name, exe_path):
        """Write the executable path to config.json with the format {exe_name}_exe_path."""
        # Remove .exe extension if present for the config key
        tool_name_no_ext = exe_name.replace('.exe', '').lower()
        config_key = f"{tool_name_no_ext}_exe_path"
        
        if self.main_window and hasattr(self.main_window, 'config') and self.main_window.config:
            setattr(self.main_window.config, config_key, exe_path)
            self.config_changed.emit()
            logging.info(f"Wrote executable path to config: {config_key} = {exe_path}")

            # Trigger mount script generation for disc tools
            mount_tools = ["wincdemu", "osf", "imgdrive", "cdmage", "native"]
            if tool_name_no_ext in mount_tools:
                 self._generate_mount_scripts_files(os.path.join(constants.APP_ROOT_DIR, "bin"), tool_name_no_ext)
        else:
            logging.warning(f"Failed to write {config_key} to config: Configuration object is not initialized.")

    def _generate_mount_scripts_files(self, bin_dir, tool_type):
        """Generate the appropriate mount/unmount scripts based on tool type."""
        assets_dir = constants.ASSETS_DIR
        
        # Determine script names based on tool type
        mount_script_name = ""
        if tool_type == "native":
            mount_script_name = "nativemount"
        elif tool_type == "wincdemu":
            mount_script_name = "cdemu"
        elif tool_type == "imgdrive":
            mount_script_name = "imgdrive"
        elif tool_type == "cdmage":
            mount_script_name = "cdmage"
        elif tool_type == "osf":
            mount_script_name = "osf"
        
        if not mount_script_name:
            logging.warning(f"Unknown mount tool type: {tool_type}")
            return
        
        # Generate mount script (handles both mount and unmount via flag)
        if os.name == 'nt':
            # Windows: use combined.cmd.set template
            template_path = os.path.join(assets_dir, "combined.cmd.set")
            if os.path.exists(template_path):
                dest_path = os.path.join(bin_dir, f"{mount_script_name}.cmd")
                self._copy_template_file(template_path, dest_path)
                
                # Create _unmount.cmd that calls the mount script with unmount flag
                unmount_dest = os.path.join(bin_dir, "_unmount.cmd")
                unmount_content = f"""@echo off
REM Universal unmount script - calls mount scripts with unmount flag
set "ISO=%~1"
set "BIN_DIR=%~dp0"

REM Try all available mount tools with unmount flag
if exist "%BIN_DIR%{mount_script_name}.cmd" (
    call "%BIN_DIR%{mount_script_name}.cmd" "%ISO%" --unmount
    exit /b %ERRORLEVEL%
)

REM Fallback to native PowerShell unmount
powershell -command "Dismount-DiskImage -ImagePath '%ISO%'" >nul 2>&1
exit /b %ERRORLEVEL%
"""
                try:
                    with open(unmount_dest, 'w', encoding='utf-8') as f:
                        f.write(unmount_content)
                except Exception as e:
                    logging.error(f"Failed to create unmount script: {e}")
            else:
                logging.warning(f"Mount script template not found: {template_path}")
        else:
            # Linux/macOS: use combined.sh.set template
            template_path = os.path.join(assets_dir, "combined.sh.set")
            if os.path.exists(template_path):
                dest_path = os.path.join(bin_dir, f"{mount_script_name}.sh")
                self._copy_template_file(template_path, dest_path)
                # Make script executable
                try:
                    os.chmod(dest_path, 0o755)
                except Exception as e:
                    logging.error(f"Failed to make script executable: {e}")
                
                # Create _unmount.sh that calls the mount script with unmount flag
                unmount_dest = os.path.join(bin_dir, "_unmount.sh")
                unmount_content = f"""#!/bin/bash
# Universal unmount script - calls mount scripts with unmount flag
DISCIMAGE="$1"
BIN_DIR="$(dirname "$0")"

# Try the selected mount tool with unmount flag
if [ -f "$BIN_DIR/{mount_script_name}.sh" ]; then
    "$BIN_DIR/{mount_script_name}.sh" "$DISCIMAGE" --unmount
    exit $?
fi

# Fallback unmount logic
if [ -f "drvltr" ]; then
    MOUNTPOINT=$(cat "drvltr")
    
    # Try cdemu
    if command -v cdemu &> /dev/null; then
        cdemu unload 0 &> /dev/null
        rm -f "drvltr"
        exit 0
    fi
    
    # Try udisksctl
    if command -v udisksctl &> /dev/null && [ ! -z "$MOUNTPOINT" ]; then
        udisksctl unmount -b "$MOUNTPOINT" 2>/dev/null
        udisksctl loop-delete -b "$MOUNTPOINT" 2>/dev/null
        rm -f "drvltr"
        exit 0
    fi
fi

echo "Could not unmount disc image."
exit 1
"""
                try:
                    with open(unmount_dest, 'w', encoding='utf-8') as f:
                        f.write(unmount_content)
                    os.chmod(unmount_dest, 0o755)
                except Exception as e:
                    logging.error(f"Failed to create unmount script: {e}")
            else:
                logging.warning(f"Mount script template not found: {template_path}")

    def _copy_template_file(self, template_path, dest_path):
        """Copy a template file to destination with variable replacement."""
        try:
            if os.path.exists(template_path):
                with open(template_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Replace variables in brackets with config values
                # Pattern matches [$VARIABLE_NAME] tags
                def replace_var(match):
                    var_name = match.group(1)
                    # Convert to a config key, e.g., 'WINCDEMU_EXE_PATH' -> 'wincdemu_exe_path'
                    config_key = var_name.lower()
                    if self.main_window and hasattr(self.main_window, 'config'):
                        # Return the value if found, otherwise return an empty string to remove the tag
                        value = getattr(self.main_window.config, config_key, "")
                        if value:
                            logging.info(f"Replaced [{var_name}] with: {value}")
                        else:
                            logging.warning(f"No value found for [{var_name}] (config key: {config_key})")
                        return value
                    return ""

                # Match [$VARIABLE_NAME] pattern
                content = re.sub(r'\[\$([A-Z_]+)\]', replace_var, content)

                with open(dest_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                # Remove .set extension from destination
                if dest_path.endswith('.set'):
                    final_path = dest_path[:-4]
                    os.rename(dest_path, final_path)
                    logging.info(f"Generated mount script: {final_path}")
            else:
                logging.warning(f"Template not found: {template_path}")
        except Exception as e:
            logging.error(f"Error copying template {template_path} to {dest_path}: {e}")

    def _find_exe_recursive(self, root_dir, exe_name):
        """Recursively search a directory for a specific executable (case-insensitive)."""
        exe_lower = exe_name.lower()
        for dirpath, dirnames, filenames in os.walk(root_dir):
            for fname in filenames:
                if fname.lower() == exe_lower:
                    return os.path.join(dirpath, fname)
        return None

    def _auto_populate_mapper_templates(self, tool_name, mapper_exe_path):
        """After downloading a mapper tool, populate missing profile templates via config_manager."""
        tool_lower = tool_name.lower().replace('.exe', '')
        mapper_tools = {'antimicrox': '.amgp', 'keysticks': '.keysticks'}
        ext = mapper_tools.get(tool_lower)
        if not ext:
            return

        config = self.main_window.config if self.main_window and hasattr(self.main_window, 'config') else None
        if not config:
            return

        # Check whether any profile paths are already configured — if all set, skip
        needs_population = (
            not config.p1_profile_path or
            not config.p2_profile_path or
            not config.desk_profile_path
        )
        if not needs_population:
            return

        try:
            if hasattr(self.main_window, 'config_manager'):
                # Set the controller_mapper_path if not already set
                if not config.controller_mapper_path:
                    config.controller_mapper_path = mapper_exe_path
                    config.defaults['controller_mapper_path_enabled'] = True
                
                self.main_window.config_manager._populate_controller_profiles(
                    config, mapper_exe_path, tool_lower, ext
                )
                logging.info(f"Auto-populated controller profiles for {tool_lower}")
                self.main_window.config_manager.save_config(config)
                self.config_changed.emit()
                self.main_window.sync_ui_from_config()
        except Exception as e:
            logging.error(f"Failed to auto-populate mapper profiles for {tool_lower}: {e}")

    def _on_download_finished_slot(self, success, message, result_path):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()
            
        if success:
            # Check if this is an installer
            is_installer = False
            installed_path = None
            silent_install = False
            
            if hasattr(self, '_current_download_tool_data'):
                tool_data = self._current_download_tool_data
                is_installer = tool_data.get('is_installer', False)
                installed_path = tool_data.get('installed_path')
                silent_install = tool_data.get('silent_install', False)
            
            if is_installer:
                # Handle installer
                self._handle_installer(result_path, installed_path, silent_install)
            else:
                # If result_path is a directory (exe not found at top level), search recursively
                resolved_path = result_path
                if os.path.isdir(result_path) and hasattr(self, '_current_download_tool_data') and self._current_download_tool_data:
                    exe_name = self._current_download_tool_data.get('exe_name', '')
                    if exe_name:
                        found = self._find_exe_recursive(result_path, exe_name)
                        if found:
                            resolved_path = found
                            logging.info(f"Located executable via recursive search: {resolved_path}")
                        else:
                            logging.warning(f"Executable '{exe_name}' not found in extracted directory '{result_path}'")

                # Handle portable executable
                if hasattr(self, 'active_download_row') and self.active_download_row:
                    self.active_download_row.path = resolved_path
                    
                    # Write the executable path to config.json
                    if hasattr(self, '_current_download_tool_name') and self._current_download_tool_name:
                        tool_name = self._current_download_tool_name
                        self._write_exe_path_to_config(tool_name, resolved_path)

                        # Auto-populate mapper profile templates if applicable
                        self._auto_populate_mapper_templates(tool_name, resolved_path)
                
                # Refresh all tool paths from bin directory after successful download
                self._refresh_tool_paths()
                    
                QMessageBox.information(self, "Download Complete", f"Successfully downloaded to:\n{resolved_path}")
        else:
            QMessageBox.critical(self, "Download Failed", f"Error: {message}")
            
        self.active_download_row = None
        if hasattr(self, '_current_download_tool_name'):
            self._current_download_tool_name = None
        if hasattr(self, '_current_download_tool_data'):
            self._current_download_tool_data = None
    
    def _handle_installer(self, installer_path, installed_path, silent_install):
        """Handle running an installer and tracking the installed executable."""
        logging.info(f"Handling installation for: {installer_path}")
        try:
            if not os.path.exists(installer_path):
                error_msg = f"Installer executable not found on disk: {installer_path}"
                logging.error(error_msg)
                QMessageBox.critical(self, "Installation Error", error_msg)
                return

            # Ask user if they want to run the installer
            reply = QMessageBox.question(
                self, 
                "Installer Detected",
                f"This tool requires installation.\n\n"
                f"Installer: {os.path.basename(installer_path)}\n\n"
                f"Would you like to run the installer now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes
            )
            
            if reply != QMessageBox.StandardButton.Yes:
                logging.info("User declined to run the installer.")
                QMessageBox.information(
                    self, 
                    "Installation Skipped",
                    f"You can manually run the installer later:\n{installer_path}\n\n"
                    f"After installation, manually set the path in the configuration."
                )
                return
            
            # Build installer command
            cmd = [installer_path]
            if silent_install:
                # Common silent install flags
                cmd.extend(['/S', '/SILENT', '/VERYSILENT'])
            
            # Run installer
            logging.info(f"Executing installer: {' '.join(cmd)}")
            
            if silent_install:
                # Run silently and wait
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=0x08000000  # CREATE_NO_WINDOW
                )
                
                # Show progress dialog
                progress = QProgressDialog("Installing...", "Cancel", 0, 0, self)
                progress.setWindowModality(Qt.WindowModality.WindowModal)
                progress.setMinimumDuration(0)
                progress.show()
                
                # Wait for installation to complete
                while process.poll() is None:
                    QApplication.processEvents()
                    if progress.wasCanceled():
                        logging.warning("User cancelled the silent installation process.")
                        process.terminate()
                        QMessageBox.warning(self, "Installation Cancelled", "Installation was cancelled by user.")
                        return
                
                progress.close()
                
                if process.returncode != 0:
                    stderr = process.stderr.read().decode('utf-8', errors='ignore')
                    logging.error(f"Silent installer failed with code {process.returncode}. Stderr: {stderr}")
                    QMessageBox.critical(
                        self, 
                        "Installation Failed",
                        f"Installer returned error code {process.returncode}.\n\n"
                        f"Details: {stderr[:200]}...\n\n"
                        f"You may need to run the installer manually:\n{installer_path}"
                    )
                    return
                logging.info("Silent installation process finished successfully.")
            else:
                # Run installer with UI (non-blocking)
                subprocess.Popen(cmd)
                logging.info("Installer launched with UI (non-blocking).")
                
                QMessageBox.information(
                    self,
                    "Installer Launched",
                    f"The installer has been launched.\n\n"
                    f"Please complete the installation, then click OK.\n\n"
                    f"After installation, the tool path will be detected automatically."
                )
            
            # Try to find the installed executable
            if installed_path:
                # Expand environment variables in installed path
                expanded_path = os.path.expandvars(installed_path)
                logging.info(f"Verifying installation at target path: {expanded_path}")
                
                # Check if installed executable exists
                if os.path.exists(expanded_path):
                    logging.info(f"Verified installation. Updating config with path: {expanded_path}")
                    # Update the path row
                    if hasattr(self, 'active_download_row') and self.active_download_row:
                        self.active_download_row.path = expanded_path
                    
                    # Write to config
                    if hasattr(self, '_current_download_tool_name') and self._current_download_tool_name:
                        tool_name = self._current_download_tool_name
                        self._write_exe_path_to_config(tool_name, expanded_path)
                        
                        # Auto-populate mapper profile templates if applicable
                        self._auto_populate_mapper_templates(tool_name, expanded_path)
                    
                    # Refresh tool paths
                    self._refresh_tool_paths()
                    
                    QMessageBox.information(
                        self,
                        "Installation Complete",
                        f"Tool installed successfully!\n\nInstalled to: {expanded_path}"
                    )
                else:
                    # Installed path not found - ask user to locate it
                    logging.warning(f"Installation verified as finished but executable not found at: {expanded_path}")
                    QMessageBox.warning(
                        self,
                        "Installed Path Not Found",
                        f"Expected installation path not found:\n{expanded_path}\n\n"
                        f"Please manually locate the installed executable."
                    )
                    
                    # Open file dialog to locate installed exe
                    initial_dir = os.path.dirname(expanded_path) if os.path.dirname(expanded_path) else ""
                    file_path, _ = QFileDialog.getOpenFileName(
                        self,
                        "Locate Installed Executable",
                        initial_dir,
                        "Executables (*.exe);;All Files (*.*)"
                    )
                    
                    if file_path:
                        logging.info(f"User manually mapped installed path: {file_path}")
                        if hasattr(self, 'active_download_row') and self.active_download_row:
                            self.active_download_row.path = file_path
                        
                        if hasattr(self, '_current_download_tool_name') and self._current_download_tool_name:
                            tool_name = self._current_download_tool_name
                            self._write_exe_path_to_config(tool_name, file_path)
                            
                            # Auto-populate mapper profile templates if applicable
                            self._auto_populate_mapper_templates(tool_name, file_path)
                        
                        self._refresh_tool_paths()
                        
                        QMessageBox.information(
                            self,
                            "Path Set",
                            f"Tool path set to:\n{file_path}"
                        )
                    else:
                        logging.warning("User cancelled manual file location selection.")
            else:
                # No installed path specified - try to auto-detect
                logging.info("No explicit installed path defined in repos.set. Attempting auto-detection.")
                QMessageBox.information(
                    self,
                    "Installation Complete",
                    f"Installation complete!\n\n"
                    f"The tool path will be auto-detected if it's in a standard location.\n"
                    f"Otherwise, please manually set the path in the configuration."
                )
                
                # Refresh to try auto-detection
                self._refresh_tool_paths()
                
        except Exception as e:
            logging.error(f"Critical error during installer handling: {e}", exc_info=True)
            QMessageBox.critical(
                self,
                "Installer Error",
                f"An error occurred while handling the installer:\n{str(e)}\n\n"
                f"You may need to run the installer manually:\n{installer_path}"
            )
    
    def _refresh_tool_paths(self):
        """Refresh tool paths by re-scanning the bin directory and updating config."""
        if hasattr(self.main_window, 'config_manager') and hasattr(self.main_window, 'config'):
            logging.info("Refreshing tool paths after download...")
            self.main_window.config_manager.refresh_tool_paths(self.main_window.config)
            self.main_window.sync_ui_from_config()
            logging.info("Tool paths refreshed and UI updated.")

    def _reset_to_defaults(self):
        """Reset the application's configuration to the shipped defaults."""
        reply = QMessageBox.question(self, "Reset to Defaults",
                                     "This will reset all configuration to the application's default values. Continue?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                     QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return
        
        # Call the main window's method to handle the reset logic
        if hasattr(self.main_window, 'reset_configuration_to_defaults'):
            self.main_window.reset_configuration_to_defaults()

    def _add_source_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Source Directory")
        if directory:
            # Normalize path to use forward slashes
            directory = directory.replace('\\', '/')
            self.source_dirs_list.addItem(directory)

    def _remove_source_dir(self):
        selected_items = self.source_dirs_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.source_dirs_list.takeItem(self.source_dirs_list.row(item))

    def _add_excluded_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "Select Directory to Exclude")
        if directory:
            # Normalize path to use forward slashes
            directory = directory.replace('\\', '/')
            self.excluded_dirs_list.addItem(directory)

    def _remove_excluded_dir(self):
        selected_items = self.excluded_dirs_list.selectedItems()
        if not selected_items:
            return
        for item in selected_items:
            self.excluded_dirs_list.takeItem(self.excluded_dirs_list.row(item))

    def _reset_launch_sequence(self):
        self.launch_sequence_list.clear()
        self.launch_sequence_list.addItems(["Cloud-Sync", "mount-disc", "Controller-Mapper", "Monitor-Config", "No-TB", "Pre1", "Pre2", "Pre3", "Borderless", "RunAudio", "Backup"])
        self.config_changed.emit()
        self._update_list_tooltips(self.launch_sequence_list)
        self._update_sequence_item_colors()

    def _reset_exit_sequence(self):
        self.exit_sequence_list.clear()
        self.exit_sequence_list.addItems(["Post1", "Post2", "Post3", "Monitor-Config", "Taskbar", "Controller-Mapper", "Borderless", "ReturnAudio", "Unmount-disc", "Cloud-Sync", "Backup"])
        self.config_changed.emit()
        self._update_list_tooltips(self.exit_sequence_list)
        self._update_sequence_item_colors()

    def _on_sequence_context_menu(self, pos, list_widget, sequence_type):
        item = list_widget.itemAt(pos)

        menu = QMenu(self)
        
        # Define full sets
        if sequence_type == "launch":
            full_set = ["Cloud-Sync", "mount-disc", "Kill-Game", "Kill-List", "Controller-Mapper", "Monitor-Config", "No-TB", "Pre1", "Pre2", "Pre3", "Borderless", "RunAudio", "Backup"]
        else:
            full_set = ["Post1", "Post2", "Post3", "Kill-Game", "Kill-List", "Monitor-Config", "Taskbar", "Controller-Mapper", "Borderless", "Unmount-disc", "Cloud-Sync", "ReturnAudio", "Backup"]
            
        current_items = [list_widget.item(i).text() for i in range(list_widget.count())]
        removed_items = [x for x in full_set if x not in current_items]
        
        if item:
            # Remove
            remove_action = menu.addAction("Remove")
            remove_action.triggered.connect(lambda: self._remove_sequence_item(list_widget, item))
            
            # Swap
            swap_menu = menu.addMenu("Swap with")
            current_row = list_widget.row(item)
            for i in range(list_widget.count()):
                if i == current_row:
                    continue
                other_item = list_widget.item(i)
                action = swap_menu.addAction(other_item.text())
                action.triggered.connect(lambda checked, r1=current_row, r2=i: self._swap_sequence_items(list_widget, r1, r2))
            
            menu.addSeparator()
            
            move_up = menu.addAction("Move Up")
            move_up.triggered.connect(lambda: self._move_sequence_item(list_widget, item, -1))
            
            move_down = menu.addAction("Move Down")
            move_down.triggered.connect(lambda: self._move_sequence_item(list_widget, item, 1))
            
            if current_row == 0:
                move_up.setEnabled(False)
            if current_row == list_widget.count() - 1:
                move_down.setEnabled(False)

            # Replace (with removed items)
            replace_menu = menu.addMenu("Replace with")
            
            if not removed_items:
                replace_menu.setDisabled(True)
            else:
                for removed in removed_items:
                    action = replace_menu.addAction(removed)
                    action.triggered.connect(lambda checked, it=item, txt=removed: self._replace_sequence_item(list_widget, it, txt))
            
            menu.addSeparator()

        # Add (append from removed items)
        add_menu = menu.addMenu("Add")
        if not removed_items:
            add_menu.setDisabled(True)
        else:
            for removed in removed_items:
                action = add_menu.addAction(removed)
                action.triggered.connect(lambda checked, txt=removed: self._add_sequence_item(list_widget, txt))

        if not menu.isEmpty():
            menu.exec(list_widget.mapToGlobal(pos))

    def _remove_sequence_item(self, list_widget, item):
        list_widget.takeItem(list_widget.row(item))
        self.config_changed.emit()

    def _add_sequence_item(self, list_widget, text):
        list_widget.addItem(text)
        # Set tooltip for the new item
        item = list_widget.item(list_widget.count() - 1)
        self._update_item_tooltip(item)
        self.config_changed.emit()

    def _swap_sequence_items(self, list_widget, row1, row2):
        item1 = list_widget.item(row1)
        item2 = list_widget.item(row2)
        text1 = item1.text()
        text2 = item2.text()
        item1.setText(text2)
        item2.setText(text1)
        self._update_item_tooltip(item1)
        self._update_item_tooltip(item2)
        self.config_changed.emit()

    def _replace_sequence_item(self, list_widget, item, new_text):
        item.setText(new_text)
        self._update_item_tooltip(item)
        self.config_changed.emit()

    def _move_sequence_item(self, list_widget, item, direction):
        row = list_widget.row(item)
        new_row = row + direction
        if 0 <= new_row < list_widget.count():
            current_item = list_widget.takeItem(row)
            list_widget.insertItem(new_row, current_item)
            list_widget.setCurrentItem(current_item)
            self.config_changed.emit()

    def _update_item_tooltip(self, item):
        text = item.text()
        if text in self.SEQUENCE_TOOLTIPS:
            item.setToolTip(self.SEQUENCE_TOOLTIPS[text])
        else:
            item.setToolTip("")

    def _update_list_tooltips(self, list_widget):
        for i in range(list_widget.count()):
            self._update_item_tooltip(list_widget.item(i))

    def _update_sequence_item_colors(self):
        """Grey out sequence list items whose corresponding feature is disabled/unconfigured."""
        config = self.main_window.config if self.main_window and hasattr(self.main_window, 'config') else None
        if config is None:
            return

        grey = QColor(150, 150, 150)

        # Map sequence item text -> callable that returns True if the item is active
        def has_path(attr):
            return bool(getattr(config, attr, '') and config.defaults.get(f'{attr}_enabled', True))

        active_map = {
            'No-TB':             lambda: config.hide_taskbar,
            'Taskbar':           lambda: config.hide_taskbar,
            'Controller-Mapper': lambda: has_path('controller_mapper_path'),
            'Borderless':        lambda: has_path('borderless_gaming_path'),
            'Monitor-Config':    lambda: has_path('monitorapp_path'),
            'Cloud-Sync':        lambda: has_path('cloud_sync_path'),
            'mount-disc':        lambda: has_path('disc_mount_path'),
            'Unmount-disc':      lambda: has_path('disc_mount_path') or bool(getattr(config, 'disc_unmount_cfg', '') and config.defaults.get('disc_unmount_cfg_enabled', True)),
            'Kill-Game':         lambda: True,
            'Kill-List':         lambda: config.use_kill_list,
            'Pre1':              lambda: has_path('pre1_path'),
            'Pre2':              lambda: has_path('pre2_path'),
            'Pre3':              lambda: has_path('pre3_path'),
            'Post1':             lambda: has_path('post1_path'),
            'Post2':             lambda: has_path('post2_path'),
            'Post3':             lambda: has_path('post3_path'),
            'JustAfterLaunch':   lambda: has_path('just_after_launch_path'),
            'JustBeforeExit':    lambda: has_path('just_before_exit_path'),
            'RunAudio':          lambda: has_path('audio_tool_path'),
            'ReturnAudio':       lambda: has_path('audio_tool_path'),
            'Backup':            lambda: has_path('local_backup_path'),
        }

        for list_widget in (self.launch_sequence_list, self.exit_sequence_list):
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                text = item.text()
                is_active = active_map.get(text, lambda: True)()
                if is_active:
                    # Clear any explicit foreground so Qt uses the palette colour
                    item.setData(Qt.ItemDataRole.ForegroundRole, None)
                else:
                    item.setForeground(QBrush(grey))

    def sync_ui_from_config(self, config: AppConfig):
        self.blockSignals(True)

        self.source_dirs_list.clear()
        self.source_dirs_list.addItems(config.source_dirs)
        self.excluded_dirs_list.clear()
        self.excluded_dirs_list.addItems(config.excluded_dirs)
        self.other_managers_combo.setCurrentText(config.game_managers_present)
        self.exclude_manager_checkbox.setChecked(config.exclude_selected_manager_games)
        self.logging_verbosity_combo.setCurrentText(config.logging_verbosity)
        self.fuzzy_match_spin.setValue(getattr(config, 'fuzzy_match_cutoff', 0.6))

        # Appearance
        theme_id = getattr(config, 'ui_theme', 'default') or 'default'
        idx = self.theme_selector.findData(theme_id)
        self.theme_selector.setCurrentIndex(idx if idx >= 0 else 0)

        font_family = getattr(config, 'ui_font_family', "")
        if font_family:
            self.font_selector.setCurrentFont(QFont(font_family))
        
        font_size = getattr(config, 'ui_font_size', 9)
        self.font_size_spin.setValue(font_size)

        editor_font_family = getattr(config, 'editor_font_family', "")
        if editor_font_family:
            self.editor_font_selector.setCurrentFont(QFont(editor_font_family))
        
        editor_font_size = getattr(config, 'editor_font_size', 9)
        self.editor_font_size_spin.setValue(editor_font_size)

        self.run_as_admin_checkbox.setChecked(config.run_as_admin)
        self.use_kill_list_checkbox.setChecked(config.use_kill_list)
        self.hide_taskbar_checkbox.setChecked(config.hide_taskbar)
        self.terminate_bw_on_exit_checkbox.setChecked(config.terminate_borderless_on_exit)

        for attr_name in self.PATH_ATTRIBUTES:
            if attr_name in self.path_rows:
                row = self.path_rows[attr_name]
                path_value = getattr(config, attr_name, "")
                
                # Determine if this path should be enabled
                if not path_value and attr_name not in ["profiles_dir", "launchers_dir"]:
                    should_be_enabled = False
                else:
                    should_be_enabled = config.defaults.get(f"{attr_name}_enabled", True)
                
                # Set enabled state FIRST before setting path
                if row.enabled_cb:
                    row.enabled = should_be_enabled
                
                # If disabled and using combobox, ensure blank option is prepended and selected
                if not should_be_enabled and row.use_combobox:
                    # Prepend blank option if not already there
                    if row.combo.count() == 0 or row.combo.itemText(0) != "":
                        row.combo.insertItem(0, "")
                    row.combo.setCurrentIndex(0)
                else:
                    # Special handling for launcher_executable: if empty, keep the default selection
                    if attr_name == "launcher_executable" and not path_value:
                        # Don't set the path, keep the default from _populate_launcher_combo
                        pass
                    else:
                        row.path = path_value
                
                row.mode = config.deployment_path_modes.get(attr_name, "CEN")
                row.run_wait = config.run_wait_states.get(f"{attr_name}_run_wait", False)

                # Initialize last detected tool to prevent overwrite on load/sync
                if row.path:
                    exe_name = os.path.basename(row.path).lower()
                    exe_no_ext = os.path.splitext(exe_name)[0]
                    if exe_name in self.options_args_map:
                        self.last_detected_tools[attr_name] = exe_name
                    elif exe_no_ext in self.options_args_map:
                        self.last_detected_tools[attr_name] = exe_no_ext
                    elif attr_name in self.options_args_map:
                        self.last_detected_tools[attr_name] = attr_name
                    else:
                        self.last_detected_tools[attr_name] = exe_name

        self.launch_sequence_list.clear()
        # Ensure new items are in the sequence (migration for existing configs)
        launch_seq = config.launch_sequence if config.launch_sequence else []
        if not launch_seq:
            # Use defaults for new configs
            launch_seq = ["Cloud-Sync", "mount-disc", "Controller-Mapper", "Monitor-Config", "No-TB", "Pre1", "Pre2", "Pre3", "Borderless", "RunAudio", "Backup"]
        else:
            # Migrate existing configs: add new items if missing
            if "Cloud-Sync" not in launch_seq:
                launch_seq.insert(0, "Cloud-Sync")
            if "mount-disc" not in launch_seq:
                # Insert after Cloud-Sync
                insert_pos = launch_seq.index("Cloud-Sync") + 1 if "Cloud-Sync" in launch_seq else 0
                launch_seq.insert(insert_pos, "mount-disc")
            if "RunAudio" not in launch_seq:
                if "No-TB" in launch_seq:
                    launch_seq.insert(launch_seq.index("No-TB") + 1, "RunAudio")
                else:
                    launch_seq.append("RunAudio")
            if "Backup" not in launch_seq:
                launch_seq.append("Backup")
        
        self.launch_sequence_list.addItems(launch_seq)
        self._update_list_tooltips(self.launch_sequence_list)
        
        self.exit_sequence_list.clear()
        # Ensure new items are in the sequence (migration for existing configs)
        exit_seq = config.exit_sequence if config.exit_sequence else []
        if not exit_seq:
            # Use defaults for new configs
            exit_seq = ["Post1", "Post2", "Post3", "Monitor-Config", "Taskbar", "Controller-Mapper", "Unmount-disc", "Cloud-Sync", "ReturnAudio", "Backup"]
        else:
            # Migrate existing configs: add new items if missing
            if "Unmount-disc" not in exit_seq:
                # Insert before Cloud-Sync if it exists, otherwise at end
                if "Cloud-Sync" in exit_seq:
                    insert_pos = exit_seq.index("Cloud-Sync")
                else:
                    insert_pos = len(exit_seq)
                exit_seq.insert(insert_pos, "Unmount-disc")
            if "Cloud-Sync" not in exit_seq:
                exit_seq.append("Cloud-Sync")
            if "ReturnAudio" not in exit_seq:
                if "Borderless" in exit_seq:
                    exit_seq.insert(exit_seq.index("Borderless") + 1, "ReturnAudio")
                else:
                    exit_seq.append("ReturnAudio")
            if "Backup" not in exit_seq:
                exit_seq.append("Backup")
        
        self.exit_sequence_list.addItems(exit_seq)
        self._update_list_tooltips(self.exit_sequence_list)
        self._update_sequence_item_colors()        
        # Cloud Backup Configuration
        self.rclone_remote_name_edit.setText(getattr(config, 'rclone_remote_name', ''))
        self.rclone_local_path_row.path = getattr(config, 'rclone_local_path', '')
        self.rclone_remote_path_edit.setText(getattr(config, 'rclone_remote_path', ''))
        self.rclone_sync_mode_combo.setCurrentText(getattr(config, 'rclone_sync_mode', 'sync'))
        self.rclone_backup_on_launch_cb.setChecked(getattr(config, 'rclone_backup_on_launch', False))
        self.rclone_backup_on_exit_cb.setChecked(getattr(config, 'rclone_backup_on_exit', True))
        
        self.ludusavi_backup_path_row.path = getattr(config, 'ludusavi_backup_path', '')
        self.ludusavi_game_name_edit.setText(getattr(config, 'ludusavi_game_name', ''))
        self.ludusavi_backup_on_launch_cb.setChecked(getattr(config, 'ludusavi_backup_on_launch', False))
        self.ludusavi_backup_on_exit_cb.setChecked(getattr(config, 'ludusavi_backup_on_exit', True))
        
        # Syncthing Configuration
        self.syncthing_sync_folder_row.path = getattr(config, 'syncthing_sync_folder', '')
        self.syncthing_auto_start_cb.setChecked(getattr(config, 'syncthing_auto_start', True))
        
        # EmuSync Configuration
        self.emusync_emulator_path_row.path = getattr(config, 'emusync_emulator_path', '')
        self.emusync_sync_on_launch_cb.setChecked(getattr(config, 'emusync_sync_on_launch', True))
        self.emusync_sync_on_exit_cb.setChecked(getattr(config, 'emusync_sync_on_exit', True))
        
        # Game Backup Monitor Configuration
        self.gbm_backup_path_row.path = getattr(config, 'gbm_backup_path', '')
        self.gbm_monitor_on_launch_cb.setChecked(getattr(config, 'gbm_monitor_on_launch', True))
        
        # Game Save Manager Configuration
        self.gsm_backup_path_row.path = getattr(config, 'gsm_backup_path', '')
        self.gsm_backup_on_exit_cb.setChecked(getattr(config, 'gsm_backup_on_exit', True))
        
        # Save State Configuration
        self.savestate_backup_path_row.path = getattr(config, 'savestate_backup_path', '')
        self.savestate_auto_backup_cb.setChecked(getattr(config, 'savestate_auto_backup', True))

        # Update initial state of sub-tab widgets
        self._update_cloud_backup_state()

        # Configuration Presets: reflect the active settings path in the combobox.
        if hasattr(self, 'config_preset_manager'):
            self._populate_preset_combo()
            current = self.config_preset_manager.current_settings_path()
            idx = self.preset_combo.findData(current)
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            else:
                # Fall back to the LOCAL preset (default element).
                local_idx = self.preset_combo.findData(LOCAL_PRESET_MARKER)
                if local_idx >= 0:
                    self.preset_combo.setCurrentIndex(local_idx)

        # Auto-populate Monitor-Config Game/Desk paths from root .cfg files
        _root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _auto_populate_pairs = [
            ("monitor_game_path", "G_MON.cfg", "monitor_game_enabled"),
            ("monitor_desk_path", "DT_D.cfg", "monitor_desk_enabled"),
        ]
        _auto_populated = False
        for _path_key, _cfg_file, _enabled_key in _auto_populate_pairs:
            _current = getattr(config, _path_key, "")
            if not _current:
                _cfg_path = os.path.join(_root_dir, _cfg_file)
                if os.path.exists(_cfg_path):
                    setattr(config, _path_key, _cfg_path)
                    setattr(config, _enabled_key, True)
                    config.defaults[f'{_path_key}_enabled'] = True
                    _auto_populated = True
                    if _path_key in self.path_rows:
                        row = self.path_rows[_path_key]
                        row.path = _cfg_path
                        row.enabled = True

        self.blockSignals(False)

        if _auto_populated:
            self.config_changed.emit()

    def sync_config_from_ui(self, config: AppConfig):
        config.source_dirs = [self.source_dirs_list.item(i).text() for i in range(self.source_dirs_list.count())]
        config.excluded_dirs = [self.excluded_dirs_list.item(i).text() for i in range(self.excluded_dirs_list.count())]
        config.game_managers_present = self.other_managers_combo.currentText()
        config.exclude_selected_manager_games = self.exclude_manager_checkbox.isChecked()
        config.logging_verbosity = self.logging_verbosity_combo.currentText()
        config.fuzzy_match_cutoff = self.fuzzy_match_spin.value()

        # Appearance
        theme_id = self.theme_selector.currentData()
        if theme_id:
            config.ui_theme = theme_id

        config.ui_font_family = self.font_selector.currentFont().family()
        config.ui_font_size = self.font_size_spin.value()
        
        config.editor_font_family = self.editor_font_selector.currentFont().family()
        config.editor_font_size = self.editor_font_size_spin.value()

        config.run_as_admin = self.run_as_admin_checkbox.isChecked()
        config.use_kill_list = self.use_kill_list_checkbox.isChecked()
        config.hide_taskbar = self.hide_taskbar_checkbox.isChecked()
        config.terminate_borderless_on_exit = self.terminate_bw_on_exit_checkbox.isChecked()

        for attr_name in self.PATH_ATTRIBUTES:
            if attr_name in self.path_rows:
                row = self.path_rows[attr_name]
                
                # If disabled, save empty string; otherwise save the path
                if row.enabled_cb and not row.enabled:
                    setattr(config, attr_name, "")
                else:
                    setattr(config, attr_name, row.path)
                
                config.deployment_path_modes[attr_name] = row.mode
                if row.enabled_cb:
                    config.defaults[f"{attr_name}_enabled"] = row.enabled
                if row.run_wait_cb:
                    config.run_wait_states[f"{attr_name}_run_wait"] = row.run_wait

        config.launch_sequence = [self.launch_sequence_list.item(i).text() for i in range(self.launch_sequence_list.count())]
        config.exit_sequence = [self.exit_sequence_list.item(i).text() for i in range(self.exit_sequence_list.count())]
        
        # Check if Cloud Sync is enabled
        cloud_enabled = self.path_rows["cloud_sync_path"].enabled
        
        # Cloud Backup Configuration
        config.rclone_remote_name = self.rclone_remote_name_edit.text() if cloud_enabled else ""
        config.rclone_local_path = self.rclone_local_path_row.path if cloud_enabled else ""
        config.rclone_remote_path = self.rclone_remote_path_edit.text() if cloud_enabled else ""
        config.rclone_sync_mode = self.rclone_sync_mode_combo.currentText() if cloud_enabled else "sync"
        config.rclone_backup_on_launch = self.rclone_backup_on_launch_cb.isChecked() if cloud_enabled else False
        config.rclone_backup_on_exit = self.rclone_backup_on_exit_cb.isChecked() if cloud_enabled else False
        
        config.ludusavi_backup_path = self.ludusavi_backup_path_row.path if cloud_enabled else ""
        config.ludusavi_game_name = self.ludusavi_game_name_edit.text() if cloud_enabled else ""
        config.ludusavi_backup_on_launch = self.ludusavi_backup_on_launch_cb.isChecked() if cloud_enabled else False
        config.ludusavi_backup_on_exit = self.ludusavi_backup_on_exit_cb.isChecked() if cloud_enabled else False
        
        # Syncthing Configuration
        config.syncthing_sync_folder = self.syncthing_sync_folder_row.path if cloud_enabled else ""
        config.syncthing_auto_start = self.syncthing_auto_start_cb.isChecked() if cloud_enabled else False
        
        # EmuSync Configuration
        config.emusync_emulator_path = self.emusync_emulator_path_row.path if cloud_enabled else ""
        config.emusync_sync_on_launch = self.emusync_sync_on_launch_cb.isChecked() if cloud_enabled else False
        config.emusync_sync_on_exit = self.emusync_sync_on_exit_cb.isChecked() if cloud_enabled else False
        
        # Game Backup Monitor Configuration
        config.gbm_backup_path = self.gbm_backup_path_row.path if cloud_enabled else ""
        config.gbm_monitor_on_launch = self.gbm_monitor_on_launch_cb.isChecked() if cloud_enabled else False
        
        # Game Save Manager Configuration
        config.gsm_backup_path = self.gsm_backup_path_row.path if cloud_enabled else ""
        config.gsm_backup_on_exit = self.gsm_backup_on_exit_cb.isChecked() if cloud_enabled else False
        
        # Save State Configuration
        config.savestate_backup_path = self.savestate_backup_path_row.path if cloud_enabled else ""
        config.savestate_auto_backup = self.savestate_auto_backup_cb.isChecked() if cloud_enabled else False

        # Configuration Presets: persist the active settings path (LOCAL -> Python/config.json)
        text, data = self._current_preset_selection()
        if data == LOCAL_PRESET_MARKER:
            config.current_settings = os.path.join(
                self.config_preset_manager.app_directory, "Python", DEFAULT_CONFIG_JSON
            )
        elif data:
            config.current_settings = data
        elif text:
            config.current_settings = text
        config.app_directory = self.config_preset_manager.app_directory

    def _on_theme_changed(self, index: int):
        """Apply the selected theme immediately and persist it to config."""
        theme_id = self.theme_selector.itemData(index)
        if not theme_id:
            return
        theme_manager = ThemeManager()
        config = getattr(self.main_window, 'config', None)
        requires_restart = theme_manager.apply_theme(theme_id, QApplication.instance(), config=config)
        if config is not None:
            config.ui_theme = theme_id
            self.config_changed.emit()
        # Re-apply Qlementine capability enhancements (nav bar, popover QSS,
        # accordion style) whenever the theme changes at runtime.
        if hasattr(self.main_window, 'apply_ui_capabilities'):
            self.main_window.apply_ui_capabilities()
        if requires_restart:
            QMessageBox.information(
                self,
                "Restart Required",
                "The selected theme will take full effect after restarting the application.",
            )

    def _reset_theme(self):
        """Reset theme to default (Fluent WinUI 3)."""
        idx = self.theme_selector.findData("fluent_winui3")
        self.theme_selector.setCurrentIndex(idx if idx >= 0 else 0)

    def _reset_ui_font(self):
        """Reset UI font to system default."""
        self.font_selector.setCurrentFont(self.font().family())
        self.font_size_spin.setValue(9)

    def _reset_editor_font(self):
        """Reset Editor font to system default."""
        self.editor_font_selector.setCurrentFont(self.font().family())
        self.editor_font_size_spin.setValue(9)

    def _on_font_changed(self, font):
        """Apply font change immediately."""
        font.setPointSize(self.font_size_spin.value())
        QApplication.instance().setFont(font)
        if hasattr(self.main_window, 'config'):
            self.main_window.config.ui_font_family = font.family()
            self.config_changed.emit()

    def _on_font_size_changed(self, size):
        """Apply font size change immediately."""
        font = self.font_selector.currentFont()
        font.setPointSize(size)
        QApplication.instance().setFont(font)
        if hasattr(self.main_window, 'config'):
            self.main_window.config.ui_font_size = size
            self.config_changed.emit()

    def _on_editor_font_changed(self, font):
        """Apply editor font change immediately."""
        font.setPointSize(self.editor_font_size_spin.value())
        if hasattr(self.main_window, 'editor_tab'):
            self.main_window.editor_tab.table.setFont(font)
        if hasattr(self.main_window, 'config'):
            self.main_window.config.editor_font_family = font.family()
            self.config_changed.emit()

    def _on_editor_font_size_changed(self, size):
        """Apply editor font size change immediately."""
        font = self.editor_font_selector.currentFont()
        font.setPointSize(size)
        if hasattr(self.main_window, 'editor_tab'):
            self.main_window.editor_tab.table.setFont(font)
        if hasattr(self.main_window, 'config'):
            self.main_window.config.editor_font_size = size
            self.config_changed.emit()
    def _on_local_backup_tool_changed(self, index):
        self.local_backup_stack.setCurrentIndex(index)

    def _on_cloud_sync_tool_changed(self, index):
        self.cloud_sync_stack.setCurrentIndex(index)

    def _on_path_text_changed(self, config_key, new_path):
        """Updates options and arguments if the new path matches a known tool."""
        if not new_path:
            return

    def _log_plugin_info(self):
        """Log information about registered plugins"""
        import logging
        registry = self.plugin_manager.get_registry()
        logging.info(f"Plugin system initialized with {len(registry)} plugins")
        
        for plugin in registry.get_all():
            logging.info(f"  - {plugin.metadata.display_name} ({plugin.metadata.name}) v{plugin.metadata.version}")
        
        # Log installed tools
        installed = self.plugin_manager.scan_installed_tools()
        if installed:
            logging.info(f"Found {len(installed)} installed tools:")
            for tool_name, paths in installed.items():
                logging.info(f"  - {tool_name}: {len(paths)} executable(s) found")

    # ── Tool plugin-gated tab visibility ───────────────────────────── #
    SETUP_TOOL_TAB_MAP = {
        'borderless_window': 3,   # WINDOWING
        'disc_mount': 4,          # DISC-MOUNTING
        'local_backup': 5,        # LOCAL-BACKUP
        'cloud_sync': 6,          # CLOUD-SYNC
        'audio': 7,               # AUDIO
    }

    def set_enabled_tools(self, enabled_tools: set):
        """Show/hide setup sub-tabs based on which tool plugins are enabled."""
        for tool, tab_idx in self.SETUP_TOOL_TAB_MAP.items():
            visible = tool in enabled_tools
            self.paths_tabs.setTabVisible(tab_idx, visible)

    def _open_plugin_manager(self):
        """Open the Plugin Manager dialog"""
        from Python.ui.plugin_manager_dialog import PluginManagerDialog
        current_tools = set(getattr(self.window(), 'enabled_tools', set()))
        dialog = PluginManagerDialog(self, enabled_tools=current_tools)
        dialog.exec()
        new_tools = dialog.get_enabled_tools()
        if new_tools is not None and new_tools != current_tools:
            mw = self.window()
            if hasattr(mw, 'set_enabled_tools'):
                mw.set_enabled_tools(new_tools)