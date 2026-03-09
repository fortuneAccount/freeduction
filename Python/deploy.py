#!/usr/bin/env python3
"""deploy.py

Tool to load bracketed tags from README.set and site/index.set,
provide a simple UI to set values, save them to an INI file, and
write README.md and site/index.html with tags replaced.

Usage:
  python -m Python.deploy       # start GUI
  python -m Python.deploy --apply  # apply replacements using INI values
  python -m Python.deploy --init-ini  # create ini with keys discovered
"""
from __future__ import annotations

import configparser
import hashlib
import os
import datetime
import platform
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

DEFAULT_INI = "deploy_ui.ini"
README_SET = Path("README.set")
SITE_SET = Path("site") / "index.set"
OUT_README = Path("README.md")
OUT_INDEX = Path("site") / "index.html"

def read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def find_tags_in_text(text: str) -> Set[str]:
    # Find double-curly-brace tokens like {{TAG}}
    tokens = re.findall(r"\{\{([^\}]+)\}\}", text)
    return set(token.strip() for token in tokens)


def find_tags(files: List[Path]) -> List[str]:
    tags: Set[str] = set()
    for p in files:
        tags.update(find_tags_in_text(read_file(p)))
    # Keep deterministic order
    return sorted(tags)


def load_ini(path: Path, keys: List[str]) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if path.exists():
        cfg.read(path, encoding="utf-8")
    if "values" not in cfg:
        cfg["values"] = {}
    # Ensure keys exist
    for k in keys:
        if k not in cfg["values"]:
            cfg["values"][k] = ""
    return cfg


def save_ini(path: Path, cfg: configparser.ConfigParser) -> None:
    with path.open("w", encoding="utf-8") as f:
        cfg.write(f)


def apply_replacements(tag_values: Dict[str, str]) -> None:
    # Replace in README.set -> README.md
    readme_text = read_file(README_SET)
    index_text = read_file(SITE_SET)
    for k, v in tag_values.items():
        readme_text = readme_text.replace(f"{{{{{k}}}}}", v)
        index_text = index_text.replace(f"{{{{{k}}}}}", v)

    # Ensure site dir exists
    OUT_README.write_text(readme_text, encoding="utf-8")
    OUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    OUT_INDEX.write_text(index_text, encoding="utf-8")


def init_ini(ini_path: Path, keys: List[str]) -> None:
    cfg = load_ini(ini_path, keys)
    save_ini(ini_path, cfg)
    print(f"Created/updated INI: {ini_path}")


def increment_version(v: str) -> str:
    prefix = ""
    if v.lower().startswith("v"):
        prefix = v[0]
        v = v[1:]
    
    parts = v.split('.')
    try:
        parts[-1] = str(int(parts[-1]) + 1)
        return prefix + ".".join(parts)
    except (ValueError, IndexError):
        return prefix + v

def run_cli_apply(ini_path: Path) -> None:
    cfg = configparser.ConfigParser()
    cfg.read(ini_path, encoding="utf-8")
    values = dict(cfg.get("values", fallback={})) if cfg else {}
    # Fallback: gather tags if none in ini
    tags = find_tags([README_SET, SITE_SET])
    tag_values = {k: values.get(k, "") for k in tags}
    apply_replacements(tag_values)
    print(f"Wrote {OUT_README} and {OUT_INDEX}")


def run_gui(ini_path: Path) -> None:
    try:
        import tkinter as tk
        from tkinter import ttk
        from tkinter import filedialog
        from tkinter import messagebox
        from tkinter import scrolledtext
    except Exception as e:
        print("Tkinter not available:", e)
        print("Use --apply or --init-ini instead.")
        sys.exit(1)

    tags = find_tags([README_SET, SITE_SET])
    cfg = load_ini(ini_path, tags)

    if not cfg.has_section("build"):
        cfg.add_section("build")
    
    # Add launcher_build section if not exists
    if not cfg.has_section("launcher_build"):
        cfg.add_section("launcher_build")

    root = tk.Tk()
    root.title("Deploy: tag editor & builder")
    root.geometry("900x600")
    
    # Make the window resizable but with minimum size
    root.minsize(800, 500)
    
    # Configure grid weights for resizing
    root.grid_rowconfigure(0, weight=1)
    root.grid_columnconfigure(0, weight=1)

    # Create main container with two sections: tags (scrollable) and build controls
    main_container = ttk.Frame(root, padding=4)
    main_container.grid(row=0, column=0, sticky="nsew")
    
    # Configure main container grid
    main_container.grid_rowconfigure(0, weight=1)  # Tags frame gets all extra vertical space
    main_container.grid_rowconfigure(1, weight=0)  # Build controls fixed height
    main_container.grid_columnconfigure(0, weight=1)
    
    # --- Tags Section (Scrollable) ---
    tags_container = ttk.Frame(main_container)
    tags_container.grid(row=0, column=0, sticky="nsew", pady=(0, 4))
    
    # Create canvas with scrollbar for tags
    tags_canvas = tk.Canvas(tags_container, highlightthickness=0)
    tags_scrollbar = ttk.Scrollbar(tags_container, orient="vertical", command=tags_canvas.yview)
    tags_scrollable_frame = ttk.Frame(tags_canvas)
    
    tags_scrollable_frame.bind(
        "<Configure>",
        lambda e: tags_canvas.configure(scrollregion=tags_canvas.bbox("all"))
    )
    
    tags_canvas.create_window((0, 0), window=tags_scrollable_frame, anchor="nw")
    tags_canvas.configure(yscrollcommand=tags_scrollbar.set)
    
    # Pack canvas and scrollbar
    tags_canvas.pack(side="left", fill="both", expand=True)
    tags_scrollbar.pack(side="right", fill="y")
    
    # Add mouse wheel support for scrolling
    def _on_mousewheel(event):
        tags_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
    
    tags_canvas.bind_all("<MouseWheel>", _on_mousewheel)
    
    # Clean up binding when window closes
    def unbind_mousewheel():
        tags_canvas.unbind_all("<MouseWheel>")
    
    root.bind("<Destroy>", lambda e: unbind_mousewheel())
    
    # Configure tags_container for resizing
    tags_container.grid_rowconfigure(0, weight=1)
    tags_container.grid_columnconfigure(0, weight=1)
    
    vars: Dict[str, tk.StringVar] = {}

    def save_all(_=None):
        for k, sv in vars.items():
            cfg["values"][k] = sv.get()
        
        # Save build vars
        cfg["build"]["dest"] = build_vars['dest'].get()
        cfg["build"]["workpath"] = build_vars['workpath'].get()
        cfg["build"]["commit_msg"] = build_vars['commit_msg'].get()
        cfg["build"]["skip_python"] = str(build_vars['skip_python'].get())
        cfg["build"]["skip_c"] = str(build_vars['skip_c'].get())
        cfg["build"]["skip_application"] = str(build_vars['skip_application'].get())
        cfg["build"]["clean_build"] = str(build_vars['clean_build'].get())
        cfg["build"]["default_launcher"] = build_vars['default_launcher'].get()
        
        # Save launcher build options
        cfg["launcher_build"]["preset"] = build_vars['launcher_preset'].get()
            
        save_ini(ini_path, cfg)
        apply_replacements({k: cfg["values"].get(k, "") for k in tags})

    # Build tag form in scrollable frame - optimized for 900x600 screen
    for i, k in enumerate(tags):
        lbl = ttk.Label(tags_scrollable_frame, text=k)
        lbl.grid(row=i, column=0, sticky="w", padx=(0, 4), pady=1)
        sv = tk.StringVar(value=cfg["values"].get(k, ""))
        ent = ttk.Entry(tags_scrollable_frame, textvariable=sv, width=45)
        ent.grid(row=i, column=1, sticky="we", pady=1)
        vars[k] = sv

        if k == "VERSION":
            btn_inc = ttk.Button(tags_scrollable_frame, text="+", width=2, command=lambda s=sv: s.set(increment_version(s.get())))
            btn_inc.grid(row=i, column=2, padx=1)

        # autosave on change
        def make_callback(key):
            def cb(*args):
                cfg["values"][key] = vars[key].get()
                save_ini(ini_path, cfg)
                apply_replacements({k: cfg["values"].get(k, "") for k in tags})
            return cb

        sv.trace_add("write", make_callback(k))

    if "RDATE" in vars:
        now = datetime.datetime.now()
        vars["RDATE"].set(now.strftime("%m-%d-%Y"))
    
    # Configure columns in scrollable frame
    tags_scrollable_frame.grid_columnconfigure(1, weight=1)
    
    # --- Build Controls Section (Fixed) ---
    build_container = ttk.LabelFrame(main_container, text="Build Controls", padding=6)
    build_container.grid(row=1, column=0, sticky="ew", pady=(0, 4))
    
    # Configure build container columns for resizing
    build_container.grid_columnconfigure(0, weight=1)
    build_container.grid_columnconfigure(1, weight=1)
    
    build_vars = {
        'dest': tk.StringVar(value=cfg.get('build', 'dest', fallback=str(Path("dist").absolute()))),
        'workpath': tk.StringVar(value=cfg.get('build', 'workpath', fallback=str(Path("build").absolute()))),
        'commit_msg': tk.StringVar(value=cfg.get('build', 'commit_msg', fallback="Update")),
        'skip_python': tk.BooleanVar(value=cfg.getboolean('build', 'skip_python', fallback=False)),
        'skip_c': tk.BooleanVar(value=cfg.getboolean('build', 'skip_c', fallback=False)),
        'skip_application': tk.BooleanVar(value=cfg.getboolean('build', 'skip_application', fallback=False)),
        'clean_build': tk.BooleanVar(value=cfg.getboolean('build', 'clean_build', fallback=True)),
        'default_launcher': tk.StringVar(value=cfg.get('build', 'default_launcher', fallback='C')),
        # Launcher build options
        'launcher_preset': tk.StringVar(value=cfg.get('launcher_build', 'preset', fallback='standard')),
    }
    
    # Build options grid layout
    row = 0
    
    # First row: Onefile checkbox and Dest path
    ctl_frame = ttk.Frame(build_container)
    ctl_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 2))
    
    ttk.Label(ctl_frame, text="Dest:").pack(side="left", padx=2)
    ttk.Entry(ctl_frame, textvariable=build_vars['dest'], width=35).pack(side="left", fill="x", expand=True)
    
    def browse_dest():
        d = filedialog.askdirectory()
        if d: build_vars['dest'].set(d)
    ttk.Button(ctl_frame, text="...", width=2, command=browse_dest).pack(side="left", padx=1)
    
    row += 1
    
    # Second row: Workpath
    wp_frame = ttk.Frame(build_container)
    wp_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 2))
    ttk.Label(wp_frame, text="Workpath:").pack(side="left", padx=2)
    ttk.Entry(wp_frame, textvariable=build_vars['workpath'], width=35).pack(side="left", fill="x", expand=True)
    def browse_workpath():
        d = filedialog.askdirectory()
        if d: build_vars['workpath'].set(d)
    ttk.Button(wp_frame, text="...", width=2, command=browse_workpath).pack(side="left", padx=1)
    
    row += 1
    
    # Third row: Commit message
    git_frame = ttk.Frame(build_container)
    git_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 2))
    ttk.Label(git_frame, text="Commit:").pack(side="left", padx=2)
    ttk.Entry(git_frame, textvariable=build_vars['commit_msg'], width=35).pack(side="left", fill="x", expand=True)
    
    row += 1
    
    # Fourth row: Skip options
    skip_frame = ttk.Frame(build_container)
    skip_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
    ttk.Checkbutton(skip_frame, text="Skip Python", variable=build_vars['skip_python']).pack(side="left", padx=2)
    ttk.Checkbutton(skip_frame, text="Skip App", variable=build_vars['skip_application']).pack(side="left", padx=2)
    ttk.Checkbutton(skip_frame, text="Skip C", variable=build_vars['skip_c']).pack(side="left", padx=2)
    ttk.Checkbutton(skip_frame, text="Clean Build", variable=build_vars['clean_build']).pack(side="left", padx=2)
    
    row += 1
    
    # Launcher Build Options
    launcher_frame = ttk.LabelFrame(build_container, text="Launcher Options", padding=4)
    launcher_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 2))
    row += 1

    # Default Launcher Executable
    launcher_type_frame = ttk.LabelFrame(build_container, text="Default Launcher Executable", padding=4)
    launcher_type_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 2))
    ttk.Radiobutton(launcher_type_frame, text="C Launcher", variable=build_vars['default_launcher'], value='C').pack(side="left", padx=10)
    ttk.Radiobutton(launcher_type_frame, text="Python Launcher", variable=build_vars['default_launcher'], value='Python').pack(side="left", padx=10)

    row += 1
    
    # Launcher options in two columns
    launcher_frame.grid_columnconfigure(0, weight=1)
    
    # Left column: Preset selection
    preset_frame = ttk.Frame(launcher_frame)
    preset_frame.grid(row=0, column=0, sticky="w", padx=2, pady=2)
    
    ttk.Label(preset_frame, text="Preset:").pack(side="left", padx=2)
    preset_combo = ttk.Combobox(preset_frame, textvariable=build_vars['launcher_preset'], 
                                 values=['minimal', 'standard'],
                                 state='readonly', width=10)
    preset_combo.pack(side="left", padx=2)
    
    # Preset descriptions
    preset_descriptions = {
        'minimal': 'Minimal',
        'standard': 'Standard',
    }
    
    preset_desc_label = ttk.Label(preset_frame, text=preset_descriptions.get(build_vars['launcher_preset'].get(), ''))
    preset_desc_label.pack(side="left", padx=4)
    
    def update_preset_desc(*args):
        preset_desc_label.config(text=preset_descriptions.get(build_vars['launcher_preset'].get(), ''))
    
    build_vars['launcher_preset'].trace_add('write', update_preset_desc)
    
    # Global reference for the log window and widget
    log_window_ref = {'win': None, 'widget': None}

    def open_log_window(title="Process Log"):
        if log_window_ref['win'] is not None and log_window_ref['win'].winfo_exists():
            log_window_ref['win'].lift()
            return
        
        log_win = tk.Toplevel(root)
        log_win.title(title)
        log_win.geometry("700x500")
        log_win.transient(root)
        log_win.grab_set()
        
        txt = scrolledtext.ScrolledText(log_win, state='disabled', font=("Consolas", 9))
        txt.pack(fill='both', expand=True)
        
        log_window_ref['win'] = log_win
        log_window_ref['widget'] = txt
    
    def log(msg):
        def _log():
            if log_window_ref['widget'] and log_window_ref['widget'].winfo_exists():
                log_window_ref['widget'].config(state='normal')
                log_window_ref['widget'].insert("end", msg)
                log_window_ref['widget'].see("end")
                log_window_ref['widget'].config(state='disabled')
        root.after(0, _log)
        
    # Process state management
    proc_state = {'proc': None, 'cancelled': False}
    
    def set_ui_busy(busy):
        state = 'disabled' if busy else 'normal'
        
        def _recursive_set_state(widget):
            for child in widget.winfo_children():
                if isinstance(child, (ttk.Button, ttk.Entry, ttk.Checkbutton, ttk.Radiobutton)):
                    if child != btn_cancel:
                        child.configure(state=state)
                if isinstance(child, (ttk.Frame, tk.Frame, ttk.LabelFrame)):
                    _recursive_set_state(child)
        
        _recursive_set_state(main_container)
        btn_cancel.configure(state='normal' if busy else 'disabled')

    def cancel_process():
        proc_state['cancelled'] = True
        if proc_state['proc']:
            try:
                proc_state['proc'].kill()
            except:
                pass
        log("\n>>> Operation Cancelled by User <<<\n")

    def run_cmd_sequence(commands, cwd=None):
        for cmd in commands:
            if proc_state['cancelled']: return False
            log(f"> {' '.join(cmd)}\n")
            try:
                process = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, encoding='utf-8', cwd=str(cwd) if cwd else None
                )
                proc_state['proc'] = process
                for line in process.stdout:
                    log(line)
                process.wait()
                if process.returncode != 0:
                    log(f"Command failed with code {process.returncode}\n")
                    return False
            except Exception as e:
                log(f"Error executing {cmd[0]}: {e}\n")
                return False
        return True

    def run_build_and_release():
        import threading
        import subprocess
        import platform
        import shutil

        # Get all vars from UI
        save_all()
        
        version = vars.get('VERSION', tk.StringVar(value="")).get()
        git_user = vars.get('GITUSER', tk.StringVar(value="")).get()
        rj_proj = vars.get('RJ_PROJ', tk.StringVar(value="")).get()
        dest_dir_str = build_vars['dest'].get()
        dest_dir = Path(dest_dir_str)
        workpath = build_vars['workpath'].get()
        commit_msg = build_vars['commit_msg'].get()
        skip_python = build_vars['skip_python'].get()
        skip_c = build_vars['skip_c'].get()
        skip_application = build_vars['skip_application'].get()
        clean_build = build_vars['clean_build'].get()
        default_launcher = build_vars['default_launcher'].get()
        
        def worker():
            set_ui_busy(True)
            proc_state['cancelled'] = False
            log("\n>>> Starting Build & Release Process <<<\n")

            # 0. Clean directories if requested
            if clean_build:
                log("Cleaning previous build artifacts...\n")
                archive_path_to_clean = Path.cwd() / "portable.7z"
                
                if dest_dir.exists() and dest_dir.is_dir():
                    log(f"Removing destination directory: {dest_dir}\n")
                    try:
                        shutil.rmtree(dest_dir)
                    except Exception as e:
                        log(f"Could not remove destination directory: {e}\n")
                
                workpath_path = Path(workpath)
                if workpath_path.exists() and workpath_path.is_dir():
                    log(f"Removing work directory: {workpath_path}\n")
                    try:
                        shutil.rmtree(workpath_path)
                    except Exception as e:
                        log(f"Could not remove work directory: {e}\n")
                
                if archive_path_to_clean.exists():
                    log(f"Removing previous archive: {archive_path_to_clean}\n")
                    try:
                        archive_path_to_clean.unlink()
                    except Exception as e:
                        log(f"Could not remove previous archive: {e}\n")
                log("Cleaning complete.\n")

            # 1. Check GitHub version
            if version:
                log(f"Checking if version {version} exists on GitHub...\n")
                try:
                    check_cmd = ["gh", "release", "view", version]
                    proc = subprocess.run(check_cmd, capture_output=True, text=True)
                    
                    if proc.returncode == 0:
                        log(f"Version {version} already exists.\n")
                        
                        def show_error_and_increment():
                            messagebox.showerror("Version Conflict", f"Version {version} already exists on GitHub.\nPlease increment the version and try again.")
                        
                        root.after(0, show_error_and_increment)
                        set_ui_busy(False)
                        return
                except FileNotFoundError:
                    log("GH CLI not found, skipping version check.\n")
                except Exception as e:
                    log(f"Version check failed: {e}\n")
            
            if proc_state['cancelled']: set_ui_busy(False); return

            # 2. Run Build
            sep = ';' if platform.system() == 'Windows' else ':'
            script_dir = Path(__file__).parent.absolute()
            project_root = script_dir.parent if script_dir.name.lower() == "python" else script_dir
            
            python_launcher_built_path = None
            
            if not skip_python:
                # Main Application Build
                if not skip_application:
                    log(f"Starting Main Build (application)...\n")
                    main_script = script_dir / "main.py"
                    icon_path = project_root / "assets" / "Joystick.ico"
                    cmd_main = [
                        sys.executable, '-m', 'PyInstaller', str(main_script),
                        f'--name={rj_proj}', '--noconfirm', '--clean', '--windowed',
                        f'--distpath={dest_dir_str}', f'--workpath={workpath}',
                        f'--add-data={project_root / "site"}{sep}site',
                        f'--add-data={project_root / "assets"}{sep}assets',
                        '--onefile', '--noupx'
                    ]
                    if platform.system() == 'Windows' and icon_path.exists():
                        cmd_main.append(f'--icon={icon_path}')
                    
                    if not run_cmd_sequence([cmd_main], cwd=project_root):
                        set_ui_busy(False); proc_state['proc'] = None; return
                else:
                    log("Skipping Main Build (application).\n")

                if proc_state['cancelled']: set_ui_busy(False); return

                # Launcher Build
                launcher_preset = build_vars['launcher_preset'].get()
                build_script = project_root / "assets" / "launcher" / "Build_PyLauncher.py"
                if build_script.exists():
                    log(f"\nStarting Launcher Build with preset '{launcher_preset}'...\n")
                    cmd_launcher = [sys.executable, str(build_script), launcher_preset]
                    if not run_cmd_sequence([cmd_launcher], cwd=project_root):
                        set_ui_busy(False); proc_state['proc'] = None; return
                    
                    # Store path to the built python launcher for later
                    # It is built into a dedicated directory to avoid being in the main dist folder.
                    preset_name = {'minimal': 'Launcher_minimal', 'standard': 'Launcher_standard'}.get(launcher_preset, 'Launcher_standard')
                    py_launcher_dist_path = Path(workpath) / 'py_launcher_dist'
                    src = py_launcher_dist_path / f"{preset_name}.exe"

                    if src.exists():
                        python_launcher_built_path = src
                        log(f"Python launcher built successfully at: {src}\n")
                    else:
                        log(f"\nError: {preset_name}.exe not found in {py_launcher_dist_path} after build.\n")
                else:
                    log(f"\nError: Build_PyLauncher.py not found. Cannot build launcher.\n")
            else:
                log("Skipping Python builds.\n")

            if proc_state['cancelled']: set_ui_busy(False); return

            # Compile C Launcher
            c_launcher_built = False
            launcher_src_dir = project_root / "assets" / "launcher"
            if not skip_c:
                log(f"\nStarting C Launcher Build...\n")
                if platform.system() == 'Windows':
                    build_script_c = launcher_src_dir / "Build.bat"
                    cmd_c_build = ["cmd", "/c", str(build_script_c)]
                else:
                    build_script_c = launcher_src_dir / "build.sh"
                    cmd_c_build = ["sh", str(build_script_c), "--linux"]
                
                if build_script_c.exists():
                    if run_cmd_sequence([cmd_c_build], cwd=launcher_src_dir): # This returns False on failure
                        log("C Launcher Build Completed.\n")
                        c_launcher_built = True
                    else:
                        log("\nC Launcher build failed. Halting process.\n")
                        set_ui_busy(False); proc_state['proc'] = None; return
                else:
                    log(f"Build script not found: {build_script_c}\n")
            else:
                log("Skipping C Launcher build.\n")

            # Manage Launcher Executables
            log("\nManaging launcher executables...\n")
            bin_dir = project_root / "bin"
            bin_dir.mkdir(exist_ok=True)
            c_launcher_src_path = launcher_src_dir / "Launcher.exe"

            # Define final destinations
            c_launcher_final_default = bin_dir / "Launcher.exe"
            c_launcher_final_alt = bin_dir / "Launcher.c.exe"
            py_launcher_final_default = bin_dir / "Launcher.exe"
            py_launcher_final_alt = bin_dir / "Launcher.py.exe"

            # Clean up previous versions in bin to avoid conflicts
            for p in [c_launcher_final_default, c_launcher_final_alt, py_launcher_final_alt]:
                if p.exists():
                    try:
                        p.unlink()
                    except OSError as e:
                        log(f"Could not remove old launcher {p}: {e}\n")

            if default_launcher == 'C':
                log("Setting C Launcher as default.\n")
                if c_launcher_built and c_launcher_src_path.exists():
                    shutil.move(str(c_launcher_src_path), str(c_launcher_final_default))
                    log(f"  - C Launcher set as default: {c_launcher_final_default}\n")
                else:
                    log("  - C Launcher source not found or build skipped/failed.\n")
                
                if python_launcher_built_path and python_launcher_built_path.exists():
                    shutil.copy2(str(python_launcher_built_path), str(py_launcher_final_alt))
                    log(f"  - Python Launcher set as alternate: {py_launcher_final_alt}\n")
                else:
                    log("  - Python Launcher source not found or build skipped/failed.\n")
            else:  # Python is default
                log("Setting Python Launcher as default.\n")
                if python_launcher_built_path and python_launcher_built_path.exists():
                    shutil.copy2(str(python_launcher_built_path), str(py_launcher_final_default))
                    log(f"  - Python Launcher set as default: {py_launcher_final_default}\n")
                else:
                    log("  - Python Launcher source not found or build skipped/failed.\n")

                if c_launcher_built and c_launcher_src_path.exists():
                    shutil.move(str(c_launcher_src_path), str(c_launcher_final_alt))
                    log(f"  - C Launcher set as alternate: {c_launcher_final_alt}\n")
                else:
                    log("  - C Launcher source not found or build skipped/failed.\n")

            log("Build phase completed.\n")
            if proc_state['cancelled']: set_ui_busy(False); return

            # 3. Package and Release
            log("\nStarting Packaging and Release phase...\n")

            # Calculate SHA1
            log("Calculating SHA1 of executable...\n")
            exe_name = f"{rj_proj}.exe" if platform.system() == "Windows" else f"{rj_proj}"
            exe_path = None
            for dirpath, _, files in os.walk(dest_dir):
                if exe_name in files:
                    exe_path = Path(dirpath) / exe_name
                    break
            
            sha1_hash = ""
            if exe_path and exe_path.exists():
                log(f"Found executable at: {exe_path}\n")
                sha1 = hashlib.sha1()
                with open(exe_path, 'rb') as f:
                    while chunk := f.read(65536):
                        sha1.update(chunk)
                sha1_hash = sha1.hexdigest()
                log(f"Executable SHA1: {sha1_hash}\n")
            else:
                log(f"Executable '{exe_name}' not found in '{dest_dir_str}'. Build might have failed. Aborting release.\n")
                set_ui_busy(False)
                return

            if proc_state['cancelled']: set_ui_busy(False); return

            # Compress
            archive_name = "portable.7z"
            # Place the archive in the parent of the dist directory.
            # This allows the user to place build artifacts outside the git repo.
            archive_path = dest_dir.parent / archive_name
            seven_z = project_root / "bin" / "7z.exe"
            
            if seven_z.exists() and dest_dir.exists():
                log(f"Compressing {dest_dir} to {archive_name}...\n")
                if archive_path.exists(): archive_path.unlink()
                
                cmd_7z = [str(seven_z), "a", str(archive_path), f"{dest_dir_str}\\*"]
                if not run_cmd_sequence([cmd_7z]):
                    set_ui_busy(False); return
                log("Compression complete.\n")
            else:
                log("7z.exe or dist directory not found. Cannot create archive.\n")
                set_ui_busy(False); return

            if proc_state['cancelled']: set_ui_busy(False); return

            # Calculate Size and update UI
            size_mb = os.path.getsize(archive_path) / (1024 * 1024)
            
            def update_ui_for_release():
                if 'RSHA1' in vars and sha1_hash: vars['RSHA1'].set(sha1_hash)
                if 'RSIZE' in vars: vars['RSIZE'].set(f"{size_mb:.2f}")
                if 'PORTABLE' in vars and git_user and rj_proj and version:
                    url = f"https://github.com/{git_user}/{rj_proj}/releases/download/{version}/{archive_name}"
                    vars['PORTABLE'].set(url)
                save_all()
            root.after(0, update_ui_for_release)
            
            import time
            time.sleep(1)

            if proc_state['cancelled']: set_ui_busy(False); return

            # Git Push & Release
            log("Committing changes and pushing to Git...\n")
            git_commands = [
                ["git", "add", "."],
                ["git", "commit", "-m", commit_msg],
                ["git", "push", "-f", "-u", "origin", "main"]
            ]
            if not run_cmd_sequence(git_commands, cwd=Path.cwd()):
                set_ui_busy(False); return

            if proc_state['cancelled']: set_ui_busy(False); return

            log("Creating GitHub Release...\n")
            try:
                release_cmd = ["gh", "release", "create", version, str(archive_path), "--title", version, "--notes", "Automated release"]
                if not run_cmd_sequence([release_cmd], cwd=Path.cwd()):
                    log("GitHub release creation failed.\n")
                    set_ui_busy(False); return
                
                log(f"Release {version} created successfully.\n")
                
                # Auto-increment version
                new_ver = increment_version(version)
                if new_ver != version:
                    def update_ver_ui():
                        if 'VERSION' in vars:
                            vars['VERSION'].set(new_ver)
                            save_all()
                            log(f"Version auto-incremented to {new_ver}\n")
                    root.after(0, update_ver_ui)
            except FileNotFoundError:
                log("GH CLI not found. Skipping upload.\n")
            except Exception as e:
                log(f"Release upload failed: {e}\n")
            finally:
                log("\n>>> Build & Release Process Completed <<<\n")
                set_ui_busy(False)
                proc_state['proc'] = None

        open_log_window("Build & Release Log")
        threading.Thread(target=worker, daemon=True).start()

    # Button Row in build container
    btn_row = ttk.Frame(build_container, padding=(0, 4))
    btn_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 0))
    
    ttk.Button(btn_row, text="Apply & Save", command=save_all).pack(side="left", padx=2)
    ttk.Button(btn_row, text="Build & Release", command=run_build_and_release).pack(side="left", padx=2)
    
    btn_cancel = ttk.Button(btn_row, text="Cancel", command=cancel_process, state='disabled')
    btn_cancel.pack(side="left", padx=2)

    def on_close():
        save_all()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


def main(argv: List[str]) -> None:
    ini_path = Path(DEFAULT_INI)
    if "--init-ini" in argv:
        tags = find_tags([README_SET, SITE_SET])
        init_ini(ini_path, tags)
        return
    if "--apply" in argv:
        if not ini_path.exists():
            print("INI not found. Run with --init-ini or start the GUI to create it.")
            sys.exit(1)
        run_cli_apply(ini_path)
        return
    # Default: start GUI
    if not ini_path.exists():
        tags = find_tags([README_SET, SITE_SET])
        init_ini(ini_path, tags)
    run_gui(ini_path)


if __name__ == "__main__":
    main(sys.argv[1:])
