from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTabWidget, QWidget, 
    QMessageBox, QFileDialog, QProgressDialog
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QIcon
import os
import shutil
from Python.ui.deployment_tab import DeploymentTab
from Python.ui.setup_tab import SetupTab
from Python.ui.steam_cache import SteamCacheManager, STEAM_FILTERED_TXT, NORMALIZED_INDEX_CACHE
from Python.ui.editor_tab import EditorTab
from Python.models import AppConfig
from Python.managers.config_manager import ConfigManager
from Python.managers.data_manager import DataManager
from Python.managers.steam_manager import SteamManager
from Python.managers.plugin_manager import PluginManager
from Python import constants
from Python.utils import format_bytes
import logging


class MainWindow(QMainWindow):
    def __init__(self):
        """Initialize the main window"""
        super().__init__()
        
        # Initialize managers
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load_config()

        self.indexing_cancelled = False
        self.data_manager = DataManager(self.config, self)
        self.steam_cache_manager = SteamCacheManager(self)
        self.steam_manager = SteamManager(self.steam_cache_manager)
        
        # Initialize plugin manager
        bin_dir = os.path.join(constants.APP_ROOT_DIR, 'bin')
        self.plugin_manager = PluginManager(bin_dir)
        self.plugin_manager.load_builtin_plugins()
        self.plugin_manager.scan_for_installed_tools()
        logging.info(f"Plugin system initialized with {self.plugin_manager.registry.get_plugin_count()} plugins")
        
        # Initialize creation controller
        self._setup_creation_controller()
        
        # Set up the UI, which now depends on some config values being pre-loaded
        self._setup_ui()
        
        self._connect_signals()
        
        # Sync the UI to reflect the loaded configuration
        self.sync_ui_from_config()
        
        # Show the window
        self.show()
        
        # Check if steam.json exists but caches don't - auto-process if needed
        self._check_and_process_steam_on_startup()

    def reset_configuration_to_defaults(self):
        """Handles the logic for resetting the app config to its default state."""
        self.config_manager.reset_to_defaults(self)
        QMessageBox.information(self, "Defaults Loaded", "Default configuration has been loaded and applied.")

    def _load_steam_cache(self):
        """Load Steam cache from files"""
        # Load filtered Steam cache
        self.steam_cache_manager.load_filtered_steam_cache()
        
        # Load normalized Steam index
        self.steam_cache_manager.load_normalized_steam_index()
        
    def _setup_ui(self):
        self.setWindowTitle("Game Environment Manager")
        self.setWindowIcon(QIcon(constants.APP_ICON))
        self.setGeometry(100, 100, 880, 500)  # Reduced from 950, 750 to 800, 600

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        # Create all tab widgets first
        self.setup_tab = SetupTab(self)
        self.deployment_tab = DeploymentTab(self)
        self.editor_tab = EditorTab(self)
        # Add tabs to the tab widget
        self.tabs.addTab(self.setup_tab, "   SETUP   ")
        self.tabs.addTab(self.deployment_tab, "DEPLOYMENT")
        self.tabs.addTab(self.editor_tab, "   EDITOR   ")

        # Highlight unpopulated items in deployment tab with red color
        self.deployment_tab.highlight_unpopulated_items(self)
        
        # Create status bar
        self.statusBar().showMessage("Ready")

    def _locate_and_exclude_manager_config(self):
        """Locate and exclude games from other managers' configurations"""
        from Python.ui.steam_utils import locate_and_exclude_manager_config
        locate_and_exclude_manager_config(self)
        
    def _on_clear_listview(self):
        """Clear the editor table"""
        self.editor_tab.clear_table()
        self.statusBar().showMessage("List view cleared", 3000)
    
    def _check_and_process_steam_on_startup(self):
        """Check if steam.json exists but caches don't, and auto-process if needed."""
        import os
        steam_json_path = constants.STEAM_JSON_FILE
        filtered_path = os.path.join(constants.APP_ROOT_DIR, "steam_filtered.txt")
        normalized_path = os.path.join(constants.APP_ROOT_DIR, "normalized_steam_games.cache")
        
        # If steam.json exists but caches don't, auto-process
        if os.path.exists(steam_json_path):
            if not os.path.exists(filtered_path) or not os.path.exists(normalized_path):
                self.statusBar().showMessage("Processing steam.json on startup...", 0)
                self.steam_manager.process_existing_json()

    def _connect_signals(self):
        """Connect signals from UI tabs and managers to slots."""
        # --- Manager Signals ---
        self.config_manager.status_updated.connect(self.statusBar().showMessage)
        self.data_manager.status_updated.connect(self.statusBar().showMessage)
        self.data_manager.status_updated.connect(self.deployment_tab.append_log_message)
        self.data_manager.index_data_loaded.connect(self.editor_tab.populate_from_data)

        self.steam_manager.status_updated.connect(self.statusBar().showMessage)
        self.steam_manager.status_updated.connect(self.deployment_tab.append_log_message)
        self.steam_manager.download_started.connect(self._disable_ui_for_long_process)
        self.steam_manager.download_finished.connect(self._enable_ui_after_long_process)
        self.steam_manager.processing_prompt_requested.connect(self._on_processing_prompt_requested)
        self.steam_manager.processing_started.connect(self._disable_ui_for_long_process)
        self.steam_manager.process_file_selection_requested.connect(self._on_process_file_selection_requested)
        self.steam_manager.processing_finished.connect(self._enable_ui_after_long_process)
        self.steam_manager.processing_finished.connect(self.deployment_tab.update_steam_status)

        # --- UI Signals ---
        self.setup_tab.config_changed.connect(self._sync_config_from_ui_and_save)
        self.setup_tab.config_changed.connect(self.editor_tab.update_from_config)
        # Update deployment tab overwrite boxes when specific settings change
        self.setup_tab.setting_changed.connect(lambda key: self.deployment_tab.update_overwrite_checkboxes(self.config, key))
        
        self.deployment_tab.config_changed.connect(self._sync_config_from_ui_and_save)
        self.deployment_tab.index_sources_requested.connect(self._on_index_sources_requested)
        self.deployment_tab.cancel_indexing_requested.connect(self._on_cancel_indexing_requested)
        self.deployment_tab.create_selected_requested.connect(self.on_create_button_clicked)
        self.deployment_tab.download_steam_json_requested.connect(self._on_download_steam_json_requested)
        self.deployment_tab.delete_steam_json_requested.connect(self._on_delete_steam_json_requested)
        self.deployment_tab.delete_steam_cache_requested.connect(self.steam_cache_manager.delete_cache_files)
        self.deployment_tab.process_steam_json_requested.connect(self._on_process_existing_json_requested)

        self.editor_tab.data_changed.connect(self.deployment_tab.update_create_button_count)
        self.editor_tab.save_index_requested.connect(self._on_save_index_requested)
        self.editor_tab.load_index_requested.connect(self._on_load_index_requested)
        self.editor_tab.delete_indexes_requested.connect(self._on_delete_indexes_requested)
        self.editor_tab.clear_view_requested.connect(self._on_clear_listview)

    @pyqtSlot()
    def _on_index_sources_requested(self):
        """Handle request to index sources."""
        self.deployment_tab.set_indexing_state(True)
        # Reset cancellation flag
        self.indexing_cancelled = False
        # Call data manager (assuming it runs synchronously or emits finished signal)
        self.data_manager.index_sources()
        self.deployment_tab.set_indexing_state(False)

    @pyqtSlot()
    def _on_cancel_indexing_requested(self):
        """Handle request to cancel indexing."""
        self.indexing_cancelled = True
        self.statusBar().showMessage("Cancelling indexing...", 3000)

    @pyqtSlot(int)
    def _on_download_steam_json_requested(self, version: int):
        """Handle request to download Steam JSON, with user confirmation."""
        if self.steam_manager.is_downloading:
            self.statusBar().showMessage("Download already in progress", 3000)
            return

        output_file = constants.STEAM_JSON_FILE
        if os.path.exists(output_file):
            reply = QMessageBox.question(self, "Confirm Overwrite",
                                         f"The file 'steam.json' already exists. Are you sure you want to download and replace it?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                         QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        
        self.steam_manager.download_steam_json(version)

    @pyqtSlot()
    def _on_delete_steam_json_requested(self):
        """Handle request to delete Steam JSON, with user confirmation."""
        reply = QMessageBox.question(self, "Delete Steam JSON", "Are you sure you want to delete steam.json?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.steam_manager.delete_steam_json()

    @pyqtSlot()
    def _on_process_existing_json_requested(self):
        """Handle request to process existing JSON, with user confirmation."""
        filtered_cache = os.path.join(constants.APP_ROOT_DIR, STEAM_FILTERED_TXT)
        normalized_cache = os.path.join(constants.APP_ROOT_DIR, NORMALIZED_INDEX_CACHE)
        
        if os.path.exists(filtered_cache) or os.path.exists(normalized_cache):
            reply = QMessageBox.question(
                self, "Confirm Processing",
                "This will overwrite/delete existing Steam cache files. Are you sure you want to proceed?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return
        
        self.steam_manager.process_existing_json()

    @pyqtSlot(str)
    def _on_processing_prompt_requested(self, file_path: str):
        """Auto-process newly downloaded Steam JSON file."""
        # Auto-process without prompting
        self.steam_manager.prompt_and_process_steam_json(file_path)
        # Update deployment tab status after processing starts
        self.deployment_tab.update_steam_status()

    @pyqtSlot()
    def _on_process_file_selection_requested(self):
        """Show file dialog to select a JSON file for processing."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Steam JSON file", constants.APP_ROOT_DIR, "JSON Files (*.json)"
        )
        if file_path:
            # Now call the manager's method with the file path
            self.steam_manager.prompt_and_process_steam_json(file_path)

    def _disable_ui_for_long_process(self):
        """Disable UI elements during a long process."""
        self.tabs.setEnabled(False)

    def _enable_ui_after_long_process(self):
        """Re-enable UI elements after a long process."""
        self.tabs.setEnabled(True)
        
    def _regenerate_all_names(self):
        """Regenerate all name overrides in the table"""
        from Python.ui.name_processor import regenerate_all_names
        regenerate_all_names(self)
        self.statusBar().showMessage("All names regenerated", 3000)
        
    def _on_editor_table_edited(self, item):
        """Called when the editor table is edited"""
        # Save the editor table data to the index file
        self._save_editor_table_to_index()
        
        # Update the status bar
        self.statusBar().showMessage("Editor table updated and saved", 3000)
    
    def _on_editor_table_cell_left_click(self, row, column):
        """Called when a cell in the editor table is left-clicked"""
        # This method can be used to handle cell click events
        # Currently just a placeholder for future functionality
        pass

    def _save_editor_table_to_index(self):
        """Saves the current editor table to the default index file."""
        file_path = os.path.join(constants.APP_ROOT_DIR, "current.index")
        data = self.editor_tab.get_all_game_data()
        self.data_manager.save_editor_table_to_index(data, file_path)

    @pyqtSlot()
    def _on_load_index_requested(self):
        """Handle request to load an index file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Load Index File", constants.APP_ROOT_DIR, "Index Files (*.index)"
        )
        if file_path:
            self.data_manager.load_index(file_path)

    @pyqtSlot()
    def _on_save_index_requested(self):
        """Handle request to save the editor table to an index file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Index File", constants.APP_ROOT_DIR, "Index Files (*.index)"
        )
        if file_path:
            if not file_path.endswith(".index"):
                file_path += ".index"
            data = self.editor_tab.get_all_game_data()
            self.data_manager.save_editor_table_to_index(data, file_path)

    @pyqtSlot()
    def _on_delete_indexes_requested(self):
        """Handle request to delete index files, with user confirmation."""
        reply = QMessageBox.question(self, "Confirm Delete", "Are you sure you want to delete all index files?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.data_manager.delete_indexes()


    def _setup_creation_controller(self):
        """Initialize the creation controller"""
        from Python.ui.creation.creation_controller import CreationController
        self.creation_controller = CreationController(self)

    @pyqtSlot(str)
    def _on_logging_verbosity_changed(self, level_text):
        """Update the application's logging level based on the dropdown selection."""
        level_map = {
            "None": logging.CRITICAL + 1,  # A level higher than critical to disable most logging
            "Low": logging.WARNING,
            "Medium": logging.INFO,
            "High": logging.DEBUG,
            "Debug": logging.DEBUG
        }
        
        # Get the corresponding logging level, default to INFO
        log_level = level_map.get(level_text, logging.INFO)
        
        # Get the root logger and set its level
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        
        # Log the change itself for confirmation
        logging.warning(f"Logging level changed to: {level_text} ({log_level})")
        self.statusBar().showMessage(f"Logging level set to {level_text}", 3000)

        # Update the model and save the configuration
        self.config.logging_verbosity = level_text
        self.config_manager.save_config(self.config)

    def sync_ui_from_config(self):
        """Updates the UI widgets with values from the AppConfig model."""
        self.setup_tab.sync_ui_from_config(self.config)
        self.deployment_tab.sync_ui_from_config(self.config)

    @pyqtSlot()
    def _sync_config_from_ui_and_save(self):
        """Updates the AppConfig model from the UI and saves it to disk."""
        self.setup_tab.sync_config_from_ui(self.config)
        self.deployment_tab.sync_config_from_ui(self.config)
                
        self.config_manager.save_config(self.config)

    def on_create_button_clicked(self):
        """Handle the Create button click"""
        # Get all game data and filter for items marked 'create'
        all_games = self.editor_tab.get_all_game_data()
        games_to_process = [g for g in all_games if g.get('create')]
        
        if not games_to_process:
            QMessageBox.warning(self, "No Games to Create", "Please mark at least one game with 'Create' in the Editor tab.")
            return
        
        # Validation Step
        missing_items = self.creation_controller.validate_prerequisites(games_to_process)
        if missing_items:
            msg = "The following referenced files are missing:\n\n"
            # Limit to first 10 items to avoid huge dialog
            for item in missing_items[:10]:
                msg += f"- {item}\n"
            if len(missing_items) > 10:
                msg += f"... and {len(missing_items) - 10} more.\n"
            msg += "\nDo you want to proceed anyway?"
            
            reply = QMessageBox.warning(self, "Missing Files Detected", msg, 
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, 
                                        QMessageBox.StandardButton.No)
            if reply != QMessageBox.StandardButton.Yes:
                return

        # --- Statistics Calculation ---
        create_count = len(games_to_process)
        
        # 1. Duplicates
        name_counts = {}
        for g in games_to_process:
            name = g.get('name_override', '')
            name_counts[name] = name_counts.get(name, 0) + 1
        duplicate_count = sum(1 for g in games_to_process if name_counts.get(g.get('name_override', ''), 0) > 1)
        
        # 2. Empty Steam ID
        empty_steam_id_count = sum(1 for g in games_to_process if not g.get('steam_id') or str(g.get('steam_id')) == 'NOT_FOUND_IN_DATA')
        
        # 3. Launchers/Profiles Status
        def get_status_html(name, enabled_key, overwrite_key):
            enabled = self.config.defaults.get(enabled_key, True)
            overwrite = self.config.overwrite_states.get(overwrite_key, True)
            status_str = f"Create: {enabled}, Overwrite: {overwrite}"
            if not enabled or not overwrite:
                return f"<b>{name}: {status_str}</b>"
            return f"{name}: {status_str}"

        launchers_status = get_status_html("Launchers", "launchers_dir_enabled", "launchers_dir")
        profiles_status = get_status_html("Profiles", "profiles_dir_enabled", "profiles_dir")
        
        # 4. File Size Calculation
        lc_unchecked_size = 0
        lc_overwrite_size = 0
        
        file_keys = [
            "launcher_executable",
            "controller_mapper_path", "borderless_gaming_path", "multi_monitor_tool_path",
            "just_after_launch_path", "just_before_exit_path",
            "p1_profile_path", "p2_profile_path", "mediacenter_profile_path",
            "multimonitor_gaming_path", "multimonitor_media_path",
            "pre1_path", "post1_path", "pre2_path", "post2_path", "pre3_path", "post3_path"
        ]
        
        for key in file_keys:
            mode = self.config.deployment_path_modes.get(key, "CEN")
            if mode == "LC":
                path = getattr(self.config, key, "")
                if path and os.path.exists(path) and os.path.isfile(path):
                    size = os.path.getsize(path)
                    overwrite = self.config.overwrite_states.get(key, True)
                    if not overwrite:
                        lc_unchecked_size += size
                    else:
                        lc_overwrite_size += size

        # Count existing profiles
        existing_profiles_count = 0
        from Python.ui.name_utils import make_safe_filename
        for g in games_to_process:
            safe_name = make_safe_filename(g.get('name_override', '') or g.get('name', ''))
            profile_path = os.path.join(self.config.profiles_dir, safe_name)
            if os.path.exists(profile_path):
                existing_profiles_count += 1
        
        new_profiles_count = max(0, create_count - existing_profiles_count)
        total_bytes = (lc_unchecked_size * new_profiles_count) + (lc_overwrite_size * create_count)
        
        total_size_str = format_bytes(total_bytes)

        # Construct Message
        msg_text = (
            f"<h3>Creation Summary</h3>"
            f"Items to be created: <b>{create_count}</b><br>"
            f"Duplicate Name-Overrides: <b>{duplicate_count}</b><br>"
            f"Titles with Empty Steam ID: <b>{empty_steam_id_count}</b><br>"
            f"<br>"
            f"{launchers_status}<br>"
            f"{profiles_status}<br>"
            f"<br>"
            f"Estimated Total File Copy Size: <b>{total_size_str}</b><br>"
            f"<br>"
            f"Proceed with creation?"
        )
        
        reply = QMessageBox.question(self, "Confirm Creation", msg_text, QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if reply != QMessageBox.StandardButton.Yes:
            return

        # Create Progress Dialog
        progress = QProgressDialog("Creating launchers...", "Cancel", 0, create_count, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        
        def update_progress(current, _, game_name):
            if progress.wasCanceled():
                return False
            self.deployment_tab.append_log_message(f"Creating launcher for: {game_name}")
            progress.setValue(current)
            progress.setLabelText(f"Creating launcher for: {game_name}")
            QApplication.processEvents()
            return True

        # Debug output to verify selected games
        print(f"Found {len(games_to_process)} games marked for creation")
        for i, game in enumerate(games_to_process):
            print(f"Game {i+1}: {game.get('name_override', '')}")
        
        # Call create_all with the selected games
        result = self.creation_controller.create_all(games_to_process, progress_callback=update_progress)
        
        progress.setValue(create_count)
        
        if progress.wasCanceled():
            self.statusBar().showMessage(f"Creation cancelled. Processed: {result['processed_count']}", 5000)
            self.deployment_tab.append_log_message(f"Creation cancelled. Processed: {result['processed_count']}")
        else:
            self.statusBar().showMessage(f"Creation process finished. Processed: {result['processed_count']}, Failed: {result['failed_count']}", 5000)
            self.deployment_tab.append_log_message(f"Creation process finished. Processed: {result['processed_count']}, Failed: {result['failed_count']}")

    def _backup_steam_cache_files(self):
        """Backup Steam cache files before processing"""
        from Python.ui.steam_cache import STEAM_FILTERED_TXT, NORMALIZED_INDEX_CACHE
        
        cache_files = [
            os.path.join(constants.APP_ROOT_DIR, STEAM_FILTERED_TXT),
            os.path.join(constants.APP_ROOT_DIR, NORMALIZED_INDEX_CACHE)
        ]
        
        for cache_path in cache_files:
            if os.path.exists(cache_path):
                backup_path = cache_path + ".old"
                try:
                    if os.path.exists(backup_path):
                        os.remove(backup_path)
                    shutil.copy2(cache_path, backup_path)
                except OSError as e:
                    logging.warning(f"Failed to backup {cache_path}: {e}")
