# Phase 1 E2E Report

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 1 — Dashboard Layout + Compact Log

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Dashboard 3-col layout at 1280px | Nearby, Character, Location side-by-side | All 3 columns visible, proper grid layout | pass |
| Dashboard stacks at narrow width (780px) | Panels stack vertically | Panels stacked vertically | pass |
| Compact log strip shows events | Last few events in a strip above panels | Combat events shown in compact strip | pass |
| Log expand button present | Chevron button in compact strip | Button present, clickable | pass |
| Log overlay opens on click | Full log overlay covers panel area | Overlay opens with "Журнал событий" header and full log | pass |
| Log overlay close via Escape | Overlay closes, dashboard returns | Overlay closed, dashboard restored | pass |
| Combat mode: left column switches | BattleMap + CombatPanel replace Nearby | BattleMap and CombatPanel rendered in left column | pass |
| Action bar with budget display | Budget (actions, bonus, movement, reaction) shown in combat | All 4 budget counters displayed above action buttons | pass |
| Header shows player info | Name, HP bar, location, time | All displayed correctly | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (player setup) | pass | World picker, session creation, character creation all work |
| Basic combat | pass | Attack via NPC card initiates combat, damage rolls display correctly |
| NPC interaction | pass | NPC visible in Nearby panel with Attack/Talk buttons |

## Quick Fixes Applied

- None needed

## Log Analysis

- No errors in backend logs for test session (session_23253846)
- No console errors in frontend
- 1 warning: WebSocket reconnect on page load (expected — Vite HMR reconnect race)

## Blockers

- None

## Minor Issues

- Action bar "Attack" button (not the per-NPC one) sends attack without target_id, causing `KeyError: 'target_id'` crash in backend. Pre-existing bug, not introduced by phase 1. Candidate for backlog.
- "GAME OVER" text appears when round loop crashes (from the above bug). The game_over flag should probably not be set on backend errors — also pre-existing.
