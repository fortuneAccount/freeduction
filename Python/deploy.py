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

# Variables to exclude from the deploy UI
EXCLUDED_TAGS = {
    "0",
    "1",
    "?&",
    "htmlinjection",
    "just after lauch &amp; just before exit",
    "keymappers",
    "monitors",
    '^"&?\\/',
    "^\\/",
    "assigned level",
    '"module", "exports"',
    "data-smoothie",
    "i",
    "r",
    "t",
    "user",
    "pre / post",
}


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
    # Filter out excluded tags (case-insensitive)
    excluded_lower = {tag.lower() for tag in EXCLUDED_TAGS}
    tags = {tag for tag in tags if tag.lower() not in excluded_lower}
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
    except Exception as e:
        print("Tkinter not available:", e)
        print("Use --apply or --init-ini instead.")
        sys.exit(1)

    tags = find_tags([README_SET, SITE_SET])
    cfg = load_ini(ini_path, tags)

    if not cfg.has_section("build"):
        cfg.add_section("build")

    root = tk.Tk()
    root.title("Deploy: tag editor & builder")

    frame = ttk.Frame(root, padding=10)
    frame.grid(row=0, column=0, sticky="nsew")

    vars: Dict[str, tk.StringVar] = {}

    def save_all(_=None):
        for k, sv in vars.items():
            cfg["values"][k] = sv.get()
        
        # Save build vars
        if 'onefile' in build_vars:
            cfg["build"]["onefile"] = str(build_vars['onefile'].get())
            cfg["build"]["dest"] = build_vars['dest'].get()
            cfg["build"]["workpath"] = build_vars['workpath'].get()
            cfg["build"]["commit_msg"] = build_vars['commit_msg'].get()
            cfg["build"]["skip_python"] = str(build_vars['skip_python'].get())
            cfg["build"]["skip_c"] = str(build_vars['skip_c'].get())
            cfg["build"]["skip_anattagen"] = str(build_vars['skip_anattagen'].get())
            
        save_ini(ini_path, cfg)
        apply_replacements({k: cfg["values"].get(k, "") for k in tags})

    # Build form
    for i, k in enumerate(tags):
        lbl = ttk.Label(frame, text=k)
        lbl.grid(row=i, column=0, sticky="w", padx=(0, 8), pady=4)
        sv = tk.StringVar(value=cfg["values"].get(k, ""))
        ent = ttk.Entry(frame, textvariable=sv, width=60)
        ent.grid(row=i, column=1, sticky="we", pady=4)
        vars[k] = sv

        if k == "VERSION":
            btn_inc = ttk.Button(frame, text="+", width=3, command=lambda s=sv: s.set(increment_version(s.get())))
            btn_inc.grid(row=i, column=2, padx=2)

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

    # --- Build Section ---
    last_row = len(tags)
    ttk.Separator(frame, orient='horizontal').grid(row=last_row, column=0, columnspan=2, sticky="ew", pady=15)
    
    lbl_build = ttk.Label(frame, text="Build Portable Binary", font=("", 10, "bold"))
    lbl_build.grid(row=last_row+1, column=0, columnspan=2, pady=(0, 5))
    
    build_vars = {
        'onefile': tk.BooleanVar(value=cfg.getboolean('build', 'onefile', fallback=False)),
        'dest': tk.StringVar(value=cfg.get('build', 'dest', fallback=str(Path("dist").absolute()))),
        'workpath': tk.StringVar(value=cfg.get('build', 'workpath', fallback=str(Path("build").absolute()))),
        'commit_msg': tk.StringVar(value=cfg.get('build', 'commit_msg', fallback="Update")),
        'skip_python': tk.BooleanVar(value=cfg.getboolean('build', 'skip_python', fallback=False)),
        'skip_c': tk.BooleanVar(value=cfg.getboolean('build', 'skip_c', fallback=False)),
        'skip_anattagen': tk.BooleanVar(value=cfg.getboolean('build', 'skip_anattagen', fallback=False))
    }
    
    ctl_frame = ttk.Frame(frame)
    ctl_frame.grid(row=last_row+2, column=0, columnspan=2, sticky="ew")
    
    ttk.Checkbutton(ctl_frame, text="Onefile", variable=build_vars['onefile']).pack(side="left", padx=5)
    ttk.Label(ctl_frame, text="Dest:").pack(side="left", padx=5)
    ttk.Entry(ctl_frame, textvariable=build_vars['dest']).pack(side="left", fill="x", expand=True)
    
    def browse_dest():
        d = filedialog.askdirectory()
        if d: build_vars['dest'].set(d)
    ttk.Button(ctl_frame, text="...", width=3, command=browse_dest).pack(side="left", padx=2)

    wp_frame = ttk.Frame(frame)
    wp_frame.grid(row=last_row+3, column=0, columnspan=2, sticky="ew")
    ttk.Label(wp_frame, text="Workpath:").pack(side="left", padx=5)
    ttk.Entry(wp_frame, textvariable=build_vars['workpath']).pack(side="left", fill="x", expand=True)
    def browse_workpath():
        d = filedialog.askdirectory()
        if d: build_vars['workpath'].set(d)
    ttk.Button(wp_frame, text="...", width=3, command=browse_workpath).pack(side="left", padx=2)

    git_frame = ttk.Frame(frame)
    git_frame.grid(row=last_row+4, column=0, columnspan=2, sticky="ew", pady=(5, 0))
    ttk.Label(git_frame, text="Commit Msg:").pack(side="left", padx=5)
    ttk.Entry(git_frame, textvariable=build_vars['commit_msg']).pack(side="left", fill="x", expand=True)

    skip_frame = ttk.Frame(frame)
    skip_frame.grid(row=last_row+5, column=0, columnspan=2, sticky="ew")
    ttk.Checkbutton(skip_frame, text="Skip Python Build", variable=build_vars['skip_python']).pack(side="left", padx=5)
    ttk.Checkbutton(skip_frame, text="Skip Anattagen Build", variable=build_vars['skip_anattagen']).pack(side="left", padx=5)
    ttk.Checkbutton(skip_frame, text="Skip C Launcher Build", variable=build_vars['skip_c']).pack(side="left", padx=5)
    
    from tkinter import scrolledtext
    
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
        
        _recursive_set_state(frame)
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

    def run_build():
        import threading
        import subprocess
        import platform
        import shutil
        
        onefile = build_vars['onefile'].get()
        dest = build_vars['dest'].get()
        workpath = build_vars['workpath'].get()
        skip_python = build_vars['skip_python'].get()
        skip_c = build_vars['skip_c'].get()
        skip_anattagen = build_vars['skip_anattagen'].get()
        
        def worker():
            set_ui_busy(True)
            proc_state['cancelled'] = False
            sep = ';' if platform.system() == 'Windows' else ':'
            script_dir = Path(__file__).parent.absolute()
            project_root = script_dir.parent if script_dir.name == "Python" else script_dir
            
            if skip_python and skip_c:
                log("Skipping all builds as requested.\n")
                set_ui_busy(False)
                return

            # 1. Main Application Build
            main_script = project_root / "Python" / "main.py"
            icon_path = project_root / "assets" / "Joystick.ico"
            
            cmd_main = [
                sys.executable, '-m', 'PyInstaller',
                str(main_script),
                '--name=anattagen',
                '--noconfirm',
                '--clean',
                '--windowed',
                f'--distpath={dest}',
                f'--workpath={workpath}',
                f'--add-data={project_root / "site"}{sep}site',
                f'--add-data={project_root / "assets"}{sep}assets',
            ]
            
            if platform.system() == 'Windows' and icon_path.exists():
                cmd_main.append(f'--icon={icon_path}')
            
            if onefile:
                cmd_main.append('--onefile')
            else:
                cmd_main.append('--onedir')
                
            if not skip_python:
                if not skip_anattagen:
                    log(f"Starting Main Build (anattagen)...\n")
                    if not run_cmd_sequence([cmd_main], cwd=project_root):
                        set_ui_busy(False)
                        proc_state['proc'] = None
                        return
                else:
                    log("Skipping Main Build (anattagen).\n")

                # 2. Launcher Build
                if proc_state['cancelled']:
                    set_ui_busy(False)
                    return

                launcher_script = project_root / "Python" / "Launcher.py"
                cmd_launcher = [
                    sys.executable, '-m', 'PyInstaller',
                    str(launcher_script),
                    '--name=Launcher',
                    '--noconfirm',
                    '--clean',
                    '--windowed',
                    '--onefile',
                    f'--distpath={dest}',
                    f'--workpath={workpath}',
                ]
                
                if platform.system() == 'Windows' and icon_path.exists():
                    cmd_launcher.append(f'--icon={icon_path}')

                log(f"\nStarting Launcher Build...\n")
                if not run_cmd_sequence([cmd_launcher], cwd=project_root):
                    set_ui_busy(False)
                    proc_state['proc'] = None
                    return

                # 3. Copy Launcher
                try:
                    src = Path(dest) / "Launcher.exe"
                    dst_dir = project_root / "bin"
                    dst = dst_dir / "Launcher.python.exe"
                    
                    if src.exists():
                        dst_dir.mkdir(exist_ok=True)
                        shutil.copy2(src, dst)
                        log(f"\nCopied Launcher.exe to {dst}\n")
                    else:
                        log(f"\nError: Launcher.exe not found in {dest}\n")
                except Exception as e:
                    log(f"\nError copying launcher: {e}\n")

            # 4. Compile C Launcher
            if skip_c:
                log("Skipping C Launcher Build.\n")
                set_ui_busy(False)
                proc_state['proc'] = None
                return

            if proc_state['cancelled']:
                set_ui_busy(False)
                return

            log(f"\nStarting C Launcher Build...\n")
            launcher_src_dir = project_root / "assets" / "launcher"
            
            if platform.system() == 'Windows':
                build_script = launcher_src_dir / "Build.bat"
                cmd_c_build = ["cmd", "/c", str(build_script)]
            else:
                build_script = launcher_src_dir / "build.sh"
                cmd_c_build = ["sh", str(build_script), "--linux"]

            if build_script.exists():
                if run_cmd_sequence([cmd_c_build], cwd=launcher_src_dir):
                    log("C Launcher Build Completed.\n")
            else:
                log(f"Build script not found: {build_script}\n")

            log("Build Sequence Completed Successfully.\n")
            set_ui_busy(False)
            proc_state['proc'] = None

        open_log_window("Build Log")
        threading.Thread(target=worker, daemon=True).start()

    def run_git():
        import threading
        
        # Save and apply replacements before pushing
        save_all()
        
        msg = build_vars['commit_msg'].get()
        version = vars.get('VERSION', tk.StringVar(value="")).get()
        
        def worker():
            set_ui_busy(True)
            proc_state['cancelled'] = False
            
            # Check GitHub version
            if version:
                log(f"Checking if version {version} exists on GitHub...\n")
                try:
                    check_cmd = ["gh", "release", "view", version]
                    proc = subprocess.run(check_cmd, capture_output=True, text=True)
                    
                    if proc.returncode == 0:
                        log(f"Version {version} already exists.\n")
                        
                        def show_error_and_increment():
                            messagebox.showerror("Version Conflict", f"Version {version} already exists on GitHub.\nAuto-incrementing version.")
                            new_ver = increment_version(version)
                            if 'VERSION' in vars:
                                vars['VERSION'].set(new_ver)
                                save_all()
                            log(f"Version auto-incremented to {new_ver}.\n")
                        
                        root.after(0, show_error_and_increment)
                        set_ui_busy(False)
                        return
                except FileNotFoundError:
                    log("GH CLI not found, skipping version check.\n")
                except Exception as e:
                    log(f"Version check failed: {e}\n")

            commands = [
                ["git", "add", "."],
                ["git", "commit", "-m", msg],
                ["git", "push", "-f", "-u", "origin", "main"]
            ]
            
            log(f"\nStarting Git Push sequence...\n")
            if run_cmd_sequence(commands, cwd=Path.cwd()):
                log("Git sequence completed successfully.\n")
            
            set_ui_busy(False)
            proc_state['proc'] = None
            
        open_log_window("Git Push Log")
        threading.Thread(target=worker, daemon=True).start()

    def run_release():
        import threading
        import subprocess
        import shutil
        
        version = vars.get('VERSION', tk.StringVar(value="")).get()
        git_user = vars.get('GITUSER', tk.StringVar(value="")).get()
        rj_proj = vars.get('RJ_PROJ', tk.StringVar(value="")).get()
        dest_dir = Path(build_vars['dest'].get())
        msg = build_vars['commit_msg'].get()
        
        def worker():
            set_ui_busy(True)
            proc_state['cancelled'] = False
            log("\nStarting Release sequence...\n")
            
            # 0. Calculate SHA1 of Executable (Pre-compression)
            if proc_state['cancelled']: 
                set_ui_busy(False)
                return

            log("Calculating SHA1 of executable...\n")
            exe_name = "anattagen.exe" if platform.system() == "Windows" else "anattagen"
            exe_path = None
            for root, dirs, files in os.walk(dest_dir):
                if exe_name in files:
                    exe_path = Path(root) / exe_name
                    break
            
            sha1_hash = ""
            if exe_path and exe_path.exists():
                log(f"Found executable: {exe_path}\n")
                sha1 = hashlib.sha1()
                with open(exe_path, 'rb') as f:
                    while True:
                        data = f.read(65536)
                        if not data: break
                        sha1.update(data)
                sha1_hash = sha1.hexdigest()
                log(f"Executable SHA1: {sha1_hash}\n")
            else:
                log(f"Executable {exe_name} not found in {dest_dir}. Skipping SHA1.\n")
            
            # 1. Compress
            if proc_state['cancelled']: 
                set_ui_busy(False)
                return

            archive_name = "portable.7z"
            archive_path = Path.cwd() / archive_name
            
            # Find 7z.exe
            script_dir = Path(__file__).parent.absolute()
            project_root = script_dir.parent if script_dir.name == "Python" else script_dir
            seven_z = project_root / "bin" / "7z.exe"
            
            if seven_z.exists() and dest_dir.exists():
                log(f"Compressing {dest_dir} to {archive_name}...\n")
                # Remove existing
                if archive_path.exists():
                    archive_path.unlink()
                    
                cmd = [str(seven_z), "a", str(archive_path), f"{dest_dir}\\*"]
                try:
                    # Use Popen to allow cancellation
                    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    proc_state['proc'] = proc
                    proc.wait()
                    if proc.returncode != 0: raise Exception("7z returned non-zero")
                    log("Compression complete.\n")
                except Exception as e:
                    log(f"Compression failed: {e}\n")
                    set_ui_busy(False)
                    return
            else:
                log("7z.exe or dist directory not found.\n")
                set_ui_busy(False)
                return

            # 2. Calculate Size
            if proc_state['cancelled']:
                set_ui_busy(False)
                return
            
            size_mb = os.path.getsize(archive_path) / (1024 * 1024)
            
            # 3. Update GUI vars (thread-safe update)
            def update_ui():
                if 'RSHA1' in vars and sha1_hash: vars['RSHA1'].set(sha1_hash)
                if 'RSIZE' in vars: vars['RSIZE'].set(f"{size_mb:.2f}")
                if 'PORTABLE' in vars and git_user and rj_proj and version:
                    url = f"https://github.com/{git_user}/{rj_proj}/releases/download/Portable/{archive_name}"
                    vars['PORTABLE'].set(url)
                save_all() # Save INI and apply replacements
            root.after(0, update_ui)
            
            # 4. Git Push & Release
            # We wait a bit for UI update to save files
            import time
            time.sleep(1)
            
            # Trigger existing git push logic
            if proc_state['cancelled']: 
                set_ui_busy(False)
                return

            commands = [
                ["git", "add", "."],
                ["git", "commit", "-m", msg],
                ["git", "push", "-f", "-u", "origin", "main"]
            ]
            if not run_cmd_sequence(commands, cwd=Path.cwd()):
                set_ui_busy(False)
                return
            
            log("Replacing GitHub Release...\n")
            try:
                if proc_state['cancelled']: raise Exception("Cancelled")
                
                # Check if release exists
                check_cmd = ["gh", "release", "view", version]
                check_proc = subprocess.run(check_cmd, cwd=str(Path.cwd()), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                if check_proc.returncode == 0:
                    log(f"Release {version} exists. Deleting...\n")
                    subprocess.run(["gh", "release", "delete", version, "-y"], cwd=str(Path.cwd()), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                else:
                    log(f"Release {version} does not exist. Creating new...\n")
                
                # Create new release
                subprocess.run(["gh", "release", "create", version, str(archive_path), "--title", version, "--notes", "Automated release"], cwd=str(Path.cwd()), check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                log(f"Release {version} uploaded successfully.\n")
                
                # Auto-increment version
                new_ver = increment_version(version)
                if new_ver != version:
                    def update_ver():
                        if 'VERSION' in vars:
                            vars['VERSION'].set(new_ver)
                            save_all()
                            log(f"Version auto-incremented to {new_ver}\n")
                    root.after(0, update_ver)
            except FileNotFoundError:
                log("GH CLI not found. Skipping upload.\n")
            except Exception as e:
                log(f"Release upload failed: {e}\n")
            finally:
                set_ui_busy(False)
                proc_state['proc'] = None

        open_log_window("Release Log")
        threading.Thread(target=worker, daemon=True).start()

    # Consolidated Button Row
    btn_row = ttk.Frame(frame, padding=(0, 10))
    btn_row.grid(row=last_row+6, column=0, columnspan=2, sticky="ew")
    
    ttk.Button(btn_row, text="Apply & Save", command=save_all).pack(side="left", padx=5)
    ttk.Button(btn_row, text="Compile", command=run_build).pack(side="left", padx=5)
    ttk.Button(btn_row, text="Compress & Release", command=run_release).pack(side="left", padx=5)
    
    btn_cancel = ttk.Button(btn_row, text="Cancel", command=cancel_process, state='disabled')
    btn_cancel.pack(side="left", padx=5)
    
    ttk.Button(btn_row, text="Push to GitHub", command=run_git).pack(side="right", padx=5)

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
