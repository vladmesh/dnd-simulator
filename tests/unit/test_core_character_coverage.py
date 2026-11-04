"""Coverage for base-character metadata and non-character perception."""

import pytest

from dnd_simulator.core.character import Character, Entity


def test_base_character_has_no_npc_metadata() -> None:
    character = Character(id="c1", name="Hero", location_id="arena")

    assert character.get_npc_data() == {}


@pytest.mark.parametrize("name", ["Treasure chest", ""])
def test_perceive_non_character_returns_its_name(name: str) -> None:
    character = Character(id="c1", name="Hero", location_id="arena")
    target = Entity(id="chest", name=name, location_id="arena")

    assert character.perceive(target) == name
