"""Tests for D&D check mechanics — attack rolls, ability checks, saving throws."""

import random

from dnd_simulator.rules.checks import (
    ability_check,
    attack_roll,
    damage_roll,
    saving_throw,
)


class TestAttackRoll:
    def test_hit_when_total_meets_ac(self) -> None:
        # Force d20=10, modifier=5, AC=15 → 15 >= 15 → hit
        rng = self._rng_returning(10)
        result = attack_roll(modifier=5, ac=15, rng=rng)
        assert result.success is True
        assert result.roll == 10
        assert result.total == 15

    def test_miss_when_total_below_ac(self) -> None:
        rng = self._rng_returning(8)
        result = attack_roll(modifier=3, ac=15, rng=rng)
        assert result.success is False
        assert result.total == 11

    def test_nat_20_always_hits(self) -> None:
        rng = self._rng_returning(20)
        result = attack_roll(modifier=-5, ac=30, rng=rng)
        assert result.success is True
        assert result.critical is True

    def test_nat_1_always_misses(self) -> None:
        rng = self._rng_returning(1)
        result = attack_roll(modifier=20, ac=5, rng=rng)
        assert result.success is False
        assert result.critical is True

    def test_normal_roll_not_critical(self) -> None:
        rng = self._rng_returning(15)
        result = attack_roll(modifier=3, ac=10, rng=rng)
        assert result.critical is False

    @staticmethod
    def _rng_returning(value: int) -> random.Random:
        """Create an RNG that always returns ``value`` for randint(1, 20)."""
        rng = random.Random()
        rng.randint = lambda a, b: value  # type: ignore[assignment]
        return rng


class TestAbilityCheck:
    def test_success(self) -> None:
        rng = random.Random()
        rng.randint = lambda a, b: 15  # type: ignore[assignment]
        result = ability_check(modifier=2, dc=15, rng=rng)
        assert result.success is True
        assert result.total == 17

    def test_failure(self) -> None:
        rng = random.Random()
        rng.randint = lambda a, b: 5  # type: ignore[assignment]
        result = ability_check(modifier=2, dc=15, rng=rng)
        assert result.success is False

    def test_no_criticals(self) -> None:
        rng = random.Random()
        rng.randint = lambda a, b: 20  # type: ignore[assignment]
        result = ability_check(modifier=0, dc=25, rng=rng)
        # Nat 20 doesn't auto-succeed on ability checks (RAW)
        assert result.success is False
        assert result.critical is False


class TestSavingThrow:
    def test_same_as_ability_check(self) -> None:
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        a = ability_check(modifier=3, dc=14, rng=rng1)
        s = saving_throw(modifier=3, dc=14, rng=rng2)
        assert a == s


class TestDamageRoll:
    def test_normal_damage(self) -> None:
        result = damage_roll("1d8+3", rng=random.Random(42))
        assert result >= 4  # min 1+3
        assert result <= 11  # max 8+3

    def test_critical_doubles_dice(self) -> None:
        # With same seed, critical should roll more dice
        normal_results = [damage_roll("1d6+2", rng=random.Random(s)) for s in range(100)]
        crit_results = [damage_roll("1d6+2", critical=True, rng=random.Random(s)) for s in range(100)]
        # Critical average should be higher (2d6+2 vs 1d6+2)
        assert sum(crit_results) / len(crit_results) > sum(normal_results) / len(normal_results)

    def test_critical_constant_not_doubled(self) -> None:
        # "5" is a flat modifier, no dice to double
        assert damage_roll("5", critical=True) == 5

    def test_deterministic(self) -> None:
        a = damage_roll("2d6+3", rng=random.Random(99))
        b = damage_roll("2d6+3", rng=random.Random(99))
        assert a == b
