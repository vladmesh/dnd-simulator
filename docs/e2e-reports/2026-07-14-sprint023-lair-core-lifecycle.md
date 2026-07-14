# E2E Report: Sprint 023 lair core lifecycle

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
| §15.2 Master core mutation → save/load → reconnect | pass | Master UI set `goblin_chieftain_1` to 0 HP. After UI save/load and player reconnect, the table retained the same dead core and its three original minions. No second roster appeared. |

## Log Analysis

- `session_4ffed947/full.jsonl` records `lair_death_written_back` for `goblin_chieftain_1` with `role=core` and `state=depleted`.
- The reconnect awareness entries retain only `goblin_chieftain_1`, `goblin_2`, `goblin_3`, and `goblin_4`; no new `lair_materialize` event occurs.
- Backend log and Playwright console contained no errors.
