# Task: Combat log i18n

**Date:** 2026-03-28
**Sprint:** 010-e2e-polish
**Phase:** 1 — E2E UX Fixes

## Description

Combat log messages mix languages: template strings (verbs, outcomes) go through `gettext`, but damage types (`"bludgeoning"`, `"piercing"`), damage source labels (`"sneak_attack"`, `"dueling"`), weapon names (`"Dagger"`, `"Longsword"`), item names (`"Health Potion"`), and the `"AC"` label stay in English.

Fix `perception.py` so that all fragments of attack/use_item/equip log lines go through `_()`. Damage types and source labels are finite enums — add them to the `.pot` catalog. Weapon and item names come from YAML content — wrap them at the perception layer (content stays English, display is translated).

Key files:
- `src/dnd_simulator/layers/entities/perception.py` — `_perceive_attack`, `_format_damage`, `_perceive_use_item`, `_perceive_equip`
- `src/dnd_simulator/core/character.py` — `DamageType` enum (values are English strings)
- `src/dnd_simulator/layers/entities/combat_manager.py` — `_build_damage_components` (produces `source`/`type` keys)

## Tests First

In `tests/unit/test_perception.py` (or extend existing):

1. **Attack with damage detail fully translated.** Build an attack event with damage_detail containing `[{"dice": "1d8", "type": "slashing", "source": "weapon"}, {"amount": 3, "type": "slashing", "source": "ability"}]`. Perceive it and assert the description contains `_("slashing")` (the translated form), not raw `"slashing"`. Assert `"AC"` is also wrapped.
2. **Use item: item name translated.** Build an entity_use_item event with `item_name: "Health Potion"`. Assert output uses `_("Health Potion")`.
3. **Equip: weapon name translated.** Build entity_equip event with `weapon_name: "Dagger"`. Assert output uses `_("Dagger")`.
4. **Sneak attack source label translated.** Damage detail with `source: "sneak_attack"`. Assert the description shows the translated label, not raw `"sneak_attack"`.

## Implementation

1. In `perception.py`, create a small helper `_translate_damage_type(raw: str) -> str` that wraps the value in `_()`. Same for source labels and item/weapon names.
2. Apply the helper in `_format_damage()` where `dc["type"]` and `dc["source"]` are interpolated.
3. Wrap weapon name in `_perceive_attack` and item name in `_perceive_use_item` / `_perceive_equip` with `_()`.
4. Wrap `"AC"` in `_()` where it appears in roll descriptions.
5. Run `make messages` to extract new strings to `.pot`. Update the Russian `.po` file with translations.
6. Run `make compile-messages` to build `.mo`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] All attack log fragments (damage types, sources, weapon names, "AC") go through `_()`
- [ ] `make messages` extracts the new strings
- [ ] Russian `.po` updated with translations for damage types, common weapon/item names

## Status

`done`

## Developer Notes

All dynamic values in combat log messages now go through `_()`: damage types (DamageType enum values), damage source labels (weapon/ability/sneak_attack/dueling), weapon names, item names, and the "AC" label.

Since `pygettext3` can't parse `_(str(x))` calls, added `_TRANSLATABLE_STRINGS` catalog at top of perception.py listing all known values as string literals for extraction.

Russian translations added for all 13 damage types, 4 source labels, 13 common weapons, and the AC label. `.mo` compiled via pure Python (no `msgfmt` on this system).
