# Task: Level 1 Paladin Spell Slot (Temporary)

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 7 — Smite UI + Level 1 Spell Slot

## Description

Give Paladin level 1 a single spell slot (level 1) as a temporary measure until the leveling system exists. By RAW, Paladins get spell slots at level 2, but without leveling there's no way to test smite end-to-end. This is a 1-line table change + test update.

## Tests First

- Paladin level 1 gets exactly 1 spell slot (level 1) from `build_class_resource_pools`.
- Paladin level 2 still gets 2 spell slots (level 1) — no regression.
- Level 1 Paladin with this slot can pass `validate_smite()` (slot exists and has uses).

## Implementation

- `src/dnd_simulator/content_loader/creatures.py`: Add `1: {1: 1}` to `_SPELL_SLOT_TABLES[CharClass.PALADIN]` with a `# TEMPORARY` comment.
- `tests/unit/test_paladin_infra.py`: Update `test_level1_no_spell_slots` → expect 1 spell slot.
- `tests/unit/test_divine_smite.py`: Update `test_level_1_paladin_no_spell_slots_returns_error` if it asserts no slots at level 1.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Level 1 Paladin created via content loader has a spell slot

## Status

`done`

## Developer Notes

Trivial change: added `1: {1: 1}` to Paladin spell slot table. Updated test_paladin_infra to expect 1 slot at level 1 instead of 0. Updated test_divine_smite helper to give level 1 paladins a slot (matching new production behavior) and changed `test_level_1_paladin_no_spell_slots_returns_error` → `test_level_1_paladin_can_smite`.
