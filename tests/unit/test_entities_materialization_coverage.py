"""Coverage for coreless lair treasuries and combat-delayed dematerialization."""

import random

import pytest

from dnd_simulator.core.character import AbilityScores, Creature
from dnd_simulator.core.container import Container
from dnd_simulator.core.events import LairDematerializedPayload
from dnd_simulator.core.lair import LairState
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.core.queries import LairInfo
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.materialization import (
    materialize_lair,
    sync_lair_treasury,
    update_lair_materialization,
)


@pytest.fixture
def layer() -> EntitiesLayer:
    template = MonsterTemplate(
        id="orc",
        name="Orc",
        hp=15,
        ac=13,
        speed=30,
        ability_scores=AbilityScores(),
        attacks=(),
        cr=0.5,
        faction_id="orcs",
    )
    return EntitiesLayer(monster_templates={"orc": template}, seed=0, dice_rng=random.Random(0))


def _make_lair_info(*, has_core: bool = False) -> LairInfo:
    return LairInfo(
        id="orc_cave",
        name="Orc Cave",
        faction_id="orcs",
        location_id="cave",
        members=("orc",),
        core="orc" if has_core else None,
        state=LairState.ACTIVE,
        has_core=has_core,
        core_alive=has_core,
        treasure_items=(),
        treasure_gold=25,
        treasure_behind_core=True,
    )


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


@pytest.mark.parametrize("materialized", [False, True])
def test_coreless_treasury_is_open(layer: EntitiesLayer, materialized: bool) -> None:
    info = _make_lair_info()
    if materialized:
        materialize_lair(layer._activation, info.id, info)

    sync_lair_treasury(layer._activation, info.id, info)

    treasury = layer.get_entity(f"{info.id}_treasury")
    assert isinstance(treasury, Container)
    assert treasury.is_open
    assert treasury.gold == 25
    assert treasury.location_id == info.location_id
    assert not treasury.temporary


@pytest.mark.parametrize("fighting_role", ["core", "member"])
def test_lair_dematerialization_waits_for_combat_to_end(layer: EntitiesLayer, fighting_role: str) -> None:
    info = _make_lair_info(has_core=True)
    mgr = layer._activation
    materialize_lair(mgr, info.id, info)
    roster = mgr.materialization_state().lairs[info.id]
    creature_ids = roster.creature_ids
    fighting_id = roster.core_creature_id if fighting_role == "core" else creature_ids[-1]
    assert fighting_id is not None
    fighter = layer.get_entity(fighting_id)
    assert isinstance(fighter, Creature)
    fighter.in_combat = True
    events: list[Event] = []

    def emit(event: Event) -> ActionResult:
        events.append(event)
        return ActionResult()

    update_lair_materialization(mgr, 60, set(), _noop_query_fn, emit)

    assert mgr.materialization_state().lairs[info.id] == roster
    assert all(isinstance(layer.get_entity(cid), Creature) for cid in creature_ids)
    assert events == []

    fighter.in_combat = False
    update_lair_materialization(mgr, 120, set(), _noop_query_fn, emit)

    assert info.id not in mgr.materialization_state().lairs
    assert all(layer.get_entity(cid) is None for cid in creature_ids)
    assert len(events) == 1
    assert events[0].event_type is EventType.LAIR_DEMATERIALIZED
    assert events[0].source_layer == "entities"
    assert events[0].data == LairDematerializedPayload(info.id, True, ("orc",), 120)
