"""Tests for character creation rules — HP formula, hit dice."""

import pytest

from dnd_simulator.core.character import CharClass
from dnd_simulator.rules.character_creation import HIT_DICE, calculate_max_hp


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
