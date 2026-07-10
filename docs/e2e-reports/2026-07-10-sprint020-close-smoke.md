# E2E Report: sprint020-close-smoke

**Date:** 2026-07-10  
**Flags:** no LLM  
**Sections tested:** smoke subset of playbook sections 1, 2, 3, 5, 3.5  
**Stack:** `uvicorn :8001`, `vite :5173`, local headless Playwright Chromium

Playwright MCP was unavailable in this Codex session. Coordinator approved local Playwright automation as the browser E2E substitute. The runner and screenshots are in [2026-07-10-sprint020-close-artifacts/](2026-07-10-sprint020-close-artifacts/).

## Summary

- Scenarios: 5 tested, 5 passed, 0 failed
- Quick fixes: 0 applied during E2E
- Blockers: 0 found

## Results

| Scenario | Status | Notes |
|----------|--------|-------|
| Session + character | pass | Landing `/` → Play → New Session → Fighter creation through UI; character entered game with AC 19. |
| Combat attack | pass | Real game UI opened on `level_up_test`; Attack clicked, combat started, log populated. |
| Equipment | pass | Item granted through master API, then equipped from the in-game Inventory panel through UI. |
| Level-up | pass | Paladin killed deterministic XP dummy, level-up modal opened, Dueling selected, OK confirmed; player reached L2 with HP 20 and resources. |
| Wait / time | pass | Wait clicked in `test_vale`; game time advanced from 10:00 to 11:00. |

## Findings

### Blockers

- None.

### Minor

- None from the final smoke run.

## Log Analysis

- Backend/Vite logs contain errors from earlier failed runner attempts using non-app world ids (`combat_test`, `village`) before the script was corrected to `level_up_test` / `test_vale`.
- Vite logged `ECONNRESET` / `EPIPE` WebSocket proxy messages while the headless browser closed sessions. No final scenario failed from these messages.
