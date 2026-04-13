# Task: perform_level_up unit tests

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 5 — Post-audit cleanup

## Description

`rules/perform_level_up.py` is currently exercised end-to-end (kill → XP → modal → level-up) but has no isolated unit tests. Add a focused unit test file covering each class transition and the validation paths.

## Tests First

Create `tests/unit/test_rules_perform_level_up.py`. Use small `Character` factories (helper functions in the test file). Cover:

- **Fighter L1→L2** — `fighting_style=None` succeeds. After call: `level=2`, `level_up_available=False`, `max_hp` increased by `roll_avg(d10) + CON_mod`, `current_hp` increased by same delta, `class_features` has `FighterFeatures(level=2)`. New resource pool `action_surge` exists with `max_uses=1, current_uses=1`.
- **Rogue L1→L2** — `fighting_style=None` succeeds. After call: `level=2`, HP delta applied, `class_features` has `RogueFeatures(level=2)`. No new pools.
- **Paladin L1→L2 with Defense** — `fighting_style=FightingStyle.DEFENSE`. After call: `class_features` has `PaladinFeatures(level=2, fighting_style=DEFENSE)`. Spell slot pool now non-empty (Paladin gets 2× L1 slots at L2).
- **Paladin L1→L2 with Dueling** — same as above but Dueling style stored.
- **Paladin L1→L2 with no style** — raises `ValueError("Paladin level 2 requires a fighting_style choice")`.
- **Fighter L1→L2 with style passed** — raises `ValueError` (not applicable for fighter).
- **No level-up available** — `level_up_available=False` → raises `ValueError("No level-up available")`.
- **Resource pool merge** — Pre-existing Lay-on-Hands pool with `current_uses=2 (max=5)` survives the level-up with current_uses preserved (clamped to new max if reduced — should not be the case for L1→L2 LoH, which grows to 10).

These describe game behavior — what a player sees after pressing "Level Up" — not implementation structure.

## Implementation

Pure test file. No production changes unless a test surfaces a real bug.

## Acceptance Criteria

- [ ] Tests written for all 8 scenarios above
- [ ] All tests pass against current `perform_level_up.py`
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Added `tests/unit/test_rules_perform_level_up.py` with 9 tests across 5 classes: Fighter L1→L2 (no-style, HP delta applied to wounded current_hp, style-passed rejection), Rogue L1→L2 (no pools), Paladin L1→L2 (Defense, Dueling, missing-style rejection), no-level-up-available, and LoH resource pool merge (current_uses preserved, max grows 5→10). Tests are regression pins for existing behavior — all pass against current `perform_level_up.py` (same pattern as task 1). Full `make check` green (2167 py + 238 fe).
