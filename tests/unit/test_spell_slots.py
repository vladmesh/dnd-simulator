"""Tests for spell slot pool infrastructure."""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.rules.resources import (
    build_spell_slot_pools,
    get_available_spell_slots,
    reset_resources,
    spell_slot_pool_id,
)


def _creature(*pools: ResourcePool) -> Creature:
    c = Creature(id="test", name="Test", location_id="arena", max_hp=10, current_hp=10, ac=10)
    c.resource_pools = list(pools)
    return c


# ---------------------------------------------------------------------------
# spell_slot_pool_id
# ---------------------------------------------------------------------------


class TestSpellSlotPoolId:
    def test_level_1(self) -> None:
        assert spell_slot_pool_id(1) == "spell_slot_1"

    def test_level_5(self) -> None:
        assert spell_slot_pool_id(5) == "spell_slot_5"


# ---------------------------------------------------------------------------
# build_spell_slot_pools
# ---------------------------------------------------------------------------


class TestBuildSpellSlotPools:
    def test_build_from_table(self) -> None:
        pools = build_spell_slot_pools({1: 2, 2: 1})
        assert len(pools) == 2
        slot1 = next(p for p in pools if p.id == "spell_slot_1")
        assert slot1.max_uses == 2
        assert slot1.current_uses == 2
        assert slot1.reset_on == RestType.LONG_REST
        slot2 = next(p for p in pools if p.id == "spell_slot_2")
        assert slot2.max_uses == 1
        assert slot2.current_uses == 1
        assert slot2.reset_on == RestType.LONG_REST

    def test_empty_table_produces_no_pools(self) -> None:
        pools = build_spell_slot_pools({})
        assert pools == []


# ---------------------------------------------------------------------------
# get_available_spell_slots
# ---------------------------------------------------------------------------


class TestGetAvailableSpellSlots:
    def test_full_pools(self) -> None:
        creature = _creature(
            ResourcePool("spell_slot_1", 2, 2, RestType.LONG_REST),
            ResourcePool("spell_slot_2", 1, 1, RestType.LONG_REST),
        )
        result = get_available_spell_slots(creature)
        assert result == {1: 2, 2: 1}

    def test_partially_depleted(self) -> None:
        creature = _creature(
            ResourcePool("spell_slot_1", 2, 1, RestType.LONG_REST),
            ResourcePool("spell_slot_2", 1, 0, RestType.LONG_REST),
        )
        result = get_available_spell_slots(creature)
        assert result == {1: 1}

    def test_no_spell_slots(self) -> None:
        creature = _creature(ResourcePool("second_wind", 1, 1, RestType.SHORT_REST))
        result = get_available_spell_slots(creature)
        assert result == {}


# ---------------------------------------------------------------------------
# Integration with rest system
# ---------------------------------------------------------------------------


class TestSpellSlotsAndRest:
    def test_long_rest_restores_spell_slots(self) -> None:
        creature = _creature(
            ResourcePool("spell_slot_1", 2, 0, RestType.LONG_REST),
            ResourcePool("spell_slot_2", 1, 0, RestType.LONG_REST),
        )
        reset_resources(creature, RestType.LONG_REST)
        assert creature.resource_pools[0].current_uses == 2
        assert creature.resource_pools[1].current_uses == 1

    def test_short_rest_does_not_restore_spell_slots(self) -> None:
        creature = _creature(
            ResourcePool("spell_slot_1", 2, 0, RestType.LONG_REST),
        )
        reset_resources(creature, RestType.SHORT_REST)
        assert creature.resource_pools[0].current_uses == 0
