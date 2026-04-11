"""Tests for resource pool system."""

from __future__ import annotations

import pytest

from dnd_simulator.core.character import Creature
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.rules.resources import has_resource, reset_resources, use_resource


def _creature(*pools: ResourcePool) -> Creature:
    c = Creature(id="test", name="Test", location_id="arena", max_hp=10, current_hp=10, ac=10)
    c.resource_pools = list(pools)
    return c


# ---------------------------------------------------------------------------
# ResourcePool validation
# ---------------------------------------------------------------------------


class TestResourcePoolValidation:
    def test_max_uses_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="max_uses must be >= 1"):
            ResourcePool(id="bad", max_uses=0, current_uses=0, reset_on=RestType.SHORT_REST)

    def test_current_uses_cannot_exceed_max(self) -> None:
        with pytest.raises(ValueError, match=r"current_uses must be 0\.\.2"):
            ResourcePool(id="bad", max_uses=2, current_uses=3, reset_on=RestType.SHORT_REST)

    def test_current_uses_cannot_be_negative(self) -> None:
        with pytest.raises(ValueError, match=r"current_uses must be 0\.\.1"):
            ResourcePool(id="bad", max_uses=1, current_uses=-1, reset_on=RestType.SHORT_REST)

    def test_valid_pool(self) -> None:
        pool = ResourcePool(id="ok", max_uses=3, current_uses=2, reset_on=RestType.LONG_REST)
        assert pool.current_uses == 2


# ---------------------------------------------------------------------------
# has_resource
# ---------------------------------------------------------------------------


class TestHasResource:
    def test_has_resource_with_uses(self) -> None:
        creature = _creature(ResourcePool("second_wind", 1, 1, RestType.SHORT_REST))
        assert has_resource(creature, "second_wind") is True

    def test_has_resource_exhausted(self) -> None:
        creature = _creature(ResourcePool("second_wind", 1, 0, RestType.SHORT_REST))
        assert has_resource(creature, "second_wind") is False

    def test_has_resource_missing_pool_raises(self) -> None:
        creature = _creature()
        with pytest.raises(KeyError, match="No resource pool 'second_wind'"):
            has_resource(creature, "second_wind")


# ---------------------------------------------------------------------------
# use_resource
# ---------------------------------------------------------------------------


class TestUseResource:
    def test_use_decrements(self) -> None:
        pool = ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)
        creature = _creature(pool)
        use_resource(creature, "second_wind")
        assert pool.current_uses == 0

    def test_use_multiple_times(self) -> None:
        pool = ResourcePool("action_surge", 2, 2, RestType.SHORT_REST)
        creature = _creature(pool)
        use_resource(creature, "action_surge")
        assert pool.current_uses == 1
        use_resource(creature, "action_surge")
        assert pool.current_uses == 0

    def test_use_exhausted_raises(self) -> None:
        creature = _creature(ResourcePool("second_wind", 1, 0, RestType.SHORT_REST))
        with pytest.raises(ValueError, match="insufficient uses"):
            use_resource(creature, "second_wind")

    def test_use_missing_pool_raises(self) -> None:
        creature = _creature()
        with pytest.raises(KeyError, match="No resource pool"):
            use_resource(creature, "second_wind")


# ---------------------------------------------------------------------------
# reset_resources
# ---------------------------------------------------------------------------


class TestResetResources:
    def test_short_rest_resets_short_rest_pools(self) -> None:
        pool = ResourcePool("second_wind", 1, 0, RestType.SHORT_REST)
        creature = _creature(pool)
        reset_ids = reset_resources(creature, RestType.SHORT_REST)
        assert pool.current_uses == 1
        assert reset_ids == ["second_wind"]

    def test_short_rest_does_not_reset_long_rest_pools(self) -> None:
        pool = ResourcePool("spell_slot_1", 2, 0, RestType.LONG_REST)
        creature = _creature(pool)
        reset_ids = reset_resources(creature, RestType.SHORT_REST)
        assert pool.current_uses == 0
        assert reset_ids == []

    def test_long_rest_resets_both(self) -> None:
        short_pool = ResourcePool("second_wind", 1, 0, RestType.SHORT_REST)
        long_pool = ResourcePool("spell_slot_1", 2, 0, RestType.LONG_REST)
        creature = _creature(short_pool, long_pool)
        reset_ids = reset_resources(creature, RestType.LONG_REST)
        assert short_pool.current_uses == 1
        assert long_pool.current_uses == 2
        assert set(reset_ids) == {"second_wind", "spell_slot_1"}

    def test_already_full_pool_not_in_reset_list(self) -> None:
        pool = ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)
        creature = _creature(pool)
        reset_ids = reset_resources(creature, RestType.SHORT_REST)
        assert pool.current_uses == 1
        assert reset_ids == []

    def test_partial_pool_resets_to_max(self) -> None:
        pool = ResourcePool("action_surge", 3, 1, RestType.SHORT_REST)
        creature = _creature(pool)
        reset_resources(creature, RestType.SHORT_REST)
        assert pool.current_uses == 3

    def test_multiple_pools_mixed(self) -> None:
        pools = [
            ResourcePool("second_wind", 1, 0, RestType.SHORT_REST),
            ResourcePool("action_surge", 1, 1, RestType.SHORT_REST),  # full
            ResourcePool("spell_slot_1", 4, 2, RestType.LONG_REST),
        ]
        creature = _creature(*pools)
        reset_ids = reset_resources(creature, RestType.SHORT_REST)
        assert pools[0].current_uses == 1  # reset
        assert pools[1].current_uses == 1  # unchanged (was full)
        assert pools[2].current_uses == 2  # unchanged (long rest only)
        assert reset_ids == ["second_wind"]
