# Phase 2 E2E Report

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 2 — Personal Reputation + effective_relation

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Create session, enter combat (Sword Vale) | Combat starts with correct sides (player vs NPC) | Combat started, initiative rolled, player attacked NPC, NPC took turn (moved, dodged), round 2 started | pass |
| Combat sides with effective_relation | Player and NPC on opposing sides, combat continues across rounds | Sides built correctly, combat continued to round 2 | pass |
| Player HP/AC display during combat | Shows correct values from character creation | HP 12/12, AC 18 displayed correctly | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | World loaded, NPC visible at The Salty Anchor |
| Character creation (point buy) | pass | STR 15, DEX 12, CON 14 — HP 12, AC 18, starting equipment correct |
| Basic combat (attack NPC) | pass | Attack resolved: d20(12)+4=16 vs AC 10, 3 damage. NPC took turn correctly |
| Battle map | pass | Grid displayed with player "@" and enemy "1", clickable movement cells |
| Action bar | pass | All combat actions visible (Flee, Dash, Attack, Disengage, Dodge, End Turn) |
| Turn budget display | pass | Actions 1, Bonus 1, Movement 30ft, Reaction 1 |

## Quick Fixes Applied

- Fixed `on_leave_reach` in `round.py`: process OA reactors one at a time, stop if mover dies (was firing all OAs even against dead creatures)
- Added `factions.yaml` to `oa_test` world (hero_faction HOSTILE to enemy_faction)
- Reduced guard STR in `oa_test` world (16 -> 10) to prevent player death before OA test completes
- Created `move_test` world with single weak NPC for `test_move_to_in_combat` (was using `arena` with 4 strong NPCs that killed the player before their turn)

## Log Analysis

- No errors or exceptions in session logs for E2E session (12c61b24)
- Server log clean — only old session entries from previous runs

## Blockers

- None

## Minor Issues

- None
