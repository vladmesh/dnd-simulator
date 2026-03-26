"""Tests for EntitiesLayer public methods that replace Round's private _entities access."""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc, NpcRole


def _make_npc(npc_id: str, role: NpcRole, location: str, *, active: bool = True) -> Npc:
    return Npc(
        id=npc_id,
        name=npc_id,
        location_id=location,
        max_hp=10,
        current_hp=10,
        ac=10,
        speed=30,
        attacks=[],
        role=role,
        personality="test",
        active=active,
    )


def _make_creature(cid: str, *, wake_at: int | None = None) -> Creature:
    c = Creature(
        id=cid,
        name=cid,
        location_id="loc1",
        max_hp=10,
        current_hp=10,
        ac=10,
        speed=30,
        attacks=[],
    )
    c.wake_at_seconds = wake_at
    return c


class TestGetMerchantsAt:
    def test_returns_merchants_at_location(self) -> None:
        merchant_a = _make_npc("m_a", NpcRole.MERCHANT, "loc1")
        merchant_a.inventory = [
            Item(id="sword", name="Sword", item_type=ItemType.WEAPON, price=10),
        ]
        merchant_a.gold = 50
        merchant_b = _make_npc("m_b", NpcRole.MERCHANT, "loc2")
        guard = _make_npc("guard", NpcRole.GUARD, "loc1")

        layer = EntitiesLayer(entities=[merchant_a, merchant_b, guard])

        merchants = layer.get_merchants_at("loc1", hour=12)
        assert len(merchants) == 1
        assert merchants[0].id == "m_a"

    def test_excludes_dead_and_inactive(self) -> None:
        dead = _make_npc("dead", NpcRole.MERCHANT, "loc1")
        dead.current_hp = 0
        inactive = _make_npc("inactive", NpcRole.MERCHANT, "loc1", active=False)

        layer = EntitiesLayer(entities=[dead, inactive])
        assert layer.get_merchants_at("loc1", hour=12) == []


class TestGetNearestWakeTime:
    def test_returns_minimum_wake_time(self) -> None:
        c1 = _make_creature("c1", wake_at=100)
        c2 = _make_creature("c2", wake_at=50)
        c3 = _make_creature("c3", wake_at=None)

        layer = EntitiesLayer(entities=[c1, c2, c3])
        assert layer.get_nearest_wake_time() == 50

    def test_returns_none_when_no_wake_times(self) -> None:
        c1 = _make_creature("c1", wake_at=None)
        c2 = _make_creature("c2", wake_at=None)

        layer = EntitiesLayer(entities=[c1, c2])
        assert layer.get_nearest_wake_time() is None

    def test_returns_none_for_empty_layer(self) -> None:
        layer = EntitiesLayer(entities=[])
        assert layer.get_nearest_wake_time() is None
