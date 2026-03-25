# Phase 3 E2E Report

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 3 — Trading

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Trade panel visible when merchant nearby | Merchant name, gold, items displayed | Маша-торговка, 200g, 2 items shown correctly | pass |
| Buy dagger (10g) | Gold 100→90, dagger in inventory, merchant gold 200→210 | Exact match | pass |
| Sell dagger back (10g) | Gold 90→100, dagger removed, merchant gold 210→200 | Exact match | pass |
| Sell section shows sellable items | Items with prices appear in Sell list | Dagger appeared with Sell button after buying | pass |
| Buy/Sell buttons in action bar | Buy and Sell buttons visible in peaceful mode | Both present in action bar | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| World selection | pass | All 4 worlds load |
| Join session by ID | pass | |
| Character creation | pass | Gold field works |
| Arena combat (Blood Arena) | pass | Initiative, battle map, attacks, movement all work |
| Attack out of range error | pass | "Target too far (20ft, reach 5ft)" displayed |
| Round advancement | pass | NPC turns execute, round counter increments |

## Quick Fixes Applied

- **Merchant schedule location mismatch**: `_build_merchants()` in `round.py` and `get_nearby_merchants()` in `action_dispatcher.py` used `e.location_id` (raw start_location) instead of `e.current_location(hour)` (schedule-resolved location). Merchants were invisible when they moved to scheduled locations. Fixed both to use `current_location(hour)`.
- **`GiveItemRequest` missing `price` field**: Added `price: int | None` to the API schema so items given via master API can have prices (needed for sell integration tests).
- **Production village.yaml**: Added gold (200) and items (Health Potion 50g, Dagger 10g) to Masha merchant NPC, matching the sprint's trading feature.

## Log Analysis

- Zero backend errors or exceptions
- Zero frontend console errors
- Only warnings: uvicorn file-watcher reloads from hot-fix (expected)

## Blockers

None.

## Minor Issues

- NPC nearby card shows "masha" (id) instead of the display name — pre-existing, not phase 3 related
- "Cannot move there — blocked" spam in arena combat event log from RuleBrain NPCs — pre-existing pathfinding issue
