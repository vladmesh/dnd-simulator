# Task: Divine Smite Rules & Attack Param

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 3 — Divine Smite

## Description

Create the pure rules module for Divine Smite and extend the attack action schema to carry smite intent.

Divine Smite = on weapon melee hit, spend a spell slot → +2d8 radiant damage (1st-level slot). Slot is only spent on hit. Scaling by slot level (+1d8 per level above 1st) and bonus vs undead/fiend are deferred (`divine-smite-scaling` backlog).

Design: smite is an optional `smite_slot_level` integer param on the existing `attack` ActionDef. Not a separate ActionType. The brain declares intent when choosing attack; combat_manager handles the rest.

Changes:
- New `rules/divine_smite.py` with pure functions
- Extend attack ActionDef with optional `smite_slot_level` param
- `handle_attack` forwards `smite_slot_level` in event data

## Tests First

1. **Smite damage calculation** — `build_smite_damage(slot_level=1)` returns `ExtraDamage(dice="2d8", type=RADIANT, source="divine_smite")`.
2. **Smite validation: Paladin with slots** — `validate_smite(paladin_with_slots, slot_level=1)` returns None (no error).
3. **Smite validation: no spell slots** — `validate_smite(paladin_no_slots, slot_level=1)` raises/returns error.
4. **Smite validation: non-Paladin** — `validate_smite(fighter, slot_level=1)` raises/returns error.
5. **Smite validation: invalid slot level** — `validate_smite(paladin, slot_level=0)` raises/returns error. Same for levels the Paladin doesn't have pools for.

## Implementation

1. Create `src/dnd_simulator/rules/divine_smite.py`:
   - `build_smite_damage(slot_level: int) -> ExtraDamage` — returns `ExtraDamage(dice=f"{1 + slot_level}d8", type=DamageType.RADIANT, source="divine_smite")`
   - `validate_smite(creature: Creature, slot_level: int) -> str | None` — checks: is Character with PALADIN class, has `spell_slot_{level}` pool with uses remaining. Returns error string or None.
2. Extend attack `ActionDef` in `core/action_defs.py`: add `ParamDef("smite_slot_level", "integer", ...)` (not required).
3. Update `handle_attack` in `rules/handlers/combat.py`: forward `smite_slot_level` from `action.params` into event data (only if present).
4. Update attack `llm_hint` to mention smite option for Paladins.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `build_smite_damage` returns correct ExtraDamage for slot level 1
- [ ] `validate_smite` rejects non-Paladins, empty pools, invalid levels
- [ ] Attack ActionDef includes optional `smite_slot_level` param
- [ ] `handle_attack` forwards smite param in event data

## Status

`done`

## Developer Notes

Straightforward implementation following the sneak_attack.py pattern. `validate_smite` returns error string (not raises) to match the pattern used by combat_manager for graceful error handling. Level 1 Paladin correctly has no spell slots (half-caster table starts at level 2), so smite validation rejects them. Attack handler forwards `smite_slot_level` only when present in params — no overhead for non-smite attacks.
