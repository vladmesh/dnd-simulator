# Task: Extract AwarenessBuilder from EntitiesLayer

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 2 — God Class Splits

## Description

Extract the 5 awareness-building methods from `EntitiesLayer` into a new `AwarenessBuilder` class in `layers/entities/awareness_builder.py`. These methods query geography, politics, and settlements layers to assemble what a creature perceives — a clear cross-cutting concern that doesn't belong in the entity storage layer.

Methods to extract:
- `build_awareness()` (dispatcher, 7 LOC)
- `build_peaceful_awareness()` (85 LOC) — queries time, weather, region, settlements, territory owner, nearby entities
- `build_combat_awareness()` (72 LOC) — builds combat perception with positions, distances, conditions
- `build_nearby_entities()` (31 LOC) — constructs NearbyEntity list via perceive() and hostility checks
- `_check_faction_hostility()` (32 LOC) — queries politics layer for faction relations

~227 LOC moving out of the 1214-line layer.

`EntitiesLayer` keeps a `self._awareness: AwarenessBuilder` and delegates `build_awareness()` to it. The public signature doesn't change — callers (round.py, service/) still call `entities_layer.build_awareness(creature, query_fn)`.

## Tests First

1. **Peaceful awareness includes location context** — creature at a village location gets awareness with region name, settlement info, weather, time of day, and nearby entities list. Verify the awareness object has all expected fields populated by querying real (stubbed) geography/settlements/politics layers.

2. **Combat awareness includes battle map state** — creature in combat gets awareness with HP, AC, weapon, nearby combatants with distances and directions, round number, and battle map ASCII. Verify positions and distance calculations match the BattleMap state.

3. **Nearby entities list respects hostility** — two creatures from hostile factions at the same location: `build_nearby_entities()` marks them as hostile. Two from the same faction: marked friendly. Verify via faction relation setup.

4. **Faction hostility delegates to politics query** — `_check_faction_hostility()` calls `query_fn` with `QueryType.FACTION_RELATION` and returns the correct hostile/friendly/neutral result.

## Implementation

1. Create `src/dnd_simulator/layers/entities/awareness_builder.py` with class `AwarenessBuilder`.
2. Constructor takes the references it needs: `entities` dict, `location_log` dict, and the `perceive_event` import.
3. Move the 5 methods. They become regular methods on `AwarenessBuilder`. The `query_fn` is passed per-call (same as now).
4. In `layer.py`: instantiate `self._awareness = AwarenessBuilder(self._entities, self._location_log)` in `__init__`. Replace method bodies with delegation: `return self._awareness.build_awareness(creature, query_fn)`.
5. Export `AwarenessBuilder` from `__init__.py` if needed by tests.
6. Existing tests should pass unchanged — the public API on `EntitiesLayer` is preserved.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `layer.py` no longer contains awareness-building logic (only delegation)
- [ ] `awareness_builder.py` has no imports from `layer.py` (no circular deps)

## Status

`done`

## Developer Notes

Extracted 5 methods (build_awareness, build_peaceful_awareness, build_combat_awareness, build_nearby_entities, _check_faction_hostility) into AwarenessBuilder class. The private `_check_faction_hostility` was renamed to `check_faction_hostility` (public on the new class) since tests need direct access. EntitiesLayer delegates via `self._awareness` — public API unchanged. Layer.py: 1214 → 1002 LOC. No old tests modified.
