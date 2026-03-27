# Phase 5 E2E Report

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 5 — Combat Layout + Click-to-Move

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Combat layout restructure — left column | CombatPanel takes full left column (self stats, enemies, round info) | CombatPanel shows round number, HP bar, AC, speed, weapon, enemies with distance | pass |
| Combat layout restructure — right column | BattleMap replaces LocationPanel in combat | BattleMap renders as CSS Grid in right column, LocationPanel hidden | pass |
| BattleMap CSS Grid rendering | Grid cells with player `@`, numbered enemies, walls | Grid shows `@` for player, `1` for marta, clickable reachable cells with cursor=pointer | pass |
| Click-to-move — reachable cells | Cells within movement range are clickable | Reachable cells have cursor=pointer, unreachable cells don't | pass |
| Click-to-move — movement | Click reachable cell → player moves, budget decreases | Clicked cell right of player → `@` moved, budget 30ft → 25ft, enemy distance updated 35ft → 40ft | pass |
| Click-to-move — budget reset | End turn → new turn has full movement budget | After end turn, round advanced to 2, movement reset to 30ft | pass |
| Action bar in combat | Budget display + action buttons | Budget shows actions:1, bonus:1, movement:30ft, reaction:1. Buttons: Бегство, Атаковать, Рывок, Уклонение, Отход, potions, Конец хода | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Landing page | pass | Player/DM cards, language toggle visible |
| World selection + character creation | pass | Долина Мечей selected, default character created |
| Peaceful dashboard layout | pass | All 3 panels (Nearby, Character+Inventory, Location) visible simultaneously |
| Talk to NPC (rule-based) | pass | Said "Hello there!", NPC replied "Что будете заказывать?" |
| Combat initiation | pass | Attack → combat starts, initiative order shown |
| Log formatting | pass | Combat events with icons, turn headers |

## Quick Fixes Applied

None needed.

## Log Analysis

- No errors or exceptions in backend logs
- No browser console errors (only expected WS reconnection warning during session switch)
- One `action_failed` log entry from previous E2E run (target too far) — expected behavior
- Frontend proxy error during startup race (vite started before backend) — cosmetic

## Blockers

None.

## Minor Issues

None.
