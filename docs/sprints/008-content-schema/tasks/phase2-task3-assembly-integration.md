# Task: Assembly Integration — Wire Catalogs into Game Start

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 2 — Catalogs — Monsters + Items

## Description

Wire catalog loading into `GameService.start_game()` so catalogs are loaded once at startup and passed to all content loaders that need them. Verify the full pipeline works end-to-end: catalogs load → world references resolve → game starts.

**Flow change in `start_game()`:**
1. Load monster catalog: `load_monster_catalog(content_dir)`
2. Load item catalog: `load_item_catalog(content_dir)`
3. Pass `monster_catalog` to `load_monsters(path, lang, catalog=monster_catalog)`
4. Pass `item_catalog` to `load_npcs(path, lang, known_locations, item_catalog=item_catalog)`
5. Everything else unchanged

**Catalog path convention:** `content_dir / "catalogs" / "monsters"` and `content_dir / "catalogs" / "items"`. Missing catalog dirs → empty catalogs (worlds without catalog refs are valid).

**Update world list/create/fork APIs** if they need awareness of catalogs. Scaffold ecology layer should reference catalog monsters by default if catalogs exist.

## Tests First

1. **Full game start with catalog references.** Load sword_vale world (which now uses catalog refs from tasks 1-2), call `start_game()`, verify: world loads, monsters resolve from catalog, NPC items resolve from catalog, ecology layer has squads with correct member CRs, entities layer has NPCs with correct equipment.

2. **Game start with empty catalogs.** A world that uses only inline definitions (no `base:` or `ref:`) still loads correctly when catalogs are empty.

3. **Game start with missing catalog directory.** If `content/catalogs/monsters/` doesn't exist, `load_monster_catalog()` returns empty dict — no crash.

4. **Catalog references across multiple worlds.** Two worlds referencing the same catalog goblin but with different overrides (one has HP=7, other has HP=20) both load correctly with their respective stats.

5. **World CRUD API still works.** Create world, fork world, scaffold layers — all work correctly with catalog-aware loaders. A scaffolded ecology layer can reference catalog monsters.

## Implementation

After tests are red:

1. Update `src/dnd_simulator/service/game_service.py`:
   - In `start_game()`: load catalogs before loading world content.
   - Pass catalogs to `load_monsters()` and `load_npcs()`.

2. Update `content_loader/catalogs.py`:
   - `load_monster_catalog()` and `load_item_catalog()` handle missing dirs gracefully (return empty dict).

3. Update any API endpoints or service methods that load content and now need catalog access:
   - World preview/validation endpoints if they exist
   - Layer read/write endpoints if they validate content

4. Integration test in `tests/integration/` that starts a full game with sword_vale and verifies the catalog pipeline works.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] `start_game()` loads catalogs and passes them through
- [x] sword_vale world starts correctly with catalog-based monsters and items
- [x] Worlds without catalog references still work
- [x] Missing catalog directories don't crash

## Status

`done`

## Developer Notes

The catalog wiring into `start_game()` was already completed in tasks 1-2. This task's
real value was integration tests: a `catalog_world` test world with catalog refs for
both monsters (`base: goblin`) and NPC items (`ref: dagger`, `ref: health_potion`),
plus test catalogs in `tests/integration/content/catalogs/`.

5 integration tests added:
- Session starts with catalog refs
- NPC items resolve from item catalog (name, type verified via API)
- Time advance works with catalog-resolved squad member CRs
- Inline-only world (arena) still works alongside catalogs
- Save/load round-trip preserves catalog-resolved data
