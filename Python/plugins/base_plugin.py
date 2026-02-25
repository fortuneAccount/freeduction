"""
Base classes and data structures for the plugin system
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class ConfigField:
    """Defines a configuration field for a plugin"""
    name: str
    field_type: str  # 'file', 'directory', 'boolean', 'string', 'integer'
    label: str
    required: bool = False
    default: Any = None
    filter: Optional[str] = None  # File filter (e.g., "*.amgp")
    help_text: Optional[str] = None


@dataclass
class PluginConfig:
    """Runtime configuration for a plugin instance"""
    tool_path: Optional[str] = None
    options: str = ""
    arguments: str = ""
    wait: bool = False
    enabled: bool = True
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    
    def get_field(self, name: str, default: Any = None) -> Any:
        """Get a custom field value with optional default"""
        return self.custom_fields.get(name, default)
    
    def set_field(self, name: str, value: Any):
        """Set a custom field value"""
        self.custom_fields[name] = value


class ToolPlugin(ABC):
    """
    Abstract base class for all tool plugins.
    
    Plugins represent external tools that can be integrated into anattaGen.
    Each plugin defines how to discover, configure, and execute its tool.
    """
    
    # ===== Identity =====
    
    @property
    @abstractmethod
    def name(self) -> str:
        """
        Unique identifier for the plugin (lowercase, no spaces).
        Example: 'antimicrox', 'borderless'
        """
        pass
    
    @property
    @abstractmethod
    def display_name(self) -> str:
        """
        Human-readable name for display in UI.
        Example: 'AntiMicroX', 'Borderless Gaming'
        """
        pass
    
    @property
    @abstractmethod
    def category(self) -> str:
        """
        Category for grouping plugins.
        Standard categories: MAPPERS, WINDOWING, DISPLAY, AUDIO, DISCS, SYNC, UTILITIES
        """
        pass
    
    @property
    def description(self) -> str:
        """Optional description of what the tool does"""
        return ""
    
    @property
    def version(self) -> str:
        """Plugin version"""
        return "1.0.0"
    
    # ===== Discovery =====
    
    @abstractmethod
    def get_executable_patterns(self) -> List[str]:
        """
        List of executable names to search for (case-insensitive).
        Example: ['antimicrox.exe', 'AntiMicroX.exe']
        """
        pass
    
    def get_search_paths(self) -> List[str]:
        """
        Optional list of relative paths to search within bin directory.
        Example: ['antimicrox', 'AntiMicroX', 'antimicrox/bin']
        """
        return []
    
    # ===== Configuration =====
    
    def get_config_schema(self) -> Dict[str, ConfigField]:
        """
        Define configuration fields needed by this plugin.
        Returns a dictionary mapping field names to ConfigField objects.
        """
        return {}
    
    def validate_config(self, config: PluginConfig) -> tuple[bool, Optional[str]]:
        """
        Validate a configuration.
        Returns (is_valid, error_message)
        """
        # Check required fields
        schema = self.get_config_schema()
        for field_name, field_def in schema.items():
            if field_def.required:
                value = config.get_field(field_name)
                if value is None or value == "":
                    return False, f"Required field '{field_def.label}' is missing"
        
        return True, None
    
    # ===== Command Building =====
    
    @abstractmethod
    def build_launch_command(self, config: PluginConfig) -> Optional[str]:
        """
        Build the command line for launching the tool.
        Returns None if the tool cannot be launched with the given config.
        """
        pass
    
    def build_exit_command(self, config: PluginConfig) -> Optional[str]:
        """
        Build the command line for the exit sequence.
        Returns None if no exit command is needed.
        """
        return None
    
    def supports_exit_action(self) -> bool:
        """Whether this plugin has a distinct exit action"""
        return False
    
    # ===== Process Management =====
    
    def should_track_process(self) -> bool:
        """Whether the launched process should be tracked for cleanup"""
        return True
    
    def should_terminate_on_exit(self) -> bool:
        """Whether the process should be terminated on exit"""
        return False
    
    def get_process_name(self, config: PluginConfig) -> Optional[str]:
        """
        Get the process name for killing by name.
        Returns None to use the executable name from tool_path.
        """
        return None
    
    # ===== UI Hints =====
    
    def get_icon_name(self) -> Optional[str]:
        """Optional icon name for UI display"""
        return None
    
    def get_documentation_url(self) -> Optional[str]:
        """Optional URL to tool documentation"""
        return None
