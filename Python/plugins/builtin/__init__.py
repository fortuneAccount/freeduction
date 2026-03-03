"""
Built-in plugins for mainApp
"""

from .antimicrox_plugin import AntiMicroXPlugin
from .borderless_plugin import BorderlessGamingPlugin
from .multimonitor_plugin import MultiMonitorToolPlugin
from .cloud_backup_plugin import RcloneBackupPlugin, LudusaviBackupPlugin

__all__ = [
    'AntiMicroXPlugin',
    'BorderlessGamingPlugin', 
    'MultiMonitorToolPlugin',
    'RcloneBackupPlugin',
    'LudusaviBackupPlugin'
]
