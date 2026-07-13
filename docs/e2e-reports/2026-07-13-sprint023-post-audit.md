# E2E Report: sprint023-post-audit

**Date:** 2026-07-13
**Flags:** --no-llm
**Sections tested:** targeted post-audit smoke; regression halted by blockers
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 9 tested, 6 passed, 3 failed
- Quick fixes: 0 applied
- Blockers: 2 found

## Results

### Session setup and dashboard smoke

| # | Scenario | Status | Notes |
|---|---|---|---|
| 1.1 | Landing Player/DM split | pass | Both cards route to `/play` and `/master`. |
| 1.2 | Create Sword Vale player session | pass | Character creation completed and player WebSocket connected. |
| 1.4 | Character creation preview | pass | Point-buy controls, preview, starting equipment, and Fighter style selector rendered. |
| 1.5 | Fighter equipment preview | pass | Defense style produced AC 19 after entering play. |
| 2.1 | Peaceful perception | pass | Nearby NPC controls and inspect action rendered. |
| 2.3 / 16.1 | Wait advances world time | pass | Clock advanced from 10:00 to 11:00 with a RuleBrain NPC nearby. |
| 3.1–3.4 / 13.2–13.3 / 15.5 | Attack, death, reputation, and corpse controls | fail | Combat completed and corpse exposed only Inspect/Loot, but event text was mixed-language and `combat_ended` fell back to a generic message. |

### Master panel and Sprint 023 controls

| # | Scenario | Status | Notes |
|---|---|---|---|
| 6.1 / 6.5 | Worlds, session creation, and management | partial | World cards and new-session flow work. Existing saved session rows can link to a missing session. |
| Sprint 023 Phase 4 | Activation controls | pass | Fresh session showed actual/manual state plus Activate, Make dormant, and Automatic controls; dormant then activate updated the displayed state. |

### Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|---|---|---|---|
| Typed event rendering after combat | Sprint 023 moved the event codec and perception formatting. | fail | English frontend displayed Russian combat strings and `Something happened (combat_ended)`. |
| Saved-session management | Sprint 023 split master transport clients. | fail | A visible saved session (`01cdad0e`) returned 404 from `/api/master/sessions/01cdad0e` and showed `Session not found.` |
| GM activation state | Sprint 023 Phase 4 UI/API. | pass | Manual dormant/activate cycle worked in a fresh Level-up Test Arena session. |

## Findings

### Blockers

- Mixed frontend/backend locale: with English frontend controls, combat output was Russian (`Бой начался`, `Ты атакуешь`, `человек погибает`) while other strings were English. The same run rendered `Something happened (combat_ended)`, which exposes the raw event type instead of a localized perception message.
- The Master Sessions list includes stale saved session rows whose Manage link is actionable but resolves to `Session not found.` and logs a 404. This breaks session management until the list excludes stale saves or the session can be restored.

### Minor

- Closing the tested player session during browser navigation produced one expected WebSocket-close warning. No backend errors, exceptions, or tracebacks appeared in `/tmp/dnd-e2e-backend.log`.

## Log Analysis

- Backend debug log had no matching error, exception, or traceback entries.
- Browser console recorded three 404s for the stale master-session link and one WebSocket-close warning after navigation.
- The two blockers prevent calling this a green post-audit E2E; untested playbook sections remain pending their fixes.
