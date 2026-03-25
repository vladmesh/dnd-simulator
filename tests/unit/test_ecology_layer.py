"""Tests for EcologyLayer — squad ownership, queries, serialization, world integration."""

from __future__ import annotations

from dnd_simulator.core.models import GameDateTime, Query, QueryType, TimeDelta
from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType
from dnd_simulator.layers.ecology.layer import EcologyLayer


def _make_squad(
    squad_id: str = "patrol_1",
    location: str = "road_north",
    faction: str = "kingdom",
    strength: int = 5,
    behavior: SquadBehavior = SquadBehavior.PATROL,
) -> Squad:
    return Squad(
        id=squad_id,
        name=f"Squad {squad_id}",
        faction_id=faction,
        squad_type=SquadType.PATROL,
        behavior=behavior,
        current_location_id=location,
        route=["road_north", "road_south"],
        territory=["road_north", "road_south"],
        strength=strength,
        max_strength=strength,
        member_templates=["bandit", "bandit"],
        tick_interval=3600,
    )


class TestEcologyLayerQueries:
    """EcologyLayer initializes with squads and exposes them via query."""

    def test_squads_at_location_returns_matching_squads(self) -> None:
        squad_a = _make_squad("patrol_1", location="road_north")
        squad_b = _make_squad("wolves_1", location="forest_edge")
        layer = EcologyLayer(squads=[squad_a, squad_b])

        answer = layer.query(Query(QueryType.SQUADS_AT_LOCATION, params={"location_id": "road_north"}))
        squads = answer.value
        assert isinstance(squads, list)
        assert len(squads) == 1
        assert squads[0]["id"] == "patrol_1"
        assert squads[0]["faction_id"] == "kingdom"
        assert squads[0]["strength"] == 5

    def test_squads_at_location_empty_for_no_squads(self) -> None:
        squad = _make_squad("patrol_1", location="road_north")
        layer = EcologyLayer(squads=[squad])

        answer = layer.query(Query(QueryType.SQUADS_AT_LOCATION, params={"location_id": "forest_edge"}))
        assert answer.value == []

    def test_squad_info_returns_squad_details(self) -> None:
        squad = _make_squad("patrol_1", location="road_north", strength=7)
        layer = EcologyLayer(squads=[squad])

        answer = layer.query(Query(QueryType.SQUAD_INFO, params={"squad_id": "patrol_1"}))
        info = answer.value
        assert isinstance(info, dict)
        assert info["id"] == "patrol_1"
        assert info["current_location_id"] == "road_north"
        assert info["strength"] == 7
        assert info["member_templates"] == ["bandit", "bandit"]

    def test_squad_info_raises_for_unknown_squad(self) -> None:
        layer = EcologyLayer(squads=[])
        import pytest

        with pytest.raises(KeyError):
            layer.query(Query(QueryType.SQUAD_INFO, params={"squad_id": "nonexistent"}))

    def test_multiple_squads_at_same_location(self) -> None:
        squad_a = _make_squad("patrol_1", location="crossroads")
        squad_b = _make_squad("wolves_1", location="crossroads")
        layer = EcologyLayer(squads=[squad_a, squad_b])

        answer = layer.query(Query(QueryType.SQUADS_AT_LOCATION, params={"location_id": "crossroads"}))
        assert len(answer.value) == 2
        ids = {s["id"] for s in answer.value}
        assert ids == {"patrol_1", "wolves_1"}


class TestEcologyLayerSerialization:
    """EcologyLayer serializes and restores squad state (mutable fields)."""

    def test_get_state_captures_location_and_strength(self) -> None:
        squad = _make_squad("patrol_1", location="road_north", strength=5)
        layer = EcologyLayer(squads=[squad])

        state = layer.get_state()
        assert "squads" in state
        squads_state = state["squads"]
        assert isinstance(squads_state, dict)
        assert "patrol_1" in squads_state
        assert squads_state["patrol_1"]["current_location_id"] == "road_north"
        assert squads_state["patrol_1"]["strength"] == 5

    def test_load_state_restores_mutable_fields(self) -> None:
        squad = _make_squad("patrol_1", location="road_north", strength=5)
        layer = EcologyLayer(squads=[squad])

        # Save original state
        saved = layer.get_state()

        # Mutate
        squad.current_location_id = "road_south"
        squad.strength = 2

        # Verify mutation happened
        answer = layer.query(Query(QueryType.SQUAD_INFO, params={"squad_id": "patrol_1"}))
        assert answer.value["current_location_id"] == "road_south"
        assert answer.value["strength"] == 2

        # Restore
        layer.load_state(saved)

        # Verify restoration
        answer = layer.query(Query(QueryType.SQUAD_INFO, params={"squad_id": "patrol_1"}))
        assert answer.value["current_location_id"] == "road_north"
        assert answer.value["strength"] == 5


class TestEcologyLayerWorldIntegration:
    """EcologyLayer integrates into the World layer stack."""

    def test_ecology_layer_ticks_with_world(self) -> None:
        """EcologyLayer participates in World.advance_time()."""
        from dnd_simulator.core.world import World

        layer = EcologyLayer(squads=[_make_squad()])
        world = World(
            layers=[layer],
            time=GameDateTime(year=1, month=1, day=1, hour=0),
        )

        # Tick interval is 3600 (1 hour). Advance 1 hour — layer should tick.
        events = world.advance_time(TimeDelta(seconds=3600))
        # No events from no-op tick, but no error either
        assert isinstance(events, list)

    def test_entities_layer_can_query_ecology_via_world(self) -> None:
        """EntitiesLayer (above ecology) can query squad data through query_fn."""
        from dnd_simulator.core.world import World
        from dnd_simulator.layers.entities.layer import EntitiesLayer

        squad = _make_squad("patrol_1", location="road_north")
        ecology = EcologyLayer(squads=[squad])
        entities = EntitiesLayer()

        # ecology at index 0, entities at index 1 — entities can query ecology (below)
        world = World(
            layers=[ecology, entities],
            time=GameDateTime(year=1, month=1, day=1, hour=0),
        )

        # Query via world to verify layer integration
        answer = world.query_layer("ecology", Query(QueryType.SQUADS_AT_LOCATION, params={"location_id": "road_north"}))
        assert len(answer.value) == 1
        assert answer.value[0]["id"] == "patrol_1"

    def test_ecology_layer_name_is_ecology(self) -> None:
        layer = EcologyLayer(squads=[])
        assert layer.name == "ecology"

    def test_ecology_layer_tick_interval_is_3600(self) -> None:
        layer = EcologyLayer(squads=[])
        assert layer.tick_interval == 3600
