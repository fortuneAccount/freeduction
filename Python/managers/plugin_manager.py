"""
Plugin manager for handling plugin lifecycle and tool discovery
"""

import os
import logging
from typing import Dict, List, Optional
from pathlib import Path

from Python.plugins.registry import PluginRegistry
from Python.plugins.base_plugin import ToolPlugin


class PluginManager:
    """
    Manages plugin lifecycle and tool discovery.
    
    Responsibilities:
    - Load and register plugins
    - Scan for installed tools
    - Provide access to plugin registry
    - Support dependency injection
    """
    
    def __init__(self, bin_directory: str = None, registry: PluginRegistry = None):
        """
        Initialize the plugin manager.
        
        Args:
            bin_directory: Path to the bin directory to scan for tools (optional, uses DI if None)
            registry: Plugin registry instance (optional, creates new if None)
        """
        self.registry = registry if registry is not None else PluginRegistry()
        self.bin_directory = bin_directory
        self.installed_tools: Dict[str, List[str]] = {}
        self.logger = logging.getLogger(__name__)
        
        # Support for dependency injection
        self._container = None
    
    def set_container(self, container):
        """
        Set the dependency injection container.
        
        Args:
            container: DependencyContainer instance
        """
        self._container = container
    
    def get_service(self, name: str):
        """
        Get a service from the dependency container.
        
        Args:
            name: Service name
            
        Returns:
            Service instance or None
        """
        if self._container:
            return self._container.resolve(name)
        return None
    
    def load_builtin_plugins(self):
        """Load all built-in plugins from Python/plugins/builtin/"""
        builtin_dir = Path(__file__).parent.parent / 'plugins' / 'builtin'
        
        if not builtin_dir.exists():
            self.logger.warning(f"Built-in plugins directory not found: {builtin_dir}")
            return
        
        # Import and register each plugin
        try:
            from Python.plugins.builtin.antimicrox_plugin import AntiMicroXPlugin
            self.registry.register(AntiMicroXPlugin())
            self.logger.info("Loaded AntiMicroX plugin")
        except ImportError as e:
            self.logger.warning(f"Could not load AntiMicroX plugin: {e}")
        
        try:
            from Python.plugins.builtin.borderless_plugin import BorderlessGamingPlugin
            self.registry.register(BorderlessGamingPlugin())
            self.logger.info("Loaded Borderless Gaming plugin")
        except ImportError as e:
            self.logger.warning(f"Could not load Borderless Gaming plugin: {e}")
        
        try:
            from Python.plugins.builtin.multimonitor_plugin import MultiMonitorToolPlugin
            self.registry.register(MultiMonitorToolPlugin())
            self.logger.info("Loaded MultiMonitorTool plugin")
        except ImportError as e:
            self.logger.warning(f"Could not load MultiMonitorTool plugin: {e}")
        
        try:
            from Python.plugins.builtin.cloud_backup_plugin import RcloneBackupPlugin, LudusaviBackupPlugin
            self.registry.register(RcloneBackupPlugin())
            self.registry.register(LudusaviBackupPlugin())
            self.logger.info("Loaded cloud backup plugins")
        except ImportError as e:
            self.logger.warning(f"Could not load cloud backup plugins: {e}")
        
        self.logger.info(f"Loaded {self.registry.get_plugin_count()} built-in plugins")
    
    def scan_for_installed_tools(self) -> Dict[str, List[str]]:
        """
        Scan the bin directory for installed tools.
        
        Returns:
            Dictionary mapping plugin names to lists of found executable paths
        """
        self.installed_tools.clear()
        
        if not os.path.exists(self.bin_directory):
            self.logger.warning(f"Bin directory does not exist: {self.bin_directory}")
            return self.installed_tools
        
        for plugin in self.registry.get_all_plugins():
            paths = self._find_executables_for_plugin(plugin)
            if paths:
                self.installed_tools[plugin.name] = paths
                self.logger.info(f"Found {len(paths)} installation(s) of {plugin.display_name}")
        
        return self.installed_tools
    
    def _find_executables_for_plugin(self, plugin: ToolPlugin) -> List[str]:
        """
        Find all executables for a given plugin.
        
        Args:
            plugin: The plugin to search for
            
        Returns:
            List of absolute paths to found executables
        """
        patterns = plugin.get_executable_patterns()
        patterns_lower = [p.lower() for p in patterns]
        found_paths = []
        
        # Search recursively in bin directory
        for root, dirs, files in os.walk(self.bin_directory):
            for file in files:
                if file.lower() in patterns_lower:
                    full_path = os.path.join(root, file)
                    if full_path not in found_paths:
                        found_paths.append(full_path)
        
        return found_paths
    
    def get_installed_tool_path(self, plugin_name: str, index: int = 0) -> Optional[str]:
        """
        Get the path to an installed tool.
        
        Args:
            plugin_name: Name of the plugin
            index: Index if multiple installations exist (default: 0)
            
        Returns:
            Path to the tool or None if not found
        """
        paths = self.installed_tools.get(plugin_name, [])
        if index < len(paths):
            return paths[index]
        return None
    
    def is_tool_installed(self, plugin_name: str) -> bool:
        """Check if a tool is installed"""
        return plugin_name in self.installed_tools and len(self.installed_tools[plugin_name]) > 0
    
    def get_plugin_for_executable(self, executable_path: str) -> Optional[ToolPlugin]:
        """
        Find the plugin that matches a given executable path.
        
        Args:
            executable_path: Path to an executable
            
        Returns:
            Matching plugin or None
        """
        exe_name = os.path.basename(executable_path)
        plugins = self.registry.find_plugins_by_executable(exe_name)
        
        if plugins:
            return plugins[0]  # Return first match
        return None
    
    def refresh_installed_tools(self):
        """Refresh the list of installed tools"""
        self.scan_for_installed_tools()
