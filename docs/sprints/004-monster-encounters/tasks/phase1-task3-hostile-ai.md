# Task: Hostile AI — RuleBrain Initiates Combat

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 1 — Spawn Foundation

## Description

Make hostile creatures attack on sight. Currently RuleBrain peaceful mode only responds to speech — hostile creatures just stand there until attacked. Add a `hostile` flag to Creature and modify RuleBrain's peaceful behavior: if the creature is hostile and there's a valid target (PlayerCharacter) at the same location, choose ATTACK instead of END_TURN.

**Hostile flag:** Add `hostile: bool = False` to Creature. MonsterTemplate.spawn() sets this to True. Lair monsters (Phase 2) will also set it via YAML.

**RuleBrain change:** In `_choose_peaceful_action()`, before the speech-response logic, check: if `creature.hostile` and there's a PlayerCharacter (or any non-hostile creature) nearby → return Attack action targeting the nearest one. This triggers combat automatically (existing mechanic: first attack creates CombatState).

**Target selection:** In peaceful mode, pick the closest PlayerCharacter. If multiple, pick randomly or by distance. Don't overthink — combat targeting already handles priority once combat starts.

## Tests First

1. Hostile creature at same location as player, peaceful mode → chooses ATTACK targeting the player.
2. Non-hostile creature at same location as player, peaceful mode → does NOT attack (existing behavior: END_TURN or speech response).
3. Hostile creature at location with no valid targets (only other hostile creatures) → END_TURN, not friendly fire.
4. Hostile creature attacks player → combat starts automatically (integration: verify CombatState created after the attack action is dispatched).
5. Full encounter flow (integration): player moves to encounter location → monsters spawn → next round monsters are active → they attack → combat starts.

## Implementation

- `core/character.py` — add `hostile: bool = False` to Creature
- `core/brain.py` — modify `RuleBrain._choose_peaceful_action()`: check hostile + nearby targets before speech logic
- `core/monster.py` — `MonsterTemplate.spawn()` sets `hostile=True`
- `core/awareness.py` — ensure PeacefulAwareness includes enough info to identify target entity IDs and types (may already have this via `nearby` field)

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Hostile creatures attack players on their first peaceful turn
- [ ] Non-hostile NPCs unaffected (no regression)
- [ ] Combat auto-starts from the hostile attack (existing mechanic, just verify)
- [ ] End-to-end: spawn → hostile turn → combat begun

## Status

`superseded`

## Developer Notes

Pre-pivot task from original Phase 1 ("Spawn Foundation"). Sprint was pivoted to living world architecture on 2026-03-25. Hostile AI moved to Phase 2 of the new plan with faction-aware targeting instead of a simple `hostile` flag. This task file is no longer active.
