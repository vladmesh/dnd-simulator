# Task: World creator field

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 1 — Identity & role keystone

## Description

Add a `creator` tag to worlds so the system can record *who made* a template. Pure attribution, not access control — who may view/edit/play is a separate dimension deferred to a future many-to-many model. Data half of the keystone, no enforcement (that's Phase 2+). `creator` is a free-form `user_id` string; an absent creator reads as `""` (unknown authorship). Shipped base worlds carry `creator: system`.

The manifest is parsed as a raw dict (no Pydantic model), so this is straight plumbing through the three manifest-creation sites and the read site:

- `content_loader/assembly.py` — `create_empty_world` (manifest dict ~L98), `assemble_world` (~L60), `fork_world` (~L187): accept a `creator: str = ""` param, write `"creator": creator` into the manifest dict. For `fork_world`, the new world's creator is the *forking* user (param), NOT copied from source.
- `content_loader/manifest.py` — `load_world_meta_from_manifest` (~L66): include `"creator": manifest.get("creator", "")` in the returned meta.
- `service/commands_worldbuilder.py` — `create_empty_world` / `assemble_world` / `fork_world`: add `creator: str = ""` param, pass through to assembly. `list_worlds` (~L38): include `creator` in each returned dict.
- `adapters/api/schemas.py` — `WorldListItem` (~L172): add `creator: str = ""`. `CreateWorldRequest` (~L125) / `AssembleWorldRequest` (~L134): add `creator: str = ""` (so the field round-trips even before the identity seam in task 2 wires it from the caller).
- `adapters/api/routes_world.py` — pass `creator` from request body through to the service for now (task 2 replaces this with the resolved caller identity).

Keep the service param defaulted to `""` so this task is testable on its own and existing header-less callers keep working.

## Tests First

Product-level, exercised at the service + content_loader layer (no HTTP needed):

- **Create stamps creator:** `create_empty_world(world_id, ..., creator="alice")` then `list_worlds()` reports that world with `creator == "alice"`; reading the on-disk `manifest.yaml` shows `creator: alice`.
- **Assemble stamps creator:** assembling a world from library templates with `creator="alice"` persists the creator and the world is still startable (`start_game` succeeds — creator is metadata, not a layer).
- **Fork re-attributes, source untouched:** fork a source world (creator `alice`) with `creator="bob"` → the new world's `creator == "bob"`; the source world's creator is unchanged (`alice`).
- **Backward compat:** `load_world_meta_from_manifest` on a manifest with NO `creator` key returns `creator == ""` and does not raise; a shipped base world (`sword_vale`) loads and lists with `creator == "system"`.

## Implementation

After tests are red: thread the `creator` param through the four files above. The manifest being a raw dict means no schema migration — just add the key on write and `.get("creator", "")` on read. Run the full integration suite — existing tests don't pass `creator`, so they must keep working with the `""` default and the new manifest key must not break any test asserting on world metadata.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check` / integration)
- [ ] `creator` round-trips: write → manifest.yaml → read → `list_worlds`/`get_world_manifest`
- [ ] Fork sets creator to the forking user; source world creator unchanged
- [ ] Worlds without an `creator` key load with `creator == ""` (no crash)

## Status

`done`

## Developer Notes

Mid-task brainstorm changed the field from `owner` → **`creator`**. The distinction matters: `creator` is immutable attribution (who made the template), NOT access control. Sharing/visibility goes the other direction and becomes a future many-to-many (user ↔ resource) model, likely DB-backed — deliberately NOT baked into the manifest now. Public worlds = have a creator, no access restriction.

- Threaded `creator: str = ""` through `assembly.py` (create/assemble/fork), `manifest.py` (read via `.get("creator", "")`), `commands_worldbuilder.py` (3 methods; `list_worlds` surfaces it via `**meta`; `fork_world` return dict gained `creator`), `schemas.py` (`WorldListItem`, `CreateWorldRequest`, `AssembleWorldRequest`), `routes_world.py` (body → service, into `WorldListItem` responses).
- Base/system worlds stamped explicitly: `creator: system` added to `content/worlds/sword_vale/manifest.yaml` and `test_vale/manifest.yaml`. `level_up_test` left unset (reads `""`) — not in `base_worlds`.
- Tests: `tests/unit/test_world_creator.py` (6, all green). No `tests/integration/` touched, so no docker run; `make check` green (2273 backend + 240 frontend).
- Session attribution (`meta.created_by`) was approved in the same brainstorm and folded into **task 2** (identity seam) — see task 2 scope. Decision recorded in sprint Decisions.
