# Task: Paladin Combo Integration Test

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 5 — Smite + Magic Weapon Combo + Polish

## Description

End-to-end proof that the full Paladin combo works: flaming longsword (1d8 slashing + 1d6 fire) + Divine Smite (2d8 radiant) = 3 damage types in one attack, displayed correctly in the event stream, with spell slot consumed on hit.

Changes:
1. **Test content** — Add `flaming_longsword.yaml` to `tests/integration/content/catalogs/items/` (copy from main catalogs).
2. **Integration test** — New `TestPaladinCombat` class in `test_combat_turns.py`:
   - Create Paladin player in combat_test world (level 1 — no spell slots by default)
   - PATCH creature to add spell_slot_1 resource pool (2 uses)
   - Give flaming longsword via master API, equip it in combat
   - Attack target_dummy with `smite_slot_level=1`
   - Verify attack_event has 3 damage component types: slashing, fire, divine_smite (radiant)
   - Verify spell slot consumed (current_uses decremented) via GET creature API
   - Verify spell slots visible in combat awareness (from task 1)

## Tests First

1. **Integration: Paladin attacks with flaming longsword + smite → 3 damage types** — Create Paladin session, setup spell slots and magic weapon, enter combat, attack with smite. On hit: assert damage_components contains sources for weapon (slashing), weapon (fire), and divine_smite. Assert total damage > 0.

2. **Integration: Spell slot consumed after smite hit** — After the smite attack (on hit), GET creature via master API. Assert spell_slot_1 pool has current_uses = original - 1.

3. **Integration: Spell slots visible in turn awareness** — After Paladin creation and PATCH, connect WS, receive turn message. Assert awareness contains `self_resource_pools` with spell_slot_1 entry (depends on task 1).

## Implementation

After tests are red:
- Copy `flaming_longsword.yaml` to integration test catalogs
- Write `TestPaladinCombat` class following existing Fighter/Rogue test patterns
- Use `_create_session` with `char_class="paladin"` and appropriate ability scores (STR 16, CHA 14 for Paladin)
- PATCH resource_pools to inject spell slots (level 1 Paladin doesn't get them naturally)
- Give flaming longsword via POST items endpoint
- Enter combat, equip weapon if needed, attack with smite_slot_level=1
- Assert on damage_components and resource pool state

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Attack with flaming longsword + smite produces 3 distinct damage types in event data
- [ ] Spell slot consumed only on hit
- [ ] Spell slots visible in awareness data

## Status

`pending`
