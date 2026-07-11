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
_OUT_README = Path("README.md")
_OUT_INDEX = Path("site") / "index.html"
_REPOS_SET = Path("assets") / "repos.set"


_REPR_PATTERN = re.compile(r"<[A-Za-z0-9_.]+ object at 0x[0-9a-fA-F]+>")


def _clean_tag_value(val: str) -> str:
    """Return *val* if it looks like a real string, else empty string.

    Strips values that are ``repr()`` dumps of PyQt widgets or other
    Python objects – these are never valid tag values.
    """
    if not val:
        return ""
    if _REPR_PATTERN.search(val):
        return ""
    return val


def _load_repos_global() -> Dict[str, str]:
    """Return key/value pairs from the ``[GLOBAL]`` section of ``repos.set``.

    Falls back to an empty dict when the file or section is missing.
    """
    if not _REPOS_SET.exists():
        return {}
    cfg = configparser.ConfigParser()
    cfg.read(_REPOS_SET, encoding="utf-8")
    if "GLOBAL" not in cfg:
        return {}
    return {k: v.strip() for k, v in cfg["GLOBAL"].items()}

def read_file(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def find_tags_in_text(text: str) -> Set[str]:
    tokens = re.findall(r"\{\{([^\}]+)\}\}", text)
    return set(token.strip() for token in tokens)


def find_tags(files: List[Path]) -> List[str]:
    tags: Set[str] = set()
    for p in files:
        tags.update(find_tags_in_text(read_file(p)))
    return sorted(tags)


def load_ini(path: Path, keys: List[str]) -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    if path.exists():
        cfg.read(path, encoding="utf-8")
    if "values" not in cfg:
        cfg["values"] = {}

    repos_global = _load_repos_global()

    for k in keys:
        if k in cfg["values"]:
            cfg["values"][k] = _clean_tag_value(cfg["values"][k])
        else:
            cfg["values"][k] = ""
        if not cfg["values"][k] and k in repos_global:
            cfg["values"][k] = _clean_tag_value(repos_global[k])
    return cfg


def save_ini(path: Path, cfg: configparser.ConfigParser) -> None:
    with path.open("w", encoding="utf-8") as f:
        cfg.write(f)


def apply_replacements(tag_values: Dict[str, str]) -> None:
    readme_text = read_file(README_SET)
    index_text = read_file(SITE_SET)
    for k, v in tag_values.items():
        if v:
            readme_text = readme_text.replace(f"{{{{{k}}}}}", v)
            index_text = index_text.replace(f"{{{{{k}}}}}", v)
    _OUT_README.write_text(readme_text, encoding="utf-8")
    _OUT_INDEX.parent.mkdir(parents=True, exist_ok=True)
    _OUT_INDEX.write_text(index_text, encoding="utf-8")


def apply_repos_replacements(tag_values: Dict[str, str]) -> None:
    """Replace ``{{TAG}}`` variables in ``repos.set`` and overwrite the file.

    Only tags with non-empty values are replaced; unresolved tags are
    left as ``{{TAG}}`` in the output.
    """
    repos_text = read_file(_REPOS_SET)
    if not repos_text:
        return
    for k, v in tag_values.items():
        if v:
            repos_text = repos_text.replace(f"{{{{{k}}}}}", v)
    _REPOS_SET.write_text(repos_text, encoding="utf-8")


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
    tags = find_tags([README_SET, SITE_SET])
    tag_values = {k: values.get(k, "") for k in tags}
    apply_replacements(tag_values)
    apply_repos_replacements(tag_values)
    print(f"Wrote {_OUT_README}, {_OUT_INDEX}, and {_REPOS_SET}")


# ======================================================================
#  PyQt6 GUI
# ======================================================================

def run_gui(ini_path: Path) -> None:
    try:
        from PyQt6.QtWidgets import (
            QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
            QScrollArea, QLabel, QLineEdit, QPushButton, QCheckBox,
            QRadioButton, QGroupBox, QFormLayout, QTextEdit, QComboBox,
            QFileDialog, QMessageBox, QButtonGroup, QSizePolicy, QSplitter,
            QGridLayout,
        )
        from PyQt6.QtCore import Qt, pyqtSignal, QObject, QThread
        from PyQt6.QtGui import QFont, QTextCursor
    except Exception as e:
        print("PyQt6 not available:", e)
        print("Use --apply or --init-ini instead.")
        sys.exit(1)

    setup_deploy_logging()

    tags = find_tags([README_SET, SITE_SET])
    cfg = load_ini(ini_path, tags)
    if not cfg.has_section("build"):
        cfg.add_section("build")
    if not cfg.has_section("launcher_build"):
        cfg.add_section("launcher_build")

    _script_dir = Path(__file__).parent.absolute()
    _project_root = _script_dir.parent if _script_dir.name.lower() == "python" else _script_dir
    _default_dest = str(Path.home() / "Desktop")
    _default_workpath = str(get_writable_dir("build", _project_root))

    # ------------------------------------------------------------------ #
    #  DeployWindow                                                       #
    # ------------------------------------------------------------------ #

    class DeployWindow(QMainWindow):
        log_signal = pyqtSignal(str)
        set_busy_signal = pyqtSignal(bool)

        def __init__(self):
            super().__init__()
            self.setWindowTitle("Deploy: tag editor & builder")
            self.setMinimumSize(800, 500)
            self.resize(900, 600)
            self.setFont(QFont("Segoe UI", 9))

            self.tag_vars: Dict[str, str] = {}
            self.tag_widgets: Dict[str, tuple] = {}
            self.log_lines: List[str] = []
            self.proc = None
            self.cancelled = False

            central = QWidget()
            self.setCentralWidget(central)
            root_layout = QVBoxLayout(central)
            root_layout.setContentsMargins(6, 6, 6, 6)
            root_layout.setSpacing(4)

            splitter = QSplitter(Qt.Orientation.Vertical)
            root_layout.addWidget(splitter)

            # --- Tags (scrollable) ---
            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll_widget = QWidget()
            self.tags_layout = QVBoxLayout(scroll_widget)
            self.tags_layout.setContentsMargins(0, 0, 0, 0)
            for i, k in enumerate(tags):
                row = QHBoxLayout()
                lbl = QLabel(k)
                lbl.setMinimumWidth(160)
                row.addWidget(lbl)
                ent = QLineEdit(cfg["values"].get(k, ""))
                ent.setMinimumWidth(200)
                ent.textChanged.connect(self._make_tag_callback(k))
                row.addWidget(ent, 1)
                self.tag_vars[k] = _clean_tag_value(ent.text())
                self.tag_widgets[k] = (lbl, ent)
                if k == "VERSION":
                    btn = QPushButton("+")
                    btn.setFixedWidth(28)
                    btn.clicked.connect(self._make_inc_version(ent))
                    row.addWidget(btn)
                self.tags_layout.addLayout(row)
            self.tags_layout.addStretch()
            scroll.setWidget(scroll_widget)
            splitter.addWidget(scroll)

            # --- Build Controls ---
            build_group = QGroupBox("Build Controls")
            build_layout = QGridLayout(build_group)
            build_layout.setColumnStretch(1, 1)

            row = 0

            # Dest
            build_layout.addWidget(QLabel("Dest:"), row, 0)
            self.dest_edit = QLineEdit(cfg.get("build", "dest", fallback=_default_dest))
            build_layout.addWidget(self.dest_edit, row, 1)
            btn = QPushButton("...")
            btn.setFixedWidth(28)
            btn.clicked.connect(self._browse_dest)
            build_layout.addWidget(btn, row, 2)

            row += 1

            # Workpath
            build_layout.addWidget(QLabel("Workpath:"), row, 0)
            self.workpath_edit = QLineEdit(cfg.get("build", "workpath", fallback=_default_workpath))
            build_layout.addWidget(self.workpath_edit, row, 1)
            btn = QPushButton("...")
            btn.setFixedWidth(28)
            btn.clicked.connect(self._browse_workpath)
            build_layout.addWidget(btn, row, 2)

            row += 1

            # Commit message
            build_layout.addWidget(QLabel("Commit:"), row, 0)
            self.commit_edit = QLineEdit(cfg.get("build", "commit_msg", fallback="Update"))
            build_layout.addWidget(self.commit_edit, row, 1)

            row += 1

            # Skip checkboxes
            skip_layout = QHBoxLayout()
            self.skip_python_cb = QCheckBox("Skip Python")
            self.skip_python_cb.setChecked(cfg.getboolean("build", "skip_python", fallback=False))
            skip_layout.addWidget(self.skip_python_cb)
            self.skip_app_cb = QCheckBox("Skip App")
            self.skip_app_cb.setChecked(cfg.getboolean("build", "skip_application", fallback=False))
            skip_layout.addWidget(self.skip_app_cb)
            self.skip_c_cb = QCheckBox("Skip C")
            self.skip_c_cb.setChecked(cfg.getboolean("build", "skip_c", fallback=False))
            skip_layout.addWidget(self.skip_c_cb)
            self.clean_cb = QCheckBox("Clean Build")
            self.clean_cb.setChecked(cfg.getboolean("build", "clean_build", fallback=True))
            skip_layout.addWidget(self.clean_cb)
            skip_layout.addStretch()
            build_layout.addLayout(skip_layout, row, 0, 1, 3)

            row += 1

            # Launcher options
            launcher_group = QGroupBox("Launcher Options")
            lg_layout = QHBoxLayout(launcher_group)

            self.default_launcher_group = QButtonGroup(self)
            self.radio_c = QRadioButton("C Launcher")
            self.radio_c.setChecked(cfg.get("build", "default_launcher", fallback="C") == "C")
            self.default_launcher_group.addButton(self.radio_c)
            lg_layout.addWidget(self.radio_c)
            self.radio_py = QRadioButton("Python Launcher")
            self.radio_py.setChecked(cfg.get("build", "default_launcher", fallback="C") == "Python")
            self.default_launcher_group.addButton(self.radio_py)
            lg_layout.addWidget(self.radio_py)

            lg_layout.addWidget(QLabel("  Preset:"))
            self.preset_combo = QComboBox()
            self.preset_combo.addItems(["minimal", "standard"])
            idx = self.preset_combo.findText(cfg.get("launcher_build", "preset", fallback="standard"))
            if idx >= 0:
                self.preset_combo.setCurrentIndex(idx)
            lg_layout.addWidget(self.preset_combo)
            lg_layout.addStretch()

            build_layout.addWidget(launcher_group, row, 0, 1, 3)

            row += 1

            # Action buttons
            btn_layout = QHBoxLayout()
            for text, slot in [
                ("Deps", self._run_check_deps),
                ("Audit", self._run_audit),
                ("Compile", self._run_compile),
                ("Apply", self._run_apply),
                ("Deploy", self._run_deploy),
                ("Release", self._run_release),
            ]:
                b = QPushButton(text)
                b.clicked.connect(slot)
                btn_layout.addWidget(b)
            self.cancel_btn = QPushButton("Cancel")
            self.cancel_btn.setEnabled(False)
            self.cancel_btn.clicked.connect(self._cancel)
            btn_layout.addWidget(self.cancel_btn)
            build_layout.addLayout(btn_layout, row, 0, 1, 3)

            row += 1

            # Deps status
            self.dep_label = QLabel("Deps: unknown")
            self.dep_label.setFont(QFont("Segoe UI", 8))
            build_layout.addWidget(self.dep_label, row, 0, 1, 3)

            splitter.addWidget(build_group)
            splitter.setStretchFactor(0, 3)
            splitter.setStretchFactor(1, 1)

            self.log_signal.connect(self._append_log)
            self.set_busy_signal.connect(self._set_busy)

            self._apply_initial_rdate()

        # ---------- tag helpers ----------

        def _make_tag_callback(self, key):
            def cb(text):
                self.tag_vars[key] = text
                self._save_all()
            return cb

        def _make_inc_version(self, line_edit):
            def cb():
                line_edit.setText(increment_version(line_edit.text()))
            return cb

        def _apply_initial_rdate(self):
            if "RDATE" in self.tag_vars:
                self.tag_vars["RDATE"] = datetime.datetime.now().strftime("%m-%d-%Y")
                w = self.tag_widgets.get("RDATE")
                if w:
                    w[1].setText(self.tag_vars["RDATE"])

        # ---------- save ----------

        def _save_all(self):
            for k in self.tag_vars:
                val = self.tag_vars[k]
                if not isinstance(val, str):
                    val = str(val) if val else ""
                cfg["values"][k] = val
            cfg["build"]["dest"] = self.dest_edit.text()
            cfg["build"]["workpath"] = self.workpath_edit.text()
            cfg["build"]["commit_msg"] = self.commit_edit.text()
            cfg["build"]["skip_python"] = str(self.skip_python_cb.isChecked())
            cfg["build"]["skip_c"] = str(self.skip_c_cb.isChecked())
            cfg["build"]["skip_application"] = str(self.skip_app_cb.isChecked())
            cfg["build"]["clean_build"] = str(self.clean_cb.isChecked())
            cfg["build"]["default_launcher"] = "C" if self.radio_c.isChecked() else "Python"
            cfg["launcher_build"]["preset"] = self.preset_combo.currentText()
            save_ini(ini_path, cfg)
            apply_replacements({k: cfg["values"].get(k, "") for k in tags})

        # ---------- log ----------

        def _append_log(self, msg):
            logging.info(msg.rstrip("\n"))
            self.log_lines.append(msg)
            if hasattr(self, "_log_text") and self._log_text is not None:
                self._log_text.moveCursor(QTextCursor.MoveOperation.End)
                self._log_text.insertPlainText(msg)
                self._log_text.moveCursor(QTextCursor.MoveOperation.End)
                self._log_text.ensureCursorVisible()
                self._log_text.viewport().update()

        def _open_log(self, title="Process Log"):
            if hasattr(self, "_log_text") and self._log_text is not None:
                self._log_win.show()
                self._log_win.raise_()
                return
            self._log_win = QMainWindow(self)
            self._log_win.setWindowTitle(title)
            self._log_win.resize(700, 500)
            self._log_text = QTextEdit()
            self._log_text.setReadOnly(True)
            self._log_text.setFont(QFont("Consolas", 9))
            self._log_win.setCentralWidget(self._log_text)
            self._log_win.show()

        def _reset_log(self):
            self.log_lines = []
            if hasattr(self, "_log_win") and self._log_win is not None:
                self._log_win.close()
                self._log_win.deleteLater()
            self._log_text = None
            self._log_win = None

        # ---------- busy ----------

        def _set_busy(self, busy):
            self.cancel_btn.setEnabled(busy)
            for w in self.centralWidget().findChildren(QPushButton):
                if w != self.cancel_btn:
                    w.setEnabled(not busy)
            for w in self.centralWidget().findChildren(QLineEdit):
                w.setEnabled(not busy)
            for w in self.centralWidget().findChildren(QCheckBox):
                w.setEnabled(not busy)
            for w in self.centralWidget().findChildren(QRadioButton):
                w.setEnabled(not busy)
            for w in self.centralWidget().findChildren(QComboBox):
                w.setEnabled(not busy)

        def _cancel(self):
            self.cancelled = True
            if self.proc:
                try:
                    self.proc.kill()
                except Exception:
                    pass
            self._append_log("\n>>> Operation Cancelled by User <<<\n")

        # ---------- file dialogs ----------

        def _browse_dest(self):
            d = QFileDialog.getExistingDirectory(self, "Output Directory", self.dest_edit.text())
            if d:
                self.dest_edit.setText(d)

        def _browse_workpath(self):
            d = QFileDialog.getExistingDirectory(self, "Work Directory", self.workpath_edit.text())
            if d:
                self.workpath_edit.setText(d)

        # ---------- command runner ----------

        def _run_cmd_sequence(self, commands, cwd=None):
            for cmd in commands:
                if self.cancelled:
                    return False
                self.log_signal.emit(f"> {' '.join(cmd)}\n")
                try:
                    process = subprocess.Popen(
                        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                        text=True, bufsize=0, encoding="utf-8", errors="replace",
                        cwd=str(cwd) if cwd else None,
                        env={**os.environ, "PYTHONUNBUFFERED": "1"},
                    )
                    self.proc = process
                    for line in process.stdout:
                        if line:
                            self.log_signal.emit(line if line.endswith('\n') else line + '\n')
                    process.wait()
                    if process.returncode != 0:
                        self.log_signal.emit(f"Command failed with code {process.returncode}\n")
                        return False
                except Exception as e:
                    self.log_signal.emit(f"Error executing {cmd[0]}: {e}\n")
                    return False
            return True

        # ------------------------------------------------------------------ #
        #  AUDIT                                                              #
        # ------------------------------------------------------------------ #
        def _run_audit(self):
            """Run PyInstaller in onedir mode to analyze bundled modules."""
            import threading

            self._reset_log()
            self._open_log("Audit Log")

            def worker():
                try:
                    self.log_signal.emit("\n" + "="*60 + "\n")
                    self.log_signal.emit("RUNNING AUDIT: Analyzing build dependencies...\n")
                    self.log_signal.emit("="*60 + "\n\n")

                    project_root = Path(__file__).resolve().parents[1]
                    script_dir = project_root / "Python"
                    main_script = script_dir / "main.py"
                    workpath = self.workpath_edit.text() or str(Path.home() / "AppData" / "Local" / "Temp" / "build")
                    
                    # Create audit directory
                    audit_dir = Path(workpath) / "audit"
                    audit_dir.mkdir(parents=True, exist_ok=True)
                    dist_dir = audit_dir / "dist_audit"

                    self.log_signal.emit("Building in --onedir mode to analyze dependencies...\n")
                    self.log_signal.emit("(This creates a folder with all included modules)\n\n")

                    cmd_audit = [
                        sys.executable, "-m", "PyInstaller", str(main_script),
                        "--onedir", "--noconfirm", "--clean",
                        f"--specpath={audit_dir}",
                        f"--distpath={dist_dir}",
                        f"--workpath={workpath}/audit_work",
                        "--name=freeduction_audit",
                        "--exclude", "PySide6",
                        "--exclude", "PySide2",
                        "--exclude", "PyQt5",
                    ]

                    if not self._run_cmd_sequence([cmd_audit], cwd=project_root):
                        self.set_busy_signal.emit(False)
                        self.proc = None
                        return

                    self.log_signal.emit("\n✓ Audit complete!\n\n")
                    spec_file = audit_dir / "freeduction_audit.spec"
                    dist_folder = dist_dir / "freeduction_audit"
                    
                    if spec_file.exists():
                        self.log_signal.emit(f"Spec file: {spec_file}\n")
                        self.log_signal.emit(f"Distribution folder: {dist_folder}\n\n")
                        
                        # Try to analyze folder size
                        if dist_folder.exists():
                            total_size = sum(f.stat().st_size for f in dist_folder.rglob('*') if f.is_file())
                            size_mb = total_size / (1024 * 1024)
                            self.log_signal.emit(f"Total bundled size: {size_mb:.1f} MB\n\n")
                        
                        self.log_signal.emit("To reduce build size, consider:\n")
                        self.log_signal.emit("  1. Review modules in the spec file under 'modules' list\n")
                        self.log_signal.emit("  2. Remove unused packages from requirements.txt\n")
                        self.log_signal.emit("  3. Add '--exclude' flags for heavy packages:\n")
                        self.log_signal.emit("     --exclude numpy --exclude scipy --exclude matplotlib\n")
                        self.log_signal.emit("  4. Check warn-freeduction.txt for modules that failed to load\n\n")
                    
                except Exception as e:
                    self.log_signal.emit(f"\nAudit failed: {e}\n")
                finally:
                    self.set_busy_signal.emit(False)
                    self.proc = None

            self.set_busy_signal.emit(True)
            threading.Thread(target=worker, daemon=True).start()

        # ------------------------------------------------------------------ #
        #  DEPS                                                               #
        # ------------------------------------------------------------------ #
        def _run_check_deps(self):
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
            self.dep_label.setText(" | ".join(parts))
            self._append_log(f"[Deps] Python packages missing: {missing_py}\n")
            self._append_log(f"[Deps] C compiler: {c_info}\n")
            self._append_log(f"[Deps] GitHub CLI: {gh_info}\n")
            if missing_py:
                reply = QMessageBox.question(
                    self, "Install Dependencies",
                    f"Missing {len(missing_py)} Python packages.\nInstall them now?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply == QMessageBox.StandardButton.Yes:
                    if install_python_deps(missing_py):
                        self.dep_label.setText("Deps: installed")
                        self._append_log("[Deps] Python packages installed successfully.\n")
                    else:
                        self._append_log("[Deps] Failed to install Python packages.\n")

        # ------------------------------------------------------------------ #
        #  COMPILE                                                            #
        # ------------------------------------------------------------------ #
        def _run_compile(self):
            import threading

            self._save_all()
            self._reset_log()
            self._open_log("Compile Log")

            def worker():
                self.set_busy_signal.emit(True)
                self.cancelled = False
                self.log_signal.emit("\n>>> Starting Compile <<<\n")

                dest_dir = Path(self.dest_edit.text())
                workpath = self.workpath_edit.text()
                skip_python = self.skip_python_cb.isChecked()
                skip_c = self.skip_c_cb.isChecked()
                skip_app = self.skip_app_cb.isChecked()
                clean_build = self.clean_cb.isChecked()
                default_launcher = "C" if self.radio_c.isChecked() else "Python"
                launcher_preset = self.preset_combo.currentText()
                rj_proj = self.tag_vars.get("RJ_PROJ", "")
                # Extract just the project name if RJ_PROJ contains a URL
                if rj_proj and ("http://" in rj_proj or "https://" in rj_proj or "/" in rj_proj):
                    rj_proj = rj_proj.rstrip("/").split("/")[-1]

                sep = ";" if platform.system() == "Windows" else ":"
                script_dir = Path(__file__).parent.absolute()
                project_root = script_dir.parent if script_dir.name.lower() == "python" else script_dir
                launcher_src_dir = project_root / "assets" / "launcher"
                bin_dir = project_root / "bin"
                bin_dir.mkdir(exist_ok=True)

                # 0. Clean
                if clean_build:
                    self.log_signal.emit("Cleaning previous build artifacts...\n")
                    for d, label in [(dest_dir, "destination"), (Path(workpath), "work")]:
                        if d.exists() and d.is_dir():
                            self.log_signal.emit(f"  Removing {label} directory: {d}\n")
                            try:
                                shutil.rmtree(d)
                            except Exception as e:
                                self.log_signal.emit(f"  Could not remove {d}: {e}\n")
                    archive_name_clean = f"{rj_proj}.7z" if rj_proj else "portable.7z"
                    old_archive = dest_dir / archive_name_clean
                    if old_archive.exists():
                        try:
                            old_archive.unlink()
                        except Exception as e:
                            self.log_signal.emit(f"  Could not remove archive: {e}\n")
                    old_orig = dest_dir / "portable.orig"
                    if old_orig.exists():
                        try:
                            old_orig.unlink()
                        except Exception as e:
                            self.log_signal.emit(f"  Could not remove backup: {e}\n")
                    self.log_signal.emit("Clean complete.\n")

                if self.cancelled:
                    self.set_busy_signal.emit(False)
                    return

                # 1. Python Launcher
                py_launcher_final = bin_dir / "Launcher.py.exe"
                if not skip_python:
                    build_script_py = project_root / "assets" / "launcher" / "Build_PyLauncher.py"
                    if build_script_py.exists():
                        self.log_signal.emit(f"Building Python Launcher (preset: {launcher_preset})...\n")
                        cmd_launcher = [sys.executable, str(build_script_py), launcher_preset]
                        if not self._run_cmd_sequence([cmd_launcher], cwd=project_root):
                            self.set_busy_signal.emit(False)
                            self.proc = None
                            return
                        preset_name = {
                            "minimal": "Launcher_minimal",
                            "standard": "Launcher_standard",
                        }.get(launcher_preset, "Launcher_standard")
                        src_py = Path(workpath) / "py_launcher_dist" / f"{preset_name}.exe"
                        if src_py.exists():
                            if py_launcher_final.exists():
                                py_launcher_final.unlink()
                            shutil.copy2(str(src_py), str(py_launcher_final))
                            self.log_signal.emit(f"  Python Launcher -> {py_launcher_final}\n")
                        else:
                            self.log_signal.emit(f"  Error: built file not found: {src_py}\n")
                    else:
                        self.log_signal.emit("  Error: Build_PyLauncher.py not found.\n")
                else:
                    self.log_signal.emit("Skipping Python Launcher build.\n")

                if self.cancelled:
                    self.set_busy_signal.emit(False)
                    return

                # 2. C Launcher
                c_launcher_final = bin_dir / "Launcher.c.exe"
                if not skip_c:
                    self.log_signal.emit("Building C Launcher...\n")
                    if platform.system() == "Windows":
                        build_script_c = launcher_src_dir / "Build.bat"
                        cmd_c = ["cmd", "/c", str(build_script_c)]
                    else:
                        build_script_c = launcher_src_dir / "build.sh"
                        cmd_c = ["sh", str(build_script_c), "--linux"]
                    if build_script_c.exists():
                        if self._run_cmd_sequence([cmd_c], cwd=launcher_src_dir):
                            src_c = launcher_src_dir / "Launcher.exe"
                            if src_c.exists():
                                if c_launcher_final.exists():
                                    c_launcher_final.unlink()
                                shutil.move(str(src_c), str(c_launcher_final))
                                self.log_signal.emit(f"  C Launcher -> {c_launcher_final}\n")
                            else:
                                self.log_signal.emit("  Error: Launcher.exe not found after C build.\n")
                        else:
                            self.log_signal.emit("C Launcher build failed. Halting.\n")
                            self.set_busy_signal.emit(False)
                            self.proc = None
                            return
                    else:
                        self.log_signal.emit(f"  Build script not found: {build_script_c}\n")
                else:
                    self.log_signal.emit("Skipping C Launcher build.\n")

                if self.cancelled:
                    self.set_busy_signal.emit(False)
                    return

                # 3. Main application
                if not skip_python and not skip_app:
                    self.log_signal.emit("Building main application...\n")
                    main_script = script_dir / "main.py"
                    icon_path = project_root / "assets" / "Joystick.ico"
                    cmd_main = [
                    sys.executable, "-m", "PyInstaller", str(main_script),
                    f"--name={rj_proj}", "--noconfirm", "--clean", "--windowed",
                    f"--distpath={self.dest_edit.text()}",
                    f"--workpath={workpath}",
                    f"--add-data={project_root / 'site'}{sep}site",
                    f"--add-data={project_root / 'assets'}{sep}assets",
                    "--onefile", "--noupx",
                    "--exclude", "PySide6",
                    "--exclude", "PySide2",
                    "--exclude", "PyQt5",
                    "--exclude", "numpy",
                    "--exclude", "scipy",
                    "--exclude", "matplotlib",
                    "--exclude", "pandas",
                    "--exclude", "nltk",
                    "--exclude", "pygame",
                    "--exclude", "screeninfo",
                    "--exclude", "winshell",
                    "--exclude", "setuptools",
                    "--exclude", "packaging",
                    "--exclude", "wheel",
                    "--exclude", "pwd",
                    "--exclude", "grp",
                    "--exclude", "posix",
                    "--exclude", "resource",
                    "--exclude", "fcntl",
                    "--exclude", "termios",
                    "--exclude", "curses",
                    "--exclude", "readline",
                    "--exclude", "cryptography",
                    "--exclude", "OpenSSL",
                    "--exclude", "brotli",
                    "--exclude", "socks",
                    "--exclude", "cchardet",
                    "--exclude", "lxml",
                    "--exclude", "html5lib",
                    "--exclude", "defusedxml",
                    "--exclude", "olefile",
                    "--exclude", "cffi",
                    "--exclude", "simplejson",
                    "--exclude", "sparse",
                    "--exclude", "cupy",
                    "--exclude", "cupyx",
                    "--exclude", "torch",
                    "--exclude", "jax",
                    "--exclude", "dask",
                    "--exclude", "ndonnx",
                    "--exclude", "uarray",
                    "--exclude", "Cython",
                    "--exclude", "pytest",
                    "--exclude", "sphinx",
                    "--exclude", "backports.zstd",
                    "--exclude", "win32com.gen_py",
                    "--exclude", "trove_classifiers",
                    "--exclude", "pyimod02_importers",
                    "--exclude", "cloudscraper",
                    "--exclude", "qdarktheme",
                    "--exclude", "qdarkstyle",
                    "--exclude", "qfluentwidgets",
                    "--exclude", "PyQt6Qlementine",
                    "--exclude", "Cryptodome",
                    "--exclude", "qframelesswindow",
                    "--exclude", "requests_toolbelt",
                    ]
                    if platform.system() == "Windows" and icon_path.exists():
                        cmd_main.append(f"--icon={icon_path}")
                    if not self._run_cmd_sequence([cmd_main], cwd=project_root):
                        self.set_busy_signal.emit(False)
                        self.proc = None
                        return
                else:
                    self.log_signal.emit("Skipping main application build.\n")

                if self.cancelled:
                    self.set_busy_signal.emit(False)
                    return

                # 4. Copy default launcher
                default_dst = bin_dir / "Launcher.exe"
                if default_dst.exists():
                    try:
                        default_dst.unlink()
                    except OSError as e:
                        self.log_signal.emit(f"  Could not remove old Launcher.exe: {e}\n")
                src_default = c_launcher_final if default_launcher == "C" else py_launcher_final
                label_default = "C" if default_launcher == "C" else "Python"
                if src_default.exists():
                    shutil.copy2(str(src_default), str(default_dst))
                    self.log_signal.emit(f"  Default Launcher ({label_default}) -> {default_dst}\n")
                else:
                    self.log_signal.emit(f"  Warning: chosen default launcher not found: {src_default}\n")

                self.log_signal.emit("\n>>> Compile complete <<<\n")
                self.set_busy_signal.emit(False)
                self.proc = None

            threading.Thread(target=worker, daemon=True).start()

        # ------------------------------------------------------------------ #
        #  APPLY                                                              #
        # ------------------------------------------------------------------ #
        def _run_apply(self):
            dest_dir = Path(self.dest_edit.text())
            rj_proj = self.tag_vars.get("RJ_PROJ", "")
            # Extract just the project name if RJ_PROJ contains a URL
            if rj_proj and ("http://" in rj_proj or "https://" in rj_proj or "/" in rj_proj):
                rj_proj = rj_proj.rstrip("/").split("/")[-1]
            archive_name = f"{rj_proj}.7z" if rj_proj else "portable.7z"
            archive_path = dest_dir / archive_name
            version = self.tag_vars.get("VERSION", "")
            git_user = self.tag_vars.get("GITUSER", "")

            if not archive_path.exists():
                QMessageBox.critical(self, "Apply", f"Archive not found:\n{archive_path}\n\nRun Compile + Deploy first.")
                return

            sha1 = hashlib.sha1()
            try:
                with open(archive_path, "rb") as f:
                    while chunk := f.read(65536):
                        sha1.update(chunk)
                sha1_hash = sha1.hexdigest()
            except OSError as e:
                QMessageBox.critical(self, "Apply", f"Could not read archive: {e}")
                return

            size_mb = os.path.getsize(archive_path) / (1024 * 1024)

            if "RSHA1" in self.tag_vars:
                self.tag_vars["RSHA1"] = sha1_hash
                w = self.tag_widgets.get("RSHA1")
                if w:
                    w[1].setText(sha1_hash)
            if "RSIZE" in self.tag_vars:
                self.tag_vars["RSIZE"] = f"{size_mb:.2f}"
                w = self.tag_widgets.get("RSIZE")
                if w:
                    w[1].setText(f"{size_mb:.2f}")
            if "PORTABLE" in self.tag_vars and git_user and rj_proj and version:
                url = f"https://github.com/{git_user}/{rj_proj}/releases/download/portable/{archive_name}"
                self.tag_vars["PORTABLE"] = url
                w = self.tag_widgets.get("PORTABLE")
                if w:
                    w[1].setText(url)
            if "RDATE" in self.tag_vars:
                self.tag_vars["RDATE"] = datetime.datetime.now().strftime("%m-%d-%Y")
                w = self.tag_widgets.get("RDATE")
                if w:
                    w[1].setText(self.tag_vars["RDATE"])

            new_ver = increment_version(version)
            if "VERSION" in self.tag_vars and new_ver != version:
                self.tag_vars["VERSION"] = new_ver
                w = self.tag_widgets.get("VERSION")
                if w:
                    w[1].setText(new_ver)

            for k in self.tag_vars:
                cfg["values"][k] = self.tag_vars[k]
            save_ini(ini_path, cfg)
            tag_vals = {k: cfg["values"].get(k, "") for k in tags}
            apply_replacements(tag_vals)
            apply_repos_replacements(tag_vals)

            QMessageBox.information(
                self, "Apply",
                f"Fields updated.\nSHA1: {sha1_hash}\nSize: {size_mb:.2f} MB\n"
                f"Version incremented to {new_ver}\nREADME.md, index.html, and repos.set written.",
            )

        # ------------------------------------------------------------------ #
        #  DEPLOY                                                             #
        # ------------------------------------------------------------------ #
        def _run_deploy(self):
            import threading

            dest_dir_str = self.dest_edit.text()
            dest_dir = Path(dest_dir_str)
            rj_proj = self.tag_vars.get("RJ_PROJ", "freeduction")
            # Extract just the project name if RJ_PROJ contains a URL
            if rj_proj and ("http://" in rj_proj or "https://" in rj_proj or "/" in rj_proj):
                rj_proj = rj_proj.rstrip("/").split("/")[-1]
            archive_name = f"{rj_proj}.7z" if rj_proj else "portable.7z"
            archive_path = dest_dir / archive_name
            seven_z = _project_root / "bin" / "7z.exe"

            if not seven_z.exists():
                QMessageBox.critical(self, "Deploy", f"7z.exe not found at:\n{seven_z}")
                return
            if not dest_dir.exists():
                QMessageBox.critical(self, "Deploy", f"Output directory not found:\n{dest_dir}")
                return

            self._reset_log()
            self._open_log("Deploy Log")

            def worker():
                self.set_busy_signal.emit(True)
                self.cancelled = False
                self.log_signal.emit("\n>>> Starting Deploy (compress) <<<\n")
                self.log_signal.emit(f"Destination: {dest_dir}\n")
                self.log_signal.emit(f"Archive: {archive_path}\n")

                if archive_path.exists():
                    self.log_signal.emit(f"Overwriting existing archive: {archive_path}\n")
                    try:
                        archive_path.unlink()
                    except Exception as e:
                        self.log_signal.emit(f"Could not remove old archive: {e}\n")

                sep = "\\" if platform.system() == "Windows" else "/"
                cmd_7z = [str(seven_z), "a", str(archive_path), f"{dest_dir_str}{sep}*"]
                if not self._run_cmd_sequence([cmd_7z]):
                    self.log_signal.emit("Compression failed.\n")
                    self.set_busy_signal.emit(False)
                    return

                self.log_signal.emit(f"Archive created: {archive_path}\n")

                sfx_module = _project_root / "bin" / "7zCon.sfx"
                sfx_output = dest_dir / f"{rj_proj}_portable.exe"
                if sfx_module.exists():
                    self.log_signal.emit("Building SFX portable executable...\n")
                    sfx_config = dest_dir / "sfx_config.txt"
                    try:
                        sfx_config.write_text(
                            f";!@Install@!UTF-8!\r\n"
                            f"InstallPath=\".\\\\{rj_proj}\\\\\"\r\n"
                            f";!@InstallEnd@!\r\n",
                            encoding="utf-8",
                        )
                        sfx_cmd = ["cmd", "/c", "copy", "/b",
                                   f"{sfx_module}+{sfx_config}+{archive_path}",
                                   str(sfx_output)]
                        result = subprocess.run(sfx_cmd, capture_output=True, timeout=30)
                        if result.returncode == 0:
                            self.log_signal.emit(f"  SFX portable: {sfx_output}\n")
                        else:
                            self.log_signal.emit(f"  SFX build failed (code {result.returncode})\n")
                    except Exception as e:
                        self.log_signal.emit(f"  SFX build error: {e}\n")
                    finally:
                        try:
                            os.remove(str(sfx_config))
                        except Exception:
                            pass
                else:
                    self.log_signal.emit(f"SFX module not found at {sfx_module}, skipping SFX build.\n")

                self.log_signal.emit("Portable archive ready\n")
                self.log_signal.emit("\n>>> Deploy complete <<<\n")
                self.set_busy_signal.emit(False)
                self.proc = None

            threading.Thread(target=worker, daemon=True).start()

        # ------------------------------------------------------------------ #
        #  RELEASE                                                            #
        # ------------------------------------------------------------------ #
        def _run_release(self):
            import threading

            self._save_all()

            version = self.tag_vars.get("VERSION", "")
            commit_msg = self.commit_edit.text()
            dest_dir = Path(self.dest_edit.text())
            rj_proj = self.tag_vars.get("RJ_PROJ", "freeduction")
            # Extract just the project name if RJ_PROJ contains a URL
            if rj_proj and ("http://" in rj_proj or "https://" in rj_proj or "/" in rj_proj):
                rj_proj = rj_proj.rstrip("/").split("/")[-1]
            archive_name = f"{rj_proj}.7z" if rj_proj else "portable.7z"
            archive_path = dest_dir / archive_name

            if not version:
                QMessageBox.critical(self, "Release", "VERSION field is empty.")
                return
            if not archive_path.exists():
                QMessageBox.critical(self, "Release",
                                     f"Archive not found:\n{archive_path}\nRun Deploy first.")
                return

            gh_ok, gh_info = check_gh_cli()
            if not gh_ok:
                reply = QMessageBox.question(
                    self, "GitHub CLI Missing",
                    f"GitHub CLI is {gh_info}.\n\n"
                    "The release workflow requires:\n"
                    "  1. 'gh' CLI installed\n"
                    "  2. 'gh auth login' completed\n"
                    "  3. A GitHub remote configured\n\n"
                    "Continue anyway (will likely fail)?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return

            self._reset_log()
            self._open_log("Release Log")

            def worker():
                self.set_busy_signal.emit(True)
                self.cancelled = False
                self.log_signal.emit("\n>>> Starting Release <<<\n")
                self.log_signal.emit(f"Release version: {version}\n")
                self.log_signal.emit(f"Archive: {archive_path}\n")
                self.log_signal.emit(f"gh CLI: {gh_info}\n")

                # Ensure the 'portable' release tag exists
                self.log_signal.emit(f"Checking if 'portable' release tag exists on GitHub...\n")
                portable_exists = False
                try:
                    proc = subprocess.run(
                        ["gh", "release", "view", "portable"],
                        capture_output=True, text=True,
                        cwd=str(_project_root), timeout=30,
                    )
                    portable_exists = proc.returncode == 0
                except FileNotFoundError:
                    self.log_signal.emit("GH CLI not found.\n")
                    self.set_busy_signal.emit(False)
                    return
                except subprocess.TimeoutExpired:
                    self.log_signal.emit("GitHub release check timed out.\n")
                except Exception as e:
                    self.log_signal.emit(f"Release check failed: {e}\n")

                if not portable_exists:
                    self.log_signal.emit("Creating 'portable' release tag...\n")
                    create_release_cmd = [
                        "gh", "release", "create", "portable",
                        "--title", "Portable Build",
                        "--notes", "Latest portable build (updated on each release)",
                    ]
                    if not self._run_cmd_sequence([create_release_cmd], cwd=_project_root):
                        self.log_signal.emit("Failed to create 'portable' release.\n")
                        self.set_busy_signal.emit(False)
                        return

                if self.cancelled:
                    self.set_busy_signal.emit(False)
                    return

                # Verify git remote
                self.log_signal.emit("Checking git remote configuration...\n")
                try:
                    rmt = subprocess.run(
                        ["git", "remote", "-v"], capture_output=True, text=True,
                        cwd=str(_project_root), timeout=15,
                    )
                    self.log_signal.emit(rmt.stdout or "(no remotes configured)\n")
                    if rmt.returncode != 0 or not rmt.stdout.strip():
                        self.log_signal.emit("ERROR: No git remote found.\n")
                        self.set_busy_signal.emit(False)
                        return
                except Exception as e:
                    self.log_signal.emit(f"Failed to check git remote: {e}\n")

                if self.cancelled:
                    self.set_busy_signal.emit(False)
                    return

                # Git commit and push
                self.log_signal.emit("Committing and pushing to Git...\n")
                git_commands = [
                    ["git", "add", "."],
                    ["git", "commit", "-m", commit_msg],
                    ["git", "push", "-f", "-u", "origin", "main"],
                ]
                if not self._run_cmd_sequence(git_commands, cwd=_project_root):
                    self.log_signal.emit("Git push failed.\n")
                    self.set_busy_signal.emit(False)
                    return

                if self.cancelled:
                    self.set_busy_signal.emit(False)
                    return

                # Upload portable archive to the 'portable' release tag
                self.log_signal.emit(f"Uploading portable archive to 'portable' release tag...\n")
                release_cmd = [
                    "gh", "release", "upload", "portable", str(archive_path),
                    "--clobber",
                ]
                if not self._run_cmd_sequence([release_cmd], cwd=_project_root):
                    self.log_signal.emit("GitHub release creation failed.\n")
                    self.set_busy_signal.emit(False)
                    return

                self.log_signal.emit(f"Portable archive uploaded to 'portable' release successfully.\n")
                self.log_signal.emit("\n>>> Release complete <<<\n")
                self.set_busy_signal.emit(False)
                self.proc = None

            threading.Thread(target=worker, daemon=True).start()

        # ---------- close ----------

        def closeEvent(self, event):
            self._save_all()
            event.accept()

    # ---- launch ----
    app = QApplication.instance() or QApplication(sys.argv)
    app.setStyle("Fusion")
    window = DeployWindow()
    window.show()
    app.exec()


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
    if not ini_path.exists():
        tags = find_tags([README_SET, SITE_SET])
        init_ini(ini_path, tags)
    run_gui(ini_path)


if __name__ == "__main__":
    main(sys.argv[1:])
