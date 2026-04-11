"""Tests for character creation rules — HP formula, hit dice, point buy."""

import pytest

from dnd_simulator.core.character import Ability, CharClass
from dnd_simulator.core.class_features import FightingStyle
from dnd_simulator.rules.character_creation import (
    HIT_DICE,
    STARTING_GOLD,
    calculate_max_hp,
    starting_equipment,
    validate_point_buy,
)


class TestCalculateMaxHp:
    """D&D 5e HP formula: L1 = max hit die + CON mod (min 1 total).
    Higher levels: L1 HP + (level-1) x (die_avg_rounded_up + CON mod), min 1 per level.
    """

    def test_fighter_l1_con14(self) -> None:
        # d10 + 2 = 12
        assert calculate_max_hp(CharClass.FIGHTER, level=1, con_modifier=2) == 12

    def test_fighter_l1_con8(self) -> None:
        # d10 - 1 = 9
        assert calculate_max_hp(CharClass.FIGHTER, level=1, con_modifier=-1) == 9

    def test_rogue_l1_con12(self) -> None:
        # d8 + 1 = 9
        assert calculate_max_hp(CharClass.ROGUE, level=1, con_modifier=1) == 9

    def test_rogue_l1_con6(self) -> None:
        # d8 - 2 = 6
        assert calculate_max_hp(CharClass.ROGUE, level=1, con_modifier=-2) == 6

    def test_fighter_l1_con1(self) -> None:
        # d10 - 5 = 5 (still above 1)
        assert calculate_max_hp(CharClass.FIGHTER, level=1, con_modifier=-5) == 5

    def test_fighter_l3_con14(self) -> None:
        # L1: 10+2=12, L2-3: 2*(6+2)=16, total=28
        assert calculate_max_hp(CharClass.FIGHTER, level=3, con_modifier=2) == 28

    def test_rogue_l5_con10(self) -> None:
        # L1: 8+0=8, L2-5: 4*(5+0)=20, total=28
        assert calculate_max_hp(CharClass.ROGUE, level=5, con_modifier=0) == 28

    def test_min_1_hp_per_level(self) -> None:
        # Even with terrible CON, each level adds at least 1 HP
        # Rogue d8, avg=5, con_mod=-10 → 5+(-10)=-5 → clamped to 1 per level
        # L1: max(8-10, 1)=1, L2: max(5-10, 1)=1, total=2
        assert calculate_max_hp(CharClass.ROGUE, level=2, con_modifier=-10) == 2

    def test_min_1_total_hp_at_l1(self) -> None:
        # L1 total HP is at least 1
        assert calculate_max_hp(CharClass.ROGUE, level=1, con_modifier=-10) == 1

    def test_unknown_class_raises(self) -> None:
        with pytest.raises(RuntimeError, match="No hit die defined"):
            calculate_max_hp(CharClass.WIZARD, level=1, con_modifier=0)

    def test_level_zero_raises(self) -> None:
        with pytest.raises(RuntimeError, match="level"):
            calculate_max_hp(CharClass.FIGHTER, level=0, con_modifier=0)

    def test_negative_level_raises(self) -> None:
        with pytest.raises(RuntimeError, match="level"):
            calculate_max_hp(CharClass.FIGHTER, level=-1, con_modifier=0)


class TestHitDice:
    """HIT_DICE mapping covers Fighter and Rogue."""

    def test_fighter_d10(self) -> None:
        assert HIT_DICE[CharClass.FIGHTER] == 10

    def test_rogue_d8(self) -> None:
        assert HIT_DICE[CharClass.ROGUE] == 8


class TestValidatePointBuy:
    """D&D 5e point buy: 27 points, scores 8-15, specific cost table."""

    def test_standard_array_valid(self) -> None:
        # {15, 14, 13, 12, 10, 8} -> 9+7+5+4+2+0 = 27
        scores = {
            Ability.STR: 15,
            Ability.DEX: 14,
            Ability.CON: 13,
            Ability.INT: 12,
            Ability.WIS: 10,
            Ability.CHA: 8,
        }
        validate_point_buy(scores)  # should not raise

    def test_all_13s_over_budget(self) -> None:
        scores = {a: 13 for a in Ability}
        with pytest.raises(ValueError, match=r"30.*exceeds.*27"):
            validate_point_buy(scores)

    def test_all_8s_underspend_valid(self) -> None:
        scores = {a: 8 for a in Ability}
        validate_point_buy(scores)  # underspending allowed

    def test_score_above_15_raises(self) -> None:
        scores = {
            Ability.STR: 16,
            Ability.DEX: 8,
            Ability.CON: 8,
            Ability.INT: 8,
            Ability.WIS: 8,
            Ability.CHA: 8,
        }
        with pytest.raises(ValueError, match=r"16.*out of range"):
            validate_point_buy(scores)

    def test_score_below_8_raises(self) -> None:
        scores = {
            Ability.STR: 7,
            Ability.DEX: 8,
            Ability.CON: 8,
            Ability.INT: 8,
            Ability.WIS: 8,
            Ability.CHA: 8,
        }
        with pytest.raises(ValueError, match=r"7.*out of range"):
            validate_point_buy(scores)

    def test_missing_ability_raises(self) -> None:
        scores = {
            Ability.STR: 10,
            Ability.DEX: 10,
            Ability.CON: 10,
            Ability.INT: 10,
            Ability.WIS: 10,
        }
        with pytest.raises(ValueError, match="Missing abilities"):
            validate_point_buy(scores)

    def test_balanced_build_underspend_valid(self) -> None:
        # {14,14,14,10,8,8} -> 7+7+7+2+0+0 = 23
        scores = {
            Ability.STR: 14,
            Ability.DEX: 14,
            Ability.CON: 14,
            Ability.INT: 10,
            Ability.WIS: 8,
            Ability.CHA: 8,
        }
        validate_point_buy(scores)

    def test_exact_max_valid(self) -> None:
        # {15,15,15,8,8,8} -> 9+9+9+0+0+0 = 27
        scores = {
            Ability.STR: 15,
            Ability.DEX: 15,
            Ability.CON: 15,
            Ability.INT: 8,
            Ability.WIS: 8,
            Ability.CHA: 8,
        }
        validate_point_buy(scores)

    def test_one_over_budget_raises(self) -> None:
        # {15,15,15,9,8,8} -> 9+9+9+1+0+0 = 28
        scores = {
            Ability.STR: 15,
            Ability.DEX: 15,
            Ability.CON: 15,
            Ability.INT: 9,
            Ability.WIS: 8,
            Ability.CHA: 8,
        }
        with pytest.raises(ValueError, match=r"28.*exceeds.*27"):
            validate_point_buy(scores)


class TestStartingEquipment:
    """Starting equipment per class — item catalog refs."""

    def test_fighter_equipment(self) -> None:
        equip = starting_equipment(CharClass.FIGHTER)
        assert set(equip) == {"chain_mail", "longsword", "shield"}

    def test_rogue_equipment(self) -> None:
        equip = starting_equipment(CharClass.ROGUE)
        assert set(equip) == {"leather", "rapier", "shortbow", "dagger"}

    def test_fighter_no_rogue_items(self) -> None:
        equip = starting_equipment(CharClass.FIGHTER)
        assert "dagger" not in equip
        assert "shortbow" not in equip

    def test_rogue_no_fighter_items(self) -> None:
        equip = starting_equipment(CharClass.ROGUE)
        assert "chain_mail" not in equip
        assert "shield" not in equip

    def test_unknown_class_raises(self) -> None:
        with pytest.raises(RuntimeError, match="No starting equipment"):
            starting_equipment(CharClass.WIZARD)

    def test_fighter_gwf_gets_greatsword(self) -> None:
        equip = starting_equipment(CharClass.FIGHTER, FightingStyle.GREAT_WEAPON_FIGHTING)
        assert set(equip) == {"chain_mail", "greatsword"}
        assert "shield" not in equip
        assert "longsword" not in equip

    def test_fighter_defense_gets_longsword_shield(self) -> None:
        equip = starting_equipment(CharClass.FIGHTER, FightingStyle.DEFENSE)
        assert set(equip) == {"chain_mail", "longsword", "shield"}

    def test_fighter_no_style_gets_longsword_shield(self) -> None:
        equip = starting_equipment(CharClass.FIGHTER, None)
        assert set(equip) == {"chain_mail", "longsword", "shield"}

    def test_returns_copy(self) -> None:
        a = starting_equipment(CharClass.FIGHTER)
        b = starting_equipment(CharClass.FIGHTER)
        assert a is not b


class TestStartingGold:
    def test_starting_gold_is_1000(self) -> None:
        assert STARTING_GOLD == 1000
