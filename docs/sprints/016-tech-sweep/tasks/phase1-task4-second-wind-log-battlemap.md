# Task: Second Wind perception formatter + battle map content configs

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 1 — Bug Sweep

## Description

Two small fixes:

### A) Second Wind log shows "Что-то произошло (entity_second_wind)"

Missing perception formatter in `layers/entities/perception.py`. The `_DISPATCH` dict (line ~435) has no entry for `EventType.ENTITY_SECOND_WIND`. The event is emitted from `rules/handlers/items.py:206` with data `{entity_id, healed, dice_detail}`. Frontend already has icon/color configured (`logProcessing.ts:67,99`).

Fix: add `_perceive_second_wind()` function + dispatch entry. Follow the pattern of `_perceive_bless()`.

### B) Battle map dimensions from regions.yaml not connected

The infrastructure is fully implemented (`load_battle_maps()` in `content_loader/world.py:153`, `CombatManager` uses it at line 79). But production content (`content/library/geography/sword_vale/regions.yaml`) has no `battle_map` sections. All combats fall back to 60x60 default.

Fix: add `battle_map` configs to `sword_vale/regions.yaml` with sensible per-region dimensions. Test worlds already have examples (e.g. `arena: battle_map: {width: 80, height: 80}`).

## Tests First

1. **Second Wind perception** — Create an `ENTITY_SECOND_WIND` event with entity_id + healed=5. Call `perceive_event()` with observer = self → expect "You catch your breath, regaining 5 HP". Call with observer = other → expect "{name} catches their breath...".
2. **Battle map from YAML** — Call `load_battle_maps()` on sword_vale regions.yaml after adding configs. Assert returned dict has entries with correct width/height for at least 2 regions.

## Implementation

### A) Perception formatter
1. Add `_perceive_second_wind(event, observer, get_entity)` in `perception.py` after `_perceive_bless`.
2. Add `EventType.ENTITY_SECOND_WIND: _perceive_second_wind` to `_DISPATCH`.
3. Add i18n strings for both perspectives.

### B) Battle map content
1. Add `battle_map` sections to regions in `content/library/geography/sword_vale/regions.yaml`:
   - Forest/wilderness regions: 60x60 (default, can omit)
   - Town squares/docks: 40x40 (tighter)
   - Open areas: 80x80

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Second Wind log shows descriptive message, not "Что-то произошло"
- [ ] `load_battle_maps()` returns region-specific dimensions for sword_vale

## Status

`done`

## Developer Notes

**A) Second Wind perception formatter:** Added `_perceive_second_wind()` to `perception.py` following the `_perceive_bless` pattern — first/third person messages with healed HP amount. Added dispatch entry for `EventType.ENTITY_SECOND_WIND`. Added Russian translations to `.po` file.

**B) Battle map configs:** Added `battle_map` sections to 6 of 7 sword_vale regions (greenwood omitted — forest at default 60x60). Silverport 40x40 (tight port town), Highfield/Dustmere 80x80 (open terrain), Iron Peaks/Bogmire 50x50 (constrained terrain), Frostholm 70x70 (tundra).
