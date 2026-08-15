import logging
import time
import requests
try:
    import cloudscraper
except ImportError:
    cloudscraper = None
from urllib.parse import quote, unquote, urlparse
from bs4 import BeautifulSoup

class PCGWManager:
    """
    Manages interactions with the PCGamingWiki Cargo API.
    PCGamingWiki migrated from Semantic MediaWiki to Cargo for backend data.
    """
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }

        # Use requests.Session directly - cloudscraper can cause issues
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
        self.api_url = "https://www.pcgamingwiki.com/w/api.php"

    def fetch_data(self, game_name, steam_id=None):
        """
        Fetches metadata from PCGamingWiki using the Cargo API.
        
        Args:
            game_name (str): The name of the game to search for.
            steam_id (str, optional): The Steam AppID to query directly.
            
        Returns:
            dict: A dictionary containing parsed PCGW data, or None if failed.
        """
        pcgw_data = {}
        page_id = None
        page_name = None

        # 1. Try to query by Steam AppID using Cargo API
        if steam_id and str(steam_id) not in ['NOT_FOUND_IN_DATA', 'ITEM_IS_NONE', '']:
            try:
                time.sleep(0.5)  # Rate limiting
                params = {
                    'action': 'cargoquery',
                    'tables': 'Infobox_game',
                    'fields': 'Infobox_game._pageID=PageID,Infobox_game._pageName=Page,Infobox_game.Developers,Infobox_game.Publishers,Infobox_game.Engines,Infobox_game.Released,Infobox_game.Genres,Infobox_game.Modes,Infobox_game.Series,Infobox_game.Monetization,Infobox_game.Microtransactions',
                    'where': f'Infobox_game.Steam_AppID HOLDS "{steam_id}"',
                    'format': 'json',
                    'limit': '1'
                }
                
                logging.debug(f"Querying PCGW by Steam AppID: {steam_id}")
                response = self.session.get(self.api_url, params=params, timeout=10)
                logging.debug(f"Response status: {response.status_code}")
                
                if response.status_code == 200:
                    data = response.json()
                    logging.debug(f"Response keys: {list(data.keys())}")
                    
                    if 'cargoquery' in data and len(data['cargoquery']) > 0:
                        result = data['cargoquery'][0]['title']
                        page_id = result.get('PageID')
                        page_name = result.get('Page')
                        pcgw_data['Developers'] = result.get('Developers', '')
                        pcgw_data['Publishers'] = result.get('Publishers', '')
                        pcgw_data['Engines'] = result.get('Engines', '')
                        pcgw_data['Released'] = result.get('Released', '')
                        pcgw_data['Genres'] = result.get('Genres', '')
                        pcgw_data['Modes'] = result.get('Modes', '')
                        pcgw_data['Series'] = result.get('Series', '')
                        pcgw_data['Monetization'] = result.get('Monetization', '')
                        pcgw_data['Microtransactions'] = result.get('Microtransactions', '')
                        logging.info(f"Found PCGW data via Steam AppID {steam_id}: {page_name}")
                    else:
                        logging.warning(f"No PCGW data found for Steam AppID {steam_id}")
                        if 'error' in data:
                            logging.error(f"API Error: {data['error']}")
                else:
                    logging.warning(f"PCGW Cargo API returned status {response.status_code}")
            except Exception as e:
                logging.error(f"PCGW Cargo query by AppID failed: {e}", exc_info=True)

        # 2. If no data found by AppID, try searching by game name
        if not page_name and game_name:
            try:
                time.sleep(0.5)
                params = {
                    'action': 'cargoquery',
                    'tables': 'Infobox_game',
                    'fields': 'Infobox_game._pageID=PageID,Infobox_game._pageName=Page,Infobox_game.Developers,Infobox_game.Publishers,Infobox_game.Engines,Infobox_game.Released,Infobox_game.Genres,Infobox_game.Modes,Infobox_game.Series,Infobox_game.Monetization,Infobox_game.Microtransactions',
                    'where': f'Infobox_game._pageName="{game_name}"',
                    'format': 'json',
                    'limit': '1'
                }
                
                response = self.session.get(self.api_url, params=params, timeout=10)
                
                if response.status_code == 200:
                    data = response.json()
                    if 'cargoquery' in data and len(data['cargoquery']) > 0:
                        result = data['cargoquery'][0]['title']
                        page_id = result.get('PageID')
                        page_name = result.get('Page')
                        pcgw_data['Developers'] = result.get('Developers', '')
                        pcgw_data['Publishers'] = result.get('Publishers', '')
                        pcgw_data['Engines'] = result.get('Engines', '')
                        pcgw_data['Released'] = result.get('Released', '')
                        pcgw_data['Genres'] = result.get('Genres', '')
                        pcgw_data['Modes'] = result.get('Modes', '')
                        pcgw_data['Series'] = result.get('Series', '')
                        pcgw_data['Monetization'] = result.get('Monetization', '')
                        pcgw_data['Microtransactions'] = result.get('Microtransactions', '')
                        logging.info(f"Found PCGW data by name: {page_name}")
            except Exception as e:
                logging.error(f"PCGW Cargo query by name failed: {e}")

        # 3. Get save/config locations by parsing page HTML
        if page_name:
            self._fetch_save_config_from_html(page_name, pcgw_data)
            self._fetch_video_settings(page_name, pcgw_data)
            self._fetch_input_settings(page_name, pcgw_data)

        return pcgw_data if pcgw_data else None

    def _fetch_save_config_from_html(self, page_name, pcgw_data):
        """Fetch save and config locations by parsing the page HTML."""
        try:
            time.sleep(0.5)
            params = {
                'action': 'parse',
                'page': page_name,
                'prop': 'text',
                'format': 'json'
            }
            
            response = self.session.get(self.api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if 'parse' in data and 'text' in data['parse']:
                    html_content = data['parse']['text']['*']
                    soup = BeautifulSoup(html_content, 'html.parser')
                    
                    save_locations = {}
                    config_locations = {}
                    
                    # Find all h3 headers
                    headers = soup.find_all('h3')
                    
                    for header in headers:
                        header_text = header.get_text(strip=True).lower()
                        
                        # Determine section type
                        section_type = None
                        if 'save game data location' in header_text:
                            section_type = 'save'
                        elif 'configuration file' in header_text:
                            section_type = 'config'
                        else:
                            continue
                        
                        # Find the next table after this header (not just siblings)
                        table = header.find_next('table')
                        
                        # Make sure we don't go past the next section header
                        if table:
                            next_header = header.find_next(['h2', 'h3'])
                            if next_header:
                                # Check if table comes before next header by comparing positions
                                header_pos = str(soup).find(str(next_header))
                                table_pos = str(soup).find(str(table))
                                if table_pos > header_pos:
                                    table = None
                        
                        if not table:
                            continue
                        
                        # Parse the table
                        rows = table.find_all('tr')
                        
                        for row in rows:
                            # Skip header row - data rows have 1 th (system) and 1 td (location)
                            th_cells = row.find_all('th')
                            td_cells = row.find_all('td')
                            
                            if len(th_cells) == 1 and len(td_cells) == 1:
                                system = th_cells[0].get_text(strip=True)
                                location_text = td_cells[0].get_text(separator='\n', strip=True)
                                
                                if system and location_text:
                                    # Remove footnote markers first
                                    import re
                                    raw_text = re.sub(r'\[Note \d+\]', '', location_text)
                                    
                                    # Split by newlines and reconstruct paths
                                    lines = [l.strip() for l in raw_text.split('\n') if l.strip()]
                                    
                                    paths = []
                                    current_path = ""
                                    
                                    for line in lines:
                                        if line.startswith('It\'s unknown'):
                                            continue
                                        
                                        # Check if this line starts a new path
                                        # Paths start with: <, %, /, ~, or drive letter (C:)
                                        is_new_path = (
                                            line.startswith(('<', '%', '/', '~')) or 
                                            (len(line) > 1 and line[1] == ':')
                                        )
                                        
                                        # Also check if current line is a placeholder that should continue previous path
                                        # Placeholders like <user-id> should NOT start a new path if we're mid-path
                                        if is_new_path and current_path:
                                            # If current path ends with a path separator, this might be a continuation
                                            if current_path.endswith(('\\', '/')):
                                                current_path += line
                                                continue
                                            else:
                                                # Save previous path and start new one
                                                paths.append(current_path)
                                                current_path = line
                                        elif is_new_path:
                                            # Start new path
                                            current_path = line
                                        else:
                                            # Continue building current path
                                            current_path += line
                                    
                                    # Don't forget the last path
                                    if current_path:
                                        paths.append(current_path)
                                    
                                    if paths:
                                        target_dict = save_locations if section_type == 'save' else config_locations
                                        
                                        if system not in target_dict:
                                            target_dict[system] = []
                                        
                                        for path in paths:
                                            target_dict[system].append({'path': path})
                    
                    pcgw_data['save_locations'] = save_locations
                    pcgw_data['config_locations'] = config_locations
                    
                    if save_locations:
                        total_saves = sum(len(v) for v in save_locations.values())
                        logging.info(f"Found {total_saves} save locations for {page_name} across {len(save_locations)} systems")
                    if config_locations:
                        total_configs = sum(len(v) for v in config_locations.values())
                        logging.info(f"Found {total_configs} config locations for {page_name} across {len(config_locations)} systems")
                else:
                    pcgw_data['save_locations'] = {}
                    pcgw_data['config_locations'] = {}
            else:
                logging.warning(f"PCGW page parse returned status {response.status_code}")
                pcgw_data['save_locations'] = {}
                pcgw_data['config_locations'] = {}
                
        except Exception as e:
            logging.error(f"Failed to fetch save/config locations from HTML: {e}", exc_info=True)
            pcgw_data['save_locations'] = {}
            pcgw_data['config_locations'] = {}

    def _fetch_video_settings(self, page_name, pcgw_data):
        """Fetch video settings from Cargo API."""
        try:
            time.sleep(0.5)
            params = {
                'action': 'cargoquery',
                'tables': 'Video',
                'fields': 'Video.Widescreen_resolution,Video.Multimonitor,Video.Ultra_widescreen,Video.4K_ultra_HD,Video.Field_of_view,Video.Windowed,Video.Borderless_fullscreen_windowed,Video.Anisotropic_filtering,Video.Anti_aliasing,Video.Vertical_sync,Video.FPS_limit',
                'where': f'Video._pageName="{page_name}"',
                'format': 'json',
                'limit': '1'
            }
            
            response = self.session.get(self.api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'cargoquery' in data and len(data['cargoquery']) > 0:
                    result = data['cargoquery'][0]['title']
                    video_settings = {}
                    
                    for key, value in result.items():
                        if value:
                            # Clean up key names
                            clean_key = key.replace('Video.', '').replace('_', ' ')
                            video_settings[clean_key] = value
                    
                    if video_settings:
                        pcgw_data['video_settings'] = video_settings
                        logging.info(f"Found video settings for {page_name}")
                
        except Exception as e:
            logging.error(f"Failed to fetch video settings: {e}")

    def _fetch_input_settings(self, page_name, pcgw_data):
        """Fetch input settings from Cargo API."""
        try:
            time.sleep(0.5)
            params = {
                'action': 'cargoquery',
                'tables': 'Input',
                'fields': 'Input.Remapping,Input.Mouse_acceleration,Input.Controller_support,Input.Full_controller_support,Input.Controller_remapping,Input.Tracked_controllers_support,Input.VR_motion_controllers_support',
                'where': f'Input._pageName="{page_name}"',
                'format': 'json',
                'limit': '1'
            }
            
            response = self.session.get(self.api_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'cargoquery' in data and len(data['cargoquery']) > 0:
                    result = data['cargoquery'][0]['title']
                    input_settings = {}
                    
                    for key, value in result.items():
                        if value:
                            # Clean up key names
                            clean_key = key.replace('Input.', '').replace('_', ' ')
                            input_settings[clean_key] = value
                    
                    if input_settings:
                        pcgw_data['input_settings'] = input_settings
                        logging.info(f"Found input settings for {page_name}")
                
        except Exception as e:
            logging.error(f"Failed to fetch input settings: {e}")
