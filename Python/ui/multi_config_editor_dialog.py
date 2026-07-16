#!/usr/bin/env python3
"""
multi_config_editor_dialog.py - Multi-file Game.ini editor.

Provides a modal dialog that can edit one *or many* Game.ini files at once.

When several files are selected the dialog shows the *union* of every section
and key found in any of the selected files. For each key it inspects the value
across every file and visually indicates whether the value is:

  * homogeneous - present in every file with an identical value (green tint), or
  * mixed       - missing in some files, or differing between files (amber tint).

Mixed fields start blank / partially-checked and are only written back to the
files if the user actually edits them ("only write if changed"), so per-file
differences are preserved unless the user deliberately overrides them.

When a single file is selected every section and key is shown and fully
editable, behaving like a straightforward single-file editor.

This module reuses the schema, label abbreviations and the ListEditWidget from
config_editor_dialog.py so the two editors stay consistent.
"""

import os
import configparser
from typing import Dict, List, Optional, Tuple

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
    QCheckBox, QComboBox, QScrollArea, QWidget, QGroupBox, QFormLayout,
    QFileDialog, QSizePolicy, QMessageBox, QFrame
)
from PyQt6.QtCore import Qt

from Python.config_editor_dialog import (
    CONFIG_SCHEMA,
    KEY_ABBREVIATIONS,
    ListEditWidget,
)

# Sentinel used to represent "this file does not contain this key".
_MISSING = object()

# Theme-agnostic tint colours. Explicit background + foreground keeps the text
# legible under both the light and dark themes the app ships with.
_HOMOGENEOUS_QSS = (
    "background-color: #cde6cf; color: #14351a; border: 1px solid #5ba36a;"
)
_MIXED_QSS = (
    "background-color: #f6e0a0; color: #3a2f00; border: 1px solid #c9a227;"
)

_MIXED_PLACEHOLDER = "<multiple values>"


class MultiConfigEditorDialog(QDialog):
    """Edit one or more Game.ini files, highlighting shared vs. differing keys."""

    def __init__(self, ini_paths: List[str], parent=None, on_saved=None):
        super().__init__(parent)
        # De-duplicate while preserving order, keep only existing files.
        seen = set()
        self.ini_paths: List[str] = []
        for p in ini_paths:
            norm = os.path.normpath(p)
            if norm not in seen and os.path.isfile(norm):
                seen.add(norm)
                self.ini_paths.append(norm)

        self.on_saved = on_saved
        self.multi = len(self.ini_paths) > 1

        # One ConfigParser per file, preserving key case.
        self.configs: List[configparser.ConfigParser] = []
        for path in self.ini_paths:
            cfg = configparser.ConfigParser()
            cfg.optionxform = str  # preserve case
            try:
                cfg.read(path, encoding="utf-8")
            except Exception:
                try:
                    cfg.read(path)
                except Exception:
                    pass
            self.configs.append(cfg)

        # Each entry: dict(section, key, type, widget, is_mixed, dirty).
        self.rows: List[dict] = []

        title = (
            f"Edit {len(self.ini_paths)} Game.ini Files"
            if self.multi
            else "Edit Game.ini"
        )
        self.setWindowTitle(title)
        self.setModal(True)
        self.resize(720, 620)
        self._build_ui()

    # ------------------------------------------------------------------
    # Data helpers
    # ------------------------------------------------------------------

    def _file_label(self, path: str) -> str:
        """Human-friendly label for a Game.ini path (its profile folder name)."""
        parent = os.path.basename(os.path.dirname(path))
        return parent or os.path.basename(path)

    def _collect_union(self) -> Dict[str, List[str]]:
        """Return an ordered mapping of section -> [keys] present in any file.

        Sections and keys follow the schema order first (for a stable, familiar
        layout) and any extra keys found on disk are appended afterwards.
        """
        # Gather everything present across the selected files.
        present: Dict[str, List[str]] = {}
        for cfg in self.configs:
            for section in cfg.sections():
                bucket = present.setdefault(section, [])
                for key in cfg.options(section):
                    if key not in bucket:
                        bucket.append(key)

        ordered: Dict[str, List[str]] = {}

        # Schema-ordered sections/keys first.
        for section, keys in CONFIG_SCHEMA.items():
            if section not in present:
                continue
            present_keys = present[section]
            ordered_keys: List[str] = []
            for key in keys:
                # Schema keys are lower-case; match case-insensitively.
                match = next(
                    (pk for pk in present_keys if pk.lower() == key.lower()), None
                )
                if match is not None:
                    ordered_keys.append(match)
            # Extra keys present on disk but not in the schema.
            for pk in present_keys:
                if pk not in ordered_keys:
                    ordered_keys.append(pk)
            if ordered_keys:
                ordered[section] = ordered_keys

        # Sections present on disk but absent from the schema.
        for section, keys in present.items():
            if section not in ordered and keys:
                ordered[section] = list(keys)

        return ordered

    def _values_for(self, section: str, key: str) -> List[object]:
        """Return the per-file value for a key (or _MISSING when absent)."""
        values: List[object] = []
        for cfg in self.configs:
            if cfg.has_option(section, key):
                values.append(cfg.get(section, key))
            else:
                values.append(_MISSING)
        return values

    @staticmethod
    def _is_homogeneous(values: List[object]) -> bool:
        """True when present in every file with a single identical value."""
        if any(v is _MISSING for v in values):
            return False
        return len(set(values)) <= 1

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(6)

        # Header: which files, and (for multi) the colour legend.
        header = QLabel(self._header_text())
        header.setWordWrap(True)
        header.setTextFormat(Qt.TextFormat.RichText)
        main_layout.addWidget(header)

        if self.multi:
            legend = QLabel(
                '<span style="background-color:#cde6cf;color:#14351a;'
                'padding:2px 6px;border:1px solid #5ba36a;">identical in all</span>'
                '&nbsp;&nbsp;'
                '<span style="background-color:#f6e0a0;color:#3a2f00;'
                'padding:2px 6px;border:1px solid #c9a227;">differs between files</span>'
            )
            legend.setTextFormat(Qt.TextFormat.RichText)
            main_layout.addWidget(legend)

        # Scroll area holding all the fields.
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(8)

        union = self._collect_union()

        if not union:
            scroll_layout.addWidget(
                QLabel("The selected Game.ini file(s) contain no readable settings.")
            )
        else:
            for section, keys in union.items():
                group = QGroupBox(f"[{section}]")
                form = QFormLayout()
                form.setSpacing(4)
                form.setContentsMargins(8, 8, 8, 8)
                form.setFieldGrowthPolicy(
                    QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow
                )
                for key in keys:
                    values = self._values_for(section, key)
                    self._add_field(form, section, key, values)
                group.setLayout(form)
                scroll_layout.addWidget(group)

        # Collapsible "Available settings" group: schema keys absent everywhere.
        available_group = self._build_available_group(union)
        if available_group is not None:
            scroll_layout.addWidget(available_group)

        scroll_layout.addStretch()
        scroll.setWidget(scroll_widget)
        main_layout.addWidget(scroll, 1)

        # Buttons.
        button_layout = QHBoxLayout()
        save_btn = QPushButton("Save")
        save_btn.setStyleSheet("font-weight: bold;")
        save_btn.clicked.connect(self.save_all)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(save_btn)
        button_layout.addStretch()
        button_layout.addWidget(cancel_btn)
        main_layout.addLayout(button_layout)

    def _header_text(self) -> str:
        if not self.ini_paths:
            return "No valid Game.ini files were found for the selection."
        if self.multi:
            names = ", ".join(self._file_label(p) for p in self.ini_paths)
            return (
                f"<b>Editing {len(self.ini_paths)} Game.ini files:</b> {names}<br>"
                "Only fields you change are written to every selected file; "
                "untouched differing fields keep their per-file values."
            )
        return f"<b>Editing:</b> {self.ini_paths[0]}"

    def _build_available_group(self, union: Dict[str, List[str]]) -> Optional[QGroupBox]:
        """Group of schema keys not present in any selected file (for adding)."""
        group = QGroupBox("Available settings (not set - click to expand)")
        group.setCheckable(True)
        group.setChecked(False)
        outer = QVBoxLayout()
        outer.setContentsMargins(8, 8, 8, 8)

        added_any = False
        for section, keys in CONFIG_SCHEMA.items():
            present_keys = {k.lower() for k in union.get(section, [])}
            missing = [k for k in keys if k.lower() not in present_keys]
            if not missing:
                continue
            sub = QGroupBox(f"[{section}]")
            form = QFormLayout()
            form.setSpacing(4)
            form.setContentsMargins(8, 8, 8, 8)
            for key in missing:
                # Absent everywhere => trivially homogeneous (empty), no tint.
                values = [_MISSING] * len(self.configs)
                self._add_field(form, section, key, values, force_type=keys[key])
                added_any = True
            sub.setLayout(form)
            outer.addWidget(sub)

        if not added_any:
            return None
        group.setLayout(outer)
        return group

    def _add_field(
        self,
        form: QFormLayout,
        section: str,
        key: str,
        values: List[object],
        force_type: Optional[str] = None,
    ):
        """Create a labelled, homogeneity-aware widget and register it."""
        present_values = [v for v in values if v is not _MISSING]
        if not present_values:
            # Key is absent from every selected file (e.g. an "available"
            # setting the user may choose to add) - show a normal empty field.
            is_mixed = False
        else:
            is_mixed = not self._is_homogeneous(values)
        common_value = present_values[0] if (present_values and not is_mixed) else ""

        key_type = force_type or self._infer_type(section, key, common_value)
        widget = self._create_widget(key_type, common_value, is_mixed)

        row = {
            "section": section,
            "key": key,
            "type": key_type,
            "widget": widget,
            "is_mixed": is_mixed,
            "dirty": False,
        }
        self.rows.append(row)

        # Wire up dirty tracking AFTER the initial value has been set.
        self._connect_dirty(row)

        # Visual homogeneity cue (only meaningful when editing multiple files).
        if self.multi and values and any(v is not _MISSING for v in values):
            self._apply_tint(widget, key_type, is_mixed)

        # Tooltip explaining the per-file values.
        if self.multi:
            widget.setToolTip(self._value_tooltip(values))

        label = self._label_for(section, key)
        if self.multi and is_mixed:
            label += "  *"  # mark differing keys in the label too
        form.addRow(label, widget)

    def _value_tooltip(self, values: List[object]) -> str:
        lines = []
        for path, val in zip(self.ini_paths, values):
            shown = "(not set)" if val is _MISSING else (val or "(empty)")
            lines.append(f"{self._file_label(path)}: {shown}")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Widget factory / type inference (mirrors AdvancedConfigEditor)
    # ------------------------------------------------------------------

    def _label_for(self, section: str, key: str) -> str:
        key_lower = key.lower()
        if key_lower in KEY_ABBREVIATIONS:
            return KEY_ABBREVIATIONS[key_lower]
        return key

    def _infer_type(self, section: str, key: str, value: str) -> str:
        key_lower = key.lower()
        schema_section = CONFIG_SCHEMA.get(section, {})
        if key_lower in schema_section:
            return schema_section[key_lower]
        if any(t in key_lower for t in ("path", "app", "profile", "executable")):
            return "file"
        if "directory" in key_lower or "folder" in key_lower:
            return "folder"
        if value and value.lower() in (
            "true", "false", "0", "1", "on", "off", "enabled", "disabled"
        ):
            return "bool"
        if value and ("," in value or "|" in value):
            return "list"
        return "text"

    def _create_widget(self, key_type: str, value: str, is_mixed: bool) -> QWidget:
        if key_type == "bool":
            checkbox = QCheckBox()
            if is_mixed:
                checkbox.setTristate(True)
                checkbox.setCheckState(Qt.CheckState.PartiallyChecked)
            else:
                checkbox.setChecked(
                    str(value).lower() in ("true", "1", "on", "enabled")
                )
            return checkbox

        if key_type == "list":
            separator = "|" if (value and "|" in value) else ","
            widget = ListEditWidget("" if is_mixed else value, separator)
            return widget

        if key_type in ("file", "folder"):
            container = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(2)
            line_edit = QLineEdit()
            if not is_mixed:
                line_edit.setText(value)
            else:
                line_edit.setPlaceholderText(_MIXED_PLACEHOLDER)
            browse_btn = QPushButton("...")
            browse_btn.setMaximumWidth(30)
            browse_btn.clicked.connect(
                lambda _=False, le=line_edit, kt=key_type: self._browse_path(le, kt)
            )
            layout.addWidget(line_edit)
            layout.addWidget(browse_btn)
            container.setLayout(layout)
            container.line_edit = line_edit  # store reference for value retrieval
            return container

        # Plain text.
        line_edit = QLineEdit()
        if not is_mixed:
            line_edit.setText(value)
        else:
            line_edit.setPlaceholderText(_MIXED_PLACEHOLDER)
        return line_edit

    def _connect_dirty(self, row: dict):
        """Mark a row dirty on any user interaction with its widget."""
        widget = row["widget"]

        def mark_dirty(*_args):
            row["dirty"] = True

        if isinstance(widget, QCheckBox):
            widget.stateChanged.connect(mark_dirty)
        elif isinstance(widget, ListEditWidget):
            # The combo drives all edits (typing, +, -, selection).
            combo = widget.combo
            combo.currentTextChanged.connect(mark_dirty)
            combo.currentIndexChanged.connect(mark_dirty)
        elif hasattr(widget, "line_edit"):  # path container
            widget.line_edit.textChanged.connect(mark_dirty)
        elif isinstance(widget, QLineEdit):
            widget.textChanged.connect(mark_dirty)

    def _apply_tint(self, widget: QWidget, key_type: str, is_mixed: bool):
        qss = _MIXED_QSS if is_mixed else _HOMOGENEOUS_QSS
        if isinstance(widget, QCheckBox):
            widget.setStyleSheet(f"QCheckBox {{ {qss} padding: 2px 6px; }}")
        elif isinstance(widget, ListEditWidget):
            widget.combo.setStyleSheet(f"QComboBox {{ {qss} }}")
        elif hasattr(widget, "line_edit"):
            widget.line_edit.setStyleSheet(f"QLineEdit {{ {qss} }}")
        elif isinstance(widget, QLineEdit):
            widget.setStyleSheet(f"QLineEdit {{ {qss} }}")

    def _browse_path(self, line_edit: QLineEdit, path_type: str):
        current = line_edit.text()
        if path_type == "folder":
            path = QFileDialog.getExistingDirectory(self, "Select Folder", current)
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Select File", current)
        if path:
            line_edit.setText(path.replace("\\", "/"))

    # ------------------------------------------------------------------
    # Value retrieval + saving
    # ------------------------------------------------------------------

    def _widget_value(self, row: dict) -> Optional[str]:
        """Return the string value for a row, or None when it must be skipped."""
        widget = row["widget"]
        if isinstance(widget, QCheckBox):
            state = widget.checkState()
            if state == Qt.CheckState.PartiallyChecked:
                return None  # still "mixed" - do not write
            return "True" if state == Qt.CheckState.Checked else "False"
        if isinstance(widget, ListEditWidget):
            return widget.get_value()
        if hasattr(widget, "line_edit"):
            return widget.line_edit.text()
        if isinstance(widget, QLineEdit):
            return widget.text()
        return None

    def save_all(self):
        if not self.ini_paths:
            self.reject()
            return

        # Apply every dirty field's value to every selected file's config.
        for row in self.rows:
            if not row["dirty"]:
                continue
            value = self._widget_value(row)
            if value is None:
                continue  # e.g. a bool left in the partially-checked state
            section, key = row["section"], row["key"]
            for cfg in self.configs:
                if not cfg.has_section(section):
                    cfg.add_section(section)
                cfg.set(section, key, value)

        # Write each file back to disk.
        errors = []
        written = 0
        for path, cfg in zip(self.ini_paths, self.configs):
            try:
                with open(path, "w", encoding="utf-8") as f:
                    cfg.write(f)
                written += 1
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{self._file_label(path)}: {exc}")

        if errors:
            QMessageBox.warning(
                self,
                "Save Errors",
                "Some files could not be saved:\n\n" + "\n".join(errors),
            )
            if written == 0:
                return

        if callable(self.on_saved):
            try:
                self.on_saved(self.ini_paths)
            except Exception:
                pass

        self.accept()
