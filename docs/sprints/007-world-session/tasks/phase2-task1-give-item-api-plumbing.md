# Task: Give Item API Plumbing — Backend Response + TS Types + Client Method

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 2 — Master Controls + Give Item UI

## Description

Wire up the give_item endpoint to the frontend. Three concrete changes:

1. **Backend: expose inventory in creature detail.** `_entity_detail()` in `query_handler.py` doesn't return `inventory` or `equipped_weapon`/`equipped_armor`/`equipped_shield`. The master UI needs to see what a creature has before giving more items. Add these fields to the creature detail response.

2. **TS types.** Add `GiveItemRequest` interface to `frontend/src/types/api.ts` matching the backend `GiveItemRequest` schema (name, type, price, weapon fields, potion fields). Extend `CreatureResponse` with `inventory` and `equipped_weapon` fields so the UI can display them.

3. **API client method.** Add `giveItem(sessionId, entityId, data)` to `apiClient.ts` master object, calling `POST /api/master/sessions/{sid}/creatures/{eid}/items`.

## Tests First

- **Unit test (backend):** Query `ALL_CREATURES` and `ENTITY_INFO` for a creature with items in inventory and an equipped weapon. Assert the response dict includes `inventory` (list of item dicts with id, name, type) and `equipped_weapon` (dict with weapon_id, attack_name, damage, or null).
- **Unit test (backend):** Give item to a creature via `give_item()`, then query `ENTITY_INFO` — assert the item appears in response.
- **Integration test (frontend, if test runner exists):** skip — frontend has no test runner; this will be covered by E2E in task 3.

## Implementation

- `query_handler.py` `_entity_detail()`: serialize `entity.inventory` and `entity.equipped_weapon` for Creature instances. Keep it minimal — id, name, item_type for inventory items; weapon_id, attack_name, damage for equipped weapon.
- `frontend/src/types/api.ts`: add `GiveItemRequest`, extend `CreatureResponse`.
- `frontend/src/transport/apiClient.ts`: add `giveItem` method to `master` object.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `CreatureResponse` from backend includes inventory and equipment for creatures that have them
- [ ] `api.master.giveItem()` callable from frontend code
- [ ] TypeScript compiles cleanly (`npm run build` in frontend/)

## Status

`pending`
