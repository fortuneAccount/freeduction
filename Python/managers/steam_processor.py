import json
import logging
import re
import threading
from PyQt6.QtCore import QObject, pyqtSignal

def create_filtered_list(steam_data):
    """Filters the raw Steam data to get a simple list of names."""
    filtered_list = []
    for app in steam_data:
        if 'name' in app and app.get('name'):
            filtered_list.append(app['name'])
    return filtered_list

def _normalize_steam_name(name: str) -> str:
    """Normalizes a Steam name for matching."""
    if not name:
        return ""
    # 1. Remove non-alphanumeric characters except spaces
    result = re.sub(r'[^a-zA-Z0-9 ]', '', name)
    # 2. Remove common prefixes
    result = re.sub(r'^(?:the|a|an)\s+', '', result, flags=re.IGNORECASE)
    # 3. Remove all spaces
    result = result.replace(' ', '')
    # 4. Convert to lowercase
    return result.lower()

def create_normalized_index(steam_data):
    """Creates a normalized index (normalized_name: {id: appid, name: app_name}) from the raw Steam data."""
    normalized_index = {}
    for app in steam_data:
        app_id = app.get('appid') or app.get('steam_id')
        app_name = app.get('name')
        if app_id and app_name:
            match_name = _normalize_steam_name(app_name)
            if match_name:
                normalized_index[match_name] = {"id": str(app_id), "name": app_name}
    return normalized_index

class SteamProcessor(QObject):
    """Processes the downloaded Steam JSON data."""
    status_updated = pyqtSignal(str, int)
    processing_finished = pyqtSignal()

    def __init__(self, steam_cache_manager):
        super().__init__()
        self.steam_cache_manager = steam_cache_manager
        self.processing_thread = None

    def start_processing(self, file_path):
        """Starts the processing of the Steam JSON file in a separate thread."""
        self.processing_thread = threading.Thread(
            target=self._process_steam_data,
            args=(file_path,)
        )
        self.processing_thread.daemon = True
        self.processing_thread.start()

    def _process_steam_data(self, file_path):
        """The actual data processing logic."""
        try:
            self.status_updated.emit("Processing Steam data...", 0)
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            steam_apps = data.get("applist", {}).get("apps", []) if isinstance(data, dict) else data

            self.status_updated.emit("Creating filtered list...", 0)
            filtered_list = create_filtered_list(steam_apps)
            self.steam_cache_manager.save_filtered_steam_cache(filtered_list)

            self.status_updated.emit("Creating normalized index...", 0)
            normalized_index = create_normalized_index(steam_apps)
            self.steam_cache_manager.save_normalized_steam_index(normalized_index)

            self.status_updated.emit("Steam data processing complete.", 5000)
        except Exception as e:
            logging.error(f"Error processing Steam data: {e}")
            self.status_updated.emit(f"Error processing data: {e}", 5000)
        finally:
            self.processing_finished.emit()