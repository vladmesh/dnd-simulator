# Task: Spawn Engine + Temporary Creature Lifecycle

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 1 — Spawn Foundation

## Description

Build the runtime spawn engine: when a player enters a location with an encounter table, roll for each entry, spawn temporary Creatures from MonsterTemplates. Add a `temporary` flag to Entity so spawned monsters can be distinguished from persistent NPCs. Clean up temporary creatures on death (remove from EntitiesLayer).

**Spawn trigger:** EntitiesLayer.handle_event() intercepts ENTITY_MOVE events. When the moving entity is a PlayerCharacter and the destination has encounter entries, roll each entry's chance. On success, instantiate `count` Creatures from the template, add them to the layer. Add a cooldown per location to prevent re-rolling every time the player re-enters (e.g. store last-rolled time, skip if < N rounds ago).

**Creature instantiation:** `MonsterTemplate.spawn(location_id) → Creature` — creates a Creature with the template's stats, attacks, HP. Sets `temporary = True`. Brain assigned by the caller (RuleBrain).

**Death cleanup:** When a temporary creature dies (ENTITY_DIED event for an entity with `temporary=True`), remove it from the layer. This happens in handle_event().

**Spawn event:** Emit a new `ENCOUNTER_SPAWNED` event so the log shows what appeared.

## Tests First

1. Player moves to a location with an encounter table, RNG returns success → correct number of Creatures spawned at that location with stats matching the template.
2. Player moves to a location with an encounter table, RNG returns failure → no creatures spawned.
3. Spawned creatures have `temporary=True`, correct HP/AC/speed/attacks from template.
4. Temporary creature dies → automatically removed from EntitiesLayer (no longer in `_entities`).
5. Non-temporary creature dies → NOT removed (existing behavior preserved).
6. Player re-enters same location within cooldown → no new spawn roll.
7. Player enters location after cooldown expires → new spawn roll happens.

## Implementation

- `core/character.py` — add `temporary: bool = False` field to Entity
- `core/monster.py` — add `MonsterTemplate.spawn(location_id, id_suffix) → Creature` factory method
- `core/models.py` — add `ENCOUNTER_SPAWNED` to EventType
- `layers/entities/layer.py` — intercept ENTITY_MOVE in handle_event, spawn logic, death cleanup for temporary entities
- Encounter state tracking: `_encounter_cooldowns: dict[str, int]` (location_id → last_spawn_time) on EntitiesLayer
- RNG: use `random.random()` for chance rolls, `random.randint()` for count — injectable for testing

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Spawned creatures appear at the correct location with template stats
- [ ] Temporary creatures cleaned up on death
- [ ] Cooldown prevents spam-spawning on repeated location entry
- [ ] ENCOUNTER_SPAWNED event emitted with details (monster names, count)

## Status

`done`

## Developer Notes

Deviated from task plan: ENTITY_MOVE events are combat-only (grid movement). Peaceful travel uses `handle_wait(travel_to=...)` which sets `location_id` directly with no event. Hooked encounter checks into `update_activation()` instead — tracks `_player_locations` dict and detects when a player's location changes. Spawn logic in `_check_encounters()` → `_roll_encounters()`. Death cleanup added to `handle_event()` for ENTITY_DIED events on temporary entities. Wired `load_monsters()` into GameService.start_game(). Cooldown is 600 seconds (10 minutes game time).
