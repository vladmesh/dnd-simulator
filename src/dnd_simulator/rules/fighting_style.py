"""Fighting style mechanics — shared logic for Fighter/Paladin/Ranger.

Pure functions that map a ``FightingStyle`` + creature context to
``Modifier`` lists / ``AttackContribution``. Any class feature that carries a
``fighting_style`` field delegates here so the rules for Defense/Dueling/GWF
live in exactly one place.
"""

from __future__ import annotations

from dnd_simulator.core.character import Character, Creature
from dnd_simulator.core.class_features import FightingStyle
from dnd_simulator.core.modifiers import (
    AttackContribution,
    Modifier,
    ModifierOp,
    RollComponent,
    StatType,
)


def self_modifiers_for_style(style: FightingStyle | None, creature: Creature) -> list[Modifier]:
    """Return passive self-modifiers granted by a fighting style."""
    if style is None:
        return []
    if style == FightingStyle.DEFENSE and isinstance(creature, Character) and creature.equipped_armor:
        return [Modifier(StatType.AC, ModifierOp.ADD, value=1, source="fighting_style_defense")]
    return []


def attack_contribution_for_style(
    style: FightingStyle | None,
    creature: Creature,
    *,
    melee: bool,
) -> AttackContribution:
    """Return damage/roll contributions a fighting style adds to an attack."""
    if style is None or not melee or not isinstance(creature, Character):
        return AttackContribution()

    weapon = creature.equipped_weapon
    weapon_def = weapon.weapon_def if weapon else None

    if style == FightingStyle.DUELING and weapon and (not weapon_def or not weapon_def.is_two_handed):
        return AttackContribution(
            damage_bonus=2,
            damage_components=(RollComponent(source="dueling", value=2),),
        )
    if style == FightingStyle.GREAT_WEAPON_FIGHTING and weapon_def and weapon_def.is_two_handed:
        return AttackContribution(gwf_reroll=True)
    return AttackContribution()
