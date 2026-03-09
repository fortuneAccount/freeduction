"""
MultiMonitorTool plugin
"""

import os
from typing import Dict, List, Optional
from Python.plugins.base_plugin import ToolPlugin, ConfigField, PluginConfig


class MultiMonitorToolPlugin(ToolPlugin):
    """Plugin for NirSoft MultiMonitorTool"""
    
    @property
    def name(self) -> str:
        return "multimonitortool"
    
    @property
    def display_name(self) -> str:
        return "MultiMonitorTool"
    
    @property
    def category(self) -> str:
        return "DISPLAY"
    
    @property
    def description(self) -> str:
        return "Manage multiple monitor configurations"
    
    def get_executable_patterns(self) -> List[str]:
        return ["multimonitortool.exe", "MultiMonitorTool.exe"]
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        return {
            'gaming_config': ConfigField(
                name='gaming_config',
                field_type='file',
                label='Gaming Monitor Config',
                required=False,
                filter='Config Files (*.cfg);;All Files (*.*)',
                help_text='Monitor configuration for gaming'
            ),
            'desktop_config': ConfigField(
                name='desktop_config',
                field_type='file',
                label='Desktop Monitor Config',
                required=False,
                filter='Config Files (*.cfg);;All Files (*.*)',
                help_text='Monitor configuration for desktop/media center'
            )
        }
    
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for applying gaming monitor config"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        gaming_config = config.get_field('gaming_config')
        if not gaming_config or not os.path.exists(gaming_config):
            return None
        
        cmd = f'"{config.tool_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        cmd += f' /load "{gaming_config}"'
        
        if config.arguments:
            cmd += f' {config.arguments}'
        
        return cmd
    
    def build_exit_command(self, config: PluginConfig) -> Optional[str]:
        """Build command for restoring desktop monitor config"""
        if not config.tool_path or not os.path.exists(config.tool_path):
            return None
        
        desktop_config = config.get_field('desktop_config')
        if not desktop_config or not os.path.exists(desktop_config):
            return None
        
        cmd = f'"{config.tool_path}"'
        
        if config.options:
            cmd += f' {config.options}'
        
        cmd += f' /load "{desktop_config}"'
        
        if config.arguments:
            cmd += f' {config.arguments}'
        
        return cmd
    
    def supports_exit_action(self) -> bool:
        return True
    
    def should_track_process(self) -> bool:
        return False  # Runs and exits immediately
    
    def get_documentation_url(self) -> Optional[str]:
        return "https://www.nirsoft.net/utils/multi_monitor_tool.html"
