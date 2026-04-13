# Phase 1 E2E Report

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 1 — XP & Leveling Core

## New Functionality Tested

Phase 1 is backend-only (no UI surface for level-up yet — that lands in Phase 3). Verification is
API-level: the player state payload must expose the new XP fields.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| `GET /api/player/sessions/{id}/status` after character creation | response carries `experience`, `level_up_available`, `xp_to_next_level` | `experience=0`, `level_up_available=false`, `xp_to_next_level=300` for a freshly created L1 Fighter | pass |
| Integration coverage of XP-on-kill + payload shape | `tests/integration/test_player_state_xp.py` exercises the flow over the live stack | 137/137 integration tests pass | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world list (Play/Master pages) | pass | Sword Vale + Test Vale render |
| Create character (Fighter, Defense FS) | pass | HP 10, AC 19, Longsword/Chain Mail/Shield equipped |
| Enter session, see nearby NPC (barkeep) | pass | Tavern location, map render OK |
| Attack NPC → combat starts | pass | Roll resolved: `d20(6)+2=8 vs AC 10, miss`; combat state active, initiative running |
| Player state payload shape | pass | Includes XP fields and existing fields (pools, ability scores, gear) |

## Quick Fixes Applied

None.

## Log Analysis

- `/tmp/dnd-e2e-logs/backend.log` shows normal round/turn events, no exceptions or tracebacks.
- Frontend console: 0 errors, 1 warning (pre-existing, unrelated to this phase).

## Blockers

None.

## Minor Issues

None observed for Phase 1. Level-up UX (modal, class choices) is Phase 3 work and not expected here.
