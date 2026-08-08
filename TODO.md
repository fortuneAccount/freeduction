# Options & Arguments Parsing — Harmonization Plan

## Goal
Ensure options/arguments derived from `assets/options_arguments.set` are parsed
consistently by both the main (Python) application and the C launcher:
- Sections match both `constants.SECTION_TO_CONFIG_KEY` (Python) and
  `get_options_section_for_key()` (C config_editor).
- Empty tokens / leading `|` (empty-priority) are preserved and observed when
  building launcher parameters.
- Preset values default to the first identified token; empty-priority -> empty.
- Resolve naming mismatches between Game.ini keys and `.set` sections.

## Steps
- [x] Rewrite `assets/options_arguments.set` with canonical `[Xoptions]`/
      `[Xarguments]` sections plus alias sections (borderlesswindowing, audioapp).
- [x] Fix `get_options_section_for_key()` in `config_editor.c` to strip the
      `path` token before the `options`/`arguments` suffix, and remap aliases.
- [x] Make `load_options_section()` read the key matching the section suffix
      (`options` vs `arguments`).
- [x] Update `populate_options_combo()` caller to pass `want_key` to
      `load_options_section()`.
- [x] Add a runtime empty-token resolver in `launcher.c` and apply it in the
      command builders so absent (empty) option/argument tokens are omitted.
      (`normalize_pipe_options_arguments()` + `pipe_first_effective_token()`).
- [x] Add alias-section mappings to `SECTION_TO_CONFIG_KEY` in `constants.py`.
- [x] Fix `_apply_tool_defaults()` in `config_manager.py` to resolve the first
      effective token (honoring empty-priority) instead of the raw pipe string.
      (added `ConfigManager._resolve_first_token()`).
- [ ] Fix `_show_options_args_dialog()` in `setup_tab.py` to compare/select
      against the first-effective token rather than the raw pipe string.
