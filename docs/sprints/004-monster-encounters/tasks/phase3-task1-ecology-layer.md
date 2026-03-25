# Task: EcologyLayer Skeleton + Squad Ownership

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 3 — Squad Movement + Materialization

## Description

Create `EcologyLayer` implementing the `Layer` ABC. Move squad storage from `EntitiesLayer` (where it's stored but never used) to `EcologyLayer`. Register in World between Settlements and Entities (index 3). Expose squad queries so EntitiesLayer (above) can read squad data for materialization in Task 3.

Layer order after this task:
```
[geography(0), politics(1), settlements(2), ecology(3), entities(4)]
```

EcologyLayer can query down: geography, politics, settlements.
EntitiesLayer can query down: everything including ecology.

## Tests First

1. **EcologyLayer initializes with squads and exposes them via query** — create layer with 2 squads, query `SQUADS_AT_LOCATION` for a location where one squad starts → get that squad's info back. Query a location with no squads → empty list.

2. **EcologyLayer serializes and restores squad state** — create layer with squads, call `get_state()`, modify a squad's location/strength, call `load_state()` with saved state → squad is back to original location/strength.

3. **EcologyLayer integrates into World layer stack** — build a World with all 5 layers, verify EcologyLayer ticks when time advances, verify EntitiesLayer can query ecology for squad data via `query_fn`.

4. **GameService loads squads into EcologyLayer** — start a game with sword_vale content, verify squads exist on EcologyLayer (via query), verify EntitiesLayer no longer receives squads.

## Implementation

1. Create `src/dnd_simulator/layers/ecology/__init__.py` and `layer.py`.
2. Add `QueryType.SQUADS_AT_LOCATION` and `QueryType.SQUAD_INFO` to `core/models.py`.
3. Implement `EcologyLayer`:
   - `name = "ecology"`
   - `tick_interval = 3600` (1 hour — movement tick, actual movement logic in Task 2)
   - `tick()` — no-op for now (Task 2 adds movement)
   - `handle_event()` — no-op for now
   - `query()` — handle `SQUADS_AT_LOCATION(location_id)` → list of squad dicts, `SQUAD_INFO(squad_id)` → squad dict
   - `get_state()` / `load_state()` — serialize squad `current_location_id` and `strength` (the mutable fields)
4. Remove `squads` parameter from `EntitiesLayer.__init__()` and `self._squads`.
5. Update `GameService.start_game()`: create `EcologyLayer(squads=squads)`, insert into layer list at index 3 (before entities).
6. Update any existing tests that pass squads to EntitiesLayer.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] EcologyLayer registered in World between settlements and entities
- [ ] Squads no longer stored on EntitiesLayer
- [ ] Squad state survives save/load cycle

## Status

`done`

## Developer Notes

Clean migration — squads were stored on EntitiesLayer but never used there (no queries, no serialization, no logic). Removed `squads` param from EntitiesLayer, created EcologyLayer with squad ownership. Layer stack is now [geography, politics, settlements, ecology, entities]. Added `QueryType.SQUADS_AT_LOCATION` and `QueryType.SQUAD_INFO`. No existing tests broke because no tests were passing squads to EntitiesLayer.
