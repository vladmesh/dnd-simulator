# Task: Content — Fighter & Rogue NPCs + Equip Existing NPCs

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 4 — Content & Tests

## Description

Add class-featured NPCs to sword_vale content and upgrade existing NPCs to use catalog equipment instead of hardcoded stats.

Concrete changes:
- Add a Fighter guard NPC (e.g. "Ser Aldric") with `class: fighter`, `class_features: {fighting_style: defense}`, catalog items (longsword, chain_mail, shield), proper ability scores
- Add a Rogue scout NPC (e.g. "Lira") with `class: rogue`, catalog items (rapier, studded_leather), DEX-focused ability scores
- Update Rodrik: add `class: fighter`, `class_features: {fighting_style: dueling}`, replace inline attacks with catalog `longsword` item ref, add catalog `chain_mail` + `shield`
- Update Edgar: give him catalog `warhammer` instead of inline hammer attack
- Verify all NPCs load without errors

## Tests First

- Load sword_vale world content. Fighter NPC has `FighterFeatures` with correct fighting style, `equipped_weapon` is a longsword with `WeaponDef`, `equipped_armor` is chain_mail with `ArmorDef`, `equipped_shield` is shield with `ShieldDef`.
- Rogue NPC has `RogueFeatures` with `sneak_attack_dice=1`, equipped rapier (finesse), equipped studded_leather (light armor).
- Fighter NPC has `resource_pools` with `second_wind` pool (auto-created by `build_class_resource_pools`).
- Rodrik loads with `FighterFeatures(fighting_style=DUELING)`, catalog longsword equipped, chain_mail equipped.
- Edgar loads with catalog warhammer equipped.
- All NPCs pass `make check` — no schema validation errors, no missing refs.

## Implementation

- Edit `content/library/entities/sword_vale/npcs.yaml` — add Fighter and Rogue NPCs, update Rodrik and Edgar
- Use `ref: longsword`, `ref: chain_mail`, `ref: shield` etc. for catalog items
- Set `class: fighter` / `class: rogue` and `class_features:` blocks
- Set realistic ability scores (Fighter STR-focused, Rogue DEX-focused)
- Verify with `uv run pytest tests/unit/test_content_loading.py` or equivalent

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Fighter NPC: class_features + catalog weapon/armor/shield + resource_pools
- [ ] Rogue NPC: class_features + catalog finesse weapon + light armor
- [ ] Rodrik + Edgar upgraded to catalog refs
- [ ] No inline attack definitions on NPCs that have catalog weapons

## Status

`done`

## Developer Notes

All changes were straightforward content + test updates:
- Added Ser Aldric (fighter/defense at gate) and Lira (rogue/scout at docks) as new NPCs
- Upgraded Rodrik: added `class: fighter`, `class_features: {fighting_style: dueling}`, replaced inline attacks with catalog longsword + chain_mail + shield
- Upgraded Edgar: replaced inline hammer attack with catalog warhammer, added realistic ability scores
- Updated 3 existing tests that hardcoded NPC count (4 → 6) — intentional change from adding 2 new NPCs
- Updated `test_start_game_npcs_present` to check `equipped_weapon` instead of `attacks` for Edgar
