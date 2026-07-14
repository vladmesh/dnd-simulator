# E2E Report: Sprint 023 lair core lifecycle rerun

**Date:** 2026-07-14
**Flags:** --no-llm, targeted §15.2
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 1 tested, 1 passed
- Quick fixes: 0
- Blockers: 0

## Results

| Scenario | Status | Notes |
|---|---|---|
| §15.2 Master core mutation → save/load → reconnect | pass | In Test Vale, UI travel materialized `goblin_chieftain_5` and three minions at Forest Clearing. The Master creature editor set the core to 0 HP; after UI save/load and player reconnect, the UI retained that one corpse plus `goblin_6`, `goblin_7`, and `goblin_8`. No second core or minion roster appeared. |

## Log Analysis

- `session_a3d9bb3f/full.jsonl` records one initial `lair_materialize` sequence for the core and three minions, followed by `lair_death_written_back` with `role=core` and `state=depleted`.
- Reconnect awareness entries contain only the original core and three minions; there is no subsequent `lair_materialize` event.
- Backend log and Playwright console contained no errors or exceptions.
