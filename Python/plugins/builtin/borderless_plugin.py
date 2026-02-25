"""
Borderless Gaming plugin
"""

import os
from typing import Dict, List, Optional
from Python.plugins.base_plugin import ToolPlugin, ConfigField, PluginConfig


class BorderlessGamingPlugin(ToolPlugin):
    """Plugin for Borderless Gaming windowing tool"""
    
    @property
    def name(self) -> str:
        return "borderless"
    
    @property
    def display_name(self) -> str:
        return "Borderless Gaming"
    
    @property
    def category(self) -> str:
        return "WINDOWING"
    
    @property
    def description(self) -> str:
        return "Forces games to run in borderless windowed mode"
    
    def get_executable_patterns(self) -> List[str]:
        return [
            "borderless.exe",
            "borderlessgaming.exe",
            "BorderlessGaming.exe"
        ]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'terminate_on_exit': ConfigField(
                name='terminate_on_exit',
                field_type='boolean',
                label='Terminate on Exit',
                required=False,
                default=True,
                help_text='Terminate Borderless Gaming when the game exits'
            )
        }
    
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for launching borderless gaming"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        cmd = f'"{config.tool_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        if config.arguments:
            cmd += f' {config.arguments}'
        
        return cmd
    
    def build_exit_command(self, config: PluginConfig) -> Optional[str]:
        """Borderless Gaming is typically terminated, not restarted"""
        return None
    
    def supports_exit_action(self) -> bool:
        return False  # We just terminate it
    
    def should_track_process(self) -> bool:
        return True
    
    def should_terminate_on_exit(self) -> bool:
        """Check if we should terminate on exit"""
        # This will be checked from config in the sequence executor
        return True
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://github.com/Codeusa/Borderless-Gaming"
