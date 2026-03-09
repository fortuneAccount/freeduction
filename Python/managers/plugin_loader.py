"""
Plugin hot-reloading system

Supports dynamic loading, unloading, and reloading of plugins without restarting.
"""

import os
import sys
import importlib
import importlib.util
import logging
from typing import Dict, List, Optional, Type
from pathlib import Path
import time

from Python.plugins.base_plugin import ToolPlugin
from Python.plugins.registry import PluginRegistry


class PluginLoader:
    """
    Handles dynamic plugin loading and hot-reloading.
    
    Features:
    - Load plugins from directories
    - Hot-reload changed plugins
    - Unload plugins
    - Watch for file changes
    """
    
    def __init__(self, registry: PluginRegistry):
        """
        Initialize the plugin loader.
        
        Args:
            registry: Plugin registry to register loaded plugins
        """
        self.registry = registry
        self.logger = logging.getLogger(__name__)
        self.loaded_modules: Dict[str, any] = {}
        self.plugin_paths: Dict[str, str] = {}  # plugin_name -> file_path
        self.file_mtimes: Dict[str, float] = {}  # file_path -> modification time
    
    def load_plugin_from_file(self, file_path: str) -> Optional[ToolPlugin]:
        """
        Load a plugin from a Python file.
        
        Args:
            file_path: Path to the plugin file
            
        Returns:
            Loaded plugin instance or None if failed
        """
        try:
            # Generate module name from file path
            module_name = f"dynamic_plugin_{Path(file_path).stem}_{int(time.time())}"
            
            # Load the module
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec is None or spec.loader is None:
                self.logger.error(f"Could not load spec for {file_path}")
                return None
            
            module = importlib.util.module_from_spec(spec)
            sys.modules[module_name] = module
            spec.loader.exec_module(module)
            
            # Find ToolPlugin subclasses in the module
            plugin_classes = []
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if (isinstance(attr, type) and 
                    issubclass(attr, ToolPlugin) and 
                    attr is not ToolPlugin):
                    plugin_classes.append(attr)
            
            if not plugin_classes:
                self.logger.warning(f"No ToolPlugin subclasses found in {file_path}")
                return None
            
            # Instantiate the first plugin class found
            plugin_class = plugin_classes[0]
            plugin = plugin_class()
            
            # Track the module and file
            self.loaded_modules[plugin.name] = module
            self.plugin_paths[plugin.name] = file_path
            self.file_mtimes[file_path] = os.path.getmtime(file_path)
            
            # Register with registry
            self.registry.register(plugin)
            
            self.logger.info(f"Loaded plugin: {plugin.display_name} from {file_path}")
            return plugin
            
        except Exception as e:
            self.logger.error(f"Failed to load plugin from {file_path}: {e}", exc_info=True)
            return None
    
    def load_plugins_from_directory(self, directory: str, recursive: bool = False) -> List[ToolPlugin]:
        """
        Load all plugins from a directory.
        
        Args:
            directory: Directory to scan
            recursive: Whether to scan subdirectories
            
        Returns:
            List of loaded plugins
        """
        loaded = []
        
        if not os.path.exists(directory):
            self.logger.warning(f"Plugin directory does not exist: {directory}")
            return loaded
        
        pattern = "**/*.py" if recursive else "*.py"
        plugin_files = Path(directory).glob(pattern)
        
        for file_path in plugin_files:
            # Skip __init__.py and private files
            if file_path.name.startswith('_'):
                continue
            
            plugin = self.load_plugin_from_file(str(file_path))
            if plugin:
                loaded.append(plugin)
        
        self.logger.info(f"Loaded {len(loaded)} plugins from {directory}")
        return loaded
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """
        Unload a plugin.
        
        Args:
            plugin_name: Name of the plugin to unload
            
        Returns:
            True if unloaded successfully
        """
        if plugin_name not in self.loaded_modules:
            self.logger.warning(f"Plugin not loaded: {plugin_name}")
            return False
        
        try:
            # Unregister from registry
            self.registry.unregister(plugin_name)
            
            # Remove from tracking
            module = self.loaded_modules.pop(plugin_name)
            file_path = self.plugin_paths.pop(plugin_name, None)
            if file_path and file_path in self.file_mtimes:
                del self.file_mtimes[file_path]
            
            # Remove from sys.modules
            module_name = module.__name__
            if module_name in sys.modules:
                del sys.modules[module_name]
            
            self.logger.info(f"Unloaded plugin: {plugin_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to unload plugin {plugin_name}: {e}", exc_info=True)
            return False
    
    def reload_plugin(self, plugin_name: str) -> Optional[ToolPlugin]:
        """
        Reload a plugin (unload and load again).
        
        Args:
            plugin_name: Name of the plugin to reload
            
        Returns:
            Reloaded plugin instance or None if failed
        """
        if plugin_name not in self.plugin_paths:
            self.logger.warning(f"Cannot reload plugin: {plugin_name} (not tracked)")
            return None
        
        file_path = self.plugin_paths[plugin_name]
        
        # Unload
        self.unload_plugin(plugin_name)
        
        # Load again
        plugin = self.load_plugin_from_file(file_path)
        
        if plugin:
            self.logger.info(f"Reloaded plugin: {plugin.display_name}")
        
        return plugin
    
    def check_for_changes(self) -> List[str]:
        """
        Check if any loaded plugin files have been modified.
        
        Returns:
            List of plugin names that have changed
        """
        changed = []
        
        for plugin_name, file_path in self.plugin_paths.items():
            if not os.path.exists(file_path):
                self.logger.warning(f"Plugin file deleted: {file_path}")
                changed.append(plugin_name)
                continue
            
            current_mtime = os.path.getmtime(file_path)
            stored_mtime = self.file_mtimes.get(file_path, 0)
            
            if current_mtime > stored_mtime:
                self.logger.info(f"Plugin file changed: {file_path}")
                changed.append(plugin_name)
        
        return changed
    
    def auto_reload_changed(self) -> List[ToolPlugin]:
        """
        Automatically reload any changed plugins.
        
        Returns:
            List of reloaded plugins
        """
        changed_names = self.check_for_changes()
        reloaded = []
        
        for plugin_name in changed_names:
            plugin = self.reload_plugin(plugin_name)
            if plugin:
                reloaded.append(plugin)
        
        if reloaded:
            self.logger.info(f"Auto-reloaded {len(reloaded)} plugins")
        
        return reloaded
    
    def get_loaded_plugin_names(self) -> List[str]:
        """Get names of all loaded plugins"""
        return list(self.loaded_modules.keys())
    
    def get_plugin_info(self, plugin_name: str) -> Optional[Dict[str, any]]:
        """
        Get information about a loaded plugin.
        
        Args:
            plugin_name: Plugin name
            
        Returns:
            Dictionary with plugin info or None
        """
        if plugin_name not in self.loaded_modules:
            return None
        
        plugin = self.registry.get_plugin(plugin_name)
        if not plugin:
            return None
        
        return {
            'name': plugin.name,
            'display_name': plugin.display_name,
            'category': plugin.category,
            'description': plugin.description,
            'file_path': self.plugin_paths.get(plugin_name),
            'module': self.loaded_modules[plugin_name].__name__
        }
