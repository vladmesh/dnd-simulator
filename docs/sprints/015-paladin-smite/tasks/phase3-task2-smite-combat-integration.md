# Task: Divine Smite Combat Integration & Brain Support

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 3 — Divine Smite

## Description

Wire Divine Smite into the combat resolution chain so that when a Paladin attacks with `smite_slot_level` set and hits, the radiant damage is added and the spell slot is consumed. On miss, the slot is NOT spent. Add RuleBrain smite logic: always smite when spell slots available and attacking in melee.

Changes:
- `combat_manager.resolve_attack` reads `smite_slot_level` from event data, validates, builds ExtraDamage, spends slot on hit
- `RuleBrain._try_attack` adds `smite_slot_level` param for Paladins with spell slots
- Action provider: advertise smite availability in LLM context (update ClassFeatureActionProvider or attack hint)
- Perception: `_format_damage` already handles multi-source damage — verify "divine_smite" renders correctly

## Tests First

1. **Smite on hit adds radiant damage and spends slot** — Paladin attacks with `smite_slot_level=1`, hits → AttackResult contains 2d8 radiant DamageResult with source "divine_smite", spell_slot_1 current_uses decremented by 1.
2. **Smite on miss does NOT spend slot** — Paladin attacks with `smite_slot_level=1`, misses → spell_slot_1 unchanged.
3. **Smite with no slots fails** — Paladin with exhausted slots attacks with `smite_slot_level=1` → error result.
4. **Non-Paladin with smite param fails** — Fighter attacks with `smite_slot_level=1` → error result.
5. **RuleBrain smites when slots available** — Paladin RuleBrain with spell slots chooses attack with `smite_slot_level=1` in params.
6. **RuleBrain does NOT smite when no slots** — Paladin RuleBrain with exhausted slots chooses plain attack (no smite param).
7. **Damage components in log** — after smite hit, event log `damage_components` includes entry with source="divine_smite", type="radiant".

## Implementation

1. In `combat_manager.resolve_attack` (after sneak attack check, before `resolve_attack` call):
   - Read `smite_slot_level` from `event.data`
   - If present: call `validate_smite(attacker, slot_level)` — on error, return ActionResult(success=False)
   - Call `build_smite_damage(slot_level)` and append to `extra_damage` tuple
   - After hit confirmed: call `use_resource(attacker, spell_slot_pool_id(slot_level))`
   - Important: slot spent AFTER hit check, not before
2. In `RuleBrain._try_attack`:
   - Import `get_available_spell_slots` from `rules/resources`
   - If creature is Paladin and has spell slots → add `"smite_slot_level": min(available_levels)` to attack params
   - Simple heuristic: always smite in melee. Future: smite on crit only, save slots, etc.
3. Verify perception `_format_damage` handles "divine_smite" source — should work with existing multi-component logic, no changes expected.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Smite damage appears in AttackResult on hit
- [ ] Spell slot consumed only on hit, not on miss
- [ ] RuleBrain Paladin auto-smites when slots available
- [ ] Damage log contains divine_smite component
- [ ] LLM brains see smite option in attack tool schema

## Status

`pending`
