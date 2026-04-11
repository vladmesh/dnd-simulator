# Task: Spell Slot Pool Infrastructure

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 1 — Spell Slots as ResourcePool

## Description

Add generic spell slot infrastructure so any caster class can declare its slot table and get working ResourcePools. Phase 2 will add Paladin to `build_class_resource_pools()` — this task builds the machinery.

Currently `build_class_resource_pools()` in `content_loader/creatures.py` only handles Fighter's second_wind with a hardcoded `if char_class == CharClass.FIGHTER` block. Need:

1. Generic `build_spell_slot_pools()` that takes a slot table `{level: count}` and returns `list[ResourcePool]`.
2. Query helper `get_available_spell_slots()` — returns which slot levels have remaining uses. Smite (Phase 3) needs this to offer slot level choice.
3. Naming convention: `spell_slot_1`, `spell_slot_2`, etc. Helper `spell_slot_pool_id(level)` for consistency.

Key files:
- `rules/resources.py` — add spell slot helpers (pure functions)
- `core/resource.py` — possibly add slot-related constants

## Tests First

Scenarios for `tests/unit/test_spell_slots.py`:

1. **Build spell slot pools from table.** Input: `{1: 2, 2: 1}` → two ResourcePools: `spell_slot_1` (max=2, current=2, LONG_REST), `spell_slot_2` (max=1, current=1, LONG_REST).
2. **Empty slot table produces no pools.** Input: `{}` → empty list.
3. **Get available spell slots — full pools.** Creature with spell_slot_1 (2/2) and spell_slot_2 (1/1) → `{1: 2, 2: 1}`.
4. **Get available spell slots — partially depleted.** Creature with spell_slot_1 (1/2, one used) → `{1: 1}`. Level 2 fully depleted (0/1) → not in result.
5. **Get available spell slots — no pools.** Creature without spell slots → empty dict.
6. **Spell slots restored by long rest.** Creature with depleted spell_slot_1 and spell_slot_2. Call `reset_resources(creature, LONG_REST)` → all spell slots restored. (Validates naming convention works with existing reset logic.)
7. **Spell slots NOT restored by short rest.** Depleted spell_slot_1. Short rest → still depleted.

## Implementation

1. Add to `rules/resources.py`:
   - `spell_slot_pool_id(level: int) -> str` — returns `f"spell_slot_{level}"`
   - `build_spell_slot_pools(slot_table: dict[int, int]) -> list[ResourcePool]` — iterates table, creates pools with LONG_REST reset
   - `get_available_spell_slots(creature: Creature) -> dict[int, int]` — scans resource_pools for `spell_slot_*` pattern, returns {level: current_uses} excluding exhausted
2. Extend `build_class_resource_pools()` in `content_loader/creatures.py` — add a `SPELL_SLOT_TABLES: dict[CharClass, dict[int, int]]` mapping. Empty for now (Paladin added in Phase 2). Call `build_spell_slot_pools()` and append results.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Spell slot pools use LONG_REST reset (not SHORT_REST)
- [ ] Naming convention `spell_slot_N` is consistent throughout
- [ ] `get_available_spell_slots()` returns only non-exhausted levels
- [ ] Infrastructure ready for Phase 2 to just add Paladin's slot table

## Status

`done`

## Developer Notes

Straightforward implementation. Added three pure functions to `rules/resources.py`:
- `spell_slot_pool_id(level)` — canonical naming
- `build_spell_slot_pools(slot_table)` — creates ResourcePool list from `{level: count}` dict
- `get_available_spell_slots(creature)` — scans pools by prefix, returns non-exhausted slots

Wired into `build_class_resource_pools()` in `content_loader/creatures.py` via `_SPELL_SLOT_TABLES` dict — currently empty, Phase 2 adds Paladin entry. No existing tests modified.
