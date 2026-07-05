"""
Path Discovery Utility for Save/Config File Detection

This module handles dynamic discovery of save and config files based on
template paths from PCGW data stored in Game.ini [SYSTEM] section.
"""

import os
import glob
import logging
import configparser


class PathDiscovery:
    """Discovers and resolves save/config file paths from templates."""
    
    def __init__(self, game_ini_path):
        """
        Initialize path discovery for a game.
        
        Args:
            game_ini_path: Path to the Game.ini file
        """
        self.game_ini_path = game_ini_path
        self.config = configparser.ConfigParser(interpolation=None)
        self.config.read(game_ini_path, encoding='utf-8')
        
        # Get game directory for template expansion
        self.game_directory = self.config.get('Game', 'Directory', fallback='')
        self.game_name = self.config.get('Game', 'Name', fallback='')

        # Cache for expensive lookups
        self._steam_path_cache = None
        self._steam_user_id_cache = None
    
    def needs_discovery(self):
        """
        Check if path discovery is needed.
        
        Returns True if:
        - [SYSTEM] section exists with queryable paths
        - [SAVE] or [CONFIG] sections are empty or have missing keys
        """
        if not self.config.has_section('SYSTEM'):
            return False
        
        # Check if we have any SYSTEM keys
        system_keys = self.config.options('SYSTEM')
        if not system_keys:
            return False
        
        # Check if SAVE/CONFIG sections are incomplete
        has_save_section = self.config.has_section('SAVE')
        has_config_section = self.config.has_section('CONFIG')
        
        # Extract platforms from SYSTEM keys
        platforms = set()
        for key in system_keys:
            if key.endswith('_save') or key.endswith('_config'):
                platform = key.rsplit('_', 1)[0]
                platforms.add(platform)
        
        # Check if any platform is missing from SAVE/CONFIG sections
        for platform in platforms:
            if not has_save_section or not self.config.has_option('SAVE', platform):
                return True
            if not has_config_section or not self.config.has_option('CONFIG', platform):
                return True
        
        return False
    
    def expand_template(self, template_path):
        """
        Expand template variables in a path.
        
        Supported variables:
        - <path-to-game> → Game directory
        - <Steam-folder> → Steam installation path
        - <user-id> → Steam user ID (if detectable)
        - %LOCALAPPDATA% → Local AppData folder
        - %APPDATA% → Roaming AppData folder
        - %USERPROFILE% → User profile folder
        - %PROGRAMFILES% → Program Files folder
        - %PROGRAMFILES(X86)% → Program Files (x86) folder
        
        Args:
            template_path: Path with template variables
            
        Returns:
            Expanded path string
        """
        expanded = template_path
        
        # Replace game-specific variables
        if '<path-to-game>' in expanded:
            expanded = expanded.replace('<path-to-game>', self.game_directory)
        
        # Replace Steam variables
        if '<Steam-folder>' in expanded or '<steam-folder>' in expanded:
            steam_path = self._find_steam_path()
            if steam_path:
                expanded = expanded.replace('<Steam-folder>', steam_path)
                expanded = expanded.replace('<steam-folder>', steam_path)
        
        if '<user-id>' in expanded:
            user_id = self._find_steam_user_id()
            if user_id:
                expanded = expanded.replace('<user-id>', user_id)
        
        # Replace Windows environment variables
        expanded = os.path.expandvars(expanded)
        
        return expanded
    
    def _find_steam_path(self):
        """Find Steam installation path."""
        if self._steam_path_cache:
            return self._steam_path_cache

        # Common Steam installation paths
        raw_paths = [
            r'C:\Program Files (x86)\Steam',
            r'C:\Program Files\Steam',
            os.path.expandvars(r'%PROGRAMFILES(X86)%\Steam'),
            os.path.expandvars(r'%PROGRAMFILES%\Steam'),
        ]
        # Deduplicate while preserving order
        possible_paths = list(dict.fromkeys(raw_paths))
        
        for path in possible_paths:
            if os.path.exists(path):
                self._steam_path_cache = path
                return path
        
        return None
    
    def _find_steam_user_id(self):
        """Find Steam user ID (most recently used)."""
        if self._steam_user_id_cache:
            return self._steam_user_id_cache

        steam_path = self._find_steam_path()
        if not steam_path:
            return None
        
        userdata_path = os.path.join(steam_path, 'userdata')
        if not os.path.exists(userdata_path):
            return None
        
        # Find most recently modified user directory
        try:
            user_dirs = [d for d in os.listdir(userdata_path) 
                        if os.path.isdir(os.path.join(userdata_path, d)) and d.isdigit()]
            
            if user_dirs:
                # Get most recently modified
                user_dirs.sort(key=lambda d: os.path.getmtime(os.path.join(userdata_path, d)), reverse=True)
                self._steam_user_id_cache = user_dirs[0]
                return self._steam_user_id_cache
        except Exception as e:
            logging.warning(f"Failed to find Steam user ID: {e}")
        
        return None
    
    def discover_paths(self, path_type='both'):
        """
        Discover actual file paths from templates.
        
        Args:
            path_type: 'save', 'config', or 'both'
            
        Returns:
            Dictionary with discovered paths:
            {
                'save': {platform: [path1, path2, ...]},
                'config': {platform: [path1, path2, ...]}
            }
        """
        discovered = {
            'save': {},
            'config': {}
        }
        
        if not self.config.has_section('SYSTEM'):
            return discovered
        
        # Process each SYSTEM key
        for key in self.config.options('SYSTEM'):
            if not (key.endswith('_save') or key.endswith('_config')):
                continue
            
            # Determine type and platform
            if key.endswith('_save'):
                if path_type not in ('save', 'both'):
                    continue
                file_type = 'save'
                platform = key[:-5]  # Remove '_save'
            elif key.endswith('_config'):
                if path_type not in ('config', 'both'):
                    continue
                file_type = 'config'
                platform = key[:-7]  # Remove '_config'
            else:
                continue
            
            # Get template paths
            template_value = self.config.get('SYSTEM', key)
            template_paths = template_value.split('|')
            
            # Discover actual paths
            actual_paths = []
            for template in template_paths:
                template = template.strip()
                if not template:
                    continue
                
                # Expand template variables
                expanded = self.expand_template(template)
                
                # Check if path exists (handle wildcards)
                if '*' in expanded or '?' in expanded:
                    # Use glob for wildcards
                    try:
                        matches = glob.glob(expanded, recursive=False)
                        actual_paths.extend(matches)
                    except Exception as e:
                        logging.debug(f"Glob failed for {expanded}: {e}")
                else:
                    # Direct path check
                    if os.path.exists(expanded):
                        actual_paths.append(expanded)
            
            # Store discovered paths
            if actual_paths:
                discovered[file_type][platform] = actual_paths
                logging.info(f"Discovered {len(actual_paths)} {file_type} paths for {platform}")
        
        return discovered
    
    def update_game_ini(self, discovered_paths):
        """
        Update Game.ini with discovered paths.
        
        Args:
            discovered_paths: Dictionary from discover_paths()
            
        Returns:
            True if any updates were made
        """
        updated = False
        
        # Ensure sections exist
        if not self.config.has_section('SAVE'):
            self.config.add_section('SAVE')
        if not self.config.has_section('CONFIG'):
            self.config.add_section('CONFIG')
        
        # Update SAVE section
        for platform, paths in discovered_paths.get('save', {}).items():
            if paths:
                # Only update if key doesn't exist or is empty
                if not self.config.has_option('SAVE', platform) or not self.config.get('SAVE', platform):
                    pipe_delimited = '|'.join(paths)
                    self.config.set('SAVE', platform, pipe_delimited)
                    updated = True
                    logging.info(f"Updated [SAVE] {platform} with {len(paths)} paths")
        
        # Update CONFIG section
        for platform, paths in discovered_paths.get('config', {}).items():
            if paths:
                # Only update if key doesn't exist or is empty
                if not self.config.has_option('CONFIG', platform) or not self.config.get('CONFIG', platform):
                    pipe_delimited = '|'.join(paths)
                    self.config.set('CONFIG', platform, pipe_delimited)
                    updated = True
                    logging.info(f"Updated [CONFIG] {platform} with {len(paths)} paths")
        
        # Write back to file if updated
        if updated:
            with open(self.game_ini_path, 'w', encoding='utf-8') as configfile:
                self.config.write(configfile)
            logging.info(f"Updated {self.game_ini_path} with discovered paths")
        
        return updated
    
    def run_discovery(self, context='launch'):
        """
        Main entry point: check if discovery is needed and run it.
        
        Args:
            context: 'launch' or 'exit' - indicates when discovery is running
        
        Returns:
            True if discovery was run and paths were updated
        """
        if not self.needs_discovery():
            logging.debug(f"Path discovery not needed for {self.game_name}")
            return False
        
        logging.info(f"Running path discovery for {self.game_name} ({context})")
        
        discovered = self.discover_paths()
        
        total_found = sum(len(paths) for paths in discovered['save'].values()) + \
                     sum(len(paths) for paths in discovered['config'].values())
        
        if total_found == 0:
            logging.info(f"No paths discovered for {self.game_name} ({context})")
            return False
        
        logging.info(f"Discovered {total_found} total paths for {self.game_name} ({context})")
        
        return self.update_game_ini(discovered)


def discover_and_update_paths(game_ini_path, context='launch'):
    """
    Convenience function to run path discovery on a Game.ini file.
    
    Args:
        game_ini_path: Path to Game.ini file
        context: 'launch' or 'exit' - indicates when discovery is running
        
    Returns:
        True if paths were discovered and updated
    """
    try:
        discovery = PathDiscovery(game_ini_path)
        return discovery.run_discovery(context=context)
    except Exception as e:
        logging.error(f"Path discovery failed for {game_ini_path}: {e}", exc_info=True)
        return False
