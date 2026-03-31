"""
Plugin system for mainApp

This package provides a modular plugin architecture for integrating external tools.
"""

from .base_plugin import ToolPlugin, ConfigField, PluginConfig
from .registry import PluginRegistry

# Stable public API version — bump this when making breaking changes (Requirement 2.2)
PLUGIN_API_VERSION = "1.0.0"

# TODO: PluginManifest will be defined in Python/plugins/manifest.py (Requirement 3.1)
try:
    from .manifest import PluginManifest
except ImportError:
    PluginManifest = None  # type: ignore[assignment,misc]

# TODO: PluginFacade will be defined in Python/plugins/facade.py (Requirement 1.1)
try:
    from .facade import PluginFacade
except ImportError:
    PluginFacade = None  # type: ignore[assignment,misc]

# TODO: create_plugin_scaffold will be defined in Python/plugins/scaffold.py (Requirement 6.3)
try:
    from .scaffold import create_plugin_scaffold
except ImportError:
    create_plugin_scaffold = None  # type: ignore[assignment]

__all__ = [
    'ToolPlugin', 'ConfigField', 'PluginConfig', 'PluginRegistry',
    'PLUGIN_API_VERSION',
    'PluginManifest',
    'PluginFacade',
    'create_plugin_scaffold',
]
