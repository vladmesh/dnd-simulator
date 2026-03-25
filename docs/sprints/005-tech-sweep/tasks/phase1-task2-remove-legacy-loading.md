# Task: Remove legacy single-file loading code and fallback aliases

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 1 — Content Standardization

## Description

With all worlds in directory format, remove the dual-path loading logic and dead fallback aliases:

1. **`content_loader.py`** — `_resolve_source()` becomes unnecessary (always a directory). `_load_section()` simplifies to just `_read_yaml(path / f"{section}.yaml")`. Remove the single-file branch. Update docstring at module top.
2. **`content_loader.py:parse_npc()`** — Remove `ndata.get("region_id")` fallback on line 532. Require `start_location`.
3. **`content_loader.py:parse_player()`** — Remove `pdata.get("start_region")` and `pdata.get("location_id")` fallbacks on line 593. Require `start_location`.
4. **`commands_creatures.py:_parse_spawn()`** — Remove `data["region_id"]` fallback on line 177. Require `start_location`.
5. **`schemas.py`** — Remove `start_region` field from `CreatePlayerRequest`. Remove `region_id` field from `SpawnCreatureRequest`.
6. **`game_service.py`** — Update docstring on `start_game()` that mentions "legacy filename".
7. **`game_service.py:list_worlds()`** — Remove `is_world_file` branch (line 193). Only list directories with `world.yaml`.

## Tests First

- `parse_npc()` with only `start_location` works; with neither `start_location` nor `region_id` → empty string (existing behavior, no crash).
- `parse_player()` with only `start_location` works; legacy keys `start_region`/`location_id` are ignored (not recognized).
- `_parse_spawn()` with `start_location` works; without `start_location` → `KeyError` (fail fast).
- `CreatePlayerRequest` rejects unknown field `start_region` (Pydantic strict — actually it just ignores it, but the field is gone from schema).
- `SpawnCreatureRequest` requires `start_location`, no `region_id` fallback.
- `list_worlds()` does not pick up stray `.yaml` files in `worlds/` directory — only directories with `world.yaml`.

## Implementation

Work through the list above. Each removal is small and independent. Run `make check` after each file change to catch regressions early.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] `_resolve_source()` removed or simplified to directory-only
- [ ] `_load_section()` simplified — no single-file branch
- [ ] All fallback aliases removed from parsers and schemas
- [ ] `list_worlds()` directory-only
- [ ] Module docstring updated
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)

## Status

`pending`
