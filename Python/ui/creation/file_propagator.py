import os
import shutil
import logging

class FilePropagator:
    """Handles file copying and template operations for game environments"""
    
    def __init__(self, profiles_dir="", launchers_dir=""):
        """Initialize the file propagator
        
        Args:
            profiles_dir: Path to the profiles directory
            launchers_dir: Path to the launchers directory
        """
        self.profiles_dir = profiles_dir
        self.launchers_dir = launchers_dir
        self.logger = logging.getLogger(__name__)
        
        # Get script directory for templates
        self.script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.app_root_dir = os.path.dirname(self.script_dir)
        
    def set_directories(self, profiles_dir, launchers_dir):
        """Set the profiles and launchers directories
        
        Args:
            profiles_dir: Path to the profiles directory
            launchers_dir: Path to the launchers directory
        """
        self.profiles_dir = profiles_dir
        self.launchers_dir = launchers_dir
        
    def ensure_directories_exist(self):
        """Ensure all necessary directories exist
        
        Returns:
            True if directories exist or were created, False otherwise
        """
        try:
            # Create directories if they don't exist
            if self.profiles_dir:
                os.makedirs(self.profiles_dir, exist_ok=True)
                
            if self.launchers_dir:
                os.makedirs(self.launchers_dir, exist_ok=True)
                
            return True
        except Exception as e:
            self.logger.error(f"Error creating directories: {str(e)}")
            return False
            
    def create_profile_directory(self, game_name):
        """Create a profile directory for a game
        
        Args:
            game_name: Name of the game (used as directory name)
            
        Returns:
            Path to created profile directory or None if failed
        """
        try:
            # Create a safe directory name from the game name
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_name)
            
            # Create the profile directory path
            profile_dir = os.path.join(self.profiles_dir, safe_name)
            
            # Create the directory if it doesn't exist
            os.makedirs(profile_dir, exist_ok=True)
            
            # Create subdirectories for profiles, saves, etc.
            os.makedirs(os.path.join(profile_dir, "Profiles"), exist_ok=True)
            os.makedirs(os.path.join(profile_dir, "Saves"), exist_ok=True)
            
            return profile_dir
            
        except Exception as e:
            self.logger.error(f"Error creating profile directory for {game_name}: {str(e)}")
            return None
            
    def copy_template(self, template_path, destination_path, replacements=None, overwrite=True):
        """Copy a template file with variable replacements
        
        Args:
            template_path: Path to the template file
            destination_path: Path where the processed file will be saved
            replacements: Dictionary of replacements (e.g., {"{{VAR}}": "value"})
            overwrite: Whether to overwrite existing files
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check overwrite
            if os.path.exists(destination_path) and not overwrite:
                return True

            # Check if the template exists
            if not os.path.exists(template_path):
                self.logger.error(f"Template file not found: {template_path}")
                return False
                
            # Read the template
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Apply replacements
            if replacements:
                for key, value in replacements.items():
                    content = content.replace(key, str(value))
                    
            # Create the destination directory if it doesn't exist
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            
            # Write the processed file
            with open(destination_path, 'w', encoding='utf-8') as f:
                f.write(content)
                
            return True
            
        except Exception as e:
            self.logger.error(f"Error copying template: {str(e)}")
            return False
            
    def copy_file(self, source_path, destination_path, overwrite=True):
        """Copy a file from source to destination
        
        Args:
            source_path: Path to the source file
            destination_path: Path where the file will be copied
            overwrite: Whether to overwrite existing files
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check overwrite
            if os.path.exists(destination_path) and not overwrite:
                return True

            # Check if the source file exists
            if not os.path.exists(source_path):
                self.logger.error(f"Source file not found: {source_path}")
                return False
                
            # Create the destination directory if it doesn't exist
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            
            # Copy the file
            shutil.copy2(source_path, destination_path)
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error copying file: {str(e)}")
            return False
            
    def create_launcher(self, game_name, executable_path, working_dir, arguments="", profile_dir="", overwrite=True):
        """Create a launcher batch file for a game
        
        Args:
            game_name: Name of the game
            executable_path: Path to the game executable
            working_dir: Working directory for the game
            arguments: Command line arguments for the game
            profile_dir: Path to the profile directory
            overwrite: Whether to overwrite existing launcher
            
        Returns:
            Path to created launcher file or None if failed
        """
        try:
            # Get template path
            template_path = os.path.join(self.script_dir, "cmdtemplate.set")
            
            # Create a safe file name
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_name)
            
            # Create the launcher file path
            launcher_path = os.path.join(self.launchers_dir, f"{safe_name}.bat")
            
            # Create replacements dictionary
            replacements = {
                "{{GAME_NAME}}": game_name,
                "{{EXECUTABLE}}": executable_path,
                "{{DIRECTORY}}": working_dir,
                "{{ARGUMENTS}}": arguments,
                "{{PROFILE_FOLDER}}": profile_dir
            }
            
            # Copy the template with replacements
            if not self.copy_template(template_path, launcher_path, replacements, overwrite=overwrite):
                return None
                
            return launcher_path
            
        except Exception as e:
            self.logger.error(f"Error creating launcher for {game_name}: {str(e)}")
            return None
            
    def create_shortcut(self, game_name, target_path, icon_path=None, overwrite=True):
        """Create a shortcut to a launcher or executable
        
        Args:
            game_name: Name of the game (used for shortcut name)
            target_path: Path to the target file
            icon_path: Path to an icon file (optional)
            overwrite: Whether to overwrite existing shortcut
            
        Returns:
            Path to created shortcut or None if failed
        """
        try:
            # Get the path to Shortcut.exe
            shortcut_exe = os.path.join(self.app_root_dir, "bin", "Shortcut.exe")
            
            # Check if Shortcut.exe exists
            if not os.path.exists(shortcut_exe):
                self.logger.error(f"Shortcut.exe not found at {shortcut_exe}")
                return None
                
            # Create a safe file name
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_name)
            
            # Create the shortcut file path
            shortcut_path = os.path.join(self.launchers_dir, f"{safe_name}.lnk")
            
            # Check overwrite
            if os.path.exists(shortcut_path) and not overwrite:
                return shortcut_path

            # Build the command to create the shortcut
            import subprocess
            cmd = [
                shortcut_exe,
                "/F:" + shortcut_path,
                "/A:C",
                "/T:" + target_path,
                "/W:" + os.path.dirname(target_path),
                "/N:" + game_name
            ]
            
            # Add icon if provided
            if icon_path and os.path.exists(icon_path):
                cmd.append("/I:" + icon_path)
            # Otherwise use default Joystick.ico if available
            elif os.path.exists(os.path.join(self.script_dir, "Joystick.ico")):
                cmd.append("/I:" + os.path.join(self.script_dir, "Joystick.ico"))
                
            # Execute the command
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                self.logger.error(f"Error creating shortcut: {result.stderr}")
                return None
                
            return shortcut_path
            
        except Exception as e:
            self.logger.error(f"Error creating shortcut for {game_name}: {str(e)}")
            return None