# Task: RuleBrain Movement Budget Check

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 4 — Bug Fixes

## Description

RuleBrain keeps requesting move actions after movement budget is exhausted (0 ft remaining), producing 3+ failed action logs per NPC turn. The `consecutive_failures` counter eventually breaks the loop (at 3), but the failures are logged and sometimes surface as warnings in the event log.

**Root cause analysis:** `_try_advance()` in `brain.py:331-339` correctly guards with `if movement_left > 0: return move`, returning None otherwise. However, the decision chain in `_choose_combat_action()` calls `_try_advance` → None → `_try_dash` → returns Dash action → round executes Dash (restores movement) → next iteration calls `_try_advance` → returns move → succeeds. This works.

The spam happens when `_try_dash` also returns None (no actions/bonus left), and the entire decision chain produces no action. The brain then falls through to... let me check.

Actually, the real scenario: NPC exhausts movement and actions/bonus. Budget `turn_over` is True, loop breaks. No spam. The spam happens when NPC has actions left but no movement and no target in reach — it tries to advance (fails), dash (fails if no action budget), then the rules chain returns None and `_choose_combat_action` falls back to `end_turn`. But the dispatcher rejects the move with "Insufficient budget" before consecutive_failures hits 3.

The fix: when `_try_advance` returns None (no movement) and `_try_dash` also returns None (no action/bonus for dash), the brain should not keep trying to move. The decision chain should skip movement-related actions entirely when budget is exhausted.

## Tests First

1. **Unit test: RuleBrain with 0 movement doesn't request move** — Create a creature with a target out of reach, movement_remaining=0, actions=1. Call `choose_action()`. The returned action should NOT be a MOVE — it should be END_TURN or IDLE (no valid actions available).

2. **Unit test: NPC turn with 0 movement produces no failed move actions** — Run a full NPC combat turn via `Round.run_combat_turn()` where the NPC starts with 0 movement and an unreachable target. Verify the action list contains no failed MOVE attempts.

## Implementation

In `core/brain.py:_choose_combat_action()`, the rules chain at lines 185-199 already correctly guards each step. The issue is that when all rules return None, the method falls through without returning — check what happens at the bottom of the method. Add explicit `end_turn` fallback if all rules fail.

Also verify that `_try_advance` and `_try_dash` guards are tight — they should return None immediately when budget is insufficient, not attempt the action.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] NPC turns produce 0 "action_failed" logs for movement when budget is exhausted
- [x] NPC still moves correctly when budget allows

## Status

`done`

## Developer Notes

Root cause: two separate budget issues in RuleBrain.

1. **Movement under-check**: `_try_advance` checked `movement_left > 0` but a MOVE step costs 5ft.
   After diagonal movement (5/10/5 rule), budget can end at 1-4ft remaining. Brain would return MOVE,
   dispatcher would reject (budget insufficient), repeat 3x → consecutive_failures break.
   Fix: changed to `movement_left >= 5`.

2. **Early exit too aggressive**: `choose_action` had `if budget.actions <= 0: return END_TURN` which
   prevented post-attack movement (D&D 5e split movement). Changed to `budget.turn_over` which only
   ends when ALL resources (actions, bonus, movement) are exhausted.

3. **Action-costing rules lacked budget checks**: With the early exit relaxed, `_try_attack`,
   `_try_potion`, `_try_flee`, `_try_flee_fallback` needed their own `budget.actions > 0` guards
   to avoid requesting actions the dispatcher would reject. `_try_disengage` and `_try_dash` already
   had these checks. Also tightened `_try_retreat` movement check to `>= 5`.
