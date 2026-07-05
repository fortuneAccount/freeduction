#!/usr/bin/env python3
"""
Build_PyLauncher.py - Flexible Build System for Launcher.exe

Supports multiple build presets with different feature sets and sizes.
Usage: python Build_PyLauncher.py [preset] [modifiers...]

Available presets:
  - minimal   : Minimal build with hotkeys only (10-15 MB)
  - standard  : Standard build without heavy GUI (20-25 MB)


Examples:
  python Build_PyLauncher.py minimal
  python Build_PyLauncher.py standard
"""

import sys
import os
import argparse
import shutil
from pathlib import Path
import configparser

# Add parent directory to path to import PyInstaller
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import PyInstaller.__main__
except ImportError:
    print("ERROR: PyInstaller not found. Install it with: pip install pyinstaller")
    sys.exit(1)


# ============================================================================
# CONFIGURATION
# ============================================================================

def get_project_root():
    """Get the project root directory.
    
    Returns the project root whether script is run from:
    - Project root: python assets/launcher/Build_PyLauncher.py
    - assets/launcher directory: cd assets/launcher && python Build_PyLauncher.py
    """
    script_path = Path(__file__).resolve()
    
    # If script is in assets/launcher directory, go up 2 levels
    if script_path.parent.name == 'launcher' and script_path.parent.parent.name == 'assets':
        return script_path.parent.parent.parent
    else:
        # Try to find project root by looking for common project markers
        current = script_path.parent
        while current != current.parent:  # Stop at root
            # Check for project markers
            if (current / 'Python').exists() and (current / 'assets').exists():
                return current
            current = current.parent
        
        # Fallback: assume script is in assets/launcher
        return script_path.parent.parent.parent

project_root = get_project_root()
config_path = project_root / 'deploy_ui.ini'

# Default paths
workpath = str(project_root / 'build')

if config_path.exists():
    cfg = configparser.ConfigParser()
    cfg.read(config_path)
    if 'build' in cfg:
        workpath = cfg['build'].get('workpath', workpath)

# Define a dedicated output path for the python launcher inside the main build folder
# This prevents it from being included in the main application's dist folder and final archive.
py_launcher_dist_path = Path(workpath) / 'py_launcher_dist'
dest_dir_str = str(py_launcher_dist_path)

# ============================================================================
# BUILD PRESETS
# ============================================================================

PRESETS = {
   'standard': {
        'name': 'Launcher_standard',
        'description': 'Standard build with tray menu and process management',
        'console': False,
        'env_vars': {},
        'excluded_modules': [
            'pygame', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
            'matplotlib', 'numpy', 'pandas', 'scipy', 'tensorflow', 'torch',
            'test', 'unittest', 'pydoc', 'email', 'http', 'xml', 'distutils',
        ],
        'extra_args': [
            f'--distpath={dest_dir_str}', f'--workpath={workpath}'
        ],
        'expected_size': '20-25 MB',
    },
    
    'minimal': {
        'name': 'Launcher_minimal',
        'description': 'Minimal build with tray menu',
        'console': False,
        'env_vars': {'LAUNCHER_MINIMAL': '1'},
        'excluded_modules': [
            'pygame', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
            'psutil', 'matplotlib', 'numpy', 'pandas', 'Python.hotkey_handler',
            'Python.managers.plugin_manager',
            'Python.plugins', 'Python.marketplace',
            'test', 'unittest', 'pydoc', 'email', 'http', 'xml', 'distutils',
        ],
        'extra_args': [
            f'--distpath={dest_dir_str}', f'--workpath={workpath}'
        ],
        'expected_size': '10-15 MB',
    },
}


# ============================================================================
# BUILD FUNCTIONS
# ============================================================================

def build_launcher(preset_name='stadard'):
    """Build the launcher with the specified preset and optional modifiers
    
    Args:
        preset_name: Name of the preset to use
    """
    
    if preset_name not in PRESETS:
        print(f"ERROR: Unknown preset '{preset_name}'")
        print(f"Available presets: {', '.join(PRESETS.keys())}")
        sys.exit(1)
    
    preset = PRESETS[preset_name].copy()  # Make a copy to avoid modifying original
    project_root = get_project_root()
    
    excluded_modules = list(preset['excluded_modules'])  # Copy the list
    extra_args = list(preset['extra_args'])  # Copy the list
    
    preset['excluded_modules'] = excluded_modules
    preset['extra_args'] = extra_args
    
    print("=" * 70)
    print(f"Building Launcher with preset: {preset_name}")
    print("=" * 70)
    print(f"Description: {preset['description']}")
    print(f"Output name: {preset['name']}.exe")
    print(f"Expected size: {preset['expected_size']}")
    print(f"Console mode: {'Yes' if preset['console'] else 'No'}")
    print(f"Excluded modules: {len(preset['excluded_modules'])}")
    print()
    
    # Set environment variables
    for key, value in preset['env_vars'].items():
        os.environ[key] = value
        print(f"Set {key}={value}")
    
    if preset['env_vars']:
        print()
    
    # Build base arguments
    args = [
        str(project_root / 'Python' / 'Launcher.py'),
        '--onefile',
        f"--name={preset['name']}",
        '--clean',
    ]
    
    # Add console/noconsole
    if preset['console']:
        args.append('--console')
    else:
        args.append('--noconsole')
    
    # Add excluded modules
    for module in preset['excluded_modules']:
        args.append(f'--exclude-module={module}')
    
    # Add data files
    assets_path = project_root / 'assets'
    if assets_path.exists():
        args.append(f'--add-data={assets_path}{os.pathsep}assets')
    
    # Add icon (Windows only)
    if sys.platform == 'win32':
        icon_path = assets_path / 'Joystick.ico'
        if icon_path.exists():
            args.append(f'--icon={icon_path}')
    
    # Add extra arguments from preset
    args.extend(preset['extra_args'])
    
    # Always disable UPX to prevent issues
    if '--noupx' not in args:
        args.append('--noupx')
    
    print("PyInstaller arguments:")
    for arg in args:
        print(f"  {arg}")
    print()
    
    # Run PyInstaller
    print("Running PyInstaller...")
    print("-" * 70)
    
    try:
        PyInstaller.__main__.run(args)
        print("-" * 70)
        print()
        print("=" * 70)
        print("BUILD SUCCESSFUL!")
        print("=" * 70)
        print(f"Output: dist/{preset['name']}.exe")
        print(f"Expected size: {preset['expected_size']}")
        print()
        
        # Show next steps based on preset
        if preset_name == 'minimal':
            print("Minimal build notes:")
            print("  - Hotkeys are enabled (Ctrl+Alt+F9 for help)")
            print("  - No splash screen or tray menu")
            print("  - Process management uses taskkill fallback")
            print()
        
    except Exception as e:
        print("-" * 70)
        print()
        print("=" * 70)
        print("BUILD FAILED!")
        print("=" * 70)
        print(f"Error: {e}")
        sys.exit(1)


def list_presets():
    """List all available presets"""
    print("=" * 70)
    print("Available Build Presets")
    print("=" * 70)
    print()
    
    for name, preset in PRESETS.items():
        print(f"{name:12} - {preset['description']}")
        print(f"{'':12}   Size: {preset['expected_size']}")
        print(f"{'':12}   Console: {'Yes' if preset['console'] else 'No'}")
        print(f"{'':12}   Excluded: {len(preset['excluded_modules'])} modules")
        print()
    
def clean_artifacts():
    """Remove build artifacts (dist, build, spec files)"""
    project_root = get_project_root()
    
    # Directories to clean
    dirs_to_clean = [
        project_root / 'dist',
        project_root / 'build',
        Path('dist').absolute(),
        Path('build').absolute(),
    ]
    
    # Spec files to clean
    specs_to_clean = []
    for preset in PRESETS.values():
        name = preset['name']
        specs_to_clean.append(project_root / f"{name}.spec")
        specs_to_clean.append(Path(f"{name}.spec").absolute())

    print("=" * 70)
    print("Cleaning build artifacts...")
    print("=" * 70)
    
    for d in set(dirs_to_clean):
        if d.exists():
            try:
                shutil.rmtree(d)
                print(f"Removed directory: {d}")
            except Exception as e:
                print(f"Error removing {d}: {e}")
    
    for s in set(specs_to_clean):
        if s.exists():
            try:
                os.remove(s)
                print(f"Removed file: {s}")
            except Exception as e:
                print(f"Error removing {s}: {e}")
    
    print()
    print("Clean complete.")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Build Launcher.exe with different feature presets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Build_PyLauncher.py              # Build with 'standard' preset (default)
  python Build_PyLauncher.py minimal      # Build minimal version
  python Build_PyLauncher.py --list       # List all available presets
  python Build_PyLauncher.py --clean      # Clean build artifacts
  
Presets:
  minimal   - Minimal build with hotkeys (10-15 MB)
  standard  - Standard build without GUI (20-25 MB)

        """
    )
    
    parser.add_argument(
        'preset',
        nargs='?',
        default='standard',
        choices=list(PRESETS.keys()),
        help='Build preset to use (default: standard)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available presets and exit'
    )
    
    parser.add_argument(
        '--clean',
        action='store_true',
        help='Clean build artifacts (dist, build, spec files) and exit'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_presets()
        sys.exit(0)
    
    if args.clean:
        clean_artifacts()
        sys.exit(0)
    
    build_launcher(args.preset)

if __name__ == '__main__':
    main()
