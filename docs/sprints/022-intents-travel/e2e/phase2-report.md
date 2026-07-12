# E2E Report: sprint022-phase2

**Date:** 2026-07-11
**Flags:** --no-llm
**Sections tested:** 2
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 4 tested, 4 passed, 0 failed
- Quick fixes: 0 applied
- Blockers: 0 found

## Results

### Section 2: Peaceful Mode

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 2.3 | Wait and time advance | pass | Wait at The Salty Anchor advanced 10:00 → 11:00 and returned the player turn while Marta, a RuleBrain NPC, was nearby. |
| 2.4 | Move between locations | pass | Moving to Silverport Market Square updated the location panel and nearby list. |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Short rest wake lifecycle | Timed rest completion moved to the intent wake boundary | pass | Short Rest advanced 11:00 → 12:00; the action bar returned after wake. |
| Long rest wake lifecycle | Timed rest completion moved to the intent wake boundary | pass | Long Rest advanced 12:00 → 20:00; the action bar returned after wake. |

## Quick Fixes

None.

## Findings

### Blockers

None.

### Minor

- Vite dev mode logged one transient WebSocket warning while the initial connection was being replaced. The active connection succeeded and all actions completed without reconnect symptoms.

## Log Analysis

- Backend log contains no errors, exceptions, or tracebacks.
- Round logs show direct fast-forward deltas of 3594 seconds for wait/short rest and 28794 seconds for long rest after the six-second action round.
- Entity logs show one wake boundary and one rest completion for each tested intent.
