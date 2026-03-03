import logging
import os
import configparser
import requests
import zipfile
import shutil
import subprocess
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QGroupBox, QLabel, QFormLayout, QPushButton,
    QComboBox, QHBoxLayout, QCheckBox, QTabWidget,
    QFileDialog, QApplication, QSpinBox, QMessageBox, QMenu, QInputDialog,
    QDialog, QDialogButtonBox, QLineEdit, QProgressDialog, QGridLayout, QDoubleSpinBox,
    QStyle
)
import re
from PyQt6.QtCore import pyqtSignal, Qt, QThread, pyqtSlot
from Python.models import AppConfig
from Python.ui.widgets import DragDropListWidget, PathConfigRow
from Python.ui.accordion import AccordionSection
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
                    
                except Exception as e:
                    last_error = str(e)
                    continue  # Try next URL
            
            if success:
                self.finished.emit(True, "Download completed successfully", self.extract_dir)
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
        "borderless_gaming_path", "multi_monitor_tool_path", "disc_mount_path", "disc_unmount_path", "p1_profile_path",
        "p2_profile_path", "mediacenter_profile_path", "multimonitor_gaming_path",
        "multimonitor_media_path", "pre1_path", "pre2_path", "pre3_path",
        "just_after_launch_path", "just_before_exit_path",
        "post1_path", "post2_path", "post3_path",
        "cloud_sync_path", "local_backup_path"
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

    def _add_path_row(self, layout, label_text, config_key, row_widget):
        formatted_text = f"{label_text}"
        label = QLabel(formatted_text)
        label.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        label.setToolTip("Right-click to configure Options & Arguments")
        label.customContextMenuRequested.connect(
            lambda pos: self._show_options_args_dialog(pos, config_key, label_text)
        )
        layout.addRow(label, row_widget)

    def _setup_ui(self):
        """Create and arrange all widgets for the Setup tab."""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 0, 5)

        # --- Section 1: Sources & Indexing ---
        source_config_widget = QWidget()
        source_config_layout = QGridLayout(source_config_widget)
        source_config_layout.setSpacing(10)
        
        # --- Sources Group (Top-Left) ---
        sources_group_widget = QWidget()
        sources_layout = QVBoxLayout(sources_group_widget)
        sources_layout.setContentsMargins(0, 0, 0, 0)

        source_label = QLabel("<b>Source Directories</b>")
        source_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        source_buttons_widget = QWidget()
        source_buttons_layout = QHBoxLayout(source_buttons_widget)
        source_buttons_layout.setContentsMargins(0, 0, 0, 0)
        add_source_button = QPushButton("+")
        add_source_button.setToolTip("Add a directory to scan for games.")
        add_source_button.setFixedWidth(30)
        add_source_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        remove_source_button = QPushButton("-")
        remove_source_button.setToolTip("Remove the selected directory from scanning.")
        remove_source_button.setFixedWidth(30)
        remove_source_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
        source_buttons_layout.addWidget(add_source_button)
        source_buttons_layout.addWidget(remove_source_button)
        source_buttons_layout.addStretch()

        self.source_dirs_list = DragDropListWidget()
        self.source_dirs_list.setMinimumHeight(40)
        self.source_dirs_list.setMaximumHeight(200)

        sources_layout.addWidget(source_label)
        sources_layout.addWidget(source_buttons_widget)
        sources_layout.addWidget(self.source_dirs_list)

        self.add_source_dir_button = add_source_button
        self.remove_source_dir_button = remove_source_button

        # --- Excluded Group (Bottom-Right) ---
        excluded_group_widget = QWidget()
        excluded_layout = QVBoxLayout(excluded_group_widget)
        excluded_layout.setContentsMargins(0, 0, 0, 0)

        excluded_label = QLabel("<b>Excluded Directories</b>")
        excluded_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        excluded_buttons_widget = QWidget()
        excluded_buttons_layout = QHBoxLayout(excluded_buttons_widget)
        excluded_buttons_layout.setContentsMargins(0, 1, 0, 1)
        add_excluded_button = QPushButton("+")
        add_excluded_button.setToolTip("Add a directory to exclude from scanning.")
        add_excluded_button.setFixedWidth(30)
        add_excluded_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        remove_excluded_button = QPushButton("-")
        remove_excluded_button.setToolTip("Remove the selected directory from exclusion.")
        remove_excluded_button.setFixedWidth(30)
        remove_excluded_button.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton))
        excluded_buttons_layout.addStretch()
        excluded_buttons_layout.addWidget(add_excluded_button)
        excluded_buttons_layout.addWidget(remove_excluded_button)

        self.excluded_dirs_list = DragDropListWidget()
        self.excluded_dirs_list.setMaximumHeight(70)

        excluded_layout.addWidget(excluded_label)
        excluded_layout.addWidget(excluded_buttons_widget)
        excluded_layout.addWidget(self.excluded_dirs_list)

        self.add_excluded_dir_button = add_excluded_button
        self.remove_excluded_dir_button = remove_excluded_button

        # --- Add groups to main grid layout ---
        source_config_layout.addWidget(sources_group_widget, 0, 0, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        source_config_layout.addWidget(excluded_group_widget, 0, 1, Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        # Game managers
        self.other_managers_combo = QComboBox()
        self.other_managers_combo.addItems(["None", "Steam", "Epic", "GOG", "Origin", "Ubisoft Connect", "Battle.net", "Xbox"])
        self.exclude_manager_checkbox = QCheckBox("Exclude Selected Manager's Games")
        game_managers_layout = QHBoxLayout()
        game_managers_layout.addWidget(self.other_managers_combo)
        game_managers_layout.addWidget(self.exclude_manager_checkbox)
        game_managers_layout.addStretch(1)
        
        source_config_layout.addWidget(QLabel("Game Managers Present"), 2, 0)
        source_config_layout.addLayout(game_managers_layout, 2, 1)
        
        # Set column stretch to allow lists to expand
        source_config_layout.setColumnStretch(0, 1)
        source_config_layout.setColumnStretch(1, 1)

        source_config_section = AccordionSection("SOURCES AND INDEXING", source_config_widget, start_expanded=True)

        # --- Section 2: Paths & Profiles ---
        paths_widget = QWidget()
        paths_layout = QVBoxLayout(paths_widget)
        paths_layout.setContentsMargins(0,0,0,0)
        paths_tabs = QTabWidget()
        paths_layout.addWidget(paths_tabs)

        # Core Paths Tab
        # Prepare repo items for generic lists (All except GLOBAL)
        all_tools = {}
        # Add Mount DISC option at the top
        all_tools["Mount DISC"] = {"special": "mount_disc"}
        
        for section, items in self.repos.items():
            if section != "GLOBAL":
                all_tools.update(items)

        core_paths_widget = QWidget()
        core_paths_layout = QVBoxLayout(core_paths_widget)
        
        # Directories Group
        directories_group = QGroupBox("Directories")
        directories_layout = QFormLayout(directories_group)
        self.path_rows["profiles_dir"] = PathConfigRow("profiles_dir", is_directory=True, add_enabled=True, add_cen_lc=True, use_combobox=False)
        self.path_rows["profiles_dir"].enabled_cb.setToolTip("Create Profile Folders")
        directories_layout.addRow("Profiles Directory:", self.path_rows["profiles_dir"]) # No options/args for dirs
        self.path_rows["launchers_dir"] = PathConfigRow("launchers_dir", is_directory=True, add_enabled=True, add_cen_lc=True, use_combobox=False)
        self.path_rows["launchers_dir"].enabled_cb.setToolTip("Create Launcher")
        directories_layout.addRow("Launchers Directory:", self.path_rows["launchers_dir"]) # No options/args for dirs
        core_paths_layout.addWidget(directories_group)

        # Launcher Configuration Group
        launcher_group = QGroupBox("Launcher Configuration")
        launcher_layout = QFormLayout(launcher_group)
        self.path_rows["launcher_executable"] = PathConfigRow("launcher_executable", is_directory=False, add_enabled=False, add_cen_lc=True, use_combobox=True)
        self._add_path_row(launcher_layout, "Launcher Executable:", "launcher_executable", self.path_rows["launcher_executable"])

        # Moved checkboxes from Deployment Tab
        self.run_as_admin_checkbox = QCheckBox("Run As Admin")
        self.use_kill_list_checkbox = QCheckBox("Use Kill List")
        self.hide_taskbar_checkbox = QCheckBox("Hide Taskbar")
        self.terminate_bw_on_exit_checkbox = QCheckBox("Terminate Borderless on Exit")

        cb_container = QWidget()
        cb_layout = QGridLayout(cb_container)
        cb_layout.setContentsMargins(0, 0, 0, 0)
        cb_layout.addWidget(self.run_as_admin_checkbox, 0, 0)
        cb_layout.addWidget(self.use_kill_list_checkbox, 0, 1)
        cb_layout.addWidget(self.hide_taskbar_checkbox, 1, 0)
        cb_layout.addWidget(self.terminate_bw_on_exit_checkbox, 1, 1)
        launcher_layout.addRow(cb_container)
        
        core_paths_layout.addWidget(launcher_group)
        core_paths_layout.addStretch()

        paths_tabs.addTab(core_paths_widget, "   CORE   ")

        # Application Paths Tab
        app_paths_widget = QWidget()
        app_paths_layout = QFormLayout(app_paths_widget)
        self.path_rows["disc_mount_path"] = PathConfigRow("disc_mount_path", add_run_wait=True, repo_items=self.mounting_tools, add_cen_lc=True, add_enabled=True)
        self.path_rows["disc_mount_path"].enabled_cb.setToolTip("Overwrite Mounting")
        self._add_path_row(app_paths_layout, "Disc-Mount:", "disc_mount_path", self.path_rows["disc_mount_path"])
        self.path_rows["disc_unmount_path"] = PathConfigRow("disc_unmount_path", add_run_wait=True, repo_items=self.mounting_tools, add_cen_lc=True, add_enabled=True)
        self.path_rows["disc_unmount_path"].enabled_cb.setToolTip("Overwrite Unmounting")
        self._add_path_row(app_paths_layout, "Disc-Unmount:", "disc_unmount_path", self.path_rows["disc_unmount_path"])
        
        self.path_rows["controller_mapper_path"] = PathConfigRow("controller_mapper_path", add_run_wait=True, repo_items=self.repos.get("MAPPERS"))
        self.path_rows["controller_mapper_path"].enabled_cb.setToolTip("Enable Controller Mapper")
        self._add_path_row(app_paths_layout, "Controller Mapper:", "controller_mapper_path", self.path_rows["controller_mapper_path"])
        self.path_rows["borderless_gaming_path"] = PathConfigRow("borderless_gaming_path", add_run_wait=True, repo_items=self.repos.get("WINDOWING"))
        self.path_rows["borderless_gaming_path"].enabled_cb.setToolTip("Enable Borderless Windowing")
        self._add_path_row(app_paths_layout, "Borderless Windowing:", "borderless_gaming_path", self.path_rows["borderless_gaming_path"])
        self.path_rows["multi_monitor_tool_path"] = PathConfigRow("multi_monitor_tool_path", add_run_wait=True, repo_items=self.repos.get("DISPLAY"))
        self.path_rows["multi_monitor_tool_path"].enabled_cb.setToolTip("Enable Multi-Monitor Tool")
        self._add_path_row(app_paths_layout, "Multi-Monitor App:", "multi_monitor_tool_path", self.path_rows["multi_monitor_tool_path"])
        self.path_rows["just_after_launch_path"] = PathConfigRow("just_after_launch_path", add_run_wait=True, repo_items=all_tools)
        self.path_rows["just_after_launch_path"].enabled_cb.setToolTip("Enable Just After Launch App")
        self._add_path_row(app_paths_layout, "Just After Launch:", "just_after_launch_path", self.path_rows["just_after_launch_path"])
        self.path_rows["just_before_exit_path"] = PathConfigRow("just_before_exit_path", add_run_wait=True, repo_items=all_tools)
        self.path_rows["just_before_exit_path"].enabled_cb.setToolTip("Enable Just Before Exit App")
        self._add_path_row(app_paths_layout, "Just Before Exit:", "just_before_exit_path", self.path_rows["just_before_exit_path"])
        
        # Cloud Backup / Sync Tools (Unified)
        cloud_sync_tools = {}
        if "SYNC" in self.repos:
            cloud_sync_tools.update(self.repos["SYNC"])
        
        self.path_rows["cloud_sync_path"] = PathConfigRow("cloud_sync_path", add_run_wait=True, add_cen_lc=True, add_enabled=True, repo_items=cloud_sync_tools)
        self.path_rows["cloud_sync_path"].enabled_cb.setToolTip("Enable Cloud Sync/Backup")
        self._add_path_row(app_paths_layout, "Cloud Sync:", "cloud_sync_path", self.path_rows["cloud_sync_path"])
        
        # Local Backup Tools (Unified)
        local_backup_tools = {}
        if "LOCAL_BACKUP" in self.repos:
            local_backup_tools.update(self.repos["LOCAL_BACKUP"])
        
        self.path_rows["local_backup_path"] = PathConfigRow("local_backup_path", add_run_wait=True, add_cen_lc=True, add_enabled=True, repo_items=local_backup_tools)
        self.path_rows["local_backup_path"].enabled_cb.setToolTip("Enable Local Backup")
        self._add_path_row(app_paths_layout, "Local Backup:", "local_backup_path", self.path_rows["local_backup_path"])
        
        paths_tabs.addTab(app_paths_widget, "APPLICATIONS")

        # Profile Paths Tab
        profile_paths_widget = QWidget()
        profile_paths_layout = QFormLayout(profile_paths_widget)
        self.path_rows["p1_profile_path"] = PathConfigRow("p1_profile_path", add_enabled=True)
        profile_paths_layout.addRow("Player 1 Profile:", self.path_rows["p1_profile_path"])
        self.path_rows["p2_profile_path"] = PathConfigRow("p2_profile_path", add_enabled=True)
        profile_paths_layout.addRow("Player 2 Profile:", self.path_rows["p2_profile_path"])
        self.path_rows["mediacenter_profile_path"] = PathConfigRow("mediacenter_profile_path", add_enabled=True)
        profile_paths_layout.addRow("MediaCenter Profile:", self.path_rows["mediacenter_profile_path"])
        self.path_rows["multimonitor_gaming_path"] = PathConfigRow("multimonitor_gaming_path", add_enabled=True)
        profile_paths_layout.addRow("MM Gaming Config:", self.path_rows["multimonitor_gaming_path"])
        self.path_rows["multimonitor_media_path"] = PathConfigRow("multimonitor_media_path", add_enabled=True)
        profile_paths_layout.addRow("MM Desktop Config:", self.path_rows["multimonitor_media_path"])
        paths_tabs.addTab(profile_paths_widget, "   PROFILES   ")

        # Cloud Backup Configuration Tab
        cloud_backup_widget = QWidget()
        cloud_backup_layout = QFormLayout(cloud_backup_widget)
        
        # Rclone Configuration
        cloud_backup_layout.addRow(QLabel("<b>Rclone Configuration:</b>"))
        self.rclone_remote_name_edit = QLineEdit()
        self.rclone_remote_name_edit.setPlaceholderText("e.g., gdrive:")
        cloud_backup_layout.addRow("Remote Name:", self.rclone_remote_name_edit)
        
        self.rclone_local_path_row = PathConfigRow("rclone_local_path", is_directory=True, add_enabled=False)
        cloud_backup_layout.addRow("Local Save Path:", self.rclone_local_path_row)
        
        self.rclone_remote_path_edit = QLineEdit()
        self.rclone_remote_path_edit.setPlaceholderText("e.g., GameSaves/MyGame")
        cloud_backup_layout.addRow("Remote Path:", self.rclone_remote_path_edit)
        
        self.rclone_sync_mode_combo = QComboBox()
        self.rclone_sync_mode_combo.addItems(["sync", "copy", "copyto"])
        self.rclone_sync_mode_combo.setToolTip("sync=bidirectional, copy=upload only, copyto=download only")
        cloud_backup_layout.addRow("Sync Mode:", self.rclone_sync_mode_combo)
        
        self.rclone_backup_on_launch_cb = QCheckBox("Backup on Launch (download saves)")
        cloud_backup_layout.addRow("", self.rclone_backup_on_launch_cb)
        
        self.rclone_backup_on_exit_cb = QCheckBox("Backup on Exit (upload saves)")
        self.rclone_backup_on_exit_cb.setChecked(True)
        cloud_backup_layout.addRow("", self.rclone_backup_on_exit_cb)
        
        # Separator
        cloud_backup_layout.addRow(QLabel(""))
        
        # Ludusavi Configuration
        cloud_backup_layout.addRow(QLabel("<b>Ludusavi Configuration:</b>"))
        self.ludusavi_backup_path_row = PathConfigRow("ludusavi_backup_path", is_directory=True, add_enabled=False)
        cloud_backup_layout.addRow("Backup Directory:", self.ludusavi_backup_path_row)
        
        self.ludusavi_game_name_edit = QLineEdit()
        self.ludusavi_game_name_edit.setPlaceholderText("Leave empty for auto-detection")
        cloud_backup_layout.addRow("Game Name:", self.ludusavi_game_name_edit)
        
        self.ludusavi_backup_on_launch_cb = QCheckBox("Restore on Launch")
        cloud_backup_layout.addRow("", self.ludusavi_backup_on_launch_cb)
        
        self.ludusavi_backup_on_exit_cb = QCheckBox("Backup on Exit")
        self.ludusavi_backup_on_exit_cb.setChecked(True)
        cloud_backup_layout.addRow("", self.ludusavi_backup_on_exit_cb)
        
        # Separator
        cloud_backup_layout.addRow(QLabel(""))
        
        # Syncthing Configuration
        cloud_backup_layout.addRow(QLabel("<b>Syncthing Configuration:</b>"))
        self.syncthing_sync_folder_row = PathConfigRow("syncthing_sync_folder", is_directory=True, add_enabled=False)
        cloud_backup_layout.addRow("Sync Folder:", self.syncthing_sync_folder_row)
        
        self.syncthing_auto_start_cb = QCheckBox("Auto Start with Game")
        self.syncthing_auto_start_cb.setChecked(True)
        cloud_backup_layout.addRow("", self.syncthing_auto_start_cb)
        
        # Separator
        cloud_backup_layout.addRow(QLabel(""))
        
        # EmuSync Configuration
        cloud_backup_layout.addRow(QLabel("<b>EmuSync Configuration:</b>"))
        self.emusync_emulator_path_row = PathConfigRow("emusync_emulator_path", is_directory=True, add_enabled=False)
        cloud_backup_layout.addRow("Emulator Directory:", self.emusync_emulator_path_row)
        
        self.emusync_sync_on_launch_cb = QCheckBox("Sync on Launch")
        self.emusync_sync_on_launch_cb.setChecked(True)
        cloud_backup_layout.addRow("", self.emusync_sync_on_launch_cb)
        
        self.emusync_sync_on_exit_cb = QCheckBox("Sync on Exit")
        self.emusync_sync_on_exit_cb.setChecked(True)
        cloud_backup_layout.addRow("", self.emusync_sync_on_exit_cb)
        
        # Separator
        cloud_backup_layout.addRow(QLabel(""))
        
        # Game Backup Monitor Configuration
        cloud_backup_layout.addRow(QLabel("<b>Game Backup Monitor Configuration:</b>"))
        self.gbm_backup_path_row = PathConfigRow("gbm_backup_path", is_directory=True, add_enabled=False)
        cloud_backup_layout.addRow("Backup Directory:", self.gbm_backup_path_row)
        
        self.gbm_monitor_on_launch_cb = QCheckBox("Monitor on Launch")
        self.gbm_monitor_on_launch_cb.setChecked(True)
        cloud_backup_layout.addRow("", self.gbm_monitor_on_launch_cb)
        
        # Separator
        cloud_backup_layout.addRow(QLabel(""))
        
        # Game Save Manager Configuration
        cloud_backup_layout.addRow(QLabel("<b>Game Save Manager Configuration:</b>"))
        self.gsm_backup_path_row = PathConfigRow("gsm_backup_path", is_directory=True, add_enabled=False)
        cloud_backup_layout.addRow("Backup Directory:", self.gsm_backup_path_row)
        
        self.gsm_backup_on_exit_cb = QCheckBox("Backup on Exit")
        self.gsm_backup_on_exit_cb.setChecked(True)
        cloud_backup_layout.addRow("", self.gsm_backup_on_exit_cb)
        
        # Separator
        cloud_backup_layout.addRow(QLabel(""))
        
        # Save State Configuration
        cloud_backup_layout.addRow(QLabel("<b>Save State Configuration:</b>"))
        self.savestate_backup_path_row = PathConfigRow("savestate_backup_path", is_directory=True, add_enabled=False)
        cloud_backup_layout.addRow("Backup Directory:", self.savestate_backup_path_row)
        
        self.savestate_auto_backup_cb = QCheckBox("Auto Backup")
        self.savestate_auto_backup_cb.setChecked(True)
        cloud_backup_layout.addRow("", self.savestate_auto_backup_cb)
        
        paths_tabs.addTab(cloud_backup_widget, "CLOUD BACKUP")

        # Script Paths Tab
        script_paths_widget = QWidget()
        script_paths_layout = QFormLayout(script_paths_widget)
        for i in range(1, 4):
            key = f"pre{i}_path"
            self.path_rows[key] = PathConfigRow(key, add_run_wait=True, repo_items=all_tools)
            self.path_rows[key].enabled_cb.setToolTip(f"Enable Pre-Launch App {i}")
            self._add_path_row(script_paths_layout, f"Pre-Launch App {i}:", key, self.path_rows[key])
        for i in range(1, 4):
            key = f"post{i}_path"
            self.path_rows[key] = PathConfigRow(key, add_run_wait=True, repo_items=all_tools)
            self.path_rows[key].enabled_cb.setToolTip(f"Enable Post-Launch App {i}")
            self._add_path_row(script_paths_layout, f"Post-Launch App {i}:", key, self.path_rows[key])
        paths_tabs.addTab(script_paths_widget, "   SCRIPTS   ")
        
        paths_section = AccordionSection("PATHS AND PROFILES", paths_widget)

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
        sequences_section = AccordionSection("EXECUTION SEQUENCES", sequences_widget)

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

        # Editor Page Size
        self.page_size_spin = QSpinBox()
        self.page_size_spin.setRange(25, 2000)
        self.page_size_spin.setValue(50)
        self.page_size_spin.setToolTip("Number of rows per page in the Editor tab (75-2000)")
        behavior_layout.addRow("Editor Page Size:", self.page_size_spin)
        
        # Plugin Manager Button
        self.plugin_manager_btn = QPushButton("Plugin Manager")
        self.plugin_manager_btn.setToolTip("Open Plugin Manager to view, enable/disable, and manage plugins")
        self.plugin_manager_btn.clicked.connect(self._open_plugin_manager)
        behavior_layout.addRow("Plugins:", self.plugin_manager_btn)
        
        # Restart Button
        self.restart_btn = QPushButton("Reset to Defaults")
        self.restart_btn.setToolTip("Reset all application configuration to defaults")
        behavior_layout.addRow(self.restart_btn)
        behavior_section = AccordionSection("BEHAVIOR", behavior_widget)

        main_layout.addWidget(source_config_section)
        main_layout.addWidget(paths_section)
        main_layout.addWidget(sequences_section)
        main_layout.addWidget(behavior_section)
        main_layout.addStretch()
        self._connect_signals()
        
        # Populate Launcher Executable Combobox
        self._populate_launcher_combo()

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

    def _show_options_args_dialog(self, pos, config_key, label_text):
        """Show a modal dialog to edit options and arguments for the selected app."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"Options & Arguments - {label_text.strip(':')}")
        layout = QFormLayout(dialog)
        
        # Determine defaults based on the current executable path
        current_path = getattr(self.main_window.config, config_key, "")
        exe_name = os.path.basename(current_path).lower() if current_path else ""
        
        # Mutable container for defaults
        defaults_state = {
            'opts': "",
            'args': "",
            'has_defaults': False
        }
        
        if exe_name in self.options_args_map:
            defaults_state['opts'], defaults_state['args'] = self.options_args_map[exe_name]
            defaults_state['has_defaults'] = True

        options_edit = QLineEdit()
        options_edit.setText(getattr(self.main_window.config, f"{config_key}_options", ""))
        layout.addRow("Options:", options_edit)
        
        args_edit = QLineEdit()
        args_edit.setText(getattr(self.main_window.config, f"{config_key}_arguments", ""))
        layout.addRow("Arguments:", args_edit)
        
        # Visual indicator for defaults match
        status_label = QLabel()
        layout.addRow("", status_label)

        def check_defaults():
            if not defaults_state['has_defaults']:
                status_label.setText("")
                return
            
            is_match = (options_edit.text() == defaults_state['opts'] and 
                        args_edit.text() == defaults_state['args'])
            
            if is_match:
                status_label.setText("✓ Matches defaults")
            else:
                status_label.setText("⚠ Custom values")

        options_edit.textChanged.connect(check_defaults)
        args_edit.textChanged.connect(check_defaults)
        
        # Initial check
        check_defaults()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        
        # Add Reset button
        reset_btn = buttons.addButton("Reset to Defaults", QDialogButtonBox.ButtonRole.ResetRole)
        reset_btn.setVisible(defaults_state['has_defaults'])
        
        def reset_values():
            if defaults_state['has_defaults']:
                options_edit.setText(defaults_state['opts'])
                args_edit.setText(defaults_state['args'])
        reset_btn.clicked.connect(reset_values)

        # Function to update defaults if path changes while dialog is open
        def update_defaults_from_path():
            if config_key in self.path_rows:
                curr_path = self.path_rows[config_key].path
            else:
                curr_path = ""
            
            curr_exe = os.path.basename(curr_path).lower() if curr_path else ""
            
            if curr_exe in self.options_args_map:
                defaults_state['opts'], defaults_state['args'] = self.options_args_map[curr_exe]
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
                setattr(self.main_window.config, f"{config_key}_options", options_edit.text())
                setattr(self.main_window.config, f"{config_key}_arguments", args_edit.text())
                self.config_changed.emit()
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
            row.downloadRequested.connect(self._on_download_requested)
        
        # Link disc mount and unmount comboboxes
        if "disc_mount_path" in self.path_rows and "disc_unmount_path" in self.path_rows:
            mount_row = self.path_rows["disc_mount_path"]
            unmount_row = self.path_rows["disc_unmount_path"]
            if mount_row.combo and unmount_row.combo:
                mount_row.combo.currentTextChanged.connect(
                    lambda text: self._sync_disc_unmount(text)
                )
        
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
        self.page_size_spin.valueChanged.connect(self.config_changed.emit)
        self.restart_btn.clicked.connect(self._reset_to_defaults)

        # Connect Cloud/Backup enable signals to update sub-tab state
        if "cloud_sync_path" in self.path_rows:
            self.path_rows["cloud_sync_path"].enabled_cb.stateChanged.connect(self._update_cloud_backup_state)
        if "local_backup_path" in self.path_rows:
            self.path_rows["local_backup_path"].enabled_cb.stateChanged.connect(self._update_local_backup_state)

    def _update_cloud_backup_state(self):
        """Enable/Disable Cloud Backup tab widgets based on main cloud sync enable state."""
        enabled = self.path_rows["cloud_sync_path"].enabled
        
        self.rclone_remote_name_edit.setEnabled(enabled)
        self.rclone_local_path_row.setEnabled(enabled)
        self.rclone_remote_path_edit.setEnabled(enabled)
        self.rclone_sync_mode_combo.setEnabled(enabled)
        self.rclone_backup_on_launch_cb.setEnabled(enabled)
        self.rclone_backup_on_exit_cb.setEnabled(enabled)
        
        self.ludusavi_backup_path_row.setEnabled(enabled)
        self.ludusavi_game_name_edit.setEnabled(enabled)
        self.ludusavi_backup_on_launch_cb.setEnabled(enabled)
        self.ludusavi_backup_on_exit_cb.setEnabled(enabled)
        
        self.syncthing_sync_folder_row.setEnabled(enabled)
        self.syncthing_auto_start_cb.setEnabled(enabled)
        
        self.emusync_emulator_path_row.setEnabled(enabled)
        self.emusync_sync_on_launch_cb.setEnabled(enabled)
        self.emusync_sync_on_exit_cb.setEnabled(enabled)
        
        self.gbm_backup_path_row.setEnabled(enabled)
        self.gbm_monitor_on_launch_cb.setEnabled(enabled)
        
        self.gsm_backup_path_row.setEnabled(enabled)
        self.gsm_backup_on_exit_cb.setEnabled(enabled)
        
        self.savestate_backup_path_row.setEnabled(enabled)
        self.savestate_auto_backup_cb.setEnabled(enabled)

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

        config = configparser.ConfigParser()
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
                mapping[section.lower()] = (options, arguments)
        except Exception as e:
            logging.error(f"Error parsing options_arguments.set: {e}")
        return mapping

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


    def _on_wincdemu_download_finished(self, success, message, result_path, bin_dir):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        if success:
            self._write_exe_path_to_config("wincdemu", result_path)
            self._generate_mount_scripts_files(bin_dir, "wincdemu")
            self._refresh_tool_paths()  # Refresh all tool paths
            
            QMessageBox.information(self, "Download Complete", f"Successfully downloaded to:\n{result_path}")
        else:
            QMessageBox.critical(self, "Download Failed", f"Error: {message}")
            
        self.active_download_row = None
        self._current_download_tool_name = None

    def _on_imgdrive_download_finished(self, success, message, result_path, bin_dir):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        if success:
            exe_path = os.path.join(bin_dir, "imgdrive.exe")
            self._write_exe_path_to_config("imgdrive", exe_path)
            self._generate_mount_scripts_files(bin_dir, "imgdrive")
            self._refresh_tool_paths()  # Refresh all tool paths
            
            QMessageBox.information(self, "Download Complete", f"Successfully downloaded to:\n{result_path}")
        else:
            QMessageBox.critical(self, "Download Failed", f"Error: {message}")

        self.active_download_row = None
        self._current_download_tool_name = None
        
    def _on_cdmage_download_finished(self, success, message, result_path, bin_dir):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        if success:
            exe_path = os.path.join(bin_dir, "cdmage.exe")
            self._write_exe_path_to_config("cdmage", exe_path)
            self._generate_mount_scripts_files(bin_dir, "cdmage")
            self._refresh_tool_paths()  # Refresh all tool paths
            
            QMessageBox.information(self, "Download Complete", f"Successfully downloaded to:\n{result_path}")
        else:
            QMessageBox.critical(self, "Download Failed", f"Error: {message}")

        self.active_download_row = None
        self._current_download_tool_name = None

    def _on_osf_download_finished(self, success, message, result_path, bin_dir):
        if hasattr(self, 'progress_dialog'):
            self.progress_dialog.close()

        if success:
            exe_path = os.path.join(bin_dir, "osf.exe")
            self._write_exe_path_to_config("osf", exe_path)
            self._generate_mount_scripts_files(bin_dir, "osf")
            self._refresh_tool_paths()  # Refresh all tool paths
            
            QMessageBox.information(self, "Download Complete", f"Successfully downloaded to:\n{result_path}")
        else:
            QMessageBox.critical(self, "Download Failed", f"Error: {message}")

        self.active_download_row = None
        self._current_download_tool_name = None

    def _write_exe_path_to_config(self, exe_name, exe_path):
        """Write the executable path to config.json with the format {exe_name}_exe_path."""
        # Remove .exe extension if present for the config key
        tool_name_no_ext = exe_name.replace('.exe', '').lower()
        config_key = f"{tool_name_no_ext}_exe_path"
        
        if self.main_window and hasattr(self.main_window, 'config') and self.main_window.config:
            setattr(self.main_window.config, config_key, exe_path)
            self.config_changed.emit()
            logging.info(f"Wrote executable path to config: {config_key} = {exe_path}")
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
                # Handle portable executable
                if hasattr(self, 'active_download_row') and self.active_download_row:
                    self.active_download_row.path = result_path
                    
                    # Write the executable path to config.json
                    if hasattr(self, '_current_download_tool_name') and self._current_download_tool_name:
                        tool_name = self._current_download_tool_name
                        self._write_exe_path_to_config(tool_name, result_path)
                
                # Refresh all tool paths from bin directory after successful download
                self._refresh_tool_paths()
                    
                QMessageBox.information(self, "Download Complete", f"Successfully downloaded to:\n{result_path}")
        else:
            QMessageBox.critical(self, "Download Failed", f"Error: {message}")
            
        self.active_download_row = None
        if hasattr(self, '_current_download_tool_name'):
            self._current_download_tool_name = None
        if hasattr(self, '_current_download_tool_data'):
            self._current_download_tool_data = None
    
    def _handle_installer(self, installer_path, installed_path, silent_install):
        """Handle running an installer and tracking the installed executable."""
        try:
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
            logging.info(f"Running installer: {' '.join(cmd)}")
            
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
                        process.terminate()
                        QMessageBox.warning(self, "Installation Cancelled", "Installation was cancelled by user.")
                        return
                
                progress.close()
                
                if process.returncode != 0:
                    stderr = process.stderr.read().decode('utf-8', errors='ignore')
                    logging.error(f"Installer failed with code {process.returncode}: {stderr}")
                    QMessageBox.critical(
                        self, 
                        "Installation Failed",
                        f"Installer returned error code {process.returncode}\n\n"
                        f"You may need to run the installer manually:\n{installer_path}"
                    )
                    return
            else:
                # Run installer with UI (non-blocking)
                subprocess.Popen(cmd)
                
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
                
                # Check if installed executable exists
                if os.path.exists(expanded_path):
                    # Update the path row
                    if hasattr(self, 'active_download_row') and self.active_download_row:
                        self.active_download_row.path = expanded_path
                    
                    # Write to config
                    if hasattr(self, '_current_download_tool_name') and self._current_download_tool_name:
                        tool_name = self._current_download_tool_name
                        self._write_exe_path_to_config(tool_name, expanded_path)
                    
                    # Refresh tool paths
                    self._refresh_tool_paths()
                    
                    QMessageBox.information(
                        self,
                        "Installation Complete",
                        f"Tool installed successfully!\n\nInstalled to: {expanded_path}"
                    )
                else:
                    # Installed path not found - ask user to locate it
                    QMessageBox.warning(
                        self,
                        "Installed Path Not Found",
                        f"Expected installation path not found:\n{expanded_path}\n\n"
                        f"Please manually locate the installed executable."
                    )
                    
                    # Open file dialog to locate installed exe
                    file_path, _ = QFileDialog.getOpenFileName(
                        self,
                        "Locate Installed Executable",
                        "",
                        "Executables (*.exe);;All Files (*.*)"
                    )
                    
                    if file_path:
                        if hasattr(self, 'active_download_row') and self.active_download_row:
                            self.active_download_row.path = file_path
                        
                        if hasattr(self, '_current_download_tool_name') and self._current_download_tool_name:
                            tool_name = self._current_download_tool_name
                            self._write_exe_path_to_config(tool_name, file_path)
                        
                        self._refresh_tool_paths()
                        
                        QMessageBox.information(
                            self,
                            "Path Set",
                            f"Tool path set to:\n{file_path}"
                        )
            else:
                # No installed path specified - try to auto-detect
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
            logging.error(f"Error handling installer: {e}", exc_info=True)
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
            # Re-sync UI to show updated paths
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
        self.launch_sequence_list.addItems(["Cloud-Sync", "mount-disc", "Controller-Mapper", "Monitor-Config", "No-TB", "Pre1", "Pre2", "Pre3", "Borderless"])
        self.config_changed.emit()
        self._update_list_tooltips(self.launch_sequence_list)

    def _reset_exit_sequence(self):
        self.exit_sequence_list.clear()
        self.exit_sequence_list.addItems(["Post1", "Post2", "Post3", "Monitor-Config", "Taskbar", "Controller-Mapper", "Unmount-disc", "Cloud-Sync"])
        self.config_changed.emit()
        self._update_list_tooltips(self.exit_sequence_list)

    def _on_sequence_context_menu(self, pos, list_widget, sequence_type):
        item = list_widget.itemAt(pos)

        menu = QMenu(self)
        
        # Define full sets
        if sequence_type == "launch":
            full_set = ["Cloud-Sync", "mount-disc", "Kill-Game", "Kill-List", "Controller-Mapper", "Monitor-Config", "No-TB", "Pre1", "Pre2", "Pre3", "Borderless"]
        else:
            full_set = ["Post1", "Post2", "Post3", "Kill-Game", "Kill-List", "Monitor-Config", "Taskbar", "Controller-Mapper", "Borderless", "Unmount-disc", "Cloud-Sync"]
            
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

        self.run_as_admin_checkbox.setChecked(config.run_as_admin)
        self.use_kill_list_checkbox.setChecked(config.use_kill_list)
        self.hide_taskbar_checkbox.setChecked(config.hide_taskbar)
        self.terminate_bw_on_exit_checkbox.setChecked(config.terminate_borderless_on_exit)

        self.page_size_spin.setValue(config.editor_page_size)

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
                    else:
                        self.last_detected_tools[attr_name] = exe_name

        self.launch_sequence_list.clear()
        # Ensure new items are in the sequence (migration for existing configs)
        launch_seq = config.launch_sequence if config.launch_sequence else []
        if not launch_seq:
            # Use defaults for new configs
            launch_seq = ["Cloud-Sync", "mount-disc", "Controller-Mapper", "Monitor-Config", "No-TB", "Pre1", "Pre2", "Pre3", "Borderless"]
        else:
            # Migrate existing configs: add new items if missing
            if "Cloud-Sync" not in launch_seq:
                launch_seq.insert(0, "Cloud-Sync")
            if "mount-disc" not in launch_seq:
                # Insert after Cloud-Sync
                insert_pos = launch_seq.index("Cloud-Sync") + 1 if "Cloud-Sync" in launch_seq else 0
                launch_seq.insert(insert_pos, "mount-disc")
        
        self.launch_sequence_list.addItems(launch_seq)
        self._update_list_tooltips(self.launch_sequence_list)
        
        self.exit_sequence_list.clear()
        # Ensure new items are in the sequence (migration for existing configs)
        exit_seq = config.exit_sequence if config.exit_sequence else []
        if not exit_seq:
            # Use defaults for new configs
            exit_seq = ["Post1", "Post2", "Post3", "Monitor-Config", "Taskbar", "Controller-Mapper", "Unmount-disc", "Cloud-Sync"]
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
        
        self.exit_sequence_list.addItems(exit_seq)
        self._update_list_tooltips(self.exit_sequence_list)
        
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

        self.blockSignals(False)

    def sync_config_from_ui(self, config: AppConfig):
        config.source_dirs = [self.source_dirs_list.item(i).text() for i in range(self.source_dirs_list.count())]
        config.excluded_dirs = [self.excluded_dirs_list.item(i).text() for i in range(self.excluded_dirs_list.count())]
        config.game_managers_present = self.other_managers_combo.currentText()
        config.exclude_selected_manager_games = self.exclude_manager_checkbox.isChecked()
        config.logging_verbosity = self.logging_verbosity_combo.currentText()
        config.fuzzy_match_cutoff = self.fuzzy_match_spin.value()
        config.editor_page_size = self.page_size_spin.value()

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

    def _on_path_text_changed(self, config_key, new_path):
        """Updates options and arguments if the new path matches a known tool."""
        if not new_path:
            return

    def _sync_disc_unmount(self, mount_path):
        """Sync disc unmount path with disc mount path."""
        if not mount_path:
            return
        
        unmount_row = self.path_rows.get("disc_unmount_path")
        if unmount_row and unmount_row.combo:
            # Set the same executable for unmount
            unmount_row.combo.setCurrentText(mount_path)
            # Enable the unmount row if mount is set
            if unmount_row.enabled_cb:
                unmount_row.enabled_cb.setChecked(True)

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

    def _open_plugin_manager(self):
        """Open the Plugin Manager dialog"""
        from Python.ui.plugin_manager_dialog import PluginManagerDialog
        dialog = PluginManagerDialog(self)
        dialog.exec()
