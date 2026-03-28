# Phase 0 E2E Report

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 0 — Structured Dice & Roll Breakdown

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Attack shows structured dice in log | `d20(N)+mods=total vs AC X` format | `d20(16)+5=21 vs КЗ 10`, `4 урона (1 дробящий + +3 модификатор)` | pass |
| Expandable roll breakdown | Click chevron expands d20 + modifier components + damage breakdown | d20: [16], +3 ability, +2 proficiency = 21 vs AC 10 HIT; Damage: 4 (1 bludgeoning weapon, +3 ability) | pass |
| Second attack breakdown | Same structure on different attack | d20: [5] +3 ability +2 proficiency = 10 vs AC 10 HIT; Damage: 4 (1 bludgeoning weapon, +3 ability) | pass |
| Breakdown collapse/expand toggle | Button toggles visibility | Chevron rotates, breakdown panel toggles | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | Session created, character creation form works |
| Character creation | pass | Fighter with custom stats, joined session |
| Basic combat | pass | Attack NPC, combat starts with initiative, battle map renders |
| Travel between locations | pass | Navigated Salty Anchor -> Market Square, paths and NPCs load |
| Combat UI (budget, battle map) | pass | Actions/Bonus/Movement/Reaction budget displayed, grid with player @ and enemy 1 |
| NPC interaction (rule-based) | pass | Gretta the Merchant visible with Trade button |

## Quick Fixes Applied

- None needed

## Log Analysis

- No errors or exceptions in debug logs (session_74d633cb)
- No unhandled exceptions or tracebacks
- Single transient WebSocket reconnect warning during page transition (expected)

## Blockers

- None

## Minor Issues

- None
