# Steam Subtitle Matching + Editor Search Menu — Implementation Todo

## Task
1. Fix steam-matching so subtitle titles match (e.g. "SuperGame" → "SuperGame: Super Dupers").
2. Add "Search on Steampowered" / "Search on Steamdb" menu items to Editor Tab context menu.
3. Add an automatic match action that populates the Name-Override field.

## Steps
- [x] Step 1: Expand `NameProcessor.find_steam_match()` in `Python/ui/name_processor.py` with subtitle/prefix fallback matching
- [x] Step 2: Update `_get_steam_match()` in `Python/ui/game_indexer.py` to use `find_steam_match()`
- [ ] Step 3: Update `Python/ui/editor_tab.py`:
    - [x] Step 3a: Add `QUrl` and `QDesktopServices` imports
    - [x] Step 3b: Add context-menu actions (Auto-Fill Steam Title & ID, Search on Steampowered, Search on Steamdb)
    - [ ] Step 3c: Add new handler methods
    - [ ] Step 3d: Update existing exact-lookup sites to use `find_steam_match()`
- [ ] Step 4: Syntax-check edited files with `py_compile`
- [ ] Step 5: Final review

## Follow-up
- Manual test of context menu + matching behavior
- Regenerate Steam cache if needed (caches rebuilt from `steam.json`)

