# Phase 2 E2E Report

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 2 — Inventory UI + Gold

## New Functionality Tested

| Scenario | Expected | Actual | Status |
|----------|----------|--------|--------|
| Create character with gold | Gold field in create form, gold visible in UI | Gold field present, "100g" shown in character panel | pass |
| Empty inventory panel | 6 equipment slots shown empty | All 6 slots (weapon, armor, shield, head, feet, ring) rendered with labels | pass |
| Items appear in bag after give_item API | Longsword + Healing Potion in bag | Both items visible with descriptions | pass |
| EQUIP button on weapon | Click EQUIP → weapon moves to slot | Longsword moved to weapon slot, event log "You equip Longsword" | pass |
| Unequip by clicking slot | Click equipped item → returns to bag | Longsword returned to bag, event log "You put away Longsword" | pass |
| USE button on potion | USE button shown only on consumables | USE button on Healing Potion, EQUIP on Longsword | pass |
| Price display in bag | Items with price show gold value | Prices shown inline (verified in snapshot) | pass |
| Actions bar updates | Equip/Unequip actions appear contextually | "Equip" when weapon in bag, "Unequip" when weapon equipped | pass |

## Regression

| Scenario | Status | Notes |
|----------|--------|-------|
| Load world (village) | pass | World list, character creation, game view all work |
| Load world (arena) | pass | 4 NPCs visible, battle map renders |
| Basic combat | pass | Attack landed (d20+5=17 vs AC 13), NPCs take turns, movement works |
| NPC interaction | pass | NPCs visible with Attack/Talk buttons |

## Quick Fixes Applied

- **Frontend equip/unequip param mismatch**: inventory panel was sending `equip` with `{ item_id }` but backend expects slot-specific actions and param names (`weapon_id`, `armor_id`, etc.). Also `unequip` was sending `{ slot }` but the action takes no params (separate actions per slot). Fixed by:
  - Adding `type` and `slot` fields to inventory item data from backend
  - Frontend now maps item type to correct action name and param key
  - Unequip from slot uses slot-specific action names (`unequip`, `unequip_armor`, etc.)

## Log Analysis

- `round_loop_error` observed in first test session — caused by the equip param mismatch (KeyError on `weapon_id`). Fixed by the quick fix above.
- `ws_send_failed` at connection time — benign race condition from Playwright opening two WS connections rapidly (first closes before send completes).
- No other errors or warnings in logs after the fix.

## Blockers

- None

## Minor Issues

- Event log shows raw event type tags like `[entity_equip]` — cosmetic, not a blocker
- World list occasionally shows spinner on navigation (stale frontend state) — resolved by page reload
