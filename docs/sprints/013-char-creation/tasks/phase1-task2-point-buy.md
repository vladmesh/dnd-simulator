# Task: Point Buy Validation

**Date:** 2026-04-01
**Sprint:** 013-char-creation
**Phase:** 1 — HP Formula + Starting Equipment Rules

## Description

Add `validate_point_buy(scores: dict[Ability, int])` to `rules/character_creation.py`. D&D 5e point buy: 27 points budget, each ability 8–15, cost table: 8→0, 9→1, 10→2, 11→3, 12→4, 13→5, 14→7, 15→9. Raises ValueError with descriptive message on invalid input.

## Tests First

In `tests/unit/test_character_creation.py`:

- Standard array {15, 14, 13, 12, 10, 8} → valid (0+2+4+5+7+9 = 27)
- All 13s {13,13,13,13,13,13} → invalid (5×6 = 30 > 27)
- All 8s → valid (cost 0, 27 unspent is fine — underspending allowed? Or must spend exactly 27? D&D says ≤27. Let's allow underspending.)
- Score 16 in any ability → ValueError (above max 15)
- Score 7 in any ability → ValueError (below min 8)
- Missing ability (only 5 provided) → ValueError
- Balanced build {14, 14, 14, 10, 8, 8} → cost 7+7+7+2+0+0 = 23 → valid (underspent)
- Exact max {15, 15, 15, 8, 8, 8} → cost 9+9+9+0+0+0 = 27 → valid
- One over budget {15, 15, 15, 9, 8, 8} → 9+9+9+1+0+0 = 28 → ValueError

## Implementation

In `rules/character_creation.py`:
- `POINT_BUY_COSTS: dict[int, int]` — cost table
- `POINT_BUY_BUDGET = 27`
- `validate_point_buy(scores: dict[Ability, int]) -> None` — raises ValueError on invalid, returns None on valid
- Check: all 6 abilities present, each in [8, 15], total cost ≤ 27

## Acceptance Criteria

- [ ] Tests written and RED
- [ ] Implementation makes tests GREEN
- [ ] `make check` passes
- [ ] Valid builds accepted, invalid rejected with descriptive error messages
- [ ] Fails fast on out-of-range scores and missing abilities

## Status

`pending`
