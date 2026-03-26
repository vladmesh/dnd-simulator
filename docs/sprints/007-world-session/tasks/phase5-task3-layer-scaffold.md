# Task: Layer Scaffold Endpoint

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 5 — Partial Worlds + World Management API

## Description

New endpoint: `POST /api/master/worlds/{world_id}/layers/{layer_type}/scaffold`. Creates a minimal but valid custom layer for a world that's missing this layer type. Updates manifest to `source: custom`. The scaffold contains empty-but-parseable YAML files so the layer can be loaded (producing an empty world section) or edited further.

Scaffold templates per layer type:
- **geography**: `regions.yaml` (empty list), `locations.yaml` (empty list)
- **politics**: `nations.yaml` (empty list), `factions.yaml` (empty list)
- **settlements**: `settlements.yaml` (empty list)
- **ecology**: `squads.yaml` (empty list), `monsters.yaml` (empty dict with `types: []`, `encounters: {}`)
- **entities**: `npcs.yaml` (empty list)

After scaffolding all 5 layers, the world should be startable (empty but valid — zero regions, zero NPCs, etc.). The load functions already handle empty lists gracefully (return `[]`).

Key files: `content_loader/assembly.py` (scaffold function + templates), `service/game_service.py` (service method), `adapters/api/routes_master.py` (endpoint).

## Tests First

Unit tests in `tests/unit/test_layer_scaffold.py`:

1. **Scaffold geography creates valid layer files.** Empty world → scaffold geography → `regions.yaml` and `locations.yaml` exist, are valid YAML, manifest updated to `source: custom`.
2. **Scaffold all 5 layers makes world complete.** Create empty world → scaffold each layer → `complete: True` in list_worlds, `start_game()` succeeds (empty world, no crash).
3. **Scaffold on already-defined layer raises ValueError.** World with geography defined → scaffold geography → error.
4. **Scaffold on nonexistent world raises FileNotFoundError.**
5. **Scaffold updates manifest correctly.** After scaffold, `get_world_manifest()` shows layer as `source: custom` with no template/version.
6. **Scaffolded ecology has correct structure.** monsters.yaml has `types` and `encounters` keys (not just empty list — ecology loader expects specific structure).
7. **Full pipeline: create empty → scaffold all → fork layer → edit → start session.** The golden path combining tasks 1-3.

## Implementation

1. **assembly.py**: Define `LAYER_SCAFFOLDS: dict[LayerType, dict[str, str]]` — maps layer type to dict of filename → default YAML content. Add `scaffold_layer(content_dir, world_id, layer_type) -> Path`. Creates layer dir, writes scaffold files, updates manifest to `source: custom`. Raises `ValueError` if layer already defined, `FileNotFoundError` if world missing.
2. **game_service.py**: `scaffold_layer()` method — delegates to assembly function.
3. **routes_master.py**: `POST /api/master/worlds/{world_id}/layers/{layer_type}/scaffold` — calls service, returns 201.
4. Verify that content loaders (`load_world`, `load_nations`, `load_settlements`, `load_npcs`, `load_squads`, `load_monsters`) handle empty YAML gracefully (empty list / empty dict). Fix any that crash on empty input.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] All 5 layer types have scaffold templates
- [ ] Scaffolded world with all 5 layers starts a session without crash
- [ ] Content loaders handle empty YAML without errors
- [ ] Manifest correctly updated after scaffold

## Status

`done`

## Developer Notes

Implemented scaffold_layer in assembly.py with LAYER_SCAFFOLDS dict mapping each LayerType to its minimal YAML files. Fixed load_locations to return [] on empty input instead of raising RuntimeError — required for scaffolded worlds to be startable. The ecology scaffold uses explicit `templates: {}` / `encounters: {}` keys since load_monsters expects that structure (not just an empty file). All other loaders already handled empty gracefully via `_read_yaml`'s `or {}` pattern.
