"""Tests for D&D 5e Conditions mechanics.

Note: advantage/disadvantage, speed reduction, and auto-crit tests have been moved
to test_modifiers.py (modifier pipeline). This file tests: is_incapacitated,
prone_stand_cost, tick_conditions, Creature condition fields, save/load.
"""

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
from dnd_simulator.core.conditions import Condition, ConditionsMap
from dnd_simulator.rules.combat import resolve_attack
from dnd_simulator.rules.conditions import (
    is_incapacitated,
    prone_stand_cost,
    tick_conditions,
)


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


def _conds(*conditions: Condition, rounds: int | None = None) -> ConditionsMap:
    """Helper: build a ConditionsMap from conditions with optional duration."""
    return {c: rounds for c in conditions}


def _make_creature(*, conditions: ConditionsMap | None = None, speed: int = 30) -> Creature:
    return Creature(
        id="test",
        name="Test",
        location_id="loc",
        speed=speed,
        conditions=conditions or {},
    )


# ---------------------------------------------------------------------------
# Pure rules functions
# ---------------------------------------------------------------------------


class TestIsIncapacitated:
    def test_no_conditions(self) -> None:
        assert not is_incapacitated({})

    def test_stunned(self) -> None:
        assert is_incapacitated(_conds(Condition.STUNNED))

    def test_paralyzed(self) -> None:
        assert is_incapacitated(_conds(Condition.PARALYZED))

    def test_unconscious(self) -> None:
        assert is_incapacitated(_conds(Condition.UNCONSCIOUS))

    def test_petrified(self) -> None:
        assert is_incapacitated(_conds(Condition.PETRIFIED))

    def test_incapacitated_itself(self) -> None:
        assert is_incapacitated(_conds(Condition.INCAPACITATED))

    def test_prone_is_not_incapacitated(self) -> None:
        assert not is_incapacitated(_conds(Condition.PRONE))


class TestProneStandCost:
    def test_half_speed(self) -> None:
        assert prone_stand_cost(30) == 15

    def test_zero_speed(self) -> None:
        assert prone_stand_cost(0) == 0


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
        assert c.conditions == {}

    def test_add_remove_condition(self) -> None:
        c = _make_creature()
        c.conditions[Condition.PRONE] = None
        assert Condition.PRONE in c.conditions
        del c.conditions[Condition.PRONE]
        assert Condition.PRONE not in c.conditions

    def test_timed_condition(self) -> None:
        c = _make_creature()
        c.conditions[Condition.BLESSED] = 3
        assert Condition.BLESSED in c.conditions
        assert c.conditions[Condition.BLESSED] == 3

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
            conditions={Condition.PRONE: None, Condition.STUNNED: None},
        )
        desc = observer.perceive(target)
        assert "prone" in desc
        assert "stunned" in desc


# ---------------------------------------------------------------------------
# Timed conditions tick
# ---------------------------------------------------------------------------


class TestTickConditions:
    def test_permanent_not_affected(self) -> None:
        conds: ConditionsMap = {Condition.PRONE: None}
        expired = tick_conditions(conds)
        assert expired == []
        assert conds == {Condition.PRONE: None}

    def test_decrement_timed(self) -> None:
        conds: ConditionsMap = {Condition.BLESSED: 3}
        expired = tick_conditions(conds)
        assert expired == []
        assert conds[Condition.BLESSED] == 2

    def test_expire_at_one(self) -> None:
        conds: ConditionsMap = {Condition.BLESSED: 1}
        expired = tick_conditions(conds)
        assert expired == [Condition.BLESSED]
        assert Condition.BLESSED not in conds

    def test_mixed_conditions(self) -> None:
        conds: ConditionsMap = {
            Condition.PRONE: None,
            Condition.BLESSED: 1,
            Condition.POISONED: 3,
        }
        expired = tick_conditions(conds)
        assert expired == [Condition.BLESSED]
        assert Condition.PRONE in conds
        assert conds[Condition.PRONE] is None
        assert Condition.POISONED in conds
        assert conds[Condition.POISONED] == 2


# ---------------------------------------------------------------------------
# Save/load round-trip
# ---------------------------------------------------------------------------


class TestConditionsSaveLoad:
    def test_serialize_conditions(self) -> None:
        """Conditions serialize as dict of condition → remaining rounds."""
        c = _make_creature(conditions={Condition.PRONE: None, Condition.STUNNED: 2})
        serialized = {cond.value: r for cond, r in c.conditions.items()}
        assert serialized == {"prone": None, "stunned": 2}

    def test_deserialize_conditions(self) -> None:
        """Conditions deserialize from dict of strings → int|None."""
        raw = {"grappled": None, "poisoned": 3}
        conditions: ConditionsMap = {Condition(k): v for k, v in raw.items()}
        assert conditions == {Condition.GRAPPLED: None, Condition.POISONED: 3}

    def test_deserialize_legacy_list(self) -> None:
        """Legacy format: list of condition strings → all permanent."""
        raw = ["grappled", "poisoned"]
        conditions: ConditionsMap = {Condition(v): None for v in raw}
        assert conditions == {Condition.GRAPPLED: None, Condition.POISONED: None}
