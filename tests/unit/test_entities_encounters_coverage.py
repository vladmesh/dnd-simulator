"""Encounter suppression, missing-layer fallbacks, and factionless arrivals."""

import random

import pytest

from dnd_simulator.core.character import AbilityScores, Creature
from dnd_simulator.core.events import EncounterSpawnedPayload
from dnd_simulator.core.lair import Lair, LairState
from dnd_simulator.core.models import Answer, EventType, FactionRelation, GameDateTime, Query, QueryType, TimeOfDay
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate
from dnd_simulator.core.world import World
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.encounters import check_encounters, maybe_start_combat
from dnd_simulator.layers.entities.layer import EntitiesLayer

_TIME = GameDateTime(year=1490, month=6, day=1, hour=12)


def _encounter_layer(*creatures: Creature, time_of_day: TimeOfDay = TimeOfDay.DAY) -> EntitiesLayer:
    template = MonsterTemplate(
        id="wolf",
        name="Wolf",
        hp=11,
        ac=13,
        speed=40,
        ability_scores=AbilityScores(),
        attacks=(),
        cr=0.25,
        faction_id="wild_beasts",
    )
    return EntitiesLayer(
        list(creatures),
        monster_templates={"wolf": template},
        encounter_tables={
            "forest": [EncounterEntry("wolf", chance=1.0, count_min=1, count_max=1, time_of_day=time_of_day)]
        },
        seed=0,
        dice_rng=random.Random(0),
    )


@pytest.mark.parametrize("state", [LairState.ACTIVE, LairState.DEPLETED])
def test_only_active_lair_suppresses_arrival_encounter(state: LairState) -> None:
    traveler = Creature(id="traveler", name="Traveler", location_id="forest")
    layer = _encounter_layer(traveler)
    lair = Lair(
        id="den",
        name="Wolf Den",
        faction_id="wild_beasts",
        location_id="forest",
        members=["wolf"],
        state=state,
    )
    world = World([EcologyLayer(lairs=[lair]), layer], time=_TIME, seed=0)

    check_encounters(layer._activation, _TIME, {traveler.id}, world.make_query_fn("entities"))

    assert layer._creature_locations == {traveler.id: "forest"}
    if state is LairState.ACTIVE:
        assert layer.get_entity("wolf_1") is None
        assert layer._encounter_cooldowns == {}
        assert layer._location_log.get("forest", []) == []
    else:
        assert isinstance(layer.get_entity("wolf_1"), Creature)
        assert layer._encounter_cooldowns == {"forest": _TIME.to_total_seconds()}
        assert [event.event_type for event in layer._location_log["forest"]] == [EventType.ENCOUNTER_SPAWNED]


@pytest.mark.parametrize("time_of_day", [TimeOfDay.DAY, TimeOfDay.NIGHT])
def test_missing_ecology_and_geography_allow_daytime_encounters(time_of_day: TimeOfDay) -> None:
    traveler = Creature(id="traveler", name="Traveler", location_id="forest")
    layer = _encounter_layer(traveler, time_of_day=time_of_day)
    world = World([layer], time=_TIME, seed=0)

    check_encounters(layer._activation, _TIME, {traveler.id}, world.make_query_fn("entities"))

    assert layer._encounter_cooldowns == {"forest": _TIME.to_total_seconds()}
    spawned = layer.get_entity("wolf_1")
    if time_of_day is TimeOfDay.DAY:
        assert isinstance(spawned, Creature)
        assert spawned.location_id == "forest"
        assert spawned.active is True
        assert spawned.temporary is True
        events = layer._location_log["forest"]
        assert len(events) == 1
        assert events[0].event_type is EventType.ENCOUNTER_SPAWNED
        assert events[0].data == EncounterSpawnedPayload(
            location_id="forest", spawned_names=("Wolf",), spawned_entity_ids=("wolf_1",)
        )
    else:
        assert spawned is None
        assert layer._location_log.get("forest", []) == []
    assert layer.get_combat_locations() == []


def _hostile_query(layer: str, query: Query) -> Answer:
    assert layer == "politics"
    assert query.question is QueryType.FACTION_RELATION
    return Answer(value=FactionRelation.HOSTILE)


@pytest.mark.parametrize(
    ("spawned_faction", "existing_faction", "starts_combat"),
    [("", "townsfolk", False), ("wild_beasts", "", False), ("wild_beasts", "townsfolk", True)],
)
def test_auto_combat_requires_factions_on_both_creatures(
    spawned_faction: str, existing_faction: str, starts_combat: bool
) -> None:
    traveler = Creature(id="traveler", name="Traveler", location_id="forest", faction_id=existing_faction)
    spawned = Creature(id="wolf_1", name="Wolf", location_id="forest", faction_id=spawned_faction, temporary=True)
    layer = _encounter_layer(traveler, spawned)

    maybe_start_combat(layer._activation, "forest", [spawned], _hostile_query)

    assert layer.get_combat_locations() == (["forest"] if starts_combat else [])
    assert traveler.in_combat is starts_combat
    assert spawned.in_combat is starts_combat
    events = layer._location_log.get("forest", [])
    assert [event.event_type for event in events] == ([EventType.COMBAT_STARTED] if starts_combat else [])
