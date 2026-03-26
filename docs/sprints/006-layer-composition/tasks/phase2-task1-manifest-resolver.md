# Task: Manifest Resolver + Standalone Settlements Loader

**Date:** 2026-03-26
**Sprint:** 006-layer-composition
**Phase:** 2 — Content Loader Reads from Manifest

## Description

Create a manifest resolver that reads `manifest.yaml` from a world directory and returns concrete filesystem paths for each layer's data files. Also refactor `load_settlements` to read from the new standalone `settlements.yaml` format (with per-settlement `region` field) instead of extracting settlements nested under regions in `regions.yaml`.

The resolver must handle two source types:
- `source: library` — resolve to `content/library/{layer_type}/{template}/`
- `source: custom` — resolve to `content/worlds/{world}/{layer_type}/`

The resolver should validate that referenced paths exist and fail fast on missing data.

## Tests First

1. **Manifest resolution for library-sourced world (sword_vale):** Given sword_vale's manifest with all layers pointing to `source: library, template: sword_vale`, the resolver returns 5 paths, each pointing into `content/library/{layer_type}/sword_vale/`. All paths exist on disk.

2. **Manifest resolution for custom-sourced world (test_vale):** Given test_vale's manifest with all layers `source: custom`, the resolver returns paths pointing into `content/worlds/test_vale/{layer_type}/`. All paths exist on disk.

3. **Manifest resolution fails on missing template:** A manifest referencing `source: library, template: nonexistent` raises RuntimeError.

4. **Manifest resolution fails on missing manifest:** Calling resolver on a world directory without `manifest.yaml` raises RuntimeError (no backward compat for old format).

5. **Standalone settlements loading:** `load_settlements` with new standalone format (settlements.yaml with `region` field per settlement) correctly loads settlement count, types, region assignments, and population.

6. **Standalone settlements loading fails on missing region field:** A settlement entry without `region` crashes (fail fast, not silent default).

## Implementation

1. Add `resolve_manifest()` to `content_loader/manifest.py` (new file):
   - Reads `manifest.yaml` from world path
   - Returns a dict of `layer_type -> Path` (resolved data directory)
   - Validates all paths exist
   - Also extracts world metadata (name, description, default_player_faction) from the manifest itself

2. Add `load_world_meta_from_manifest()` — reads name/description/default_player_faction directly from manifest.yaml (replacing `world.yaml` as the source of truth).

3. Refactor `load_settlements` in `content_loader/world.py`:
   - New code path: reads `settlements.yaml` directly, each entry has a `region` field
   - Old code path (nested under regions): removed entirely

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `resolve_manifest()` handles both `library` and `custom` sources
- [ ] `load_settlements()` reads standalone format with `region` per settlement
- [ ] Missing manifest / missing template / missing region field all crash with clear errors

## Status

`pending`
