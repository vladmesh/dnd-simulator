# Task: World Assembly + Fork API

**Date:** 2026-03-26
**Sprint:** 006-layer-composition
**Phase:** 3 — World Assembly Backend

## Description

API to assemble a new world from library templates and to fork a library template into a world's custom directory.

**Assemble world** — `POST /api/master/worlds/assemble`: given a world name/id, description, and a dict of layer selections (`{geography: "sword_vale", politics: "sword_vale", ...}`), create a new world directory with a `manifest.yaml` pointing all selected layers to `source: library`. Validates that all 5 layer types are provided and that each referenced template exists in the library. Returns the created world metadata.

This replaces the old `create_world` / `content_saver` flow which wrote flat YAML files. The old `POST /api/master/worlds` and `PUT /api/master/worlds/{id}` endpoints (and `content_saver.py`) become dead code — remove them.

**Fork template** — `POST /api/master/worlds/{world_id}/fork/{layer_type}`: copies the library template directory into the world's own `{layer_type}/` subdirectory and updates `manifest.yaml` to `source: custom` for that layer. After forking, the world uses a local copy that can be edited freely. Raises 409 if the layer is already custom. Raises 404 if world doesn't exist.

**New module:** `src/dnd_simulator/content_loader/assembly.py`
- `assemble_world(content_dir, world_id, name, description, layer_selections, default_player_faction) -> Path` — creates world dir + manifest.yaml.
- `fork_layer(content_dir, world_id, layer_type) -> Path` — copies library template to custom, updates manifest.

**Update GameService:**
- `assemble_world()` method wrapping the assembly function.
- `fork_layer()` method wrapping the fork function.
- Remove `create_world()` and `update_world()` methods.

**Update routes:**
- Replace `POST /api/master/worlds` with `POST /api/master/worlds/assemble`.
- Remove `PUT /api/master/worlds/{id}`.
- Add `POST /api/master/worlds/{world_id}/fork/{layer_type}`.
- Remove `content_saver.py`.

## Tests First

1. **Assemble world** — assemble a world "my_world" selecting sword_vale for all 5 layers. Verify: directory created, manifest.yaml exists with all layers pointing to `source: library`, `template: sword_vale`. `list_worlds()` includes the new world. Starting a session with it works (loads successfully via existing manifest resolver).

2. **Assemble validation** — assembling with a missing layer type raises RuntimeError. Assembling with a nonexistent template slug raises RuntimeError. Assembling over an existing world raises FileExistsError.

3. **Fork template** — assemble a world (all library), then fork the entities layer. Verify: `{world_dir}/entities/` directory exists with copied files (npcs.yaml). Manifest.yaml now says `source: custom` for entities, still `source: library` for the rest. Starting a session still works (custom entities loaded from local dir).

4. **Fork already-custom** — forking a layer that's already `source: custom` raises ValueError (409).

5. **API integration** — POST to `/api/master/worlds/assemble` creates a world. POST to `/api/master/worlds/{id}/fork/entities` forks the layer. GET `/api/master/worlds` lists the new world.

## Implementation

1. Create `src/dnd_simulator/content_loader/assembly.py` with `assemble_world()` and `fork_layer()`.
2. Add `AssembleWorldRequest` schema to `schemas.py`.
3. Wire into `GameService` — new `assemble_world()` and `fork_layer()` methods.
4. Update `routes_master.py` — new endpoints, remove old create/update.
5. Delete `src/dnd_simulator/content_saver.py`.
6. Update any tests that used the old create_world/update_world flow.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Assembling a world from library templates creates a valid manifest
- [ ] Session can be started from the assembled world
- [ ] Forking copies files and updates manifest to custom
- [ ] Session works after forking a layer
- [ ] Old content_saver.py deleted
- [ ] Old create_world/update_world endpoints removed

## Status

`pending`
