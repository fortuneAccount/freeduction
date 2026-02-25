import os
import logging
from PyQt6.QtWidgets import QApplication
from Python.ui.name_processor import NameProcessor
from Python.ui.game_indexer import _process_executable

class GameIndexer:
    def __init__(self, config, main_window):
        self.config = config
        self.main_window = main_window

    def index_sources(self, progress_callback=None, item_found_callback=None):
        """
        Scans configured source directories for games.
        Checks for cancellation requests during the process.
        """
        logging.info("Starting source indexing...")
        indexed_games = []
        
        # Initialize NameProcessor with exclusion sets loaded in main_window
        name_processor = NameProcessor(
            release_groups_set=getattr(self.main_window, 'release_groups_set', set()),
            exclude_exe_set=getattr(self.main_window, 'exclude_exe_set', set())
        )
        
        # Track processed paths to prevent duplicates across source directories
        processed_paths = set()
        if hasattr(self.main_window, 'processed_paths'):
             self.main_window.processed_paths = processed_paths

        # Iterate through configured source directories
        for source_dir in self.config.source_dirs:
            # Check for cancellation before starting a directory
            if getattr(self.main_window, 'indexing_cancelled', False):
                logging.info("Indexing cancelled by user.")
                break

            if not os.path.exists(source_dir):
                continue

            # Walk the directory structure
            for root, dirs, files in os.walk(source_dir):
                # Check for cancellation inside the loop
                if getattr(self.main_window, 'indexing_cancelled', False):
                    logging.info("Indexing cancelled by user.")
                    return indexed_games
                
                # Update progress UI
                if progress_callback:
                    progress_callback(root)
                
                # Keep UI responsive
                QApplication.processEvents()
                
                # Check if this directory is excluded or is a subdirectory of an excluded directory
                root_normalized = os.path.normpath(root).lower()
                is_excluded = any(
                    root_normalized == os.path.normpath(excluded).lower() or
                    root_normalized.startswith(os.path.normpath(excluded).lower() + os.sep)
                    for excluded in self.config.excluded_dirs
                )
                if is_excluded:
                    # Skip this directory and all its subdirectories
                    dirs[:] = []  # Clear dirs list to prevent os.walk from descending
                    continue

                for filename in files:
                    if not filename.lower().endswith('.exe'):
                        continue

                    exec_full_path = os.path.join(root, filename)
                    exec_full_path_lower = exec_full_path.lower()
                    
                    # Skip if we've already processed this file (e.g. overlapping source dirs)
                    if exec_full_path_lower in processed_paths:
                        continue
                    processed_paths.add(exec_full_path_lower)

                    # Process the executable using the shared logic
                    game_data = _process_executable(
                        exec_full_path, self.main_window, name_processor
                    )

                    if game_data:
                        indexed_games.append(game_data)
                        if item_found_callback:
                            item_found_callback(game_data)
        
        logging.info("Indexing complete.")
        return indexed_games