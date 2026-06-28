"""Lootable holders (corpses, open containers) surface in peaceful awareness."""

from __future__ import annotations

from dnd_simulator.core.awareness import PeacefulAwareness
from dnd_simulator.core.character import Character, Creature
from dnd_simulator.core.container import Container
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.models import Answer, GameDateTime, Query
from dnd_simulator.layers.entities.layer import EntitiesLayer

_TIME = GameDateTime(year=1490, month=6, day=15, hour=14)
CAVE = "cave"


def _query_fn(target: str, query: Query) -> Answer:
    return Answer(value=None)


def _player() -> Character:
    return Character(id="player_1", name="Hero", location_id=CAVE)


def _peaceful(layer: EntitiesLayer, player: Creature) -> PeacefulAwareness:
    awareness = layer.build_awareness(player, _TIME, _query_fn)
    assert isinstance(awareness, PeacefulAwareness)
    return awareness


class TestLootableInAwareness:
    def test_dead_creature_appears_as_lootable(self) -> None:
        player = _player()
        corpse = Creature(id="goblin_corpse", name="Goblin", location_id=CAVE, max_hp=7, current_hp=0)
        corpse.active = False  # corpses are dormant after death — must still surface
        corpse.inventory = [Item(id="sword_0", name="Longsword", item_type=ItemType.WEAPON)]
        corpse.gold = 12
        layer = EntitiesLayer([player, corpse])

        awareness = _peaceful(layer, player)
        looted = next((n for n in awareness.nearby if n.id == "goblin_corpse"), None)
        assert looted is not None
        assert looted.lootable is True
        assert looted.loot_gold == 12
        assert [i.name for i in looted.loot_items] == ["Longsword"]

    def test_open_container_appears_as_lootable(self) -> None:
        player = _player()
        chest = Container(
            id="chest_1",
            name="Chest",
            location_id=CAVE,
            inventory=[Item(id="potion_0", name="Health Potion", item_type=ItemType.POTION)],
            gold=0,
        )
        layer = EntitiesLayer([player, chest])

        awareness = _peaceful(layer, player)
        looted = next((n for n in awareness.nearby if n.id == "chest_1"), None)
        assert looted is not None
        assert looted.lootable is True
        assert [i.name for i in looted.loot_items] == ["Health Potion"]

    def test_living_creature_not_marked_lootable(self) -> None:
        player = _player()
        goblin = Creature(id="goblin_live", name="Goblin", location_id=CAVE, max_hp=10, current_hp=10)
        goblin.inventory = [Item(id="sword_0", name="Longsword", item_type=ItemType.WEAPON)]
        layer = EntitiesLayer([player, goblin])

        awareness = _peaceful(layer, player)
        living = next((n for n in awareness.nearby if n.id == "goblin_live"), None)
        assert living is not None
        assert living.lootable is False
        assert living.loot_items == []

    def test_closed_container_not_lootable(self) -> None:
        player = _player()
        chest = Container(id="chest_1", name="Chest", location_id=CAVE, is_open=False)
        layer = EntitiesLayer([player, chest])

        awareness = _peaceful(layer, player)
        looted = next((n for n in awareness.nearby if n.id == "chest_1"), None)
        # Closed container is inactive-equivalent: not lootable, so not surfaced as loot.
        assert looted is None or looted.lootable is False
