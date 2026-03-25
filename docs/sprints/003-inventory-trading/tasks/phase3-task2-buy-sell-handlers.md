# Task: Buy/Sell Action Handlers + Dispatch

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 3 — Trading

## Description

Wire BUY/SELL actions through the full dispatch pipeline: handlers, dispatcher registration, action provider, event perception, awareness exposure.

**Action handlers** (`rules/action_handlers.py`):
- `handle_buy(actor, action, emit_fn, ctx, world)` — resolve merchant from `merchant_id` param via world entities, call `validate_buy`, call `execute_buy`, emit `ENTITY_BUY` event.
- `handle_sell(actor, action, emit_fn, ctx, world)` — same pattern for selling.

**Dispatcher** (`service/action_dispatcher.py`):
- Register both handlers in `create_dispatcher()`.

**Action provider** (`rules/action_provider.py`):
- New `TradeActionProvider` — returns `[ActionType.BUY, ActionType.SELL]` when a merchant NPC is at the same location as the creature. Needs access to world/entities to check co-location — check how existing providers get context from `ActionContext`.

**Validation** (`rules/validation.py`):
- BUY/SELL validation: merchant_id and item_id params are required, merchant exists and is at same location.

**Perception** (`layers/entities/perception.py`):
- `_perceive_buy()` / `_perceive_sell()` — "X bought Y from Z for N gold" / "X sold Y to Z for N gold".

**Awareness**:
- When BUY/SELL are available actions, the frontend needs to know which merchants are nearby and what they sell. Extend awareness or add a new field (e.g. `merchants: list[MerchantInfo]` on PeacefulAwareness) with merchant_id, name, items (id, name, price), gold.

## Tests First

Scenarios for `tests/unit/test_trade_handlers.py`:

1. **Full buy flow** — set up world with player + merchant at same location. Dispatch BUY action → player gets item, gold transfers, ENTITY_BUY event emitted with correct data.
2. **Full sell flow** — dispatch SELL action → merchant gets item, gold transfers, ENTITY_SELL event emitted.
3. **Buy validation rejects** — insufficient gold → dispatch returns error, no mutation.
4. **TradeActionProvider** — merchant at same location → BUY/SELL available. No merchant → not available. Merchant at different location → not available.
5. **Perception** — ENTITY_BUY event perceived as "Player bought Health Potion from Merchant for 50 gold".

## Implementation

1. `handle_buy` / `handle_sell` in `action_handlers.py` — look up merchant via world entity query, delegate to `rules/trade.py`.
2. Register in `create_dispatcher()`.
3. `TradeActionProvider` in `action_provider.py` — check nearby entities for merchants.
4. Add perception handlers for ENTITY_BUY/ENTITY_SELL.
5. Add `MerchantInfo` dataclass to `core/awareness.py`. Add `merchants` field to `PeacefulAwareness`.
6. Build merchant awareness in `round.py` alongside existing awareness building.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] BUY/SELL go through full dispatcher pipeline (validate → execute → emit → perceive)
- [ ] Awareness exposes merchant inventory to frontend

## Status

`done`

## Developer Notes

Full dispatch pipeline wired: handlers → dispatcher → provider → perception → awareness.
- `handle_buy`/`handle_sell` in action_handlers: resolve merchant via ctx.get_entity, delegate to rules/trade.py, emit events.
- `MerchantActionProvider` takes a `NearbyMerchantsFn` callable (injected by dispatcher factory), returns BUY/SELL when merchants co-located.
- Perception: "You buy X from Y for Z gold" / third-person variants.
- `MerchantInfo` dataclass added to awareness; `PeacefulAwareness.merchants` populated in round.py peaceful turn.
- Used `build_peaceful_awareness` directly (not `build_awareness`) to satisfy mypy — peaceful turn always produces `PeacefulAwareness`.
- Dispatcher factory builds the nearby-merchants callable by closing over the `EntitiesLayer` reference.
