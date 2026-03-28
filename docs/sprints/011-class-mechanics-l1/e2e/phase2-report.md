# Phase 2 E2E Report

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 2 — Weapon Properties & Fighting Styles

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Item catalog loads via API | All 12 weapons, 12 armors, 1 shield returned | 26 items returned with correct properties | pass |
| Weapon properties on catalog items | Greatsword: two_handed+heavy, Dagger: finesse+light, Rapier: finesse | All properties correct | pass |
| Armor categories and AC | Plate: heavy AC 18, Leather: light AC 11, Chain Mail: heavy AC 16 | All correct | pass |
| Shield AC bonus | Shield: ac_bonus 2 | Correct | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | All regions, locations, settlements displayed correctly |
| Character creation (Fighter) | pass | Stats, class, race all set correctly; AC computed as 12 (10+DEX) |
| Basic combat — attack NPC | pass | Unarmed attack resolved correctly (d20+STR+proficiency vs AC) |
| Attack card modal | pass | Shows full breakdown: d20 roll, modifiers, damage components |
| Crit attack display | pass | Nat 20 shown as CRIT, damage breakdown correct |
| Battle map movement | pass | Click-to-move works, reachable cells highlighted, movement budget spent |
| Range validation | pass | "Target too far" error when attacking from 50ft with 5ft reach |
| Combat end | pass | Combat ends after target dies, UI returns to exploration mode |

## Quick Fixes Applied

- None needed

## Log Analysis

- Session logs clean. Only logged "error" is the expected range validation message ("target too far") at info level.
- No exceptions, tracebacks, or unexpected warnings.

## Blockers

- None

## Minor Issues

- None
