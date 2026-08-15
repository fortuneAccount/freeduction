import os
import shutil
import logging

class JoystickProfileManager:
    """Manages joystick profiles for games"""
    
    def __init__(self):
        """Initialize the joystick profile manager"""
        self.logger = logging.getLogger(__name__)
        
        # Get script directory for templates
        self.script_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # Define template paths
        self.game_template_path = os.path.join(self.script_dir, "ax_GameTemplate.set")
        self.desktop_template_path = os.path.join(self.script_dir, "ax_DeskTemplate.set")
        self.triggers_template_path = os.path.join(self.script_dir, "ax_Trigger.set")
        self.kbm_template_path = os.path.join(self.script_dir, "ax_KBM_Template.set")
        
    def create_profiles(self, game_name, profile_dir):
        """Create all joystick profiles for a game
        
        Args:
            game_name: Name of the game
            profile_dir: Path to the game's profile directory
            
        Returns:
            Dictionary with paths to created profiles
        """
        # Create profiles directory if needed
        profiles_dir = os.path.join(profile_dir, "Profiles")
        os.makedirs(profiles_dir, exist_ok=True)
        
        # Create the game profile
        game_profile_path = self.create_game_profile(game_name, profiles_dir)
        
        # Create the desktop profile
        desktop_profile_path = self.create_desktop_profile(game_name, profiles_dir)
        
        # Create the triggers profile
        triggers_profile_path = self.create_triggers_profile(game_name, profiles_dir)
        
        # Create the KBM profile
        kbm_profile_path = self.create_kbm_profile(game_name, profiles_dir)
        
        return {
            "game": game_profile_path,
            "desktop": desktop_profile_path,
            "triggers": triggers_profile_path,
            "kbm": kbm_profile_path
        }
    
    def create_game_profile(self, game_name, profiles_dir):
        """Create the game joystick profile
        
        Args:
            game_name: Name of the game
            profiles_dir: Path to the profiles directory
            
        Returns:
            Path to the created profile or None if failed
        """
        try:
            # Create safe file name
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_name)
            
            # Create the profile path
            profile_path = os.path.join(profiles_dir, f"{safe_name}.gamecontroller.amgp")
            
            # Process the template
            self._process_template(self.game_template_path, profile_path, game_name)
            
            return profile_path
        except Exception as e:
            self.logger.error(f"Error creating game profile for {game_name}: {str(e)}")
            return None
    
    def create_desktop_profile(self, game_name, profiles_dir):
        """Create the desktop joystick profile
        
        Args:
            game_name: Name of the game
            profiles_dir: Path to the profiles directory
            
        Returns:
            Path to the created profile or None if failed
        """
        try:
            # Create safe file name
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_name)
            
            # Create the profile path
            profile_path = os.path.join(profiles_dir, f"{safe_name}_Desktop.gamecontroller.amgp")
            
            # Process the template
            self._process_template(self.desktop_template_path, profile_path, game_name)
            
            return profile_path
        except Exception as e:
            self.logger.error(f"Error creating desktop profile for {game_name}: {str(e)}")
            return None
    
    def create_triggers_profile(self, game_name, profiles_dir):
        """Create the triggers joystick profile
        
        Args:
            game_name: Name of the game
            profiles_dir: Path to the profiles directory
            
        Returns:
            Path to the created profile or None if failed
        """
        try:
            # Create safe file name
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_name)
            
            # Create the profile path
            profile_path = os.path.join(profiles_dir, f"{safe_name}_Trigger.gamecontroller.amgp")
            
            # Process the template
            self._process_template(self.triggers_template_path, profile_path, game_name)
            
            return profile_path
        except Exception as e:
            self.logger.error(f"Error creating triggers profile for {game_name}: {str(e)}")
            return None
    
    def create_kbm_profile(self, game_name, profiles_dir):
        """Create the keyboard and mouse (KBM) joystick profile
        
        Args:
            game_name: Name of the game
            profiles_dir: Path to the profiles directory
            
        Returns:
            Path to the created profile or None if failed
        """
        try:
            # Create safe file name
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_name)
            
            # Create the profile path
            profile_path = os.path.join(profiles_dir, f"{safe_name}_KBM.gamecontroller.amgp")
            
            # Process the template
            self._process_template(self.kbm_template_path, profile_path, game_name)
            
            return profile_path
        except Exception as e:
            self.logger.error(f"Error creating KBM profile for {game_name}: {str(e)}")
            return None
    
    def _process_template(self, template_path, output_path, game_name):
        """Process a template file, replacing variables and writing to output
        
        Args:
            template_path: Path to the template file
            output_path: Path where the processed file will be saved
            game_name: Name of the game for replacement
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if template exists
            if not os.path.exists(template_path):
                self.logger.error(f"Template file not found: {template_path}")
                return False
            
            # Read the template
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Replace placeholders
            content = content.replace("{{GAME_NAME}}", game_name)
            
            # Write the processed file
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return True
        except Exception as e:
            self.logger.error(f"Error processing template {template_path}: {str(e)}")
            return False
    
    def import_profile(self, source_path, game_name, profiles_dir, profile_type="game"):
        """Import an existing joystick profile for a game
        
        Args:
            source_path: Path to the source profile
            game_name: Name of the game
            profiles_dir: Path to the profiles directory
            profile_type: Type of profile ("game", "desktop", "triggers", "kbm")
            
        Returns:
            Path to the imported profile or None if failed
        """
        try:
            # Check if source file exists
            if not os.path.exists(source_path):
                self.logger.error(f"Source profile not found: {source_path}")
                return None
            
            # Create safe file name
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_name)
            
            # Determine output filename based on profile type
            if profile_type == "game":
                filename = f"{safe_name}.gamecontroller.amgp"
            elif profile_type == "desktop":
                filename = f"{safe_name}_Desktop.gamecontroller.amgp"
            elif profile_type == "triggers":
                filename = f"{safe_name}_Trigger.gamecontroller.amgp"
            else:  # kbm
                filename = f"{safe_name}_KBM.gamecontroller.amgp"
            
            # Create output path
            output_path = os.path.join(profiles_dir, filename)
            
            # Copy the file
            shutil.copy2(source_path, output_path)
            
            return output_path
        except Exception as e:
            self.logger.error(f"Error importing profile for {game_name}: {str(e)}")
            return None
    
    def export_profile(self, profile_path, destination_path):
        """Export a joystick profile to a destination
        
        Args:
            profile_path: Path to the profile to export
            destination_path: Destination path for the export
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Check if source file exists
            if not os.path.exists(profile_path):
                self.logger.error(f"Profile not found: {profile_path}")
                return False
            
            # Create the destination directory if needed
            os.makedirs(os.path.dirname(destination_path), exist_ok=True)
            
            # Copy the file
            shutil.copy2(profile_path, destination_path)
            
            return True
        except Exception as e:
            self.logger.error(f"Error exporting profile: {str(e)}")
            return False
    
    def find_existing_profiles(self, game_name, profiles_dir):
        """Find existing joystick profiles for a game
        
        Args:
            game_name: Name of the game
            profiles_dir: Path to the profiles directory
            
        Returns:
            Dictionary with paths to existing profiles
        """
        try:
            # Create safe file name
            from Python.ui.name_utils import make_safe_filename
            safe_name = make_safe_filename(game_name)
            
            # Define expected filenames
            filenames = {
                "game": f"{safe_name}.gamecontroller.amgp",
                "desktop": f"{safe_name}_Desktop.gamecontroller.amgp",
                "triggers": f"{safe_name}_Trigger.gamecontroller.amgp",
                "kbm": f"{safe_name}_KBM.gamecontroller.amgp"
            }
            
            # Check for existing profiles
            result = {}
            for profile_type, filename in filenames.items():
                path = os.path.join(profiles_dir, filename)
                if os.path.exists(path):
                    result[profile_type] = path
            
            return result
        except Exception as e:
            self.logger.error(f"Error finding profiles for {game_name}: {str(e)}")
            return {}