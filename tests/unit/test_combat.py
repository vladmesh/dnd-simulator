"""Tests for combat resolution."""

from __future__ import annotations

import random

from dnd_simulator.core.character import (
    Ability,
    Attack,
    DamageComponent,
    DamageType,
    ResolveType,
)
from dnd_simulator.core.rolls import DieRoll
from dnd_simulator.rules.combat import ExtraDamage, resolve_attack


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


def _flame_tongue() -> Attack:
    return Attack(
        name="flame_tongue",
        ability=Ability.STR,
        damage=(
            DamageComponent("1d8", DamageType.SLASHING),
            DamageComponent("2d6", DamageType.FIRE),
        ),
    )


def _magic_missile() -> Attack:
    return Attack(
        name="magic_missile",
        ability=Ability.INT,
        damage=(DamageComponent("1d4+1", DamageType.FORCE),),
        reach=120,
        resolve=ResolveType.AUTO_HIT,
    )


class TestResolveAttack:
    def test_hit_deals_damage(self) -> None:
        # Seed RNG so d20 roll is high enough to hit AC 10
        rng = random.Random(42)
        result = resolve_attack(modifier=3, ac=10, attack=_sword(), rng=rng)
        if result.hit:
            assert result.total_damage > 0
            assert len(result.damage) == 1
            assert result.damage[0].type == DamageType.SLASHING

    def test_guaranteed_hit_with_nat20(self) -> None:
        # Force nat 20
        rng = random.Random()
        rng.randint = lambda a, b: 20  # type: ignore[method-assign]
        result = resolve_attack(modifier=0, ac=25, attack=_sword(), rng=rng)
        assert result.hit is True
        assert result.critical is True

    def test_guaranteed_miss_with_nat1(self) -> None:
        rng = random.Random()
        rng.randint = lambda a, b: 1  # type: ignore[method-assign]
        result = resolve_attack(modifier=10, ac=5, attack=_sword(), rng=rng)
        assert result.hit is False
        assert result.total_damage == 0
        assert result.damage == ()

    def test_miss_returns_zero_damage(self) -> None:
        rng = random.Random()
        rng.randint = lambda a, b: 2  # type: ignore[method-assign]
        result = resolve_attack(modifier=0, ac=20, attack=_sword(), rng=rng)
        assert result.miss is True
        assert result.total_damage == 0

    def test_multi_component_damage(self) -> None:
        rng = random.Random()
        rng.randint = lambda a, b: 20  # type: ignore[method-assign]
        result = resolve_attack(modifier=3, ac=10, attack=_flame_tongue(), rng=rng)
        assert result.hit is True
        assert len(result.damage) == 2
        types = {d.type for d in result.damage}
        assert DamageType.SLASHING in types
        assert DamageType.FIRE in types
        assert result.total_damage > 0

    def test_auto_hit_always_succeeds(self) -> None:
        # Magic missile always hits, even vs high AC
        rng = random.Random(1)
        result = resolve_attack(modifier=0, ac=30, attack=_magic_missile(), rng=rng)
        assert result.hit is True
        assert result.critical is False
        assert result.total_damage > 0
        assert result.damage[0].type == DamageType.FORCE

    def test_extra_damage_added(self) -> None:
        # Simulate smite: extra 2d8 radiant
        rng = random.Random()
        rng.randint = lambda a, b: 20  # type: ignore[method-assign]
        result = resolve_attack(
            modifier=3,
            ac=10,
            attack=_sword(),
            extra_damage=(ExtraDamage(dice="2d8", type=DamageType.RADIANT, source="divine_smite"),),
            rng=rng,
        )
        assert result.hit is True
        assert len(result.damage) == 2
        types = {d.type for d in result.damage}
        assert DamageType.SLASHING in types
        assert DamageType.RADIANT in types


def _greatsword() -> Attack:
    return Attack(
        name="greatsword",
        ability=Ability.STR,
        damage=(DamageComponent("2d6", DamageType.SLASHING),),
    )


class TestGWFReroll:
    """Great Weapon Fighting: reroll 1-2 on weapon damage dice, once per die."""

    def test_gwf_rerolls_low_weapon_dice(self) -> None:
        """Dice showing 1 or 2 are rerolled once."""
        call_idx = 0
        # d20=15 (hit, not crit), then 2d6 damage: 1→5, 2→6
        values = [15, 1, 5, 2, 6]

        def fixed_randint(a: int, b: int) -> int:
            nonlocal call_idx
            v = values[call_idx]
            call_idx += 1
            return v

        rng = random.Random()
        rng.randint = fixed_randint  # type: ignore[method-assign]
        result = resolve_attack(
            modifier=5,
            ac=10,
            attack=_greatsword(),
            gwf_reroll=True,
            rng=rng,
        )
        assert result.hit is True
        assert result.critical is False
        # Weapon damage: rerolled 1→5 + rerolled 2→6 = 11, no bonus
        assert result.total_damage == 11
        # Check individual dice show originals
        weapon_dr = result.damage[0].dice_result
        assert weapon_dr is not None
        assert weapon_dr.dice[0] == DieRoll(sides=6, result=5, original=1)
        assert weapon_dr.dice[1] == DieRoll(sides=6, result=6, original=2)

    def test_gwf_no_reroll_on_high_dice(self) -> None:
        """Dice showing 3+ are NOT rerolled."""
        call_idx = 0
        values = [15, 4, 5]

        def fixed_randint(a: int, b: int) -> int:
            nonlocal call_idx
            v = values[call_idx]
            call_idx += 1
            return v

        rng = random.Random()
        rng.randint = fixed_randint  # type: ignore[method-assign]
        result = resolve_attack(
            modifier=5,
            ac=10,
            attack=_greatsword(),
            gwf_reroll=True,
            rng=rng,
        )
        assert result.hit is True
        assert result.total_damage == 9  # 4 + 5
        weapon_dr = result.damage[0].dice_result
        assert weapon_dr is not None
        # No originals recorded — no rerolls happened
        assert weapon_dr.dice[0].original is None
        assert weapon_dr.dice[1].original is None

    def test_gwf_keeps_rerolled_value_even_if_still_low(self) -> None:
        """D&D RAW: reroll once, keep second result even if 1 or 2."""
        call_idx = 0
        # d20=15, then 2d6: first die=1→reroll→1 (keep it), second=6 (no reroll)
        values = [15, 1, 1, 6]

        def fixed_randint(a: int, b: int) -> int:
            nonlocal call_idx
            v = values[call_idx]
            call_idx += 1
            return v

        rng = random.Random()
        rng.randint = fixed_randint  # type: ignore[method-assign]
        result = resolve_attack(
            modifier=5,
            ac=10,
            attack=_greatsword(),
            gwf_reroll=True,
            rng=rng,
        )
        assert result.hit is True
        assert result.total_damage == 7  # rerolled 1 (kept) + 6
        weapon_dr = result.damage[0].dice_result
        assert weapon_dr is not None
        assert weapon_dr.dice[0] == DieRoll(sides=6, result=1, original=1)

    def test_gwf_does_not_reroll_extra_damage(self) -> None:
        """GWF only applies to weapon damage dice, not Sneak Attack / Smite."""
        call_idx = 0
        # d20=15, weapon 2d6=[3, 4], sneak attack 1d6=[1] (should NOT be rerolled)
        values = [15, 3, 4, 1]

        def fixed_randint(a: int, b: int) -> int:
            nonlocal call_idx
            v = values[call_idx]
            call_idx += 1
            return v

        rng = random.Random()
        rng.randint = fixed_randint  # type: ignore[method-assign]
        result = resolve_attack(
            modifier=5,
            ac=10,
            attack=_greatsword(),
            gwf_reroll=True,
            extra_damage=(ExtraDamage(dice="1d6", type=DamageType.PIERCING, source="sneak_attack"),),
            rng=rng,
        )
        assert result.hit is True
        # weapon 3+4=7, sneak attack 1 (not rerolled), total=8
        assert result.total_damage == 8
        # Sneak attack die has no original (not rerolled)
        sa_dr = result.damage[1].dice_result
        assert sa_dr is not None
        assert sa_dr.dice[0].original is None

    def test_gwf_false_no_reroll(self) -> None:
        """When gwf_reroll=False (default), no rerolling happens."""
        call_idx = 0
        values = [15, 1, 2]

        def fixed_randint(a: int, b: int) -> int:
            nonlocal call_idx
            v = values[call_idx]
            call_idx += 1
            return v

        rng = random.Random()
        rng.randint = fixed_randint  # type: ignore[method-assign]
        result = resolve_attack(
            modifier=5,
            ac=10,
            attack=_greatsword(),
            rng=rng,
        )
        assert result.hit is True
        assert result.total_damage == 3  # 1 + 2, no rerolls
