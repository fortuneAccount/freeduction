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
import logging
import os
import datetime
import platform
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set

def get_writable_dir(subdir: str, fallback_base: Path) -> Path:
    """Return system temp/<subdir> if writable, else fallback_base/<subdir>."""
    import tempfile
    tmp = Path(tempfile.gettempdir()) / subdir
    try:
        tmp.mkdir(parents=True, exist_ok=True)
        test = tmp / ".write_test"
        test.touch()
        test.unlink()
        return tmp
    except OSError:
        fb = fallback_base / subdir
        fb.mkdir(parents=True, exist_ok=True)
        return fb


# --- Deploy logging ---
def setup_deploy_logging(approot=None):
    """Set up logging to {approot}/deploy.log"""
    if approot is None:
        approot = get_approot()
    log_path = Path(approot) / "deploy.log"
    root_logger = logging.getLogger()
    # Only add the deploy.log handler if it's not already attached
    already_attached = any(
        isinstance(h, logging.FileHandler) and h.baseFilename == str(log_path.resolve())
        for h in root_logger.handlers
    )
    if not already_attached:
        handler = logging.FileHandler(str(log_path), mode="a", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        root_logger.addHandler(handler)
    if not any(isinstance(h, logging.StreamHandler) for h in root_logger.handlers):
        root_logger.addHandler(logging.StreamHandler(sys.stdout))
    root_logger.setLevel(logging.INFO)
    logging.info("=== Deploy session started ===")
    return log_path


def get_approot():
    script_dir = Path(__file__).parent.absolute()
    return script_dir.parent if script_dir.name.lower() == "python" else script_dir


# --- Dependency helpers ---
def check_python_deps():
    """Return list of missing Python packages found in requirements*.txt."""
    import importlib.metadata
    approot = get_approot()
    missing = []
    req_files = [approot / "requirements.txt"]
    if platform.system() == "Windows":
        req_files.append(approot / "requirements_win.txt")
    for req_file in req_files:
        if req_file.exists():
            for line in req_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                pkg = line.split("#")[0].strip()
                if not pkg:
                    continue
                try:
                    importlib.metadata.distribution(pkg)
                except (importlib.metadata.PackageNotFoundError, Exception):
                    missing.append(pkg)
    return missing


def install_python_deps(missing_pkgs):
    """Install missing Python packages via pip."""
    if not missing_pkgs:
        return True
    logging.info("Installing missing Python packages: %s", ", ".join(missing_pkgs))
    try:
        cmd = [sys.executable, "-m", "pip", "install"] + missing_pkgs
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logging.info("Python packages installed successfully")
            return True
        else:
            logging.error("Failed to install packages: %s", result.stderr)
            return False
    except Exception as e:
        logging.error("Error installing packages: %s", e)
        return False


def check_c_compiler():
    """Check for C compiler toolchain presence."""
    if platform.system() != "Windows":
        try:
            result = subprocess.run(["gcc", "--version"], capture_output=True, text=True, timeout=10)
            return result.returncode == 0, "gcc" if result.returncode == 0 else "not found"
        except Exception:
            return False, "gcc not found"
    for root in [Path("C:/msys64"), Path("C:/msys2"), Path("C:/msys32")]:
        if root.exists():
            for arch in ["mingw64", "ucrt64", "clang64", "mingw32"]:
                if (root / arch / "bin" / "gcc.exe").exists():
                    return True, f"MSYS2 ({root.name}/{arch})"
            if (root / "usr" / "bin" / "gcc.exe").exists():
                return True, "MSYS2 (msys)"
    pf86 = Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)"))
    vswhere = pf86 / "Microsoft Visual Studio" / "Installer" / "vswhere.exe"
    if vswhere.exists():
        try:
            r = subprocess.run([str(vswhere), "-latest", "-requires",
                                "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                                "-find", "**\\vcvars64.bat"],
                               capture_output=True, text=True, timeout=15)
            if r.returncode == 0 and r.stdout.strip():
                return True, "MSVC"
        except Exception:
            pass
    return False, "No C compiler found"


def check_gh_cli():
    """Check for GitHub CLI availability and auth status."""
    try:
        r = subprocess.run(["gh", "--version"], capture_output=True, text=True, timeout=10)
        if r.returncode != 0:
            return False, "not installed"
        auth = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True, timeout=10)
        if auth.returncode == 0:
            return True, "installed and authenticated"
        return True, "installed but not authenticated"
    except FileNotFoundError:
        return False, "not installed"


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

    # Initialize deploy logging
    setup_deploy_logging()

    class ToolTip:
        """A simple tooltip for tkinter widgets."""
        def __init__(self, widget, text):
            self.widget = widget
            self.text = text
            self.tip_window = None
            widget.bind('<Enter>', self.show_tip)
            widget.bind('<Leave>', self.hide_tip)

        def show_tip(self, event=None):
            if self.tip_window:
                return
            x = self.widget.winfo_rootx() + 25
            y = self.widget.winfo_rooty() + 25
            self.tip_window = tw = tk.Toplevel(self.widget)
            tw.wm_overrideredirect(True)
            tw.wm_geometry(f"+{x}+{y}")
            lbl = tk.Label(tw, text=self.text, justify='left',
                           background="#ffffe0", relief='solid', borderwidth=1,
                           font=("tahoma", 8, "normal"))
            lbl.pack()

        def hide_tip(self, event=None):
            if self.tip_window:
                self.tip_window.destroy()
                self.tip_window = None

    def create_tooltip(widget, text):
        return ToolTip(widget, text)

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
        create_tooltip(ent, f"Tag value for {{{{k}}}} — replaces this tag in README.set and site/index.set")
        vars[k] = sv

        if k == "VERSION":
            btn_inc = ttk.Button(tags_scrollable_frame, text="+", width=2, command=lambda s=sv: s.set(increment_version(s.get())))
            btn_inc.grid(row=i, column=2, padx=1)
            create_tooltip(btn_inc, "Increment the version number (e.g. v1.0 → v1.1)")

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
    
    _script_dir = Path(__file__).parent.absolute()
    _project_root = _script_dir.parent if _script_dir.name.lower() == "python" else _script_dir
    _default_dest = str(Path.home() / "Desktop")
    _default_workpath = str(get_writable_dir("build", _project_root))

    build_vars = {
        'dest': tk.StringVar(value=cfg.get('build', 'dest', fallback=_default_dest)),
        'workpath': tk.StringVar(value=cfg.get('build', 'workpath', fallback=_default_workpath)),
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
    
    # First row: Dest path (portable binary output directory)
    ctl_frame = ttk.Frame(build_container)
    ctl_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 2))
    
    ttk.Label(ctl_frame, text="Dest:").pack(side="left", padx=2)
    dest_entry = ttk.Entry(ctl_frame, textvariable=build_vars['dest'], width=35)
    dest_entry.pack(side="left", fill="x", expand=True)
    create_tooltip(dest_entry, "Output directory for the compiled portable binary (defaults to Desktop)")
    create_tooltip(ctl_frame.winfo_children()[0], "Output directory for the compiled portable binary")
    
    def browse_dest():
        d = filedialog.askdirectory()
        if d:
            build_vars['dest'].set(d)
    browse_btn = ttk.Button(ctl_frame, text="...", width=2, command=browse_dest)
    browse_btn.pack(side="left", padx=1)
    create_tooltip(browse_btn, "Browse for output directory")
    
    row += 1
    
    # Second row: Workpath
    wp_frame = ttk.Frame(build_container)
    wp_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 2))
    ttk.Label(wp_frame, text="Workpath:").pack(side="left", padx=2)
    wp_entry = ttk.Entry(wp_frame, textvariable=build_vars['workpath'], width=35)
    wp_entry.pack(side="left", fill="x", expand=True)
    create_tooltip(wp_entry, "Temporary build directory for PyInstaller intermediate files")
    def browse_workpath():
        d = filedialog.askdirectory()
        if d:
            build_vars['workpath'].set(d)
    wp_btn = ttk.Button(wp_frame, text="...", width=2, command=browse_workpath)
    wp_btn.pack(side="left", padx=1)
    create_tooltip(wp_btn, "Browse for work directory")
    
    row += 1
    
    # Third row: Commit message
    git_frame = ttk.Frame(build_container)
    git_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 2))
    ttk.Label(git_frame, text="Commit:").pack(side="left", padx=2)
    commit_entry = ttk.Entry(git_frame, textvariable=build_vars['commit_msg'], width=35)
    commit_entry.pack(side="left", fill="x", expand=True)
    create_tooltip(commit_entry, "Git commit message used when creating the release")
    
    row += 1
    
    # Fourth row: Skip options
    skip_frame = ttk.Frame(build_container)
    skip_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
    chk_py = ttk.Checkbutton(skip_frame, text="Skip Python", variable=build_vars['skip_python'])
    chk_py.pack(side="left", padx=2)
    create_tooltip(chk_py, "Skip building the Python-based launcher executable")
    chk_app = ttk.Checkbutton(skip_frame, text="Skip App", variable=build_vars['skip_application'])
    chk_app.pack(side="left", padx=2)
    create_tooltip(chk_app, "Skip building the main application via PyInstaller")
    chk_c = ttk.Checkbutton(skip_frame, text="Skip C", variable=build_vars['skip_c'])
    chk_c.pack(side="left", padx=2)
    create_tooltip(chk_c, "Skip building the native C launcher")
    chk_clean = ttk.Checkbutton(skip_frame, text="Clean Build", variable=build_vars['clean_build'])
    chk_clean.pack(side="left", padx=2)
    create_tooltip(chk_clean, "Remove all previous build artifacts before starting")
    
    row += 1
    
    # Launcher Build Options
    launcher_frame = ttk.LabelFrame(build_container, text="Launcher Options", padding=4)
    launcher_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 2))
    row += 1

    # Default Launcher Executable
    launcher_type_frame = ttk.LabelFrame(build_container, text="Default Launcher Executable", padding=4)
    launcher_type_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 2))
    radio_c = ttk.Radiobutton(launcher_type_frame, text="C Launcher", variable=build_vars['default_launcher'], value='C')
    radio_c.pack(side="left", padx=10)
    create_tooltip(radio_c, "Use the compiled C launcher (native, lightweight) as the default game launcher")
    radio_py = ttk.Radiobutton(launcher_type_frame, text="Python Launcher", variable=build_vars['default_launcher'], value='Python')
    radio_py.pack(side="left", padx=10)
    create_tooltip(radio_py, "Use the Python-based launcher as the default game launcher")

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
    create_tooltip(preset_combo, "Build preset: 'minimal' (smaller binary) or 'standard' (full features)")
    
    # Preset descriptions
    preset_descriptions = {
        'minimal': 'Minimal - smaller binary, fewer features',
        'standard': 'Standard - full feature set',
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
        logging.info(msg.rstrip('\n'))
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
            except Exception:
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

    # ------------------------------------------------------------------ #
    #  COMPILE  – build launchers and main application                   #
    # ------------------------------------------------------------------ #
    def run_compile():
        import threading

        save_all()

        dest_dir_str = build_vars['dest'].get()
        dest_dir     = Path(dest_dir_str)
        workpath     = build_vars['workpath'].get()
        skip_python  = build_vars['skip_python'].get()
        skip_c       = build_vars['skip_c'].get()
        skip_app     = build_vars['skip_application'].get()
        clean_build  = build_vars['clean_build'].get()
        default_launcher = build_vars['default_launcher'].get()
        launcher_preset  = build_vars['launcher_preset'].get()
        rj_proj      = vars.get('RJ_PROJ', tk.StringVar(value="")).get()

        def worker():
            set_ui_busy(True)
            proc_state['cancelled'] = False
            log("\n>>> Starting Compile <<<\n")

            sep = ';' if platform.system() == 'Windows' else ':'
            script_dir   = Path(__file__).parent.absolute()
            project_root = script_dir.parent if script_dir.name.lower() == "python" else script_dir
            launcher_src_dir = project_root / "assets" / "launcher"
            bin_dir      = project_root / "bin"
            bin_dir.mkdir(exist_ok=True)

            # 0. Optional clean
            if clean_build:
                log("Cleaning previous build artifacts...\n")
                for d, label in [(dest_dir, "destination"), (Path(workpath), "work")]:
                    if d.exists() and d.is_dir():
                        log(f"  Removing {label} directory: {d}\n")
                        try:    shutil.rmtree(d)
                        except Exception as e: log(f"  Could not remove {d}: {e}\n")
                archive_name_clean = f"{rj_proj}.7z" if rj_proj else "portable.7z"
                old_archive = dest_dir / archive_name_clean
                if old_archive.exists():
                    try:    old_archive.unlink()
                    except Exception as e: log(f"  Could not remove archive: {e}\n")
                old_orig = dest_dir / "portable.orig"
                if old_orig.exists():
                    try:    old_orig.unlink()
                    except Exception as e: log(f"  Could not remove backup: {e}\n")
                log("Clean complete.\n")

            if proc_state['cancelled']: set_ui_busy(False); return

            # 1. Python Launcher → bin/Launcher.py.exe
            py_launcher_final = bin_dir / "Launcher.py.exe"
            if not skip_python:
                build_script_py = project_root / "assets" / "launcher" / "Build_PyLauncher.py"
                if build_script_py.exists():
                    log(f"Building Python Launcher (preset: {launcher_preset})...\n")
                    cmd_launcher = [sys.executable, str(build_script_py), launcher_preset]
                    if not run_cmd_sequence([cmd_launcher], cwd=project_root):
                        set_ui_busy(False); proc_state['proc'] = None; return

                    preset_name = {
                        'minimal':  'Launcher_minimal',
                        'standard': 'Launcher_standard',
                    }.get(launcher_preset, 'Launcher_standard')
                    src_py = Path(workpath) / 'py_launcher_dist' / f"{preset_name}.exe"

                    if src_py.exists():
                        if py_launcher_final.exists():
                            py_launcher_final.unlink()
                        shutil.copy2(str(src_py), str(py_launcher_final))
                        log(f"  Python Launcher → {py_launcher_final}\n")
                    else:
                        log(f"  Error: built file not found: {src_py}\n")
                else:
                    log("  Error: Build_PyLauncher.py not found.\n")
            else:
                log("Skipping Python Launcher build.\n")

            if proc_state['cancelled']: set_ui_busy(False); return

            # 2. C Launcher → bin/Launcher.c.exe
            c_launcher_final = bin_dir / "Launcher.c.exe"
            if not skip_c:
                log("Building C Launcher...\n")
                if platform.system() == 'Windows':
                    build_script_c = launcher_src_dir / "Build.bat"
                    cmd_c = ["cmd", "/c", str(build_script_c)]
                else:
                    build_script_c = launcher_src_dir / "build.sh"
                    cmd_c = ["sh", str(build_script_c), "--linux"]

                if build_script_c.exists():
                    if run_cmd_sequence([cmd_c], cwd=launcher_src_dir):
                        # Build script drops Launcher.exe into launcher_src_dir
                        src_c = launcher_src_dir / "Launcher.exe"
                        if src_c.exists():
                            if c_launcher_final.exists():
                                c_launcher_final.unlink()
                            shutil.move(str(src_c), str(c_launcher_final))
                            log(f"  C Launcher → {c_launcher_final}\n")
                            c_launcher_built = True
                        else:
                            log("  Error: Launcher.exe not found after C build.\n")
                    else:
                        log("C Launcher build failed. Halting.\n")
                        set_ui_busy(False); proc_state['proc'] = None; return
                else:
                    log(f"  Build script not found: {build_script_c}\n")
            else:
                log("Skipping C Launcher build.\n")

            if proc_state['cancelled']: set_ui_busy(False); return

            # 3. Main application (PyInstaller)
            if not skip_python and not skip_app:
                log("Building main application...\n")
                main_script = script_dir / "main.py"
                icon_path   = project_root / "assets" / "Joystick.ico"
                cmd_main = [
                    sys.executable, '-m', 'PyInstaller', str(main_script),
                    f'--name={rj_proj}', '--noconfirm', '--clean', '--windowed',
                    f'--distpath={dest_dir_str}', f'--workpath={workpath}',
                    f'--add-data={project_root / "site"}{sep}site',
                    f'--add-data={project_root / "assets"}{sep}assets',
                    '--onefile', '--noupx',
                    # The app uses PyQt6 exclusively; exclude other Qt bindings
                    # (pulled in transitively) so PyInstaller doesn't try to
                    # collect multiple Qt packages.
                    '--exclude', 'PySide6',
                    '--exclude', 'PySide2',
                    '--exclude', 'PyQt5',
                ]
                if platform.system() == 'Windows' and icon_path.exists():
                    cmd_main.append(f'--icon={icon_path}')
                if not run_cmd_sequence([cmd_main], cwd=project_root):
                    set_ui_busy(False); proc_state['proc'] = None; return
            elif skip_python or skip_app:
                log("Skipping main application build.\n")

            if proc_state['cancelled']: set_ui_busy(False); return

            # 4. Copy chosen default launcher → bin/Launcher.exe
            default_dst = bin_dir / "Launcher.exe"
            if default_dst.exists():
                try:    default_dst.unlink()
                except OSError as e: log(f"  Could not remove old Launcher.exe: {e}\n")

            if default_launcher == 'C':
                src_default = c_launcher_final
                label_default = "C"
            else:
                src_default = py_launcher_final
                label_default = "Python"

            if src_default.exists():
                shutil.copy2(str(src_default), str(default_dst))
                log(f"  Default Launcher ({label_default}) → {default_dst}\n")
            else:
                log(f"  Warning: chosen default launcher not found: {src_default}\n")

            log("\n>>> Compile complete <<<\n")
            set_ui_busy(False)
            proc_state['proc'] = None

        open_log_window("Compile Log")
        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    #  APPLY  – read portable.7z, populate fields, increment version,    #
    #           save INI, write README.md and index.html                  #
    # ------------------------------------------------------------------ #
    def run_apply():
        dest_dir    = Path(build_vars['dest'].get())
        rj_proj     = vars.get('RJ_PROJ', tk.StringVar(value="")).get()
        archive_name = f"{rj_proj}.7z" if rj_proj else "portable.7z"
        archive_path = dest_dir / archive_name
        version     = vars.get('VERSION', tk.StringVar(value="")).get()
        git_user    = vars.get('GITUSER', tk.StringVar(value="")).get()

        if not archive_path.exists():
            messagebox.showerror("Apply", f"Archive not found:\n{archive_path}\n\nRun Compile + Deploy first.")
            return

        # SHA1 of the archive itself
        sha1 = hashlib.sha1()
        try:
            with open(archive_path, 'rb') as f:
                while chunk := f.read(65536):
                    sha1.update(chunk)
            sha1_hash = sha1.hexdigest()
        except OSError as e:
            messagebox.showerror("Apply", f"Could not read archive: {e}")
            return

        size_mb = os.path.getsize(archive_path) / (1024 * 1024)

        # Populate GUI fields
        if 'RSHA1' in vars:
            vars['RSHA1'].set(sha1_hash)
        if 'RSIZE' in vars:
            vars['RSIZE'].set(f"{size_mb:.2f}")
        if 'PORTABLE' in vars and git_user and rj_proj and version:
            url = f"https://github.com/{git_user}/{rj_proj}/releases/download/{version}/{archive_name}"
            vars['PORTABLE'].set(url)
        if 'RDATE' in vars:
            vars['RDATE'].set(datetime.datetime.now().strftime("%m-%d-%Y"))

        # Increment version
        new_ver = increment_version(version)
        if 'VERSION' in vars and new_ver != version:
            vars['VERSION'].set(new_ver)

        # Persist to INI and write output files
        for k, sv in vars.items():
            cfg["values"][k] = sv.get()
        save_ini(ini_path, cfg)
        apply_replacements({k: cfg["values"].get(k, "") for k in tags})

        messagebox.showinfo("Apply", f"Fields updated.\nSHA1: {sha1_hash}\nSize: {size_mb:.2f} MB\nVersion incremented to {new_ver}\nREADME.md and index.html written.")

    # ------------------------------------------------------------------ #
    #  DEPLOY  – compress dist → portable binary                         #
    # ------------------------------------------------------------------ #
    def run_deploy():
        import threading

        dest_dir_str = build_vars['dest'].get()
        dest_dir     = Path(dest_dir_str)
        script_dir   = Path(__file__).parent.absolute()
        project_root = script_dir.parent if script_dir.name.lower() == "python" else script_dir
        rj_proj      = vars.get('RJ_PROJ', tk.StringVar(value="freeduction")).get()
        archive_name = f"{rj_proj}.7z" if rj_proj else "portable.7z"
        archive_path = dest_dir / archive_name
        orig_path    = dest_dir / "portable.orig"
        seven_z      = project_root / "bin" / "7z.exe"

        if not seven_z.exists():
            messagebox.showerror("Deploy", f"7z.exe not found at:\n{seven_z}")
            return
        if not dest_dir.exists():
            messagebox.showerror("Deploy", f"Output directory not found:\n{dest_dir}")
            return

        def worker():
            set_ui_busy(True)
            proc_state['cancelled'] = False
            log("\n>>> Starting Deploy (compress) <<<\n")
            log(f"Destination: {dest_dir}\n")
            log(f"Archive: {archive_path}\n")

            # Backup existing archive → portable.orig
            if archive_path.exists():
                log(f"Backing up existing archive → {orig_path}\n")
                if orig_path.exists():
                    try:
                        orig_path.unlink()
                    except Exception as e:
                        log(f"Could not remove old {orig_path}: {e}\n")
                try:
                    shutil.copy2(str(archive_path), str(orig_path))
                    log(f"Backup saved: {orig_path}\n")
                except Exception as e:
                    log(f"Backup failed: {e}\n")
                try:
                    archive_path.unlink()
                except Exception as e:
                    log(f"Could not remove old archive: {e}\n")

            sep = "\\" if platform.system() == "Windows" else "/"
            cmd_7z = [str(seven_z), "a", str(archive_path), f"{dest_dir_str}{sep}*"]
            if not run_cmd_sequence([cmd_7z]):
                log("Compression failed.\n")
                set_ui_busy(False); return

            log(f"Archive created: {archive_path}\n")

            # Build SFX portable executable that extracts to .\{rj_proj}\ by default
            sfx_module = project_root / "bin" / "7zCon.sfx"
            sfx_output = dest_dir / f"{rj_proj}_portable.exe"

            if sfx_module.exists():
                log("Building SFX portable executable...\n")
                sfx_config = dest_dir / "sfx_config.txt"
                try:
                    sfx_config.write_text(
                        f";!@Install@!UTF-8!\r\n"
                        f"InstallPath=\".\\\\{rj_proj}\\\\\"\r\n"
                        f";!@InstallEnd@!\r\n",
                        encoding="utf-8"
                    )
                    sfx_cmd = ["cmd", "/c", "copy", "/b",
                               f"{sfx_module}+{sfx_config}+{archive_path}",
                               str(sfx_output)]
                    result = subprocess.run(sfx_cmd, capture_output=True, timeout=30)
                    if result.returncode == 0:
                        log(f"  SFX portable: {sfx_output}\n")
                        log(f"  Default extraction path: .{sep}{rj_proj}{sep}\n")
                    else:
                        log(f"  SFX build failed (code {result.returncode})\n")
                        log(f"  stderr: {result.stderr.decode('utf-8', errors='replace')}\n")
                except Exception as e:
                    log(f"  SFX build error: {e}\n")
                finally:
                    try:
                        os.remove(str(sfx_config))
                    except Exception:
                        pass
            else:
                log(f"SFX module not found at {sfx_module}, skipping SFX build.\n")

            log("Portable archive ready\n")
            log("\n>>> Deploy complete <<<\n")
            set_ui_busy(False)
            proc_state['proc'] = None

        open_log_window("Deploy Log")
        threading.Thread(target=worker, daemon=True).start()

    # ------------------------------------------------------------------ #
    #  RELEASE  – git commit/push + gh release create                    #
    # ------------------------------------------------------------------ #
    def run_release():
        import threading

        save_all()

        version      = vars.get('VERSION', tk.StringVar(value="")).get()
        commit_msg   = build_vars['commit_msg'].get()
        dest_dir     = Path(build_vars['dest'].get())
        rj_proj      = vars.get('RJ_PROJ', tk.StringVar(value="freeduction")).get()
        archive_name = f"{rj_proj}.7z" if rj_proj else "portable.7z"
        archive_path = dest_dir / archive_name
        script_dir   = Path(__file__).parent.absolute()
        project_root = script_dir.parent if script_dir.name.lower() == "python" else script_dir

        if not version:
            messagebox.showerror("Release", "VERSION field is empty.")
            return
        if not archive_path.exists():
            messagebox.showerror("Release", f"Archive not found:\n{archive_path}\nRun Deploy first.")
            return

        # Pre-flight diagnostics
        gh_ok, gh_info = check_gh_cli()
        if not gh_ok:
            answer = messagebox.askyesno(
                "GitHub CLI Missing",
                f"GitHub CLI is {gh_info}.\n\n"
                "The release workflow requires:\n"
                "  1. 'gh' CLI installed (https://cli.github.com)\n"
                "  2. 'gh auth login' completed\n"
                "  3. A GitHub remote configured ('git remote -v')\n\n"
                "Continue anyway (will likely fail)?")
            if not answer:
                return

        def worker():
            set_ui_busy(True)
            proc_state['cancelled'] = False
            log("\n>>> Starting Release <<<\n")
            log(f"Release version: {version}\n")
            log(f"Archive: {archive_path}\n")
            log(f"gh CLI: {gh_info}\n")

            # Check if version already exists on GitHub
            log(f"Checking if version {version} already exists on GitHub...\n")
            try:
                proc = subprocess.run(["gh", "release", "view", version],
                                      capture_output=True, text=True, cwd=str(project_root), timeout=30)
                if proc.returncode == 0:
                    log(f"Version {version} already exists on GitHub.\n")
                    root.after(0, lambda: messagebox.showerror(
                        "Version Conflict",
                        f"Version {version} already exists on GitHub.\nIncrement the version and try again."))
                    set_ui_busy(False); return
            except FileNotFoundError:
                log("GH CLI not found. Install from https://cli.github.com/\n")
                set_ui_busy(False); return
            except subprocess.TimeoutExpired:
                log("GitHub version check timed out (network issue?)\n")
            except Exception as e:
                log(f"Version check failed: {e}\n")

            if proc_state['cancelled']: set_ui_busy(False); return

            # Verify git remote
            log("Checking git remote configuration...\n")
            try:
                rmt = subprocess.run(["git", "remote", "-v"], capture_output=True, text=True,
                                     cwd=str(project_root), timeout=15)
                log(rmt.stdout or "(no remotes configured)\n")
                if rmt.returncode != 0 or not rmt.stdout.strip():
                    log("ERROR: No git remote found. Configure with: git remote add origin <url>\n")
                    set_ui_busy(False); return
            except Exception as e:
                log(f"Failed to check git remote: {e}\n")

            if proc_state['cancelled']: set_ui_busy(False); return

            # Git commit and push
            log("Committing and pushing to Git...\n")
            git_commands = [
                ["git", "add", "."],
                ["git", "commit", "-m", commit_msg],
                ["git", "push", "-f", "-u", "origin", "main"],
            ]
            if not run_cmd_sequence(git_commands, cwd=project_root):
                log("Git push failed. Check:\n")
                log("  - You have write access to the remote repository\n")
                log("  - Your SSH key or token is configured correctly\n")
                log("  - The remote URL is correct (git remote -v)\n")
                set_ui_busy(False); return

            if proc_state['cancelled']: set_ui_busy(False); return

            # Create GitHub Release
            log(f"Creating GitHub Release {version}...\n")
            release_cmd = [
                "gh", "release", "create", version, str(archive_path),
                "--title", version, "--notes", "Automated release"
            ]
            try:
                if not run_cmd_sequence([release_cmd], cwd=project_root):
                    log("GitHub release creation failed.\n")
                    log("Troubleshooting:\n")
                    log("  - Run 'gh auth status' to verify authentication\n")
                    log("  - Ensure the version tag doesn't already exist\n")
                    log("  - Check network connectivity to github.com\n")
                    set_ui_busy(False); return
                log(f"Release {version} created successfully.\n")
                log(f"URL: https://github.com/{{GITUSER}}/{{RJ_PROJ}}/releases/tag/{version}\n")
            except FileNotFoundError:
                log("GH CLI not found. Install from https://cli.github.com/\n")
            except Exception as e:
                log(f"Release failed: {e}\n")
                log("Troubleshooting: run 'gh auth login' and 'gh release list'\n")
            finally:
                log("\n>>> Release complete <<<\n")
                set_ui_busy(False)
                proc_state['proc'] = None

        open_log_window("Release Log")
        threading.Thread(target=worker, daemon=True).start()

    # Dependency status display
    dep_status_var = tk.StringVar(value="Deps: unknown")
    dep_label = ttk.Label(build_container, textvariable=dep_status_var, font=("Segoe UI", 8))
    dep_label.grid(row=row, column=0, columnspan=2, sticky="w", padx=2)
    row += 1

    # Button Row in build container
    btn_row = ttk.Frame(build_container, padding=(0, 4))
    btn_row.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 0))

    def run_check_deps():
        """Check dependencies and update status label."""
        missing_py = check_python_deps()
        c_ok, c_info = check_c_compiler()
        gh_ok, gh_info = check_gh_cli()
        parts = []
        if missing_py:
            parts.append(f"Python: {len(missing_py)} missing")
        else:
            parts.append("Python: OK")
        parts.append(f"C: {c_info}")
        parts.append(f"gh: {gh_info}")
        dep_status_var.set(" | ".join(parts))
        log(f"[Deps] Python packages missing: {missing_py}\n")
        log(f"[Deps] C compiler: {c_info}\n")
        log(f"[Deps] GitHub CLI: {gh_info}\n")
        if missing_py:
            if messagebox.askyesno("Install Dependencies",
                                   f"Missing {len(missing_py)} Python packages.\nInstall them now?"):
                if install_python_deps(missing_py):
                    dep_status_var.set("Deps: installed")
                    log("[Deps] Python packages installed successfully.\n")
                else:
                    log("[Deps] Failed to install Python packages.\n")

    btn_deps = ttk.Button(btn_row, text="Deps", command=run_check_deps)
    btn_deps.pack(side="left", padx=2)
    create_tooltip(btn_deps, "Check for missing Python packages, C compiler, and GitHub CLI")

    btn_compile = ttk.Button(btn_row, text="Compile", command=run_compile)
    btn_compile.pack(side="left", padx=2)
    create_tooltip(btn_compile, "Build launchers (Python + C) and main application via PyInstaller")

    btn_apply = ttk.Button(btn_row, text="Apply", command=run_apply)
    btn_apply.pack(side="left", padx=2)
    create_tooltip(btn_apply, "Read portable binary, compute SHA1/size, increment version, update README.md")

    btn_deploy = ttk.Button(btn_row, text="Deploy", command=run_deploy)
    btn_deploy.pack(side="left", padx=2)
    create_tooltip(btn_deploy, "Compress the built distribution into a portable binary archive")

    btn_release = ttk.Button(btn_row, text="Release", command=run_release)
    btn_release.pack(side="left", padx=2)
    create_tooltip(btn_release, "Git commit/push and create a GitHub Release with the portable binary")

    btn_cancel = ttk.Button(btn_row, text="Cancel", command=cancel_process, state='disabled')
    btn_cancel.pack(side="left", padx=2)
    create_tooltip(btn_cancel, "Cancel the currently running operation")

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