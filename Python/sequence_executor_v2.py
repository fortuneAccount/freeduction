"""
Refactored sequence executor using the plugin system
"""

import json
import os
import platform
import logging
from typing import Optional, Any

# Conditional imports for Windows-specific features
if platform.system() == 'Windows':
    import win32gui
    import win32con

from Python.plugins.base_plugin import PluginConfig


class SequenceExecutorV2:
    """
    Plugin-based sequence executor for the GameLauncher.
    
    This version uses the plugin system for tool execution while maintaining
    backward compatibility with legacy actions.
    """

    def __init__(self, launcher):
        self.launcher = launcher
        self.plugin_manager = getattr(launcher, 'plugin_manager', None)
        self.taskbar_hwnd = None
        self.taskbar_was_hidden = False
        self.running_processes = {}  # Track stoppable processes

        if platform.system() == 'Windows':
            try:
                self.taskbar_hwnd = win32gui.FindWindow("Shell_TrayWnd", None)
            except Exception as e:
                self.launcher.show_message(f"Could not find taskbar: {e}")

        # Core system actions (not plugin-based)
        self.system_actions = {
            'Kill-Game': self.kill_game_process,
            'Kill-List': self.kill_process_list,
            'No-TB': self.hide_taskbar,
            'Taskbar': self.show_taskbar,
            'mount-disc': self.mount_disc,
            'Unmount-disc': self.unmount_disc,
        }
        
        # Plugin-based actions
        self.plugin_actions = {
            'Controller-Mapper': 'antimicrox',
            'Monitor-Config': 'monitorapp',
            'Borderless': 'borderless',
            'Cloud-Sync': 'rclone',  # or 'ludusavi'
        }
        
        # Generic app actions (legacy support)
        self.generic_actions = {
            'Pre1': ('pre_launch_app_1', 'pre_launch_app_1_wait', 'pre_launch_app_1_options', 'pre_launch_app_1_arguments'),
            'Pre2': ('pre_launch_app_2', 'pre_launch_app_2_wait', 'pre_launch_app_2_options', 'pre_launch_app_2_arguments'),
            'Pre3': ('pre_launch_app_3', 'pre_launch_app_3_wait', 'pre_launch_app_3_options', 'pre_launch_app_3_arguments'),
            'Post1': ('post_launch_app_1', 'post_launch_app_1_wait', 'post_launch_app_1_options', 'post_launch_app_1_arguments'),
            'Post2': ('post_launch_app_2', 'post_launch_app_2_wait', 'post_launch_app_2_options', 'post_launch_app_2_arguments'),
            'Post3': ('post_launch_app_3', 'post_launch_app_3_wait', 'post_launch_app_3_options', 'post_launch_app_3_arguments'),
            'JustAfterLaunch': ('just_after_launch_app', 'just_after_launch_wait', 'just_after_launch_options', 'just_after_launch_arguments'),
            'JustBeforeExit': ('just_before_exit_app', 'just_before_exit_wait', 'just_before_exit_options', 'just_before_exit_arguments'),
        }

    def execute(self, sequence_name: str):
        """Execute a named sequence from the launcher's configuration."""
        sequence = getattr(self.launcher, sequence_name, [])
        is_exit_sequence = (sequence_name == 'exit_sequence')

        self.launcher.show_message(f"Executing {sequence_name}...")
        logging.info(f"Executing sequence: {sequence_name}")
        
        for item in sequence:
            item = item.strip()
            if not item:
                continue

            self.launcher.show_message(f"  - Running: {item}")
            logging.info(f"  - Action: {item}")
            
            try:
                self._execute_action(item, is_exit_sequence)
            except Exception as e:
                self.launcher.show_message(f"  - Error executing '{item}': {e}")
                logging.error(f"Error executing sequence item '{item}': {e}", exc_info=True)

    def _execute_action(self, action_name: str, is_exit: bool):
        """Execute a single action, trying plugin system first, then fallback to legacy."""
        
        # Try system actions first
        if action_name in self.system_actions:
            self.system_actions[action_name]()
            return
        
        
        
        # Try plugin-based actions
        if action_name in self.plugin_actions:
            plugin_name = self.plugin_actions[action_name]
            if self._execute_plugin_action(plugin_name, is_exit):
                return
            # If plugin execution failed, fall through to legacy
        
        # Try generic app actions
        if action_name in self.generic_actions:
            attrs = self.generic_actions[action_name]
            self.run_generic_app(*attrs)
            return
        
        # Unknown action
        self.launcher.show_message(f"  - Unknown action: {action_name}")
        logging.warning(f"Unknown action in sequence: {action_name}")

    def _execute_plugin_action(self, plugin_name: str, is_exit: bool) -> bool:
        """
        Execute an action using a plugin.
        
        Returns:
            True if plugin execution succeeded, False otherwise
        """
        if not self.plugin_manager:
            logging.debug(f"Plugin manager not available for {plugin_name}")
            return False
        
        plugin = self.plugin_manager.registry.get_plugin(plugin_name)
        if not plugin:
            logging.debug(f"Plugin not found: {plugin_name}")
            return False
        
        # Build configuration from launcher attributes
        config = self._build_plugin_config(plugin, plugin_name)
        if not config or not config.tool_path:
            logging.debug(f"Could not build config for {plugin_name}")
            return False
        
        # Build command
        if is_exit and plugin.supports_exit_action():
            cmd = plugin.build_exit_command(config)
        else:
            cmd = plugin.build_launch_command(config)
        
        if not cmd:
            logging.debug(f"Plugin {plugin_name} returned no command")
            return False
        
        # Execute command
        logging.info(f"Executing plugin command for {plugin.display_name}: {cmd}")
        wait = config.wait
        process = self.launcher.run_process(cmd, wait=wait)
        
        # Track process if needed
        if process and not wait and plugin.should_track_process():
            self.running_processes[plugin_name] = process
        
        return True

    def _build_plugin_config(self, plugin, plugin_name: str) -> Optional[PluginConfig]:
        """Build a PluginConfig from launcher attributes."""
        
        # Get tool path
        tool_path = self._get_launcher_attr(f'{plugin_name}_app', None)
        if not tool_path:
            # Try alternative attribute names
            alt_names = {
                'antimicrox': 'controller_mapper_app',
                'monitorapp': 'monitorapp',
                'borderless': 'borderless_app',
                'rclone': 'rclone_app',
                'ludusavi': 'ludusavi_app'
            }
            tool_path = self._get_launcher_attr(alt_names.get(plugin_name, ''), None)
        
        if not tool_path:
            return None
        
        # Resolve path
        tool_path = self.launcher.resolve_path(tool_path)
        if not os.path.exists(tool_path):
            return None
        
        # Get options and arguments
        options = self._get_launcher_attr(f'{plugin_name}_options', '')
        arguments = self._get_launcher_attr(f'{plugin_name}_arguments', '')
        wait = self._get_launcher_attr(f'{plugin_name}_wait', False)
        
        # Build custom fields from plugin schema
        custom_fields = {}
        schema = plugin.get_config_schema()
        for field_name, field_def in schema.items():
            # Try to find matching launcher attribute
            # First try plugin-specific attribute (e.g., rclone_remote_name)
            attr_name = f'{plugin_name}_{field_name}'
            value = self._get_launcher_attr(attr_name, None)
            
            # If not found, use default from schema
            if value is None:
                value = field_def.default
            
            if value is not None:
                custom_fields[field_name] = value
        
        return PluginConfig(
            tool_path=tool_path,
            options=options,
            arguments=arguments,
            wait=wait,
            custom_fields=custom_fields
        )

    def _get_launcher_attr(self, attr_name: str, default: Any = None) -> Any:
        """Safely get an attribute from the launcher."""
        return getattr(self.launcher, attr_name, default)

    # Legacy methods for backward compatibility
    def run_generic_app(self, app_attr, wait_attr, options_attr=None, args_attr=None):
        """Run a generic application (legacy support)."""
        app_path = self.launcher.resolve_path(getattr(self.launcher, app_attr, ''))
        wait = getattr(self.launcher, wait_attr, False)
        options = getattr(self.launcher, options_attr, '') if options_attr else ''
        args = getattr(self.launcher, args_attr, '') if args_attr else ''

        if app_path and os.path.exists(app_path):
            logging.info(f"Running generic app: {app_path} (Wait: {wait})")
            cmd = f'"{app_path}"'
            if options:
                cmd += f' {options}'
            if args:
                cmd += f' {args}'
            process = self.launcher.run_process(cmd, wait=wait)
            if process and not wait:
                self.running_processes[app_attr] = process

    # System actions
    def hide_taskbar(self):
        """Hide the Windows taskbar."""
        hide = getattr(self.launcher, 'hide_taskbar', False)
        if hide and self.taskbar_hwnd and platform.system() == 'Windows':
            logging.info("Hiding Taskbar")
            try:
                win32gui.ShowWindow(self.taskbar_hwnd, win32con.SW_HIDE)
                self.taskbar_was_hidden = True
            except Exception as e:
                self.launcher.show_message(f"Failed to hide taskbar: {e}")
                logging.error(f"Failed to hide taskbar: {e}", exc_info=True)

    def show_taskbar(self):
        """Show the Windows taskbar."""
        if self.taskbar_hwnd and platform.system() == 'Windows':
            logging.info("Showing Taskbar")
            try:
                win32gui.ShowWindow(self.taskbar_hwnd, win32con.SW_SHOW)
                self.taskbar_was_hidden = False
            except Exception as e:
                self.launcher.show_message(f"Failed to show taskbar: {e}")
                logging.error(f"Failed to show taskbar: {e}", exc_info=True)

    def kill_game_process(self):
        """Kill the game executable process."""
        game_path = getattr(self.launcher, 'game_path', '')
        if game_path:
            exe_name = os.path.basename(game_path)
            logging.info(f"Killing game process: {exe_name}")
            self.launcher.kill_process_by_name(exe_name)

    def kill_process_list(self):
        """Kill processes defined in the kill list."""
        kill_list = getattr(self.launcher, 'kill_list', [])
        if kill_list:
            logging.info("Executing Kill List...")
            self.launcher.kill_processes_in_list()

    def mount_disc(self):
        """Mount disc image."""
        # Delegate to launcher's mount_disc method if available
        if hasattr(self.launcher, 'mount_disc'):
            self.launcher.mount_disc()

    def unmount_disc(self):
        """Unmount disc image."""
        # Delegate to launcher's unmount_disc method if available
        if hasattr(self.launcher, 'unmount_disc'):
            self.launcher.unmount_disc()

    def ensure_cleanup(self):
        """Final cleanup to restore system state."""
        logging.info("Ensuring cleanup...")
        if self.taskbar_was_hidden:
            self.show_taskbar()
        self.kill_all_tracked()

    def kill_all_tracked(self):
        """Kill all tracked processes."""
        if platform.system() != 'Windows':
            return
        self.launcher.show_message("Cleaning up background processes...")
        logging.info("Cleaning up background processes...")
        for name, process in list(self.running_processes.items()):
            self.launcher.terminate_process_tree(process)
        self.running_processes.clear()
