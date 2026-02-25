from __future__ import annotations
import os
import shutil
import time
import threading
import logging
from typing import TYPE_CHECKING
import requests
from PyQt6.QtCore import QObject, pyqtSignal
from .. import constants

if TYPE_CHECKING:
    from ..ui.steam_cache import SteamCacheManager

class SteamManager(QObject):
    """Manages Steam data operations like downloading and processing JSON."""
    status_updated = pyqtSignal(str, int)
    download_started = pyqtSignal()
    download_finished = pyqtSignal(bool, str) # success, file_path
    processing_prompt_requested = pyqtSignal(str)
    processing_started = pyqtSignal()
    process_file_selection_requested = pyqtSignal()
    processing_finished = pyqtSignal()

    def __init__(self, steam_cache_manager: SteamCacheManager):
        super().__init__()
        self.steam_cache_manager = steam_cache_manager
        self.download_thread = None
        self.is_downloading = False

    def download_steam_json(self, version=2):
        """Download the Steam JSON file with progress tracking."""
        output_file = constants.STEAM_JSON_FILE

        url = None
        repos_file = constants.REPOS_SET
        try:
            if os.path.exists(repos_file):
                with open(repos_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if version == 1 and "STEAMJSON1" in line:
                            url = line.split("=")[1].strip()
                            break
                        elif version == 2 and "STEAMJSON2" in line:
                            url = line.split("=")[1].strip()
                            break
        except Exception as e:
            logging.error(f"Could not read repos.set file: {e}")

        if not url:
            url = f"http://api.steampowered.com/ISteamApps/GetAppList/v{version}/?format=json"

        if os.path.exists(output_file):
            backup_file = output_file + ".old"
            if os.path.exists(backup_file):
                os.remove(backup_file)
            shutil.copy2(output_file, backup_file)
            logging.info(f"Backed up existing '{os.path.basename(output_file)}' to '{os.path.basename(backup_file)}'")

        # Signal UI to disable elements
        self.download_started.emit()

        # Start download in a separate thread
        self.download_thread = threading.Thread(
            target=self._download_with_progress,
            args=(url, output_file, version)
        )
        self.download_thread.daemon = True
        self.download_thread.start()

    def _download_with_progress(self, url, output_file, version):
        """Download file with progress tracking and rate-limit handling."""
        self.is_downloading = True
        success = False
        start_time = time.time()
        max_retries = 5
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
                with requests.get(url, headers=headers, stream=True, timeout=30) as r:
                    if r.status_code == 429:  # Too Many Requests
                        retry_after = int(r.headers.get("Retry-After", retry_delay))
                        self.status_updated.emit(f"Rate limited by Steam API. Retrying in {retry_after} seconds...", 0)
                        time.sleep(retry_after)
                        retry_delay *= 2
                        continue

                    r.raise_for_status()
                    total_size = int(r.headers.get('content-length', 0))
                    downloaded = 0

                    with open(output_file, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            if not chunk: break
                            f.write(chunk)
                            downloaded += len(chunk)
                            if total_size > 0:
                                percent = min(100, (downloaded * 100) / total_size)
                                elapsed_time = time.time() - start_time
                                speed = downloaded / elapsed_time if elapsed_time > 0 else 0
                                speed_mb = speed / (1024 * 1024)
                                remaining = total_size - downloaded
                                eta_seconds = remaining / speed if speed > 0 else 0
                                eta_str = self._format_eta(eta_seconds)
                                progress_text = f"Downloading Steam JSON (v{version}): {percent:.1f}% | {speed_mb:.2f} MB/s | ETA: {eta_str}"
                            else:
                                downloaded_mb = downloaded / (1024 * 1024)
                                progress_text = f"Downloading Steam JSON (v{version}): {downloaded_mb:.2f} MB"
                            self.status_updated.emit(progress_text, 0)

                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        self.status_updated.emit(f"Steam JSON (v{version}) downloaded successfully", 5000)
                        success = True
                        self.processing_prompt_requested.emit(output_file)
                    else:
                        self.status_updated.emit(f"Failed to download Steam JSON (v{version})", 5000)
                    break  # Success, break from retry loop

            except requests.exceptions.RequestException as e:
                self.status_updated.emit(f"Network error downloading Steam JSON: {e}", 5000)
                if attempt < max_retries - 1:
                    self.status_updated.emit(f"Retrying in {retry_delay} seconds...", 0)
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.status_updated.emit("Download failed after multiple retries.", 5000)
            except Exception as e:
                self.status_updated.emit(f"Error downloading Steam JSON: {e}", 5000)
                break
        else:
            self.is_downloading = False
            self.download_finished.emit(success, output_file)

    def _format_eta(self, seconds):
        """Format ETA in human readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int((seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def prompt_and_process_steam_json(self, file_path=None):
        """Prompt the user to select a Steam JSON file and process it."""
        from .steam_processor import SteamProcessor
        
        if not hasattr(self, 'steam_processor'):
            self.steam_processor = SteamProcessor(self.steam_cache_manager)
            # Connect signals from the processor
            self.steam_processor.status_updated.connect(self.status_updated)
            self.steam_processor.processing_finished.connect(self.processing_finished)

        if file_path:
            self.processing_started.emit()
            self.steam_processor.start_processing(file_path)
        else:
            # Request the UI to open a file dialog
            self.process_file_selection_requested.emit()

    def delete_steam_json(self):
        """Delete the Steam JSON file."""
        if os.path.exists(constants.STEAM_JSON_FILE):
            os.remove(constants.STEAM_JSON_FILE)
            self.status_updated.emit("Steam JSON file deleted", 3000)

    def process_existing_json(self):
        """Process the existing steam.json file."""
        steam_json_path = constants.STEAM_JSON_FILE
        if not os.path.exists(steam_json_path):
            self.status_updated.emit("steam.json not found.", 5000)
            return
        self.prompt_and_process_steam_json(steam_json_path)