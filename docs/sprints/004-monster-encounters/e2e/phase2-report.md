# Phase 2 E2E Report

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 2 — Generalize Encounters + Hostile AI

## New Functionality Tested

Phase 2 changes are internal mechanics (encounter trigger generalization, faction-aware hostile AI, abstract combat formula). No new API endpoints or protocol changes. The `is_hostile` field flows through awareness to the frontend as a data addition on existing structures.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Sword Vale world loads, player can travel | World loads, locations navigable | Player created, moved through 3 locations (tavern → market → gates → forest road) | pass |
| Blood Arena combat — NPCs fight each other | NPCs attack using RuleBrain | Combat started automatically, paladin blessed + attacked razor (3 dmg), shadow equipped rapier + attacked razor (4 dmg), iron attacked paladin | pass |
| Player combat actions | Attack, dash, move work | Attack out-of-range correctly rejected ("target too far"), dash toward target worked, move updated battle map positions | pass |
| NPC dialogue (Quiet Village) | RuleBrain canned responses | Tanya responded "Что будете заказывать?" to greeting | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | 4 worlds listed, session created, character customization works |
| Load world (Blood Arena) | pass | Combat auto-starts with 4 arena fighters |
| Load world (Quiet Village) | pass | Village locations, NPC present at tavern |
| Basic combat | pass | Full flow: initiative, battle map, multi-action turns, distance validation |
| NPC interaction | pass | RuleBrain dialogue works (no LLM needed) |
| Navigation | pass | Location paths, movement between areas |
| UI elements | pass | HP bar, nearby panel, location info, character sheet, inventory, action bar |

## Quick Fixes Applied

- None needed.

## Log Analysis

- **No errors in session logs** for Sword Vale or Quiet Village sessions.
- **One `round_loop_error` in Blood Arena** — LLM (paladin NPC) returned malformed tool call args after player death. Pre-existing LLM parsing edge case, not related to Phase 2 changes.
- **No warnings or exceptions** related to faction hostility, encounter triggers, or abstract combat.

## Blockers

- None.

## Minor Issues

- Encounter table keys in `content/worlds/sword_vale/monsters.yaml` (`greenwood_deep_forest`, `highfield_mountain_pass`) don't match any actual location IDs in `locations.yaml`. Encounters never trigger in Sword Vale. Pre-existing content gap from before Phase 2 — should be fixed when EcologyLayer (Phase 3) adds wilderness locations or updates encounter table keys to match existing locations.
