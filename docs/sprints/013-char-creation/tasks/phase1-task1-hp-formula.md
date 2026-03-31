# Task: HP Formula + Hit Dice

**Date:** 2026-04-01
**Sprint:** 013-char-creation
**Phase:** 1 — HP Formula + Starting Equipment Rules

## Description

Add `calculate_max_hp(char_class, level, con_modifier)` to a new `rules/character_creation.py`. D&D 5e formula: level 1 = max hit die + CON modifier (min 1 total HP). Higher levels: max die at L1 + (level-1) × (die_avg_rounded_up + CON mod), min 1 per level. Hit dice mapping: Fighter d10, Rogue d8. Other classes can get placeholder values but only Fighter/Rogue matter now.

## Tests First

In `tests/unit/test_character_creation.py`:

- Fighter L1, CON 14 (+2) → max HP 12 (10 + 2)
- Fighter L1, CON 8 (−1) → max HP 9 (10 − 1)
- Rogue L1, CON 12 (+1) → max HP 9 (8 + 1)
- Rogue L1, CON 6 (−2) → max HP 6 (8 − 2)
- Fighter L1, CON 1 (−5) → max HP 5 (10 − 5, but min 1... actually 5 > 1 so fine)
- Fighter L3, CON 14 (+2) → 12 + 2×(6+2) = 28 (avg d10 = 5.5, rounded up = 6)
- Rogue L5, CON 10 (+0) → 8 + 4×5 = 28 (avg d8 = 4.5, rounded up = 5)
- Unknown class (WIZARD) with no hit die defined → RuntimeError

## Implementation

New file `src/dnd_simulator/rules/character_creation.py`:
- `HIT_DICE: dict[CharClass, int]` mapping (Fighter→10, Rogue→8)
- `calculate_max_hp(char_class: CharClass, level: int, con_modifier: int) -> int`
- Fail-fast: unknown class → RuntimeError, level < 1 → RuntimeError

## Acceptance Criteria

- [ ] Tests written and RED
- [ ] Implementation makes tests GREEN
- [ ] `make check` passes
- [ ] Fighter and Rogue HP correct at L1 and higher levels
- [ ] Unknown class raises RuntimeError

## Status

`done`

## Developer Notes

Straightforward implementation. `HIT_DICE` dict maps CharClass to die size (Fighter→10, Rogue→8).
`calculate_max_hp` uses D&D 5e formula with min 1 HP per level and min 1 total at L1.
The `die_avg` is `ceil(die/2) + 1` which gives d10→6, d8→5 matching PHB averages.
No existing code touched — new module + new test file only.
