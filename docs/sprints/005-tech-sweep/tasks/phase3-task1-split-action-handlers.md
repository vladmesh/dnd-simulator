# Task: Split action_handlers.py into domain modules

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 3 — Growing Files Split

## Description

Split `rules/action_handlers.py` (607 LOC) into a `rules/handlers/` package with domain-specific modules:

- `rules/handlers/combat.py` — handle_attack, handle_dodge, handle_flee (combat actions that emit events)
- `rules/handlers/movement.py` — handle_move, handle_dash, handle_disengage, handle_wait (position/time actions)
- `rules/handlers/equipment.py` — SlotConfig, SLOT_CONFIGS, _handle_equip_slot, _handle_unequip_slot, and all 12 public equip/unequip wrappers
- `rules/handlers/trade.py` — _resolve_merchant, handle_buy, handle_sell
- `rules/handlers/items.py` — handle_idle, handle_say, handle_use_item, handle_bless, handle_second_wind (misc item/buff/class-feature actions)
- `rules/handlers/__init__.py` — re-exports all public handles so `from dnd_simulator.rules.handlers import handle_attack` works

Update `action_dispatcher.py` imports to point to `rules.handlers` instead of `rules.action_handlers`. Delete the old `action_handlers.py`. Update test imports.

## Tests First

No new behavioral tests needed — this is a pure structural refactor. The verification is:

- All existing tests in test_action_dispatcher.py, test_combat_awareness.py, test_second_wind.py, test_trade_handlers.py pass without modification (beyond import path changes)
- `make check` passes (lint + typecheck + tests)
- Each new module imports cleanly and contains only its domain's handlers

## Implementation

1. Create `rules/handlers/` package with `__init__.py`
2. Move functions into domain modules, preserving exact signatures and behavior
3. Add re-exports in `__init__.py`
4. Update `action_dispatcher.py` to import from `rules.handlers`
5. Update test imports
6. Delete `rules/action_handlers.py`
7. Verify `make check`

## Acceptance Criteria

- [ ] `rules/action_handlers.py` deleted
- [ ] `rules/handlers/` package exists with 5 domain modules + `__init__.py`
- [ ] `action_dispatcher.py` imports from new location
- [ ] All existing tests pass (`make check`)
- [ ] No circular imports

## Status

`pending`
