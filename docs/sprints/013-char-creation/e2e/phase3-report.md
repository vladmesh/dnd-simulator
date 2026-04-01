# Phase 3 E2E Report

**Date:** 2026-04-02
**Sprint:** 013-char-creation
**Phase:** 3 — Content Fixes + Polish

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Create Sword Vale session | Session starts without errors | Session created successfully (after guard template fix) | pass |
| Character creation form — point buy UI | 6 abilities with +/- buttons, remaining points counter | All controls present, points decrement correctly, + disabled at 0 remaining | pass |
| Character creation form — fighting style | Defense/Dueling/GWF dropdown appears for Fighter | Dropdown appears, Defense selectable | pass |
| Character creation form — preview | HP/AC/Gold/equipment shown before submit | HP: 11, AC: 19 (chain mail+shield+defense), Gold: 100, Starting equipment: Chain Mail, Longsword, Shield | pass |
| Create Fighter (STR 15, DEX 14, CON 13) | Character with derived stats | HP 11/11, AC 19, correct ability scores, equipment auto-equipped | pass |
| Inventory shows starting equipment | Longsword, Chain Mail, Shield in equipment slots | All 3 items shown in equipped slots | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | Required guard template fix in ecology monsters.yaml |
| Basic combat (attack NPC) | pass | Longsword slash d20(12)+4=16 vs AC 10, 4 damage. NPC killed in one hit. Combat ended cleanly. |
| Game UI layout | pass | Header, log, nearby, character, inventory, location panels all render correctly |

## Quick Fixes Applied

- Added `guard` template entry (`base: guard`) to `content/library/ecology/sword_vale/monsters.yaml` — squad referenced `guard` as member but no template existed to resolve CR.
- Same fix for `content/worlds/test_vale/ecology/monsters.yaml`.

## Log Analysis

- No errors in console during E2E (0 errors after session creation fix).
- Backend debug logs show normal operation — no warnings or silent failures.

## Blockers

- None.

## Minor Issues

- None observed.
