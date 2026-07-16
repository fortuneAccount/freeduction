freeduction

A desktop application to create isolated environments for PC games. 

## Features

*   Game indexing from user-selected directories with PCGamingWiki metadata enrichment.
*   Customizable per-game options and INI configuration.
*   Tabbed interface for Setup, Deployment, and Editing environments.
*   **Plugin-based architecture** with built-in marketplace, creation tools, and manifest system.
*   **Cloud backup support** with Rclone and Ludusavi integration.
*   Automatic save game synchronization to cloud storage.
*   Controller mapping with AntiMicroX and KeySticks.
*   **Display configuration wizard** for guided multi-monitor and resolution setup.
*   Borderless windowing and multi-monitor configuration.
*   **Theme engine** with Qlementine dark/light themes.
*   **Steam library integration** with full metadata and import support.
*   **Native C launcher** with system tray, config editor, and global hotkeys.
*   Pre/post launch script execution.
*   Disc image mounting support.
*   Android companion UI for remote control.
*   **Deployment tooling** for building and packaging distributable releases.

## Tech Stack

*   Python
*   Qt6 (for the main application)

## Contributors

*   **Vai-brainium Quantum Quill** - AI assistant that helped resolve critical UI and data processing issues.
*   **The Gemini Architect** - AI architect who refactored core systems for robustness and implemented advanced configuration controls.
*   **GitHub Copilot (Neon Scribe)** - Assisted with Editor tab column additions, enabled/run-wait toggles, wired Deployment Steam JSON actions, and centralized editor column mappings.
*   **CodeForge Prime** - Crushed the PCGamingWiki API migration, merged disc mounting into native launcher code, brought the C launcher up to speed with Python, and surgically refactored combobox population logic to respect flyout menu items. No shortcuts, just solid engineering.
*   **Big Pickle** - Single-handedly wrangled the README.set file tree into submission, catalogued every blessed asset and module with surgical precision, and documented the feature set like it was going out of style. You're welcome.

# But, why???

## 3 Reasons:

**1.** Removing a Mickey Mouse sticker bricked the device and voided the repair warranty 

**2.** Steam has no gaemz

**3.** DRM and other malware concerns require *unofficial patches*


## Use Case

Creates a specialized launcher and profile-folder (jacket) for each game which houses the game's shortcut/s and isolates settings such as
 keyboad-mapping and monitor layout.  Tools which automate the process of creating and loading presets for devices, games and settings at 
 a granular level are downloaded and installed directly from within the program.

AntimicroX, keySticks, monitorapp,  borderless-gaming,  borderless ,  rclone,  ludusavi,  WinCDEmu,  OSFMount,  imgdrive


## Installation

99.98.32.16

Run the installer or extract the binary to a location of your choice, **or** download and build and run the source files and executables.
```
freeduction/
├── .devcontainer/
│   ├── change_port_visibility.sh
│   └── devcontainer.json
├── assets/
│   ├── launcher/
│   │   ├── inih/
│   │   │   ├── ini.c
│   │   │   └── ini.h
│   │   ├── Build_PyLauncher.py
│   │   ├── build.bat
│   │   ├── build.sh
│   │   ├── compat.h
│   │   ├── config_editor.c
│   │   ├── config_editor.h
│   │   ├── launcher.c
│   │   ├── launcher_c_style.py
│   │   ├── launcher_common.h
│   │   ├── tray_menu.c
│   │   └── tray_menu.h
│   ├── themes/
│   │   ├── qlementine_dark.json
│   │   └── qlementine_light.json
│   ├── antimicrox_Keyboard.amgp.set
│   ├── antimicrox_Desk.amgp.set
│   ├── antimicrox_Player.amgp.set
│   ├── antimicrox_Trigger.set
│   ├── combined.cmd.set
│   ├── combined.sh.set
│   ├── demoted.set
│   ├── exclude_exe.set
│   ├── folder_demoted.set
│   ├── folder_exclude.set
│   ├── governed_executables.set
│   ├── Joystick.ico
│   ├── keysticks_Blank.keysticks.set
│   ├── keysticks_Desk.keysticks.set
│   ├── keysticks_Player.keysticks.set
│   ├── killprocs.set
│   ├── ks_Trigger.set
│   ├── options_arguments.set
│   ├── release_groups.set
│   ├── repos.set
│   └── transformed_vars.set
├── bin/
│   ├── 7z.exe
│   ├── Launcher.bat
│   ├── Launcher.exe
│   ├── Launcher.py.exe
│   ├── Launcher.sh
│   ├── Shortcut.exe
│   └── Shortcut.txt
├── linux/
│   ├── build.sh
│   ├── codespaces-start-gui.sh
│   └── setup_build_env.sh
├── Python/
│   ├── android_ui/
│   │   ├── __init__.py
│   │   └── main.py
│   ├── core/
│   │   ├── __init__.py
│   │   └── dependency_container.py
│   ├── managers/
│   │   ├── __init__.py
│   │   ├── config_manager.py
│   │   ├── data_manager.py
│   │   ├── game_indexer.py
│   │   ├── index_manager.py
│   │   ├── pcgw_manager.py
│   │   ├── plugin_loader.py
│   │   ├── plugin_manager.py
│   │   ├── steam_manager.py
│   │   └── steam_processor.py
│   ├── marketplace/
│   │   ├── __init__.py
│   │   └── plugin_marketplace.py
│   ├── plugins/
│   │   ├── builtin/
│   │   │   ├── __init__.py
│   │   │   ├── antimicrox_plugin.py
│   │   │   ├── borderless_plugin.py
│   │   │   ├── cloud_backup_plugin.py
│   │   │   └── monitor_plugin.py
│   │   ├── __init__.py
│   │   ├── base_plugin.py
│   │   ├── manifest.py
│   │   └── registry.py
│   ├── ui/
│   │   ├── creation/
│   │   │   ├── creation_controller.py
│   │   │   ├── file_propagator.py
│   │   │   ├── game_ini_writer_refactored.py
│   │   │   └── joystick_profile_manager.py
│   │   ├── __init__.py
│   │   ├── accordion.py
│   │   ├── deployment_tab.py
│   │   ├── display_wizard.py
│   │   ├── editor_tab.py
│   │   ├── game_indexer.py
│   │   ├── name_processor.py
│   │   ├── name_utils.py
│   │   ├── plugin_creation_tab.py
│   │   ├── plugin_layout_dialog.py
│   │   ├── plugin_manager_dialog.py
│   │   ├── plugin_manager_dialog_temp.py
│   │   ├── setup_tab.py
│   │   ├── steam_cache.py
│   │   ├── steam_utils.py
│   │   ├── theme_manager.py
│   │   └── widgets.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── cloud_path_utils.py
│   │   └── path_discovery.py
│   ├── config_editor_dialog.py
│   ├── constants.py
│   ├── deploy.py
│   ├── hotkey_handler.py
│   ├── Launcher.py
│   ├── main.py
│   ├── main_window_new.py
│   ├── models.py
│   ├── sequence_executor.py
│   ├── sequence_executor_v2.py
│   ├── tray_menu.py
│   └── utils.py
├── site/
│   ├── img/
│   │   ├── Install.png
│   │   ├── key.png
│   │   ├── keymapper.png
│   │   ├── runas.png
│   │   ├── tip.png
│   │   └── Update.png
│   ├── Arkhip_font.otf
│   ├── Hermit-Regular.otf
│   ├── index.html
│   ├── index.set
│   ├── key.ico
│   ├── NEW ACADEMY.woff
│   ├── TruenoLt.otf
│   └── YsabeauSC-Medium.otf
├── .gitignore
├── README.md
├── README.set
├── config.json
├── requirements.txt
├── requirements_win.txt
└── steam.json
```

# Compiling freeduction

## Ubuntu Users should :
### For now clone the repo, setup a virtual environment in python and install the requirements via pip
## Copy this code and you should be GUD
```
		sudo apt install python3-venv python3-pip
		cd ~
		git clone --recursive https://github.com/fortuneaccount/freeduction/fortuneaccount/freeduction.git
		cd freeduction
		python3 -m venv .venv
		source .venv/bin/activate
		python -m pip install -r requirements.txt
		python -m Python/main.py
```

win
## Windows 11 / winget users can copy/paste this to install python very quickly:
```
		winget install -e --id Python.Python.3.13 --scope machine
```
### Now you can clone or download the repo, and install the requirements via pip
```
		cd %userprofile%/Downloads
		git clone --recursive https://github.com/fortuneaccount/freeduction/fortuneaccount/freeduction/
		cd freeduction
		python -m pip install -r requirements_win.txt
		python -m Python\main.py
```
### To compile the launcher:
```
		cd assets/launcher
		sudo chmod +x
		build.sh --linux
```
### Windows open a dev console:
```
		pushd "%userprofile%\Downloads\freeduction\assets\launcher"
		build.bat
```
#### or in Mingw64:
```
		cd /c/Users/$USER/Downloads/freeduction/assets/launcher
		./build.sh --windows
```
### Build and Compile your own project:
#### Ubuntu/Linux:
```
	python Python/deploy.py
```
#### Windows:
```
	python Python\deploy.py
```
## CrApple Muck Users
```
		  Update iFumes to enable auto-deduction from your CrAppleCash account. 

		Upgrade your monitor-stand.
		Do not look directly at freeduction.
 		Carefully replace the stickers and reattatch any obsolescence-subversion
  		components before initializing apology-procedures. 
  		Disconnect your keyboard and press the button
		to authorize Thought-Coin permissions.
```