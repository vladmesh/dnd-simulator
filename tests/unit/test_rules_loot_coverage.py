"""Coverage for lootability of ordinary world entities."""

from dnd_simulator.core.character import Entity
from dnd_simulator.rules.loot import is_lootable


def test_non_creature_non_container_is_not_lootable() -> None:
    entity = Entity(id="statue_1", name="Statue", location_id="cave")

    assert is_lootable(entity) is False
