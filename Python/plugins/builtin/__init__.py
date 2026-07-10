"""
Built-in plugins for mainApp
"""

from .antimicrox_plugin import AntiMicroXPlugin
from .borderless_plugin import BorderlessGamingPlugin
from .monitor_app_plugin import MonitorAppPlugin
from .cloud_backup_plugin import RcloneBackupPlugin, LudusaviBackupPlugin

__all__ = [
    'AntiMicroXPlugin',
    'BorderlessGamingPlugin', 
    'MonitorAppPlugin',
    'RcloneBackupPlugin',
    'LudusaviBackupPlugin'
]
