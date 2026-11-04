"""Entity query accessor coverage through a real entities layer."""

import random

import pytest

from dnd_simulator.core.character import Character
from dnd_simulator.core.models import Answer, EntityKind, Query, QueryFn
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.queries import query_all_creatures, query_player
from dnd_simulator.layers.entities.layer import EntitiesLayer


@pytest.fixture
def entities_query() -> QueryFn:
    layer = EntitiesLayer(
        entities=[
            PlayerCharacter(id="hero", name="Hero", location_id="village", active=True),
            PlayerCharacter(id="resting_hero", name="Resting Hero", location_id="village", active=False),
            PlayerCharacter(id="traveler", name="Traveler", location_id="road", active=True),
            Character(id="wolf", name="Wolf", location_id="village", active=True),
            Character(id="sleeping_wolf", name="Sleeping Wolf", location_id="village", active=False),
        ],
        seed=0,
        dice_rng=random.Random(0),
    )
    by_name = {layer.name: layer}

    def query_fn(layer_name: str, query: Query) -> Answer:
        return by_name[layer_name].query(query)

    return query_fn


@pytest.mark.parametrize("player_id", ["missing", "wolf"])
def test_query_player_returns_none_for_missing_or_non_player(entities_query: QueryFn, player_id: str) -> None:
    assert query_player(entities_query, player_id) is None


def test_query_player_returns_the_requested_player(entities_query: QueryFn) -> None:
    player = query_player(entities_query, "resting_hero")

    assert isinstance(player, PlayerCharacter)
    assert player.id == "resting_hero"
    assert player.active is False


@pytest.mark.parametrize(
    ("entity_type", "location_id", "active", "expected_ids"),
    [
        (None, None, None, ["hero", "resting_hero", "traveler", "wolf", "sleeping_wolf"]),
        (EntityKind.PLAYER, None, None, ["hero", "resting_hero", "traveler"]),
        (EntityKind.MONSTER, None, None, ["wolf", "sleeping_wolf"]),
        (None, "village", None, ["hero", "resting_hero", "wolf", "sleeping_wolf"]),
        (None, None, True, ["hero", "traveler", "wolf"]),
        (None, None, False, ["resting_hero", "sleeping_wolf"]),
        (EntityKind.PLAYER, "village", False, ["resting_hero"]),
        (EntityKind.PLAYER, "missing", None, []),
    ],
)
def test_query_all_creatures_applies_optional_filters(
    entities_query: QueryFn,
    entity_type: EntityKind | None,
    location_id: str | None,
    active: bool | None,
    expected_ids: list[str],
) -> None:
    creatures = query_all_creatures(
        entities_query,
        entity_type=entity_type,
        location_id=location_id,
        active=active,
    )

    assert [creature["id"] for creature in creatures] == expected_ids
