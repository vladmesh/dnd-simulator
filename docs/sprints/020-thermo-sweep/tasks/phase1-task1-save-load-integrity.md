# Task: Save/load data integrity (BLOCKER)

**Date:** 2026-06-30
**Sprint:** 020-thermo-sweep
**Phase:** 1 — Корректность и инварианты

## Description

Two save→load data-loss bugs share the same `to_full_save_data` hole. Fix both and lock them with a round-trip regression test.

1. **[BLOCKER] Accessory modifiers dropped on save→load.** `_serialize_item` (`core/player.py:13-53`) writes accessory mods under key `grant_modifiers` (`:47`), but `ItemContent` (`content_loader/schemas.py:113-155`) names the field `modifiers` (`:152`) and has no `model_config`, so Pydantic's default `extra="ignore"` discards the key on `model_validate` (`content_loader/items.py:237`). An equipped ring with +1 STR loads fine from authored YAML (YAML uses `modifiers`), but loses its modifier after one autosave cycle (save writes `grant_modifiers` → reload validates against `ItemContent` → dropped).

2. **XP / level-up flag not persisted.** `to_full_save_data` (`core/player.py:74-113`) does not write `experience` or `level_up_available`, though `load_save_data` (`:122-123`) reads them. `PlayerContent` (`schemas.py:431-457`) lacks both fields and `_to_player` (`content_loader/creatures.py:216-265`) never sets them, so the modern load path resets XP to the content value (0). Backlog: `player-xp-not-persisted` (serialization half only; the WS `session-disconnect-debounce` race is out of scope).

## Tests First (RED)

Product-level round-trips, using the magic accessories added in `d0e8eda` (`ring_of_protection`, `circlet_of_aim`, `boots_of_speed`):

1. **Accessory modifier survives autosave cycle.** Build a player, equip `ring_of_protection` (carries a `grant_modifiers` entry, e.g. +1 AC/STAT). Capture an observable derived effect (e.g. `effective_ac` or the relevant `effective_*`). Serialize via `to_full_save_data()`, re-parse through the player load path (`PlayerContent`/`_to_player` / `parse_player`), and assert the equipped accessory still carries its modifier AND the derived effect matches the pre-save value. This must fail on current code (modifier becomes empty).
2. **XP + level-up flag survive round-trip.** Set `experience` to a non-zero value past a level threshold and `level_up_available=True`, run `to_full_save_data()` → load, assert both are preserved (not reset to 0/False).
3. **`extra="forbid"` catches drift.** An item dict carrying an unknown key fails `ItemContent.model_validate` loudly (guards future silent drift). Confirm all authored catalog/world item entries still validate (no real entry carries an unknown key — verified during planning).

Place alongside existing round-trip tests: `tests/integration/test_save_roundtrip.py` and/or `tests/unit/test_starting_equipment.py` (equipment persistence patterns live there).

## Implementation (GREEN)

- **Modifiers symmetric names.** In `ItemContent`, make the accessory-modifier field accept both the authored YAML name (`modifiers`) and the runtime serialize name (`grant_modifiers`): keep `modifiers` as the field, add `alias="grant_modifiers"` + `model_config = ConfigDict(populate_by_name=True, extra="forbid")`. This accepts authored YAML (`modifiers`) and save data (`grant_modifiers`) without breaking either, and old saves survive. (Alternative: rename `_serialize_item` to emit `modifiers` — simpler but breaks pre-existing saves under `extra="forbid"`. Prefer the alias.) Type the modifier entries (a `ModifierContent` submodel) only if cheap; not required for this task.
- **`extra="forbid"`** on `ItemContent` so future key drift fails at validation instead of silently dropping.
- **XP fields.** Add `experience` and `level_up_available` to: `to_full_save_data()` output, `PlayerContent` (with sensible defaults), and `_to_player` (set them on the constructed `PlayerCharacter`).
- Files: `core/player.py`, `content_loader/schemas.py`, `content_loader/creatures.py`, `content_loader/items.py`.

Gotchas:
- `_to_accessory_def` (`items.py:87-104`) already reads `model.modifiers` — the alias means it keeps working unchanged.
- Confirm the player load path used by save-restore actually routes through `ItemContent`/`PlayerContent` (it does: `_to_player` → `parse_items([item.model_dump(...)])`).
- Don't touch the `core/player.py → content_loader` import cycle here — that's Phase 3 scope.

## Acceptance Criteria

- [ ] Tests written and RED before implementation
- [ ] Accessory modifier survives a full `to_full_save_data` → load cycle, with the derived effect preserved
- [ ] `experience` and `level_up_available` survive the round-trip
- [ ] `ItemContent` uses `extra="forbid"`; all authored item YAML still validates
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Two separate data-loss bugs fixed:

1. **Accessory modifiers**: `_serialize_item` emits `grant_modifiers` but `ItemContent.modifiers` had no alias, so Pydantic silently dropped the key on load. Fix: added `Field(None, alias="grant_modifiers")` + `ConfigDict(populate_by_name=True, extra="forbid")` to `ItemContent`. Also added `id: str | None = None` to `ItemContent` since save data includes runtime-generated item IDs — `extra="forbid"` would have rejected them otherwise.

2. **XP / level-up flag**: `to_full_save_data()` never wrote `experience`/`level_up_available`; `PlayerContent` had no such fields; `_to_player` never set them. Fixed all three sites.

All 2272 unit tests pass, mypy and ruff clean.
