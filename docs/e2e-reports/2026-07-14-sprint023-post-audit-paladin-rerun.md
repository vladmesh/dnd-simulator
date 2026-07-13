# E2E Report: Sprint 023 post-audit Paladin rerun

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** 1, 3.5, 14
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 3 tested, 2 passed, 1 failed
- Quick fixes: 0 applied
- Blockers: 1 found

The required full non-LLM rerun stopped at the Paladin L2 prerequisite. The remaining sections
were not run because §3.5 cannot be completed after its required deferred-level-up check.

## Results

| # | Scenario | Status | Notes |
|---|---|---|---|
| 1.1 | Landing page Player/DM split | pass | Both Play and Dungeon Master cards rendered and routed from `/`. |
| 14.1 | Paladin L1 creation | pass | Paladin selection removed the Fighting Style selector. The created Human Paladin L1 had 12 HP with CON 14, AC 18, and Chain Mail, Longsword, and Shield. |
| 3.5, 14.2–14.4 | Paladin L1 → L2 and dependent features | fail | Killing `xp_dummy` granted 500 XP and opened `Level up to L2` with the expected Fighting Style selector and two level-1 slots. After Close deferred the modal, no `Level Up` button appeared, including after End Turn and the next `round_result`; the modal could not be reopened to select Dueling, so Lay on Hands, Smite, and target-scope checks could not continue. |

## Findings

### Blockers

- The UI does not expose the documented manual `Level Up` control after deferring `LevelUpModal`.
  Reproduce in `level_up_test`: create Paladin L1, kill `xp_dummy`, close the automatic L2 modal,
  wait through the next round, then inspect the action bar and character panel. The level-up
  prompt remains absent despite the player still being L1 with the earned 500 XP.

### Minor

- Nearby creature race labels remained Russian (`человек`) in the EN session. This is the known
  non-blocking `DND_LANGUAGE` content-name contract, not the live-session locale failure fixed
  in Phase 7.

## Log Analysis

- `/tmp/dnd-e2e-backend.log` had no error, exception, or traceback lines.
- The browser had no console errors. It recorded one benign warning about a WebSocket closing
  during navigation.
- `/tmp/dnd-e2e-logs/session_3a31211b/full.jsonl` was created for the attempted session.
