import os
import re
from typing import Set, Dict, Tuple, Optional, Any

class NameProcessor:
    """
    Class for processing game names according to specified rules.
    Handles release group removal, version tag removal, and other name cleaning operations.
    """
    
    def __init__(self, 
                 release_groups_set: Optional[set[str]] = None,
                 exclude_exe_set: Optional[set[str]] = None,
                 source_dirs: Optional[list[str]] = None):
        """
        Initialize the NameProcessor with optional sets of exclusions and source directories.
        
        Args:
            release_groups_set: Set of release group names to remove from game titles
            exclude_exe_set: Set of executable name patterns to exclude
            source_dirs: List of source directories being scanned
        """
        self.release_groups_set = release_groups_set or set()
        self.exclude_exe_set = exclude_exe_set or set()
        self.source_dirs = source_dirs or []
        
        # Compile common regex patterns
        self.delimiter_pattern = re.compile(r'[._\-]+')
        self.whitespace_pattern = re.compile(r'\s+')
        self.camel_case_pattern = re.compile(r'([a-z])([A-Z])')
        
        # Compile version patterns
        self.version_patterns = [
            re.compile(r'\s+v?[0-9]+(?:\.[0-9]+)*(?:-[a-zA-Z0-9]+)?$'),  # Version numbers like v1.2.3 or 1.2.3-alpha
            re.compile(r'\s+(?:build|bulid|bld)\s+[0-9]+$', re.IGNORECASE),  # Build numbers
            re.compile(r'\s+(?:early\s*access)$', re.IGNORECASE),  # Early Access
            re.compile(r'\s+(?:alpha|beta|demo|trial|playtest|preview)$', re.IGNORECASE),  # Development stages
            #re.compile(r'\s+(?:remaster(?:ed)?|hd)$', re.IGNORECASE),  # Remastered versions
        ]
        
        # Patterns for match name normalization
        self.non_alphanum_except_spaces_commas = re.compile(r'[^a-zA-Z0-9 ]') # Changed to remove commas initially
        self.prefix_pattern = re.compile(r'^(?:the|a|an)\s+', re.IGNORECASE)
        self.suffix_pattern = re.compile(r'\s+(?:game|edition|collection|complete|deluxe|goty|premium)$', re.IGNORECASE)
    
    def get_display_name(self, name: str) -> str:
        """
        Process a name to get a clean display name for the name-override field.
        
        Args:
            name: The name to process
            
        Returns:
            Clean display name
        """
        if not name:
            return ""
        
        # Store original for debugging
        original = name
        
        # The correct order of operations:
        
        # Step 1: Cull release group tags from the original name
        result = self.cull_release_group_tags(name)
        
        # Step 2: Cull version tags
        result = self.cull_version_tags(result)
        
        # Step 3: Replace delimiters with spaces
        result = self.replace_delimiters_with_spaces(result)
        
        # Step 4: Convert from camel case
        result = self.convert_from_camel_case(result)
        
        # Step 5: Clean whitespace
        result = self.clean_whitespace(result)
        
        # Step 6: Apply title case
        result = self.title_case(result)
        
        # Step 7: Final cleanup
        result = self.final_cleanup(result)
        
        return result
    
    def replace_delimiters_with_spaces(self, name: str) -> str:
        """
        Replace common delimiters with spaces.
        
        Args:
            name: The name to process
            
        Returns:
            Name with delimiters replaced by spaces
        """
        if not name:
            return ""
        
        # Replace common delimiters with spaces
        result = self.delimiter_pattern.sub(' ', name)
        
        return result
    
    def cull_release_group_tags(self, name: str) -> str:
        """
        Cull release group tags from a name with original delimiters intact.
        Only removes release groups that appear at the end of the name.
        
        Args:
            name: The name to process
        
        Returns:
            Name with release group tags culled
        """
        if not name or not self.release_groups_set:
            return name
        
        result = name
        original = name
        
        # Sort release groups by length (longest first) to avoid partial matches
        sorted_groups = sorted(self.release_groups_set, key=len, reverse=True)
        
        # Check for release groups at the end of the name
        for group in sorted_groups:
            if not group or len(group) <= 2:  # Skip very short groups
                continue
            
            # Check for the group at the end with various delimiters (case insensitive)
            delimiters = ['.', '-', '_', ' ', '[', '(', '{']
            for delimiter in delimiters:
                # Pattern for group at the end with delimiter before it
                # Ensure it's a complete word by checking for word boundaries
                pattern = re.compile(re.escape(delimiter) + r'\b' + re.escape(group) + r'\b' + r'$', re.IGNORECASE)
                if pattern.search(result):
                    # Replace only the group, keeping the delimiter
                    result = pattern.sub('', result)

                    # Exit both loops after first match
                    break
            
            # If we found a match in the inner loop, break the outer loop too
            if original != result:
                break
        
        # If no match found with delimiters, check for exact match at the end
        if original == result:
            for group in sorted_groups:
                if not group or len(group) <= 2:  # Skip very short groups
                    continue
                
                # Check if the string ends with the group (case insensitive)
                # Ensure it's a complete word by checking for word boundaries
                pattern = re.compile(r'\b' + re.escape(group) + r'\b' + r'$', re.IGNORECASE)
                if pattern.search(result):
                    # Remove only the group at the end
                    result = re.sub(pattern, '', result)

                    # Exit the loop after first match
                    break
        
        # Clean up any trailing delimiters
        result = result.rstrip('.-_[] ')
        
        return result
    
    def cull_version_tags(self, name: str) -> str:
        """
        Cull version/build/release tags from a name with original delimiters intact.
        
        Args:
            name: The name to process
            
        Returns:
            Name with version tags culled
        """
        if not name:
            return name
        
        result = name
        original = name
        
        # First pass: Check for build/version keywords followed by a number
        # Only match version identifiers that are followed by a number
        version_identifiers = [
            "build", "bulid", "bld", "version", "ver", "v", 
            "alpha", "beta", "release"
        ]
        
        for identifier in version_identifiers:
            # Pattern to match identifier with delimiter before it AND a number after it
            # The number must follow either immediately or after a delimiter
            pattern = re.compile(
                r'([\s._\-])' + re.escape(identifier) + 
                r'(?:[\s._\-]+[0-9]|[0-9])', 
                re.IGNORECASE
            )
            match = pattern.search(result)
            if match:
                # Find where the version identifier starts
                start_pos = match.start()
                # Remove the version identifier and everything after it
                result = result[:start_pos]

                break
        
        # Second pass: Check for specific complete phrases at the end
        if original == result:
            # Define specific complete phrases to remove
            specific_phrases = [
                "early access", "demo", "trial", "playtest", "preview",
                "remaster", "hd", "developer", "dev", "prerelease"
            ]
            
            # Check for specific phrases at the end with delimiters
            for phrase in specific_phrases:
                # Create patterns that match the phrase with delimiters
                delimiters = ['.', '-', '_', ' ']
                for delimiter in delimiters:
                    pattern = re.compile(re.escape(delimiter) + re.escape(phrase) + r'$', re.IGNORECASE)
                    if pattern.search(result):
                        result = pattern.sub('', result)

                        # Exit both loops after first match
                        break
                
                # If we found a match in the inner loop, break the outer loop too
                if original != result:
                    break
        
        # Clean up any trailing delimiters
        result = result.rstrip('.-_[] ')
        
        return result
    
    def convert_from_camel_case(self, name: str) -> str:
        """
        Convert camel case to space-separated words.
        
        Args:
            name: The name to process
            
        Returns:
            Name with camel case converted to spaces
        """
        if not name:
            return ""
        
        # Convert camel case to space-separated
        result = self.camel_case_pattern.sub(r'\1 \2', name)
        
        return result
    
    def clean_whitespace(self, name: str) -> str:
        """
        Clean up whitespace in a name.
        
        Args:
            name: The name to process
            
        Returns:
            Name with clean whitespace
        """
        if not name:
            return ""
        
        # Replace multiple spaces with a single space
        result = self.whitespace_pattern.sub(' ', name)
        
        # Trim leading and trailing whitespace
        result = result.strip()
        
        return result
    
    def title_case(self, name: str) -> str:
        """
        Apply title case to a name.
        
        Args:
            name: The name to process
            
        Returns:
            Name in title case
        """
        if not name:
            return ""
        
        # Split into words
        words = name.split()
        
        # Define words that should not be capitalized
        non_cap_words = {'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'on', 'at', 
                         'to', 'from', 'by', 'of', 'in', 'with', 'as'}
        
        # Apply title case
        result_words = []
        for i, word in enumerate(words):
            if i == 0 or i == len(words) - 1 or word.lower() not in non_cap_words:
                result_words.append(word.capitalize())
            else:
                result_words.append(word.lower())
        
        # Join words back together
        result = ' '.join(result_words)
        
        return result
    
    def final_cleanup(self, name: str) -> str:
        """
        Perform final cleanup on a name.
        
        Args:
            name: The name to process
            
        Returns:
            Clean name
        """
        if not name:
            return ""
        
        result = name
        original = name
        
        # Final check for any remaining release groups - ONLY AT THE END
        for group in sorted(self.release_groups_set, key=len, reverse=True):
            if not group or len(group) <= 2:  # Skip very short groups
                continue
            
            # Only check for the group at the end of words
            # Ensure it's a complete word by checking for word boundaries
            pattern = re.compile(r'\b(' + re.escape(group) + r')\b$', re.IGNORECASE)
            if pattern.search(result):
                result = pattern.sub('', result)

                # Clean up whitespace again
                result = self.clean_whitespace(result)
        
        # Final check for version tags and specific phrases - ONLY AT THE END
        specific_phrases = [
            "early access", "beta", "alpha", "demo", "trial", "playtest", "preview",
            "remastered edition", "remaster", "hd", "developer", "dev", "prerelease"
        ]
        
        for phrase in specific_phrases:
            pattern = re.compile(r'\b(' + re.escape(phrase) + r')\b$', re.IGNORECASE)
            if pattern.search(result):
                result = pattern.sub('', result)

                # Clean up whitespace again
                result = self.clean_whitespace(result)
        
        # Check for any remaining version patterns - ONLY SPECIFIC PATTERNS
        version_patterns = [
            r'v[0-9]+(?:\.[0-9]+)*$',  # v1, v1.0, etc.
            r'build[0-9]+$', r'bld[0-9]+$',  # build123, bld123
            r'\[[^\]]*\]$', r'\([^\)]*\)$'  # [EN], (Demo), etc.
        ]
        
        for pattern in version_patterns:
            match = re.search(pattern, result, re.IGNORECASE)
            if match:
                result = result[:match.start()] + result[match.end():]

                # Clean up whitespace again
                result = self.clean_whitespace(result)
        
        # Clean up any trailing delimiters or punctuation
        result = result.rstrip('.-_[](){} ')
        
        # Clean up any leading delimiters or punctuation
        result = result.lstrip('.-_[](){} ')
        
        # Final whitespace cleanup
        result = self.clean_whitespace(result)
        
        return result
    
    def get_match_name(self, name: str) -> str:
        """
        Process a name to get a normalized form for matching with Steam titles.
        Follows the exact rules specified.
        
        Args:
            name: The name to process
            
        Returns:
            Normalized name for matching
        """
        if not name:
            return ""
        
        # Step 1: Remove non-alphanumeric characters except commas and spaces
        result = self.non_alphanum_except_spaces_commas.sub('', name)
        
        # Step 2: Remove prefixes (suffixes are not removed to prevent improper culling)
        result = self.prefix_pattern.sub('', result)
        
        # Step 3: Remove all remaining spaces (commas already removed by regex)
        result = result.replace(' ', '')
        
        # Step 4: Convert to lowercase
        result = result.lower()
        
        return result
    
    def get_match_name_with_stemmer(self, name: str, stemmer=None) -> str:
        """
        Process a name to get a normalized form for matching with Steam titles.
        Includes optional stemming support.
        
        Args:
            name: The name to process
            stemmer: Optional stemmer to use
        
        Returns:
            Normalized name for matching
        """
        if not name:
            return ""
        
        # Step 1: Remove non-alphanumeric characters except commas and spaces
        result = self.non_alphanum_except_spaces_commas.sub('', name)
        
        # Step 2: Remove prefixes (suffixes are not removed to prevent improper culling)
        result = self.prefix_pattern.sub('', result)
        
        # Step 3: Apply stemming if available
        if stemmer:
            try:
                words = result.split()
                if words:  # Only try to stem if we have words
                    stemmed_words = [stemmer.stem(word) for word in words]
                    result = ' '.join(stemmed_words)
            except Exception:
                pass
        
        # Step 4: Remove all remaining spaces (commas already removed by regex)
        result = result.replace(' ', '')
        
        # Step 5: Convert to lowercase
        result = result.lower()
        
        return result
    
    def normalize_steam_name(self, name: str) -> str:
        """
        Normalize a Steam name for matching according to the specified rules.
        
        Args:
            name: The Steam name to normalize
            
        Returns:
            Normalized Steam name for matching
        """
        if not name:
            return ""
        
        # Step 1: Remove all non-alphanumeric characters except spaces
        result = re.sub(r'[^a-zA-Z0-9 ]', '', name)
        
        # Step 2: Remove prefixes
        result = self.prefix_pattern.sub('', result)
        
        # Step 3: Remove all spaces
        result = result.replace(' ', '')
        
        # Step 4: Convert to lowercase
        result = result.lower()
        
        return result
    
    def process_executable(self, exec_path: str) -> Dict[str, Any]:
        """
        Process an executable path to extract all relevant name information.
        
        Args:
            exec_path: Path to the executable
            
        Returns:
            Dictionary with processed name information
        """
        # Get executable name and directory
        exec_name = os.path.basename(exec_path)
        directory = os.path.dirname(exec_path)
        
        # Check if executable should be excluded
        if self.should_exclude_executable(exec_name):
            return {
                'exec_name': exec_name,
                'directory': directory,
                'candidate_dir': '',
                'is_fallback': True,
                'display_name': '',
                'match_name': '',
                'excluded': True
            }
        
        # Find candidate directory
        candidate_dir, is_fallback = self.find_candidate_directory(exec_path)
        
        # Process candidate directory name
        display_name = self.get_display_name(candidate_dir)
        match_name = self.get_match_name(candidate_dir)
        
        return {
            'exec_name': exec_name,
            'directory': directory,
            'candidate_dir': candidate_dir,
            'is_fallback': is_fallback,
            'display_name': display_name,
            'match_name': match_name,
            'excluded': False
        }
    
    def find_steam_match(self, match_name: str, steam_index: Dict[str, Dict[str, str]]) -> tuple[str, str]:
        """
        Find a matching Steam title for a normalized match name.
        
        Args:
            match_name: Normalized name to match
            steam_index: Dictionary mapping normalized Steam names to original names and IDs
            
        Returns:
            Tuple of (steam_name, steam_id) if a match is found, or ("", "") if no match
        """
        if not match_name or not steam_index:
            return "", ""
        
        # Try exact match first
        if match_name in steam_index:
            steam_data = steam_index[match_name]
            return steam_data["name"], steam_data["id"]
        
        # No match found
        return "", ""

    def find_candidate_directory(self, exec_path: str) -> Tuple[str, bool]:
        """
        Finds the most suitable candidate directory name for a given executable path.
        Walks up the directory tree, considering source directories.
        
        Args:
            exec_path: The full path to the executable.
            
        Returns:
            A tuple containing:
            - The candidate directory name (str)
            - A boolean indicating if it's a fallback name (True if fallback, False otherwise)
        """
        directory = os.path.dirname(exec_path)
        original_directory = directory
        
        # Iterate upwards from the executable's directory
        while True:
            base_name = os.path.basename(directory)
            
            # If we hit a source directory, the current directory is the candidate
            if directory in self.source_dirs:
                return base_name, False
            
            # If the parent is a source directory, then the current directory is the candidate
            parent_dir = os.path.dirname(directory)
            if parent_dir in self.source_dirs:
                return base_name, False
            
            # If we've gone up to the root or the directory hasn't changed, break
            if directory == parent_dir:
                break
            
            directory = parent_dir
            
        # Fallback: If no suitable candidate found, use the immediate parent of the executable
        # This is the directory where the executable itself resides
        fallback_name = os.path.basename(original_directory)
        return fallback_name, True
