# Task: Dead-code removal + backlog reconcile

**Date:** 2026-06-29
**Sprint:** 019-control-plane-prep
**Phase:** 3 — Visible gaps + backlog reconcile + dead code

## Description

Remove dead functions that exist only for their tests, and reconcile backlog entries that code review found already-fixed or obsolete.

### Remove dead code (function + its tests)

Each of these has zero production callers (only test references). Delete the function and the tests that exercise it; if a test file's only purpose was the dead function, remove the now-empty test class.

- **`dead-refund`** — `core/turn_budget.py:58` `TurnBudget.refund()`. Test ref: `tests/unit/test_opportunity_attack.py:187`.
- **`dead-walk-path`** — `rules/movement.py:201` `walk_path()`. Test refs: `tests/unit/test_move_to.py` (lines 88,112,119,127,136,141,145) and `tests/unit/test_movement.py:175`. Check none of those tests also assert other movement behavior before deleting — drop only the `walk_path` assertions/cases. (`move_to` is driven by `compute_reachable` + `step_cost` in the handler, not `walk_path`.)
- **`dead-prone-stand-cost`** — `rules/conditions.py:27` `prone_stand_cost()`. Test refs: `tests/unit/test_conditions.py:83,86` (and the import at line 25 / module docstring at line 5).
- **`dead-to-save-data`** — `core/player.py:74` `to_save_data()`. Test refs: `tests/unit/test_character.py:321`, `tests/unit/test_xp_grant_on_kill.py:185`. Confirm the real save path is `PlayerCharacter` serialization elsewhere (it is — sessions persist via the store), so this method is genuinely orphaned.

After removal, `grep -rn` for each symbol must return nothing in `src/` and `tests/`.

### Reconcile backlog (no code change — verified during Phase 3 planning)

Edit `docs/BACKLOG.md`, mark these with the project's `[x] ... ~~strikethrough~~ FIXED/OBSOLETE Sprint 019 phase 3` convention:

- **`dead-can-opportunity-attack`** — already removed (commit 67f057b "audit triage"); `rules/reactions.py` now only defines `find_oa_triggers`. Mark FIXED.
- **`battle-map-configs-not-wired`** — wired: `game_service.py:171-183` builds `battle_map_configs` via `_flatten_region_defaults(load_battle_maps(...))` and passes it to the `EntitiesLayer`. Mark FIXED (Sprint 018 wiring).
- **`player-character-no-attacks`** — symptom gone: `create_player` (`commands_player.py:79-85`) loads `starting_equipment` weapons, so players fight via `get_weapon_attack()`, not unarmed-for-1. The `attacks` field on `CreatePlayerRequest` is vestigial for player creation (raw `attacks` is the monster/spawn path). Mark FIXED (Sprint 013 char-creation), note the field is unused for players.
- **`look-action-i18n-hardcode`** — obsolete: `_cmd_look` was removed in an earlier refactor (no `Terrain:`/`Weather:` strings remain in `service/`; only stale `.po` msgids, which Task 1's `make messages` will mark obsolete). Mark OBSOLETE.

## Tests First

This task is removal + doc edits, so there are no new product behaviors to assert. The "test" is the existing suite staying green after the dead code and its tests are removed.

- Before removing, run `make check` and confirm green (baseline).
- Remove each function + its test references together so the suite never references a deleted symbol.
- `grep` confirms each symbol is gone from `src/` and `tests/`.

## Implementation

- Delete the four functions and their direct tests/imports. Keep test files that have other coverage; only prune the dead-function cases.
- Watch for module docstrings that list the removed function (e.g. `test_conditions.py:5`) — update them.
- `docs/BACKLOG.md`: flip the four reconcile entries.

## Acceptance Criteria

- [ ] `refund`, `walk_path`, `prone_stand_cost`, `to_save_data` removed; `grep` finds no references in `src/`/`tests/`
- [ ] Their tests removed/pruned without breaking sibling tests
- [ ] `docs/BACKLOG.md` reconcile entries marked (`dead-can-opportunity-attack`, `battle-map-configs-not-wired`, `player-character-no-attacks`, `look-action-i18n-hardcode`)
- [ ] `make check` green

## Status

`pending`
