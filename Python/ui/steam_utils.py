import os

def locate_and_exclude_manager_config(main_window):
    """Locate and exclude games from other managers' configurations"""
    if hasattr(main_window, 'setup_tab') and hasattr(main_window.setup_tab, 'other_managers_combo'):
        selected_manager = main_window.setup_tab.other_managers_combo.currentText()
    elif hasattr(main_window, 'other_managers_combo'):
        selected_manager = main_window.other_managers_combo.currentText()
    else:
        return
        
    main_window.statusBar().showMessage(f"Looking for {selected_manager} configuration...", 5000)
    
    # TODO: This method would need to be expanded based on what game managers
    # are being supported. For now, this is a placeholder that could be
    # customized for specific managers.

    if selected_manager == "Steam":
        # Example for Steam: Use Steam library folders containing appmanifest_*.acf
        steam_paths = []
        # Add code to detect Steam installation folders
        # ...
        
        for path in steam_paths:
            if os.path.exists(path):
                # Process Steam library folder
                # ...
                pass
                
    elif selected_manager == "Epic Games":
        # Epic Games specific implementation
        # ...
        pass
        
    elif selected_manager == "GOG Galaxy":
        # GOG Galaxy specific implementation  
        # ...
        pass
        
    else:
        main_window.statusBar().showMessage(f"No implementation for {selected_manager} yet", 5000)
        
    main_window.statusBar().showMessage(f"Processed {selected_manager} configuration", 5000)

def debug_steam_cache(main_window):
    """Debug function to print information about the Steam cache"""
    print("\n=== Steam Cache Debug Information ===")
    
    # Check if the cache exists
    if not hasattr(main_window, 'steam_title_cache') or not main_window.steam_title_cache:
        print("No Steam title cache available")
        return

    # Check a few sample entries
    sample_count = min(5, len(main_window.steam_title_cache))

    for _ in list(main_window.steam_title_cache.items())[:sample_count]:
        # Add a pass statement for empty loops
        pass

    # Check the normalized index
    if not hasattr(main_window, 'normalized_steam_match_index') or not main_window.normalized_steam_match_index:
        print("No normalized Steam match index available")
        return

    # Check a few sample entries
    sample_count = min(5, len(main_window.normalized_steam_match_index))

    for _ in list(main_window.normalized_steam_match_index.items())[:sample_count]:
        # Add a pass statement for empty loops
        pass
    # Check for "game on" specifically
    if hasattr(main_window, 'normalized_steam_match_index'):
        for _, data in main_window.normalized_steam_match_index.items():
            if data['name'].lower() == "game on":
                pass # This line was likely a print statement that was removed
            
    print("=== End DEBUG ===\n")

def debug_steam_cache_loading(main_window):
    """Debug function to help diagnose steam_filtered.txt loading issues"""
    print("\n--- STEAM CACHE LOADING DEBUG ---")
    
    # Check if the attribute exists
    if not hasattr(main_window, 'filtered_steam_cache_file_path'):
        print("filtered_steam_cache_file_path attribute does not exist on main_window")
    else:

        
        # Check if the file exists
        if main_window.filtered_steam_cache_file_path:
            file_exists = os.path.exists(main_window.filtered_steam_cache_file_path)

            
            if file_exists:
                # Check file size
                file_size = os.path.getsize(main_window.filtered_steam_cache_file_path)

                
                # Check if file is readable
                try:
                    with open(main_window.filtered_steam_cache_file_path, 'r', encoding='utf-8') as f:
                        first_lines = [next(f) for _ in range(3)]

                        for _ in first_lines:
                            pass # This line was likely a print statement that was removed
                except Exception as e:
                    pass
    
    # Check steam_title_cache
    if not hasattr(main_window, 'steam_title_cache'):
        print("steam_title_cache attribute does not exist on main_window")
    else:

        
        # Show a few sample entries if any exist
        if main_window.steam_title_cache:
            print("Sample entries:")
            for _ in list(main_window.steam_title_cache.items())[:3]:
                pass # This line was likely a print statement that was removed
    # Try to find the file in common locations
    print("\nSearching for steam_filtered.txt in common locations:")
    possible_locations = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "steam_filtered.txt"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "steam_filtered.txt"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "steam_filtered.txt"),
        os.path.join(os.getcwd(), "steam_filtered.txt"),
        os.path.join(os.path.expanduser("~"), "Documents", "steam_filtered.txt"),
        os.path.join(os.path.expanduser("~"), "steam_filtered.txt")
    ]
    
    for location in possible_locations:
        exists = os.path.exists(location)

        if exists:
            file_size = os.path.getsize(location)

    
    print("--- END DEBUG ---\n")
