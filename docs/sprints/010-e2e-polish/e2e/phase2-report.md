# Phase 2 E2E Report

**Date:** 2026-03-28
**Sprint:** 010-e2e-polish
**Phase:** 2 — ActionBar Decomposition

## New Functionality Tested

Phase 2 was a pure refactor — no new user-facing features. Testing validates visual and behavioral equivalence.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| ActionBar renders all buttons (Attack, Say, Look, Wait, drawer, End Turn) | All buttons visible | All buttons visible | pass |
| Say button opens text input | Input expands inline | Input expands inline | pass |
| Say submit sends message, NPC responds | Message appears in log, NPC replies | Works correctly | pass |
| Escape closes Say input | Input collapses back to button | Works correctly | pass |
| NPC-specific Attack button triggers combat | Combat starts, damage displayed | Works correctly | pass |
| NPC inspect button opens modal | Modal shows name, race, description, faction | Works correctly, faction shows display name | pass |
| Wait button advances time | Time advances 1 hour | Time advanced 10:00 → 11:00 | pass |
| Travel via location paths | Location changes, new NPCs appear | Traveled to Market Square, Gretta visible | pass |
| Consumable drawer button renders | Shows item count badge | Button with "1" visible | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world / create session | pass | |
| Character creation with custom stats | pass | HP/AC/STR applied correctly |
| NPC interaction (talk via nearby panel) | pass | |
| Basic combat (attack via nearby panel) | pass | Full combat flow works |
| Travel between locations | pass | |
| NPC inspect modal | pass | Faction display name (Phase 1 fix) verified |

## Quick Fixes Applied

None needed for Phase 2 scope.

## Log Analysis

- No errors or warnings in backend logs for the working session (session_0b3bb772).
- Session with ActionBar Attack button crashed with `KeyError: 'target_id'` in `rules/handlers/combat.py:23` — pre-existing bug, see Minor Issues.

## Blockers

None. Phase 2 refactor introduced no regressions.

## Minor Issues (pre-existing, not introduced by Phase 2)

1. **ActionBar Attack button crashes backend in peaceful mode.** In peaceful mode, `enemies` is `[]`, so `ActionButton` falls through to the simple click handler, sending `attack` without `target_id`. Backend handler crashes with `KeyError: 'target_id'`. Frontend shows "GAME OVER" due to round loop crash. The NPC-specific Attack buttons in the nearby panel work correctly (they pass target_id). Fix: either hide Attack from ActionBar in peaceful mode, or populate enemies from nearby NPCs.

2. **Mixed i18n in combat log.** Attack description mixes English ("You attack") with Russian ("человек", "кулаки", "дробящий"). Phase 1 task 1 addressed combat log i18n but coverage is incomplete.

3. **Raw entity IDs as combat turn headers.** The log shows `player_5fc23128` and `marta` as turn dividers instead of display names ("Adventurer", "Марта"). Cause: `logProcessing.ts:224` uses `event.actor_id` as `actorName` because `PerceivedEvent` has no `actor_name` field.
