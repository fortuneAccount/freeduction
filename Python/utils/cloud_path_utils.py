"""
Cloud Path Utilities

Utilities for generating cloud sync and local backup paths.
"""

import os
import datetime
import re
from pathlib import Path


def strip_path_variables(path, game_directory=None):
    """
    Remove common path variables to get relative path.
    
    Args:
        path: Full path with variables like %LOCALAPPDATA%\Devel\save.dat
        game_directory: Optional game directory to remove from path
        
    Returns:
        Relative path like Devel\save.dat
    """
    if not path:
        return ""
    
    # First, expand environment variables
    expanded = os.path.expandvars(path)
    
    # Define prefixes to remove (in order of priority)
    prefixes_to_remove = []
    
    # Add game directory if provided
    if game_directory:
        prefixes_to_remove.append(game_directory)
    
    # Add common Windows environment paths
    prefixes_to_remove.extend([
        os.path.expandvars('%LOCALAPPDATA%'),
        os.path.expandvars('%APPDATA%'),
        os.path.expandvars('%USERPROFILE%'),
        os.path.expandvars('%PROGRAMFILES%'),
        os.path.expandvars('%PROGRAMFILES(X86)%'),
        os.path.expandvars('%PROGRAMDATA%'),
    ])
    
    # Try to remove each prefix
    for prefix in prefixes_to_remove:
        if prefix and expanded.lower().startswith(prefix.lower()):
            # Remove prefix and leading separator
            relative = expanded[len(prefix):].lstrip('\\//')
            return relative
    
    # If path still contains template variables, try to extract relative part
    template_patterns = [
        r'<path-to-game>[/\\]+(.*)',
        r'<Steam-folder>[/\\]+userdata[/\\]+<user-id>[/\\]+\d+[/\\]+remote[/\\]+(.*)',
        r'%[A-Z_]+%[/\\]+(.*)',
    ]
    
    for pattern in template_patterns:
        match = re.search(pattern, path, re.IGNORECASE)
        if match:
            return match.group(1)
    
    # If no prefix matched, return just the filename
    return os.path.basename(path)


def generate_remote_path(user_prefix, game_name, local_path, game_directory=None):
    """
    Generate remote cloud path.
    
    Args:
        user_prefix: User's custom prefix (e.g., "GameBackups")
        game_name: Name of the game
        local_path: Local file path
        game_directory: Optional game directory for path stripping
        
    Returns:
        Full remote path (forward slashes for cloud compatibility)
        
    Example:
        user_prefix = "GameBackups"
        game_name = "Fun Game"
        local_path = "%LOCALAPPDATA%\\Devel\\save.dat"
        -> "GameBackups/Fun Game/Devel/save.dat"
    """
    if not user_prefix or not game_name or not local_path:
        return ""
    
    # Get relative path
    relative = strip_path_variables(local_path, game_directory)
    
    # Sanitize game name (remove invalid characters for cloud paths)
    safe_game_name = sanitize_path_component(game_name)
    
    # Build remote path with forward slashes
    remote_path = f"{user_prefix}/{safe_game_name}/{relative}"
    
    # Normalize slashes to forward slashes for cloud compatibility
    remote_path = remote_path.replace('\\', '/')
    
    # Remove any double slashes
    remote_path = re.sub(r'/+', '/', remote_path)
    
    return remote_path


def generate_local_backup_path(local_prefix, game_name, use_timestamp=True):
    """
    Generate local backup directory path with optional timestamp.
    
    Args:
        local_prefix: Local backup root directory
        game_name: Name of the game
        use_timestamp: Whether to include timestamp in path
        
    Returns:
        Full local backup path
        
    Example:
        local_prefix = "C:\\Backups\\Games"
        game_name = "Fun Game"
        use_timestamp = True
        -> "C:\\Backups\\Games\\Fun Game\\2024-01-15_14-30-00"
    """
    if not local_prefix or not game_name:
        return ""
    
    # Sanitize game name
    safe_game_name = sanitize_path_component(game_name)
    
    # Build base path
    backup_path = os.path.join(local_prefix, safe_game_name)
    
    # Add timestamp if requested
    if use_timestamp:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_path = os.path.join(backup_path, timestamp)
    
    return backup_path


def sanitize_path_component(name):
    """
    Sanitize a path component by removing invalid characters.
    
    Args:
        name: Path component to sanitize
        
    Returns:
        Sanitized path component
    """
    if not name:
        return ""
    
    # Remove invalid characters for Windows/cloud paths
    # Including ! which can cause issues in some cloud providers
    invalid_chars = r'[<>:"|?*!]'
    sanitized = re.sub(invalid_chars, '_', name)
    
    # Remove leading/trailing spaces and dots
    sanitized = sanitized.strip('. ')
    
    return sanitized


def build_rclone_command(rclone_path, remote_name, remote_path, local_path, 
                         sync_mode='sync', direction='download', options=''):
    """
    Build rclone command for syncing.
    
    Args:
        rclone_path: Path to rclone executable
        remote_name: Remote name (e.g., "gdrive:")
        remote_path: Remote path relative to remote
        local_path: Local path
        sync_mode: 'sync', 'copy', or 'move'
        direction: 'download' (remote->local) or 'upload' (local->remote)
        options: Additional rclone options
        
    Returns:
        Command string
    """
    # Ensure remote_name ends with colon
    if not remote_name.endswith(':'):
        remote_name += ':'
    
    # Build full remote path
    full_remote = f"{remote_name}{remote_path}"
    
    # Build command based on direction
    if direction == 'download':
        source = full_remote
        dest = local_path
    else:  # upload
        source = local_path
        dest = full_remote
    
    # Build command
    cmd = f'"{rclone_path}" {sync_mode} "{source}" "{dest}"'
    
    # Add options
    if options:
        cmd += f' {options}'
    
    # Add progress flag
    cmd += ' --progress'
    
    return cmd


def build_ludusavi_command(ludusavi_path, backup_path, game_name, 
                           action='backup', options=''):
    """
    Build ludusavi command for backup/restore.
    
    Args:
        ludusavi_path: Path to ludusavi executable
        backup_path: Path to backup directory
        game_name: Name of the game
        action: 'backup' or 'restore'
        options: Additional ludusavi options
        
    Returns:
        Command string
    """
    # Build command
    cmd = f'"{ludusavi_path}" {action}'
    
    # Add backup path
    cmd += f' --path "{backup_path}"'
    
    # Add game name
    cmd += f' --game "{game_name}"'
    
    # Add options
    if options:
        cmd += f' {options}'
    
    return cmd


def parse_save_paths_from_gameini(config, section='SAVE', platform='windows'):
    """
    Parse save paths from Game.ini [SAVE] section.
    
    Args:
        config: ConfigParser object
        section: Section name (default 'SAVE')
        platform: Platform key (default 'windows')
        
    Returns:
        List of save paths
    """
    if not config.has_section(section):
        return []
    
    if not config.has_option(section, platform):
        return []
    
    paths_str = config.get(section, platform)
    if not paths_str:
        return []
    
    # Split by pipe delimiter
    paths = [p.strip() for p in paths_str.split('|') if p.strip()]
    
    return paths


def get_primary_save_path(config, section='SAVE', platform='windows'):
    """
    Get the primary (first) save path from Game.ini.
    
    Args:
        config: ConfigParser object
        section: Section name (default 'SAVE')
        platform: Platform key (default 'windows')
        
    Returns:
        Primary save path or empty string
    """
    paths = parse_save_paths_from_gameini(config, section, platform)
    return paths[0] if paths else ""
