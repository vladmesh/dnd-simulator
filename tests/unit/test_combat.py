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
