import configparser
import os
from pathlib import Path
import shutil
import logging
import requests
import json
import subprocess
import zipfile
import re
import random
import time

from Python import constants
from Python.managers.pcgw_manager import PCGWManager
from Python.ui.name_utils import make_safe_filename

class CreationController:
    """
    Handles the creation of launcher files, shortcuts, and Game.ini configurations.
    """
    def __init__(self, main_window):
        self.main_window = main_window
        self.repo_tools = self._parse_repos_set()
        self.pcgw_manager = PCGWManager()

    def create_all(self, selected_games, progress_callback=None):
        """
        Processes all selected games from the editor tab to create their launchers.
        """
        processed_count = 0
        failed_count = 0
        total_count = len(selected_games)

        for i, game_data in enumerate(selected_games):
            if progress_callback:
                game_name = game_data.get('name_override', 'New Game')
                if progress_callback(i, total_count, game_name) is False:
                    break
            if self._create_for_single_game(game_data):
                processed_count += 1
            else:
                failed_count += 1
        
        return {"processed_count": processed_count, "failed_count": failed_count}

    def validate_prerequisites(self, selected_games):
        """
        Checks if all referenced files (profiles, apps) exist for the selected games.
        Returns a list of missing file warnings.
        """
        missing_items = []
        checked_paths = {}

        def path_exists(p):
            if not p: return True
            if p in checked_paths: return checked_paths[p]
            exists = os.path.exists(p)
            checked_paths[p] = exists
            return exists

        for game in selected_games:
            game_name = game.get('name_override', 'Unknown')
            
            # 1. Profiles
            profile_keys = [
                ('player1_profile', 'Player 1 Profile'),
                ('player2_profile', 'Player 2 Profile'),
                ('mm_game_profile', 'MM Game Config'),
                ('mm_desktop_profile', 'MM Desktop Config'),
                ('mediacenter_profile', 'Media Center Profile')
            ]
            
            for key, label in profile_keys:
                # Check enabled key if it exists
                if not game.get(f"{key}_enabled", True): continue

                val = game.get(key, "")
                if not val: continue
                
                clean_path = val
                if val.startswith(('< ', '> ')):
                    clean_path = val[2:].strip()
                
                extra_context = {}
                if key == 'player1_profile':
                    extra_context['$player_number'] = '1'
                elif key == 'player2_profile':
                    extra_context['$player_number'] = '2'
                elif key == 'player3_profile':
                    extra_context['$player_number'] = '3'
                elif key == 'player4_profile':
                    extra_context['$player_number'] = '4'
            
                clean_path = self._transform_path(clean_path, game, extra_context)
                
                if clean_path and not path_exists(clean_path):
                    missing_items.append(f"Game '{game_name}': {label} missing ({clean_path})")

            # 2. Apps
            app_keys = [
                ('controller_mapper_path', 'Controller Mapper', 'controller_mapper_enabled'),
                ('borderless_windowing_path', 'Borderless Gaming', 'borderless_windowing_enabled'),
                ('multi_monitor_app_path', 'Multi-Monitor Tool', 'multi_monitor_app_enabled'),
                ('just_after_launch_path', 'Just After Launch', 'just_after_launch_enabled'),
                ('just_before_exit_path', 'Just Before Exit', 'just_before_exit_enabled'),
                ('pre1_path', 'Pre-Launch 1', 'pre_1_enabled'),
                ('pre2_path', 'Pre-Launch 2', 'pre_2_enabled'),
                ('pre3_path', 'Pre-Launch 3', 'pre_3_enabled'),
                ('post1_path', 'Post-Launch 1', 'post_1_enabled'),
                ('post2_path', 'Post-Launch 2', 'post_2_enabled'),
                ('post3_path', 'Post-Launch 3', 'post_3_enabled'),
            ]

            for key, label, enabled_key in app_keys:
                if not game.get(enabled_key, True):
                    continue
                
                val = game.get(key, "")
                if not val: continue
                
                clean_path = val.lstrip('<> ').strip()
                if not clean_path: continue
                
                clean_path = self._transform_path(clean_path, game)

                # If LC mode (starts with >), check if it's a repo tool
                if val.startswith('>'):
                    exe_name = os.path.basename(clean_path).lower()
                    if exe_name in self.repo_tools:
                        continue # Will be downloaded
                
                if not path_exists(clean_path):
                    missing_items.append(f"Game '{game_name}': {label} missing ({clean_path})")

        return missing_items

    def _transform_path(self, path, game_data, extra_context=None):
        """Transforms variables in the path string."""
        if not path:
            return path
            
        # Load mappings if not already loaded
        if not hasattr(self, 'var_mapping'):
            self.var_mapping = {}
            set_path = os.path.join(constants.ASSETS_DIR, "transformed_vars.set")
            if os.path.exists(set_path):
                try:
                    with open(set_path, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if '=' in line and not line.startswith('['):
                                k, v = line.split('=', 1)
                                self.var_mapping[k.strip()] = v.strip()
                except Exception as e:
                    logging.error(f"Error loading transformed_vars.set: {e}")

        # Prepare context variables
        safe_name = make_safe_filename(game_data.get('name_override', ''))
        if not safe_name:
             safe_name = make_safe_filename(game_data.get('name', 'Game'))

        context = {
            '$safe_game_name': safe_name,
            '$game_title': safe_name,
            '$APP_ROOT_DIR': constants.APP_ROOT_DIR,
            '$app_dir': constants.APP_ROOT_DIR,
            '$game_directory': game_data.get('directory', ''),
            '$game_executable': game_data.get('name', ''),
            '$steam_id': str(game_data.get('steam_id', ''))
        }

        if extra_context:
            context.update(extra_context)

        temp_path = path
        for k, v in self.var_mapping.items():
            if k in temp_path:
                temp_path = temp_path.replace(k, v)
        
        for k, v in context.items():
            if k in temp_path:
                temp_path = temp_path.replace(k, str(v))
                
        return temp_path

    def _resolve_mode(self, path_val, config_key):
        """
        Resolves the path and mode (CEN vs LC) based on prefix or config default.
        Returns (clean_path, mode_symbol) where mode_symbol is '<' or '>'.
        """
        if not path_val:
            return "", '<'
            
        if path_val.startswith('> '):
            return path_val[2:].strip(), '>'
        elif path_val.startswith('< '):
            return path_val[2:].strip(), '<'
            
        # Check config default
        if hasattr(self.main_window.config, 'deployment_path_modes'):
            mode_str = self.main_window.config.deployment_path_modes.get(config_key, 'CEN')
            return path_val, ('>' if mode_str != 'CEN' else '<')
            
        return path_val, '<'

    def _create_for_single_game(self, game_data):
        """
        Creates the necessary files and folders for a single game.
        """
        app_config = self.main_window.config
        game_name_override = game_data.get('name_override', 'New Game')
        safe_game_name = make_safe_filename(game_name_override)
        
        # Check if launcher creation is enabled in Setup Tab
        if not app_config.defaults.get('launchers_dir_enabled', True):
            logging.info(f"Skipping launcher creation for {game_name_override} (Disabled in Setup)")
            return True

        # 1. Define the launcher directory for this game
        launcher_base_dir = Path(app_config.launchers_dir)
        launcher_shortcut_path = launcher_base_dir / f"{safe_game_name}.lnk"
        
        try:
            # Check overwrite flag for launcher directory
            if launcher_shortcut_path.exists() and not app_config.overwrite_states.get('launchers_dir', True): # Launcher dir overwrite is still global
                logging.info(f"Skipping launcher creation for {game_name_override} (Overwrite disabled)")
                return True

            # 2. Create the directory structure
            launcher_base_dir.mkdir(parents=True, exist_ok=True)
            
            # 2a. Create Profile Directory in the correct location (Profiles folder)
            profiles_base_dir = Path(app_config.profiles_dir)
            game_profile_dir = profiles_base_dir / safe_game_name

            if app_config.defaults.get('profiles_dir_enabled', True):
                try:
                    game_profile_dir.mkdir(parents=True, exist_ok=True)
                    (game_profile_dir / "Saves").mkdir(exist_ok=True)
                except Exception as e:
                    logging.error(f"Failed to create profile directory for {game_name_override}: {e}")

            # Resolve Launcher Executable
            # Check game_data first (populated from editor)
            launcher_val = game_data.get('launcher_executable', '')
            if launcher_val:
                launcher_source, launcher_mode_symbol = self._resolve_mode(launcher_val, 'launcher_executable')
                launcher_mode = 'LC' if launcher_mode_symbol == '>' else 'CEN'
                launcher_source = self._transform_path(launcher_source, game_data)
            else:
                launcher_source = app_config.launcher_executable
                launcher_mode = app_config.deployment_path_modes.get('launcher_executable', 'CEN')

            if not launcher_source:
                launcher_source = constants.LAUNCHER_EXECUTABLE
            
            target_launcher_exe = launcher_source

            if launcher_mode == 'LC' or launcher_mode == '>':
                if os.path.exists(launcher_source):
                    dest_path = game_profile_dir / os.path.basename(launcher_source)
                    if not dest_path.exists() or game_data.get('launcher_executable_overwrite', app_config.overwrite_states.get('launcher_executable', True)):
                        try:
                            shutil.copy2(launcher_source, dest_path)
                            logging.info(f"Copied launcher executable to {dest_path}")
                        except Exception as e:
                            logging.error(f"Failed to copy launcher executable: {e}")
                    target_launcher_exe = dest_path

            # 3. Create the Game.ini file (will be updated with PCGW data later if needed)
            ini_path = game_profile_dir / "Game.ini"
            
            # 3a. Download Game.json if enabled (before creating INI)
            if app_config.download_game_json:
                self._download_game_json(game_data, game_profile_dir)

            # 3b. Load or download PCGW data (before creating INI so data is available)
            # Always try to load existing pcgw.json, download if enabled
            pcgw_path = game_profile_dir / "pcgw.json"
            if pcgw_path.exists():
                # Load existing PCGW data
                try:
                    with open(pcgw_path, 'r', encoding='utf-8') as f:
                        game_data['pcgw_data'] = json.load(f)
                    logging.info(f"Loaded existing PCGW data for {game_name_override}")
                except Exception as e:
                    logging.warning(f"Failed to load existing pcgw.json: {e}")
            
            # Download new PCGW data if enabled (may overwrite existing)
            if app_config.download_pcgw_metadata:
                self._download_pcgw_data(game_data, game_profile_dir)
            
            # 3c. Now create Game.ini with all available data including PCGW
            self._create_game_ini(ini_path, game_data, app_config, game_profile_dir, launcher_shortcut_path, target_launcher_exe)

            # 3d. Download Artwork if enabled
            if app_config.download_artwork:
                self.download_artwork(game_data, game_profile_dir)

            # 5. Handle CEN/LC file propagation (copying profiles)
            self._propagate_files(game_data, game_profile_dir)
            self._propagate_apps(game_data, game_profile_dir)

            # 6. Create Profile Shortcut (pointing to source title's executable)
            game_exe_path = Path(game_data.get('directory', '')) / game_data.get('name', '')
            profile_shortcut_path = game_profile_dir / f"{safe_game_name}.lnk"
            
            self._create_shortcut(
                target_path=game_exe_path,
                shortcut_path=profile_shortcut_path,
                working_dir=game_data.get('directory', ''),
                description=f"Shortcut to {game_name_override}"
            )

            # 7. Create Launcher Shortcut (pointing to Launcher.exe)
            launcher_args = f'"{profile_shortcut_path}"'
            extra_args = game_data.get('launcher_executable_arguments', app_config.launcher_executable_arguments)
            if extra_args:
                launcher_args += f" {extra_args}"

            self._create_shortcut(
                target_path=target_launcher_exe,
                shortcut_path=launcher_shortcut_path,
                arguments=launcher_args,
                working_dir=game_data.get('directory', ''),
                icon_path=game_exe_path,
                description=f"Launch {game_name_override}"
            )

            self.main_window.statusBar().showMessage(f"Successfully created launcher for {game_name_override}", 3000)
            return True
            
        except Exception as e:
            logging.error(f"Failed to create launcher for {game_name_override}: {e}", exc_info=True)
            self.main_window.statusBar().showMessage(f"Error creating launcher for {game_name_override}: {e}", 5000)
            return False

    def _create_shortcut(self, target_path, shortcut_path, arguments="", working_dir="", icon_path=None, description=""):
        """Creates a Windows shortcut using the bundled Shortcut.exe."""
        shortcut_exe = os.path.join(constants.APP_ROOT_DIR, "bin", "Shortcut.exe")
        if not os.path.exists(shortcut_exe):
            logging.error(f"Shortcut.exe not found at {shortcut_exe}")
            return False

        cmd = [
            shortcut_exe,
            "/F:" + str(shortcut_path),
            "/A:C",
            "/T:" + str(target_path)
        ]
        if arguments:
            cmd.append("/P:" + str(arguments))
        if working_dir:
            cmd.append("/W:" + str(working_dir))
        if icon_path:
            cmd.append("/I:" + str(icon_path))
        if description:
            cmd.append("/D:" + str(description))

        subprocess.run(cmd, check=True, capture_output=True)

    def _download_game_json(self, game_data, game_launcher_dir):
        """Downloads Game.json from Steam API if steam_id is present."""
        steam_id = game_data.get('steam_id')
        if not steam_id or steam_id == 'NOT_FOUND_IN_DATA' or steam_id == 'ITEM_IS_NONE':
            logging.info(f"Skipping Game.json download: No valid Steam ID for {game_data.get('name_override')}")
            return

        url = f"https://store.steampowered.com/api/appdetails?appids={steam_id}"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            json_path = game_launcher_dir / "Game.json"
            
            # Check overwrite
            if json_path.exists() and not self.main_window.config.overwrite_game_json:
                logging.info(f"Skipping Game.json download (Overwrite disabled) for {game_data.get('name_override')}")
                return

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            logging.info(f"Downloaded Game.json for {game_data.get('name_override')} (AppID: {steam_id})")
            
        except Exception as e:
            logging.error(f"Failed to download Game.json for {game_data.get('name_override')} (AppID: {steam_id}): {e}")

    def _download_pcgw_data(self, game_data, game_launcher_dir):
        """Downloads metadata from PCGamingWiki."""
        steam_id = game_data.get('steam_id')
        game_name = game_data.get('name_override', '')
        
        # Check overwrite
        pcgw_path = game_launcher_dir / "pcgw.json"
        if pcgw_path.exists() and not self.main_window.config.overwrite_pcgw_metadata:
            logging.info(f"Skipping PCGW download (Overwrite disabled) for {game_name}")
            # Load existing data to game_data for INI generation
            try:
                with open(pcgw_path, 'r', encoding='utf-8') as f:
                    game_data['pcgw_data'] = json.load(f)
            except: pass
            return

        pcgw_data = self.pcgw_manager.fetch_data(game_name, steam_id)
        
        if pcgw_data:
            with open(pcgw_path, 'w', encoding='utf-8') as f:
                json.dump(pcgw_data, f, indent=4)
            logging.info(f"Downloaded PCGW metadata for {game_name}")
            game_data['pcgw_data'] = pcgw_data
        elif hasattr(self.main_window, 'config') and self.main_window.config.logging_verbosity != "None":
            logging.warning(f"[PCGW] No metadata found for: {game_name}")

    def download_artwork(self, game_data, profile_dir):
        """Downloads artwork for the game."""
        steam_id = game_data.get('steam_id')
        if not steam_id or steam_id == 'NOT_FOUND_IN_DATA' or steam_id == 'ITEM_IS_NONE':
            return

        try:
            # Check if Game.json exists to avoid re-downloading
            json_path = Path(profile_dir) / "Game.json"
            data = None
            
            if json_path.exists():
                try:
                    with open(json_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                except:
                    pass
            
            if not data:
                url = f"https://store.steampowered.com/api/appdetails?appids={steam_id}"
                response = requests.get(url, timeout=10)
                response.raise_for_status()
                data = response.json()

            if str(steam_id) in data and data[str(steam_id)]['success']:
                game_info = data[str(steam_id)]['data']
                header_url = game_info.get('header_image')
                background_url = game_info.get('background')
                
                overwrite = self.main_window.config.overwrite_artwork

                if header_url:
                    self._download_image(header_url, Path(profile_dir) / "Folder.jpg", overwrite)
                
                if background_url:
                    self._download_image(background_url, Path(profile_dir) / "Backdrop.jpg", overwrite)
                    
        except Exception as e:
            logging.error(f"Failed to download artwork for {game_data.get('name_override')}: {e}")

    def _download_image(self, url, target_path, overwrite=False):
        try:
            if target_path.exists() and not overwrite:
                return

            response = requests.get(url, stream=True, timeout=10)
            response.raise_for_status()
            with open(target_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            logging.info(f"Downloaded artwork: {target_path}")
        except Exception as e:
            logging.error(f"Failed to download image {url}: {e}")

    def _expand_pcgw_path(self, template_path, game_data):
        """
        Expand PCGW template variables in a path.
        
        Supported variables:
        - <path-to-game> → Game directory
        - <Steam-folder> → Steam installation path
        - <user-id> → Steam user ID from game_data
        - %LOCALAPPDATA%, %APPDATA%, etc. → Windows environment variables
        
        Args:
            template_path: Path with template variables
            game_data: Game data dictionary containing steam_id and directory
            
        Returns:
            Expanded path string
        """
        expanded = template_path
        
        # Replace game-specific variables
        if '<path-to-game>' in expanded:
            game_dir = game_data.get('directory', '')
            expanded = expanded.replace('<path-to-game>', game_dir)
        
        # Replace Steam variables
        if '<Steam-folder>' in expanded or '<steam-folder>' in expanded:
            # Common Steam installation paths
            steam_paths = [
                r'C:\Program Files (x86)\Steam',
                r'C:\Program Files\Steam',
                os.path.expandvars(r'%PROGRAMFILES(X86)%\Steam'),
                os.path.expandvars(r'%PROGRAMFILES%\Steam'),
            ]
            steam_path = None
            for path in steam_paths:
                if os.path.exists(path):
                    steam_path = path
                    break
            
            if steam_path:
                expanded = expanded.replace('<Steam-folder>', steam_path)
                expanded = expanded.replace('<steam-folder>', steam_path)
        
        # Replace <user-id> with steam_id from game_data
        if '<user-id>' in expanded:
            steam_id = game_data.get('steam_id', '')
            if steam_id and steam_id not in ['NOT_FOUND_IN_DATA', 'ITEM_IS_NONE', '']:
                expanded = expanded.replace('<user-id>', str(steam_id))
        
        # Replace Windows environment variables
        expanded = os.path.expandvars(expanded)
        
        # Ensure Windows-style backslashes
        expanded = expanded.replace('/', '\\')
        
        return expanded

    def _create_game_ini(self, ini_path, game_data, app_config, game_profile_dir, launcher_shortcut_path, launcher_executable_path=None):
        """
        Generates and saves the Game.ini file based on game-specific and global settings.
        
        New structure follows the pattern:
        - Section name = application type (e.g., [ControllerMapper])
        - Key name = config key with underscores removed (e.g., controllermapperpath)
        """
        config = configparser.ConfigParser(interpolation=None)

        # --- [Game] Section ---
        config.add_section('Game')
        game_exe_path = os.path.join(game_data.get('directory', ''), game_data.get('name', ''))
        config.set('Game', 'profiledirectory', str(game_profile_dir).replace('/', '\\'))
        config.set('Game', 'gameexecutablepath', str(game_exe_path).replace('/', '\\'))
        config.set('Game', 'executable', game_data.get('name', ''))
        config.set('Game', 'directory', game_data.get('directory', ''))
        config.set('Game', 'name', game_data.get('name_override', ''))
        config.set('Game', 'isopath', game_data.get('iso_path', ''))
        config.set('Game', 'steamid', str(game_data.get('steam_id', '')))

        # --- [Launcher] Section ---
        config.add_section('Launcher')
        launcher_exe = str(launcher_executable_path if launcher_executable_path else constants.LAUNCHER_EXECUTABLE).replace('/', '\\')
        config.set('Launcher', 'launchershortcut', str(launcher_shortcut_path).replace('/', '\\'))
        config.set('Launcher', 'launcherexecutable', launcher_exe)
        config.set('Launcher', 'runasadmin', str(game_data.get('run_as_admin', False)))
        config.set('Launcher', 'hidetaskbar', str(game_data.get('hide_taskbar', False)))
        config.set('Launcher', 'borderless', game_data.get('options', '0'))
        config.set('Launcher', 'usekilllist', str(game_data.get('kill_list_enabled', False)))
        config.set('Launcher', 'terminateborderlessonexit', str(game_data.get('terminate_borderless_on_exit', app_config.terminate_borderless_on_exit)))
        config.set('Launcher', 'killlist', game_data.get('kill_list', ''))

        # --- [Profiles] Section ---
        config.add_section('Profiles')
        
        if game_data.get('player1_profile_enabled', True):
            val = self._get_profile_path('player1_profile', game_data, game_profile_dir)
            config.set('Profiles', 'player1profile', val)
        else:
            config.set('Profiles', 'player1profile', "")
        
        if game_data.get('player2_profile_enabled', True):
            val = self._get_profile_path('player2_profile', game_data, game_profile_dir)
            config.set('Profiles', 'player2profile', val)
        else:
            config.set('Profiles', 'player2profile', "")
        
        if game_data.get('mediacenter_profile_enabled', True):
            val = self._get_profile_path('mediacenter_profile', game_data, game_profile_dir)
            config.set('Profiles', 'mediacenterprofile', val)
        else:
            config.set('Profiles', 'mediacenterprofile', "")
        
        if game_data.get('mm_game_profile_enabled', True):
            val = self._get_profile_path('mm_game_profile', game_data, game_profile_dir)
            config.set('Profiles', 'multimonitorgamingconfig', val)
        else:
            config.set('Profiles', 'multimonitorgamingconfig', "")
        
        if game_data.get('mm_desktop_profile_enabled', True):
            val = self._get_profile_path('mm_desktop_profile', game_data, game_profile_dir)
            config.set('Profiles', 'multimonitormediacenterconfig', val)
        else:
            config.set('Profiles', 'multimonitormediacenterconfig', "")

        # --- [DiscMount] Section ---
        config.add_section('DiscMount')
        config.set('DiscMount', 'enablediscmount', str(game_data.get('disc_mount_enabled', False)))
        config.set('DiscMount', 'discmountpath', self._get_app_path_for_ini('disc_mount_path', game_data, game_profile_dir))
        config.set('DiscMount', 'discmountpathoptions', game_data.get('disc_mount_options', ''))
        config.set('DiscMount', 'discmountpatharguments', game_data.get('disc_mount_args', ''))
        config.set('DiscMount', 'discmountpathrunwait', str(game_data.get('disc_mount_wait', False)))

        # --- [DiscUnmount] Section ---
        config.add_section('DiscUnmount')
        config.set('DiscUnmount', 'enablediscunmount', str(game_data.get('disc_unmount_enabled', False)))
        config.set('DiscUnmount', 'discunmountpath', self._get_app_path_for_ini('disc_unmount_path', game_data, game_profile_dir))
        config.set('DiscUnmount', 'discunmountpathoptions', game_data.get('disc_unmount_options', ''))
        config.set('DiscUnmount', 'discunmountpatharguments', game_data.get('disc_unmount_args', ''))
        config.set('DiscUnmount', 'discunmountpathrunwait', str(game_data.get('disc_unmount_wait', False)))

        # --- [ControllerMapper] Section ---
        config.add_section('ControllerMapper')
        config.set('ControllerMapper', 'enablecontrollermapper', str(game_data.get('controller_mapper_enabled', True)))
        config.set('ControllerMapper', 'controllermapperpath', self._get_app_path_for_ini('controller_mapper_path', game_data, game_profile_dir))
        config.set('ControllerMapper', 'controllermapperpathoptions', game_data.get('controller_mapper_options', app_config.controller_mapper_path_options))
        config.set('ControllerMapper', 'controllermapperpatharguments', game_data.get('controller_mapper_arguments', app_config.controller_mapper_path_arguments))
        config.set('ControllerMapper', 'controllermapperrunwait', str(game_data.get('controller_mapper_run_wait', False)))

        # --- [BorderlessWindowing] Section ---
        config.add_section('BorderlessWindowing')
        config.set('BorderlessWindowing', 'enableborderlesswindowing', str(game_data.get('borderless_windowing_enabled', True)))
        config.set('BorderlessWindowing', 'borderlesswindowingpath', self._get_app_path_for_ini('borderless_windowing_path', game_data, game_profile_dir))
        config.set('BorderlessWindowing', 'borderlesswindowingpathoptions', game_data.get('borderless_windowing_options', app_config.borderless_gaming_path_options))
        config.set('BorderlessWindowing', 'borderlesswindowingpatharguments', game_data.get('borderless_windowing_arguments', app_config.borderless_gaming_path_arguments))
        config.set('BorderlessWindowing', 'borderlesswindowingpathrunwait', str(game_data.get('borderless_windowing_run_wait', False)))

        # --- [MultiMonitor] Section ---
        config.add_section('MultiMonitor')
        config.set('MultiMonitor', 'enablemultimonitor', str(game_data.get('multi_monitor_app_enabled', True)))
        config.set('MultiMonitor', 'multimonitorpath', self._get_app_path_for_ini('multi_monitor_app_path', game_data, game_profile_dir))
        config.set('MultiMonitor', 'multimonitorpathoptions', game_data.get('multi_monitor_app_options', app_config.multi_monitor_tool_path_options))
        config.set('MultiMonitor', 'multimonitorpatharguments', game_data.get('multi_monitor_app_arguments', app_config.multi_monitor_tool_path_arguments))
        config.set('MultiMonitor', 'multimonitorpathrunwait', str(game_data.get('multi_monitor_app_run_wait', False)))

        # --- [CloudSync] Section ---
        config.add_section('CloudSync')
        config.set('CloudSync', 'enablecloudsync', str(game_data.get('cloud_app_enabled', False)))
        config.set('CloudSync', 'cloudsyncpath', self._get_app_path_for_ini('cloud_app_path', game_data, game_profile_dir))
        config.set('CloudSync', 'cloudsyncpathoptions', game_data.get('cloud_app_options', ''))
        config.set('CloudSync', 'cloudsyncpatharguments', game_data.get('cloud_app_args', ''))
        config.set('CloudSync', 'cloudsyncpathrunwait', str(game_data.get('cloud_app_wait', False)))

        # --- [LocalBackup] Section ---
        config.add_section('LocalBackup')
        config.set('LocalBackup', 'enablelocalbackup', str(game_data.get('backup_app_enabled', False)))
        config.set('LocalBackup', 'localbackuppath', self._get_app_path_for_ini('backup_app_path', game_data, game_profile_dir))
        config.set('LocalBackup', 'localbackuppathoptions', game_data.get('backup_app_options', ''))
        config.set('LocalBackup', 'localbackuppatharguments', game_data.get('backup_app_args', ''))
        config.set('LocalBackup', 'localbackuppathrunwait', str(game_data.get('backup_app_wait', False)))

        # --- [JustAfterLaunch] Section ---
        config.add_section('JustAfterLaunch')
        config.set('JustAfterLaunch', 'enable', str(game_data.get('just_after_launch_enabled', False)))
        config.set('JustAfterLaunch', 'path', self._get_app_path_for_ini('just_after_launch_path', game_data, game_profile_dir))
        config.set('JustAfterLaunch', 'pathoptions', game_data.get('just_after_launch_options', app_config.just_after_launch_path_options))
        config.set('JustAfterLaunch', 'patharguments', game_data.get('just_after_launch_arguments', app_config.just_after_launch_path_arguments))
        config.set('JustAfterLaunch', 'pathrunwait', str(game_data.get('just_after_launch_run_wait', False)))

        # --- [JustBeforeExit] Section ---
        config.add_section('JustBeforeExit')
        config.set('JustBeforeExit', 'enable', str(game_data.get('just_before_exit_enabled', False)))
        config.set('JustBeforeExit', 'path', self._get_app_path_for_ini('just_before_exit_path', game_data, game_profile_dir))
        config.set('JustBeforeExit', 'pathoptions', game_data.get('just_before_exit_options', app_config.just_before_exit_path_options))
        config.set('JustBeforeExit', 'patharguments', game_data.get('just_before_exit_arguments', app_config.just_before_exit_path_arguments))
        config.set('JustBeforeExit', 'pathrunwait', str(game_data.get('just_before_exit_run_wait', False)))

        # --- [Pre1] Section ---
        config.add_section('Pre1')
        config.set('Pre1', 'enablepre1', str(game_data.get('pre1_enabled', False)))
        config.set('Pre1', 'pre1path', self._get_app_path_for_ini('pre1_path', game_data, game_profile_dir))
        config.set('Pre1', 'pre1pathoptions', game_data.get('pre1_options', app_config.pre1_path_options))
        config.set('Pre1', 'pre1patharguments', game_data.get('pre1_arguments', app_config.pre1_path_arguments))
        config.set('Pre1', 'pre1pathrunwait', str(game_data.get('pre_1_run_wait', False)))

        # --- [Pre2] Section ---
        config.add_section('Pre2')
        config.set('Pre2', 'enablepre2', str(game_data.get('pre2_enabled', False)))
        config.set('Pre2', 'pre2path', self._get_app_path_for_ini('pre2_path', game_data, game_profile_dir))
        config.set('Pre2', 'pre2pathoptions', game_data.get('pre2_options', app_config.pre2_path_options))
        config.set('Pre2', 'pre2patharguments', game_data.get('pre2_arguments', app_config.pre2_path_arguments))
        config.set('Pre2', 'pre2pathrunwait', str(game_data.get('pre_2_run_wait', False)))

        # --- [Pre3] Section ---
        config.add_section('Pre3')
        config.set('Pre3', 'enablepre3', str(game_data.get('pre3_enabled', False)))
        config.set('Pre3', 'pre3path', self._get_app_path_for_ini('pre3_path', game_data, game_profile_dir))
        config.set('Pre3', 'pre3pathoptions', game_data.get('pre3_options', app_config.pre3_path_options))
        config.set('Pre3', 'pre3patharguments', game_data.get('pre3_arguments', app_config.pre3_path_arguments))
        config.set('Pre3', 'pre3pathrunwait', str(game_data.get('pre_3_run_wait', False)))

        # --- [Post1] Section ---
        config.add_section('Post1')
        config.set('Post1', 'enablepost1', str(game_data.get('post1_enabled', False)))
        config.set('Post1', 'post1path', self._get_app_path_for_ini('post1_path', game_data, game_profile_dir))
        config.set('Post1', 'post1pathoptions', game_data.get('post1_options', app_config.post1_path_options))
        config.set('Post1', 'post1patharguments', game_data.get('post1_arguments', app_config.post1_path_arguments))
        config.set('Post1', 'post1pathrunwait', str(game_data.get('post_1_run_wait', False)))

        # --- [Post2] Section ---
        config.add_section('Post2')
        config.set('Post2', 'enablepost2', str(game_data.get('post2_enabled', False)))
        config.set('Post2', 'post2path', self._get_app_path_for_ini('post2_path', game_data, game_profile_dir))
        config.set('Post2', 'post2pathoptions', game_data.get('post2_options', app_config.post2_path_options))
        config.set('Post2', 'post2patharguments', game_data.get('post2_arguments', app_config.post2_path_arguments))
        config.set('Post2', 'post2pathrunwait', str(game_data.get('post_2_run_wait', False)))

        # --- [Post3] Section ---
        config.add_section('Post3')
        config.set('Post3', 'enablepost3', str(game_data.get('post3_enabled', False)))
        config.set('Post3', 'post3path', self._get_app_path_for_ini('post3_path', game_data, game_profile_dir))
        config.set('Post3', 'post3pathoptions', game_data.get('post3_options', app_config.post3_path_options))
        config.set('Post3', 'post3patharguments', game_data.get('post3_arguments', app_config.post3_path_arguments))
        config.set('Post3', 'post3pathrunwait', str(game_data.get('post_3_run_wait', False)))

        # --- [Sequences] Section ---
        config.add_section('Sequences')
        config.set('Sequences', 'launchsequence', ",".join(app_config.launch_sequence))
        config.set('Sequences', 'exitsequence', ",".join(app_config.exit_sequence))

        # --- [SourceProfiles] Section ---
        config.add_section('SourceProfiles')
        
        source_map = [
            ('player1profile', 'player1_profile', 'p1_profile_path'),
            ('player2profile', 'player2_profile', 'p2_profile_path'),
            ('multimonitorgamingconfig', 'mm_game_profile', 'multimonitor_gaming_path'),
            ('multimonitormediacenterconfig', 'mm_desktop_profile', 'multimonitor_media_path'),
            ('mediacenterprofile', 'mediacenter_profile', 'mediacenter_profile_path'),
        ]

        for ini_key, data_key, config_key in source_map:
            path_val = game_data.get(data_key, "")
            if not path_val: continue
            
            clean_path, mode = self._resolve_mode(path_val, config_key)
            if mode == '>':
                # It is LC, write resolved source path
                extra_context = {}
                if 'player' in data_key and 'profile' in data_key:
                    if '1' in data_key: extra_context['$player_number'] = '1'
                    elif '2' in data_key: extra_context['$player_number'] = '2'
                    elif '3' in data_key: extra_context['$player_number'] = '3'
                    elif '4' in data_key: extra_context['$player_number'] = '4'
                
                resolved_source = self._transform_path(clean_path, game_data, extra_context)
                config.set('SourceProfiles', ini_key, resolved_source)

        # --- [SourceApplications] Section ---
        config.add_section('SourceApplications')
        
        app_source_map = [
            ('antimicrox', 'controller_mapper_path', 'controller_mapper_path'),
            ('borderless', 'borderless_windowing_path', 'borderless_gaming_path'),
            ('multimonitortool', 'multi_monitor_app_path', 'multi_monitor_tool_path'),
            ('wincdemu', 'disc_mount_path', 'disc_mount_path'),
            ('rclone', 'cloud_app_path', 'cloud_app_path'),
            ('ludusavi', 'backup_app_path', 'backup_app_path'),
        ]

        for ini_key, data_key, config_key in app_source_map:
            path_val = game_data.get(data_key, "")
            if not path_val: continue
            
            clean_path, mode = self._resolve_mode(path_val, config_key)
            if mode == '>':
                # It is LC, write resolved source path
                resolved_source = self._transform_path(clean_path, game_data)
                config.set('SourceApplications', ini_key, resolved_source)

        # --- [SYSTEM], [SAVE], and [CONFIG] Sections for PCGW data ---
        pcgw_data = game_data.get('pcgw_data', {})
        if pcgw_data:
            save_locations = pcgw_data.get('save_locations', {})
            config_locations = pcgw_data.get('config_locations', {})
            
            # Create sections
            if save_locations or config_locations:
                config.add_section('SYSTEM')
                config.add_section('SAVE')
                config.add_section('CONFIG')
            
            # Process each platform
            all_platforms = set(save_locations.keys()) | set(config_locations.keys())
            for platform in all_platforms:
                # Normalize platform name for keys (replace spaces with underscores)
                platform_key = platform.replace(' ', '_').replace('(', '').replace(')', '')
                
                # Process save locations
                if platform in save_locations:
                    save_entries = save_locations[platform]
                    template_paths = []
                    expanded_paths = []
                    
                    for entry in save_entries:
                        if isinstance(entry, dict):
                            path = entry.get('path', '')
                            if path:
                                template_paths.append(path)
                                # Expand template variables for SAVE section
                                expanded = self._expand_pcgw_path(path, game_data)
                                expanded_paths.append(expanded)
                        else:
                            template_paths.append(str(entry))
                            expanded = self._expand_pcgw_path(str(entry), game_data)
                            expanded_paths.append(expanded)
                    
                    if template_paths:
                        # Write templates to [SYSTEM] section: {platform}_save=path1|path2|path3
                        pipe_delimited = '|'.join(template_paths)
                        config.set('SYSTEM', f'{platform_key}_save', pipe_delimited)
                        
                        # Write expanded paths to [SAVE] section: {platform}=path1|path2|path3
                        expanded_delimited = '|'.join(expanded_paths)
                        config.set('SAVE', platform_key, expanded_delimited)
                
                # Process config locations
                if platform in config_locations:
                    config_entries = config_locations[platform]
                    template_paths = []
                    expanded_paths = []
                    
                    for entry in config_entries:
                        if isinstance(entry, dict):
                            path = entry.get('path', '')
                            if path:
                                template_paths.append(path)
                                # Expand template variables for CONFIG section
                                expanded = self._expand_pcgw_path(path, game_data)
                                expanded_paths.append(expanded)
                        else:
                            template_paths.append(str(entry))
                            expanded = self._expand_pcgw_path(str(entry), game_data)
                            expanded_paths.append(expanded)
                    
                    if template_paths:
                        # Write templates to [SYSTEM] section: {platform}_config=path1|path2|path3
                        pipe_delimited = '|'.join(template_paths)
                        config.set('SYSTEM', f'{platform_key}_config', pipe_delimited)
                        
                        # Write expanded paths to [CONFIG] section: {platform}=path1|path2|path3
                        expanded_delimited = '|'.join(expanded_paths)
                        config.set('CONFIG', platform_key, expanded_delimited)

        # Write the INI file
        with open(ini_path, 'w', encoding='utf-8') as configfile:
            config.write(configfile)

    def _get_profile_path(self, profile_key, game_data, game_profile_dir=None):
        """
        Determines the correct path for a profile based on CEN/LC mode from the editor data.
        Enforces centralized path behavior to prevent profile folders in Launchers directory.
        """
        # Map profile_key to config_key
        config_key_map = {
            'player1_profile': 'p1_profile_path',
            'player2_profile': 'p2_profile_path',
            'player3_profile': 'p3_profile_path',
            'player4_profile': 'p4_profile_path',
            'mm_game_profile': 'multimonitor_gaming_path',
            'mm_desktop_profile': 'multimonitor_media_path',
            'mediacenter_profile': 'mediacenter_profile_path'
        }
        config_key = config_key_map.get(profile_key, profile_key)
        
        path_with_mode = game_data.get(profile_key, "")
        original_path, mode = self._resolve_mode(path_with_mode, config_key)
        
        if not original_path:
            return ""

        # Prepare context for transformation
        extra_context = {}
        if profile_key == 'player1_profile':
            extra_context['$player_number'] = '1'
        elif profile_key == 'player2_profile':
            extra_context['$player_number'] = '2'
        elif profile_key == 'player3_profile':
            extra_context['$player_number'] = '3'
        elif profile_key == 'player4_profile':
            extra_context['$player_number'] = '4'

        resolved_path = self._transform_path(original_path, game_data, extra_context)

        if mode == '>': # LC (Launch Conditional / Local Copy)
            # Return absolute path to the file in the profile directory
            if game_profile_dir:
                full_path = Path(game_profile_dir) / os.path.basename(resolved_path)
                # Ensure Windows-style backslashes
                return str(os.path.abspath(full_path)).replace('/', '\\')
            return os.path.basename(resolved_path)
        
        # CEN (Centralized)
        return resolved_path

    def _get_app_path_for_ini(self, key, game_data, target_dir):
        """
        Determines the correct path for an app/script based on CEN/LC mode.
        If LC, returns the relative path to the file in the profile directory.
        """
        # Map key to config_key
        config_key_map = {
            'borderless_windowing_path': 'borderless_gaming_path',
            'multi_monitor_app_path': 'multi_monitor_tool_path'
        }
        config_key = config_key_map.get(key, key)
        
        path_val = game_data.get(key, "")
        clean_path, mode = self._resolve_mode(path_val, config_key)
        
        if not clean_path: return ""

        if mode == '>':
            # LC mode
            resolved_path = self._transform_path(clean_path, game_data)
            exe_name = os.path.basename(resolved_path)
            
            # Try to find it in target_dir (it might be in a subfolder if extracted)
            found = self._find_file_recursive(target_dir, exe_name)
            if found:
                try:
                    rel_path = Path(found).relative_to(target_dir)
                    # Ensure Windows-style backslashes
                    return str(rel_path).replace('/', '\\')
                except ValueError:
                    return exe_name
            return exe_name
        else:
            # CEN mode
            return self._transform_path(clean_path, game_data)

    def _propagate_apps(self, game_data, target_dir):
        """
        Handles LC propagation for applications and scripts.
        Downloads/Extracts if supported in repos.set, otherwise copies.
        """
        app_keys = [
            'controller_mapper_path', 'borderless_windowing_path', 'multi_monitor_app_path',
            'just_after_launch_path', 'just_before_exit_path',
            'pre1_path', 'pre2_path', 'pre3_path',
            'post1_path', 'post2_path', 'post3_path'
        ]

        config_key_map = {
            'borderless_windowing_path': 'borderless_gaming_path',
            'multi_monitor_app_path': 'multi_monitor_tool_path'
        }

        for key in app_keys:
            path_val = game_data.get(key, "")
            config_key = config_key_map.get(key, key)
            original_path, mode = self._resolve_mode(path_val, config_key)
            
            if not original_path or mode != '>':
                continue

            resolved_path = self._transform_path(original_path, game_data)
            if not resolved_path:
                continue

            exe_name = os.path.basename(resolved_path)
            exe_lower = exe_name.lower()

            # Check if it's a supported repo tool
            if exe_lower in self.repo_tools:
                url = self.repo_tools[exe_lower]
                # Check if already exists in target_dir (recursively)
                if self._find_file_recursive(target_dir, exe_name):
                    logging.info(f"Tool {exe_name} already present in {target_dir}, skipping download.")
                    continue
                
                # Download and extract
                try:
                    logging.info(f"Downloading {exe_name} from {url}...")
                    response = requests.get(url, stream=True)
                    response.raise_for_status()
                    
                    zip_path = target_dir / f"{exe_name}.zip"
                    with open(zip_path, 'wb') as f:
                        for chunk in response.iter_content(chunk_size=8192):
                            f.write(chunk)
                    
                    logging.info(f"Extracting {exe_name}...")
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        zip_ref.extractall(target_dir)
                    
                    os.remove(zip_path)
                except Exception as e:
                    logging.error(f"Failed to download/extract {exe_name}: {e}")
            else:
                # Not a repo tool, just copy the file
                src_path = Path(resolved_path)
                if src_path.exists():
                    dest_path = target_dir / src_path.name
                    if not dest_path.exists() or self.main_window.config.overwrite_states.get(key, True):
                        try:
                            shutil.copy2(src_path, dest_path)
                            logging.info(f"Copied {src_path} to {dest_path}")
                        except Exception as e:
                            logging.error(f"Failed to copy {src_path}: {e}")

    def _find_file_recursive(self, root_dir, filename):
        """Recursively find a file in a directory."""
        for root, dirs, files in os.walk(root_dir):
            if filename in files:
                return os.path.join(root, filename)
        return None

    def _propagate_files(self, game_data, target_dir):
        """
        Copies files to the target directory (Profiles folder) if they are set to LC mode.
        """
        app_config = self.main_window.config
        
        # Map profile keys to their overwrite config keys
        profile_map = {
            'player1_profile': 'p1_profile_path',
            'player2_profile': 'p2_profile_path',
            'mm_game_profile': 'multimonitor_gaming_path',
            'mm_desktop_profile': 'multimonitor_media_path',
            'mediacenter_profile': 'mediacenter_profile_path'
        }

        for key, config_key in profile_map.items():
            if not game_data.get(f"{key}_enabled", True):
                continue

            path_with_mode = game_data.get(key, "")
            if not path_with_mode:
                continue
                
            original_path_str, mode = self._resolve_mode(path_with_mode, config_key)

            extra_context = {}
            if key == 'player1_profile':
                extra_context['$player_number'] = '1'
            elif key == 'player2_profile':
                extra_context['$player_number'] = '2'
            elif key == 'player3_profile':
                extra_context['$player_number'] = '3'
            elif key == 'player4_profile':
                extra_context['$player_number'] = '4'
            resolved_path_str = self._transform_path(original_path_str, game_data, extra_context)
            
            # Only copy if mode is LC (>) and path exists
            if mode == '>' and resolved_path_str and os.path.exists(resolved_path_str):
                original_path = Path(resolved_path_str)
                target_file = target_dir / original_path.name
                
                if target_file.exists() and not app_config.overwrite_states.get(config_key, True):
                    continue

                try:
                    shutil.copy2(original_path, target_file)
                    logging.info(f"Copied profile {original_path} to {target_file}")
                except Exception as e:
                    logging.error(f"Failed to copy profile {original_path} to {target_dir}: {e}")

    def _parse_repos_set(self):
        """Parses the repos.set file to get tool download URLs."""
        repos = {}
        if not os.path.exists(constants.REPOS_SET):
            return repos

        config = configparser.ConfigParser()
        config.read(constants.REPOS_SET)

        global_vars = {}
        if "GLOBAL" in config:
            global_vars = dict(config["GLOBAL"])
            global_vars["app_directory"] = constants.APP_ROOT_DIR

        # Map exe_name -> url
        tool_map = {}

        for section in config.sections():
            if section == "GLOBAL": continue
            for key, value in config[section].items():
                # Substitute vars
                val = value
                for var_name, var_val in global_vars.items():
                    val = val.replace(f"${var_name.upper()}", var_val)
                    val = val.replace(f"${var_name}", var_val)
                val = val.replace("$ITEMNAME", key)
                
                parts = val.split('|')
                if len(parts) >= 3:
                    url = parts[0]
                    exe_name = parts[2].lower() # Normalize to lower for matching
                    tool_map[exe_name] = url
        return tool_map