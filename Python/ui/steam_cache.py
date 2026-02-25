import os
import json
import logging
from .. import constants

STEAM_FILTERED_TXT = "steam_filtered.txt"
NORMALIZED_INDEX_CACHE = "normalized_steam_games.cache"

class SteamCacheManager:
    def __init__(self, main_window):
        self.main_window = main_window
        self.filtered_steam_cache = set()
        self.normalized_steam_index = {}
        self.filtered_cache_path = os.path.join(constants.APP_ROOT_DIR, STEAM_FILTERED_TXT)
        self.normalized_index_path = os.path.join(constants.APP_ROOT_DIR, NORMALIZED_INDEX_CACHE)

    def load_filtered_steam_cache(self):
        if not os.path.exists(self.filtered_cache_path):
            self.filtered_steam_cache = set()
            return
        with open(self.filtered_cache_path, 'r', encoding='utf-8') as f:
            self.filtered_steam_cache = {line.strip() for line in f}
        logging.info(f"Loaded {len(self.filtered_steam_cache)} entries from filtered Steam cache.")

    def load_normalized_steam_index(self):
        if not os.path.exists(self.normalized_index_path):
            self.normalized_steam_index = {}
            return
        with open(self.normalized_index_path, 'r', encoding='utf-8') as f:
            self.normalized_steam_index = json.load(f)
        logging.info(f"Loaded {len(self.normalized_steam_index)} entries from normalized Steam index.")

    def save_filtered_steam_cache(self, filtered_list):
        try:
            with open(self.filtered_cache_path, 'w', encoding='utf-8') as f:
                for item in sorted(filtered_list):
                    f.write(f"{item}\n")
            logging.info(f"Saved {len(filtered_list)} entries to {STEAM_FILTERED_TXT}")
            self.filtered_steam_cache = set(filtered_list)
        except IOError as e:
            logging.error(f"Error saving filtered steam cache: {e}")

    def save_normalized_steam_index(self, normalized_index):
        try:
            with open(self.normalized_index_path, 'w', encoding='utf-8') as f:
                json.dump(normalized_index, f, indent=4)
            logging.info(f"Saved {len(normalized_index)} entries to {NORMALIZED_INDEX_CACHE}")
            self.normalized_steam_index = normalized_index
        except IOError as e:
            logging.error(f"Error saving normalized steam index: {e}")

    def delete_cache_files(self):
        deleted_count = 0
        for path in [self.filtered_cache_path, self.normalized_index_path]:
            if os.path.exists(path):
                os.remove(path)
                deleted_count += 1
        self.main_window.statusBar().showMessage(f"{deleted_count} Steam cache files deleted.", 3000)
        self.filtered_steam_cache.clear()
        self.normalized_steam_index.clear()

    def get_game_name(self, app_id):
        return self.normalized_steam_index.get(str(app_id))