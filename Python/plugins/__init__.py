"""
Plugin system for anattaGen

This package provides a modular plugin architecture for integrating external tools.
"""

from .base_plugin import ToolPlugin, ConfigField, PluginConfig
from .registry import PluginRegistry

__all__ = ['ToolPlugin', 'ConfigField', 'PluginConfig', 'PluginRegistry']
