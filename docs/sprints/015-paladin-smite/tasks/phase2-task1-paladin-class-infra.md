# Task: Paladin Class Infrastructure

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 2 — Paladin Class Foundation

## Description

Wire up Paladin as a playable class: `PaladinFeatures` dataclass, content loader support, resource pools (Lay on Hands HP pool + spell slots), starting equipment, HP hit die, and a Paladin NPC in Sword Vale YAML.

Key changes:
- `PaladinFeatures` frozen dataclass in `core/class_features.py` (fighting_style + cost_overrides)
- `ClassFeatures` union updated to include `PaladinFeatures`
- `parse_class_features()` in `content_loader/creatures.py` handles `CharClass.PALADIN`
- `build_class_resource_pools()` accepts `level` parameter; creates Lay on Hands pool (`max_uses = 5 × level`, long rest reset) and spell slots from table
- `_SPELL_SLOT_TABLES` populated for Paladin (level 1 = no slots; level 2 = 2 first-level slots per D&D 5e half-caster table)
- `use_resource()` in `rules/resources.py` extended with optional `amount` parameter (default 1) for variable-cost spending
- `HIT_DICE` in `rules/character_creation.py` gets Paladin entry (d10)
- `_STARTING_EQUIPMENT` gets Paladin entry (chain_mail, longsword, shield)
- New Paladin NPC YAML in `content/library/entities/sword_vale/npcs.yaml`

## Tests First

Scenarios to cover (all in `tests/unit/`):

1. **PaladinFeatures creation** — create PaladinFeatures with defense fighting style, verify frozen, verify it's valid ClassFeatures
2. **Resource pool creation** — `build_class_resource_pools(PALADIN, level=1)` returns pool with id="lay_on_hands", max_uses=5, reset_on=LONG_REST. Level 3 → max_uses=15. No spell slots at level 1.
3. **Spell slot pools** — `build_class_resource_pools(PALADIN, level=2)` returns Lay on Hands pool + 2 first-level spell slot pools
4. **Variable resource spending** — `use_resource(creature, "lay_on_hands", amount=10)` decrements by 10. Spending more than remaining raises ValueError.
5. **Content loader** — parse a Paladin NPC dict through `parse_npc()`, verify class_features contains PaladinFeatures, resource_pools contain lay_on_hands and spell slots
6. **Starting equipment** — `starting_equipment(PALADIN)` returns chain_mail, longsword, shield
7. **HP calculation** — `calculate_max_hp(PALADIN, level=1, con_modifier=2)` returns 12 (d10 + 2)
8. **Backward compatibility** — `build_class_resource_pools(FIGHTER)` still works (no level required, defaults to 1)

## Implementation

After tests are red:

1. Add `PaladinFeatures` to `core/class_features.py`, update union type
2. Extend `use_resource()` with `amount: int = 1` parameter in `rules/resources.py`
3. Update `build_class_resource_pools(char_class, level=1)` signature; add Paladin pools
4. Populate `_SPELL_SLOT_TABLES` for Paladin (D&D 5e half-caster: level 2 = {1: 2})
5. Add Paladin to `HIT_DICE` and `_STARTING_EQUIPMENT` in `rules/character_creation.py`
6. Update `parse_class_features()` for Paladin in `content_loader/creatures.py`
7. Pass level to `build_class_resource_pools()` in `_to_npc()` and `_to_player()`
8. Add Paladin NPC YAML (e.g. Brother Aldwyn, temple guard/healer in Silverport)

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] PaladinFeatures is a frozen dataclass in ClassFeatures union
- [ ] Lay on Hands pool = 5 × level, resets on long rest
- [ ] use_resource supports variable amounts
- [ ] Paladin NPC loads from YAML without errors
- [ ] Character creation works for Paladin (HP, equipment, pools)

## Status

`done`

## Developer Notes

- Added `level` field to `NpcContent` schema (was missing, only `PlayerContent` had it). NPCs now pass level to resource pool creation.
- `_to_npc()` now passes `level=model.level` to the Npc constructor (was defaulting to 1).
- Changed `_SPELL_SLOT_TABLES` structure from `dict[CharClass, dict[int, int]]` to `dict[CharClass, dict[int, dict[int, int]]]` — keyed by class → character level → {slot_level: count}. This supports the half-caster progression where different character levels unlock different slot configurations.
- `use_resource()` error message changed from "exhausted" to "insufficient uses" — more informative for variable-amount spending. Updated old test match pattern.
- Updated NPC count in `test_library_structure.py` (6 → 7) and `test_manifest_game_service.py` (6 → 7) for new Paladin NPC.
