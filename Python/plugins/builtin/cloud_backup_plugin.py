"""
Cloud backup plugin for save games and configuration files
Supports rclone, ludusavi, and other backup tools
"""

import os
from typing import Dict, List, Optional
from Python.plugins.base_plugin import ToolPlugin, ConfigField, PluginConfig


class RcloneBackupPlugin(ToolPlugin):
    """Plugin for rclone cloud backup"""
    
    @property
    def name(self) -> str:
        return "rclone"
    
    @property
    def display_name(self) -> str:
        return "Rclone Cloud Backup"
    
    @property
    def category(self) -> str:
        return "SYNC"
    
    @property
    def description(self) -> str:
        return "Sync save games and configs to cloud storage"
    
    def get_executable_patterns(self) -> List[str]:
        return ["rclone.exe"]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'remote_name': ConfigField(
                name='remote_name',
                field_type='string',
                label='Remote Name',
                required=True,
                help_text='Name of the rclone remote (e.g., "gdrive:", "dropbox:")'
            ),
            'local_path': ConfigField(
                name='local_path',
                field_type='directory',
                label='Local Save Directory',
                required=True,
                help_text='Local directory containing save games'
            ),
            'remote_path': ConfigField(
                name='remote_path',
                field_type='string',
                label='Remote Path',
                required=True,
                help_text='Path on remote storage (e.g., "GameSaves/MyGame")'
            ),
            'sync_mode': ConfigField(
                name='sync_mode',
                field_type='string',
                label='Sync Mode',
                required=False,
                default='sync',
                help_text='Sync mode: sync (bidirectional), copy (upload only), or copyto (download only)'
            ),
            'backup_on_launch': ConfigField(
                name='backup_on_launch',
                field_type='boolean',
                label='Backup on Launch',
                required=False,
                default=False,
                help_text='Download saves from cloud before game starts'
            ),
            'backup_on_exit': ConfigField(
                name='backup_on_exit',
                field_type='boolean',
                label='Backup on Exit',
                required=False,
                default=True,
                help_text='Upload saves to cloud after game exits'
            )
        }
    
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for downloading saves before game launch"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        # Check if backup on launch is enabled
        if not config.get_field('backup_on_launch', False):
            return None
        
        remote_name = config.get_field('remote_name')
        local_path = config.get_field('local_path')
        remote_path = config.get_field('remote_path')
        
        if not all([remote_name, local_path, remote_path]):
            return None
        
        # Build sync command (download from cloud)
        sync_mode = config.get_field('sync_mode', 'sync')
        cmd = f'"{config.tool_path}" {sync_mode} "{remote_name}{remote_path}" "{local_path}"'
        
        # Add common flags
        cmd += ' --verbose --progress'
        
        if config.options:
            cmd += f' {config.options}'
        
        if config.arguments:
            cmd += f' {config.arguments}'
        
        return cmd
    
    def build_exit_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for uploading saves after game exit"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        # Check if backup on exit is enabled
        if not config.get_field('backup_on_exit', True):
            return None
        
        remote_name = config.get_field('remote_name')
        local_path = config.get_field('local_path')
        remote_path = config.get_field('remote_path')
        
        if not all([remote_name, local_path, remote_path]):
            return None
        
        # Build sync command (upload to cloud)
        sync_mode = config.get_field('sync_mode', 'sync')
        cmd = f'"{config.tool_path}" {sync_mode} "{local_path}" "{remote_name}{remote_path}"'
        
        # Add common flags
        cmd += ' --verbose --progress'
        
        if config.options:
            cmd += f' {config.options}'
        
        if config.arguments:
            cmd += f' {config.arguments}'
        
        return cmd
    
    def supports_exit_action(self) -> bool:
        return True
    
    def should_track_process(self) -> bool:
        return False  # Sync runs and completes
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://rclone.org/docs/"


class LudusaviBackupPlugin(ToolPlugin):
    """Plugin for Ludusavi game save backup"""
    
    @property
    def name(self) -> str:
        return "ludusavi"
    
    @property
    def display_name(self) -> str:
        return "Ludusavi Save Backup"
    
    @property
    def category(self) -> str:
        return "SYNC"
    
    @property
    def description(self) -> str:
        return "Backup and restore game saves using Ludusavi"
    
    def get_executable_patterns(self) -> List[str]:
        return ["ludusavi.exe", "Ludusavi.exe"]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'backup_path': ConfigField(
                name='backup_path',
                field_type='directory',
                label='Backup Directory',
                required=True,
                help_text='Directory where backups are stored'
            ),
            'game_name': ConfigField(
                name='game_name',
                field_type='string',
                label='Game Name',
                required=False,
                help_text='Specific game to backup (leave empty for all)'
            ),
            'backup_on_launch': ConfigField(
                name='backup_on_launch',
                field_type='boolean',
                label='Restore on Launch',
                required=False,
                default=False,
                help_text='Restore saves before game starts'
            ),
            'backup_on_exit': ConfigField(
                name='backup_on_exit',
                field_type='boolean',
                label='Backup on Exit',
                required=False,
                default=True,
                help_text='Backup saves after game exits'
            )
        }
    
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for restoring saves before game launch"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        if not config.get_field('backup_on_launch', False):
            return None
        
        backup_path = config.get_field('backup_path')
        if not backup_path:
            return None
        
        cmd = f'"{config.tool_path}" restore --path "{backup_path}"'
        
        game_name = config.get_field('game_name')
        if game_name:
            cmd += f' --by-name "{game_name}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        return cmd
    
    def build_exit_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for backing up saves after game exit"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        if not config.get_field('backup_on_exit', True):
            return None
        
        backup_path = config.get_field('backup_path')
        if not backup_path:
            return None
        
        cmd = f'"{config.tool_path}" backup --path "{backup_path}"'
        
        game_name = config.get_field('game_name')
        if game_name:
            cmd += f' --by-name "{game_name}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        return cmd
    
    def supports_exit_action(self) -> bool:
        return True
    
    def should_track_process(self) -> bool:
        return False
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://github.com/mtkennerly/ludusavi"


class SyncthingBackupPlugin(ToolPlugin):
    """Plugin for Syncthing continuous file synchronization"""
    
    @property
    def name(self) -> str:
        return "syncthing"
    
    @property
    def display_name(self) -> str:
        return "Syncthing Sync"
    
    @property
    def category(self) -> str:
        return "SYNC"
    
    @property
    def description(self) -> str:
        return "Continuous file synchronization across devices"
    
    def get_executable_patterns(self) -> List[str]:
        return ["syncthing.exe", "syncthing"]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'sync_folder': ConfigField(
                name='sync_folder',
                field_type='directory',
                label='Sync Folder',
                required=True,
                help_text='Local folder to synchronize'
            ),
            'auto_start': ConfigField(
                name='auto_start',
                field_type='boolean',
                label='Auto Start',
                required=False,
                default=True,
                help_text='Start Syncthing automatically with game'
            )
        }
    
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for starting Syncthing"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        if not config.get_field('auto_start', True):
            return None
        
        cmd = f'"{config.tool_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        if config.arguments:
            cmd += f' {config.arguments}'
        
        return cmd
    
    def supports_exit_action(self) -> bool:
        return True
    
    def should_track_process(self) -> bool:
        return True  # Syncthing runs continuously
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://docs.syncthing.net/"


class EmuSyncPlugin(ToolPlugin):
    """Plugin for EmuSync emulator save synchronization"""
    
    @property
    def name(self) -> str:
        return "emusync"
    
    @property
    def display_name(self) -> str:
        return "EmuSync"
    
    @property
    def category(self) -> str:
        return "SYNC"
    
    @property
    def description(self) -> str:
        return "Synchronize emulator saves and states"
    
    def get_executable_patterns(self) -> List[str]:
        return ["emusync.exe", "emusync"]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'emulator_path': ConfigField(
                name='emulator_path',
                field_type='directory',
                label='Emulator Directory',
                required=True,
                help_text='Path to emulator installation'
            ),
            'sync_on_launch': ConfigField(
                name='sync_on_launch',
                field_type='boolean',
                label='Sync on Launch',
                required=False,
                default=True,
                help_text='Download saves before game starts'
            ),
            'sync_on_exit': ConfigField(
                name='sync_on_exit',
                field_type='boolean',
                label='Sync on Exit',
                required=False,
                default=True,
                help_text='Upload saves after game exits'
            )
        }
    
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for syncing before launch"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        if not config.get_field('sync_on_launch', True):
            return None
        
        emulator_path = config.get_field('emulator_path')
        if not emulator_path:
            return None
        
        cmd = f'"{config.tool_path}" sync --path "{emulator_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        return cmd
    
    def build_exit_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for syncing after exit"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        if not config.get_field('sync_on_exit', True):
            return None
        
        emulator_path = config.get_field('emulator_path')
        if not emulator_path:
            return None
        
        cmd = f'"{config.tool_path}" sync --path "{emulator_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        return cmd
    
    def supports_exit_action(self) -> bool:
        return True
    
    def should_track_process(self) -> bool:
        return False
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://github.com/emusync/emusync"


class GameBackupMonitorPlugin(ToolPlugin):
    """Plugin for Game Backup Monitor"""
    
    @property
    def name(self) -> str:
        return "gamebackupmonitor"
    
    @property
    def display_name(self) -> str:
        return "Game Backup Monitor"
    
    @property
    def category(self) -> str:
        return "LOCAL_BACKUP"
    
    @property
    def description(self) -> str:
        return "Automatically backup game saves when they change"
    
    def get_executable_patterns(self) -> List[str]:
        return ["gamebackupmonitor.exe", "GameBackupMonitor.exe"]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'backup_path': ConfigField(
                name='backup_path',
                field_type='directory',
                label='Backup Directory',
                required=True,
                help_text='Directory where backups are stored'
            ),
            'monitor_on_launch': ConfigField(
                name='monitor_on_launch',
                field_type='boolean',
                label='Monitor on Launch',
                required=False,
                default=True,
                help_text='Start monitoring when game launches'
            )
        }
    
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for starting Game Backup Monitor"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        if not config.get_field('monitor_on_launch', True):
            return None
        
        backup_path = config.get_field('backup_path')
        if not backup_path:
            return None
        
        cmd = f'"{config.tool_path}" --backup-path "{backup_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        if config.arguments:
            cmd += f' {config.arguments}'
        
        return cmd
    
    def supports_exit_action(self) -> bool:
        return True
    
    def should_track_process(self) -> bool:
        return True  # Runs continuously
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://github.com/MikeMaximus/gbm"


class GameSaveManagerPlugin(ToolPlugin):
    """Plugin for Game Save Manager"""
    
    @property
    def name(self) -> str:
        return "gamesavemanager"
    
    @property
    def display_name(self) -> str:
        return "Game Save Manager"
    
    @property
    def category(self) -> str:
        return "LOCAL_BACKUP"
    
    @property
    def description(self) -> str:
        return "Backup and restore game saves"
    
    def get_executable_patterns(self) -> List[str]:
        return ["gamesavemanager.exe", "GameSaveManager.exe"]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'backup_path': ConfigField(
                name='backup_path',
                field_type='directory',
                label='Backup Directory',
                required=True,
                help_text='Directory where backups are stored'
            ),
            'backup_on_exit': ConfigField(
                name='backup_on_exit',
                field_type='boolean',
                label='Backup on Exit',
                required=False,
                default=True,
                help_text='Backup saves after game exits'
            )
        }
    
    def build_exit_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for backing up saves after exit"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        if not config.get_field('backup_on_exit', True):
            return None
        
        backup_path = config.get_field('backup_path')
        if not backup_path:
            return None
        
        cmd = f'"{config.tool_path}" backup --path "{backup_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        return cmd
    
    def supports_exit_action(self) -> bool:
        return True
    
    def should_track_process(self) -> bool:
        return False
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://www.gamesave-manager.com/"


class SaveStatePlugin(ToolPlugin):
    """Plugin for Save State backup tool"""
    
    @property
    def name(self) -> str:
        return "savestate"
    
    @property
    def display_name(self) -> str:
        return "Save State"
    
    @property
    def category(self) -> str:
        return "LOCAL_BACKUP"
    
    @property
    def description(self) -> str:
        return "Create and manage save state backups"
    
    def get_executable_patterns(self) -> List[str]:
        return ["savestate.exe", "SaveState.exe"]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'backup_path': ConfigField(
                name='backup_path',
                field_type='directory',
                label='Backup Directory',
                required=True,
                help_text='Directory where save states are stored'
            ),
            'auto_backup': ConfigField(
                name='auto_backup',
                field_type='boolean',
                label='Auto Backup',
                required=False,
                default=True,
                help_text='Automatically create save states'
            )
        }
    
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for creating save state before launch"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        if not config.get_field('auto_backup', True):
            return None
        
        backup_path = config.get_field('backup_path')
        if not backup_path:
            return None
        
        cmd = f'"{config.tool_path}" create --path "{backup_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        return cmd
    
    def build_exit_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for creating save state after exit"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        if not config.get_field('auto_backup', True):
            return None
        
        backup_path = config.get_field('backup_path')
        if not backup_path:
            return None
        
        cmd = f'"{config.tool_path}" create --path "{backup_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        return cmd
    
    def supports_exit_action(self) -> bool:
        return True
    
    def should_track_process(self) -> bool:
        return False
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://github.com/savestate/savestate"
