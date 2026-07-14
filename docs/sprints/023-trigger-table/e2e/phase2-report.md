# E2E Report: sprint023-phase2

**Date:** 2026-07-13
**Flags:** --no-llm
**Sections tested:** 15 + phase-scoped lair death write-back
**Stack:** `LOG_LEVEL=DEBUG`, `LOG_DIR=/tmp/dnd-e2e-logs`, integration `lair_world`

## Summary

- Scenarios: 3 tested, 3 passed, 0 failed
- Quick fixes: 1 applied
- Blockers: 0 found

## Results

| Scenario | Status | Notes |
|---|---|---|
| Lair materialization and player UI regression | pass | `lair_world` opened through the real player UI; the core, two minions and treasury materialized at `cave`, combat started from the Goblin Boss action. |
| Core death immediately writes back to ecology and save/load | pass | The player killed `goblin_boss_1` through the UI after test setup set `current_hp` to 1 and AC to 0. Immediate save recorded `state: depleted`, `core_alive: false`, `death_writebacks: [goblin_boss_1]`; load and a second save preserved the same state. |
| Death event reaches UI once and remains JSON-safe | pass | The combat log showed one `Goblin Boss dies` entry with the stable display name. The successful retry session logged `lair_death_written_back` and no `listener_error` or traceback. |

## Quick Fixes

- Cascade events now skip the layer that produced them, matching tick propagation. This prevents the EntitiesLayer from logging its own death event twice and removing a materialized corpse before perception. Focused backend verification: 22 passed.

## Findings

### Blockers

- None.

### Minor

- The lair treasury is shown in the Nearby panel with Attack and Talk actions, although playbook scenario 15.5 expects containers to expose Inspect only. This remains outside the Phase 2 write-back contract.

## Log Analysis

- Integration suite: 160 passed.
- Successful killing hit produced one `lair_death_written_back` entry with `role: core`, `state: depleted`.
- No `WsEventListener.on_action_result` error, other `listener_error`, exception, or traceback occurred in the successful retry session.
- Browser console had no errors; navigation/load produced only transient WebSocket-close warnings.
