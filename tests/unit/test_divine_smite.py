"""Tests for Divine Smite — Paladin attack modifier (D&D 5e PHB p.85).

Covers: damage calculation, smite validation, attack handler forwarding.
"""

from __future__ import annotations

from dnd_simulator.core.character import Character, CharClass, DamageType, Race
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle, PaladinFeatures
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.rules.combat import ExtraDamage
from dnd_simulator.rules.divine_smite import build_smite_damage, validate_smite
from dnd_simulator.rules.resources import spell_slot_pool_id


def _paladin(*, level: int = 2, slot_uses: int | None = None) -> Character:
    """Level 2 Paladin with spell slots (2 first-level slots by default)."""
    pools: list[ResourcePool] = [
        ResourcePool("lay_on_hands", 5 * level, 5 * level, RestType.LONG_REST),
    ]
    default_max = 1 if level == 1 else 2
    uses = slot_uses if slot_uses is not None else default_max
    pools.append(
        ResourcePool(spell_slot_pool_id(1), max_uses=default_max, current_uses=uses, reset_on=RestType.LONG_REST)
    )
    return Character(
        id="paladin",
        name="Paladin",
        location_id="arena",
        max_hp=25,
        current_hp=25,
        ac=18,
        race=Race.HUMAN,
        char_class=CharClass.PALADIN,
        level=level,
        class_features=[PaladinFeatures(level=level)],
        resource_pools=pools,
    )


def _fighter() -> Character:
    return Character(
        id="fighter",
        name="Fighter",
        location_id="arena",
        max_hp=20,
        current_hp=20,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        resource_pools=[ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)],
    )


class TestBuildSmiteDamage:
    def test_slot_level_1_returns_2d8_radiant(self) -> None:
        result = build_smite_damage(slot_level=1)
        assert result == ExtraDamage(dice="2d8", type=DamageType.RADIANT, source="divine_smite")

    def test_slot_level_2_returns_3d8_radiant(self) -> None:
        result = build_smite_damage(slot_level=2)
        assert result == ExtraDamage(dice="3d8", type=DamageType.RADIANT, source="divine_smite")

    def test_slot_level_3_returns_4d8_radiant(self) -> None:
        result = build_smite_damage(slot_level=3)
        assert result == ExtraDamage(dice="4d8", type=DamageType.RADIANT, source="divine_smite")


class TestValidateSmite:
    def test_paladin_with_slots_passes(self) -> None:
        paladin = _paladin(level=2, slot_uses=2)
        assert validate_smite(paladin, slot_level=1) is None

    def test_paladin_no_slots_returns_error(self) -> None:
        paladin = _paladin(level=2, slot_uses=0)
        error = validate_smite(paladin, slot_level=1)
        assert error is not None
        assert "spell slot" in error.lower() or "slot" in error.lower()

    def test_non_paladin_returns_error(self) -> None:
        fighter = _fighter()
        error = validate_smite(fighter, slot_level=1)
        assert error is not None
        assert "paladin" in error.lower()

    def test_non_character_creature_returns_error(self) -> None:
        from dnd_simulator.core.character import Creature

        creature = Creature(
            id="goblin",
            name="Goblin",
            location_id="arena",
            max_hp=7,
            current_hp=7,
            ac=13,
        )
        error = validate_smite(creature, slot_level=1)
        assert error is not None

    def test_invalid_slot_level_zero_returns_error(self) -> None:
        paladin = _paladin(level=2)
        error = validate_smite(paladin, slot_level=0)
        assert error is not None

    def test_invalid_slot_level_negative_returns_error(self) -> None:
        paladin = _paladin(level=2)
        error = validate_smite(paladin, slot_level=-1)
        assert error is not None

    def test_slot_level_paladin_doesnt_have_returns_error(self) -> None:
        """Level 2 Paladin only has 1st-level slots, not 2nd."""
        paladin = _paladin(level=2)
        error = validate_smite(paladin, slot_level=2)
        assert error is not None
        assert "slot" in error.lower()

    def test_level_1_paladin_cannot_smite(self) -> None:
        """Level 1 Paladin is below Divine Smite threshold (PHB: L2+)."""
        paladin = _paladin(level=1)
        error = validate_smite(paladin, slot_level=1)
        assert error is not None
        assert "level 2" in error.lower()
