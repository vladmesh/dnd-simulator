# Task: Extract ActivationManager from EntitiesLayer

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 2 — God Class Splits

## Description

Extract activation, encounter, and squad materialization logic from `EntitiesLayer` into a new `ActivationManager` class in `layers/entities/activation_manager.py`.

Methods to extract:
- `update_activation()` (87 LOC) — proximity-based creature activation/dormification
- `_check_encounters()` (38 LOC) — encounter rolls on creature movement to new location
- `_roll_encounters()` (47 LOC) — rolls encounter table, spawns creatures, auto-starts combat
- `_maybe_start_combat()` (29 LOC) — checks hostility between spawned and existing creatures
- `_update_materialization()` (53 LOC) — materializes/dematerializes squads at active locations
- `_materialize_squad()` (47 LOC) — spawns squad creatures from templates
- `_dematerialize_squad()` (52 LOC) — removes squad creatures, updates strength

~353 LOC moving out. This is the largest cluster — self-contained lifecycle logic that runs at round start.

`EntitiesLayer` keeps `self._activation: ActivationManager` and delegates `update_activation()`. The manager needs access to `_entities`, `_monster_templates`, `_encounter_tables`, `_encounter_cooldowns`, `_creature_locations`, `_spawn_counter`, `_materialized_squads`, and `_combat` (for `_maybe_start_combat`).

## Tests First

1. **Proximity activation** — player at location A, NPC at location A (dormant), NPC at location B. After `update_activation()`: NPC at A becomes active, NPC at B stays dormant. Move player to B: NPC at B activates, NPC at A dormifies.

2. **Encounter cooldown respected** — creature moves to a location with an encounter table. First move: encounter roll happens. Move away and back within 600 game-seconds: no roll. Move back after 600+ seconds: roll happens again.

3. **Squad materialization on activation** — squad defined at location A with strength 3. Player arrives at A: 3 creatures spawned. Player leaves: creatures despawned, squad strength preserved. Kill 1 creature, player leaves and returns: only 2 creatures spawned (strength reduced).

4. **Hostile encounter auto-starts combat** — encounter table spawns a hostile creature (via faction relation). Verify combat is started at that location with both the existing creature and the spawned one.

## Implementation

1. Create `src/dnd_simulator/layers/entities/activation_manager.py` with class `ActivationManager`.
2. Constructor takes references to the shared state dicts (entities, templates, cooldowns, etc.) and `CombatManager`.
3. Move the 7 methods. `update_activation()` is the public entry point; rest are private.
4. In `layer.py`: instantiate `self._activation = ActivationManager(...)` in `__init__`. Replace `update_activation()` with delegation.
5. The spawn counter must be shared (manager increments it, layer reads it) — pass as a mutable container or sync after call.
6. Existing integration tests (test_game_loop.py, test_materialization.py, test_spawn_engine.py) should pass unchanged.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `layer.py` no longer contains activation/encounter/materialization logic
- [ ] `activation_manager.py` has no imports from `layer.py`

## Status

`done`

## Developer Notes

Extracted 7 methods into ActivationManager class (402 LOC). Layer.py: 1002→656. The `_spawn_counter` now lives on ActivationManager (shared entity dict means spawned creatures are visible to layer). Old tests in test_spawn_engine.py patched `layer.random` — updated to `activation_manager.random`. One test in test_squad_events.py called `layer._materialize_squad()` directly — updated to `layer._activation._materialize_squad()`. No behavioral changes.
