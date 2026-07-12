# E2E Report: sprint022-phase1

**Date:** 2026-07-10
**Flags:** --no-llm
**Sections tested:** 1, 2, 6 + phase lifecycle scenario
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 3 tested, 2 passed, 1 failed during the original E2E run
- Follow-up: blocker fixed and verified outside the sprint task sequence
- Quick fixes: 1 applied
- Blockers: 0 open

## Results

| Scenario | Status | Notes |
|---|---|---|
| Landing and character creation | pass | Sword Vale session created through UI; Fighter with Defense entered the game, AC 19 and the normal action bar were visible. |
| Basic peaceful action | pass | Wait advanced game time from 10:00 to 11:00 through the player UI. |
| Save → mutate → load → reconnect | resolved | The original E2E run failed after reconnect. The WS lifecycle race was fixed and verified with lifecycle tests, live save/load + WS integration tests, and 20 consecutive quick reconnect runs. The exact browser scenario was not rerun. |

## Findings

### Blockers

- None open.

### Resolved

- The disconnect path could observe an empty player-listener list, release `_lock`, and later stop the round after a reconnect had already registered a new listener and started a new round. Listener add/remove and round start/stop are now serialized by the session `_round_transition_lock`.
- Removing an unknown stale listener is now a no-op and does not arm session eviction.
- Regression coverage models the disconnect/reconnect interleaving directly.

### Minor

- None found in the tested scope.

## Log Analysis

- No browser console errors; one existing React Router future-flag warning.
- Backend accepted the reconnecting player WebSocket and logged `add_listener`. During the first reconnect transition it also logged `remove_listener`, `stop_round`, and a round ending at restored time 10:00:06. The page never received a turn afterward.

## Follow-up Verification

- `tests/unit/test_session_lifecycle.py`: 30 passed.
- Full backend check: ruff, formatting and mypy passed; 2441 unit tests passed.
- Live backend with integration content: save/load and WebSocket connection selection, 8 passed.
- Quick reconnect stress: 20 consecutive runs passed.
