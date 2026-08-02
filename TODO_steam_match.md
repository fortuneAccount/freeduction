# Steam Matching + Editor Context Menu — Implementation Todo

## Phase 1: Robust Subtitle-Aware Matching in NameProcessor
- [ ] Step 1: Refactor `NameProcessor.find_steam_match()` to add:
  - Exact match
  - Shortest prefix-extended-key fallback (existing)
  - Base-name fallback using subtitle delimiters (`:`, `;`, `,`, ` - `, `-`, `(`, `[`) when `display_name` is supplied
- [ ] Step 2: Add `NameProcessor.find_steam_match_candidates()` returning a ranked candidate list for interactive selection

## Phase 2: Game Indexer + Data Manager
- [ ] Step 3: Update `_get_steam_match()` in `game_indexer.py` to pass `display_name` into `find_steam_match()`
- [ ] Step 4: Improve `_perform_fuzzy_steam_matching()` in `data_manager.py` to check prefix/base-name matches before difflib

## Phase 3: Editor Tab — Context Menu + Fixes
- [ ] Step 5: Fix `search_steam_id()` NameError (undefined `match_data` variable)
- [ ] Step 6: Pass `display_name` in `add_game_manually()` and `auto_match_steam_id_selected()`
- [ ] Step 7: Add context-menu actions:
  - "Fetch Match & Set Name-Override" (auto-query + populate name_override + steam_id)
  - "Search on SteamDB (Browser)"
  - "Search on Steam Store (Browser)"
- [ ] Step 8: Add `QUrl`, `QDesktopServices`, `urllib.parse` imports

## Phase 4: Verification
- [ ] Step 9: Run `python -m py_compile` on all edited files
- [ ] Step 10: Review final diff

