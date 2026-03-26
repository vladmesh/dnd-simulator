# Phase 2 E2E Report

**Date:** 2026-03-27
**Sprint:** 008-content-schema
**Phase:** 2 — Catalogs — Monsters + Items

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Sword Vale loads with catalog-resolved monsters/items | Session created, world renders | Session 0f7ac9e0 created, world loaded correctly | pass |
| NPC visible with catalog-resolved data | Marta appears at The Salty Anchor | Marta displayed as "человек" with Attack/Talk buttons | pass |
| Combat with catalog-resolved NPC | Combat starts, initiative, damage calculated | Initiative: Marta/Adventurer, attack hit (d20(9)+2=11 vs AC 10), 1 damage | pass |
| NPC turn in combat | NPC brain executes actions | Round advanced to 2, NPC took turn (no attack — civilian NPC, expected) | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world | pass | Sword Vale + Test Vale both listed |
| Character creation | pass | All fields rendered, character created successfully |
| Basic combat | pass | Battle map, turn budget, initiative all correct |
| Session exit | pass | Clean return to landing page |

## Quick Fixes Applied

- None needed.

## Log Analysis

- Session logs: 58 lines, 0 errors, 0 warnings
- Browser console: 0 errors, 1 warning (WebSocket reconnect — known benign)
- Serve log: old 500 errors from previous E2E sessions (invalid NPC location in session d9f70020) — pre-existing, not related to phase 2

## Blockers

- None.

## Minor Issues

- None.
