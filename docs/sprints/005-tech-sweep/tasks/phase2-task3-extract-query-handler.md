# Task: Extract QueryHandler from EntitiesLayer

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 2 — God Class Splits

## Description

Extract the query dispatch and entity detail building from `EntitiesLayer` into a new `QueryHandler` class in `layers/entities/query_handler.py`.

Methods to extract:
- `query()` (125 LOC) — dispatches 13 query types
- `_entity_summary()` (15 LOC) — short dict for entity listings
- `_entity_detail()` (44 LOC) — full dict per entity type
- `_npc_detail()` (14 LOC) — NPC-specific detail

~198 LOC moving out. Also extract the perception log query methods that `query()` delegates to:
- `get_perceived_log()` (10 LOC)
- `get_new_perceived_events()` (13 LOC)
- `get_new_raw_events()` (7 LOC)
- `_event_location()` (19 LOC)

Total ~247 LOC. This is pure data assembly with no side effects — cleanest extraction.

`EntitiesLayer.query()` becomes a one-liner delegating to `self._query_handler.query(query)`.

## Tests First

1. **ENTITIES_AT_LOCATION query returns correct entities** — 3 entities, 2 at location A, 1 at location B. Query for A returns 2 entity summaries with correct fields (id, name, role, activity, location).

2. **ENTITY_INFO query returns full detail** — Character with race, class, HP, AC, equipped weapon. Query returns all fields including computed ones (AC from armor, weapon name).

3. **NPC_INFO query includes personality and AI type** — NPC with personality traits, settlement assignment, and brain type. Query returns all NPC-specific fields.

4. **COMBAT_INFO query returns battle state** — Active combat at a location with 2 combatants. Query returns initiative order, round number, current turn, and combatant details.

5. **PERCEIVED_LOG query filters by observer** — 3 events at a location, observer can perceive 2 of them (based on perception rules). Query returns only the 2 perceived events.

## Implementation

1. Create `src/dnd_simulator/layers/entities/query_handler.py` with class `QueryHandler`.
2. Constructor takes `_entities` dict, `_location_log` dict, `_combat` (CombatManager), and reference to `_materialized_squads`.
3. Move query dispatch and all detail builders. The perception log methods move here too since they're only called from `query()`.
4. In `layer.py`: instantiate `self._query_handler = QueryHandler(...)` in `__init__`. Replace `query()` body with delegation.
5. Keep `get_perceived_log()`, `get_new_perceived_events()`, `get_new_raw_events()` as public methods on QueryHandler — they're also called directly from `round.py` and service layer via the entities layer. Add thin forwarding methods on `EntitiesLayer` that delegate to QueryHandler.
6. Existing tests should pass unchanged.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `layer.py` no longer contains query dispatch or entity detail logic
- [ ] `query_handler.py` has no imports from `layer.py`
- [ ] Remaining `layer.py` is under ~400 LOC (CRUD, combat delegation, handle_event, state persistence)

## Status

`done`

## Developer Notes

Extracted QueryHandler (274 LOC) from EntitiesLayer. layer.py dropped from 656→443 LOC.

Moved:
- `query()` — full dispatch for 13 query types
- `_entity_summary()`, `_entity_detail()`, `_npc_detail()` — detail builders
- `get_perceived_log()`, `get_new_perceived_events()`, `get_new_raw_events()` — perception log methods

EntitiesLayer retains thin forwarding methods for `get_perceived_log`, `get_new_perceived_events`, `get_new_raw_events` since they're called directly by external code (round.py, service layer). `_event_location` stayed in layer.py — it's used by `handle_event`, not by query logic.

`query_handler.py` uses a `_get_entity` callback method for `perceive_event` instead of referencing `EntitiesLayer.get_entity` — no circular dependency.

No old tests modified. 6 new tests added covering ENTITIES_AT_LOCATION, ENTITY_INFO, NPC_INFO, COMBAT_INFO, and PERCEIVED_LOG queries.
