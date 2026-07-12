# E2E Report: sprint023-phase1

**Date:** 2026-07-12
**Flags:** --no-llm
**Sections tested:** 1 (Session Setup) + auto-discovered (typed event payloads)
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs

## Summary

- Scenarios: 8 tested, 8 passed, 0 failed
- Quick fixes: 0
- Blockers: 0

Phase 1 is a pure typing/contract migration of event payloads. Focus: confirm typed
payloads still serialize, cross the WS boundary, and render as clean localized log
lines (no raw IDs, no `{placeholder}` leaks, no "Something happened" fallback). They do.

## Results

### Section 1: Session Setup

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 1.1 | Landing — Player/DM split | pass | Two cards (Play, Dungeon Master) + EN/RU toggle |
| 1.2 | Quick start — new session, create Fighter, enter game | pass | Session 77d6ac84, redirect to /play/:id, WS "Connected" |
| 1.4 | Character creation — point buy | pass | STR 15/CON 14 → remaining 3/27, STR+ disabled at 15, preview HP 12 / AC 19 (Chain Mail 16 + Shield 2 + Defense 1) / Gold 1000 |
| 1.5 | Character creation — class-specific UI | pass | Fighter shows Fighting Style selector (Defense/Dueling/GWF); equipment Chain Mail, Longsword, Shield |
| 1.3 | Language toggle EN→RU | pass | "Choose a World" → "Выберите мир" |

### Auto-discovered scenarios (Phase 1 — typed event payloads)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| entity_say event rendering | Action event payloads typed (task 3) | pass | Player + NPC say lines render cleanly in RU: "Ты говоришь: «Hello marta»", "человек говорит: «Что будете заказывать?»". No raw IDs / placeholders / fallback |
| Wait — time advance | World event payloads typed (task 1) | pass | 10:00 → 11:00, no spurious/malformed event line |
| Dashboard render post-create | Entity lifecycle payloads typed (task 2) | pass | HP 12/12, AC 19, STR 15/CON 14, Fighter L1, equipped Longsword/Chain Mail/Shield |
| Backend log serialization | Payload typing regression risk | pass | No error/exception/traceback/Pydantic validation failure in backend or session structured logs |

## Quick Fixes

None.

## Findings

### Blockers
None.

### Minor
- NPC race renders as "человек" (RU) while the frontend chrome is EN. Pre-existing, not a
  Phase 1 regression: perceived strings come from the backend in the game language
  (`DND_LANGUAGE` defaults to `ru`); frontend i18n labels are a separate channel.

## Log Analysis

- One `llm_not_configured_fallback` warning: marta is configured `ai: llm` but no
  `OPENROUTER_API_KEY` is set, so she falls back to RuleBrain — expected in --no-llm run,
  explains the canned "Что будете заказывать?" reply.
- No errors, exceptions, tracebacks, or validation failures across backend log and the
  session structured logs.
