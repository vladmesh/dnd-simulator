"""Pure functions for weapon mechanics."""

from __future__ import annotations

from dnd_simulator.core.character import Ability, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.items import ItemType

_UNARMED_STRIKE = Attack(
    name="fists",
    ability=Ability.STR,
    damage=(DamageComponent("1", DamageType.BLUDGEONING),),
    reach=5,
)


def get_weapon_attack(creature: Creature) -> Attack:
    """Build Attack from equipped weapon, or fall back to creature.attacks[0].

    If creature has an equipped weapon with a WeaponDef, constructs an Attack
    from it. Finesse weapons use max(STR, DEX). The weapon's magic modifier
    is NOT added here — it's applied in resolve_attack via the modifier param.
    """
    weapon = creature.equipped_weapon
    if weapon is not None and weapon.item_type == ItemType.WEAPON and weapon.weapon_def is not None:
        wd = weapon.weapon_def
        ability = wd.ability or Ability.STR
        if wd.is_finesse:
            str_mod = creature.ability_scores.modifier(Ability.STR)
            dex_mod = creature.ability_scores.modifier(Ability.DEX)
            ability = Ability.DEX if dex_mod > str_mod else Ability.STR
        return Attack(
            name=wd.attack_name,
            ability=ability,
            damage=wd.damage,
            reach=wd.reach,
        )
    if creature.attacks:
        return creature.attacks[0]
    return _UNARMED_STRIKE


def get_weapon_modifier(creature: Creature) -> int:
    """Return the magic modifier (+1, +2, etc.) from equipped weapon, or 0."""
    weapon = creature.equipped_weapon
    if weapon is not None and weapon.weapon_def is not None:
        return weapon.weapon_def.modifier
    return 0
