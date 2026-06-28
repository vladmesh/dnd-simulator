"""Tests for the Container entity and its save/load persistence."""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.container import Container
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.loot import is_lootable


def _longsword() -> Item:
    return Item(id="longsword_0", name="Longsword", item_type=ItemType.WEAPON)


class TestContainerSaveLoad:
    def test_container_survives_save_load(self) -> None:
        chest = Container(id="chest_1", name="Old Chest", location_id="cave")
        chest.inventory = [_longsword()]
        chest.gold = 25

        layer = EntitiesLayer(entities=[chest])
        state = layer.get_state()

        fresh = EntitiesLayer()
        fresh.load_state(state)

        restored = fresh.get_entity("chest_1")
        assert restored is not None
        assert isinstance(restored, Container)
        assert restored.location_id == "cave"
        assert restored.gold == 25
        assert [i.id for i in restored.inventory] == ["longsword_0"]
        assert is_lootable(restored) is True

    def test_closed_state_survives_save_load(self) -> None:
        chest = Container(id="chest_1", name="Locked Chest", location_id="cave", is_open=False)

        layer = EntitiesLayer(entities=[chest])
        fresh = EntitiesLayer()
        fresh.load_state(layer.get_state())

        restored = fresh.get_entity("chest_1")
        assert isinstance(restored, Container)
        assert restored.is_open is False
        assert is_lootable(restored) is False


class TestContainerLootable:
    def test_open_container_is_lootable_closed_is_not(self) -> None:
        chest = Container(id="chest_1", name="Chest", location_id="cave", is_open=False)
        assert is_lootable(chest) is False
        chest.is_open = True
        assert is_lootable(chest) is True


class TestContainerNotACreature:
    def test_container_excluded_from_creature_queries(self) -> None:
        chest = Container(id="chest_1", name="Chest", location_id="cave")
        guard = Creature(id="guard_1", name="Guard", location_id="cave")
        layer = EntitiesLayer(entities=[chest, guard])

        active_ids = {c.id for c in layer.get_active_creatures()}
        assert "guard_1" in active_ids
        assert "chest_1" not in active_ids
        assert not isinstance(layer.get_entity("chest_1"), Creature)
