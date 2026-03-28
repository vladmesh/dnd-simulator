# Task: SRD Weapon & Armor Catalogs

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 1 — Weapon Properties & Fighting Styles

## Description

Create YAML catalog entries for the SRD basic weapon and armor sets. All weapons have correct D&D 5e properties (damage, category, finesse, two-handed, light, heavy). All armor has correct AC, DEX caps, and categories. Update existing dagger.yaml with new property fields.

## Tests First

**Catalog integrity tests:**
- All weapon catalog files load without validation errors
- All armor catalog files load without validation errors
- Greatsword is martial, two-handed, heavy, 2d6 slashing
- Rapier is martial, finesse, not two-handed, 1d8 piercing
- Shortsword is martial, finesse, light, 1d6 piercing
- Dagger is simple, finesse, light, 1d4 piercing
- Longbow has ability=dex, 1d8 piercing, not finesse
- Plate armor is heavy, base_ac=18, max_dex_bonus=0
- Leather armor is light, base_ac=11, max_dex_bonus=99
- Chain mail is heavy, base_ac=16, max_dex_bonus=0
- Shield has ac_bonus=2

**Cross-check:**
- No weapon has both `is_finesse` and `is_two_handed` (D&D rules: no such weapon in SRD)
- All martial two-handed weapons are also `is_heavy` (greatsword, greataxe, longbow)
- All weapons with `is_light` are one-handed

## Implementation

Create YAML files in `content/catalogs/items/`:

**Weapons (12):**
- `longsword.yaml` — martial, 1d8 slashing, versatile (note only, no mechanic yet)
- `greatsword.yaml` — martial, 2d6 slashing, two-handed, heavy
- `greataxe.yaml` — martial, 1d12 slashing, two-handed, heavy
- `shortsword.yaml` — martial, 1d6 piercing, finesse, light
- `rapier.yaml` — martial, 1d8 piercing, finesse
- `mace.yaml` — simple, 1d6 bludgeoning
- `warhammer.yaml` — martial, 1d8 bludgeoning, versatile (note only)
- `quarterstaff.yaml` — simple, 1d6 bludgeoning, versatile (note only)
- `longbow.yaml` — martial, 1d8 piercing, ability=dex, two-handed, heavy
- `shortbow.yaml` — simple, 1d6 piercing, ability=dex, two-handed
- `hand_crossbow.yaml` — martial, 1d6 piercing, ability=dex, light
- Update `dagger.yaml` — add `is_light: true`

**Armor (12):**
- `padded.yaml` — light, AC 11, max_dex 99
- `leather.yaml` — light, AC 11, max_dex 99
- `studded_leather.yaml` — light, AC 12, max_dex 99
- `hide.yaml` — medium, AC 12, max_dex 2
- `chain_shirt.yaml` — medium, AC 13, max_dex 2
- `scale_mail.yaml` — medium, AC 14, max_dex 2
- `breastplate.yaml` — medium, AC 14, max_dex 2
- `half_plate.yaml` — medium, AC 15, max_dex 2
- `ring_mail.yaml` — heavy, AC 14, max_dex 0
- `chain_mail.yaml` — heavy, AC 16, max_dex 0
- `splint.yaml` — heavy, AC 17, max_dex 0
- `plate.yaml` — heavy, AC 18, max_dex 0

**Shield:**
- `shield.yaml` — ac_bonus 2

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] All catalog files created with correct D&D 5e stats
- [ ] All catalog files load via content loader without errors
- [ ] Existing tests still pass (`make check`)
- [ ] Dagger updated with `is_light: true`

## Status

`done`

## Developer Notes

Straightforward data task. Created 12 weapon YAML files (longsword, greatsword, greataxe, shortsword, rapier, mace, warhammer, quarterstaff, longbow, shortbow, hand_crossbow) plus updated dagger with `is_light: true`. Created 12 armor files (padded through plate) and 1 shield. All files follow existing dagger.yaml format. Light armor omits max_dex_bonus (converter defaults to 99). 20 new tests covering individual stats, D&D rules constraints, and runtime conversion round-trips.
