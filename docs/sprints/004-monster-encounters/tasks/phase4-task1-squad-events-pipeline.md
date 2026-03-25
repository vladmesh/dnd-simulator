# Task: Squad Events in Perception Pipeline

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 4 — Frontend + E2E

## Description

Squad events (`SQUAD_MOVE`, `SQUAD_COMBAT`, `SQUAD_MATERIALIZED`, `SQUAD_DEMATERIALIZED`) are emitted by EcologyLayer but never reach the player. Three breaks in the pipeline:

1. `_LOGGED_EVENTS` in EntitiesLayer doesn't include squad event types → events are not stored in the location log
2. `_event_location()` resolves location via entity ID keys (`entity_id`, `attacker_id`) — squad events store `location_id` directly in `data`, so it returns `None`
3. `perceive_event()` has no handlers for squad events → falls through to "Something happened"
4. `_materialize_squad()` doesn't emit a `SQUAD_MATERIALIZED` event at all (only logs to structlog)

Fix all four so squad events appear as `PerceivedEvent` in the WebSocket stream.

## Tests First

1. **Squad movement event reaches player's location log** — Create EntitiesLayer with a player at location "forest_road". Emit a `SQUAD_MOVE` event with `data={"squad_id": "orc_patrol", "squad_name": "Orc Patrol", "from": "swamp", "to": "forest_road"}`. Call `get_perceived_events(player)` → returns one event with `event_type=EventType.SQUAD_MOVE` and a description mentioning the squad arriving.

2. **Squad combat event perceived at location** — Emit a `SQUAD_COMBAT` event with `data={"location_id": "forest_road", "winner_id": "guards", "winner_name": "Town Guard", "loser_id": "wolves", "loser_name": "Wolf Pack", "winner_strength": 12, "loser_strength": 0}`. Player at forest_road gets a perceived event describing the combat outcome.

3. **Squad materialization emits event** — Call `_materialize_squad()` for a squad at the player's location. Verify a `SQUAD_MATERIALIZED` event is emitted with `squad_id`, `squad_name`, `location_id`, and `creature_count`. Verify it appears in `get_perceived_events(player)`.

4. **Squad events at other locations don't leak to player** — Emit `SQUAD_MOVE` with `to: "distant_cave"`. Player at "forest_road" gets no squad events.

5. **Integration: ecology tick → perceived events** — Build full World with EcologyLayer containing a patrol squad. Advance time by 1 hour. If squad moved, verify the player at the destination gets a `SQUAD_MOVE` perceived event.

## Implementation

1. **Add squad names to events** — EcologyLayer's `tick()` must include `squad_name` in `SQUAD_MOVE` and `SQUAD_COMBAT` event data (currently only has IDs). Same for `_materialize_squad` and `_dematerialize_squad`.

2. **Add squad events to `_LOGGED_EVENTS`** in `layers/entities/layer.py`:
   ```python
   EventType.SQUAD_MOVE,
   EventType.SQUAD_COMBAT,
   EventType.SQUAD_MATERIALIZED,
   EventType.SQUAD_DEMATERIALIZED,
   ```

3. **Fix `_event_location()`** — add fallback to `event.data.get("location_id")` when entity-based resolution fails. For `SQUAD_MOVE`, the relevant location is `data["to"]` (where the squad arrived).

4. **Emit `SQUAD_MATERIALIZED` event** from `_materialize_squad()`:
   ```python
   Event(
       event_type=EventType.SQUAD_MATERIALIZED,
       source_layer="entities",
       data={"squad_id": ..., "squad_name": ..., "location_id": ..., "creature_count": ...},
       description=f"Squad {name} materialized",
   )
   ```

5. **Add perception handlers** in `layers/entities/perception.py`:
   - `SQUAD_MOVE` → "Orc Patrol passes through" / "Orc Patrol arrives" / "Orc Patrol departs" depending on observer's location vs from/to
   - `SQUAD_COMBAT` → "Town Guard defeated Wolf Pack" / "Wolf Pack destroyed"
   - `SQUAD_MATERIALIZED` → "An Orc Patrol appears — 4 creatures materialize"
   - `SQUAD_DEMATERIALIZED` → "The patrol moves on, disappearing into the distance"

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Squad events appear in `get_perceived_events()` output with correct descriptions
- [ ] Events are location-scoped — only observers at the right location see them

## Status

`done`

## Developer Notes

Four fixes applied:
1. Added 4 squad event types to `_LOGGED_EVENTS` in EntitiesLayer
2. `_event_location()` extended with fallback to `data["to"]` for SQUAD_MOVE and `data["location_id"]` for other squad events
3. SQUAD_MOVE logged at BOTH origin and destination locations (so observers at either end see the event)
4. `_materialize_squad()` now writes a `SQUAD_MATERIALIZED` event directly to the location log
5. `_dematerialize_squad()` event enriched with `squad_name` and `location_id`
6. EcologyLayer events enriched with `squad_name` and `winner_name`/`loser_name`
7. Four perception handlers added: `_perceive_squad_move` (context-aware: arrives/departs/passes through), `_perceive_squad_combat`, `_perceive_squad_materialized`, `_perceive_squad_dematerialized`
