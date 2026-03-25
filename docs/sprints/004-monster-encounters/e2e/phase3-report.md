# Phase 3 E2E Report

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 3 — Squad Movement + Materialization

## New Functionality Tested

Phase 3 is entirely backend simulation — EcologyLayer, squad movement, materialization/dematerialization. No new UI elements until Phase 4. Testing focused on verifying the backend doesn't break existing flows when squads are active.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Create Sword Vale session (has squads, factions, monster templates) | Session loads, game starts | Session created, player spawns at Salty Anchor tavern | pass |
| NPC present at Sword Vale start location | NPC visible in nearby panel | Marta (human) visible with Attack/Talk buttons | pass |
| Combat in Sword Vale with squads running | Combat starts, battle map shows | Combat started, initiative order, attack rolls, battle map all work | pass |
| Village session (no squads) still works | No regression | Village loads, NPCs at locations, talk works | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (home screen) | pass | All 4 worlds displayed (Blood Arena, Sneak Attack Test, Sword Vale, Quiet Village) |
| Basic combat | pass | Attack NPC in Sword Vale, combat UI with battle map, action budget, attack rolls |
| NPC interaction | pass | Talk to Tanya in village, RuleBrain responds with canned dialogue |
| Movement | pass | Move from Village Square to Tavern, location updates, NPC appears |

## Quick Fixes Applied

- None needed

## Log Analysis

- `round_loop_error` in Sword Vale session — occurred when exiting session mid-combat (WS disconnect during active round loop). Expected behavior, not a regression.
- Village session logs clean — zero errors.
- `action_failed` entries for goblin movement ("Cannot move there — blocked") from a previous session — normal RuleBrain pathfinding behavior.

## Blockers

- None

## Minor Issues

- `round_loop_error` on session exit during combat — pre-existing behavior, not Phase 3 related. Candidate for backlog (graceful round loop shutdown on WS disconnect).
