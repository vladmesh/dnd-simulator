# Task: World ownership field

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 1 — Identity & role keystone

## Description

Add an `owner` tag to worlds so the system can record *who* created/owns a world. This is the data half of the keystone — pure plumbing, no enforcement yet (enforcement = Phase 2). `owner` is a free-form `user_id` string; an empty/absent owner means "unowned" (the base/system worlds shipped in `content/worlds/`).

The manifest is parsed as a raw dict (no Pydantic model), so this is straight plumbing through the three manifest-creation sites and the read site:

- `content_loader/assembly.py` — `create_empty_world` (manifest dict ~L98), `assemble_world` (~L60), `fork_world` (~L187): accept an `owner: str = ""` param, write `"owner": owner` into the manifest dict. For `fork_world`, the new world's owner is the *forking* user (param), NOT copied from source.
- `content_loader/manifest.py` — `load_world_meta_from_manifest` (~L66): include `"owner": manifest.get("owner", "")` in the returned meta.
- `service/commands_worldbuilder.py` — `create_empty_world` / `assemble_world` / `fork_world`: add `owner: str = ""` param, pass through to assembly. `list_worlds` (~L38): include `owner` in each returned dict.
- `adapters/api/schemas.py` — `WorldListItem` (~L172): add `owner: str = ""`. `CreateWorldRequest` (~L125) / `AssembleWorldRequest` (~L134): add `owner: str = ""` (so the field round-trips even before the identity seam in task 2 wires it from the caller).
- `adapters/api/routes_world.py` — pass `owner` from request body through to the service for now (task 2 replaces this with the resolved caller identity).

Keep the service param defaulted to `""` so this task is testable on its own and existing header-less callers keep working.

## Tests First

Product-level, exercised at the service + content_loader layer (no HTTP needed):

- **Create stamps owner:** `create_empty_world(world_id, ..., owner="alice")` then `list_worlds()` reports that world with `owner == "alice"`; reading the on-disk `manifest.yaml` shows `owner: alice`.
- **Assemble stamps owner:** assembling a world from library templates with `owner="alice"` persists the owner and the world is still startable (`start_game` succeeds — owner is metadata, not a layer).
- **Fork re-owns, source untouched:** fork a base world (e.g. `sword_vale`) with `owner="bob"` → the new world's `owner == "bob"`; the source world's owner is unchanged (still its original value / `""`).
- **Backward compat:** `load_world_meta_from_manifest` on a manifest with NO `owner` key returns `owner == ""` and does not raise; an existing base world loads and lists fine.

## Implementation

After tests are red: thread the `owner` param through the four files above. The manifest being a raw dict means no schema migration — just add the key on write and `.get("owner", "")` on read. Run the full integration suite — existing tests don't pass `owner`, so they must keep working with the `""` default and the new manifest key must not break any test asserting on world metadata.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check` / integration)
- [ ] `owner` round-trips: write → manifest.yaml → read → `list_worlds`/`get_world_manifest`
- [ ] Fork sets owner to the forking user; source world owner unchanged
- [ ] Worlds without an `owner` key load with `owner == ""` (no crash)

## Status

`pending`
