"""Utility modules for mainapp."""

from .path_discovery import PathDiscovery, discover_and_update_paths
from .cloud_path_utils import (
    strip_path_variables,
    generate_remote_path,
    generate_local_backup_path,
    sanitize_path_component,
    build_rclone_command,
    build_ludusavi_command,
    parse_save_paths_from_gameini,
    get_primary_save_path
)


def format_bytes(size: int) -> str:
    """Format a byte size into a human-readable string."""
    if size == 0:
        return "0 B"
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels.get(n, 'B')}"

__all__ = [
    'PathDiscovery',
    'discover_and_update_paths',
    'strip_path_variables',
    'generate_remote_path',
    'generate_local_backup_path',
    'sanitize_path_component',
    'build_rclone_command',
    'build_ludusavi_command',
    'parse_save_paths_from_gameini',
    'get_primary_save_path',
    'format_bytes'
]
