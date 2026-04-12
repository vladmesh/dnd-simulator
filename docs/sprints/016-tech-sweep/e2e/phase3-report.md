# Phase 3 E2E Report

**Date:** 2026-04-13
**Sprint:** 016-tech-sweep
**Phase:** 3 — Core Boundaries

## New Functionality Tested

Phase 3 is architectural refactoring (no user-visible features). E2E validates that refactored code paths still work.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Create Fighter w/ Defense style (ClassFeatures.collect_modifiers) | AC 19 (10 + 6 chainmail + 2 shield + 1 Defense) | AC 19 displayed | pass |
| Attack NPC (round.py via CreatureHost Protocol → EntitiesLayer) | Attack dispatches, damage applied, NPC dies | "d20(10)+2=12 vs КЗ 10, 4 урона", NPC died | pass |
| Combat end + reputation drop (RuleBrain moved to rules/) | Combat resolves, reputation delta computed | "Бой окончен", reputation militia 50→30 | pass |
| Faction side assignment (NPC auto-hostile from attack) | Player vs barkeep sides built via forced_opponents | Initiative "Adventurer, Nora the Barkeep" | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load Sword Vale world (7 regions, 31 locations) | pass | DM view renders full graph |
| Create character (Human Fighter L1, Defense) | pass | HP 10, AC 19, 1000g, starting equipment |
| Combat: attack → hit → kill | pass | 1-shot kill, logs localized |
| Inventory display | pass | Longsword/Chain Mail/Shield listed |

## Quick Fixes Applied

None.

## Log Analysis

- `backend.log`: no errors.
- `session_6a27da0f/full.jsonl`: 1 traceback — `KeyError: 'target_id'` in `rules/handlers/combat.py:23` when the global Attack button is clicked in peaceful mode with no target in range. Reproduced by double-clicking Attack after combat ended (barkeep dead, nobody nearby). `combat.py` and `PlayerActionBar` have not changed in sprint 016 — this is pre-existing. Handler crashes on `str(action.params["target_id"])` in a logger call before validation. → **backlog**.
- No errors in phase-3-touched code (round.py, rule_brain.py, llm/, class_features.py, modifiers.py).

## Blockers

None.

## Minor Issues

- Pre-existing: `rules/handlers/combat.py:23` raises `KeyError` when attack action reaches handler without `target_id`. Validation happens later; logger reaches for `params["target_id"]` unconditionally. Either validate earlier or default to `None` in the log line. Candidate for Phase 4 (fail-fast hardening) or backlog.
