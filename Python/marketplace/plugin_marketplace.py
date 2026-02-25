"""
Plugin Marketplace Framework

Provides infrastructure for discovering, downloading, and installing plugins
from remote repositories.
"""

import os
import json
import logging
import hashlib
from typing import Dict, List, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class PluginMetadata:
    """Metadata for a marketplace plugin"""
    id: str
    name: str
    display_name: str
    version: str
    author: str
    description: str
    category: str
    tags: List[str]
    download_url: str
    file_hash: str
    file_size: int
    min_app_version: str
    dependencies: List[str]
    homepage: Optional[str] = None
    documentation_url: Optional[str] = None
    license: str = "MIT"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginMetadata':
        """Create from dictionary"""
        return cls(**data)


class PluginMarketplace:
    """
    Manages plugin discovery and installation from marketplace.
    
    Features:
    - Browse available plugins
    - Search and filter
    - Download and install
    - Update plugins
    - Verify integrity
    """
    
    def __init__(self, cache_dir: str, plugins_dir: str):
        """
        Initialize the marketplace.
        
        Args:
            cache_dir: Directory for caching marketplace data
            plugins_dir: Directory where plugins are installed
        """
        self.cache_dir = Path(cache_dir)
        self.plugins_dir = Path(plugins_dir)
        self.logger = logging.getLogger(__name__)
        
        # Create directories if needed
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.plugins_dir.mkdir(parents=True, exist_ok=True)
        
        self.catalog: Dict[str, PluginMetadata] = {}
        self.installed: Dict[str, PluginMetadata] = {}
        
        self._load_installed_plugins()
    
    def load_catalog_from_file(self, catalog_file: str) -> bool:
        """
        Load plugin catalog from a JSON file.
        
        Args:
            catalog_file: Path to catalog JSON file
            
        Returns:
            True if loaded successfully
        """
        try:
            with open(catalog_file, 'r') as f:
                data = json.load(f)
            
            self.catalog.clear()
            for plugin_data in data.get('plugins', []):
                metadata = PluginMetadata.from_dict(plugin_data)
                self.catalog[metadata.id] = metadata
            
            self.logger.info(f"Loaded {len(self.catalog)} plugins from catalog")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load catalog: {e}", exc_info=True)
            return False
    
    def load_catalog_from_url(self, url: str) -> bool:
        """
        Load plugin catalog from a remote URL.
        
        Args:
            url: URL to catalog JSON
            
        Returns:
            True if loaded successfully
        """
        # TODO: Implement HTTP download
        # For now, this is a placeholder
        self.logger.warning("Remote catalog loading not yet implemented")
        return False
    
    def search_plugins(self, query: str = "", category: Optional[str] = None, 
                      tags: Optional[List[str]] = None) -> List[PluginMetadata]:
        """
        Search for plugins in the catalog.
        
        Args:
            query: Search query (searches name and description)
            category: Filter by category
            tags: Filter by tags
            
        Returns:
            List of matching plugins
        """
        results = []
        query_lower = query.lower()
        
        for metadata in self.catalog.values():
            # Category filter
            if category and metadata.category != category:
                continue
            
            # Tags filter
            if tags and not any(tag in metadata.tags for tag in tags):
                continue
            
            # Query filter
            if query:
                if (query_lower in metadata.name.lower() or 
                    query_lower in metadata.display_name.lower() or
                    query_lower in metadata.description.lower()):
                    results.append(metadata)
            else:
                results.append(metadata)
        
        return results
    
    def get_plugin_by_id(self, plugin_id: str) -> Optional[PluginMetadata]:
        """Get plugin metadata by ID"""
        return self.catalog.get(plugin_id)
    
    def is_plugin_installed(self, plugin_id: str) -> bool:
        """Check if a plugin is installed"""
        return plugin_id in self.installed
    
    def get_installed_version(self, plugin_id: str) -> Optional[str]:
        """Get installed version of a plugin"""
        metadata = self.installed.get(plugin_id)
        return metadata.version if metadata else None
    
    def needs_update(self, plugin_id: str) -> bool:
        """Check if an installed plugin has an update available"""
        if not self.is_plugin_installed(plugin_id):
            return False
        
        installed_version = self.get_installed_version(plugin_id)
        catalog_metadata = self.get_plugin_by_id(plugin_id)
        
        if not catalog_metadata:
            return False
        
        # Simple version comparison (assumes semantic versioning)
        return catalog_metadata.version > installed_version
    
    def install_plugin(self, plugin_id: str, source_file: str) -> bool:
        """
        Install a plugin from a file.
        
        Args:
            plugin_id: Plugin ID
            source_file: Path to plugin file
            
        Returns:
            True if installed successfully
        """
        try:
            metadata = self.get_plugin_by_id(plugin_id)
            if not metadata:
                self.logger.error(f"Plugin not found in catalog: {plugin_id}")
                return False
            
            # Verify file hash
            if not self._verify_file_hash(source_file, metadata.file_hash):
                self.logger.error(f"File hash mismatch for {plugin_id}")
                return False
            
            # Copy to plugins directory
            dest_file = self.plugins_dir / f"{metadata.name}.py"
            
            with open(source_file, 'rb') as src:
                with open(dest_file, 'wb') as dst:
                    dst.write(src.read())
            
            # Save metadata
            self._save_plugin_metadata(plugin_id, metadata)
            self.installed[plugin_id] = metadata
            
            self.logger.info(f"Installed plugin: {metadata.display_name} v{metadata.version}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to install plugin {plugin_id}: {e}", exc_info=True)
            return False
    
    def uninstall_plugin(self, plugin_id: str) -> bool:
        """
        Uninstall a plugin.
        
        Args:
            plugin_id: Plugin ID
            
        Returns:
            True if uninstalled successfully
        """
        try:
            if not self.is_plugin_installed(plugin_id):
                self.logger.warning(f"Plugin not installed: {plugin_id}")
                return False
            
            metadata = self.installed[plugin_id]
            plugin_file = self.plugins_dir / f"{metadata.name}.py"
            
            # Remove plugin file
            if plugin_file.exists():
                plugin_file.unlink()
            
            # Remove metadata
            metadata_file = self._get_metadata_file(plugin_id)
            if metadata_file.exists():
                metadata_file.unlink()
            
            del self.installed[plugin_id]
            
            self.logger.info(f"Uninstalled plugin: {metadata.display_name}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to uninstall plugin {plugin_id}: {e}", exc_info=True)
            return False
    
    def get_categories(self) -> List[str]:
        """Get all available categories"""
        return list(set(m.category for m in self.catalog.values()))
    
    def get_all_tags(self) -> List[str]:
        """Get all available tags"""
        tags = set()
        for metadata in self.catalog.values():
            tags.update(metadata.tags)
        return sorted(list(tags))
    
    def _verify_file_hash(self, file_path: str, expected_hash: str) -> bool:
        """Verify file SHA256 hash"""
        try:
            sha256 = hashlib.sha256()
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b''):
                    sha256.update(chunk)
            
            actual_hash = sha256.hexdigest()
            return actual_hash == expected_hash
            
        except Exception as e:
            self.logger.error(f"Failed to verify hash: {e}")
            return False
    
    def _get_metadata_file(self, plugin_id: str) -> Path:
        """Get path to plugin metadata file"""
        return self.cache_dir / f"{plugin_id}.json"
    
    def _save_plugin_metadata(self, plugin_id: str, metadata: PluginMetadata):
        """Save plugin metadata to cache"""
        metadata_file = self._get_metadata_file(plugin_id)
        with open(metadata_file, 'w') as f:
            json.dump(metadata.to_dict(), f, indent=2)
    
    def _load_installed_plugins(self):
        """Load metadata for installed plugins"""
        self.installed.clear()
        
        for metadata_file in self.cache_dir.glob("*.json"):
            try:
                with open(metadata_file, 'r') as f:
                    data = json.load(f)
                
                metadata = PluginMetadata.from_dict(data)
                self.installed[metadata.id] = metadata
                
            except Exception as e:
                self.logger.warning(f"Failed to load metadata from {metadata_file}: {e}")
        
        self.logger.info(f"Found {len(self.installed)} installed plugins")
    
    def export_catalog(self, output_file: str) -> bool:
        """
        Export current catalog to a JSON file.
        
        Args:
            output_file: Path to output file
            
        Returns:
            True if exported successfully
        """
        try:
            data = {
                'version': '1.0',
                'updated_at': datetime.now().isoformat(),
                'plugins': [m.to_dict() for m in self.catalog.values()]
            }
            
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Exported catalog to {output_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to export catalog: {e}", exc_info=True)
            return False
