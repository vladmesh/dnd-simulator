# Task: Inventory & Equipment Awareness

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 2 — Inventory UI + Gold

## Description

Backend changes to expose full inventory and equipment state to the frontend. Currently, `available_items` only includes inventory items when USE_ITEM or EQUIP actions are available, and equipped items aren't exposed at all. The frontend needs:

1. `Item.price` field — optional int, parsed from YAML
2. Full inventory always visible (not gated by action availability)
3. Equipped items visible (weapon, armor, shield, head, feet, ring) with descriptions
4. `_player_to_dict()` includes equipment + inventory in WS messages
5. `ItemInfo` gets a `price` field

Key changes:
- `core/items.py` — add `price: int | None = None` to `Item`
- `core/awareness.py` — add `price: int | None = None` to `ItemInfo`; add `EquippedInfo` dataclass; add `equipped` field to `PeacefulAwareness` and `CombatAwareness`
- `round.py` — `_build_available_items()` always returns full inventory; add `_build_equipped()` that reads all 6 slots
- `content_loader.py` — parse `price` from YAML item data
- `service/session.py` — `_player_to_dict()` includes `equipped` and `inventory` dicts
- YAML content — add prices to existing items in test worlds

## Tests First

1. **Item with price round-trips through content loader:** YAML item `{name: Healing Potion, type: potion, heal_dice: "2d4+2", price: 50}` → parsed Item has `price=50`. Item without `price` → `price is None`.
2. **Equipped items visible in awareness:** creature with sword equipped + ring equipped → awareness has `equipped` containing weapon entry (name, description) and ring entry. Empty slots are absent.
3. **Full inventory always in awareness:** creature with 3 items in inventory, no USE_ITEM action available → awareness still has all 3 items in `available_items` with names, descriptions, and prices.
4. **Player dict includes equipment and inventory:** `_player_to_dict()` for a player with chain mail equipped + healing potion in inventory → dict has `equipped` with armor entry and `inventory` with potion entry including price.
5. **ItemInfo includes price:** item with price=50 → ItemInfo has price=50. Item without price → ItemInfo has price=None.

## Implementation

1. Add `price: int | None = None` to `Item` dataclass in `core/items.py`.
2. Add `price: int | None = None` to `ItemInfo` in `core/awareness.py`.
3. Add `EquippedInfo` frozen dataclass to `core/awareness.py`: `slot: str`, `item_id: str`, `name: str`, `description: str`.
4. Add `equipped: list[EquippedInfo]` to both `PeacefulAwareness` and `CombatAwareness`.
5. In `round.py`: modify `_build_available_items()` to always return full inventory (remove action-type gate), include `price` in `ItemInfo`. Add `_build_equipped()` that reads all 6 slot fields and returns `list[EquippedInfo]`.
6. In `content_loader.py`: extract `price` from YAML item data, pass to `Item()`.
7. In `service/session.py`: extend `_player_to_dict()` to include `equipped` and `inventory` lists.
8. Add `price` field to existing YAML items in test worlds (arena, village).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `ItemInfo` includes price field
- [ ] Equipped items visible in awareness data
- [ ] Full inventory visible regardless of available actions
- [ ] Content loader parses price from YAML

## Status

`pending`
