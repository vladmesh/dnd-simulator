"""Tests for D&D 5e Conditions mechanics."""

from __future__ import annotations

import random

from dnd_simulator.core.character import (
    Ability,
    Attack,
    Character,
    Creature,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.conditions import Condition
from dnd_simulator.rules.combat import resolve_attack
from dnd_simulator.rules.conditions import (
    attacker_has_disadvantage,
    attacks_against_have_advantage,
    attacks_against_have_disadvantage,
    effective_speed,
    is_auto_crit,
    is_incapacitated,
    prone_stand_cost,
)


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


def _bow() -> Attack:
    return Attack(
        name="longbow",
        ability=Ability.DEX,
        damage=(DamageComponent("1d8", DamageType.PIERCING),),
        reach=150,
    )


def _make_creature(*, conditions: set[Condition] | None = None, speed: int = 30) -> Creature:
    return Creature(
        id="test",
        name="Test",
        location_id="loc",
        speed=speed,
        conditions=conditions or set(),
    )


# ---------------------------------------------------------------------------
# Pure rules functions
# ---------------------------------------------------------------------------


class TestIsIncapacitated:
    def test_no_conditions(self) -> None:
        assert not is_incapacitated(set())

    def test_stunned(self) -> None:
        assert is_incapacitated({Condition.STUNNED})

    def test_paralyzed(self) -> None:
        assert is_incapacitated({Condition.PARALYZED})

    def test_unconscious(self) -> None:
        assert is_incapacitated({Condition.UNCONSCIOUS})

    def test_petrified(self) -> None:
        assert is_incapacitated({Condition.PETRIFIED})

    def test_incapacitated_itself(self) -> None:
        assert is_incapacitated({Condition.INCAPACITATED})

    def test_prone_is_not_incapacitated(self) -> None:
        assert not is_incapacitated({Condition.PRONE})


class TestEffectiveSpeed:
    def test_no_conditions(self) -> None:
        assert effective_speed(30, set()) == 30

    def test_grappled(self) -> None:
        assert effective_speed(30, {Condition.GRAPPLED}) == 0

    def test_restrained(self) -> None:
        assert effective_speed(30, {Condition.RESTRAINED}) == 0

    def test_stunned(self) -> None:
        assert effective_speed(30, {Condition.STUNNED}) == 0

    def test_prone_does_not_reduce_speed(self) -> None:
        assert effective_speed(30, {Condition.PRONE}) == 30

    def test_prone_stand_cost(self) -> None:
        assert prone_stand_cost(30) == 15


class TestAttackerDisadvantage:
    def test_blinded(self) -> None:
        assert attacker_has_disadvantage({Condition.BLINDED})

    def test_frightened(self) -> None:
        assert attacker_has_disadvantage({Condition.FRIGHTENED})

    def test_poisoned(self) -> None:
        assert attacker_has_disadvantage({Condition.POISONED})

    def test_prone(self) -> None:
        assert attacker_has_disadvantage({Condition.PRONE})

    def test_restrained(self) -> None:
        assert attacker_has_disadvantage({Condition.RESTRAINED})

    def test_grappled_no_disadvantage(self) -> None:
        assert not attacker_has_disadvantage({Condition.GRAPPLED})


class TestAttacksAgainstTarget:
    def test_stunned_gives_advantage(self) -> None:
        assert attacks_against_have_advantage({Condition.STUNNED}, melee=True)
        assert attacks_against_have_advantage({Condition.STUNNED}, melee=False)

    def test_paralyzed_gives_advantage(self) -> None:
        assert attacks_against_have_advantage({Condition.PARALYZED}, melee=True)

    def test_prone_melee_advantage(self) -> None:
        assert attacks_against_have_advantage({Condition.PRONE}, melee=True)

    def test_prone_ranged_disadvantage(self) -> None:
        assert not attacks_against_have_advantage({Condition.PRONE}, melee=False)
        assert attacks_against_have_disadvantage({Condition.PRONE}, melee=False)

    def test_prone_ranged_no_advantage(self) -> None:
        assert not attacks_against_have_advantage({Condition.PRONE}, melee=False)

    def test_invisible_gives_disadvantage(self) -> None:
        assert attacks_against_have_disadvantage({Condition.INVISIBLE}, melee=True)

    def test_no_conditions_no_effect(self) -> None:
        assert not attacks_against_have_advantage(set(), melee=True)
        assert not attacks_against_have_disadvantage(set(), melee=True)


class TestAutoCrit:
    def test_paralyzed_melee_auto_crit(self) -> None:
        assert is_auto_crit({Condition.PARALYZED}, melee=True)

    def test_unconscious_melee_auto_crit(self) -> None:
        assert is_auto_crit({Condition.UNCONSCIOUS}, melee=True)

    def test_paralyzed_ranged_no_auto_crit(self) -> None:
        assert not is_auto_crit({Condition.PARALYZED}, melee=False)

    def test_stunned_no_auto_crit(self) -> None:
        assert not is_auto_crit({Condition.STUNNED}, melee=True)


# ---------------------------------------------------------------------------
# Integration: resolve_attack with force_crit
# ---------------------------------------------------------------------------


class TestForceCrit:
    def test_force_crit_doubles_damage_dice(self) -> None:
        """force_crit=True should make a hit into a crit (doubled dice)."""
        rng = random.Random()
        rng.randint = lambda a, b: 15  # type: ignore[method-assign]
        result = resolve_attack(
            modifier=5,
            ac=10,
            attack=_sword(),
            force_crit=True,
            rng=rng,
        )
        assert result.hit
        assert result.critical


# ---------------------------------------------------------------------------
# Creature field
# ---------------------------------------------------------------------------


class TestCreatureConditions:
    def test_default_empty(self) -> None:
        c = _make_creature()
        assert c.conditions == set()

    def test_add_remove_condition(self) -> None:
        c = _make_creature()
        c.conditions.add(Condition.PRONE)
        assert Condition.PRONE in c.conditions
        c.conditions.discard(Condition.PRONE)
        assert Condition.PRONE not in c.conditions

    def test_conditions_in_perceive(self) -> None:
        observer = Character(
            id="obs",
            name="Observer",
            location_id="loc",
            race=Race.HUMAN,
        )
        target = Character(
            id="tgt",
            name="Target",
            location_id="loc",
            race=Race.ELF,
            conditions={Condition.PRONE, Condition.STUNNED},
        )
        desc = observer.perceive(target)
        assert "prone" in desc
        assert "stunned" in desc


# ---------------------------------------------------------------------------
# Save/load round-trip
# ---------------------------------------------------------------------------


class TestConditionsSaveLoad:
    def test_serialize_conditions(self) -> None:
        """Conditions serialize as sorted list of string values."""
        c = _make_creature(conditions={Condition.PRONE, Condition.STUNNED})
        serialized = sorted(cond.value for cond in c.conditions)
        assert serialized == ["prone", "stunned"]

    def test_deserialize_conditions(self) -> None:
        """Conditions deserialize from list of strings."""
        raw = ["grappled", "poisoned"]
        conditions = {Condition(v) for v in raw}
        assert conditions == {Condition.GRAPPLED, Condition.POISONED}
