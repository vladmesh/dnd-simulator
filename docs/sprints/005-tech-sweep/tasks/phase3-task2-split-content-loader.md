# Task: Split content_loader.py into domain modules

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 3 — Growing Files Split

## Description

Split `content_loader.py` (757 LOC, 35 functions) into a `content_loader/` package with domain-specific modules:

- `content_loader/utils.py` — resolve_text, _read_yaml, _load_section (shared utilities)
- `content_loader/items.py` — all item/equipment parsing: _parse_weapon_def, _parse_armor_def, _parse_shield_def, _parse_accessory_def, parse_items, _parse_equipped, parse_equipped_weapon/armor/shield, extract_all_equipped, and related constants (_WEAPON_KEYS, _ARMOR_KEYS, _SHIELD_KEYS)
- `content_loader/creatures.py` — parse_attacks, parse_ability_scores, parse_class_features, build_class_resource_pools, parse_npc, parse_player, load_npcs
- `content_loader/world.py` — load_world, load_locations, _parse_locations, load_nations, load_settlements, load_battle_maps, load_world_meta, load_factions, extract_region_adjacency, extract_region_terrains
- `content_loader/monsters.py` — parse_monster_template, parse_encounters, load_monsters, parse_squad, load_squads
- `content_loader/__init__.py` — re-exports all public functions so `from dnd_simulator.content_loader import load_world` keeps working

Update imports in game_service.py, commands_creatures.py, entities layer, and all test files. Delete the old `content_loader.py`.

## Tests First

Pure structural refactor — no new behavioral tests. Verification:

- All existing tests in test_content_loader_dir.py, test_content_standardization.py, test_class_features.py, test_inventory_awareness.py, test_legacy_removal.py pass
- `make check` passes
- Each module is self-contained with its domain's parsing logic

## Implementation

1. Create `content_loader/` package with `__init__.py`
2. Move `utils.py` first (shared dependency)
3. Move domain modules, updating internal cross-references (e.g., creatures.py imports parse_items from items.py)
4. Add re-exports in `__init__.py`
5. Update all consumer imports
6. Delete old `content_loader.py`
7. Verify `make check`

## Acceptance Criteria

- [ ] `content_loader.py` (single file) deleted
- [ ] `content_loader/` package exists with 5 domain modules + `__init__.py`
- [ ] All consumer imports updated (game_service, commands_creatures, entities layer, tests)
- [ ] All existing tests pass (`make check`)
- [ ] No circular imports

## Status

`pending`
