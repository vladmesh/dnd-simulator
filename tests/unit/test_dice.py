"""Tests for dice rolling mechanics."""

import random

from dnd_simulator.rules.dice import roll, roll_d20


class TestRollD20:
    def test_range(self) -> None:
        rng = random.Random(42)
        results = {roll_d20(rng=rng).natural for _ in range(200)}
        assert min(results) >= 1
        assert max(results) <= 20

    def test_deterministic_with_seed(self) -> None:
        a = roll_d20(rng=random.Random(1)).natural
        b = roll_d20(rng=random.Random(1)).natural
        assert a == b

    def test_advantage_takes_higher(self) -> None:
        results = [roll_d20(advantage=True, rng=random.Random(s)).natural for s in range(100)]
        # Average with advantage should be higher than 10.5
        assert sum(results) / len(results) > 11

    def test_disadvantage_takes_lower(self) -> None:
        results = [roll_d20(disadvantage=True, rng=random.Random(s)).natural for s in range(100)]
        assert sum(results) / len(results) < 10

    def test_advantage_and_disadvantage_cancel(self) -> None:
        # When both are set, should roll once (same as normal)
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        normal = roll_d20(rng=rng1).natural
        both = roll_d20(advantage=True, disadvantage=True, rng=rng2).natural
        assert normal == both


class TestRoll:
    def test_constant(self) -> None:
        assert roll("5").total == 5

    def test_single_die(self) -> None:
        rng = random.Random(42)
        result = roll("1d6", rng=rng).total
        assert 1 <= result <= 6

    def test_multiple_dice(self) -> None:
        rng = random.Random(42)
        result = roll("3d6", rng=rng).total
        assert 3 <= result <= 18

    def test_dice_plus_modifier(self) -> None:
        base = roll("1d6", rng=random.Random(42)).total
        result = roll("1d6+3", rng=random.Random(42)).total
        assert result == base + 3

    def test_dice_minus_modifier(self) -> None:
        base = roll("1d8", rng=random.Random(42)).total
        result = roll("1d8-2", rng=random.Random(42)).total
        assert result == base - 2

    def test_d20(self) -> None:
        rng = random.Random(42)
        result = roll("1d20", rng=rng).total
        assert 1 <= result <= 20

    def test_invalid_expression(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="Invalid dice expression"):
            roll("abc")

    def test_whitespace_tolerance(self) -> None:
        a = roll("2d6 + 3", rng=random.Random(42)).total
        b = roll("2d6+3", rng=random.Random(42)).total
        assert a == b

    def test_deterministic(self) -> None:
        a = roll("4d6+2", rng=random.Random(99)).total
        b = roll("4d6+2", rng=random.Random(99)).total
        assert a == b


class TestDiceSeedFunction:
    def test_set_global_seed_makes_rng_deterministic(self) -> None:
        from dnd_simulator.rules.dice import set_global_seed

        set_global_seed(42)
        results_a = [roll_d20().natural for _ in range(10)]

        set_global_seed(42)
        results_b = [roll_d20().natural for _ in range(10)]

        assert results_a == results_b

    def test_default_rng_works(self) -> None:
        result = roll_d20().natural
        assert 1 <= result <= 20
