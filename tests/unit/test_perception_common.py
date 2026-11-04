"""Tests for the shared subjective entity description helper (``perception_common.describe``)."""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from dnd_simulator.core.character import Character, Creature, Entity, Race
from dnd_simulator.i18n import current_lang, set_language
from dnd_simulator.layers.entities.perception_common import GetEntityFn, describe


@pytest.fixture(autouse=True)
def _english() -> Iterator[None]:
    previous = current_lang.get()
    set_language("en")
    yield
    set_language(previous)


def _lookup(*entities: Entity) -> GetEntityFn:
    by_id = {e.id: e for e in entities}
    return by_id.get


def test_unknown_entity_is_someone() -> None:
    observer = Character(id="guard", name="Guard", location_id="r1")
    assert describe(observer, "ghost", _lookup(observer)) == "someone"


def test_observer_itself_is_you() -> None:
    observer = Character(id="guard", name="Guard", location_id="r1")
    assert describe(observer, "guard", _lookup(observer)) == "you"


def test_character_observer_uses_perceive_for_stranger() -> None:
    observer = Character(id="guard", name="Guard", location_id="r1")
    stranger = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF, appearance="soot-stained")
    result = describe(observer, "smith", _lookup(observer, stranger))
    assert result == observer.perceive(stranger)
    assert "Smith" not in result
    assert "dwarf" in result


def test_character_observer_names_non_character() -> None:
    observer = Character(id="guard", name="Guard", location_id="r1")
    wolf = Creature(id="wolf", name="Wolf", location_id="r1")
    assert describe(observer, "wolf", _lookup(observer, wolf)) == "Wolf"


def test_non_character_observer_uses_raw_name() -> None:
    observer = Creature(id="wolf", name="Wolf", location_id="r1")
    target = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
    assert describe(observer, "smith", _lookup(observer, target)) == "Smith"
