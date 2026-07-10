"""Save-state model contracts for simple simulation layers."""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest
from pydantic import ValidationError

from dnd_simulator.core.lair import Lair, LairState
from dnd_simulator.core.models import ActionResult, Answer, GameDateTime, Query, QueryType, TimeDelta
from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Connection, Direction, Region, TerrainType, WeatherCondition
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.politics.models import DiplomaticStatus, FactionRelation, Leader, LeaderTrait, Nation
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.layers.settlements.models import Settlement, SettlementType


def _noop_query_fn(layer: str, query: Query) -> Answer:
    raise RuntimeError(f"Unexpected query: {layer}/{query.question}")


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _geography() -> GeographyLayer:
    return GeographyLayer(
        regions=[
            Region(
                id="north",
                name="North",
                latitude=52.0,
                longitude=24.0,
                elevation=180.0,
                terrain=TerrainType.FOREST,
                water_proximity=0.4,
                connections=[Connection(target_id="south", direction=Direction.S)],
                weather=WeatherCondition.CLOUDY,
                temperature=8.5,
            )
        ],
        weather_seed=17,
    )


def _politics() -> PoliticsLayer:
    layer = PoliticsLayer(
        nations=[
            Nation(
                id="a",
                name="A",
                regions=["ra"],
                wealth=70.0,
                military=62.0,
                stability=51.0,
                leader=Leader(name="Ada", age=44, trait=LeaderTrait.DIPLOMAT),
            ),
            Nation(
                id="b",
                name="B",
                regions=["rb"],
                wealth=45.0,
                military=80.0,
                stability=48.0,
                leader=Leader(name="Bryn", age=39, trait=LeaderTrait.MILITARIST),
            ),
        ],
        region_adjacency={"ra": ["rb"], "rb": ["ra"]},
        seed=23,
        faction_relations={("goblins", "guards"): FactionRelation.HOSTILE},
        faction_names={"guards": "Town Guard"},
    )
    layer.set_relation("a", "b", DiplomaticStatus.WAR)
    layer._war_durations[("a", "b")] = 7
    return layer


def _settlements() -> SettlementsLayer:
    return SettlementsLayer(
        settlements=[
            Settlement(
                id="town",
                name="Town",
                region_id="ra",
                type=SettlementType.TOWN,
                population=900,
                prosperity=41.0,
                defenses=25.0,
            )
        ]
    )


def _ecology() -> EcologyLayer:
    squad = Squad(
        id="wolves",
        name="Wolves",
        faction_id="wild",
        squad_type=SquadType.MONSTER_PACK,
        behavior=SquadBehavior.ROAM,
        current_location_id="den",
        route=[],
        territory=["den", "woods"],
        strength=4,
        max_strength=6,
        member_templates=["wolf"],
        tick_interval=3600,
    )
    lair = Lair(
        id="den",
        name="Den",
        faction_id="wild",
        location_id="den",
        members=["wolf", "wolf"],
        state=LairState.ACTIVE,
        alive_members=["wolf"],
        core_alive=False,
        last_respawn_time=12,
    )
    layer = EcologyLayer(squads=[squad], lairs=[lair], seed=31)
    layer._last_move_time["wolves"] = 3600
    layer._route_index["wolves"] = 1
    layer._route_direction["wolves"] = -1
    return layer


@pytest.mark.parametrize(
    ("layer_factory", "required_key"),
    [
        (_geography, "rng_state"),
        (_politics, "rng_state"),
        (_settlements, None),
        (_ecology, "rng_state"),
    ],
)
def test_simple_layer_state_round_trips_through_json(
    layer_factory: Callable[[], object], required_key: str | None
) -> None:
    layer = layer_factory()
    state = layer.get_state()
    if required_key is not None:
        assert required_key in state

    json_state = json.loads(json.dumps(state))
    restored = layer_factory()
    restored.load_state(json_state)

    assert restored.get_state() == state


def test_geography_rng_continues_after_load() -> None:
    original = _geography()
    time = GameDateTime(year=1490, month=3, day=1, hour=6)
    original.tick(TimeDelta.from_hours(6), time, _noop_query_fn, _noop_emit_fn)
    saved = json.loads(json.dumps(original.get_state()))

    expected = original._weather._rng.random()

    restored = _geography()
    restored.load_state(saved)

    assert restored._weather._rng.random() == expected


def test_politics_relations_war_durations_and_rng_round_trip() -> None:
    original = _politics()
    _ = original._rng.random()
    saved = json.loads(json.dumps(original.get_state()))

    expected = original._rng.random()
    restored = PoliticsLayer(region_adjacency={"ra": ["rb"], "rb": ["ra"]})
    restored.load_state(saved)

    assert restored.get_relation("b", "a") is DiplomaticStatus.WAR
    assert restored._war_durations[("a", "b")] == 7
    assert restored.get_faction_relation("guards", "goblins") is FactionRelation.HOSTILE
    assert restored.query(Query(question=QueryType.FACTION_NAME, params={"faction_id": "guards"})).value == "Town Guard"
    assert restored._rng.random() == expected


def test_ecology_rng_continues_after_load() -> None:
    original = _ecology()
    _ = original._rng.choice(["a", "b", "c"])
    saved = json.loads(json.dumps(original.get_state()))
    expected = original._rng.random()

    restored = _ecology()
    restored.load_state(saved)

    assert restored._rng.random() == expected


@pytest.mark.parametrize(
    ("layer", "state"),
    [
        (_geography(), {"regions": {"north": {"id": "north", "terrain": 123}}, "rng_state": []}),
        (_politics(), {"nations": {"a": {"id": "a", "name": "A", "regions": "bad"}}, "rng_state": []}),
        (_settlements(), {"settlements": {"town": {"id": "town", "name": "Town", "region_id": "ra"}}}),
        (_ecology(), {"squads": {"wolves": {"strength": "bad"}}, "rng_state": []}),
    ],
)
def test_invalid_simple_layer_state_raises_validation_error(layer: object, state: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        layer.load_state(state)
