# Task: Generic Equip/Unequip Mechanism

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 1 — Accessory Slots + Modifiers

## Description

Refactor the 6 existing equip/unequip handlers (weapon, armor, shield) into a single generic slot-based mechanism. Introduce `EquipmentSlot` enum that maps slot → ItemType, param key, Creature field name, event field. Replace the 6 copy-pasted handler functions with a factory or generic handler that dispatches by slot config.

Key files:
- `core/items.py` — add EquipmentSlot enum
- `rules/action_handlers.py` — replace 6 handlers with generic mechanism (~220 → ~50 lines)
- `rules/action_provider.py` — consolidate EquipmentActionProvider + ArmorEquipmentProvider into one slot-driven provider
- `service/action_dispatcher.py` — update handler registration

Zero new functionality. All existing equip/unequip behavior preserved exactly.

## Tests First

Product-level scenarios to verify the refactor doesn't break anything:

1. **Weapon swap mid-combat:** creature with sword in inventory and axe equipped → equip sword → axe returns to inventory, sword is now equipped, attack uses sword's damage
2. **Armor equip affects AC:** creature with chain mail in inventory → equip armor → effective_ac reflects chain mail's base_ac + dex modifier
3. **Shield equip/unequip round-trip:** equip shield → AC increases by shield bonus → unequip → AC drops back, shield is in inventory
4. **Unequip weapon to bare hands:** creature with equipped sword → unequip → falls back to unarmed strike, sword in inventory
5. **Cannot equip item not in inventory:** attempt to equip weapon_id that doesn't exist → ActionResult.success=False

These tests exercise the full chain: action dispatch → handler → creature state → downstream effects (AC, attacks). They should pass before AND after the refactor.

## Implementation

1. Add `EquipmentSlot` enum to `core/items.py` with entries for WEAPON, ARMOR, SHIELD. Each entry carries: `item_type`, `param_key`, `creature_field`, `event_field`.
2. Create `_handle_equip_slot(slot: EquipmentSlot, actor, action, emit_fn)` generic function in `action_handlers.py`.
3. Create `_handle_unequip_slot(slot: EquipmentSlot, actor, action, emit_fn)` generic function.
4. Replace `handle_equip`, `handle_equip_armor`, `handle_equip_shield` (and their unequip counterparts) with thin wrappers calling the generic functions.
5. Consolidate action providers into one `EquipmentActionProvider` that iterates EquipmentSlot entries.
6. Verify `make check` green.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Net reduction in lines of code in action_handlers.py
- [x] All 6 existing equip/unequip action types work identically

## Status

`done`

## Developer Notes

Introduced `SlotConfig` dataclass + `SLOT_CONFIGS` dict in `action_handlers.py`. Generic `_handle_equip_slot`/`_handle_unequip_slot` replace ~170 lines of copy-paste with ~60 lines. Public wrapper functions preserved for backward compatibility.

Fixed latent param key bug: `handle_equip_armor` and `handle_equip_shield` were reading `action.params["item_id"]` but their ActionDefs declared `armor_id`/`shield_id`. The generic mechanism now uses the correct param keys from SlotConfig.

`ArmorEquipmentProvider` merged into `EquipmentActionProvider` (generic slot iteration). Alias kept for backward compatibility.

action_handlers.py: 462 → 426 lines (-36 net). action_provider.py: 136 → 113 lines (-23 net).
