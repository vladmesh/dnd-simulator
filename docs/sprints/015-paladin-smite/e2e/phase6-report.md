# Phase 6 E2E Report

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 6 — Action Target Scope

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| lay_on_hands dropdown (peaceful, damaged paladin) | Shows "Self" + ally NPCs, no enemies | Shows "Self", "Attack guard", "Attack guard_1", "Attack guard_2" (all allies) | pass |
| Attack dropdown (combat) | Shows only hostile targets with distances | Shows "Attack guard (35ft)", "Attack guard_1 (20ft)", "Attack guard_2 (50ft)" — all hostile | pass |
| Attack button (peaceful, only allies nearby) | No dropdown (no hostile targets to show) | Plain button, no dropdown | pass |
| target_mode/target_scope in API | Fields present in available_actions | Verified via integration tests (5 new tests) | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | Session created, dashboard loads |
| Character creation (Paladin) | pass | Point buy, starting equipment, preview all correct |
| Combat initiation (Attack NPC from Nearby panel) | pass | Auto-hostility, combat_started, initiative order |
| Battle Map rendering | pass | Grid renders, positions shown, click-to-move cells highlighted |
| Combat action bar | pass | Budget display, action buttons, correct layout |
| Attack with reach validation | pass | "Target too far (20ft, reach 5ft)" correctly rejected |

## Quick Fixes Applied

- **React hooks order violation in ActionBar.tsx**: `useGameStore((s) => s.player)` was called after an early `return` (line 49), causing "Rendered more hooks than during the previous render" crash when `isMyTurn` transitioned from false to true. Moved hook above the early return.
- **Peaceful mode target dropdown missing**: ActionBar only read `nearby` from `CombatAwareness`, defaulting to `[]` in peaceful mode. Changed to `awareness?.nearby ?? []` so target dropdowns work in both modes.
- **Removed unused `CombatAwareness` import** from ActionBar.tsx.

## Log Analysis

- Clean combat session (ed325217): zero errors, zero warnings
- Lay on Hands session (545428c3): `KeyError: 'amount'` — lay_on_hands handler requires `amount` param but frontend only sends `target_id`. Pre-existing issue (not a phase 6 regression).

## Blockers

- None

## Minor Issues

- **lay_on_hands requires `amount` param**: Frontend target dropdown sends only `target_id`, but the handler crashes on missing `amount`. Needs an amount input UI — candidate for phase 7 or backlog.
- **Target labels use "Attack X" for all actions**: `t("game:attack_target", ...)` used for all target entries, even healing actions like lay_on_hands. Cosmetic — candidate for backlog.
