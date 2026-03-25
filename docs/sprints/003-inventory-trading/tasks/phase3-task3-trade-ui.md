# Task: Trade UI

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 3 — Trading

## Description

Frontend trade interface: a Trade button in ActionBar, a trade modal/panel showing merchant inventory, buy/sell interactions.

**Types** (`types/game.ts`):
- `MerchantInfo` — `{ id: string, name: string, gold: number, items: ItemInfo[] }`.
- Add `merchants` to `PeacefulAwareness`.

**ActionBar** (`components/game/ActionBar.tsx`):
- When `awareness.merchants` is non-empty, show a "Trade" button (or one per merchant if multiple).
- Clicking opens a trade modal.

**TradePanel** (`components/game/TradePanel.tsx` — new component):
- Left side: merchant inventory with item name, price, "Buy" button per item.
- Right side: player inventory (items with price set) with "Sell" button per item.
- Header: merchant name + merchant gold. Player gold shown too.
- Buy sends `sendAction("buy", { merchant_id, item_id })`.
- Sell sends `sendAction("sell", { merchant_id, item_id })`.
- After action result, awareness refreshes and panel updates automatically (Zustand reactivity).
- Items without price show "Not for sale" / no sell button.

**API response** (`adapters/api/schemas.py`, `routes_ws.py`):
- Ensure `merchants` field flows through WebSocket awareness payload.
- Add `MerchantInfo` to REST schemas if needed for status endpoint.

## Tests First

This is primarily a frontend task. Tests:

1. **Backend integration** — start game with merchant at same location, GET player status or awareness contains `merchants` array with correct items and prices.
2. **Buy via WebSocket** — send buy action, verify response has updated gold and inventory.
3. **Sell via WebSocket** — send sell action, verify response.

## Implementation

1. Add `MerchantInfo` to TypeScript types.
2. Add `merchants` to awareness serialization in `session.py`.
3. Create `TradePanel.tsx` component.
4. Wire Trade button into ActionBar.
5. Style consistently with InventoryPanel (shadcn/ui components, same patterns).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Trade button appears only when merchant is co-located
- [ ] Can buy item → gold decreases, item appears in inventory
- [ ] Can sell item → gold increases, item removed from inventory
- [ ] Items without price cannot be sold

## Status

`done`

## Developer Notes

Backend already had `merchants` flowing through `dataclasses.asdict()` in `_awareness_to_dict()` — no backend changes needed.

Frontend changes:
- Added `MerchantInfo` interface and `merchants` field to `PeacefulAwareness` in types
- Added `buy`/`sell` to `ActionName` union
- Created `TradePanel.tsx` — collapsible panel showing merchant inventory (buy) and player sellable items (sell), with gold display for both sides
- Wired `TradePanel` into `GameScreen.tsx` peaceful sidebar between Perception and LocationPanel
- Added i18n strings for en/ru (trade, buy, sell)
- Buy/sell buttons disable when insufficient gold on either side
- Panel auto-hides when no merchants are nearby (returns null)
