"""Tests for D&D 5e proficiency system."""

from __future__ import annotations

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Character,
    CharClass,
    Creature,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.items import ArmorCategory, ArmorDef, Item, ItemType, ShieldDef, WeaponCategory, WeaponDef
from dnd_simulator.rules.modifiers import attack_modifiers, effective_ac
from dnd_simulator.rules.proficiency import (
    is_proficient_with_armor,
    is_proficient_with_shield,
    is_proficient_with_weapon,
    proficiency_bonus,
)

# ---------------------------------------------------------------------------
# proficiency_bonus
# ---------------------------------------------------------------------------


class TestProficiencyBonus:
    def test_levels_1_to_4(self) -> None:
        for level in range(1, 5):
            assert proficiency_bonus(level) == 2

    def test_levels_5_to_8(self) -> None:
        for level in range(5, 9):
            assert proficiency_bonus(level) == 3

    def test_levels_9_to_12(self) -> None:
        for level in range(9, 13):
            assert proficiency_bonus(level) == 4

    def test_levels_13_to_16(self) -> None:
        for level in range(13, 17):
            assert proficiency_bonus(level) == 5

    def test_levels_17_to_20(self) -> None:
        for level in range(17, 21):
            assert proficiency_bonus(level) == 6


# ---------------------------------------------------------------------------
# is_proficient_with_weapon
# ---------------------------------------------------------------------------

_LONGSWORD = WeaponDef(
    weapon_id="longsword",
    attack_name="slash",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)

_RAPIER = WeaponDef(
    weapon_id="rapier",
    attack_name="thrust",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d8", DamageType.PIERCING),),
    is_finesse=True,
)

_DAGGER = WeaponDef(
    weapon_id="dagger",
    attack_name="stab",
    category=WeaponCategory.SIMPLE,
    damage=(DamageComponent("1d4", DamageType.PIERCING),),
    is_finesse=True,
)

_GREATAXE = WeaponDef(
    weapon_id="greataxe",
    attack_name="chop",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d12", DamageType.SLASHING),),
)


class TestWeaponProficiency:
    def test_fighter_all_weapons(self) -> None:
        for weapon in [_LONGSWORD, _RAPIER, _DAGGER, _GREATAXE]:
            assert is_proficient_with_weapon(CharClass.FIGHTER, weapon)

    def test_rogue_simple_weapons(self) -> None:
        assert is_proficient_with_weapon(CharClass.ROGUE, _DAGGER)

    def test_rogue_specific_martial(self) -> None:
        assert is_proficient_with_weapon(CharClass.ROGUE, _RAPIER)
        assert is_proficient_with_weapon(CharClass.ROGUE, _LONGSWORD)

    def test_rogue_not_proficient_greataxe(self) -> None:
        assert not is_proficient_with_weapon(CharClass.ROGUE, _GREATAXE)

    def test_commoner_simple_only(self) -> None:
        assert is_proficient_with_weapon(CharClass.COMMONER, _DAGGER)
        assert not is_proficient_with_weapon(CharClass.COMMONER, _LONGSWORD)


# ---------------------------------------------------------------------------
# Integration: proficiency bonus in attack_modifiers
# ---------------------------------------------------------------------------


def _character(
    char_class: CharClass = CharClass.FIGHTER,
    level: int = 1,
    strength: int = 10,
    dexterity: int = 10,
) -> Character:
    return Character(
        id="test_char",
        name="Test",
        location_id="arena",
        max_hp=20,
        current_hp=20,
        ac=10,
        ability_scores=AbilityScores(scores={**AbilityScores().scores, Ability.STR: strength, Ability.DEX: dexterity}),
        race=Race.HUMAN,
        char_class=char_class,
        level=level,
    )


def _plain_creature(strength: int = 10) -> Creature:
    return Creature(
        id="test_creature",
        name="Wolf",
        location_id="arena",
        max_hp=11,
        current_hp=11,
        ac=13,
        ability_scores=AbilityScores(scores={**AbilityScores().scores, Ability.STR: strength}),
    )


def _sword_item() -> Item:
    return Item(
        id="sword_0",
        name="Longsword",
        item_type=ItemType.WEAPON,
        weapon_def=_LONGSWORD,
    )


def _rapier_item() -> Item:
    return Item(
        id="rapier_0",
        name="Rapier",
        item_type=ItemType.WEAPON,
        weapon_def=_RAPIER,
    )


class TestProficiencyInAttackModifiers:
    def test_fighter_gets_proficiency_with_martial(self) -> None:
        fighter = _character(CharClass.FIGHTER, strength=14)  # STR mod +2
        fighter.equipped_weapon = _sword_item()
        target = _plain_creature()
        mods = attack_modifiers(fighter, target, melee=True)
        # +2 STR + 2 proficiency = +4
        assert mods.modifier == 4

    def test_rogue_gets_proficiency_with_rapier(self) -> None:
        rogue = _character(CharClass.ROGUE, strength=14)
        rogue.equipped_weapon = _rapier_item()
        target = _plain_creature()
        mods = attack_modifiers(rogue, target, melee=True)
        assert mods.modifier == 4

    def test_rogue_no_proficiency_with_greataxe(self) -> None:
        rogue = _character(CharClass.ROGUE, strength=14)
        rogue.equipped_weapon = Item(
            id="axe_0",
            name="Greataxe",
            item_type=ItemType.WEAPON,
            weapon_def=_GREATAXE,
        )
        target = _plain_creature()
        mods = attack_modifiers(rogue, target, melee=True)
        # +2 STR, no proficiency
        assert mods.modifier == 2

    def test_commoner_no_proficiency_with_martial(self) -> None:
        commoner = _character(CharClass.COMMONER, strength=14)
        commoner.equipped_weapon = _sword_item()
        target = _plain_creature()
        mods = attack_modifiers(commoner, target, melee=True)
        assert mods.modifier == 2

    def test_unarmed_strike_always_proficient(self) -> None:
        fighter = _character(CharClass.FIGHTER, strength=14)
        # No weapon, no natural attacks → unarmed strike
        target = _plain_creature()
        mods = attack_modifiers(fighter, target, melee=True)
        assert mods.modifier == 4

    def test_creature_with_natural_attacks_gets_proficiency(self) -> None:
        from dnd_simulator.core.character import Attack

        wolf = _plain_creature(strength=14)
        wolf.attacks = (
            Attack(name="bite", ability=Ability.STR, damage=(DamageComponent("1d6", DamageType.PIERCING),)),
        )
        target = _character()
        mods = attack_modifiers(wolf, target, melee=True)
        # +2 STR + 2 creature proficiency = +4
        assert mods.modifier == 4

    def test_higher_level_higher_proficiency(self) -> None:
        fighter = _character(CharClass.FIGHTER, level=5, strength=14)
        fighter.equipped_weapon = _sword_item()
        target = _plain_creature()
        mods = attack_modifiers(fighter, target, melee=True)
        # +2 STR + 3 proficiency (level 5) = +5
        assert mods.modifier == 5


# ---------------------------------------------------------------------------
# Armor proficiency
# ---------------------------------------------------------------------------

_CHAIN_MAIL = ArmorDef(armor_id="chain_mail", category=ArmorCategory.HEAVY, base_ac=16, max_dex_bonus=0)
_STUDDED_LEATHER = ArmorDef(armor_id="studded_leather", category=ArmorCategory.LIGHT, base_ac=12, max_dex_bonus=99)
_BREASTPLATE = ArmorDef(armor_id="breastplate", category=ArmorCategory.MEDIUM, base_ac=14, max_dex_bonus=2)


class TestArmorProficiency:
    def test_fighter_all_armor(self) -> None:
        for armor in [_CHAIN_MAIL, _STUDDED_LEATHER, _BREASTPLATE]:
            assert is_proficient_with_armor(CharClass.FIGHTER, armor)

    def test_rogue_light_only(self) -> None:
        assert is_proficient_with_armor(CharClass.ROGUE, _STUDDED_LEATHER)
        assert not is_proficient_with_armor(CharClass.ROGUE, _CHAIN_MAIL)
        assert not is_proficient_with_armor(CharClass.ROGUE, _BREASTPLATE)

    def test_wizard_no_armor(self) -> None:
        assert not is_proficient_with_armor(CharClass.WIZARD, _STUDDED_LEATHER)

    def test_fighter_shield_proficient(self) -> None:
        assert is_proficient_with_shield(CharClass.FIGHTER)

    def test_rogue_no_shield(self) -> None:
        assert not is_proficient_with_shield(CharClass.ROGUE)


# ---------------------------------------------------------------------------
# Effective AC calculation
# ---------------------------------------------------------------------------


def _armor_item(armor_def: ArmorDef, name: str = "Armor") -> Item:
    return Item(id="armor_0", name=name, item_type=ItemType.ARMOR, armor_def=armor_def)


def _shield_item() -> Item:
    return Item(
        id="shield_0",
        name="Shield",
        item_type=ItemType.SHIELD,
        shield_def=ShieldDef(shield_id="shield", ac_bonus=2),
    )


class TestEffectiveAc:
    def test_unarmored_character_uses_10_plus_dex(self) -> None:
        char = _character(dexterity=14)  # DEX mod +2
        assert effective_ac(char) == 12  # 10 + 2

    def test_unarmored_character_backwards_compat(self) -> None:
        # Character with high AC but no armor → keeps existing AC
        char = _character(dexterity=10)
        char.ac = 18  # type: ignore[misc]  # stat-block override
        assert effective_ac(char) == 18

    def test_light_armor_full_dex(self) -> None:
        char = _character(dexterity=16)  # DEX mod +3
        char.equipped_armor = _armor_item(_STUDDED_LEATHER)
        # studded leather base 12 + DEX 3 = 15
        assert effective_ac(char) == 15

    def test_medium_armor_capped_dex(self) -> None:
        char = _character(dexterity=16)  # DEX mod +3, capped at +2
        char.equipped_armor = _armor_item(_BREASTPLATE)
        # breastplate base 14 + DEX 2 (capped) = 16
        assert effective_ac(char) == 16

    def test_heavy_armor_no_dex(self) -> None:
        char = _character(dexterity=16)  # DEX mod +3, but heavy = 0
        char.equipped_armor = _armor_item(_CHAIN_MAIL)
        # chain mail base 16 + DEX 0 = 16
        assert effective_ac(char) == 16

    def test_heavy_armor_negative_dex_ignored(self) -> None:
        char = _character(dexterity=8)  # DEX mod -1, heavy armor ignores DEX entirely
        char.equipped_armor = _armor_item(_CHAIN_MAIL)
        # chain mail base 16, negative DEX does NOT reduce AC in heavy armor
        assert effective_ac(char) == 16

    def test_shield_adds_to_ac(self) -> None:
        char = _character(dexterity=14)
        char.equipped_armor = _armor_item(_CHAIN_MAIL)
        char.equipped_shield = _shield_item()
        # chain mail 16 + shield 2 = 18
        assert effective_ac(char) == 18

    def test_monster_stat_block_ac(self) -> None:
        wolf = _plain_creature()  # ac=13, this is stat-block
        assert effective_ac(wolf) == 13

    def test_non_proficient_armor_gives_attack_disadvantage(self) -> None:
        rogue = _character(CharClass.ROGUE, dexterity=14)
        rogue.equipped_armor = _armor_item(_CHAIN_MAIL)  # Rogue not proficient with heavy
        rogue.equipped_weapon = _rapier_item()
        target = _plain_creature()
        mods = attack_modifiers(rogue, target, melee=True)
        assert mods.disadvantage is True

    def test_proficient_armor_no_disadvantage(self) -> None:
        fighter = _character(CharClass.FIGHTER, dexterity=14)
        fighter.equipped_armor = _armor_item(_CHAIN_MAIL)
        fighter.equipped_weapon = _sword_item()
        target = _plain_creature()
        mods = attack_modifiers(fighter, target, melee=True)
        assert mods.disadvantage is False
