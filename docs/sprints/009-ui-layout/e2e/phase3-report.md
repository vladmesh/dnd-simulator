# Phase 3 E2E Report

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 3 — Action Bar Redesign + Potions

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Action bar core buttons (peaceful) | Attack, Look, Say, Wait, End Turn visible | All present with correct labels | pass |
| Class features drawer (peaceful) | Drawer button with count, opens popup with Second Wind | "1" button opens popup showing "Второе дыхание" with bonus_action tag | pass |
| Drawer hides when empty | No drawer if no items to show | Consumables drawer absent (no potions), only class features drawer shown | pass |
| Action bar in combat | Budget display + combat actions visible | Actions/Bonus/Movement/Reaction counters shown, full combat action set | pass |
| Budget updates on use | Spending bonus action decrements counter | "Бонус: 0" after Second Wind, drawer button disappears (resource spent) | pass |
| Budget updates on action | Spending action decrements counter | "Действия: 0" after attack, action-cost buttons hidden | pass |
| Budget refreshes on new turn | Full budget at turn start | All counters reset to max at round 3 | pass |
| Movement budget tracking | Movement decrements as you move | 30→25→20→15 as player moved 5ft increments | pass |
| Combat action bar filtering | Only affordable actions shown | After spending action, only Movement + End Turn remain | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Landing page load | pass | Player/DM split, world list |
| Create session + character | pass | Sword Coast world, default Fighter |
| Dashboard layout (3 panels) | pass | Nearby, Character+Equipment, Location all visible |
| Initiate combat | pass | Combat started, initiative shown, battle map rendered |
| Attack + damage | pass | d20 roll, damage applied, log formatted |
| Movement in combat | pass | Directional drawer (toward/away), map updates |
| End turn / round advance | pass | NPC acts, round counter increments |
| Log aggregation | pass | Consecutive moves aggregated ("moved (10 ft)") |
| Exit session | pass | Returns to landing page |

## Quick Fixes Applied

None needed.

## Log Analysis

- 0 browser console errors
- Backend log shows a pre-existing error: `e2e_goblin` NPC spawn with wrong location ID `salty_anchor` (should be `silverport_city_tavern`). This is from a previous E2E run's master panel test, not related to Phase 3.
- No other errors, warnings, or exceptions in backend logs.

## Blockers

None.

## Minor Issues

- Pre-existing: `e2e_goblin` location ID mismatch in master creature spawn (not Phase 3 related, logged in previous E2E reports)
