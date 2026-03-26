# Task: Partial Manifest + Complete Flag + Create Empty World

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 5 — Partial Worlds + World Management API

## Description

`resolve_manifest()` crashes if any layer is missing from manifest. `assemble_world()` requires all 5 layers. Neither supports partial/empty worlds. This task makes the core infrastructure partial-world-aware:

1. `resolve_manifest()` skips undefined layers (returns only defined ones in the dict).
2. New `create_empty_world()` in assembly.py — creates a world with manifest containing only metadata (name, description, default_player_faction) and `layers: {}`. All layers undefined.
3. `list_worlds()` returns `complete: bool` per world. Complete = all 5 layers defined and resolvable.
4. `start_game()` raises `RuntimeError` for incomplete worlds (before attempting any loads).
5. `get_world_manifest()` returns undefined layers with `source: null` so frontend knows which slots are empty.
6. Existing `assemble_world()` stays strict (all 5 required) — it's the "wizard" path. `create_empty_world()` is the "blank canvas" path.

Key files: `content_loader/manifest.py`, `content_loader/assembly.py`, `service/game_service.py`, `adapters/api/schemas.py`, `adapters/api/routes_master.py`.

## Tests First

Unit tests in `tests/unit/test_partial_manifest.py`:

1. **Partial manifest resolves defined layers only.** Create manifest with geography + politics defined, settlements/ecology/entities missing. `resolve_manifest()` returns dict with 2 entries, no crash.
2. **Empty manifest resolves to empty dict.** Manifest with `layers: {}`. Returns `{}`.
3. **Complete flag: full world = True.** `list_worlds()` on sword_vale returns `complete: True`.
4. **Complete flag: partial world = False.** Create world with 3/5 layers. `list_worlds()` returns `complete: False`.
5. **Start game rejected for incomplete world.** `start_game("partial_world")` raises `RuntimeError` with clear message about missing layers.
6. **Create empty world.** `create_empty_world(content_dir, "blank", "Blank", "test", "kingdom")` creates dir with manifest, `resolve_manifest()` returns `{}`, world appears in `list_worlds()` with `complete: False`.
7. **Create empty world — duplicate ID raises FileExistsError.**
8. **get_world_manifest for partial world.** Returns all 5 layer types: defined ones with source/template, undefined ones with `source: null`.

## Implementation

1. **manifest.py**: Change `resolve_manifest()` loop — iterate `manifest["layers"]` keys instead of `LayerType` enum. Skip entries where value is None. Return only resolved layers.
2. **assembly.py**: Add `create_empty_world(content_dir, world_id, name, description, default_player_faction) -> Path`. Creates world dir + manifest with empty `layers: {}`.
3. **game_service.py**:
   - `list_worlds()`: After loading meta, call `resolve_manifest()` and check `len(resolved) == len(LayerType)` → `complete` field.
   - `start_game()`: Check completeness first, raise before loading content.
   - `get_world_manifest()`: Return all 5 layer types, filling undefined ones with `{"source": None}`.
4. **schemas.py**: Add `complete: bool` to `WorldListItem`.
5. **routes_master.py**: Add `POST /api/master/worlds` endpoint for `create_empty_world` (distinct from `/assemble` which stays strict). Request body: `CreateWorldRequest(id, name, description, default_player_faction)`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `resolve_manifest()` handles 0-5 defined layers without crashing
- [ ] `list_worlds()` returns `complete` field for every world
- [ ] `start_game()` rejects incomplete worlds with descriptive error
- [ ] `create_empty_world` API endpoint works
- [ ] Existing `assemble_world` unchanged (still requires all 5)

## Status

`done`

## Developer Notes

All 8 acceptance criteria met. Key changes:

- `resolve_manifest()` now iterates `manifest["layers"]` keys instead of `LayerType` enum — missing layers are simply not in the result dict.
- `create_empty_world()` added to assembly.py — writes manifest with `layers: {}`.
- `list_worlds()` returns `complete: bool` based on whether all 5 layer types resolve.
- `start_game()` checks completeness before loading content, raises `RuntimeError` with missing layer names.
- `get_world_manifest()` returns all 5 layer types — undefined ones get `source: None`.
- `POST /api/master/worlds` endpoint added for creating empty worlds.
- Old test `test_old_create_world_endpoint_gone` updated to `test_create_empty_world_endpoint_exists` — the endpoint now exists intentionally.
- `test_library_paths_point_into_library_dir` updated — sword_vale settlements are custom (not library), so the assertion was wrong.
