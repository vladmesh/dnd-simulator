# Phase 3 E2E Report

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 3 — Frontend + Content

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Reaction prompt on OA trigger | Overlay with Attack/Skip when enemy leaves reach | "Reaction!" overlay with "Melee attack against Lira" and "Skip" buttons | pass |
| Player chooses OA via reaction prompt | OA fires, damage shown in log | "You attack человек (кулаки) [d20+5=19 vs КЗ 15], 4 урона" + "You seize the opening against человек!" | pass |
| Disengage action in combat | Log shows disengage event | "You disengage" in combat log | pass |
| Disengage indicator in action bar | Badge showing disengage is active | "Disengage" badge with tooltip "Disengaged — movement won't provoke opportunity attacks" | pass |
| Budget display after Disengage | Actions consumed, movement remains | Actions: 0, Bonus: 1, Movement: 30ft, Reaction: 1 | pass |
| OA perception text in log | Readable OA event text | "You seize the opening against человек!" | pass |
| Attack perception text | Readable attack with dice details | Full roll breakdown: d20, modifier, vs AC, damage dice + type | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | World loads, location description, paths visible |
| Character creation | pass | Form works, all fields, creates character |
| Basic combat (attack NPC) | pass | Combat initiates, battle map, damage in log |
| NPC interaction (LLM) | pass | Marta spoke via LLM (русский), no errors |
| Session join via ID | pass | Paste session ID, join existing session |
| Exit session | pass | Returns to home page cleanly |

## Quick Fixes Applied

- None needed.

## Log Analysis

- No errors or exceptions in backend logs.
- Expected info-level failures: Lira attempted move_to with no movement remaining (RuleBrain repeated attempts, consecutive_failures_end_turn kicked in). Marta attacked from out of range. Both are normal RuleBrain behavior.
- OA/reaction/disengage flow logged correctly with full debug detail.

## Blockers

- None.

## Minor Issues

- Lira (LLM-brain NPC at silverport_city_docks) got pulled into combat when player attacked test_guard. Not a bug — expected proximity behavior — but could surprise players. Existing behavior, not phase 3.
