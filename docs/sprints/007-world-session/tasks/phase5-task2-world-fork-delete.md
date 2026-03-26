# Task: World Fork + Delete Endpoints

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 5 — Partial Worlds + World Management API

## Description

Two new world-level operations:

1. **Fork world** — `POST /api/master/worlds/{world_id}/fork`. Creates a copy of the world with a new ID. Library references are preserved (not copied). Optional `from_layer` query param: if specified, all layers from that type upward (inclusive) are removed from the copy's manifest, creating a draft that needs those layers filled in. Layer order: geography < politics < settlements < ecology < entities.

2. **Delete world** — `DELETE /api/master/worlds/{world_id}`. Removes the world directory. Blocked if: (a) world has active sessions, or (b) world is a "base" world (shipped with the game, e.g. sword_vale, test_vale). Base worlds identified by not having any custom layers OR by a hardcoded set — use the simpler approach: check if any session references this world.

Key files: `content_loader/assembly.py` (new functions), `service/game_service.py` (new methods), `adapters/api/routes_master.py` (new endpoints), `adapters/api/schemas.py` (request/response types).

## Tests First

Unit tests in `tests/unit/test_world_fork_delete.py`:

1. **Fork world creates copy with same layers.** Fork sword_vale as "sv_copy". New world has manifest with identical layer references. Original unchanged.
2. **Fork world with from_layer truncation.** Fork sword_vale with `from_layer=settlements`. Copy has geography + politics defined, settlements/ecology/entities undefined. `complete` = False.
3. **Fork world — new ID required, conflict raises FileExistsError.** Fork to existing world ID.
4. **Fork world — source not found raises FileNotFoundError.**
5. **Fork preserves library references (no file copying).** Forked manifest still says `source: library, template: sword_vale` for kept layers.
6. **Delete world removes directory.** Create empty world, delete it, confirm gone from `list_worlds()`.
7. **Delete world blocked for base world.** Attempting to delete sword_vale raises ValueError.
8. **Delete world blocked if active session exists.** Start session from world, try delete — raises RuntimeError.
9. **from_layer=geography removes ALL layers** (everything is geography and above). Result: empty manifest, same as create_empty_world.

## Implementation

1. **assembly.py**: Add `LAYER_ORDER: list[LayerType]` constant (geography → entities). Add `fork_world(content_dir, source_world_id, new_world_id, from_layer=None) -> Path`. Reads source manifest, optionally truncates layers at `from_layer` index (inclusive, upward), writes new manifest to new world dir. No file copying for library layers.
2. **assembly.py**: Add `delete_world(content_dir, world_id) -> None`. Removes world directory via `shutil.rmtree`. Caller (service) handles safety checks.
3. **game_service.py**: `fork_world()` method — delegates to assembly, returns world info. `delete_world()` method — checks no active sessions reference this world, checks not a base world (maintain `BASE_WORLDS` frozenset or check if world dir contains only manifest.yaml with all-library layers), delegates to assembly.
4. **schemas.py**: `ForkWorldRequest(new_id: str, from_layer: str | None = None)`. No special delete schema needed.
5. **routes_master.py**: Wire endpoints.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `LAYER_ORDER` constant defined and used consistently
- [ ] Fork preserves library references without copying files
- [ ] Truncation removes correct layers (inclusive upward)
- [ ] Delete has safety checks (active sessions, base worlds)

## Status

`pending`
