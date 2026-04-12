# Task: Move RuleBrain to rules/ (remove lazy rules imports from core/brain.py)

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 3 — Core Boundaries

## Description

`core/brain.py` contains the `Brain` ABC (belongs in core) and `RuleBrain` concrete implementation (shouldn't). `RuleBrain` has 5 lazy imports from `rules/` (`rules.movement`, `rules.weapons`, `rules.resources`, `rules.actions`) to dodge a circular-import problem that only exists because the class sits in `core/`.

Fix: keep `Brain` ABC in `core/brain.py`. Move `RuleBrain` (lines 104–459) to `rules/rule_brain.py`. Imports from `rules/*` become top-level. Update all `from dnd_simulator.core.brain import RuleBrain` call-sites to `from dnd_simulator.rules.rule_brain import RuleBrain`.

Rationale: `rules/` already imports from `core/` freely; `RuleBrain` is strategy logic that consumes game rules, so it lives naturally alongside them. `core/` keeps only the ABC.

## Tests First

1. **Integration test: a RuleBrain NPC completes a combat turn** — place a rule-based NPC in combat with a player, run one round, assert the NPC picks an attack action and executes it, dealing damage to the player. Exercises `_build_context`, `get_weapon_attack`, action selection end-to-end.

2. **Integration test: a RuleBrain creature performs tactical retreat** — spawn a low-HP NPC with `retreat_threshold` high enough to trigger, confirm it chooses `move_to` away from the nearest enemy. Exercises `_move_away_from` + `calculate_away_direction`.

3. **Architecture test:** after refactor, `core/brain.py` contains no `from dnd_simulator.rules` imports (neither top-level nor lazy). Pytest reads the file and asserts.

## Implementation

1. Create `src/dnd_simulator/rules/rule_brain.py`. Move the `RuleBrain` class from `core/brain.py` (lines 104–459).
2. Convert the 5 lazy imports to top-level `from dnd_simulator.rules.movement import ...` etc.
3. In `core/brain.py`, remove the `RuleBrain` class. Keep `Brain` ABC and any types consumed by it (`BrainDecision`, `ReactionTrigger`, etc.).
4. Update imports across the codebase — likely `service/brain_factory.py`, tests, possibly `content_loader/`. Run `grep -rn "from dnd_simulator.core.brain import" src tests` and fix each site importing `RuleBrain`.
5. Keep backwards-compatible re-export? No — per CLAUDE.md no back-compat shims. Fix all call-sites.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `grep -rn "from dnd_simulator.rules" src/dnd_simulator/core/brain.py` → empty
- [ ] No lazy `from dnd_simulator.rules...` imports anywhere in `core/`
- [ ] `core/brain.py` exports only `Brain` ABC and its dependencies

## Status

`pending`
