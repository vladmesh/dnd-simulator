# Task: Unit Tests — Combat Mechanics Coverage

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 4 — Content & Tests

## Description

Fill gaps in unit test coverage for Sprint 001 + Sprint 011 mechanics. Focus on product-level behavior chains, not implementation details.

## Tests First

**GWF reroll mechanics (not just the flag):**
- A Fighter with GWF and a greatsword (2d6) rolls damage. Dice showing 1 or 2 are rerolled once. The `DiceResult` records `original` value on rerolled dice. Final total uses rerolled values.
- GWF does NOT reroll dice showing 3+.
- GWF does NOT apply to one-handed weapons.

**Sneak attack damage application:**
- A Rogue with rapier (finesse) and advantage hits a target. Damage = weapon dice (1d8) + DEX mod + sneak attack dice (1d6). The `DamageResult` includes sneak attack as a separate component.
- A Rogue without advantage and without adjacent ally — no sneak attack dice added.
- A Rogue with 3 sneak_attack_dice deals 3d6 extra.

**Weapon property interactions:**
- Versatile weapon: when no shield equipped, could use versatile_damage (future — test that the property exists and is parsed correctly from catalog).
- Two-handed weapon blocks Dueling style bonus (+0, not +2).
- Finesse weapon uses higher of STR/DEX for attack modifier.
- Light weapon property is preserved through catalog loading.

**Full attack pipeline composition:**
- Fighter (STR 16, level 5, dueling, longsword +1) attacks AC 15: attack roll = d20 + STR(+3) + prof(+3) + magic(+1) = d20+7. Damage = 1d8 + STR(+3) + dueling(+2) + magic(+1) = 1d8+6.
- Rogue (DEX 16, level 3, rapier, advantage) attacks: attack roll with advantage (roll twice, take higher) + DEX(+3) + prof(+2). On hit: 1d8 + DEX(+3) + 2d6 sneak attack.
- Creature with no proficiency in weapon: attack roll = d20 + ability mod only (no prof bonus).

## Implementation

- Add tests to existing test files where they fit (test_modifiers.py, test_sneak_attack.py, test_structured_dice.py, test_proficiency.py)
- Create `test_combat_pipeline.py` for end-to-end attack composition tests that exercise multiple rules layers together
- Mock only randomness (dice rolls), let all rules layers compose naturally
- Verify all new tests RED before any implementation fixes needed

## Acceptance Criteria

- [ ] Tests written and RED where implementation gaps exist
- [ ] Any implementation gaps found are fixed to make tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] GWF reroll tested at dice level (not just flag)
- [ ] Sneak attack damage tested through combat pipeline
- [ ] Full attack modifier chain tested (proficiency + fighting style + magic + ability)

## Status

`done`

## Developer Notes

All 25 tests pass immediately — these cover already-implemented mechanics (GWF, sneak attack, finesse, proficiency, fighting styles). No implementation gaps found. Tests were added to a new `test_combat_pipeline.py` rather than scattered across existing files, as the task's main value is end-to-end composition tests that exercise multiple rules layers together (attack_modifiers → resolve_attack → damage breakdown). Catalog property preservation tests verify YAML → Pydantic → WeaponDef pipeline for is_light, is_finesse, is_two_handed, is_heavy.
