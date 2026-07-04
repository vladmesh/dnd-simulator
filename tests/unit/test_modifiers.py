"""Tests for the modifier pipeline — derived stat computation."""

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
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle, PaladinFeatures, RogueFeatures
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.items import ArmorCategory, ArmorDef, EquipmentSlot, Item, ItemType, WeaponCategory, WeaponDef
from dnd_simulator.core.modifiers import Modifier, ModifierOp, StatType
from dnd_simulator.rules.modifiers import (
    _CONDITION_DEFENSE_MODIFIERS,
    _CONDITION_SELF_MODIFIERS,
    attack_modifiers,
    collect_defense_modifiers,
    collect_dice_bonuses,
    collect_self_modifiers,
    compute_stat,
    effective_ac,
    effective_speed,
    is_auto_crit_target,
    resolve_advantage,
)


def _creature(
    *,
    ac: int = 10,
    speed: int = 30,
    conditions: dict[Condition, int | None] | None = None,
    str_score: int = 10,
    dex_score: int = 10,
    equipped_weapon: Item | None = None,
) -> Creature:
    scores = AbilityScores()
    scores[Ability.STR] = str_score
    scores[Ability.DEX] = dex_score
    return Creature(
        id="test",
        name="Test",
        location_id="loc",
        ac=ac,
        speed=speed,
        conditions=conditions or {},
        ability_scores=scores,
        equipped={EquipmentSlot.WEAPON: equipped_weapon} if equipped_weapon else {},
    )


def _magic_sword(modifier: int = 1) -> Item:
    return Item(
        id="sword",
        name="Magic Sword",
        item_type=ItemType.WEAPON,
        weapon_def=WeaponDef(
            weapon_id="longsword",
            attack_name="magic sword",
            category=WeaponCategory.MARTIAL,
            damage=(DamageComponent("1d8", DamageType.SLASHING),),
            modifier=modifier,
        ),
    )


# ---------------------------------------------------------------------------
# Condition → Modifier mapping
# ---------------------------------------------------------------------------


class TestConditionMapping:
    """Every condition maps to the correct modifiers."""

    def test_blinded_self_disadvantage(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.BLINDED]
        assert any(m.op == ModifierOp.DISADVANTAGE and m.stat == StatType.ATTACK_ROLL for m in mods)

    def test_blinded_defense_advantage(self) -> None:
        mods = _CONDITION_DEFENSE_MODIFIERS[Condition.BLINDED]
        assert any(m.op == ModifierOp.ADVANTAGE and m.stat == StatType.ATTACK_ROLL for m in mods)

    def test_frightened_self_disadvantage(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.FRIGHTENED]
        assert any(m.op == ModifierOp.DISADVANTAGE for m in mods)

    def test_grappled_speed_zero(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.GRAPPLED]
        assert any(m.op == ModifierOp.OVERRIDE and m.stat == StatType.SPEED and m.value == 0 for m in mods)

    def test_invisible_self_advantage(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.INVISIBLE]
        assert any(m.op == ModifierOp.ADVANTAGE and m.stat == StatType.ATTACK_ROLL for m in mods)

    def test_invisible_defense_disadvantage(self) -> None:
        mods = _CONDITION_DEFENSE_MODIFIERS[Condition.INVISIBLE]
        assert any(m.op == ModifierOp.DISADVANTAGE for m in mods)

    def test_paralyzed_speed_zero(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.PARALYZED]
        assert any(m.op == ModifierOp.OVERRIDE and m.stat == StatType.SPEED and m.value == 0 for m in mods)

    def test_paralyzed_defense_advantage(self) -> None:
        mods = _CONDITION_DEFENSE_MODIFIERS[Condition.PARALYZED]
        assert any(m.op == ModifierOp.ADVANTAGE for m in mods)

    def test_poisoned_self_disadvantage(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.POISONED]
        assert any(m.op == ModifierOp.DISADVANTAGE for m in mods)

    def test_prone_self_disadvantage(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.PRONE]
        assert any(m.op == ModifierOp.DISADVANTAGE and m.stat == StatType.ATTACK_ROLL for m in mods)

    def test_prone_defense_melee_advantage(self) -> None:
        mods = _CONDITION_DEFENSE_MODIFIERS[Condition.PRONE]
        assert any(m.op == ModifierOp.ADVANTAGE and m.melee_only for m in mods)

    def test_prone_defense_ranged_disadvantage(self) -> None:
        mods = _CONDITION_DEFENSE_MODIFIERS[Condition.PRONE]
        assert any(m.op == ModifierOp.DISADVANTAGE and m.ranged_only for m in mods)

    def test_restrained_speed_zero_and_disadvantage(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.RESTRAINED]
        assert any(m.op == ModifierOp.OVERRIDE and m.stat == StatType.SPEED and m.value == 0 for m in mods)
        assert any(m.op == ModifierOp.DISADVANTAGE and m.stat == StatType.ATTACK_ROLL for m in mods)

    def test_restrained_defense_advantage(self) -> None:
        mods = _CONDITION_DEFENSE_MODIFIERS[Condition.RESTRAINED]
        assert any(m.op == ModifierOp.ADVANTAGE for m in mods)

    def test_stunned_speed_zero(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.STUNNED]
        assert any(m.op == ModifierOp.OVERRIDE and m.stat == StatType.SPEED and m.value == 0 for m in mods)

    def test_stunned_defense_advantage(self) -> None:
        mods = _CONDITION_DEFENSE_MODIFIERS[Condition.STUNNED]
        assert any(m.op == ModifierOp.ADVANTAGE for m in mods)

    def test_unconscious_speed_zero(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.UNCONSCIOUS]
        assert any(m.op == ModifierOp.OVERRIDE and m.stat == StatType.SPEED and m.value == 0 for m in mods)

    def test_unconscious_defense_advantage(self) -> None:
        mods = _CONDITION_DEFENSE_MODIFIERS[Condition.UNCONSCIOUS]
        assert any(m.op == ModifierOp.ADVANTAGE for m in mods)

    def test_blessed_dice_bonus(self) -> None:
        mods = _CONDITION_SELF_MODIFIERS[Condition.BLESSED]
        assert any(m.op == ModifierOp.ADD and m.dice == "1d4" for m in mods)

    def test_dodging_defense_disadvantage(self) -> None:
        mods = _CONDITION_DEFENSE_MODIFIERS[Condition.DODGING]
        assert any(m.op == ModifierOp.DISADVANTAGE for m in mods)

    def test_charmed_no_stat_modifiers(self) -> None:
        assert Condition.CHARMED not in _CONDITION_SELF_MODIFIERS
        assert Condition.CHARMED not in _CONDITION_DEFENSE_MODIFIERS

    def test_deafened_no_stat_modifiers(self) -> None:
        assert Condition.DEAFENED not in _CONDITION_SELF_MODIFIERS
        assert Condition.DEAFENED not in _CONDITION_DEFENSE_MODIFIERS

    def test_incapacitated_no_stat_modifiers(self) -> None:
        assert Condition.INCAPACITATED not in _CONDITION_SELF_MODIFIERS
        assert Condition.INCAPACITATED not in _CONDITION_DEFENSE_MODIFIERS


# ---------------------------------------------------------------------------
# compute_stat
# ---------------------------------------------------------------------------


class TestComputeStat:
    def test_no_modifiers(self) -> None:
        assert compute_stat(10, [], StatType.AC) == 10

    def test_add_stacks(self) -> None:
        mods = [
            Modifier(StatType.AC, ModifierOp.ADD, value=2, source="shield"),
            Modifier(StatType.AC, ModifierOp.ADD, value=1, source="ring"),
        ]
        assert compute_stat(10, mods, StatType.AC) == 13

    def test_override_wins(self) -> None:
        mods = [
            Modifier(StatType.SPEED, ModifierOp.ADD, value=10, source="boots"),
            Modifier(StatType.SPEED, ModifierOp.OVERRIDE, value=0, source="grappled"),
        ]
        assert compute_stat(30, mods, StatType.SPEED) == 0

    def test_override_takes_most_restrictive(self) -> None:
        mods = [
            Modifier(StatType.SPEED, ModifierOp.OVERRIDE, value=0, source="grappled"),
            Modifier(StatType.SPEED, ModifierOp.OVERRIDE, value=10, source="slowed"),
        ]
        assert compute_stat(30, mods, StatType.SPEED) == 0

    def test_same_source_doesnt_stack(self) -> None:
        mods = [
            Modifier(StatType.AC, ModifierOp.ADD, value=1, source="shield_spell"),
            Modifier(StatType.AC, ModifierOp.ADD, value=5, source="shield_spell"),
        ]
        # Take highest from same source
        assert compute_stat(10, mods, StatType.AC) == 15

    def test_sourceless_modifiers_always_stack(self) -> None:
        mods = [
            Modifier(StatType.AC, ModifierOp.ADD, value=2),
            Modifier(StatType.AC, ModifierOp.ADD, value=3),
        ]
        assert compute_stat(10, mods, StatType.AC) == 15

    def test_ignores_different_stat(self) -> None:
        mods = [Modifier(StatType.AC, ModifierOp.ADD, value=5, source="armor")]
        assert compute_stat(30, mods, StatType.SPEED) == 30


# ---------------------------------------------------------------------------
# resolve_advantage
# ---------------------------------------------------------------------------


class TestResolveAdvantage:
    def test_no_modifiers(self) -> None:
        assert resolve_advantage([], StatType.ATTACK_ROLL) == (False, False)

    def test_single_advantage(self) -> None:
        mods = [Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="invisible")]
        assert resolve_advantage(mods, StatType.ATTACK_ROLL) == (True, False)

    def test_single_disadvantage(self) -> None:
        mods = [Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="poisoned")]
        assert resolve_advantage(mods, StatType.ATTACK_ROLL) == (False, True)

    def test_both_cancel(self) -> None:
        mods = [
            Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="invisible"),
            Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="poisoned"),
        ]
        assert resolve_advantage(mods, StatType.ATTACK_ROLL) == (False, False)

    def test_melee_only_filtered_for_ranged(self) -> None:
        mods = [Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="prone", melee_only=True)]
        assert resolve_advantage(mods, StatType.ATTACK_ROLL, melee=False) == (False, False)

    def test_melee_only_included_for_melee(self) -> None:
        mods = [Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="prone", melee_only=True)]
        assert resolve_advantage(mods, StatType.ATTACK_ROLL, melee=True) == (True, False)

    def test_ranged_only_filtered_for_melee(self) -> None:
        mods = [Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="prone", ranged_only=True)]
        assert resolve_advantage(mods, StatType.ATTACK_ROLL, melee=True) == (False, False)

    def test_ranged_only_included_for_ranged(self) -> None:
        mods = [Modifier(StatType.ATTACK_ROLL, ModifierOp.DISADVANTAGE, source="prone", ranged_only=True)]
        assert resolve_advantage(mods, StatType.ATTACK_ROLL, melee=False) == (False, True)

    def test_multiple_advantages_still_one(self) -> None:
        """D&D 5e: any number of advantage sources = single advantage."""
        mods = [
            Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="invisible"),
            Modifier(StatType.ATTACK_ROLL, ModifierOp.ADVANTAGE, source="target_stunned"),
        ]
        assert resolve_advantage(mods, StatType.ATTACK_ROLL) == (True, False)


# ---------------------------------------------------------------------------
# collect_dice_bonuses
# ---------------------------------------------------------------------------


class TestDiceBonuses:
    def test_blessed_dice(self) -> None:
        mods = [Modifier(StatType.ATTACK_ROLL, ModifierOp.ADD, dice="1d4", source="blessed")]
        assert collect_dice_bonuses(mods, StatType.ATTACK_ROLL) == ("1d4",)

    def test_no_dice(self) -> None:
        mods = [Modifier(StatType.ATTACK_ROLL, ModifierOp.ADD, value=2, source="weapon")]
        assert collect_dice_bonuses(mods, StatType.ATTACK_ROLL) == ()

    def test_ignores_wrong_stat(self) -> None:
        mods = [Modifier(StatType.SPEED, ModifierOp.ADD, dice="1d4", source="boots")]
        assert collect_dice_bonuses(mods, StatType.ATTACK_ROLL) == ()


# ---------------------------------------------------------------------------
# effective_speed
# ---------------------------------------------------------------------------


class TestEffectiveSpeed:
    def test_base_speed(self) -> None:
        c = _creature(speed=30)
        assert effective_speed(c) == 30

    def test_grappled_zero(self) -> None:
        c = _creature(speed=30, conditions={Condition.GRAPPLED: None})
        assert effective_speed(c) == 0

    def test_stunned_zero(self) -> None:
        c = _creature(speed=30, conditions={Condition.STUNNED: 2})
        assert effective_speed(c) == 0

    def test_multiple_speed_zero_conditions(self) -> None:
        c = _creature(speed=30, conditions={Condition.GRAPPLED: None, Condition.RESTRAINED: None})
        assert effective_speed(c) == 0

    def test_non_speed_condition_no_effect(self) -> None:
        c = _creature(speed=30, conditions={Condition.POISONED: None})
        assert effective_speed(c) == 30


# ---------------------------------------------------------------------------
# effective_ac
# ---------------------------------------------------------------------------


class TestEffectiveAC:
    def test_base_ac(self) -> None:
        c = _creature(ac=15)
        assert effective_ac(c) == 15

    def test_no_conditions_affect_ac(self) -> None:
        """Currently no conditions modify AC — verify pipeline doesn't break."""
        c = _creature(ac=15, conditions={Condition.STUNNED: None})
        assert effective_ac(c) == 15


# ---------------------------------------------------------------------------
# is_auto_crit_target
# ---------------------------------------------------------------------------


class TestAutoCrit:
    def test_paralyzed_melee(self) -> None:
        assert is_auto_crit_target({Condition.PARALYZED: None}, melee=True) is True

    def test_unconscious_melee(self) -> None:
        assert is_auto_crit_target({Condition.UNCONSCIOUS: None}, melee=True) is True

    def test_paralyzed_ranged_no_crit(self) -> None:
        assert is_auto_crit_target({Condition.PARALYZED: None}, melee=False) is False

    def test_stunned_not_auto_crit(self) -> None:
        assert is_auto_crit_target({Condition.STUNNED: None}, melee=True) is False

    def test_no_conditions(self) -> None:
        assert is_auto_crit_target({}, melee=True) is False


# ---------------------------------------------------------------------------
# collect_self_modifiers / collect_defense_modifiers
# ---------------------------------------------------------------------------


class TestCollectModifiers:
    def test_weapon_magic_bonus(self) -> None:
        c = _creature(equipped_weapon=_magic_sword(modifier=2))
        mods = collect_self_modifiers(c)
        weapon_mods = [m for m in mods if m.source == "weapon_magic"]
        assert len(weapon_mods) == 1
        assert weapon_mods[0].value == 2

    def test_no_weapon_no_bonus(self) -> None:
        c = _creature()
        mods = collect_self_modifiers(c)
        assert not any(m.source == "weapon_magic" for m in mods)

    def test_condition_mods_collected(self) -> None:
        c = _creature(conditions={Condition.POISONED: None})
        mods = collect_self_modifiers(c)
        assert any(m.op == ModifierOp.DISADVANTAGE and m.stat == StatType.ATTACK_ROLL for m in mods)

    def test_defense_mods_from_dodging(self) -> None:
        c = _creature(conditions={Condition.DODGING: 1})
        mods = collect_defense_modifiers(c)
        assert any(m.op == ModifierOp.DISADVANTAGE for m in mods)


# ---------------------------------------------------------------------------
# attack_modifiers — full integration
# ---------------------------------------------------------------------------


class TestAttackModifiers:
    def test_basic_attack(self) -> None:
        attacker = _creature(str_score=16)  # +3 mod
        target = _creature(ac=15)
        result = attack_modifiers(attacker, target, melee=True)
        assert result.modifier == 3
        assert result.target_ac == 15
        assert result.advantage is False
        assert result.disadvantage is False
        assert result.force_crit is False
        assert result.dice_bonuses == ()

    def test_weapon_magic_adds_to_modifier(self) -> None:
        attacker = _creature(str_score=16, equipped_weapon=_magic_sword(modifier=2))
        target = _creature(ac=15)
        result = attack_modifiers(attacker, target, melee=True)
        assert result.modifier == 5  # +3 STR + +2 weapon

    def test_blessed_gives_dice_bonus(self) -> None:
        attacker = _creature(conditions={Condition.BLESSED: 3})
        target = _creature()
        result = attack_modifiers(attacker, target, melee=True)
        assert "1d4" in result.dice_bonuses

    def test_poisoned_attacker_disadvantage(self) -> None:
        attacker = _creature(conditions={Condition.POISONED: None})
        target = _creature()
        result = attack_modifiers(attacker, target, melee=True)
        assert result.disadvantage is True

    def test_stunned_target_advantage(self) -> None:
        attacker = _creature()
        target = _creature(conditions={Condition.STUNNED: 1})
        result = attack_modifiers(attacker, target, melee=True)
        assert result.advantage is True

    def test_dodging_target_disadvantage(self) -> None:
        attacker = _creature()
        target = _creature(conditions={Condition.DODGING: 1})
        result = attack_modifiers(attacker, target, melee=True)
        assert result.disadvantage is True

    def test_advantage_and_disadvantage_cancel(self) -> None:
        """POISONED attacker (disadv) vs STUNNED target (adv) → flat roll."""
        attacker = _creature(conditions={Condition.POISONED: None})
        target = _creature(conditions={Condition.STUNNED: 1})
        result = attack_modifiers(attacker, target, melee=True)
        assert result.advantage is False
        assert result.disadvantage is False

    def test_paralyzed_target_auto_crit_melee(self) -> None:
        attacker = _creature()
        target = _creature(conditions={Condition.PARALYZED: None})
        result = attack_modifiers(attacker, target, melee=True)
        assert result.force_crit is True
        assert result.advantage is True

    def test_paralyzed_target_no_auto_crit_ranged(self) -> None:
        attacker = _creature()
        target = _creature(conditions={Condition.PARALYZED: None})
        result = attack_modifiers(attacker, target, melee=False)
        assert result.force_crit is False

    def test_prone_target_melee_advantage(self) -> None:
        attacker = _creature()
        target = _creature(conditions={Condition.PRONE: None})
        result = attack_modifiers(attacker, target, melee=True)
        assert result.advantage is True

    def test_prone_target_ranged_disadvantage(self) -> None:
        attacker = _creature()
        target = _creature(conditions={Condition.PRONE: None})
        result = attack_modifiers(attacker, target, melee=False)
        assert result.disadvantage is True

    def test_invisible_attacker_advantage(self) -> None:
        attacker = _creature(conditions={Condition.INVISIBLE: None})
        target = _creature()
        result = attack_modifiers(attacker, target, melee=True)
        assert result.advantage is True

    def test_invisible_target_disadvantage(self) -> None:
        attacker = _creature()
        target = _creature(conditions={Condition.INVISIBLE: None})
        result = attack_modifiers(attacker, target, melee=True)
        assert result.disadvantage is True

    def test_damage_bonus_includes_ability_mod(self) -> None:
        attacker = _creature(str_score=14)  # +2 mod
        target = _creature()
        result = attack_modifiers(attacker, target, melee=True)
        assert result.damage_bonus == 2


# ---------------------------------------------------------------------------
# Fighting Style
# ---------------------------------------------------------------------------

_CHAIN_MAIL = ArmorDef(armor_id="chain_mail", category=ArmorCategory.HEAVY, base_ac=16, max_dex_bonus=0)
_STUDDED_LEATHER = ArmorDef(armor_id="studded_leather", category=ArmorCategory.LIGHT, base_ac=12, max_dex_bonus=99)

_LONGSWORD_DEF = WeaponDef(
    weapon_id="longsword",
    attack_name="slash",
    category=WeaponCategory.MARTIAL,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)


def _fighter(
    fighting_style: FightingStyle,
    *,
    strength: int = 14,
    dexterity: int = 10,
) -> Character:
    return Character(
        id="fighter",
        name="Fighter",
        location_id="loc",
        max_hp=20,
        current_hp=20,
        ac=10,
        ability_scores=AbilityScores(scores={**AbilityScores().scores, Ability.STR: strength, Ability.DEX: dexterity}),
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        class_features=[FighterFeatures(fighting_style=fighting_style)],
    )


def _sword_item() -> Item:
    return Item(id="sword_0", name="Longsword", item_type=ItemType.WEAPON, weapon_def=_LONGSWORD_DEF)


def _armor_item(armor_def: ArmorDef) -> Item:
    return Item(id="armor_0", name="Armor", item_type=ItemType.ARMOR, armor_def=armor_def)


class TestFightingStyleDefense:
    def test_defense_adds_1_ac_with_armor(self) -> None:
        fighter = _fighter(FightingStyle.DEFENSE, dexterity=10)
        fighter.equipped_armor = _armor_item(_CHAIN_MAIL)
        # chain mail base 16, +0 DEX, +1 defense = 17
        assert effective_ac(fighter) == 17

    def test_defense_no_bonus_without_armor(self) -> None:
        fighter = _fighter(FightingStyle.DEFENSE, dexterity=10)
        # No armor → 10 + 0 DEX = 10, no defense bonus
        assert effective_ac(fighter) == 10

    def test_defense_works_with_light_armor(self) -> None:
        fighter = _fighter(FightingStyle.DEFENSE, dexterity=14)
        fighter.equipped_armor = _armor_item(_STUDDED_LEATHER)
        # studded leather 12 + 2 DEX + 1 defense = 15
        assert effective_ac(fighter) == 15

    def test_dueling_style_no_ac_bonus(self) -> None:
        fighter = _fighter(FightingStyle.DUELING)
        fighter.equipped_armor = _armor_item(_CHAIN_MAIL)
        # chain mail 16, no defense bonus
        assert effective_ac(fighter) == 16


class TestFightingStyleDueling:
    def test_dueling_adds_2_on_top_of_ability(self) -> None:
        fighter = _fighter(FightingStyle.DUELING, strength=14)  # +2 ability
        fighter.equipped_weapon = _sword_item()
        target = _creature()
        result = attack_modifiers(fighter, target, melee=True)
        assert result.damage_bonus == 4  # 2 ability + 2 dueling

    def test_dueling_no_bonus_without_weapon(self) -> None:
        fighter = _fighter(FightingStyle.DUELING, strength=14)  # +2 ability
        # No weapon equipped → no dueling bonus, but ability mod still applies
        target = _creature()
        result = attack_modifiers(fighter, target, melee=True)
        assert result.damage_bonus == 2  # ability only

    def test_dueling_no_bonus_on_ranged(self) -> None:
        fighter = _fighter(FightingStyle.DUELING, strength=14)  # +2 ability
        fighter.equipped_weapon = _sword_item()
        target = _creature()
        # melee=False → no dueling bonus, but ability mod still applies
        result = attack_modifiers(fighter, target, melee=False)
        assert result.damage_bonus == 2  # ability only

    def test_defense_style_no_damage_bonus(self) -> None:
        fighter = _fighter(FightingStyle.DEFENSE, strength=14)  # +2 ability
        fighter.equipped_weapon = _sword_item()
        target = _creature()
        result = attack_modifiers(fighter, target, melee=True)
        assert result.damage_bonus == 2  # ability only, no dueling

    def test_dueling_no_bonus_with_two_handed_weapon(self) -> None:
        """Dueling style does NOT apply to two-handed weapons (PHB p.72)."""
        fighter = _fighter(FightingStyle.DUELING, strength=14)  # +2 ability
        greatsword = Item(
            id="gs_0",
            name="Greatsword",
            item_type=ItemType.WEAPON,
            weapon_def=WeaponDef(
                weapon_id="greatsword",
                attack_name="slash",
                category=WeaponCategory.MARTIAL,
                damage=(DamageComponent("2d6", DamageType.SLASHING),),
                is_two_handed=True,
            ),
        )
        fighter.equipped_weapon = greatsword
        target = _creature()
        result = attack_modifiers(fighter, target, melee=True)
        assert result.damage_bonus == 2  # ability only, no +2 dueling

    def test_plain_creature_damage_bonus_is_ability_mod(self) -> None:
        attacker = _creature(str_score=14)  # +2 ability
        target = _creature()
        result = attack_modifiers(attacker, target, melee=True)
        assert result.damage_bonus == 2


class TestGWFModifier:
    """Great Weapon Fighting sets gwf_reroll flag on AttackModifiers."""

    def test_gwf_flag_with_two_handed_weapon(self) -> None:
        fighter = _fighter(FightingStyle.GREAT_WEAPON_FIGHTING, strength=14)
        greatsword = Item(
            id="gs_0",
            name="Greatsword",
            item_type=ItemType.WEAPON,
            weapon_def=WeaponDef(
                weapon_id="greatsword",
                attack_name="slash",
                category=WeaponCategory.MARTIAL,
                damage=(DamageComponent("2d6", DamageType.SLASHING),),
                is_two_handed=True,
            ),
        )
        fighter.equipped_weapon = greatsword
        target = _creature()
        result = attack_modifiers(fighter, target, melee=True)
        assert result.gwf_reroll is True

    def test_gwf_flag_false_with_one_handed_weapon(self) -> None:
        fighter = _fighter(FightingStyle.GREAT_WEAPON_FIGHTING, strength=14)
        fighter.equipped_weapon = _sword_item()  # longsword, not two-handed
        target = _creature()
        result = attack_modifiers(fighter, target, melee=True)
        assert result.gwf_reroll is False

    def test_gwf_flag_false_without_weapon(self) -> None:
        fighter = _fighter(FightingStyle.GREAT_WEAPON_FIGHTING, strength=14)
        target = _creature()
        result = attack_modifiers(fighter, target, melee=True)
        assert result.gwf_reroll is False

    def test_non_gwf_fighter_no_flag(self) -> None:
        fighter = _fighter(FightingStyle.DUELING, strength=14)
        fighter.equipped_weapon = _sword_item()
        target = _creature()
        result = attack_modifiers(fighter, target, melee=True)
        assert result.gwf_reroll is False


# ---------------------------------------------------------------------------
# Class-feature-driven modifiers: Paladin / Rogue
# ---------------------------------------------------------------------------


def _paladin(
    fighting_style: FightingStyle | None,
    *,
    strength: int = 14,
    dexterity: int = 10,
) -> Character:
    return Character(
        id="paladin",
        name="Paladin",
        location_id="loc",
        max_hp=20,
        current_hp=20,
        ac=10,
        ability_scores=AbilityScores(scores={**AbilityScores().scores, Ability.STR: strength, Ability.DEX: dexterity}),
        race=Race.HUMAN,
        char_class=CharClass.PALADIN,
        class_features=[PaladinFeatures(fighting_style=fighting_style, level=2)],
    )


def _rogue(*, strength: int = 14, dexterity: int = 14) -> Character:
    return Character(
        id="rogue",
        name="Rogue",
        location_id="loc",
        max_hp=16,
        current_hp=16,
        ac=10,
        ability_scores=AbilityScores(scores={**AbilityScores().scores, Ability.STR: strength, Ability.DEX: dexterity}),
        race=Race.HUMAN,
        char_class=CharClass.ROGUE,
        class_features=[RogueFeatures()],
    )


class TestPaladinFightingStyle:
    def test_paladin_defense_style_gives_plus_1_ac_in_armor(self) -> None:
        paladin = _paladin(FightingStyle.DEFENSE, dexterity=10)
        paladin.equipped_armor = _armor_item(_CHAIN_MAIL)
        # chain mail 16 + 0 DEX + 1 defense = 17
        assert effective_ac(paladin) == 17

    def test_paladin_dueling_style_adds_2_damage(self) -> None:
        paladin = _paladin(FightingStyle.DUELING, strength=14)
        paladin.equipped_weapon = _sword_item()
        target = _creature()
        result = attack_modifiers(paladin, target, melee=True)
        assert result.damage_bonus == 4  # 2 ability + 2 dueling

    def test_paladin_without_fighting_style_has_no_bonus(self) -> None:
        paladin = _paladin(None, dexterity=10)
        paladin.equipped_armor = _armor_item(_CHAIN_MAIL)
        # chain mail 16, no fighting style bonus
        assert effective_ac(paladin) == 16


class TestRogueNoFightingStyleContribution:
    def test_rogue_self_mods_have_no_fighting_style_source(self) -> None:
        rogue = _rogue()
        rogue.equipped_armor = _armor_item(_STUDDED_LEATHER)
        mods = collect_self_modifiers(rogue)
        assert not any(m.source.startswith("fighting_style_") for m in mods)

    def test_rogue_attack_has_no_dueling_damage(self) -> None:
        rogue = _rogue(dexterity=14)
        rogue.equipped_weapon = _sword_item()
        target = _creature()
        result = attack_modifiers(rogue, target, melee=True)
        assert result.damage_bonus == 2  # dex only, no dueling
        assert result.gwf_reroll is False


class TestArchitectureNoHardcodedFeatureDispatch:
    def test_modifiers_py_does_not_reference_feature_subclasses(self) -> None:
        from pathlib import Path

        import dnd_simulator.rules.modifiers as mod

        source = Path(mod.__file__).read_text()
        assert "FighterFeatures" not in source, "rules/modifiers.py must not reference FighterFeatures"
        assert "PaladinFeatures" not in source, "rules/modifiers.py must not reference PaladinFeatures"
