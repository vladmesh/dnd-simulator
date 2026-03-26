# Task: Wire Manifest into GameService + Remove Old Format

**Date:** 2026-03-26
**Sprint:** 006-layer-composition
**Phase:** 2 — Content Loader Reads from Manifest

## Description

Refactor `GameService.start_game()`, `get_world_template()`, and `list_worlds()` to load content through the manifest resolver instead of passing a flat world path to each `load_*` function. Each loader receives the resolved per-layer path. Remove sword_vale's old flat data files (regions.yaml, nations.yaml, etc.) — only `manifest.yaml` remains in `content/worlds/sword_vale/`. Update `list_worlds` to detect worlds by `manifest.yaml` instead of `world.yaml`. Update or replace existing tests that relied on the old flat format.

## Tests First

1. **start_game loads sword_vale via manifest (library-sourced):** Starting a game with `world_name="sword_vale"` produces a World with 7 regions, 3 nations, 10 settlements, 32 locations, 4 NPCs, 3 squads. This is the same data as before — the test proves the manifest path produces identical results.

2. **start_game loads test_vale via manifest (custom-sourced):** Starting a game with `world_name="test_vale"` produces a World with the expected test_vale data (2 regions, 1 nation, correct NPC count, etc.).

3. **list_worlds returns both sword_vale and test_vale:** The endpoint lists both worlds with correct names and descriptions, detecting them via manifest.yaml.

4. **World without manifest.yaml is not listed and cannot start:** A stray directory without manifest.yaml in content/worlds/ is ignored by list_worlds and raises an error from start_game.

## Implementation

1. Refactor `start_game()` in `game_service.py`:
   - Call `resolve_manifest(world_path, content_dir)` to get per-layer paths
   - Pass `layer_paths["geography"]` to `load_world()`, `load_locations()`, `load_battle_maps()`
   - Pass `layer_paths["politics"]` to `load_nations()`, `load_factions()`
   - Pass `layer_paths["settlements"]` to `load_settlements()`
   - Pass `layer_paths["ecology"]` to `load_monsters()`, `load_squads()`
   - Pass `layer_paths["entities"]` to `load_npcs()`
   - Use `load_world_meta_from_manifest()` for world metadata

2. Same refactor for `get_world_template()`.

3. Update `list_worlds()`: check for `manifest.yaml` instead of `world.yaml`.

4. Delete old flat files from `content/worlds/sword_vale/` (regions.yaml, nations.yaml, npcs.yaml, locations.yaml, monsters.yaml, squads.yaml, factions.yaml, world.yaml). Only manifest.yaml remains.

5. Update `test_content_loader_dir.py`: point at resolved library paths instead of the old flat sword_vale directory.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] `make check` passes (all existing tests green)
- [ ] sword_vale loads identically via manifest (same entity counts, same data)
- [ ] test_vale loads correctly via manifest (custom source)
- [ ] No flat-format files remain in content/worlds/sword_vale/ (only manifest.yaml)
- [ ] `list_worlds` detects worlds by manifest.yaml

## Status

`pending`
