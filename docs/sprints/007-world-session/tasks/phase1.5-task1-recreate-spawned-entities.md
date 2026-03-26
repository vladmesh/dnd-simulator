# Task: Recreate Spawned Entities from Save Data

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 1.5 — Save/Load Gaps

## Description

`EntitiesLayer.load_state()` silently ignores entities that don't exist in `_entities`. When a creature is spawned at runtime via `POST /creatures`, it gets serialized into the save file, but on load the world is recreated from the template — the spawned creature has no matching entity in the fresh layer, so its data is dropped.

Fix: when `load_state()` encounters an entity ID not in `_entities`, recreate the entity from saved data. This requires:

1. `get_state()` must include `entity_type` discriminator for NPCs and generic Creatures (PlayerCharacter already has `"entity_type": "player"`).
2. `load_state()` must handle missing entities by parsing them from saved data — use `parse_npc` for NPCs, construct `Creature` for monsters.
3. Generic Creatures need enough data serialized: `max_hp`, `ac`, `speed`, `attacks`, `ability_scores`.

## Tests First

Unit tests in `tests/unit/test_entities_layer.py` (or new file `test_entities_load_spawned.py`):

1. **Spawned NPC round-trip**: Create EntitiesLayer with one NPC from template. Call `get_state()`. Add a second NPC's data to the state dict (simulating a spawned NPC in a save file). Call `load_state()` on a fresh layer (only has template NPC). Assert the spawned NPC exists with correct HP, location, role, personality, memory, ai_type.

2. **Spawned Creature (monster) round-trip**: Same pattern but with a generic Creature — verify HP, AC, speed, attacks, ability scores survive the round-trip.

3. **Spawned entity with conditions and inventory**: Spawned NPC has conditions and inventory items. After load, both are present and correct.

## Implementation

1. In `get_state()`: add `"entity_type": "npc"` for Npc instances, `"entity_type": "creature"` for generic Creatures. Also serialize `max_hp`, `ac`, `speed`, `attacks`, `ability_scores` for all Creatures (needed to reconstruct generic creatures; NPCs get these from `parse_npc` but generic creatures don't have a content loader).

2. In `load_state()`: when `entity is None` and `entity_type` is `"npc"` — call `parse_npc(eid, edata)` to create the NPC, then apply mutable state (HP, conditions, etc.) as usual. When `entity_type` is `"creature"` — construct a `Creature` directly from saved fields. Add the new entity via `self.add_entity()`.

3. Existing PlayerCharacter recreation (lines 432-436) already works — don't touch it.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `get_state()` includes `entity_type` for NPCs and Creatures
- [ ] `load_state()` recreates missing NPCs and Creatures from save data

## Status

`done`

## Developer Notes

- `get_state()` now serializes `entity_type` ("npc" / "creature") and structural fields (max_hp, ac, speed, ability_scores, attacks) for all Creatures.
- `load_state()` recreates missing NPCs via `parse_npc()` and missing Creatures directly from saved fields, then falls through to mutable state restoration.
- Mypy required explicit branching for `current_hp` on Creature reconstruction (`.get()` returns `object | None`).
