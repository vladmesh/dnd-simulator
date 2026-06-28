# Task: Peel worldbuilder + content CRUD off GameService

**Date:** 2026-06-28
**Sprint:** 019-control-plane-prep
**Phase:** 2 — GameService deeper peel + adapter hygiene

## Description

Move the disk-based world/content editing group (~500 lines) off the `GameService`
facade into a new `service/commands_worldbuilder.py` mixin `WorldBuilderCommands`,
following the existing `CreatureCommands` / `WorldStateCommands` pattern. This is the
"worldbuilder lens" the next sprint (`control-interfaces`) will slice by role, so it
should land as one cohesive module.

Methods to move (current `game_service.py` line refs):

- **World templates / manifest:** `list_worlds`, `list_library_templates`,
  `list_compatible_library_templates`, `get_world_template`, `assemble_world`,
  `create_empty_world`, `base_worlds`, `fork_world`, `delete_world`,
  `get_world_manifest`, `scaffold_layer`, `fork_layer`
- **Layer files:** `get_layer_files`, `get_layer_file`, `update_layer_file`
- **Content + catalog CRUD:** `list_content_entities`, `get_content_entity`,
  `create_content_entity`, `update_content_entity`, `delete_content_entity`,
  `list_catalog_entries`, `get_catalog_entry`, `create_catalog_entry`,
  `update_catalog_entry`, `delete_catalog_entry`, `list_refs`
- **Private helpers that travel with the group:** `_resolve_layer_path`,
  `_resolve_entity_layer_path`, `_validate_world_id`, `_validate_filename`

Keep these helpers *inside* the mixin — `_resolve_entity_layer_path` calls
`_resolve_layer_path`, and content CRUD + worldbuilder both call `_validate_world_id`,
so co-locating them avoids protocol churn.

`start_game` (stays on the facade) also calls `_validate_world_id`. Since `GameService`
subclasses the mixin, `self._validate_world_id(...)` still resolves at runtime. To keep
mypy honest, add `_content_dir: Path` and the `_validate_world_id` classmethod signature
to `GameServiceProtocol` in `service/base.py` so the facade's own call typechecks.

This is a behavior-preserving relocation. No method bodies change — only their home
module and the imports each one needs (move `content_loader` / `library` /
`content_loader.crud` imports used solely by this group into the new file; leave imports
the facade still uses in place).

## Tests First

This is a pure refactor guarded by a rich existing suite — that suite IS the
characterization net. Before moving anything, confirm it is green and that it exercises
every moved method. Covering files already present:

- `test_world_assembly.py`, `test_partial_manifest.py`, `test_manifest_game_service.py`,
  `test_world_fork_delete.py`, `test_layer_files_api.py`, `test_layer_scaffold.py`,
  `test_legacy_removal.py` — world templates / manifest / layer files
- `test_content_crud.py`, `test_content_api.py` — entity + catalog CRUD + refs
- `test_library_and_assembly.py`, `test_rest_api.py`, `test_api.py` — REST round-trips

Do NOT write new behavior tests for moved code (the move must not change behavior). If a
moved method turns out to have zero coverage, add a focused test for it *before* moving.
Spot-check during planning found none uncovered.

## Implementation

1. Add to `GameServiceProtocol` (`service/base.py`): `_content_dir: Path` attribute and
   `_validate_world_id(cls, world_id: str) -> None` classmethod signature.
2. Create `service/commands_worldbuilder.py` with `class WorldBuilderCommands(GameServiceProtocol)`.
   Move the methods + private helpers listed above verbatim. Pull in only the imports
   those bodies use.
3. In `game_service.py`: delete the moved methods, add `WorldBuilderCommands` to the
   `GameService` base list, drop now-unused imports.
4. Run `make check` (mypy + ruff + unit). Fix any import-leftover / unused-import fallout.

Gotchas:
- `_validate_world_id` / `_validate_filename` are `@classmethod` / `@staticmethod` — preserve decorators on the move.
- `create_player` / `player_status` (Task 2's group) use `_content_dir` for the item
  catalog — that's why `_content_dir` goes in the protocol now, not later.

## Acceptance Criteria

- [ ] `GameServiceProtocol` declares `_content_dir` + `_validate_world_id`; mixin created
- [ ] All listed methods moved verbatim into `commands_worldbuilder.py`; bodies unchanged
- [ ] `GameService` inherits `WorldBuilderCommands`; unused imports removed
- [ ] `game_service.py` line count drops by ~500 (verify with `wc -l`)
- [ ] Existing tests still pass (`make check`), mypy strict clean
- [ ] No new public behavior; REST routes unchanged

## Status

`done`

## Developer Notes

Behavior-preserving peel, landed as planned. GameService 1044 → 541 lines (−503), new
`commands_worldbuilder.py` is 535 lines. The whole group (lines 258–755) was contiguous,
so it moved as one block verbatim — method bodies unchanged, including the method-local
imports and the `_BASE_WORLDS` / `_SAFE_ID_RE` class attributes.

Protocol: added only `_content_dir: Path` to `GameServiceProtocol`. `_validate_world_id`
did NOT need a protocol entry after all — it's defined in the mixin and `start_game`
(facade) reaches it through inheritance, so mypy resolves it via the MRO without a
protocol declaration.

Import fallout in the facade: dropped the whole `content_loader.library` block
(`TemplateInfo`/`list_templates`/`list_compatible_templates`, all moved) and the
TYPE_CHECKING `ContentEntityType`. Every other `content_loader` top-level import stays —
`start_game` still uses nearly all of them. `effective_ac` stays too (player_status, not
yet moved).

Bonus cleanup (not in plan): `commands_creatures.py:159` had
`content_dir: Path = self._content_dir  # type: ignore[attr-defined]` — the ignore was
only there because `_content_dir` wasn't on the protocol. Adding it to the protocol made
the ignore unused (mypy flagged it), so I inlined `self._content_dir` and dropped the now
-unused `Path` import. No behavior change.

`make check` green (backend 2268, frontend 238). No integration tests touched — this is a
pure refactor guarded by the existing unit suite (171 covering tests confirmed green
before and after).
