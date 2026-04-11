# Task: Multi-Damage Weapon Catalog & Backend Tests

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 4 — Multi-Damage Weapons + UI Breakdown

## Description

Create magic weapon catalog entries with multiple damage components and prove the full backend chain works. The infrastructure already supports multi-damage weapons (`WeaponDef.damage` is `tuple[DamageComponent, ...]`, `resolve_attack` loops all components, `build_damage_components` serializes each with its type). No backend code changes needed — just content and tests.

Key files already working:
- `core/items.py`: `WeaponDef.damage: tuple[DamageComponent, ...]`
- `content_loader/items.py`: parses YAML damage list → tuple of DamageComponent
- `rules/weapons.py`: `get_weapon_attack()` passes `wd.damage` tuple through
- `rules/combat.py`: `resolve_attack()` loops `attack.damage`, rolls each independently, crits per-component
- `rules/handlers/attack_resolution.py`: `build_damage_components()` serializes each with `type: dr.type.value`
- `layers/entities/perception.py`: `_format_damage()` formats multi-component text

## Tests First

1. **Multi-damage weapon resolution**: Create a flaming longsword (1d8 slashing + 1d6 fire) with a seeded RNG. `resolve_attack()` returns `AttackResult` with exactly 2 `DamageResult` entries (slashing + fire), each with correct type, dice, and source="weapon". Total damage = sum of both.

2. **Multi-damage weapon critical hit**: Same weapon, force crit. Result has 4 damage entries: base slashing, crit slashing, base fire, crit fire. Each crit entry has source="weapon_crit" and correct type.

3. **Multi-damage + flat bonus**: Flaming longsword with `damage_bonus=4` (STR). Flat bonus in `build_damage_components` gets type from first component (slashing). Fire component has no flat bonus applied — total includes flat bonus once.

4. **Multi-damage + extra_damage (Smite)**: Flaming longsword + Divine Smite extra_damage. Result has 3+ entries: slashing (weapon), fire (weapon), radiant (divine_smite). All serialized correctly.

5. **Perception formatting**: `_format_damage()` with 2 damage components shows both types in text: "14 damage (1d8 slashing + 1d6 fire)".

6. **Catalog loading**: Load flaming_longsword from YAML catalog, verify `WeaponDef` has 2 `DamageComponent` entries with correct types.

## Implementation

1. Create `content/catalogs/items/flaming_longsword.yaml` — magic longsword: `[{dice: "1d8", type: slashing}, {dice: "1d6", type: fire}]`, `magic_bonus: 1`.

2. Create `content/catalogs/items/frost_dagger.yaml` — magic dagger: `[{dice: "1d4", type: piercing}, {dice: "1d4", type: cold}]`, `magic_bonus: 1`, finesse + light + thrown.

3. Write unit tests proving the chain with multi-damage weapons.

4. Equip a Paladin NPC or test entity with a flaming longsword in a test world to verify integration.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] 2+ magic weapons with multiple damage components in catalog
- [ ] resolve_attack correctly rolls each damage component independently
- [ ] Crit doubles each component separately
- [ ] Flat bonuses apply to primary damage type only
- [ ] Perception text shows all damage types

## Status

`done`

## Developer Notes

All 11 tests pass immediately — the multi-damage infrastructure was already fully functional across the entire chain (WeaponDef → resolve_attack → build_damage_components → perception). This task validated the existing code rather than implementing new behavior. Created 2 magic weapon catalog entries (flaming longsword, frost dagger) as reusable content. The "bug" in build_damage_components line 89 (flat bonus type from first component) is confirmed correct per D&D 5e rules.
