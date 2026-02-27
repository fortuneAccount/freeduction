#!/usr/bin/env python3
"""
Build_PyLauncher.py - Flexible Build System for Launcher.exe

Supports multiple build presets with different feature sets and sizes.
Usage: python Build_PyLauncher.py [preset] [modifiers...]

Available presets:
  - full      : Full-featured build with all dependencies (default)
  - minimal   : Minimal build with hotkeys only (10-15 MB)
  - standard  : Standard build without heavy GUI (20-25 MB)
  - portable  : Portable build optimized for distribution (15-20 MB)
  - debug     : Debug build with console and verbose logging

Optional modifiers:
  - nocs      : Exclude cloud sync utilities (saves ~1-2 MB)
  - nopd      : Exclude path discovery/PCGW templates (saves ~1-2 MB)
  - upx       : Enable UPX compression (reduces size by 30-40%)

Examples:
  python Build_PyLauncher.py minimal
  python Build_PyLauncher.py standard nocs nopd upx
  python Build_PyLauncher.py portable upx
"""

import sys
import os
import argparse
from pathlib import Path

# Add parent directory to path to import PyInstaller
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

try:
    import PyInstaller.__main__
except ImportError:
    print("ERROR: PyInstaller not found. Install it with: pip install pyinstaller")
    sys.exit(1)


# ============================================================================
# BUILD PRESETS
# ============================================================================

PRESETS = {
    'full': {
        'name': 'Launcher_full',
        'description': 'Full-featured build with all dependencies',
        'console': False,
        'env_vars': {},
        'excluded_modules': [
            'matplotlib', 'numpy', 'pandas', 'scipy', 'tensorflow', 'torch',
        ],
        'extra_args': [],
        'expected_size': '50+ MB',
    },
    
    'minimal': {
        'name': 'Launcher_minimal',
        'description': 'Minimal build with hotkeys only',
        'console': False,
        'env_vars': {'LAUNCHER_MINIMAL': '1'},
        'excluded_modules': [
            'pygame', 'PIL', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
            'psutil', 'win32gui', 'win32con', 'win32process', 'win32api',
            'pywintypes', 'win32com', 'matplotlib', 'numpy', 'pandas',
            'Python.managers.plugin_manager', 'Python.managers.plugin_loader',
            'Python.plugins', 'Python.marketplace', 'Python.tray_menu',
            'pystray', 'infi.systray',
        ],
        'extra_args': ['--strip'],
        'expected_size': '10-15 MB',
    },
    
    'standard': {
        'name': 'Launcher_standard',
        'description': 'Standard build without heavy GUI',
        'console': False,
        'env_vars': {},
        'excluded_modules': [
            'pygame', 'PIL', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
            'matplotlib', 'numpy', 'pandas', 'Python.tray_menu', 'pystray',
        ],
        'extra_args': [],
        'expected_size': '20-25 MB',
    },
    
    'portable': {
        'name': 'Launcher_portable',
        'description': 'Portable build optimized for distribution',
        'console': False,
        'env_vars': {},
        'excluded_modules': [
            'pygame', 'tkinter', 'PyQt5', 'PyQt6', 'PySide2', 'PySide6', 'wx',
            'matplotlib', 'numpy', 'pandas', 'Python.managers.plugin_manager',
            'Python.marketplace',
        ],
        'extra_args': ['--strip'],
        'expected_size': '15-20 MB',
    },
    
    'debug': {
        'name': 'Launcher_debug',
        'description': 'Debug build with console and verbose logging',
        'console': True,
        'env_vars': {'LAUNCHER_DEBUG': '1'},
        'excluded_modules': [
            'matplotlib', 'numpy', 'pandas',
        ],
        'extra_args': ['--debug=all'],
        'expected_size': '50+ MB',
    },
}


# ============================================================================
# BUILD FUNCTIONS
# ============================================================================

def get_project_root():
    """Get the project root directory (2 levels up from this script)"""
    return Path(__file__).parent.parent.parent

def build_launcher(preset_name='full', modifiers=None):
    """Build the launcher with the specified preset and optional modifiers
    
    Args:
        preset_name: Name of the preset to use
        modifiers: List of modifier flags (nocs, nopd, upx)
    """
    
    if modifiers is None:
        modifiers = []
    
    if preset_name not in PRESETS:
        print(f"ERROR: Unknown preset '{preset_name}'")
        print(f"Available presets: {', '.join(PRESETS.keys())}")
        sys.exit(1)
    
    preset = PRESETS[preset_name].copy()  # Make a copy to avoid modifying original
    project_root = get_project_root()
    
    # Apply modifiers
    excluded_modules = list(preset['excluded_modules'])  # Copy the list
    extra_args = list(preset['extra_args'])  # Copy the list
    size_reduction = []
    
    if 'nocs' in modifiers:
        # Exclude cloud sync utilities
        excluded_modules.extend([
            'Python.utils.cloud_path_utils',
            'Python.managers.cloud_sync',
        ])
        size_reduction.append('cloud sync (~1-2 MB)')
    
    if 'nopd' in modifiers:
        # Exclude path discovery and PCGW templates
        excluded_modules.extend([
            'Python.utils.path_discovery',
            'Python.managers.pcgw_manager',
        ])
        size_reduction.append('path discovery (~1-2 MB)')
    
    if 'upx' in modifiers:
        # Enable UPX compression
        if '--noupx' in extra_args:
            extra_args.remove('--noupx')
        # Note: UPX must be installed and in PATH
        size_reduction.append('UPX compression (~30-40%)')
    
    preset['excluded_modules'] = excluded_modules
    preset['extra_args'] = extra_args
    
    print("=" * 70)
    print(f"Building Launcher with preset: {preset_name}")
    if modifiers:
        print(f"Modifiers: {', '.join(modifiers)}")
    print("=" * 70)
    print(f"Description: {preset['description']}")
    print(f"Output name: {preset['name']}.exe")
    print(f"Expected size: {preset['expected_size']}")
    if size_reduction:
        print(f"Size reduction: {', '.join(size_reduction)}")
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
    
    # Add UPX disable if not using upx modifier
    if 'upx' not in modifiers and '--noupx' not in args:
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
        if size_reduction:
            print(f"Size reduction applied: {', '.join(size_reduction)}")
        print()
        
        # Show next steps based on preset
        if preset_name == 'minimal':
            print("Minimal build notes:")
            print("  - Hotkeys are enabled (Ctrl+Alt+F9 for help)")
            print("  - No splash screen or tray menu")
            print("  - Process management uses taskkill fallback")
            print()
        elif preset_name == 'debug':
            print("Debug build notes:")
            print("  - Console window will be visible")
            print("  - Verbose logging enabled")
            print("  - Check launcher.log for detailed output")
            print()
        
        if 'upx' in modifiers:
            print("UPX compression notes:")
            print("  - Make sure UPX is installed and in your PATH")
            print("  - Download from: https://upx.github.io/")
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
    
    print("Optional Modifiers:")
    print("  nocs  - Exclude cloud sync utilities (saves ~1-2 MB)")
    print("  nopd  - Exclude path discovery/PCGW templates (saves ~1-2 MB)")
    print("  upx   - Enable UPX compression (reduces size by 30-40%)")
    print()

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Build Launcher.exe with different feature presets',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python Build_PyLauncher.py              # Build with 'full' preset (default)
  python Build_PyLauncher.py minimal      # Build minimal version
  python Build_PyLauncher.py standard nocs nopd upx  # Standard without cloud sync, path discovery, with UPX
  python Build_PyLauncher.py --list       # List all available presets
  
Presets:
  full      - Full-featured build (50+ MB)
  minimal   - Minimal build with hotkeys (10-15 MB)
  standard  - Standard build without GUI (20-25 MB)
  portable  - Portable optimized build (15-20 MB)
  debug     - Debug build with console (50+ MB)

Optional Modifiers:
  nocs      - Exclude cloud sync utilities (saves ~1-2 MB)
  nopd      - Exclude path discovery/PCGW templates (saves ~1-2 MB)
  upx       - Enable UPX compression (reduces size by 30-40%)
        """
    )
    
    parser.add_argument(
        'preset',
        nargs='?',
        default='full',
        choices=list(PRESETS.keys()),
        help='Build preset to use (default: full)'
    )
    
    parser.add_argument(
        'modifiers',
        nargs='*',
        choices=['nocs', 'nopd', 'upx'],
        help='Optional modifiers: nocs (no cloud sync), nopd (no path discovery), upx (UPX compression)'
    )
    
    parser.add_argument(
        '--list',
        action='store_true',
        help='List all available presets and exit'
    )
    
    args = parser.parse_args()
    
    if args.list:
        list_presets()
        sys.exit(0)
    
    build_launcher(args.preset, args.modifiers)

if __name__ == '__main__':
    main()
