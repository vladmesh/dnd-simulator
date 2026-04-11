# Task: Fix class_features lost on save/load (AC Defense bug)

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 1 — Bug Sweep

## Description

`PlayerCharacter.to_full_save_data()` (`core/player.py:81`) does not serialize `class_features`. After save/load, `class_features` is an empty list. This means:
- Fighter's Defense fighting style +1 AC is lost → AC 18 instead of 19 in combat
- Rogue's sneak_attack_dice is lost
- Any fighting style (Dueling +2 damage, GWF reroll) is lost

Root cause: `to_full_save_data()` serializes name, race, class, ability scores, equipment, gold — but not the `class_features` dict. When `parse_player(edata)` runs during load, `parse_class_features()` gets empty data and produces no features.

Fix: add `class_features` serialization to `to_full_save_data()`. The format must match what `parse_class_features()` expects (e.g. `{"fighting_style": "defense"}` for Fighter, `{"sneak_attack_dice": 1}` for Rogue).

Also fix the quick-fix from E2E (`routes_player.py:77`): verify it's using `effective_ac(p)` (already done during E2E, confirm it's committed).

## Tests First

1. **Round-trip class features** — Create a Fighter with Defense style, serialize via `to_full_save_data()`, deserialize via `parse_player()`, assert `get_feature(FighterFeatures).fighting_style == FightingStyle.DEFENSE`.
2. **Round-trip Rogue features** — Same pattern: Rogue → save → load → assert `get_feature(RogueFeatures).sneak_attack_dice == 1`.
3. **Round-trip Paladin features** — Paladin with no fighting style → save → load → assert `get_feature(PaladinFeatures)` exists.
4. **AC after round-trip** — Create Fighter with Defense + Chain Mail + Shield, save/load, assert `effective_ac(player) == 19`.

## Implementation

1. In `core/player.py:to_full_save_data()`: serialize `class_features` by building a dict from the feature objects. Fighter: `{"fighting_style": style.value}`. Rogue: `{"sneak_attack_dice": N}`. Paladin: `{"fighting_style": style.value}` if set.
2. Confirm `parse_class_features()` already handles these formats (it does — see `content_loader/creatures.py:73`).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Fighter Defense AC survives save/load round-trip
- [ ] Rogue sneak attack dice survives round-trip
- [ ] Paladin features survive round-trip

## Status

`pending`
