import os
import json
import logging
from .. import constants

STEAM_FILTERED_TXT = "steam_filtered.txt"

class GameCacheManager:
    """Manages game title caches for Steam, GOG, and a combined index.

    The combined index is built from both Steam and GOG normalized indexes
    and is the primary lookup used by all matchers.
    """
    def __init__(self, main_window):
        self.main_window = main_window
        # Steam caches
        self.filtered_steam_cache = set()
        self.normalized_steam_index = {}
        self.filtered_cache_path = os.path.join(constants.APP_ROOT_DIR, STEAM_FILTERED_TXT)
        self.steam_index_path = os.path.join(constants.APP_ROOT_DIR, constants.NORMALIZED_STEAM_INDEX_CACHE)

        # GOG caches
        self.normalized_gog_index = {}
        self.gog_index_path = os.path.join(constants.APP_ROOT_DIR, constants.NORMALIZED_GOG_INDEX_CACHE)

        # Combined index (built on load)
        self.normalized_combined_index = {}
        self.combined_index_path = os.path.join(constants.APP_ROOT_DIR, constants.NORMALIZED_COMBINED_INDEX_CACHE)

    # ── Steam filtered list ────────────────────────────────────────

    def load_filtered_steam_cache(self):
        if not os.path.exists(self.filtered_cache_path):
            self.filtered_steam_cache = set()
            return
        with open(self.filtered_cache_path, 'r', encoding='utf-8') as f:
            self.filtered_steam_cache = {line.strip() for line in f}
        logging.info(f"Loaded {len(self.filtered_steam_cache)} entries from filtered Steam cache.")

    def save_filtered_steam_cache(self, filtered_list):
        try:
            with open(self.filtered_cache_path, 'w', encoding='utf-8') as f:
                for item in sorted(filtered_list):
                    f.write(f"{item}\n")
            logging.info(f"Saved {len(filtered_list)} entries to {STEAM_FILTERED_TXT}")
            self.filtered_steam_cache = set(filtered_list)
        except IOError as e:
            logging.error(f"Error saving filtered steam cache: {e}")

    # ── Steam normalised index ─────────────────────────────────────

    def load_normalized_steam_index(self):
        if not os.path.exists(self.steam_index_path):
            self.normalized_steam_index = {}
            return
        with open(self.steam_index_path, 'r', encoding='utf-8') as f:
            self.normalized_steam_index = json.load(f)
        logging.info(f"Loaded {len(self.normalized_steam_index)} entries from normalized Steam index.")

    def save_normalized_steam_index(self, normalized_index):
        try:
            with open(self.steam_index_path, 'w', encoding='utf-8') as f:
                json.dump(normalized_index, f, indent=4)
            logging.info(f"Saved {len(normalized_index)} entries to normalized Steam index.")
            self.normalized_steam_index = normalized_index
        except IOError as e:
            logging.error(f"Error saving normalized Steam index: {e}")

    # ── GOG normalised index ───────────────────────────────────────

    def load_normalized_gog_index(self):
        if not os.path.exists(self.gog_index_path):
            self.normalized_gog_index = {}
            return
        with open(self.gog_index_path, 'r', encoding='utf-8') as f:
            self.normalized_gog_index = json.load(f)
        logging.info(f"Loaded {len(self.normalized_gog_index)} entries from normalized GOG index.")

    def save_normalized_gog_index(self, normalized_index):
        try:
            with open(self.gog_index_path, 'w', encoding='utf-8') as f:
                json.dump(normalized_index, f, indent=4)
            logging.info(f"Saved {len(normalized_index)} entries to normalized GOG index.")
            self.normalized_gog_index = normalized_index
        except IOError as e:
            logging.error(f"Error saving normalized GOG index: {e}")

    # ── Combined index (Steam + GOG) ───────────────────────────────

    def load_combined_index(self):
        """Load and merge Steam + GOG indexes into a single lookup dict."""
        self.load_normalized_steam_index()
        self.load_normalized_gog_index()
        self._build_combined_index()
        self._save_combined_index()

    def _build_combined_index(self):
        """Merge Steam and GOG indexes; GOG entries with colliding keys
        are prefixed with 'gog_' to avoid Steam ID collisions."""
        combined = {}
        combined.update(self.normalized_steam_index)
        for key, val in self.normalized_gog_index.items():
            if key in combined:
                gog_key = f"gog_{key}"
                combined[gog_key] = val
            else:
                combined[key] = val
        self.normalized_combined_index = combined
        logging.info(
            f"Built combined game index: {len(self.normalized_steam_index)} Steam + "
            f"{len(self.normalized_gog_index)} GOG = {len(self.normalized_combined_index)} total."
        )

    def _save_combined_index(self):
        try:
            with open(self.combined_index_path, 'w', encoding='utf-8') as f:
                json.dump(self.normalized_combined_index, f, indent=4)
        except IOError as e:
            logging.error(f"Error saving combined game index: {e}")

    # ── Cache management ───────────────────────────────────────────

    def delete_cache_files(self):
        deleted_count = 0
        for path in [self.filtered_cache_path, self.steam_index_path,
                     self.gog_index_path, self.combined_index_path]:
            if os.path.exists(path):
                os.remove(path)
                deleted_count += 1
        self.main_window.statusBar().showMessage(f"{deleted_count} cache files deleted.", 3000)
        self.filtered_steam_cache.clear()
        self.normalized_steam_index.clear()
        self.normalized_gog_index.clear()
        self.normalized_combined_index.clear()

    # ── Convenience accessors ──────────────────────────────────────

    def get_game_name(self, app_id):
        """Look up a game name by app_id across Steam and GOG indexes."""
        if not app_id:
            return None
        app_id_str = str(app_id)
        for key, val in self.normalized_steam_index.items():
            if val.get("id") == app_id_str:
                return val
        for key, val in self.normalized_gog_index.items():
            if val.get("id") == app_id_str:
                return val
        return None
