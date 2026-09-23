"""Direct tests for rules/fighting_style.py — Defense, Dueling and Great Weapon Fighting."""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import Character, Creature
from dnd_simulator.core.class_features import FightingStyle
from dnd_simulator.core.items import (
    ArmorCategory,
    ArmorDef,
    EquipmentSlot,
    Item,
    ItemType,
    WeaponCategory,
    WeaponDef,
)
from dnd_simulator.core.modifiers import AttackContribution, Modifier, ModifierOp, RollComponent, StatType
from dnd_simulator.rules.fighting_style import attack_contribution_for_style, self_modifiers_for_style


def _weapon(*, two_handed: bool = False) -> Item:
    weapon_def = WeaponDef(
        weapon_id="greatsword" if two_handed else "longsword",
        attack_name="slash",
        category=WeaponCategory.MARTIAL,
        damage=(),
        is_two_handed=two_handed,
    )
    return Item(id="w1", name="Sword", item_type=ItemType.WEAPON, weapon_def=weapon_def)


def _armor() -> Item:
    armor_def = ArmorDef(armor_id="chain_mail", category=ArmorCategory.HEAVY, base_ac=16, max_dex_bonus=0)
    return Item(id="a1", name="Chain Mail", item_type=ItemType.ARMOR, armor_def=armor_def)


def _fighter(**equipped: Item) -> Character:
    slots = {EquipmentSlot(slot): item for slot, item in equipped.items()}
    return Character(id="c1", name="Fighter", location_id="arena", equipped=slots)


class TestSelfModifiers:
    def test_no_style_grants_nothing(self) -> None:
        assert self_modifiers_for_style(None, _fighter(armor=_armor())) == []

    def test_defense_in_armor_grants_plus_one_ac(self) -> None:
        mods = self_modifiers_for_style(FightingStyle.DEFENSE, _fighter(armor=_armor()))
        assert mods == [Modifier(StatType.AC, ModifierOp.ADD, value=1, source="fighting_style_defense")]

    def test_defense_without_armor_grants_nothing(self) -> None:
        assert self_modifiers_for_style(FightingStyle.DEFENSE, _fighter()) == []

    def test_defense_on_non_character_grants_nothing(self) -> None:
        creature = Creature(id="m1", name="Ogre", location_id="arena")
        assert self_modifiers_for_style(FightingStyle.DEFENSE, creature) == []

    @pytest.mark.parametrize("style", [FightingStyle.DUELING, FightingStyle.GREAT_WEAPON_FIGHTING])
    def test_offensive_styles_grant_no_self_modifiers(self, style: FightingStyle) -> None:
        assert self_modifiers_for_style(style, _fighter(armor=_armor(), weapon=_weapon())) == []


class TestAttackContribution:
    def test_dueling_one_handed_melee_adds_two_damage(self) -> None:
        contribution = attack_contribution_for_style(FightingStyle.DUELING, _fighter(weapon=_weapon()), melee=True)
        assert contribution == AttackContribution(
            damage_bonus=2, damage_components=(RollComponent(source="dueling", value=2),)
        )

    def test_dueling_with_two_handed_weapon_adds_nothing(self) -> None:
        creature = _fighter(weapon=_weapon(two_handed=True))
        assert attack_contribution_for_style(FightingStyle.DUELING, creature, melee=True) == AttackContribution()

    def test_dueling_unarmed_adds_nothing(self) -> None:
        assert attack_contribution_for_style(FightingStyle.DUELING, _fighter(), melee=True) == AttackContribution()

    def test_dueling_weapon_without_def_counts_as_one_handed(self) -> None:
        plain = Item(id="w2", name="Club", item_type=ItemType.WEAPON)
        contribution = attack_contribution_for_style(FightingStyle.DUELING, _fighter(weapon=plain), melee=True)
        assert contribution.damage_bonus == 2

    def test_gwf_two_handed_enables_reroll(self) -> None:
        creature = _fighter(weapon=_weapon(two_handed=True))
        contribution = attack_contribution_for_style(FightingStyle.GREAT_WEAPON_FIGHTING, creature, melee=True)
        assert contribution == AttackContribution(gwf_reroll=True)

    def test_gwf_one_handed_adds_nothing(self) -> None:
        creature = _fighter(weapon=_weapon())
        contribution = attack_contribution_for_style(FightingStyle.GREAT_WEAPON_FIGHTING, creature, melee=True)
        assert contribution == AttackContribution()

    @pytest.mark.parametrize(
        "style", [FightingStyle.DUELING, FightingStyle.GREAT_WEAPON_FIGHTING, FightingStyle.DEFENSE]
    )
    def test_ranged_attacks_get_nothing(self, style: FightingStyle) -> None:
        creature = _fighter(weapon=_weapon(two_handed=style is FightingStyle.GREAT_WEAPON_FIGHTING))
        assert attack_contribution_for_style(style, creature, melee=False) == AttackContribution()

    def test_no_style_or_non_character_gets_nothing(self) -> None:
        assert attack_contribution_for_style(None, _fighter(weapon=_weapon()), melee=True) == AttackContribution()
        ogre = Creature(id="m1", name="Ogre", location_id="arena")
        assert attack_contribution_for_style(FightingStyle.DUELING, ogre, melee=True) == AttackContribution()
