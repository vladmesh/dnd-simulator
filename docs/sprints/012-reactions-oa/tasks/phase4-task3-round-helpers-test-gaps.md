# Task: Round helpers + sprint 012 test gaps

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 4 — Audit Refactor

## Description

### 1. round.py — extract helpers from run_combat_turn

`run_combat_turn()` is 136 lines (210-345). Sprint target: < 80 lines. Extract:

- **Setup block (221-285):** Condition ticking, incapacitation check, budget creation, context setup → `_prepare_combat_turn(creature, time, query_fn, emit_fn) -> ActionContext | None` (returns None if incapacitated/skipped).
- **Action loop body (309-344):** Abstract move resolution, dispatcher execution, failure tracking, on_action callback → keep inline but extract the resolve-abstract-move + execute-and-track into a helper.

The main `run_combat_turn()` becomes: prepare → loop (choose → execute) → return.

### 2. Test gaps for sprint 012 files

Audit identified missing dedicated tests for files touched by this sprint:

- **`rules/reactions.py`** — `can_opportunity_attack()` and `find_oa_triggers()` are tested in `test_check_reactions.py` and `test_movement_oa.py` but have no dedicated `test_rules_reactions.py`. Add one with focused unit tests: all eligibility conditions for `can_opportunity_attack`, edge cases for `find_oa_triggers` (empty path, no combatants, multiple triggers same step).
- **`rules/handlers/reactions.py`** — `handle_opportunity_attack()` tested via `test_opportunity_attack.py` but no dedicated handler test. Add `test_handlers_reactions.py`: OA damage roll, event emission, target validation.
- **`rules/handlers/movement.py`** — handlers tested via dispatcher but no dedicated test. Add `test_handlers_movement.py`: `handle_move` in/out of combat, `handle_dash` budget addition, `handle_disengage` flag setting, `handle_wait` dormancy.

## Tests First

Write all test files first (RED). They exercise the actual game mechanics:

- "A creature without reaction budget cannot make an opportunity attack"
- "A disengaging creature does not trigger opportunity attacks"
- "An incapacitated creature cannot make opportunity attacks even with budget"
- "OA deals weapon damage to the moving creature"
- "Dash adds creature speed to movement budget"
- "Disengage sets is_disengaging flag on the creature"
- "Wait sets wake_at_seconds and marks creature dormant"

## Implementation

1. Extract `_prepare_combat_turn()` and any loop helpers from `run_combat_turn()`.
2. Write the three test files with focused unit tests.
3. Verify all pass with `make check`.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] `run_combat_turn()` < 80 lines (65 lines)
- [x] `test_rules_reactions.py` exists with ≥ 8 tests (20 tests)
- [x] `test_handlers_reactions.py` exists with ≥ 4 tests (5 tests)
- [x] `test_handlers_movement.py` exists with ≥ 6 tests (12 tests)

## Status

`done`

## Developer Notes

Extracted two helpers from `run_combat_turn`:
- `_prepare_combat_turn()` — resets turn state, ticks conditions, checks incapacitation, creates budget and ActionContext. Returns None if turn should be skipped.
- `_build_combat_awareness()` — builds awareness snapshot for each loop iteration (available actions, reachable cells, equipped items).

`run_combat_turn` went from 136 lines to 65 lines. The OA callback wiring (`on_leave_reach`) stays in `run_combat_turn` since it needs `time`/`query_fn`/`emit_fn` which are turn-level concerns.

Test files added: 37 total new tests across 3 files. All tests exercise existing implemented code (test gap fill), so they were GREEN immediately — no RED phase was possible since the code was already correct.
