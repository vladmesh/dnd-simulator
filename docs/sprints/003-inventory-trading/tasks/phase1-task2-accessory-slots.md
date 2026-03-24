# Task: Accessory Slots with Modifier Effects

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 1 — Accessory Slots + Modifiers

## Description

Add accessory item type with 3 new equipment slots (head, feet, ring). Accessories grant stat modifiers through the existing modifier pipeline. Full vertical slice: model → actions → handlers → modifiers → content loader → awareness → YAML content.

Key changes:
- `core/items.py` — `ItemType.ACCESSORY`, `AccessoryDef` (accessory_id, slot: EquipmentSlot, grant_modifiers)
- `core/character.py` — 3 new fields: `equipped_head`, `equipped_feet`, `equipped_ring`
- `core/items.py` — extend EquipmentSlot with HEAD, FEET, RING entries
- `core/action.py` — 6 new ActionTypes (EQUIP_HEAD/UNEQUIP_HEAD, EQUIP_FEET/UNEQUIP_FEET, EQUIP_RING/UNEQUIP_RING)
- `core/action_defs.py` — 6 new ActionDef registrations
- `rules/modifiers.py` — `collect_self_modifiers()` picks up grant_modifiers from equipped accessories
- `rules/action_provider.py` — EquipmentActionProvider already handles new slots via EquipmentSlot iteration (from task 1)
- `content_loader.py` — parse AccessoryDef from YAML, parse_equipped for new slots
- `core/awareness.py` — describe_item() handles accessories
- YAML content — Iron Helmet (+1 AC), Boots of Striding (+5 speed), Ring of Protection (+1 AC)

## Tests First

1. **Ring of Protection grants AC:** creature with base AC 10 equips Ring of Protection (+1 AC) → `effective_ac()` returns 11. Unequip → returns to 10.
2. **Boots of Striding grant speed:** creature with base speed 30 equips Boots of Striding (+5 speed) → `effective_speed()` returns 35. Unequip → back to 30.
3. **Iron Helmet grants AC:** equip helmet → AC increases by 1. Stacks with armor: creature in chain mail (AC 16) + helmet → effective AC 17.
4. **Accessory + armor + shield stack:** creature with chain mail (16 AC) + shield (+2) + ring (+1) → effective AC 19.
5. **Wrong slot rejected:** attempt to equip a ring into the head slot → fails. Attempt to equip a weapon as accessory → fails.
6. **Content loader round-trip:** YAML with accessories (some equipped: true) → creature has correct items in slots and inventory.
7. **Awareness describes accessories:** equipped ring shows in item description with its modifier effect.

## Implementation

1. Add `AccessoryDef` frozen dataclass to `core/items.py` with `accessory_id: str`, `slot: EquipmentSlot`, `grant_modifiers: tuple[Modifier, ...]`.
2. Add `ItemType.ACCESSORY`. Add `Item.accessory_def: AccessoryDef | None`.
3. Extend `EquipmentSlot` with HEAD, FEET, RING entries (item_type=ACCESSORY for all).
4. Add `equipped_head`, `equipped_feet`, `equipped_ring` fields to `Creature`.
5. Add 6 ActionType values + 6 ActionDef registrations.
6. Register handlers via generic mechanism from task 1 — no new handler code needed.
7. In `rules/modifiers.py` `collect_self_modifiers()`: iterate accessory slots, extend modifiers with `accessory_def.grant_modifiers`.
8. In `content_loader.py`: add `_parse_accessory_def()`, extend `parse_items()` to handle type=accessory with slot/modifiers, add parse_equipped for new slots.
9. In `core/awareness.py`: extend `describe_item()` to show accessory modifier info.
10. Create sample accessories in YAML content (test world + main world).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `effective_ac()` and `effective_speed()` reflect equipped accessory modifiers
- [ ] Accessories load from YAML with `equipped: true` support
- [ ] Awareness includes accessory descriptions

## Status

`pending`
