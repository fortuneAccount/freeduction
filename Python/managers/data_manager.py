import os
import json
import logging
import difflib
from PyQt6.QtCore import QObject, pyqtSignal, Qt
from PyQt6.QtWidgets import QProgressDialog, QApplication

from .. import constants
from ..models import AppConfig
from ..managers.game_indexer import GameIndexer
from ..ui.name_processor import NameProcessor


class DataManager(QObject):
    """Manages loading, saving, and indexing of game data."""
    status_updated = pyqtSignal(str, int)
    index_data_loaded = pyqtSignal(list)

    def __init__(self, config: AppConfig, main_window):
        super().__init__()
        self.config = config
        self.main_window = main_window

    def _load_set_file(self, filename):
        """Loads a .set file into a set of strings from the assets directory."""
        result = set()
        file_path = os.path.join(constants.ASSETS_DIR, filename)
        if not os.path.exists(file_path):
            logging.warning(f"Set file not found: {file_path}")
            return result
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                for line in f:
                    line = line.strip().lower()
                    if line and not line.startswith('#'):
                        result.add(line)
        except Exception as e:
            logging.error(f"Failed to load set file {filename}: {e}")
        return result

    def _perform_fuzzy_steam_matching(self, games):
        """
        Performs fuzzy matching for games without a valid Steam ID and stores the results.
        """
        if not self.config.enable_name_matching:
            return

        logging.info("Performing fuzzy Steam ID matching for entries without an AppID...")
        steam_index = self.main_window.steam_cache_manager.normalized_steam_index
        if not steam_index:
            logging.warning("Normalized Steam index not available for fuzzy matching.")
            return

        # Initialize NameProcessor
        release_groups = getattr(self.main_window, 'release_groups_set', set())
        exclude_exe = getattr(self.main_window, 'exclude_exe_set', set())
        name_processor = NameProcessor(release_groups, exclude_exe)
        
        all_keys = list(steam_index.keys())
        
        for game in games:
            steam_id = str(game.get('steam_id', ''))
            if not steam_id or steam_id == 'NOT_FOUND_IN_DATA':
                name_to_use = game.get('name_override') or game.get('name')
                if not name_to_use:
                    continue
                
                match_name = name_processor.get_match_name(name_to_use)
                cutoff = getattr(self.config, 'fuzzy_match_cutoff', 0.6)
                matches = difflib.get_close_matches(match_name, all_keys, n=5, cutoff=cutoff)
                if matches:
                    game['_fuzzy_matches'] = matches
                    logging.debug(f"Found fuzzy matches for '{name_to_use}': {matches}")

    def index_sources(self):
        """
        Scans source directories for games and emits the data for the UI.
        """
        self.status_updated.emit("Indexing game sources...", 0)
        logging.info("Starting to index game sources.")
        
        # Ensure Steam cache is loaded for matching
        if not self.main_window.steam_cache_manager.normalized_steam_index:
            self.main_window.steam_cache_manager.load_normalized_steam_index()

        # Reset the cancellation flag
        self.main_window.indexing_cancelled = False
        
        # Initialize a set to track processed paths for this session
        self.main_window.processed_paths = set()

        def update_progress(path):
            if self.config.logging_verbosity == "Debug":
                self.status_updated.emit(f"[t] scanning: {path}", 0)
            QApplication.processEvents()

        def item_found(game_data):
            path = os.path.join(game_data.get('directory', ''), game_data.get('name', ''))
            self.status_updated.emit(f"[t] added: {path}", 0)

        try:
            # Load necessary data sets for the indexer
            self.main_window.exclude_exe_set = self._load_set_file("exclude_exe.set")
            self.main_window.folder_exclude_set = self._load_set_file("folder_exclude.set")
            self.main_window.demoted_set = self._load_set_file("demoted.set")
            self.main_window.folder_demoted_set = self._load_set_file("folder_demoted.set")
            self.main_window.release_groups_set = self._load_set_file("release_groups.set")

            # Call the refactored, UI-agnostic indexer
            indexer = GameIndexer(self.config, self.main_window)
            found_games = indexer.index_sources(progress_callback=update_progress, item_found_callback=item_found)

            if self.main_window.indexing_cancelled:
                logging.info("Indexing was cancelled by the user.")
                self.status_updated.emit("Indexing cancelled.", 3000)
                # Emit empty list to clear the view if cancelled
                self.index_data_loaded.emit([])
            else:
                # After indexing, perform fuzzy matching for games without a Steam ID
                if found_games:
                    self._perform_fuzzy_steam_matching(found_games)

                logging.info(f"Indexing complete. Found {len(found_games)} games.")
                self.status_updated.emit(f"Found {len(found_games)} games.", 3000)
                self.index_data_loaded.emit(found_games)

                # Automatically save the index file
                if found_games:
                    index_file_path = os.path.join(constants.APP_ROOT_DIR, "current.index")
                    self.save_editor_table_to_index(found_games, index_file_path)

                # --- Generate and Log Summary ---
                # 1. Identical Name Overrides
                name_counts = {}
                for g in found_games:
                    name = g.get('name_override', '')
                    name_counts[name] = name_counts.get(name, 0) + 1
                
                duplicate_files_count = sum(count for name, count in name_counts.items() if count > 1)
                
                # 2. Missing Steam IDs
                missing_steam_id_count = sum(1 for g in found_games if not g.get('steam_id') or g.get('steam_id') == 'NOT_FOUND_IN_DATA')
                
                # 3. Demoted Items (Create = False)
                demoted_count = sum(1 for g in found_games if not g.get('create', False))
                
                # 3. Large LC Files (>5MB) set to create
                large_lc_count = 0
                large_lc_details = []
                path_keys = [
                    'controller_mapper_path', 'borderless_windowing_path', 'multi_monitor_app_path',
                    'just_after_launch_path', 'just_before_exit_path',
                    'pre1_path', 'pre2_path', 'pre3_path',
                    'post1_path', 'post2_path', 'post3_path',
                    'launcher_executable'
                ]
                
                for g in found_games:
                    if g.get('create', False):
                        for key in path_keys:
                            mode = self.config.deployment_path_modes.get(key, 'CEN')
                            if mode == 'LC':
                                path = g.get(key, '')
                                if path and os.path.exists(path):
                                    try:
                                        if os.path.getsize(path) > 5 * 1024 * 1024:
                                            large_lc_count += 1
                                    except: pass

                separator = "_" * 50
                self.status_updated.emit(f"\n{separator}\n{separator}\n{separator}", 0)
                self.status_updated.emit(f"Indexing Summary:", 0)
                self.status_updated.emit(f"  - Files with identical Name Overrides: {duplicate_files_count}", 0)
                self.status_updated.emit(f"  - Files without Steam ID: {missing_steam_id_count}", 0)
                self.status_updated.emit(f"  - Demoted items (Create=False): {demoted_count}", 0)
                
                if large_lc_count > 0:
                    self.status_updated.emit(f"  - WARNING: {large_lc_count} items > 5MB are set to LC and Create.", 0)

        except Exception as e:
            logging.error(f"Error during indexing: {e}", exc_info=True)
            self.status_updated.emit(f"Error during indexing: {e}", 5000)

    def load_index(self, file_path):
        """Loads game data from a .index file."""
        # Ensure Steam cache is loaded for matching/display purposes
        if not self.main_window.steam_cache_manager.normalized_steam_index:
            self.main_window.steam_cache_manager.load_normalized_steam_index()
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                games_data = json.load(f)
            
            # Sanitize loaded data - clear paths for disabled items
            games_data = self._sanitize_game_data(games_data)
            
            self.index_data_loaded.emit(games_data)
            self.status_updated.emit(f"Loaded {len(games_data)} games from {os.path.basename(file_path)}", 3000)
        except Exception as e:
            logging.error(f"Failed to load index file {file_path}: {e}")
            self.status_updated.emit(f"Failed to load index file: {e}", 5000)
    
    def _sanitize_game_data(self, games_data):
        """Sanitize game data by clearing paths for disabled items."""
        import copy
        sanitized_data = copy.deepcopy(games_data)
        
        # Define path fields and their corresponding enabled flags
        path_enabled_pairs = [
            ('controller_mapper_path', 'controller_mapper_enabled'),
            ('borderless_windowing_path', 'borderless_windowing_enabled'),
            ('multi_monitor_app_path', 'multi_monitor_app_enabled'),
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
            ('mediacenter_profile', 'mediacenter_profile_enabled'),
            ('mm_game_profile', 'mm_game_profile_enabled'),
            ('mm_desktop_profile', 'mm_desktop_profile_enabled'),
            ('launcher_executable', 'launcher_executable_enabled'),
            ('disc_mount_path', 'disc_mount_enabled'),
            ('disc_unmount_path', 'disc_unmount_enabled'),
            ('cloud_app_path', 'cloud_app_enabled'),
            ('backup_app_path', 'backup_app_enabled'),
        ]
        
        # Sanitize each game's data
        for game in sanitized_data:
            for path_key, enabled_key in path_enabled_pairs:
                # If the enabled flag is False, clear the path
                if not game.get(enabled_key, True):
                    game[path_key] = ""
        
        return sanitized_data

    def save_editor_table_to_index(self, data, file_path):
        """Saves the current editor table data to a .index file."""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            self.status_updated.emit(f"Saved {len(data)} games to {os.path.basename(file_path)}", 3000)
        except Exception as e:
            logging.error(f"Failed to save index file {file_path}: {e}")
            self.status_updated.emit(f"Failed to save index file: {e}", 5000)

    def delete_indexes(self):
        """Deletes all .index files in the application root directory."""
        deleted_count = 0
        try:
            for item in os.listdir(constants.APP_ROOT_DIR):
                if item.endswith(".index"):
                    file_path = os.path.join(constants.APP_ROOT_DIR, item)
                    try:
                        os.remove(file_path)
                        deleted_count += 1
                        logging.info(f"Deleted index file: {file_path}")
                    except OSError as e:
                        logging.error(f"Error deleting index file {file_path}: {e}")
            if deleted_count > 0:
                self.status_updated.emit(f"Deleted {deleted_count} index files.", 3000)
                self.index_data_loaded.emit([]) # Clear the editor view
            else:
                self.status_updated.emit("No index files found to delete.", 3000)
        except Exception as e:
            logging.error(f"Error accessing application root directory: {e}")
            self.status_updated.emit("Error deleting index files.", 5000)