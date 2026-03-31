# Phase 4 E2E Report

**Date:** 2026-03-31
**Sprint:** 012-reactions-oa
**Phase:** 4 — Audit Refactor

## New Functionality Tested

Phase 4 was a refactor phase — no new user-facing features. Testing focused on regression.

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | DM world editor shows all layers correctly |
| Create session | pass | New Session from DM tab and Play tab both work |
| Create character | pass | Form renders, character created, game loads |
| Basic combat | pass | Attack NPC, damage displayed in log, battle map renders |
| NPC turn | pass | Marta moved (15ft), attacked player, damage applied (9/10 HP) |
| Reaction prompt (OA) | pass | "Reaction!" popup with "Melee attack against Marta" / "Skip" appeared when NPC left reach |
| Battle map | pass | `@` and `1` glyphs, click-to-move cells highlighted |
| Action bar | pass | Dodge, Dash, Flee, Disengage, Attack, Second Wind, End Turn all visible |
| Turn budget display | pass | Actions: 1, Bonus: 1, Movement: 30ft, Reaction: 1 |

## Quick Fixes Applied

- `BattleMap.set_position()` — removed silent clamping, now raises `ValueError` on out-of-bounds positions
- `oa_test` world — battle map enlarged from 25x25 to 60x60 to fit guard combat_position values
- `test_two_enemies_both_oa` — redesigned: both guards adjacent to player, single move triggers both OAs
- Unit test updated: `test_set_position_clamps_to_bounds` → `test_set_position_rejects_out_of_bounds`

## Log Analysis

- No errors or exceptions in backend logs
- NPC `action_failed` at info level (move with no budget, target out of reach) — normal RuleBrain behavior
- Vite EPIPE on ws disconnect — cosmetic, not a problem

## Blockers

- None

## Minor Issues

- None
