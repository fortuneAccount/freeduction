import os
import logging
import re
from typing import Optional, Tuple, Dict, Any, Set
from .name_processor import NameProcessor
from .name_utils import replace_illegal_chars


def get_filtered_directory_name(exec_full_path: str, folder_exclude_set: set) -> str:
    """
    Walks up the directory tree from the executable path to find the first
    directory name not in the folder_exclude_set.
    """
    dir_path = os.path.dirname(exec_full_path)
    if not folder_exclude_set:
        return os.path.basename(dir_path)

    current_path = dir_path
    while True:
        dir_name = os.path.basename(current_path)
        # Transform dir_name by removing all non-alphanumeric characters
        transformed_dir_name = re.sub(r'[^a-zA-Z0-9]', '', dir_name).lower()
        if transformed_dir_name not in folder_exclude_set:
            return dir_name

        parent_path = os.path.dirname(current_path)
        if parent_path == current_path:
            return os.path.basename(dir_path)

        current_path = parent_path


def _is_demoted(
    exec_name_no_ext: str,
    name_override: str,
    dir_name: str,
    demoted_set: Set[str],
    folder_demoted_set: Set[str],
    name_processor: NameProcessor
) -> bool:
    """
    Determines if a game should be demoted based on demotion sets.

    Returns:
        True if the game is demoted, False otherwise.
    """
    normalized_exec_name = name_processor.get_match_name(exec_name_no_ext)
    normalized_name_override = name_processor.get_match_name(name_override)

    # Check against executable demotion terms
    for demoted_term in demoted_set:
        if (normalized_exec_name.startswith(demoted_term) or normalized_exec_name.endswith(demoted_term)) and demoted_term not in normalized_name_override:
            return True

    # Check against folder demotion terms
    processed_dir_name = name_processor.get_display_name(dir_name)
    normalized_dir_name = name_processor.get_match_name(processed_dir_name)
    for demoted_term in folder_demoted_set:
        if normalized_dir_name == demoted_term and demoted_term not in normalized_name_override:
            return True

    return False


def _get_steam_match(
    name_override: str,
    config: Any,
    steam_match_index: Optional[Dict[str, Any]],
    name_processor: NameProcessor
) -> Tuple[str, str, str]:
    """
    Matches the game name with the Steam index and returns Steam info.

    Returns:
        A tuple containing (steam_name, steam_id, updated_name_override).
    """
    steam_name, steam_id = "", ""
    if not (config.enable_name_matching and steam_match_index):
        return steam_name, steam_id, name_override

    match_name = name_processor.get_match_name(name_override)
    match_data = steam_match_index.get(match_name)

    if not match_data:
        return steam_name, steam_id, name_override

    steam_name = match_data.get("name", "")
    steam_id = match_data.get("id", "")

    if steam_name:
        # Clean the steam name for use as a display name
        clean_steam_name = replace_illegal_chars(steam_name, " - ")
        while "  " in clean_steam_name: clean_steam_name = clean_steam_name.replace("  ", " ")
        while "- -" in clean_steam_name: clean_steam_name = clean_steam_name.replace("- -", " - ")
        name_override = clean_steam_name.strip()

    return steam_name, steam_id, name_override


def _process_executable(
    exec_full_path: str,
    main_window: Any,
    name_processor: NameProcessor
) -> Optional[Dict[str, Any]]:
    """
    Processes a single executable file and returns its game data dictionary,
    or None if it should be skipped.
    """
    try:
        filename = os.path.basename(exec_full_path)
        exec_name_no_ext = os.path.splitext(filename)[0]

        # Check exclusion (substring match)
        for exclude_str in main_window.exclude_exe_set:
            if exclude_str in filename.lower():
                return None

        dir_name = get_filtered_directory_name(exec_full_path, main_window.folder_exclude_set)
        name_override = name_processor.get_display_name(dir_name)

        is_demoted_flag = _is_demoted(
            exec_name_no_ext, name_override, dir_name,
            main_window.demoted_set, main_window.folder_demoted_set, name_processor
        )

        steam_name, steam_id, name_override = _get_steam_match(
            name_override, main_window.config, main_window.steam_cache_manager.normalized_steam_index, name_processor
        )

        # Generate kill list
        kill_list = []
        dir_path = os.path.dirname(exec_full_path)
        try:
            for f in os.listdir(dir_path):
                if f.lower().endswith('.exe') and f.lower() != filename.lower():
                    # Check exclusion for these too
                    should_exclude = False
                    for exclude_str in main_window.exclude_exe_set:
                        if exclude_str in f.lower():
                            should_exclude = True
                            break
                    if not should_exclude:
                        kill_list.append(f)
        except Exception:
            pass

        config = main_window.config
        game_data = {
            'create': not is_demoted_flag,
            'name': filename,
            'directory': os.path.dirname(exec_full_path),
            'steam_name': steam_name,
            'name_override': name_override,
            'steam_id': steam_id,
            'options': '',
            'arguments': '',
            'run_as_admin': config.run_as_admin,
            'hide_taskbar': config.hide_taskbar,
            'kill_list_enabled': config.use_kill_list,
            'kill_list': ",".join(kill_list),
            'terminate_borderless_on_exit': config.terminate_borderless_on_exit,

            # Paths from setup tab (only if enabled)
            'controller_mapper_path': config.controller_mapper_path if config.defaults.get('controller_mapper_path_enabled', True) else "",
            'borderless_windowing_path': config.borderless_gaming_path if config.defaults.get('borderless_gaming_path_enabled', True) else "",
            'multi_monitor_app_path': config.multi_monitor_tool_path if config.defaults.get('multi_monitor_tool_path_enabled', True) else "",
            'mm_game_profile': config.multimonitor_gaming_path if config.defaults.get('multimonitor_gaming_path_enabled', True) else "",
            'mm_desktop_profile': config.multimonitor_media_path if config.defaults.get('multimonitor_media_path_enabled', True) else "",
            'player1_profile': config.p1_profile_path if config.defaults.get('p1_profile_path_enabled', True) else "",
            'player2_profile': config.p2_profile_path if config.defaults.get('p2_profile_path_enabled', True) else "",
            'mediacenter_profile': config.mediacenter_profile_path if config.defaults.get('mediacenter_profile_path_enabled', True) else "",
            'just_after_launch_path': config.just_after_launch_path if config.defaults.get('just_after_launch_path_enabled', True) else "",
            'just_before_exit_path': config.just_before_exit_path if config.defaults.get('just_before_exit_path_enabled', True) else "",
            'pre1_path': config.pre1_path if config.defaults.get('pre1_path_enabled', True) else "", 'pre2_path': config.pre2_path if config.defaults.get('pre2_path_enabled', True) else "", 'pre3_path': config.pre3_path if config.defaults.get('pre3_path_enabled', True) else "",
            'post1_path': config.post1_path if config.defaults.get('post1_path_enabled', True) else "", 'post2_path': config.post2_path if config.defaults.get('post2_path_enabled', True) else "", 'post3_path': config.post3_path if config.defaults.get('post3_path_enabled', True) else "",
            'disc_mount_path': config.disc_mount_path if config.defaults.get('disc_mount_path_enabled', True) else "", 'disc_unmount_path': config.disc_unmount_path if config.defaults.get('disc_unmount_path_enabled', True) else "",
            'launcher_executable': config.launcher_executable if config.defaults.get('launcher_executable_enabled', True) else "",

            # Enabled states from setup tab (defaults)
            'controller_mapper_enabled': config.defaults.get('controller_mapper_path_enabled', True),
            'borderless_windowing_enabled': config.defaults.get('borderless_gaming_path_enabled', True),
            'multi_monitor_app_enabled': config.defaults.get('multi_monitor_tool_path_enabled', True),
            'just_after_launch_enabled': config.defaults.get('just_after_launch_path_enabled', True),
            'just_before_exit_enabled': config.defaults.get('just_before_exit_path_enabled', True),
            'pre_1_enabled': config.defaults.get('pre1_path_enabled', True), 'pre_2_enabled': config.defaults.get('pre2_path_enabled', True), 'pre_3_enabled': config.defaults.get('pre3_path_enabled', True),
            'post_1_enabled': config.defaults.get('post1_path_enabled', True), 'post_2_enabled': config.defaults.get('post2_path_enabled', True), 'post_3_enabled': config.defaults.get('post3_path_enabled', True),
            'disc_mount_enabled': config.defaults.get('disc_mount_path_enabled', True), 'disc_unmount_enabled': config.defaults.get('disc_unmount_path_enabled', True),
            'launcher_executable_enabled': config.defaults.get('launcher_executable_enabled', True),

            # Profile enabled states
            'player1_profile_enabled': config.defaults.get('p1_profile_path_enabled', True),
            'player2_profile_enabled': config.defaults.get('p2_profile_path_enabled', True),
            'mediacenter_profile_enabled': config.defaults.get('mediacenter_profile_path_enabled', True),
            'mm_game_profile_enabled': config.defaults.get('multimonitor_gaming_path_enabled', True),
            'mm_desktop_profile_enabled': config.defaults.get('multimonitor_media_path_enabled', True),

            # Overwrite states (default to global config)
            'controller_mapper_overwrite': config.overwrite_states.get('controller_mapper_path', True),
            'borderless_windowing_overwrite': config.overwrite_states.get('borderless_gaming_path', True),
            'multi_monitor_app_overwrite': config.overwrite_states.get('multi_monitor_tool_path', True),
            'just_after_launch_overwrite': config.overwrite_states.get('just_after_launch_path', True),
            'just_before_exit_overwrite': config.overwrite_states.get('just_before_exit_path', True),
            'pre_1_overwrite': config.overwrite_states.get('pre1_path', True),
            'pre_2_overwrite': config.overwrite_states.get('pre2_path', True),
            'pre_3_overwrite': config.overwrite_states.get('pre3_path', True),
            'post_1_overwrite': config.overwrite_states.get('post1_path', True),
            'post_2_overwrite': config.overwrite_states.get('post2_path', True),
            'post_3_overwrite': config.overwrite_states.get('post3_path', True),
            'disc_mount_overwrite': config.overwrite_states.get('disc_mount_path', True),
            'disc_unmount_overwrite': config.overwrite_states.get('disc_unmount_path', True),
            'player1_profile_overwrite': config.overwrite_states.get('p1_profile_path', True),
            'player2_profile_overwrite': config.overwrite_states.get('p2_profile_path', True),
            'mediacenter_profile_overwrite': config.overwrite_states.get('mediacenter_profile_path', True),
            'mm_game_profile_overwrite': config.overwrite_states.get('multimonitor_gaming_path', True),
            'mm_desktop_profile_overwrite': config.overwrite_states.get('multimonitor_media_path', True),
            'launcher_executable_overwrite': config.overwrite_states.get('launcher_executable', True),

            # Run-wait states from setup tab
            'controller_mapper_run_wait': config.run_wait_states.get('controller_mapper_path_run_wait', False),
            'borderless_windowing_run_wait': config.run_wait_states.get('borderless_gaming_path_run_wait', False),
            'multi_monitor_app_run_wait': config.run_wait_states.get('multi_monitor_tool_path_run_wait', False),
            'just_after_launch_run_wait': config.run_wait_states.get('just_after_launch_path_run_wait', False),
            'just_before_exit_run_wait': config.run_wait_states.get('just_before_exit_path_run_wait', False),
            'pre_1_run_wait': config.run_wait_states.get('pre1_path_run_wait', False), 'pre_2_run_wait': config.run_wait_states.get('pre2_path_run_wait', False), 'pre_3_run_wait': config.run_wait_states.get('pre3_path_run_wait', False),
            'post_1_run_wait': config.run_wait_states.get('post1_path_run_wait', False), 'post_2_run_wait': config.run_wait_states.get('post2_path_run_wait', False), 'post_3_run_wait': config.run_wait_states.get('post3_path_run_wait', False),
            'disc_mount_run_wait': config.run_wait_states.get('disc_mount_path_run_wait', False), 'disc_unmount_run_wait': config.run_wait_states.get('disc_unmount_path_run_wait', False),
        }
        return game_data
    except PermissionError:
        logging.warning(f"Permission denied for: {exec_full_path}")
    except Exception as e:
        logging.error(f"Error processing file {exec_full_path}: {e}", exc_info=True)
    return None


def index_games(main_window, progress_callback=None) -> list:
    """
    Indexes games from source directories and returns a list of game data dictionaries.
    This function is decoupled from the UI and returns data, not a count.
    """
    config = main_window.config
    found_executables = []

    # Instantiate NameProcessor once for efficiency
    name_processor = NameProcessor(
        release_groups_set=main_window.release_groups_set,
        exclude_exe_set=main_window.exclude_exe_set
    )

    # Handle exclusion of games from other managers
    if config.exclude_selected_manager_games and config.game_managers_present != "None":
        main_window._locate_and_exclude_manager_config()

    for source_dir in config.source_dirs:
        if not os.path.exists(source_dir):
            logging.warning(f"Source directory not found, skipping: {source_dir}")
            continue

        for root, _, files in os.walk(source_dir):
            if progress_callback:
                progress_callback(root)

            if getattr(main_window, 'indexing_cancelled', False):
                logging.info("Indexing cancelled by user.")
                return found_executables

            # Check if this directory is excluded or is a subdirectory of an excluded directory
            root_normalized = os.path.normpath(root).lower()
            is_excluded = any(
                root_normalized == os.path.normpath(excluded).lower() or
                root_normalized.startswith(os.path.normpath(excluded).lower() + os.sep)
                for excluded in config.excluded_dirs
            )
            if is_excluded:
                # Skip this directory and all its subdirectories
                dirs[:] = []  # Clear dirs list to prevent os.walk from descending
                continue

            for filename in files:
                if not filename.lower().endswith('.exe'):
                    continue

                exec_full_path = os.path.join(root, filename)
                exec_full_path_lower = exec_full_path.lower()
                if exec_full_path_lower in main_window.processed_paths:
                    continue
                main_window.processed_paths.add(exec_full_path_lower)

                game_data = _process_executable(
                    exec_full_path, main_window, name_processor
                )

                if game_data:
                    found_executables.append(game_data)

    return found_executables
