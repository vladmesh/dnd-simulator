# Task: AwarenessBuilder unit tests

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 5 — Test Gaps

## Description

AwarenessBuilder (273 LOC) has 7 tests that cover the happy path. Missing: query failure handling, edge cases in nearby entity filtering, combat awareness detail coverage (conditions, wound state, walls, dead creature exclusion), NPC schedule-based location resolution.

No code changes — only new tests in `tests/unit/test_awareness_builder.py`.

## Tests First

### Peaceful awareness — query resilience

- Geography query for region raises exception → awareness still builds with fallback defaults (location_id as region_name, default weather)
- Region resolves but weather query fails → region_name correct, weather falls back to clear/15
- Region resolves but settlements query returns empty list → settlements is empty list, not None
- Region found, politics query fails → territory_owner is None, nation_info is None

### Peaceful awareness — NPC schedule location

- NPC with schedule: `current_location(hour)` determines both the NPC's own location_name in awareness AND where it appears as nearby to others. Two NPCs at different schedule locations at the same hour → each sees only entities at their own scheduled location, not location_id.

### Combat awareness — entity filtering and detail

- Dead creature (current_hp=0) at same combat location → excluded from nearby list
- Inactive creature at same location → excluded from nearby list
- Creature at different location → excluded even if in_combat
- Nearby enemy has conditions (e.g. poisoned, prone) → CombatEntity.conditions includes them
- Nearby enemy is wounded (hp < max_hp/2) → is_wounded=True; at exactly half → is_wounded=False

### Combat awareness — battle map

- Combat with walls on battle map → wall_descriptions is non-empty list
- No combat object for creature's location → round_number=1, empty nearby, no walls, no ascii

### Nearby entities — edge cases

- Observer and target both have no faction_id → is_hostile=False, politics never queried
- query_fn is None → hostility check returns False without error
- Politics query raises → is_hostile=False (graceful degradation), no crash

## Implementation

All tests go into `tests/unit/test_awareness_builder.py`. Use the existing test helpers and patterns (direct `EntitiesLayer` construction, stub `query_fn` closures, `_scores()` helper). For combat tests, construct `CombatState` + `BattleMap` manually and inject into `layer._combat._combats`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation — N/A, these are coverage tests for existing code, they should be GREEN immediately)
- [ ] All new tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] No mocks of internal AwarenessBuilder methods — only external boundaries (query_fn)

## Status

`pending`
