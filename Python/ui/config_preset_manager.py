"""
config_preset_manager.py - Configuration preset management for freeduction.

This module centralises the logic for the Setup tab "Configuration Presets"
section:

  * Persisting the application root (``app_directory``) and the currently
    active json-config file (``current_settings``) into ``config.json``.
  * Maintaining a ``history`` section that records every json-config file the
    user has loaded or created, along with any presets bundled in the assets
    folder and a synthetic ``LOCAL`` preset holding the default application
    values (derived from ``${approot}/Python``).
  * Indexing directories (the application root plus the parent of every path in
    a user-supplied, pipe-delimited search string) for ``*.json`` config files.

The on-disk layout in ``config.json`` is::

    {
        "app_directory": "C:/.../freeduction",
        "current_settings": "C:/.../freeduction/config.json",
        "history": {
            "config": {
                "settings": [
                    "C:/.../freeduction/config.json",
                    "C:/.../freeduction/presets/my_preset.json"
                ]
            }
        }
    }

``LOCAL`` is a virtual preset (not a real file).  Its config data is generated
by :meth:`ConfigPresetManager.build_local_preset`.
"""

import os
import json
import logging
from pathlib import Path

from .. import constants
from ..models import AppConfig
from ..managers.config_manager import ConfigManager


# Marker used as the combobox "data" for the synthetic LOCAL preset.
LOCAL_PRESET_MARKER = "__LOCAL__"

# File name fragment used to recognise the primary application config file.
DEFAULT_CONFIG_FILENAME = "config"
DEFAULT_CONFIG_JSON = f"{DEFAULT_CONFIG_FILENAME}.json"

# Sub-folder (under APP_ROOT_DIR) where bundled preset configs live.
PRESETS_DIR = os.path.join(constants.APP_ROOT_DIR, "presets")


class ConfigPresetManager:
    """Loads, records and indexes json-config presets for the Setup tab."""

    def __init__(self, config: AppConfig, config_file: str):
        self.config = config
        self.config_file = config_file
        self._config_manager = ConfigManager()

    # ------------------------------------------------------------------
    # App root / active settings persistence
    # ------------------------------------------------------------------
    @property
    def app_directory(self) -> str:
        """The application root directory (${approot})."""
        return constants.APP_ROOT_DIR

    @property
    def default_settings_path(self) -> str:
        """The default startup config path: ${approot}/config.json."""
        return os.path.join(self.app_directory, DEFAULT_CONFIG_JSON)

    def current_settings_path(self) -> str:
        """Return the currently active json-config path.

        Falls back to the default ``${approot}/config.json`` when nothing has
        been recorded yet.
        """
        path = getattr(self.config, "current_settings", "")
        if not path:
            path = self.default_settings_path
        return path

    # ------------------------------------------------------------------
    # History persistence
    # ------------------------------------------------------------------
    def _read_raw(self) -> dict:
        """Read config.json as a raw dict (or an empty dict if missing)."""
        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}

    def _write_raw(self, data: dict):
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
        except Exception as e:
            logging.error(f"Failed to write history to {self.config_file}: {e}")

    def get_history(self) -> list:
        """Return the ordered list of recorded json-config file paths."""
        raw = self._read_raw()
        history = raw.get("history", {})
        settings = history.get("config", {}).get("settings", [])
        if not isinstance(settings, list):
            settings = []
        # De-duplicate while preserving order.
        seen, out = set(), []
        for p in settings:
            norm = os.path.normpath(p)
            if norm not in seen:
                seen.add(norm)
                out.append(p)
        return out

    def add_to_history(self, path: str):
        """Record a json-config file path in the history section."""
        if not path:
            return
        raw = self._read_raw()
        history = raw.setdefault("history", {})
        config_block = history.setdefault("config", {})
        settings = config_block.get("settings", [])
        if not isinstance(settings, list):
            settings = []
        norm = os.path.normpath(path)
        settings = [p for p in settings if os.path.normpath(p) != norm]
        settings.append(path)
        config_block["settings"] = settings
        self._write_raw(raw)

    def remove_from_history(self, path: str):
        """Remove a json-config path from the history section."""
        if not path:
            return
        raw = self._read_raw()
        history = raw.get("history", {})
        config_block = history.get("config", {})
        settings = config_block.get("settings", [])
        if not isinstance(settings, list):
            return
        norm = os.path.normpath(path)
        config_block["settings"] = [p for p in settings if os.path.normpath(p) != norm]
        self._write_raw(raw)

    def reset_history(self):
        """Clear the recorded history of json-config files."""
        raw = self._read_raw()
        raw.pop("history", None)
        self._write_raw(raw)

    def set_current_settings(self, path: str):
        """Persist the supplied path as ``current_settings`` and in history."""
        self.config.current_settings = path
        self.add_to_history(path)
        raw = self._read_raw()
        raw["current_settings"] = path
        raw["app_directory"] = self.app_directory
        self._write_raw(raw)

    # ------------------------------------------------------------------
    # Preset generation
    # ------------------------------------------------------------------
    def build_local_preset(self) -> dict:
        """Build the ``LOCAL`` preset: default application values.

        The defaults are produced by a first-run setup, then any path that does
        not exist on disk is re-based onto ``${approot}/Python`` so the preset
        represents a portable, default state tied to the application's own
        Python directory.
        """
        default_cfg = self._config_manager._first_run_setup()
        data = {
            key: getattr(default_cfg, key)
            for key in dir(default_cfg)
            if not key.startswith("__") and not callable(getattr(default_cfg, key))
        }
        python_root = os.path.join(self.app_directory, "Python")
        for key, value in list(data.items()):
            if isinstance(value, str) and value and not os.path.isabs(value):
                data[key] = os.path.join(python_root, value)
        data["app_directory"] = self.app_directory
        data["current_settings"] = os.path.join(python_root, DEFAULT_CONFIG_JSON)
        return data

    def list_asset_presets(self) -> list:
        """Return paths of ``*.json`` preset files bundled in the presets dir."""
        presets = []
        if os.path.isdir(PRESETS_DIR):
            for name in sorted(os.listdir(PRESETS_DIR)):
                if name.lower().endswith(".json"):
                    presets.append(os.path.join(PRESETS_DIR, name))
        return presets

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------
    def resolve_search_roots(self, pipe_delimited: str) -> list:
        """Resolve the set of directories to index from a pipe-delimited string.

        Always includes the application root (``${approot}``).  For every path
        found in ``pipe_delimited`` (pipe ``|`` separated), its parent directory
        is also included.  Duplicate and non-existent roots are de-duplicated.
        """
        roots = []
        seen = set()

        def add(path):
            if not path:
                return
            norm = os.path.normpath(path)
            if norm not in seen:
                seen.add(norm)
                roots.append(norm)

        add(self.app_directory)
        for raw in (pipe_delimited or "").split("|"):
            p = raw.strip().strip('"').strip("'")
            if not p:
                continue
            add(p)
            parent = os.path.dirname(p)
            if parent:
                add(parent)
        return roots

    def index_json_configs(self, search_roots: list, max_depth: int = 3) -> list:
        """Recursively find ``*.json`` config files within the search roots.

        Skips obviously non-config json files (``steam.json``, cache/index
        files) and returns absolute paths sorted by name.
        """
        skip_names = {
            "steam.json", "package.json", "current.index",
            "normalized_steam_games.cache",
        }
        found = []
        seen = set()
        for root in search_roots:
            if not os.path.isdir(root):
                continue
            try:
                for dirpath, _dirnames, filenames in os.walk(root):
                    depth = dirpath[len(root):].count(os.sep)
                    if depth > max_depth:
                        continue
                    for fn in filenames:
                        low = fn.lower()
                        if not low.endswith(".json"):
                            continue
                        if fn in skip_names or low.endswith(".cache"):
                            continue
                        full = os.path.join(dirpath, fn)
                        norm = os.path.normpath(full)
                        if norm not in seen:
                            seen.add(norm)
                            found.append(full)
            except Exception as e:
                logging.warning(f"Indexing failed for {root}: {e}")
        return sorted(found, key=lambda p: os.path.basename(p).lower())

    # ------------------------------------------------------------------
    # Loading / saving config files
    # ------------------------------------------------------------------
    def load_json_config(self, path: str, mode: str = "overwrite") -> AppConfig:
        """Load settings from a json-config file into the AppConfig model.

        ``mode`` is either ``"overwrite"`` (replace current values) or
        ``"append"`` (only fill in missing/empty values).
        """
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if mode == "append":
            for key, value in data.items():
                if not hasattr(self.config, key):
                    setattr(self.config, key, value)
                    continue
                current = getattr(self.config, key, None)
                if current in (None, "", [], {}):
                    setattr(self.config, key, value)
        else:
            for key, value in data.items():
                setattr(self.config, key, value)
        return self.config

    def create_config_from_current(self, path: str) -> dict:
        """Write the current config model to ``path`` and return its data."""
        data = {
            key: getattr(self.config, key)
            for key in dir(self.config)
            if not key.startswith("__") and not callable(getattr(self.config, key))
        }
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        return data
