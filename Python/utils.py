"""Shared utility functions.

This module provides common utility functions used across the application
to reduce code duplication and improve maintainability.
"""

import os
import logging
from typing import Any, Dict, List, Optional


def resolve_path(path: str, base_dir: Optional[str] = None) -> str:
    """Resolve a path, handling relative paths and environment variables.

    Args:
        path: The path to resolve
        base_dir: Base directory for relative paths (defaults to current working dir)

    Returns:
        Absolute path
    """
    if not path:
        return ""

    # Expand environment variables
    path = os.path.expandvars(path)

    # Expand user home directory
    path = os.path.expanduser(path)

    # If already absolute, return it
    if os.path.isabs(path):
        return path

    # Make relative to base_dir or current working directory
    base = base_dir if base_dir else os.getcwd()
    return os.path.abspath(os.path.join(base, path))


def ensure_dir_exists(path: str) -> bool:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path to ensure exists

    Returns:
        True if directory exists or was created, False otherwise
    """
    try:
        os.makedirs(path, exist_ok=True)
        return True
    except OSError as e:
        logging.error(f"Failed to create directory {path}: {e}")
        return False


def safe_delete(path: str) -> bool:
    """Safely delete a file or directory.

    Args:
        path: Path to delete

    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            import shutil
            shutil.rmtree(path)
        return True
    except OSError as e:
        logging.error(f"Failed to delete {path}: {e}")
        return False


def get_file_size_mb(path: str) -> float:
    """Get file size in megabytes.

    Args:
        path: Path to file

    Returns:
        File size in MB, or 0 if file doesn't exist
    """
    try:
        return os.path.getsize(path) / (1024 * 1024)
    except OSError:
        return 0.0


def build_command(
    executable: str,
    options: str = "",
    arguments: str = "",
    extra_args: Optional[List[str]] = None
) -> str:
    """Build a command string from components.

    Args:
        executable: The executable path
        options: Command-line options
        arguments: Command-line arguments
        extra_args: Additional arguments as a list

    Returns:
        Complete command string
    """
    cmd = f'"{executable}"'
    if options:
        cmd += f' {options}'
    if arguments:
        cmd += f' {arguments}'
    if extra_args:
        cmd += ' ' + ' '.join(f'"{arg}"' if ' ' in arg else arg for arg in extra_args)
    return cmd


def normalize_path(path: str) -> str:
    """Normalize a path for comparison.

    Args:
        path: Path to normalize

    Returns:
        Normalized path
    """
    return os.path.normpath(os.path.normcase(path))


def is_executable(path: str) -> bool:
    """Check if a path is an executable file.

    Args:
        path: Path to check

    Returns:
        True if file exists and is executable
    """
    if not os.path.isfile(path):
        return False

    # On Windows, check for executable extensions
    if os.name == 'nt':
        return path.lower().endswith(('.exe', '.bat', '.cmd', '.ps1'))

    # On Unix, check execute permission
    return os.access(path, os.X_OK)


def get_unique_filename(base_path: str, extension: str = "") -> str:
    """Generate a unique filename by appending a number if needed.

    Args:
        base_path: Base path without extension
        extension: File extension (with or without dot)

    Returns:
        Unique filename
    """
    if extension and not extension.startswith('.'):
        extension = '.' + extension

    path = base_path + extension
    counter = 1

    while os.path.exists(path):
        path = f"{base_path}_{counter}{extension}"
        counter += 1

    return path


def merge_dicts(*dicts: Dict[str, Any]) -> Dict[str, Any]:
    """Merge multiple dictionaries, with later dicts taking precedence.

    Args:
        *dicts: Dictionaries to merge

    Returns:
        Merged dictionary
    """
    result = {}
    for d in dicts:
        result.update(d)
    return result


def chunk_list(lst: List[Any], chunk_size: int) -> List[List[Any]]:
    """Split a list into chunks of specified size.

    Args:
        lst: List to chunk
        chunk_size: Size of each chunk

    Returns:
        List of chunks
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def format_bytes(size: int) -> str:
    """Format a byte size into a human-readable string.

    Args:
        size: Size in bytes

    Returns:
        Human-readable string (e.g., "1.50 MB")
    """
    if size == 0:
        return "0 B"
    
    power = 1024
    n = 0
    power_labels = {0: 'B', 1: 'KB', 2: 'MB', 3: 'GB', 4: 'TB'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels.get(n, 'B')}"