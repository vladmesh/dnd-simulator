# Phase 1 E2E Report

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 1 — Bug Sweep

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Fighter with Defense style: AC = 19 (16+2+1) | AC 19 in UI | AC 19 | pass |
| class_features serialized in save file | fighting_style: defense in save JSON | Present | pass |
| Action bar: no mystery button "3" | Drawer button shows uses count | Shows "1" (Second Wind) | pass |
| Action names localized (Fighter) | "Short Rest", "Long Rest", "Second Wind" | All localized | pass |
| Action names localized (Paladin) | "Lay on Hands" in class features drawer | Correctly shown | pass |
| Paladin Defense style AC | AC 19 (16+2+1) | AC 19 after fix | pass (quick fix) |
| Paladin Lay on Hands in drawer | Not on main bar, in class features drawer | In drawer | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | |
| Create Fighter character | pass | AC, stats, equipment correct |
| Create Paladin character | pass | AC, stats, equipment correct |
| Game UI loads with WebSocket | pass | Connected notification shown |

## Quick Fixes Applied

- **Paladin Defense style AC:** `collect_self_modifiers()` in `rules/modifiers.py` only checked `FighterFeatures` for Defense style, missing `PaladinFeatures`. Added check for both. Same fix applied to Dueling/GWF in `attack_modifiers()`.
- **Flaky smite integration test:** `test_smite_adds_radiant_damage` failed intermittently because arena NPCs (shadow, iron, paladin NPC) spammed blocked moves, consuming the 80-message budget before the player could land a hit. Fixed by deleting unneeded NPCs in the test fixture.
- **Wrong sell test assertion:** `test_sell_item` asserted `gold == 1025` but the test explicitly patches gold to 100, so expected is `125`.

## Log Analysis

- No errors or exceptions in backend logs during E2E testing.
- Multiple "consecutive_failures_end_turn" warnings from arena NPCs trying to move to blocked cells — pre-existing RuleBrain pathfinding issue, not a regression.

## Blockers

None.

## Minor Issues

- Player character not restored when loading a session from save via API (pre-existing — player binding to session not part of save/load flow).
- Arena NPC RuleBrain movement pathfinding frequently fails with "Cannot move there — blocked" (pre-existing).
