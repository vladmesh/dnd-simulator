# Task: Decompose Brain Combat Decision Tree

**Date:** 2026-04-09
**Sprint:** 014-faction-reputation
**Phase:** 0 — Refactor — Prep for Faction Work

## Description

Decompose `RuleBrain._choose_combat_action()` (129-line if/elif chain in `core/brain.py`) into testable decision helpers. Sprint 014 rewrites targeting logic in this method — the monolithic chain makes that dangerous.

The current method is a linear priority list: equip weapon → use potion → pick target → retreat/disengage → attack → move → dash → end turn. Each decision is 4-18 lines of inline logic with magic thresholds (0.25, 0.15, 0.35).

Extract into a decision-rule pattern:
- Each decision is a small function: `(creature, budget, awareness) → Action | None`
- `_choose_combat_action` iterates rules in priority order, returns first non-None
- Thresholds become named constants (FLEE_HP_THRESHOLD, POTION_HP_THRESHOLD, etc.)

Also fix: duplicate flee logic (lines 234-237 ≈ lines 244-247).

## Tests First

- Wounded creature (HP < 25%) with no enemies adjacent flees combat.
- Wounded creature (HP < 25%) with enemy adjacent disengages first, then flees.
- Creature with ranged weapon and enemy at range attacks from distance (doesn't move closer).
- Creature with melee weapon and enemy out of reach moves toward target. If movement insufficient, dashes.
- Creature with potion and HP < 35% uses potion before attacking.
- Creature with no valid targets ends turn.
- Existing brain-related tests still pass.

## Implementation

1. Define threshold constants at module level.
2. Extract each decision block into a helper: `_try_equip()`, `_try_potion()`, `_pick_target()`, `_try_retreat()`, `_try_attack()`, `_try_advance()`.
3. `_choose_combat_action` becomes a loop over decision functions.
4. Remove duplicate flee check.
5. Verify `make check` green.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `_choose_combat_action` under 30 lines (dispatch loop)
- [ ] Each decision helper independently testable
- [ ] No magic numbers in decision logic

## Status

`pending`
