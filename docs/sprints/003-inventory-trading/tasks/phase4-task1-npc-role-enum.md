# Task: NpcRole Enum + Fix rules→layers Dependency

**Date:** 2026-03-25
**Sprint:** 003-inventory-trading
**Phase:** 4 — Audit Refactor

## Description

Fix two related audit findings: (1) `rules/trade.py` and `rules/action_handlers.py` import `Npc` from `layers/entities/models.py` — rules/ must depend only on core/. (2) `Npc.role == "merchant"` uses a hardcoded string instead of an enum.

Concrete changes:
- Add `NpcRole` enum to `core/character.py` (values: BLACKSMITH, TAVERN_KEEPER, GUARD, MERCHANT, FARMER, plus COMMONER default)
- Add `is_merchant` property on `Character` base class (returns `False`) so rules/ can type-check against `Character` instead of `Npc`
- Change `Npc.role` field from `str` to `NpcRole`
- Update `Npc.is_merchant` to use `self.role == NpcRole.MERCHANT`
- Change `rules/trade.py` to accept `Character` instead of `Npc` — no more layers/ import
- Change `rules/action_handlers.py:_resolve_merchant` to use `Character` + `is_merchant` check instead of `isinstance(entity, Npc)`
- Update all role string comparisons in `models.py` tables, `content_loader.py`, `layer.py`, `game_service.py` to use `NpcRole`
- Update YAML content files if they use role strings (loader must parse enum)

## Tests First

- A Character (non-NPC) has `is_merchant == False`
- An Npc with `role=NpcRole.MERCHANT` has `is_merchant == True`
- An Npc with `role=NpcRole.BLACKSMITH` has `is_merchant == False`
- `validate_buy` accepts `Character` typed seller — rejects non-merchant Character, accepts merchant Npc (no layers/ import needed)
- `rg 'from dnd_simulator.layers' src/dnd_simulator/rules/` returns zero hits after fix
- Existing trade tests still pass with enum-typed roles

## Implementation

1. Add `NpcRole` enum to `core/character.py`, add `is_merchant` property to `Character` (returns False)
2. Change `Npc.role` to `NpcRole`, update `is_merchant` override
3. Refactor `rules/trade.py`: change `Npc` param types to `Character`, remove layers/ import
4. Refactor `rules/action_handlers.py:_resolve_merchant`: check `isinstance(entity, Character) and entity.is_merchant` instead of `isinstance(entity, Npc)`
5. Update content_loader to parse role strings → NpcRole enum
6. Update models.py tables to use NpcRole keys instead of role strings
7. Update all other role string comparisons

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `rg 'from dnd_simulator.layers' src/dnd_simulator/rules/` = 0 hits
- [ ] No hardcoded `"merchant"` string comparisons remain in src/

## Status

`done`

## Developer Notes

Implemented as planned. Key changes:
- `NpcRole` enum added to `core/character.py` with COMMONER, BLACKSMITH, TAVERN_KEEPER, GUARD, MERCHANT, FARMER
- `is_merchant` property added to `Character` base (returns False), overridden in `Npc` using enum
- `rules/trade.py` now uses `Character` instead of `Npc` — zero layers/ imports in rules/
- `rules/action_handlers.py:_resolve_merchant` uses `Character` + `is_merchant` check
- `rules/action_provider.py` also cleaned — `NearbyMerchantsFn` now uses `Character` type
- All dict keys in models.py (schedules, flavor, dialogue) now use `NpcRole` enum
- `content_loader.py` parses role strings from YAML via `NpcRole(role_str)`
- All serialization points use `.value` for wire format
- 18 tests updated to use enum, 7 new tests added (Character base is_merchant, enum values, no-layers-import check)
