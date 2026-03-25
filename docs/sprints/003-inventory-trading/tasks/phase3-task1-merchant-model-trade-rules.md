# Task: Merchant Model + Trade Rules

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 3 — Trading

## Description

Add merchant capability to NPCs and pure trade validation/execution rules.

**Model changes:**
- `Npc.is_merchant` — property derived from `role == "merchant"`. Single source of truth for the check.
- `Npc.gold` — already inherited from Character, but content_loader doesn't parse it for NPCs. Wire it up.
- Items on merchant NPCs get `price` from YAML. Items without price can't be traded.

**New action types:**
- `ActionType.BUY` — player buys item from merchant's inventory
- `ActionType.SELL` — player sells item from own inventory to merchant

**Pure trade rules** (`rules/trade.py`):
- `validate_buy(buyer, seller, item_id)` → error string or None. Checks: seller is merchant, seller has item, item has price, buyer has enough gold, same location.
- `validate_sell(seller, buyer, item_id)` → error string or None. Checks: buyer is merchant, seller has item, item has price, buyer has enough gold for the item.
- `execute_buy(buyer, seller, item)` → mutates gold and inventory on both sides.
- `execute_sell(seller, buyer, item)` → mutates gold and inventory on both sides.

**YAML content:**
- New merchant NPC in `sword_vale/npcs.yaml` at `silverport_city_market` with `role: merchant`, gold, and a few priced items (health potion, a simple weapon, an accessory).
- Add prices to existing items in player YAML so they can be sold.

**ActionDef registration:**
- `BUY`: cost FREE (trade doesn't consume action economy), PEACEFUL_ONLY, params: `merchant_id` (string, required), `item_id` (string, required).
- `SELL`: same shape.

## Tests First

Scenarios for `tests/unit/test_trade.py`:

1. **Buy success** — merchant has a 50gp health potion, player has 100gp. Buy → player gets potion, player gold = 50, merchant gold += 50, merchant loses the item.
2. **Buy insufficient gold** — player has 10gp, item costs 50gp → validation error.
3. **Buy item not in merchant inventory** — bogus item_id → validation error.
4. **Buy item without price** — item exists but price is None → validation error.
5. **Sell success** — player has a 30gp dagger, merchant has 100gp. Sell → merchant gets dagger, merchant gold -= 30, player gold += 30.
6. **Sell insufficient merchant gold** — merchant has 5gp, item costs 30gp → validation error.
7. **Not a merchant** — trying to buy from a non-merchant NPC → validation error.
8. **Different location** — merchant is at market, player is at tavern → validation error.

## Implementation

1. Add `BUY`/`SELL` to `ActionType` enum in `core/action.py`.
2. Add `ENTITY_BUY`/`ENTITY_SELL` to `EventType` in `core/models.py`.
3. Create `rules/trade.py` with validate/execute functions.
4. Register `ActionDef` entries for BUY/SELL in `core/action_defs.py`.
5. Wire `gold` parsing for NPCs in `content_loader.py` (same as player: `gold=int(ndata.get("gold", 0))`).
6. Add merchant NPC to `sword_vale/npcs.yaml` with items and gold.
7. Add prices to player starting items where appropriate.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `validate_buy`/`validate_sell` are pure functions in `rules/` — no I/O, no state
- [ ] Merchant NPC loads from YAML with gold and priced items

## Status

`pending`
