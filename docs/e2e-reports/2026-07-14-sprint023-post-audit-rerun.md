# E2E Report: Sprint 023 post-audit rerun

**Date:** 2026-07-14
**Flags:** --no-llm
**Sections tested:** targeted 1, 3, 6
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 4 tested, 3 passed, 1 failed
- Quick fixes: 0 applied
- Blockers: 1 found

## Results

### Targeted regression scenarios

| # | Scenario | Status | Notes |
|---|---|---|---|
| 1.1 | Landing page Player/DM split | pass | Both Play and Dungeon Master cards lead to their expected routes. |
| 1.4 | Fighter character creation | pass | EN setup, Defense selector, AC 19 preview, and session creation worked. |
| 3.1–3.2 | Live combat event locale | fail | EN UI received a Russian live action-failure event after targeting a creature beyond reach: `Цель слишком далеко (10 ft, досягаемость 5 ft).` Screenshot: `sprint023-post-audit-locale-blocker.png`. |
| 6.5 | Master sessions list | pass | Fresh backend showed `No active sessions`; no saved-only session was exposed as manageable. |

## Auto-discovered scenarios

| Scenario | Reason | Status | Notes |
|---|---|---|---|
| EN live WS action failure | Phase 6 task 1 changed session locale and typed perception | fail | The frontend locale and most combat log events were EN, but server-generated action failure remained RU. |
| Empty Master list after clean start | Phase 6 task 2 changed session listing | pass | The UI did not show stale disk saves. |

## Findings

### Blockers

- The Phase 6 locale fix is incomplete. In an EN session, a failed melee attack produces a Russian live WebSocket message. This blocks the required post-audit E2E rerun and should be fixed before retesting `COMBAT_ENDED`.

### Minor

- EN gameplay views also rendered the nearby creature race as `человек`; this is another mixed-language symptom worth checking alongside the action-failure formatter.

## Log Analysis

- Backend structured log recorded the same Russian action error for session `f672885e`; no traceback or backend error was emitted.
- Browser console had no errors. Its one warning was a closed WebSocket during navigation before the new session connected.
