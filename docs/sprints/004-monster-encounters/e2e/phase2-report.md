# Phase 2 E2E Report

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 2 — Generalize Encounters + Hostile AI

## New Functionality Tested

### 1. Encounter Triggers (any active creature)

Player travels from Silverport to Forest Road (`silverport_greenwood_road`). Encounter table fires, goblins and wolves spawn.

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Player moves to location with encounter table | `encounter_check_moved` logged with `has_table: true`, encounters roll | Logged: `encounter_rolling`, `encounter_roll_miss` / `encounter_spawn` | pass |
| Encounter creatures spawn at location | Goblins/wolves appear in Nearby panel | 3 goblins + 3 wolves spawned, visible in UI | pass |
| Cooldown prevents re-roll at same location | No second roll within 600s | Confirmed via logs — no re-roll on same location within cooldown | pass |
| Safe locations have no encounter table | `has_table: false` for city locations | All city locations logged with `has_table: false` | pass |

### 2. Faction-Aware Hostile AI

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Player (kingdom) sees goblins (goblin_tribe) | `faction_hostility_check`: hostile=true | `relation: hostile, hostile: true` for all 3 goblins | pass |
| Player sees wolves (wildlife) | `faction_hostility_check`: hostile=false | `relation: neutral, hostile: false` for all 3 wolves | pass |
| Player sees kingdom NPCs (Marta, Gretta) | No hostility (same faction) | `hostile: false` — same faction short-circuits, no query logged | pass |
| Goblin RuleBrain attacks player on sight | `rule_hostile_attack` in peaceful mode | goblin_1 attacked player via `rule_hostile_attack` → combat started | pass |
| Combat starts from hostile encounter | Initiative roll, battle map, full combat UI | `[combat_started]` event, 7 combatants, battle map rendered | pass |

### 3. Abstract Squad Combat (unit test only)

Pure function in `rules/abstract_combat.py` — no API exposure, no UI. Covered by 8 unit tests.

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (Sword Vale) | pass | Session created, character created, locations navigable |
| NPC at location (Marta at tavern) | pass | Visible in Nearby panel, dialogue works |
| Merchant (Gretta at market) | pass | Trade panel visible, buy/sell buttons present |
| Navigation (5 locations) | pass | Tavern → Market → Gates → Forest Road, all paths correct |
| Combat UI | pass | Battle map, initiative order, action budget, attack/move/dodge buttons |

## Content Fixes Applied

- **Encounter table keys** fixed: `greenwood_deep_forest` → `silverport_greenwood_road`, `highfield_mountain_pass` → `highfield_iron_road` (keys must match location IDs)
- **Player faction**: added `default_player_faction: kingdom` to Sword Vale `world.yaml`, plumbed through `GameSession` → `create_player`. Without this, player had empty `faction_id` and faction hostility never triggered.
- **Encounter chances** tuned: goblin 0.3→0.4, wolf 0.15→0.2 (original values too low for reliable gameplay)

## Code Changes

- **Logging added** to: `_check_encounters` (move detection, roll results), `_roll_encounters` (per-entry rolls), `_check_faction_hostility` (relation query results), `build_nearby_entities` (nearby list with hostility), `RuleBrain._peaceful_action` (hostile attack with faction info), `Round.run_loop` (active creature count per iteration)
- **`parse_player`**: reads `faction` from player data
- **`GameSession`**: new `default_player_faction` field, populated from `world.yaml`
- **`create_player`**: applies `default_player_faction` when player data has no faction

## Log Analysis

- No errors in session logs for any of the test sessions
- All encounter/faction/hostility flows visible in structured logs
- `loop_check` debug log confirmed round loop continues correctly when only player is active (no spurious exit)

## Blockers

- None.

## Minor Issues

- First WS connection sometimes disconnects immediately and reconnects (race condition in session startup). Pre-existing, not related to Phase 2. Does not affect gameplay — reconnect is automatic and transparent.
