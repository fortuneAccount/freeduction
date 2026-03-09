import os
import shutil
from PyQt6.QtWidgets import QFileDialog

INDEX_FILENAME = "current.index"
BACKUP_DIR = "index_backups"
PIPE_CHAR = "|"
SAFE_PIPE_CHAR = ""  # U+2502


def save_index(main_window, directory, data):
    from .. import constants
    default_path = os.path.join(directory, INDEX_FILENAME)
    file_path = default_path
    
    # Save the index
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            for row in data:
                # Convert dict to list if necessary
                if isinstance(row, dict):
                    # Define the expected order of fields
                    fields = ["include", "executable", "directory", "steam_title", 
                              "name_override", "options", "arguments", "steam_id",
                              "p1_profile", "p2_profile", "desktop_ctrl", 
                              "game_monitor_cfg", "desktop_monitor_cfg", 
                              "post1", "post2", "post3", 
                              "pre1", "pre2", "pre3", 
                              "just_after", "just_before", "borderless", 
                              "as_admin", "no_tb", "mapper", "multimonitor",
                              "mapper_opts", "mapper_args", "borderless_opts", "borderless_args",
                              "multimonitor_opts", "multimonitor_args", "ja_opts", "ja_args",
                              "jb_opts", "jb_args", "pre1_opts", "pre1_args", "post1_opts", "post1_args",
                              "pre2_opts", "pre2_args", "post2_opts", "post2_args",
                              "pre3_opts", "pre3_args", "post3_opts", "post3_args",
                              "kill_list_enabled", "kill_list",
                              "launcher_executable",
                              "launcher_executable_opts", "launcher_executable_args",
                              "iso_path"]
                    
                    # Get path indicators
                    path_indicators = row.get("path_indicators", {})
                    
                    # Create a list of values
                    row_values = []
                    # Define path columns using EditorCols constants
                    path_columns = {constants.EditorCols.PLAYER1_PROFILE.value, constants.EditorCols.PLAYER2_PROFILE.value,
                                    constants.EditorCols.MEDIACENTER_PROFILE.value, constants.EditorCols.MM_GAME_PROFILE.value,
                                    constants.EditorCols.MM_DESKTOP_PROFILE.value, constants.EditorCols.LAUNCHER_EXE.value}
                    for i, field in enumerate(fields):
                        if i in path_columns:  # Path fields (using EditorCols mapping)
                            # Use the indicator from path_indicators if available
                            col = i
                            indicator = path_indicators.get(f"col_{col}_indicator", "<")  # Default to CEN
                            # If no indicator, use the value from the field
                            if f"col_{col}_indicator" not in path_indicators and field in row:
                                indicator = row[field]
                            # If still no indicator, default to CEN
                            if not indicator:
                                indicator = "<"
                            row_values.append(indicator)
                        else:
                            row_values.append(row.get(field, ""))
                else:
                    # Assume it's already a list
                    row_values = row
                
                # Convert all values to strings
                safe_row = [str(cell).replace(PIPE_CHAR, SAFE_PIPE_CHAR) for cell in row_values]
                f.write(PIPE_CHAR.join(safe_row) + "\n")
        
        # Show a status message if possible
        if main_window and hasattr(main_window, 'statusBar'):
            main_window.statusBar().showMessage(f"Saved index to {file_path}", 3000)
        
        return file_path
    except Exception as e:
        import traceback
        traceback.print_exc()
        if main_window and hasattr(main_window, 'statusBar'):
            main_window.statusBar().showMessage(f"Error saving index: {str(e)}", 3000)
        return None


def load_index(main_window=None, directory=None, prompt_for_filename=False):
    """
    Load the index file and return the data as a list of dictionaries.
    
    Args:
        main_window: Optional MainWindow object to update status bar
        directory: Default directory to load from (default: app root)
        prompt_for_filename: Whether to prompt for a filename
    
    Returns:
        List of dictionaries with game data
    """
    import traceback
    
    # Get the app's root directory if directory is not specified
    if directory is None:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        directory = os.path.dirname(os.path.dirname(script_dir))
    
    # Default path
    default_path = os.path.join(directory, INDEX_FILENAME)
    file_path = default_path
    
    # Prompt for filename if requested
    if prompt_for_filename and main_window:
        file_path, _ = QFileDialog.getOpenFileName(
            main_window,
            "Load Index",
            directory,
            "Index Files (*.index);;All Files (*)"
        )
        if not file_path:
            return []
    
    # Check if the file exists
    if not os.path.exists(file_path):
        if main_window and hasattr(main_window, 'statusBar'):
            main_window.statusBar().showMessage(f"Index file not found: {file_path}", 3000)
        return []
    
    # Load the data
    data = []
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            line_number = 0
            for line in f:
                line_number += 1
                if line.strip():
                    try:
                        # Replace safe pipe char back to normal pipe if needed
                        parts = line.strip().split(PIPE_CHAR)
                        parts = [p.replace(SAFE_PIPE_CHAR, PIPE_CHAR) if SAFE_PIPE_CHAR else p for p in parts]
                        
                        # Define field names to match save_index
                        from .. import constants
                        fields = ["include", "executable", "directory", "steam_title", 
                                  "name_override", "options", "arguments", "steam_id",
                                  "p1_profile", "p2_profile", "desktop_ctrl", 
                                  "game_monitor_cfg", "desktop_monitor_cfg", 
                                  "post1", "post2", "post3", 
                                  "pre1", "pre2", "pre3", 
                                  "just_after", "just_before", "borderless", 
                                  "as_admin", "no_tb", "mapper", "multimonitor",
                                  "mapper_opts", "mapper_args", "borderless_opts", "borderless_args",
                                  "multimonitor_opts", "multimonitor_args", "ja_opts", "ja_args",
                                  "jb_opts", "jb_args", "pre1_opts", "pre1_args", "post1_opts", "post1_args",
                                  "pre2_opts", "pre2_args", "post2_opts", "post2_args",
                                  "pre3_opts", "pre3_args", "post3_opts", "post3_args",
                                  "kill_list_enabled", "kill_list",
                                  "launcher_executable",
                                  "launcher_executable_opts", "launcher_executable_args",
                                  "iso_path"]
                        
                        # Create a dictionary for this row
                        row_dict = {}
                        path_indicators = {}
                        # Define path columns using EditorCols constants
                        path_columns = {constants.EditorCols.PLAYER1_PROFILE.value, constants.EditorCols.PLAYER2_PROFILE.value,
                                        constants.EditorCols.MEDIACENTER_PROFILE.value, constants.EditorCols.MM_GAME_PROFILE.value,
                                        constants.EditorCols.MM_DESKTOP_PROFILE.value, constants.EditorCols.LAUNCHER_EXE.value}
                        
                        # Fill in values from parts
                        for i, field in enumerate(fields):
                            if i < len(parts):
                                # For path fields (using EditorCols mapping), extract the indicator
                                if i in path_columns:
                                    path_indicators[f"col_{i}_indicator"] = parts[i]
                                    row_dict[field] = parts[i]
                                else:
                                    # For boolean fields, convert to boolean
                                    if field in ["include", "as_admin", "no_tb", "kill_list_enabled"]:
                                        row_dict[field] = parts[i].lower() == "true"
                                    else:
                                        row_dict[field] = parts[i]
                        
                        # Add path indicators to the row dictionary
                        row_dict["path_indicators"] = path_indicators
                        
                        # Add the row to the data
                        data.append(row_dict)
                    except Exception as e:
                        traceback.print_exc()
                        # Continue with the next line instead of failing completely
                        continue
        
        if main_window and hasattr(main_window, 'statusBar'):
            main_window.statusBar().showMessage(f"Loaded {len(data)} entries from {file_path}", 3000)
    except Exception as e:
        print(f"Error loading index: {str(e)}")
        traceback.print_exc()
        if main_window and hasattr(main_window, 'statusBar'):
            main_window.statusBar().showMessage(f"Error loading index: {str(e)}", 3000)
    
    return data


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


def delete_all_indexes(main_window_or_directory="."):
    """
    Delete current.index and all backups.
    
    Args:
        main_window_or_directory: Either MainWindow object or directory string
    """
    # Determine if we got a main_window or a directory string
    if hasattr(main_window_or_directory, 'statusBar'):
        main_window = main_window_or_directory
        directory = "."
    else:
        main_window = None
        directory = main_window_or_directory if isinstance(main_window_or_directory, str) else "."
    
    # Delete the index file
    idx = os.path.join(directory, INDEX_FILENAME)
    if os.path.exists(idx):
        os.remove(idx)
        if main_window and hasattr(main_window, 'statusBar'):
            main_window.statusBar().showMessage(f"Deleted index file: {idx}", 3000)
    
    # Delete backup directory and its contents
    backup_dir = os.path.join(directory, BACKUP_DIR)
    if os.path.exists(backup_dir):
        for f in os.listdir(backup_dir):
            os.remove(os.path.join(backup_dir, f))
        os.rmdir(backup_dir)
        if main_window and hasattr(main_window, 'statusBar'):
            main_window.statusBar().showMessage(f"Deleted backup directory: {backup_dir}", 3000)