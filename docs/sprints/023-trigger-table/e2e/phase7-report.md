# E2E Report: sprint023-phase7

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** targeted 1, 3, 6
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 4 tested, 4 passed, 0 failed
- Quick fixes: 0 applied
- Blockers: 0 found

## Results

### Targeted regression scenarios

| # | Scenario | Status | Notes |
|---|---|---|---|
| 1.1 | Landing page Player/DM split | pass | Play and Dungeon Master routes were available. |
| 1.4 | Fighter character creation | pass | EN setup, Defense selector, AC 19 preview, and session creation worked. |
| 3.1–3.2 | Live combat action-failure locale | pass | In an EN session, an out-of-reach attack rendered `Target too far (10 ft, reach 5 ft).` in the live event log. |
| 6.5 | Master sessions list | pass | The current in-memory session was manageable; no stale saved-only session was listed. |

## Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|---|---|---|---|
| EN live WS action failure | Phase 7 applies the session locale before failed action dispatch. | pass | The prior RU fallback did not recur. |

## Findings

### Blockers

- None.

### Minor

- Nearby creature race labels remained Russian (`человек`) in an EN UI. This is the known separate `DND_LANGUAGE` content-name contract and is non-blocking for this phase.

## Log Analysis

- The backend logged the expected failed action in English and emitted no exception or traceback.
- The browser console had no errors or warnings.
- Rule-based NPC movement produced its existing recoverable blocked-move retries after the player navigated away; no browser-visible failure resulted.
