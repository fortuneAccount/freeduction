"""
Core infrastructure for the plugin system
"""

from .dependency_container import DependencyContainer, get_container, reset_container

__all__ = ['DependencyContainer', 'get_container', 'reset_container']
