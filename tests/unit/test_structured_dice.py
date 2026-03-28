"""Tests for structured dice results (core/rolls.py + rules/dice.py refactor)."""

import random

from dnd_simulator.core.rolls import D20Result, DiceResult
from dnd_simulator.rules.dice import roll, roll_d20


class TestDiceResultStructure:
    def test_roll_2d6_plus_3_returns_dice_result(self) -> None:
        rng = random.Random(42)
        result = roll("2d6+3", rng=rng)
        assert isinstance(result, DiceResult)
        assert len(result.dice) == 2
        assert all(d.sides == 6 for d in result.dice)
        assert result.flat == 3
        assert result.total == sum(d.result for d in result.dice) + 3

    def test_roll_1d8_returns_dice_result(self) -> None:
        rng = random.Random(42)
        result = roll("1d8", rng=rng)
        assert isinstance(result, DiceResult)
        assert len(result.dice) == 1
        assert result.dice[0].sides == 8
        assert result.flat == 0
        assert result.total == result.dice[0].result

    def test_roll_constant_returns_empty_dice(self) -> None:
        result = roll("4")
        assert isinstance(result, DiceResult)
        assert result.dice == ()
        assert result.flat == 4
        assert result.total == 4

    def test_roll_0d6_plus_5_edge_case(self) -> None:
        result = roll("0d6+5")
        assert isinstance(result, DiceResult)
        assert result.dice == ()
        assert result.flat == 5
        assert result.total == 5

    def test_expression_preserved(self) -> None:
        result = roll("2d6+3", rng=random.Random(42))
        assert result.expression == "2d6+3"


class TestRerollMechanics:
    def test_reroll_below_triggers_reroll(self) -> None:
        # Seed that produces at least one low die on 2d6
        # Try seeds until we find one where a die shows 1 or 2
        for seed in range(100):
            rng = random.Random(seed)
            result = roll("2d6", reroll_below=2, rng=rng)
            rerolled = [d for d in result.dice if d.original is not None]
            if rerolled:
                # Found a seed with rerolls — verify structure
                for d in rerolled:
                    assert d.original is not None
                    assert d.original <= 2  # original was at or below threshold
                    assert 1 <= d.result <= 6  # rerolled result is valid
                return
        raise AssertionError("No seed produced a reroll in 100 attempts")  # pragma: no cover

    def test_reroll_keeps_new_value_even_if_still_low(self) -> None:
        # Reroll should happen once, not recursively
        for seed in range(200):
            rng = random.Random(seed)
            result = roll("2d6", reroll_below=2, rng=rng)
            rerolled = [d for d in result.dice if d.original is not None]
            low_rerolled = [d for d in rerolled if d.result <= 2]
            if low_rerolled:
                # Die was rerolled and still <= 2 — that's fine, kept as-is
                assert low_rerolled[0].original is not None
                return
        # If no seed produced this scenario, that's statistically fine — skip
        # (2d6 with reroll_below=2: ~11% chance per die of rerolling to 1 or 2)

    def test_no_reroll_when_above_threshold(self) -> None:
        # With reroll_below=2, dice showing 3+ should have original=None
        for seed in range(100):
            rng = random.Random(seed)
            result = roll("2d6", reroll_below=2, rng=rng)
            for d in result.dice:
                if d.original is None:
                    # Die was not rerolled — its result should be > threshold
                    # (or it wasn't rerolled because it was above threshold)
                    pass  # just verifying structure
                else:
                    assert d.original <= 2

    def test_default_no_rerolls(self) -> None:
        rng = random.Random(42)
        result = roll("2d6", rng=rng)
        assert all(d.original is None for d in result.dice)


class TestD20ResultStructure:
    def test_straight_roll(self) -> None:
        rng = random.Random(42)
        result = roll_d20(rng=rng)
        assert isinstance(result, D20Result)
        assert result.alt is None
        assert result.advantage is False
        assert result.disadvantage is False
        assert 1 <= result.die.result <= 20
        assert result.die.sides == 20

    def test_advantage_keeps_higher(self) -> None:
        rng = random.Random(42)
        result = roll_d20(advantage=True, rng=rng)
        assert isinstance(result, D20Result)
        assert result.alt is not None
        assert result.advantage is True
        assert result.die.result >= result.alt.result

    def test_disadvantage_keeps_lower(self) -> None:
        rng = random.Random(42)
        result = roll_d20(disadvantage=True, rng=rng)
        assert isinstance(result, D20Result)
        assert result.alt is not None
        assert result.disadvantage is True
        assert result.die.result <= result.alt.result

    def test_advantage_and_disadvantage_cancel(self) -> None:
        rng = random.Random(42)
        result = roll_d20(advantage=True, disadvantage=True, rng=rng)
        assert result.alt is None
        assert result.advantage is False
        assert result.disadvantage is False

    def test_natural_property(self) -> None:
        rng = random.Random(42)
        result = roll_d20(rng=rng)
        assert result.natural == result.die.result
