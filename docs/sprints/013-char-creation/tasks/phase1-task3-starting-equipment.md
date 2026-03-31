# Task: Starting Equipment + Gold

**Date:** 2026-04-01
**Sprint:** 013-char-creation
**Phase:** 1 — HP Formula + Starting Equipment Rules

## Description

Add `starting_equipment(char_class)` and `STARTING_GOLD = 100` to `rules/character_creation.py`. Returns a list of item catalog ref strings per class. Fighter: chain_mail, longsword, shield. Rogue: leather, rapier, shortbow, dagger. These match existing catalog IDs in `content/catalogs/items/`.

## Tests First

In `tests/unit/test_character_creation.py`:

- Fighter starting equipment contains exactly: chain_mail, longsword, shield (order doesn't matter)
- Rogue starting equipment contains exactly: leather, rapier, shortbow, dagger
- Fighter equipment does NOT contain dagger or shortbow
- Rogue equipment does NOT contain chain_mail or shield
- Unknown class (WIZARD) → RuntimeError
- Starting gold is 100

## Implementation

In `rules/character_creation.py`:
- `STARTING_GOLD = 100`
- `STARTING_EQUIPMENT: dict[CharClass, list[str]]` — mapping class → item ref IDs
- `starting_equipment(char_class: CharClass) -> list[str]` — returns copy of the list, fails on unknown class

## Acceptance Criteria

- [ ] Tests written and RED
- [ ] Implementation makes tests GREEN
- [ ] `make check` passes
- [ ] Item refs match actual catalog files in `content/catalogs/items/`
- [ ] Unknown class raises RuntimeError

## Status

`done`

## Developer Notes

Simple mapping of CharClass to item catalog ref IDs. Private `_STARTING_EQUIPMENT` dict, public
`starting_equipment()` returns a copy to prevent mutation. All refs verified against
`content/catalogs/items/` directory. `STARTING_GOLD = 100` as module-level constant.
