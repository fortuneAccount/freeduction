import os
import json
import shutil
import logging
import string
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from ..models import AppConfig
from .. import constants


CONFIG_FILE = os.path.join(constants.APP_ROOT_DIR, "config.json")

# --- First Run Constants ---
GAME_DIRECTORY_NAMES = [
    "Games", "GOG Games", "Gaemz", "vidya", "Gaymez",
    "Gaymes", "Installed Games", "Game Library"
]
ANTIMICROX_EXES = ["antimicrox.exe", "antimicrox"]
KEYSTICKS_EXES = ["keysticks.exe"]
MONITOR_EXES = ["multimonitortool.exe", "MultiMonitorTool.exe"]
BORDERLESS_EXES = ["borderlessgaming.exe"]


class ConfigManager(QObject):
    """Manages loading and saving of application configuration."""
    status_updated = pyqtSignal(str, int)

    def __init__(self):
        super().__init__()
        self.config_file = CONFIG_FILE

    def load_config(self) -> AppConfig:
        """Loads the application configuration from config.json."""
        if not os.path.exists(self.config_file):
            logging.info("Config file not found. Running first-time setup.")
            self.status_updated.emit("Performing first-time setup...", 0)
            config = self._first_run_setup()
            self.save_config(config)
            self.status_updated.emit("First-time setup complete.", 3000)
            return config

        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Create an AppConfig instance and update it with loaded data
            config = AppConfig()
            for key, value in config_data.items():
                setattr(config, key, value)

            # Always record the application root as app_directory.
            if not getattr(config, 'app_directory', ''):
                config.app_directory = constants.APP_ROOT_DIR

            self.status_updated.emit("Configuration loaded.", 3000)
            return config
        except Exception as e:
            logging.error(f"Failed to load config file {self.config_file}: {e}", exc_info=True)
            self.status_updated.emit(f"Failed to load config file: {e}", 5000)
            # Fallback to default config if loading fails
            return self._first_run_setup()

    def save_config(self, config: AppConfig):
        """Saves the application configuration to config.json."""
        try:
            # Use a dictionary representation of the AppConfig model
            config_data = {key: getattr(config, key) for key in dir(config) if not key.startswith('__') and not callable(getattr(config, key))}

            # Preserve the history section (config-file records) which is managed
            # by the Configuration Presets UI and is not a model attribute.
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    existing = json.load(f)
                if isinstance(existing, dict) and 'history' in existing:
                    config_data['history'] = existing['history']
                if isinstance(existing, dict) and 'app_directory' in existing and not config_data.get('app_directory'):
                    config_data['app_directory'] = existing['app_directory']
            except Exception:
                pass

            # Always record the application root as app_directory.
            if not config_data.get('app_directory'):
                config_data['app_directory'] = constants.APP_ROOT_DIR

            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=4)
            self.status_updated.emit("Configuration saved.", 3000)
            logging.info(f"Configuration saved to '{self.config_file}'.")
        except Exception as e:
            logging.error(f"Failed to save config file {self.config_file}: {e}", exc_info=True)
            self.status_updated.emit(f"Failed to save config file: {e}", 5000)

    def _first_run_setup(self) -> AppConfig:
        """
        Run the complete first-time setup.
        Called when no config.json exists.
        """
        logging.info("Running first-time setup...")
        config = AppConfig()

        config.source_dirs = self._scan_for_game_directories()
        config.profiles_dir, config.launchers_dir = self._find_or_create_profiles_launchers_dirs()
        self._detect_controller_mapper(config)
        self._detect_borderless_gaming(config)
        self._detect_all_bin_tools(config)  # Auto-detect all tools in bin directory

        # Set default launcher executable to bundled Launcher.exe
        if not config.launcher_executable:
            config.launcher_executable = constants.LAUNCHER_EXECUTABLE
            config.defaults['launcher_executable_enabled'] = True

        # Set default sequences
        config.launch_sequence = ["Cloud-Sync", "mount-disc", "Kill-Game", "Kill-List", "Controller-Mapper", "Monitor-Config", "No-TB", "Pre1", "Borderless", "Pre2", "Pre3"]
        config.exit_sequence = ["Kill-Game", "Kill-List", "Monitor-Config", "Taskbar", "Post1", "Controller-Mapper", "Post2", "Borderless", "Post3", "Unmount-disc", "Cloud-Sync"]

        # Set default enabled states
        config.defaults = {
            'controller_mapper_path_enabled': True,
            'borderless_gaming_path_enabled': False,
            'monitorapp_path_enabled': True,
            'just_after_launch_path_enabled': False,
            'just_before_exit_path_enabled': False,
            'pre1_path_enabled': False,
            'post1_path_enabled': False,
            'pre2_path_enabled': False,
            'post2_path_enabled': False,
            'pre3_path_enabled': False,
            'post3_path_enabled': False,
            'p1_profile_path_enabled': True,
            'p2_profile_path_enabled': True,
            'desk_profile_path_enabled': True,
            'monitor_game_path_enabled': False,
            'monitor_desk_path_enabled': False,
            'profiles_dir_enabled': True,
            'launchers_dir_enabled': True,
            'disc_mount_path_enabled': False,
            'disc_mount_cfg_enabled': False,
            'disc_unmount_cfg_enabled': False,
            'audio_tool_path_enabled': False,
            'audio_game_cfg_enabled': False,
            'audio_desk_cfg_enabled': False,
            'unborder_cfg_enabled': False,
            'reborder_cfg_enabled': False,
        }

        config.run_wait_states = {
            'controller_mapper_path_run_wait': False,
            'borderless_gaming_path_run_wait': False,
            'monitorapp_path_run_wait': False,
            'just_after_launch_path_run_wait': False,
            'just_before_exit_path_run_wait': False,
            'pre1_path_run_wait': False, 'post1_path_run_wait': False,
            'pre2_path_run_wait': False, 'post2_path_run_wait': False,
            'pre3_path_run_wait': False, 'post3_path_run_wait': False,
            'disc_mount_path_run_wait': False,
            'audio_tool_path_run_wait': False,
            'cloud_sync_path_run_wait': False,
            'local_backup_path_run_wait': False,
        }

        # Set default overwrite states (Deployment Tab -> Creation)
        # Enabled by default for all deployable paths.
        config.overwrite_states = {
            "profiles_dir": True,
            "launchers_dir": True,
            "launcher_executable": True,
            "controller_mapper_path": True,
            "monitorapp_path": True,
            "just_after_launch_path": True,
            "just_before_exit_path": True,
            "p1_profile_path": True,
            "p2_profile_path": True,
            "desk_profile_path": True,
            "monitor_game_path": True,
            "monitor_desk_path": True,
            "pre1_path": True,
            "post1_path": True,
            "pre2_path": True,
            "post2_path": True,
            "pre3_path": True,
            "post3_path": True,
        }

        # Set default deployment tab options
        config.download_game_json = True
        config.overwrite_game_json = True
        config.download_pcgw_metadata = True
        config.overwrite_pcgw_metadata = True
        config.download_artwork = True
        config.overwrite_artwork = True
        config.overwrite_game_ini = True
        config.recreate_game_ini = True
        config.hide_taskbar = False
        config.run_as_admin = True
        config.enable_name_matching = True
        config.auto_flag_existing = True
        config.create_overwrite_joystick_profiles = True

        logging.info("First-time setup complete.")
        return config

    def _get_available_drives(self):
        drives = []
        for letter in string.ascii_uppercase:
            drive = f"{letter}:\\"
            if os.path.exists(drive):
                drives.append(drive)
        return drives

    def _scan_for_game_directories(self):
        found_dirs = []
        drives = self._get_available_drives()
        for drive in drives:
            for dir_name in GAME_DIRECTORY_NAMES:
                dir_path = os.path.join(drive, dir_name)
                if os.path.isdir(dir_path):
                    found_dirs.append(dir_path)
                    logging.info(f"Found game directory: {dir_path}")
        return found_dirs

    def _find_or_create_profiles_launchers_dirs(self):
        home_dir = Path.home()
        documents_dir = home_dir / "Documents"
        project_dir = Path(constants.APP_ROOT_DIR)
        search_locations = [home_dir, documents_dir, project_dir]
        profiles_dir, launchers_dir = None, None

        for location in search_locations:
            if profiles_dir is None and (location / "Profiles").is_dir():
                profiles_dir = str(location / "Profiles")
            if launchers_dir is None and (location / "Launchers").is_dir():
                launchers_dir = str(location / "Launchers")

        if profiles_dir is None:
            profiles_dir = str(project_dir / "Profiles")
            os.makedirs(profiles_dir, exist_ok=True)
        if launchers_dir is None:
            launchers_dir = str(project_dir / "Launchers")
            os.makedirs(launchers_dir, exist_ok=True)
        return profiles_dir, launchers_dir

    def _find_executable_recursive(self, search_dir, exe_names):
        search_path = Path(search_dir)
        if not search_path.exists(): return None
        for exe_name in exe_names:
            for found in search_path.rglob(exe_name):
                if found.is_file():
                    logging.info(f"Found executable: {found}")
                    return str(found)
        return None

    def _detect_controller_mapper(self, config: AppConfig):
        project_dir = Path(constants.APP_ROOT_DIR)
        bin_dir = project_dir / "bin"
        
        # Load options/arguments for applying defaults
        options_args_map = self._load_options_arguments()
        
        antimicrox_path = self._find_executable_recursive(bin_dir, ANTIMICROX_EXES) or self._find_executable_recursive(project_dir, ANTIMICROX_EXES)
        if antimicrox_path:
            config.controller_mapper_path = antimicrox_path
            logging.info(f"Using AntimicroX: {antimicrox_path}")
            self._populate_controller_profiles(config, antimicrox_path, "antimicrox", ".amgp")
            self._apply_tool_defaults(config, 'controller_mapper_path', antimicrox_path, options_args_map)
            return

        keysticks_path = self._find_executable_recursive(bin_dir, KEYSTICKS_EXES) or self._find_executable_recursive(project_dir, KEYSTICKS_EXES)
        if keysticks_path:
            config.controller_mapper_path = keysticks_path
            logging.info(f"Using Keysticks: {keysticks_path}")
            self._populate_controller_profiles(config, keysticks_path, "keysticks", ".keysticks")
            self._apply_tool_defaults(config, 'controller_mapper_path', keysticks_path, options_args_map)
    
    def _populate_controller_profiles(self, config: AppConfig, mapper_path: str, prefix: str, ext: str):
        """Populate controller profiles for Player1, Player2, and Desk."""
        project_dir = Path(constants.APP_ROOT_DIR)
        mapper_dir = Path(mapper_path).parent
        assets_dir = project_dir / "assets"
        
        # Additional search locations in priority order
        search_locations = [
            project_dir,  # $approot
        ]
        
        # Add antimicrox-specific profile location
        if prefix == "antimicrox":
            antimicrox_profiles = Path(os.environ.get("LOCALAPPDATA", "")) / "antimicrox" / "profiles"
            if antimicrox_profiles.exists():
                search_locations.append(antimicrox_profiles)
        
        # Add user documents location
        user_docs = Path.home() / "Documents"
        if user_docs.exists():
            search_locations.append(user_docs)
        
        # Profile mappings: config_attr -> (search_name, template_name, output_name)
        profiles = {
            'p1_profile_path': ('Player1', f'{prefix}_Player{ext}.set', f'Player1{ext}'),
            'p2_profile_path': ('Player2', f'{prefix}_Player{ext}.set', f'Player2{ext}'),
            'desk_profile_path': ('Desk', f'{prefix}_Desk{ext}.set', f'Desk{ext}')
        }
        
        for config_attr, (search_name, template_name, output_name) in profiles.items():
            # Skip if already set
            if getattr(config, config_attr, ""):
                continue
            
            template_path = assets_dir / template_name
            output_path = project_dir / output_name
            
            # Search for existing profile in priority locations
            found_profile = None
            for search_dir in search_locations:
                for file in search_dir.glob(f'*{search_name}*{ext}'):
                    found_profile = str(file)
                    break
                if found_profile:
                    break
            
            # Search in mapper directory and subdirectories
            if not found_profile and mapper_dir.exists():
                for file in mapper_dir.rglob(f'*{search_name}*{ext}'):
                    found_profile = str(file)
                    break
            
            if found_profile:
                setattr(config, config_attr, found_profile)
                config.defaults[f"{config_attr}_enabled"] = True
                config.overwrite_states[config_attr] = True
                config.deployment_path_modes[config_attr] = "LC"
                logging.info(f"Found {search_name} profile: {found_profile}")
            elif not output_path.exists():
                # Create from template only if output doesn't exist
                if template_path.exists():
                    try:
                        # Read template
                        with open(template_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        # Replace tags
                        # [NEWOSK] - path to osk program
                        osk_path = "C:\\Windows\\System32\\osk.exe" if os.name == 'nt' else "/usr/bin/onboard"
                        content = content.replace('[NEWOSK]', osk_path)
                        
                        # [AMICRX] - path to antimicrox.exe
                        if prefix == "antimicrox":
                            content = content.replace('[AMICRX]', mapper_path)
                        else:
                            content = content.replace('[AMICRX]', '')
                        
                        # Write output
                        with open(output_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        
                        setattr(config, config_attr, str(output_path))
                        config.defaults[f"{config_attr}_enabled"] = True
                        config.overwrite_states[config_attr] = True
                        config.deployment_path_modes[config_attr] = "LC"
                        logging.info(f"Created {search_name} layout from template: {output_path}")
                    except Exception as e:
                        logging.error(f"Failed to create {se_name} layout from template: {e}")
            else:
                # Output exists but was not found in search - use it anyway
                setattr(config, config_attr, str(output_path))
                config.defaults[f"{config_attr}_enabled"] = True
                config.overwrite_states[config_attr] = True
                config.deployment_path_modes[config_attr] = "LC"
                logging.info(f"Using existing profile: {output_path}")

    def _detect_borderless_gaming(self, config: AppConfig):
        project_dir = Path(constants.APP_ROOT_DIR)
        bin_dir = project_dir / "bin"
        
        # Load options/arguments for applying defaults
        options_args_map = self._load_options_arguments()
        
        bg_path = self._find_executable_recursive(bin_dir, BORDERLESS_EXES) or self._find_executable_recursive(project_dir, BORDERLESS_EXES)
        if bg_path:
            config.borderless_gaming_path = bg_path
            logging.info(f"Found Borderless Gaming: {bg_path}")
            self._apply_tool_defaults(config, 'borderless_gaming_path', bg_path, options_args_map)

    def _detect_all_bin_tools(self, config: AppConfig):
        """
        Auto-detect all tools in the bin directory and populate config paths.
        This scans recursively for known executables and updates the config.
        Also loads default options and arguments from options_arguments.set.
        """
        project_dir = Path(constants.APP_ROOT_DIR)
        bin_dir = project_dir / "bin"
        
        if not bin_dir.exists():
            logging.warning(f"Bin directory not found: {bin_dir}")
            return
        
        # Load options/arguments mapping
        options_args_map = self._load_options_arguments()
        
        # Define tool mappings: config_attribute -> list of possible exe names
        tool_mappings = {
            'monitorapp_path': MONITOR_EXES,
            'cloud_sync_path': ['rclone.exe', 'rclone', 'ludusavi.exe', 'ludusavi', 'syncthing.exe', 'syncthing', 'emusync.exe', 'emusync'],
            'local_backup_path': ['gamebackupmonitor.exe', 'GameBackupMonitor.exe', 'gamesavemanager.exe', 'GameSaveManager.exe', 'savestate.exe', 'SaveState.exe'],
            'disc_mount_path': ['imgdrive.exe', 'wincdemu.exe', 'osfmount.exe'],
            'wincdemu_exe_path': ['wincdemu.exe'],
            'imgdrive_exe_path': ['imgdrive.exe'],
            'osf_exe_path': ['osfmount.exe', 'osfmount'],
            'cdmage_exe_path': ['cdmage.exe'],
            'audio_tool_path': ['audio_tool.exe', 'AudioTool.exe'],
        }
        
        logging.info("Auto-detecting tools in bin directory...")
        
        for config_attr, exe_names in tool_mappings.items():
            # Skip if already set
            current_value = getattr(config, config_attr, "")
            if current_value and os.path.exists(current_value):
                logging.info(f"{config_attr} already set to: {current_value}")
                continue
            
            # Search for the executable
            found_path = self._find_executable_recursive(bin_dir, exe_names)
            if found_path:
                setattr(config, config_attr, found_path)
                logging.info(f"Auto-detected {config_attr}: {found_path}")
                
                # Apply default options and arguments if available
                self._apply_tool_defaults(config, config_attr, found_path, options_args_map)
            else:
                logging.debug(f"Could not find executable for {config_attr} (looking for: {exe_names})")

        # Auto-detect monitor config profiles (.cfg) near the monitorapp exe
        if config.monitorapp_path:
            mdir = Path(config.monitorapp_path).parent
            if mdir.exists():
                for attr, keyword in [('monitor_game_path', 'gaming'), ('monitor_desk_path', 'desktop')]:
                    if not getattr(config, attr, ''):
                        for f in mdir.glob(f'*{keyword}*.cfg'):
                            setattr(config, attr, str(f))
                            config.defaults[f'{attr}_enabled'] = True
                            logging.info(f"Auto-detected {attr}: {f}")
                            break

        # Detect controller mapper and populate profiles if not already set
        if not config.controller_mapper_path:
            antimicrox_path = self._find_executable_recursive(bin_dir, ANTIMICROX_EXES)
            if antimicrox_path:
                config.controller_mapper_path = antimicrox_path
                logging.info(f"Auto-detected AntimicroX: {antimicrox_path}")
                self._apply_tool_defaults(config, 'controller_mapper_path', antimicrox_path, options_args_map)
                self._populate_controller_profiles(config, antimicrox_path, 'antimicrox', '.amgp')
            else:
                keysticks_path = self._find_executable_recursive(bin_dir, KEYSTICKS_EXES)
                if keysticks_path:
                    config.controller_mapper_path = keysticks_path
                    logging.info(f"Auto-detected Keysticks: {keysticks_path}")
                    self._apply_tool_defaults(config, 'controller_mapper_path', keysticks_path, options_args_map)
                    self._populate_controller_profiles(config, keysticks_path, 'keysticks', '.keysticks')
        elif config.controller_mapper_path and (not config.p1_profile_path or not config.p2_profile_path or not config.desk_profile_path):
            # Controller mapper already set but profiles might be missing - populate them
            mapper_path = config.controller_mapper_path
            if 'antimicrox' in mapper_path.lower():
                self._populate_controller_profiles(config, mapper_path, 'antimicrox', '.amgp')
            elif 'keysticks' in mapper_path.lower():
                self._populate_controller_profiles(config, mapper_path, 'keysticks', '.keysticks')
    
    def _load_options_arguments(self):
        """Load options and arguments from options_arguments.set file."""
        import configparser
        
        mapping = {}
        options_file = Path(constants.APP_ROOT_DIR) / "assets" / "options_arguments.set"
        
        if not options_file.exists():
            logging.warning(f"Options/arguments file not found: {options_file}")
            return mapping
        
        try:
            parser = configparser.ConfigParser(strict=False)
            with open(options_file, 'r', encoding='utf-8-sig') as f:
                parser.read_file(f)
            
            for section in parser.sections():
                options = parser.get(section, 'options', fallback='')
                arguments = parser.get(section, 'arguments', fallback='')
                key = section.lower()
                mapping[key] = (options, arguments)
                config_key = constants.SECTION_TO_CONFIG_KEY.get(
                    constants.canonical_options_section(section))
                if config_key:
                    mapping[config_key] = (options, arguments)
            
            logging.debug(f"Loaded options/arguments for {len(mapping)} tools")
        except Exception as e:
            logging.error(f"Error loading options_arguments.set: {e}")
        
        return mapping
    
    def _apply_tool_defaults(self, config: AppConfig, config_attr: str, tool_path: str, options_args_map: dict):
        """Apply default options and arguments for a detected tool."""
        # Map config attributes to their options/arguments attributes
        attr_mapping = {
            'controller_mapper_path': ('controller_mapper_path_options', 'controller_mapper_path_arguments'),
            'borderless_gaming_path': ('borderless_gaming_path_options', 'borderless_gaming_path_arguments'),
            'monitorapp_path': ('monitorapp_options', 'monitorapp_arguments'),
            'pre1_path': ('pre1_path_options', 'pre1_path_arguments'),
            'pre2_path': ('pre2_path_options', 'pre2_path_arguments'),
            'pre3_path': ('pre3_path_options', 'pre3_path_arguments'),
            'post1_path': ('post1_path_options', 'post1_path_arguments'),
            'post2_path': ('post2_path_options', 'post2_path_arguments'),
            'post3_path': ('post3_path_options', 'post3_path_arguments'),
            'just_after_launch_path': ('just_after_launch_path_options', 'just_after_launch_path_arguments'),
            'just_before_exit_path': ('just_before_exit_path_options', 'just_before_exit_path_arguments'),
            'disc_mount_path': ('disc_mount_path_options', 'disc_mount_path_arguments'),
            'audio_tool_path': ('audio_app_options', 'audio_app_arguments'),
            'p1_profile_path': ('p1_profile_path_options', 'p1_profile_path_arguments'),
            'p2_profile_path': ('p2_profile_path_options', 'p2_profile_path_arguments'),
            'desk_profile_path': ('desk_profile_path_options', 'desk_profile_path_arguments'),
            'monitor_game_path': ('monitor_game_cfg_options', 'monitor_game_cfg_arguments'),
            'monitor_desk_path': ('monitor_desk_cfg_options', 'monitor_desk_cfg_arguments'),
        }
        
        if config_attr not in attr_mapping:
            return
        
        options_attr, arguments_attr = attr_mapping[config_attr]
        
        # Get the executable name
        exe_name = os.path.basename(tool_path).lower()
        exe_no_ext = os.path.splitext(exe_name)[0]
        
        # Check if we have defaults for this tool
        # Lookup order: exe basename, then exe without extension, then config_attr
        defaults = None
        if exe_name in options_args_map:
            defaults = options_args_map[exe_name]
        elif exe_no_ext in options_args_map:
            defaults = options_args_map[exe_no_ext]
        elif config_attr in options_args_map:
            defaults = options_args_map[config_attr]
        
        if defaults:
            options, arguments = defaults
            
            # Only set if not already configured
            current_options = getattr(config, options_attr, "")
            current_arguments = getattr(config, arguments_attr, "")
            
            # Resolve the FIRST EFFECTIVE token (honoring empty-priority) instead
            # of storing the raw pipe-delimited string.  A leading '|' (or empty
            # value) means "no option/argument" -> resolved to empty string so the
            # parameter is omitted when the launcher builds its command.
            resolved_options = self._resolve_first_token(options)
            resolved_arguments = self._resolve_first_token(arguments)
            
            if not current_options and resolved_options:
                setattr(config, options_attr, resolved_options)
                logging.info(f"  Applied default options for {config_attr}: {resolved_options}")
            
            if not current_arguments and resolved_arguments:
                setattr(config, arguments_attr, resolved_arguments)
                logging.info(f"  Applied default arguments for {config_attr}: {resolved_arguments}")

    @staticmethod
    def _resolve_first_token(value):
        """
        Return the first EFFECTIVE token of a pipe-delimited preset string.
        Empty-priority (leading '|' or empty value) resolves to an empty string,
        meaning "no option/argument" (omitted when building launcher parameters).
        Non-pipe values pass through unchanged.
        """
        if not value or not isinstance(value, str):
            return ""
        value = value.strip()
        if value.startswith('|'):
            return ""
        if '|' not in value:
            return value
        first = value.split('|', 1)[0].strip()
        return first
    
    def refresh_tool_paths(self, config: AppConfig):
        """
        Refresh tool paths by re-scanning the bin directory.
        This can be called from the UI to update paths after downloading tools.
        """
        logging.info("Refreshing tool paths from bin directory...")
        self._detect_all_bin_tools(config)
        self.save_config(config)
        logging.info("Tool paths refreshed and saved.")
        return config

    def reset_to_defaults(self, main_window):
        """Resets the configuration to defaults and re-syncs the UI."""
        logging.info("Resetting configuration to defaults.")
        
        # Delete Profiles directory
        if os.path.exists(main_window.config.profiles_dir):
            try:
                shutil.rmtree(main_window.config.profiles_dir)
                logging.info(f"Deleted profiles directory: {main_window.config.profiles_dir}")
            except Exception as e:
                logging.error(f"Failed to delete profiles directory: {e}")

        # Delete Launchers directory
        if os.path.exists(main_window.config.launchers_dir):
            try:
                shutil.rmtree(main_window.config.launchers_dir)
                logging.info(f"Deleted launchers directory: {main_window.config.launchers_dir}")
            except Exception as e:
                logging.error(f"Failed to delete launchers directory: {e}")

        # Create a new default config
        default_config = self._first_run_setup()
        # Save it
        self.save_config(default_config)
        # Update the main window's config instance
        main_window.config = default_config
        # Update the data manager with the new config, preserving the instance
        main_window.data_manager.config = default_config
        # Re-sync the entire UI
        main_window.sync_ui_from_config()
        self.status_updated.emit("Configuration has been reset to defaults.", 4000)