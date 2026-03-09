"""
AntiMicroX controller mapper plugin
"""

import os
from typing import Dict, List, Optional
from Python.plugins.base_plugin import ToolPlugin, ConfigField, PluginConfig


class AntiMicroXPlugin(ToolPlugin):
    """Plugin for AntiMicroX controller mapping software"""
    
    @property
    def name(self) -> str:
        return "antimicrox"
    
    @property
    def display_name(self) -> str:
        return "AntiMicroX"
    
    @property
    def category(self) -> str:
        return "MAPPERS"
    
    @property
    def description(self) -> str:
        return "Controller to keyboard/mouse mapper"
    
    def get_executable_patterns(self) -> List[str]:
        return ["antimicrox.exe", "AntiMicroX.exe"]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'player1_profile': ConfigField(
                name='player1_profile',
                field_type='file',
                label='Player 1 Profile',
                required=False,
                filter='AntiMicroX Profiles (*.amgp);;All Files (*.*)',
                help_text='Controller profile for Player 1'
            ),
            'player2_profile': ConfigField(
                name='player2_profile',
                field_type='file',
                label='Player 2 Profile',
                required=False,
                filter='AntiMicroX Profiles (*.amgp);;All Files (*.*)',
                help_text='Controller profile for Player 2'
            ),
            'mediacenter_profile': ConfigField(
                name='mediacenter_profile',
                field_type='file',
                label='Media Center Profile',
                required=False,
                filter='AntiMicroX Profiles (*.amgp);;All Files (*.*)',
                help_text='Controller profile for media center/desktop use'
            )
        }
    
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for game launch (uses player profiles)"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        p1_profile = config.get_field('player1_profile')
        if not p1_profile or not os.path.exists(p1_profile):
            return None
        
        # Build base command
        cmd = f'"{config.tool_path}"'
        
        # Add options if specified
        if config.options:
            cmd += f' {config.options}'
        
        # Add tray and hidden flags
        cmd += ' --tray --hidden'
        
        # Add player 1 profile
        cmd += f' --profile "{p1_profile}"'
        
        # Add arguments if specified
        if config.arguments:
            cmd += f' {config.arguments}'
        
        # Add player 2 profile if available
        p2_profile = config.get_field('player2_profile')
        if p2_profile and os.path.exists(p2_profile):
            cmd += f' --next --profile-controller 2 --profile "{p2_profile}"'
        
        return cmd
    
    def build_exit_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for exit sequence (uses media center profile)"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        mc_profile = config.get_field('mediacenter_profile')
        if not mc_profile or not os.path.exists(mc_profile):
            return None
        
        # Build command with media center profile
        cmd = f'"{config.tool_path}" --tray --hidden --profile "{mc_profile}"'
        
        return cmd
    
    def supports_exit_action(self) -> bool:
        return True
    
    def should_track_process(self) -> bool:
        return True
    
    def should_terminate_on_exit(self) -> bool:
        return False  # We restart with media center profile instead
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://github.com/AntiMicroX/antimicrox"
