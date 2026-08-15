class AppConfig:
    """Data class to hold all application configuration."""
    def __init__(self):
        # Setup Tab: Main Settings
        self.source_dirs = []
        self.excluded_dirs = []
        self.logging_verbosity = "Debug"
        self.ui_theme: str = "Universal"
        self.plugin_creation_mode: bool = False
        self.game_managers_present = "None"
        self.exclude_selected_manager_games = False
        self.ui_font_family = ""
        self.ui_font_size = 9
        self.editor_font_family = ""
        self.editor_font_size = 9
        self.menu_expand_duration = 220
        self.menu_collapse_duration = 168
        self.menu_easing = "InBack"

        # Setup Tab: Element & Application Locations
        self.profiles_dir = ""
        self.launchers_dir = ""
        self.launcher_executable = ""
        self.controller_mapper_path = ""
        self.borderless_gaming_path = ""
        self.p1_profile_path = ""
        self.p2_profile_path = ""
        self.desk_profile_path = ""
        self.monitorapp_path = ""
        self.monitor_game_path = ""
        self.monitor_desk_path = ""
        self.filtered_steam_cache_path = ""
        
        # Pre/Post launch apps
        self.pre1_path = ""
        self.pre2_path = ""
        self.pre3_path = ""
        self.post1_path = ""
        self.post2_path = ""
        self.post3_path = ""
        
        # Just Before/After launch apps
        self.just_after_launch_path = ""
        self.just_before_exit_path = ""
        # Disc mount/unmount tools
        self.native_mount_path = ""
        self.wincdemu_exe_path = ""
        self.cdmage_exe_path = ""
        self.osf_exe_path = ""
        self.imgdrive_exe_path = ""
        self.custom_mount_path = ""
        self.disc_mount_path = ""
        
        # Disc mount/unmount config
        self.disc_mount_cfg = ""
        self.disc_unmount_cfg = ""
        
        # Audio tool
        self.audio_tool_path = ""
        
        # Audio config file paths
        self.audio_game_cfg = ""
        self.audio_desk_cfg = ""
        
        # Cloud backup tools
        self.rclone_path = ""
        self.ludusavi_path = ""
        self.cloud_backup_path = ""  # Generic cloud backup tool

        # App Options & Arguments
        self.controller_mapper_path_options = ""
        self.controller_mapper_path_arguments = ""
        self.borderless_gaming_path_options = ""
        self.borderless_gaming_path_arguments = ""
        self.monitorapp_options = ""
        self.monitorapp_arguments = ""
        self.p1_profile_path_options = ""
        self.p1_profile_path_arguments = ""
        self.p2_profile_path_options = ""
        self.p2_profile_path_arguments = ""
        self.desk_profile_path_options = ""
        self.desk_profile_path_arguments = ""
        self.monitor_game_cfg_options = ""
        self.monitor_game_cfg_arguments = ""
        self.monitor_desk_cfg_options = ""
        self.monitor_desk_cfg_arguments = ""
        
        self.just_after_launch_path_options = ""
        self.just_after_launch_path_arguments = ""
        self.just_before_exit_path_options = ""
        self.just_before_exit_path_arguments = ""
        self.disc_mount_path_options = ""
        self.disc_mount_path_arguments = ""
        
        # Audio app options & arguments
        self.audio_app_options = ""
        self.audio_app_arguments = ""
        
        # Config file options & arguments
        self.disc_mount_cfg_options = ""
        self.disc_mount_cfg_arguments = ""
        self.disc_unmount_cfg_options = ""
        self.disc_unmount_cfg_arguments = ""
        self.audio_game_cfg_options = ""
        self.audio_game_cfg_arguments = ""
        self.audio_desk_cfg_options = ""
        self.audio_desk_cfg_arguments = ""
        
        # Unborder/reborder config paths
        self.unborder_cfg = ""
        self.reborder_cfg = ""
        self.unborder_cfg_options = ""
        self.unborder_cfg_arguments = ""
        self.reborder_cfg_options = ""
        self.reborder_cfg_arguments = ""
        
        # Cloud backup options & arguments
        self.rclone_path_options = ""
        self.rclone_path_arguments = ""
        self.ludusavi_path_options = ""
        self.ludusavi_path_arguments = ""
        self.cloud_backup_path_options = ""
        self.cloud_backup_path_arguments = ""
        
        # Rclone-specific configuration
        self.rclone_remote_name = ""
        self.rclone_local_path = ""
        self.rclone_remote_path = ""
        self.rclone_sync_mode = "sync"
        self.rclone_backup_on_launch = False
        self.rclone_backup_on_exit = True
        
        # Ludusavi-specific configuration
        self.ludusavi_backup_path = ""
        self.ludusavi_game_name = ""
        self.ludusavi_backup_on_launch = False
        self.ludusavi_backup_on_exit = True
        
        # Syncthing-specific configuration
        self.syncthing_sync_folder = ""
        self.syncthing_auto_start = True
        
        # EmuSync-specific configuration
        self.emusync_emulator_path = ""
        self.emusync_sync_on_launch = True
        self.emusync_sync_on_exit = True
        
        # Audio app run-wait
        self.audio_app_run_wait = False
        
        # Game Backup Monitor-specific configuration
        self.gbm_backup_path = ""
        self.gbm_monitor_on_launch = True
        
        # Game Save Manager-specific configuration
        self.gsm_backup_path = ""
        self.gsm_backup_on_exit = True
        
        # Save State-specific configuration
        self.savestate_backup_path = ""
        self.savestate_auto_backup = True
        
        self.pre1_path_options = ""
        self.pre1_path_arguments = ""
        self.pre2_path_options = ""
        self.pre2_path_arguments = ""
        self.pre3_path_options = ""
        self.pre3_path_arguments = ""
        
        self.post1_path_options = ""
        self.post1_path_arguments = ""
        self.post2_path_options = ""
        self.post2_path_arguments = ""
        self.post3_path_options = ""
        self.post3_path_arguments = ""
        self.launcher_executable_options = ""
        self.launcher_executable_arguments = ""

        # Setup Tab: Propagation Status (CEN/LC modes)
        self.deployment_path_modes = {}
        
        # CEN/LC states for profile paths
        self.p1_profile_mode = "CEN"  # or "LC"
        self.p2_profile_mode = "CEN"
        self.desk_profile_mode = "CEN"
        self.monitor_game_mode = "CEN"
        self.monitor_desk_mode = "CEN"

        # Setup Tab: Behavior
        self.editor_page_size = 50

        # Setup Tab: Execution Sequences
        self.launch_sequence = []
        self.exit_sequence = []

        # Deployment Tab: General Options
        self.download_game_json = True
        self.overwrite_game_json = True
        self.download_artwork = True
        self.overwrite_artwork = True
        self.download_pcgw_metadata = True
        self.overwrite_pcgw_metadata = True
        self.overwrite_game_ini = True
        self.recreate_game_ini = True
        self.hide_taskbar = False
        self.run_as_admin = False
        self.enable_name_matching = True
        self.fuzzy_match_cutoff = 0.6
        self.auto_flag_existing = True
        self.use_kill_list = True
        self.terminate_borderless_on_exit = True

        # Deployment Tab: Creation Options
        self.create_overwrite_joystick_profiles = False

        # Enable toggles for applications defined in Setup -> Applications
        self.enable_controller_mapper = False
        self.enable_borderless_app = False
        self.enable_monitorapp = False
        self.enable_after_launch_app = False
        self.enable_before_exit_app = False
        self.enable_cloud_backup = False
        self.enable_pre1 = False
        self.enable_pre2 = False
        self.enable_pre3 = False
        self.enable_post1 = False
        self.enable_post2 = False
        self.enable_post3 = False
        self.enable_audio_app = False
        self.enable_unborder_cfg = False
        self.enable_reborder_cfg = False
        self.disc_mount_cfg_enabled = False
        self.disc_unmount_cfg_enabled = False
        self.cloud_sync_path_options = ""
        self.cloud_sync_path_arguments = ""
        self.local_backup_path_options = ""
        self.local_backup_path_arguments = ""
        self.monitor_game_enabled = True
        self.monitor_desk_enabled = True
        self.p1_profile_enabled = True
        self.p2_profile_enabled = True
        self.desk_profile_enabled = True
        self.audio_game_cfg_enabled = False
        self.audio_desk_cfg_enabled = False
        self.unborder_cfg_enabled = False
        self.reborder_cfg_enabled = False

        # Tool plugin-gated feature visibility (tool names comma-separated)
        self.enabled_tools = ""

        # Other settings not directly on UI
        self.app_directory = ""
        self.current_settings = ""

        # Default enabled states for various features
        self.defaults = {}

        # Overwrite states for paths (Deployment Tab -> Creation)
        # Enabled by default for all deployable paths.
        self.overwrite_states = {
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

        # Default run-wait states for various features
        self.run_wait_states = {}
