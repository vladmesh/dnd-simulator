# Phase 3 E2E Report

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 3 — Growing Files Split

## New Functionality Tested

Phase 3 was a pure refactoring phase — no new user-facing functionality. The split modules (action_handlers → handlers/, content_loader → content_loader/, decomposed resolve_attack and query dispatcher) must produce identical behavior.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Combat attack (fists, Blood Arena) | Roll format `[d20(N)+M=T vs AC X]`, hit/miss | `[d20(5)+5=10 vs AC 13]` miss, `[d20(11)+5=16 vs AC 18]` miss — correct format | pass |
| Movement in combat | Move toward target, budget decreases | Moved 5ft south toward paladin, budget 30→25ft | pass |
| NPC turn execution | NPCs equip weapons, move, attack | Paladin moved 10ft, NPCs equipped weapons (Рапира, Меч, Палка) | pass |
| Turn budget enforcement | Actions=0 hides Attack button, shows only Move/Second Wind/End Turn | Correctly limited after using action | pass |
| World loading (Blood Arena) | 4 NPCs at arena_floor | razor, shadow, iron, paladin all visible | pass |
| World loading (Quiet Village) | Village square with paths to locations | 6 paths visible, NPC tanya at tavern | pass |
| Content loader (village NPC) | NPC loads with role, location, brain | tanya visible at tavern, responds to dialogue | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Create session (Blood Arena) | pass | Session created, redirected to /play/:id |
| Create session (Quiet Village) | pass | Session created, village square loaded |
| Combat initiation | pass | Initiative order, battle map, combat panel |
| NPC dialogue (rule-based) | pass | tanya responds "Что будете заказывать?" |
| Movement between locations | pass | Village square → Tavern, location panel updates |
| Battle map rendering | pass | Grid with numbered entities, walls, @ for player |
| Inventory panel | pass | 6 slots visible (Weapon, Armor, Shield, Head, Feet, Ring) |

## Quick Fixes Applied

None needed.

## Log Analysis

- 0 tracebacks or exceptions in backend logs
- 0 frontend console errors
- `action_failed` events at info level for NPC out-of-reach attacks and wall collisions — known behavior from previous E2E, handled gracefully
- No silent errors or unexpected warnings

## Blockers

None.

## Minor Issues

- RuleBrain paladin NPC repeatedly tries to attack out of reach (3 attempts before equipping weapon and moving). Pre-existing behavior, not a regression.
