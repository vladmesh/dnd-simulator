# Task: Frontend Inventory & Equipment Panel

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 2 — Inventory UI + Gold

## Description

New frontend component: inventory panel showing 6 equipment slots, inventory bag, and gold. Equip/unequip via clicks. Replaces the minimal `PlayerStats` character section with a richer panel.

The panel has two sections:
1. **Equipment** — 6 labeled slots (weapon, armor, shield, head, feet, ring). Each slot shows item name + description if equipped, or "empty" if not. Click equipped item → send unequip action. Click inventory item that fits a slot → send equip action.
2. **Bag** — list of unequipped inventory items with name, description, price. Consumables (potions) show USE button. Equippable items show EQUIP button.

Data source: `player.equipped` and `awareness.available_items` from WS turn messages.

Key changes:
- `frontend/src/types/game.ts` — add `EquippedInfo` type, add `equipped` to `PlayerStatus`, add `price` to `ItemInfo`, add equip/unequip action names
- `frontend/src/components/game/InventoryPanel.tsx` — new component
- `frontend/src/components/game/PlayerStats.tsx` — integrate inventory panel (or replace character section)
- `frontend/src/store/` — store equipped items from player data

## Tests First

1. **Equipment slots render:** player with sword in weapon slot and ring in ring slot → panel shows "Longsword" in weapon slot, "Ring of Protection" in ring slot, other 4 slots show empty state.
2. **Inventory bag renders:** player with healing potion (price 50) in inventory → bag shows "Healing Potion" with price "50g".
3. **Unequip sends action:** click equipped weapon → WS sends `{type: "action", name: "unequip", params: {}}` (or slot-specific unequip action).
4. **Equip from bag sends action:** click equip button on a weapon in bag → WS sends `{type: "action", name: "equip_weapon", params: {weapon_id: "item_id"}}`.

Note: Frontend tests are verified via Playwright E2E during phase close, not unit tests. The "Tests First" here describes the scenarios to validate.

## Implementation

1. Update `frontend/src/types/game.ts`:
   - Add `EquippedInfo` interface: `{ slot: string; item_id: string; name: string; description: string }`
   - Add `equipped?: EquippedInfo[]` to `PlayerStatus`
   - Add `inventory?: ItemInfo[]` to `PlayerStatus`
   - Add `price?: number | null` to `ItemInfo`
   - Add equip/unequip action names to `ActionName` type

2. Create `frontend/src/components/game/InventoryPanel.tsx`:
   - Equipment section: 6 slots grid, each shows slot label + item or empty
   - Bag section: scrollable list of inventory items
   - Equip button on equippable items, unequip on equipped items
   - Use `wsClient.sendAction()` for equip/unequip actions

3. Update `PlayerStats.tsx` to include `InventoryPanel` below ability scores.

4. Update store if needed to track equipped/inventory from WS messages.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Equipment panel shows 6 slots with equipped items
- [ ] Inventory bag shows unequipped items with prices
- [ ] Equip/unequip actions dispatch via WebSocket
- [ ] Gold displayed (already exists, verify not broken)

## Status

`done`

## Developer Notes

Created InventoryPanel component with 6 equipment slots (2-column grid) and a scrollable bag section. Equipment slots show item name when equipped (click to unequip) or slot label when empty. Bag items show name, price, and contextual buttons (USE for consumables, EQUIP for equippable items). Integrated below ability scores in PlayerStats via a border separator. Added i18n keys for both EN and RU. TypeScript types updated with EquippedInfo, price on ItemInfo, and equipped/inventory on PlayerStatus.
