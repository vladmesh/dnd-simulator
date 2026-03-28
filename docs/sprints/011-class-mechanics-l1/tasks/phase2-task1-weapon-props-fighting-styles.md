# Task: Weapon Properties & Fighting Style Mechanics

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 1 — Weapon Properties & Fighting Styles

## Description

Add D&D 5e weapon properties (`is_two_handed`, `is_light`, `is_heavy`) to `WeaponDef` and use them in fighting style mechanics. Fix Dueling to exclude two-handed weapons. Implement Great Weapon Fighting (reroll 1–2 on damage dice for two-handed weapons). Thread through schema, content loader, and combat resolution.

## Tests First

Product-level scenarios to write before implementation:

**Dueling fix (two-handed exclusion):**
- Fighter with Dueling style wielding a longsword (one-handed) gets +2 damage bonus
- Fighter with Dueling style wielding a greatsword (`is_two_handed=True`) does NOT get +2 damage bonus
- Fighter with Dueling style and no weapon gets no bonus (existing, verify still passes)

**Great Weapon Fighting:**
- Fighter with GWF wielding a greatsword (two-handed): damage dice showing 1 or 2 are rerolled (use seeded RNG to force specific rolls, verify reroll happens)
- Fighter with GWF wielding a longsword (one-handed): no reroll — GWF only applies to two-handed
- Fighter with GWF: rerolled die keeps the second result even if it's still 1 or 2 (D&D RAW: reroll once, not recursively)
- GWF does not reroll flat damage bonuses or extra damage sources (Sneak Attack dice are not rerolled by GWF — GWF only applies to the weapon's damage dice)

**Weapon properties on WeaponDef:**
- `WeaponDef` with `is_two_handed=True` is recognized by fighting style checks
- Default values: `is_two_handed=False`, `is_light=False`, `is_heavy=False`

**Content loader round-trip:**
- YAML item with `is_two_handed: true` parses into `WeaponDef(is_two_handed=True)`
- YAML item without weapon properties defaults to `False` for all

## Implementation

After tests are red — make them green:

1. **`core/items.py`** — Add `is_two_handed: bool = False`, `is_light: bool = False`, `is_heavy: bool = False` to `WeaponDef`
2. **`core/class_features.py`** — Add `GREAT_WEAPON_FIGHTING = "great_weapon_fighting"` to `FightingStyle` enum
3. **`content_loader/schemas.py`** — Add `is_two_handed`, `is_light`, `is_heavy` to both `WeaponDefContent` and `ItemContent`
4. **`content_loader/items.py`** — Pass new fields through `_to_weapon_def()` converter
5. **`rules/modifiers.py`** — Fix Dueling (line 285 TODO): add `and not weapon.weapon_def.is_two_handed`. Add GWF: set a flag on `AttackModifiers` (new `gwf_reroll: bool` field)
6. **`rules/combat.py`** — In `resolve_attack()`, accept `gwf_reroll: bool` param. When true, roll weapon damage dice individually and reroll any showing 1–2 (once). Use a dedicated roll path, don't change `damage_roll()` signature — GWF is weapon-dice-only, not extra damage.
7. **`rules/checks.py`** — Add `damage_roll_gwf(expr, *, critical, rng)` that parses dice, rolls individually, rerolls 1–2 once each, adds modifier. Or inline in `resolve_attack` damage loop.
8. **Wire up** — wherever `attack_modifiers()` result feeds into `resolve_attack()`, pass `gwf_reroll` through.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Dueling +2 does NOT apply to two-handed weapons
- [ ] GWF rerolls 1–2 on weapon damage dice only, once per die
- [ ] GWF does not affect extra damage (Sneak Attack, etc.)
- [ ] Content loader handles new weapon properties

## Status

`done`

## Developer Notes

Clean implementation following existing patterns. `roll()` already had `reroll_below` param from Phase 0 — GWF plugs directly into it. Key decisions:
- GWF reroll threaded via `gwf_reroll` flag on `AttackModifiers` → `resolve_attack` kwarg → `_roll_damage` → `roll(reroll_below=2)`. Only weapon damage components use it; extra damage (Sneak Attack, Smite) is unaffected.
- Dueling fix: added `not weapon_def.is_two_handed` check. Handles case where weapon has no weapon_def gracefully.
- No old tests modified — all 1515 existing tests still pass as-is.
