# Task: Peel player commands off GameService

**Date:** 2026-06-28
**Sprint:** 019-control-plane-prep
**Phase:** 2 — GameService deeper peel + adapter hygiene

## Description

Move the player command group (~176 lines) off the `GameService` facade into a new
`service/commands_player.py` mixin `PlayerCommands`, same pattern as Task 1.

Methods to move (current `game_service.py` line refs):

- `create_player` (~794–901) — builds a `PlayerCharacter` from request data, equips
  starting gear from the item catalog, adds to the entities layer, assigns brain
- `level_up_player` (~902–921)
- `player_status` (~922–970)

These depend on facade state already declared in `GameServiceProtocol`
(`_get_session`, `_get_entities_layer`, `_assign_brains`, `_brain_factory`) plus
`_content_dir` (added to the protocol in Task 1). No new protocol additions needed if
Task 1 landed first.

Behavior-preserving relocation: move bodies verbatim, move only the imports these
methods use (`PlayerCharacter`, `effective_ac` from `rules.modifiers`, `FightingStyle`
type-only import, `PlayerStatusData` dto, `BrainType`, etc.). Leave imports the facade
still needs in place.

## Tests First

Pure refactor guarded by the existing suite. Confirm green before moving; it must
exercise all three methods. Covering files already present:

- `test_game_service_player.py` — create_player, level_up_player, player_status directly
- `test_session_lifecycle.py`, `test_region_encounters.py`,
  `test_time_of_day_encounters.py` — create_player via session setup
- `test_legacy_removal.py` — guards against re-introduced removed endpoints

No new behavior tests (the move must not change behavior). Add a focused test only if a
moved method is found uncovered — spot-check found all three covered.

## Implementation

1. Create `service/commands_player.py` with `class PlayerCommands(GameServiceProtocol)`.
   Move the three methods verbatim with their imports.
2. In `game_service.py`: delete the moved methods, add `PlayerCommands` to the
   `GameService` base list, drop now-unused imports (`PlayerCharacter`, `effective_ac`,
   `PlayerStatusData`, `FightingStyle` if no longer used by the facade).
3. `make check`; fix import-leftover fallout.

Gotcha: `create_player` reads the item catalog via `self._content_dir / "catalogs" / "items"`
— relies on `_content_dir` being in the protocol from Task 1.

## Acceptance Criteria

- [ ] `commands_player.py` created; `create_player` / `level_up_player` / `player_status`
      moved verbatim
- [ ] `GameService` inherits `PlayerCommands`; unused imports removed
- [ ] `game_service.py` line count drops by ~176; facade now ~370 lines total
- [ ] Existing tests still pass (`make check`), mypy strict clean
- [ ] REST `routes_player` behavior unchanged

## Status

`pending`
