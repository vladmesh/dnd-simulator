# Task: Split Combat Manager

**Date:** 2026-04-09
**Sprint:** 014-faction-reputation
**Phase:** 0 — Refactor — Prep for Faction Work

## Description

Split `layers/entities/combat_manager.py` (604 lines) into focused modules. Currently mixes initiative management, attack resolution, sneak attack checking, battle map setup, and combat state serialization. Sprint 014 adds CombatSides here — needs clear seams.

Extract into:
- `layers/entities/combat_manager.py` — combat lifecycle (start/end), turn order, combat state. Stays as the coordinator.
- `rules/handlers/attack_resolution.py` — `resolve_attack()` logic (roll, hit check, sneak attack, damage application, death). Currently 90 lines with mixed concerns.
- Move sneak attack eligibility (`_check_sneak_attack`) into `rules/combat.py` as a pure function — it's already a rules concern, not a manager concern.

Extract magic numbers: battle map dimensions (60x60), stalemate threshold (5.0), idle rounds limit (2), initial reaction budget (1).

## Tests First

- Sneak attack eligibility: rogue adjacent to enemy with an ally also adjacent → eligible. Same setup but no ally → not eligible. Rogue with ranged weapon, ally adjacent to target → eligible.
- Attack resolution: attacker with +5 vs AC 15 — roll 10 hits (10+5=15), roll 9 misses. Critical hit (natural 20) doubles damage dice. Attack that reduces HP to 0 triggers death handling.
- Combat stalemate: 2 consecutive rounds with no attacks → combat ends.
- Existing tests in `test_combat.py` and `test_combat_pipeline.py` still pass.

## Implementation

1. Extract `_check_sneak_attack` → `rules/combat.py::check_sneak_attack()` (pure function, takes creature + target + combat state).
2. Extract attack roll + damage into `rules/handlers/attack_resolution.py`.
3. `CombatManager.resolve_attack()` delegates to the extracted functions.
4. Magic numbers → named constants.
5. Verify `make check` green.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `combat_manager.py` under 350 lines
- [ ] Sneak attack logic is a pure function in `rules/`
- [ ] No magic numbers in business logic

## Status

`done`

## Developer Notes

Split `combat_manager.py` from 604 → 350 lines. Extracted:

- `check_sneak_attack()` + `find_adjacent_ally()` → `rules/sneak_attack.py` (pure functions)
- `build_attack_event()`, `build_damage_components()`, `roll_attack_dice()` → `rules/handlers/attack_resolution.py`
- `resolve_combat_move()` → `rules/handlers/attack_resolution.py`
- `serialize_combats()` / `deserialize_combats()` → `layers/entities/combat_serialization.py`
- Magic numbers → named constants (`DEFAULT_BATTLE_MAP_SIZE`, `IDLE_ROUNDS_TO_END_COMBAT`, `INITIAL_REACTION_BUDGET`)

Task specified `rules/combat.py` for sneak attack, but `rules/sneak_attack.py` was the correct home — all SA logic already lived there.

Updated existing tests in `test_breakdown_pipeline.py` and `test_sneak_attack_faction.py` to call the extracted functions directly instead of CombatManager private methods. No behavior changes.
