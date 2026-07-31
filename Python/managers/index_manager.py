import os
import shutil

INDEX_FILENAME = "current.index"
BACKUP_DIR = "index_backups"


def backup_index(directory=None):
    """
    Backup current.index to index_backups/current.index.0001, .0002, etc.
    Only used for automatic backups after indexing sources.

    Args:
        directory: Directory containing the index file (default: app root)
    """
    # Get the app's root directory if directory is not specified
    if directory is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        directory = os.path.dirname(os.path.dirname(script_dir))

    src = os.path.join(directory, INDEX_FILENAME)
    if not os.path.exists(src):
        return

    backup_dir = os.path.join(directory, BACKUP_DIR)
    os.makedirs(backup_dir, exist_ok=True)

    # Find next available backup number
    existing = [f for f in os.listdir(backup_dir) if f.startswith(INDEX_FILENAME)]
    nums = [int(f.split(".")[-1]) for f in existing if f.split(".")[-1].isdigit()]
    next_num = max(nums, default=0) + 1
    backup_name = f"{INDEX_FILENAME}.{next_num:04d}"
    dst = os.path.join(backup_dir, backup_name)
    shutil.copy2(src, dst)
