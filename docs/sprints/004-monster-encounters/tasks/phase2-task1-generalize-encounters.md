# Task: Generalize Encounter Triggers

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 2 — Generalize Encounters + Hostile AI

## Description

Refactor `_check_encounters` to trigger for **any active creature** that changes location, not just `PlayerCharacter`. Currently the method filters on `isinstance(e, PlayerCharacter)` — replace with an `active` check and location-change tracking for all creatures.

Key changes:
- `_player_locations` dict → `_creature_locations` (track all active creatures)
- Drop the `PlayerCharacter` isinstance check — any active `Creature` whose location changed triggers encounter rolls
- Spawned encounter creatures should still get `RuleBrain`, `temporary=True`, `active=True`
- Cooldown stays per-location (unchanged)

## Tests First

Scenarios to cover (product-level):

1. **NPC moves to dangerous location → encounters spawn.** An active NPC (not PlayerCharacter) moves to a location with an encounter table. Encounter creatures appear at that location.
2. **Dormant creature moves → no encounters.** A creature with `active=False` changes location. No encounter roll happens.
3. **Player still triggers encounters.** Existing behavior preserved — PlayerCharacter moving to encounter zone spawns monsters (regression).
4. **Cooldown applies per-location regardless of who triggered.** Player triggers encounter at forest. NPC arrives at same forest within cooldown window. No second roll.
5. **Spawned encounter creature moving doesn't self-trigger.** A temporary encounter creature that spawns at location X doesn't trigger a second encounter roll at X.

## Implementation

- Rename `_player_locations` → `_creature_locations` in `EntitiesLayer`
- In `_check_encounters`: iterate all active `Creature` instances, track their previous location, roll encounters on location change
- Keep cooldown logic identical
- Update `update_activation` call site (third pass) to pass active creature locations instead of player-only locations

## Acceptance Criteria

- [ ] Tests written and RED
- [ ] Implementation makes tests GREEN
- [ ] `make check` passes
- [ ] NPC arriving at encounter zone triggers spawns
- [ ] Dormant creatures don't trigger encounters
- [ ] Existing player encounter tests still pass

## Status

`pending`
