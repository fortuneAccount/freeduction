"""
Plugin registry for managing tool plugins
"""

from typing import Dict, List, Optional
from .base_plugin import ToolPlugin
import logging


class PluginRegistry:
    """Central registry for all tool plugins"""
    
    def __init__(self):
        self.plugins: Dict[str, ToolPlugin] = {}
        self.categories: Dict[str, List[ToolPlugin]] = {}
        self.logger = logging.getLogger(__name__)
    
    def register(self, plugin: ToolPlugin):
        """
        Register a plugin in the registry.
        
        Args:
            plugin: The plugin instance to register
        """
        plugin_name = plugin.name
        
        if plugin_name in self.plugins:
            self.logger.warning(f"Plugin '{plugin_name}' is already registered. Overwriting.")
        
        self.plugins[plugin_name] = plugin
        
        # Add to category index
        category = plugin.category
        if category not in self.categories:
            self.categories[category] = []
        
        # Remove from old category if re-registering
        for cat_plugins in self.categories.values():
            if plugin in cat_plugins:
                cat_plugins.remove(plugin)
        
        self.categories[category].append(plugin)
        
        self.logger.info(f"Registered plugin: {plugin.display_name} ({plugin_name}) in category {category}")
    
    def unregister(self, plugin_name: str) -> bool:
        """
        Unregister a plugin.
        
        Args:
            plugin_name: Name of the plugin to unregister
            
        Returns:
            True if plugin was unregistered, False if not found
        """
        if plugin_name not in self.plugins:
            return False
        
        plugin = self.plugins[plugin_name]
        del self.plugins[plugin_name]
        
        # Remove from category
        category = plugin.category
        if category in self.categories:
            self.categories[category] = [
                p for p in self.categories[category] if p.name != plugin_name
            ]
        
        self.logger.info(f"Unregistered plugin: {plugin_name}")
        return True
    
    def get_plugin(self, name: str) -> Optional[ToolPlugin]:
        """
        Get a plugin by name.
        
        Args:
            name: Plugin name
            
        Returns:
            Plugin instance or None if not found
        """
        return self.plugins.get(name)
    
    def get_by_category(self, category: str) -> List[ToolPlugin]:
        """
        Get all plugins in a category.
        
        Args:
            category: Category name
            
        Returns:
            List of plugins in the category
        """
        return self.categories.get(category, [])
    
    def get_all_plugins(self) -> List[ToolPlugin]:
        """
        Get all registered plugins.
        
        Returns:
            List of all plugins
        """
        return list(self.plugins.values())
    
    def get_all_categories(self) -> List[str]:
        """
        Get all category names.
        
        Returns:
            List of category names
        """
        return list(self.categories.keys())
    
    def find_plugins_by_executable(self, executable_name: str) -> List[ToolPlugin]:
        """
        Find plugins that match a given executable name.
        
        Args:
            executable_name: Name of executable to search for
            
        Returns:
            List of matching plugins
        """
        executable_lower = executable_name.lower()
        matching = []
        
        for plugin in self.plugins.values():
            patterns = [p.lower() for p in plugin.get_executable_patterns()]
            if executable_lower in patterns:
                matching.append(plugin)
        
        return matching
    
    def get_plugin_count(self) -> int:
        """Get total number of registered plugins"""
        return len(self.plugins)
    
    def clear(self):
        """Clear all registered plugins"""
        self.plugins.clear()
        self.categories.clear()
        self.logger.info("Cleared all plugins from registry")
