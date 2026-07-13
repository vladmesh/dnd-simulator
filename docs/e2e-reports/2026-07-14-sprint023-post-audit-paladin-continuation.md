# E2E Report: Sprint 023 post-audit Paladin continuation

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** 1.1, 3.5 (partial), 14.1 (partial)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 3 tested, 2 passed, 1 partial
- Quick fixes: 0 applied
- Blockers: 0 found in the deferred-level-up path

This continuation verifies the Phase 8 Task 3 repair, but it is not the required full non-LLM
post-audit rerun. The remaining playbook sections, Lay on Hands, target-scope validation, and
the successful Divine Smite path still need a serial UI run before Task 2 can become done.

## Results

| # | Scenario | Status | Notes |
|---|---|---|---|
| 1.1 | Landing page Player/DM split | pass | Both Play and Dungeon Master cards rendered and Play routed to the world picker. |
| 14.1 | Paladin L1 creation | pass | In `level_up_test`, a valid 26-point Human Paladin (STR 15, CON 14, CHA 12) had no Fighting Style selector, HP 12, AC 18, and Chain Mail, Longsword, and Shield. |
| 3.5 | Deferred L1 to L2 level-up | pass | Killing `xp_dummy` granted 500 XP and opened the L2 modal. Close deferred it without re-opening automatically; the visible manual `Level up` button re-opened it, Dueling confirmation produced Paladin L2, HP 20/20, and the Level 1 spell-slot UI. |
| 14.3 | Divine Smite | partial | The UI correctly returned `Target too far (15 ft, reach 5 ft).` when attacking `practice_thug`; no slot was spent. The player must move into reach before the successful Smite path can be checked. |

## Findings

### Blockers

- None found in the repaired manual Level Up flow.

### Minor

- Nearby creature race labels were Russian (`человек`) in the EN session. This remains the declared non-blocking `DND_LANGUAGE` content-name contract.

## Log Analysis

- Backend recorded the expected rejected out-of-reach attack as an `action_failed` info event; no error, exception, or traceback was emitted.
- Browser console had no errors. Its one warning was a benign WebSocket closure during navigation.
- Structured session log: `/tmp/dnd-e2e-logs/session_21da7b11/full.jsonl`.
