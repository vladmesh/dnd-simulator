"""NPC flee rejection and fallback behaviour when a home is unavailable."""

from __future__ import annotations

import random

import pytest

from dnd_simulator.core.action import Action, ActionRejectedError, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.intent import TravelIntent
from dnd_simulator.core.lair import LairMemberRole, LairOrigin
from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.world import World
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc, NpcActivity, ScheduleEntry
from dnd_simulator.rules.flee import flee_destinations
from dnd_simulator.rules.handlers.combat import _npc_home, handle_flee
from dnd_simulator.rules.validation import ActionContext


@pytest.fixture
def flee_graph() -> LocationGraph:
    return LocationGraph(
        [
            Location("arena", "Arena", "r1", edges=(LocationEdge("road", 1000), LocationEdge("ridge", 2000))),
            Location("road", "Road", "r1", edges=(LocationEdge("arena", 1000),)),
            Location("ridge", "Ridge", "r1", edges=(LocationEdge("arena", 2000),)),
            Location("isolated", "Isolated Home", "r1"),
        ]
    )


def test_npc_cannot_flee_without_an_exit() -> None:
    actor = Creature(id="fleeing", name="Fleeing", location_id="arena", in_combat=True)
    entities = EntitiesLayer(entities=[actor], seed=7, dice_rng=random.Random(7))
    world = World(layers=[entities], location_graph=LocationGraph([Location("arena", "Arena", "r1")]))

    with pytest.raises(ActionRejectedError, match=r"^There is nowhere to flee$"):
        handle_flee(
            actor, Action(name=ActionType.FLEE), world.make_emit_fn("entities"), ActionContext(is_combat=True), world
        )

    assert actor.current_intent is None
    assert actor.in_combat is True
    assert entities.get_entity(actor.id) is actor


@pytest.mark.parametrize("register_entities", [False, True], ids=["no-entities-layer", "no-ecology-layer"])
def test_npc_has_no_home_when_ecology_is_unavailable(flee_graph: LocationGraph, register_entities: bool) -> None:
    actor = Creature(id="fleeing", name="Fleeing", location_id="arena", squad_id="missing")
    entities = EntitiesLayer(entities=[actor], seed=7, dice_rng=random.Random(7))
    world = World(layers=[entities] if register_entities else [], location_graph=flee_graph)

    assert _npc_home(actor, flee_destinations(flee_graph, actor.location_id), world) is None


@pytest.mark.parametrize("origin", ["squad", "lair"])
def test_npc_has_no_home_when_its_roster_is_gone(flee_graph: LocationGraph, origin: str) -> None:
    actor = Creature(id="fleeing", name="Fleeing", location_id="arena")
    if origin == "squad":
        actor.squad_id = "missing"
    else:
        actor.lair_origin = LairOrigin(lair_id="missing", template_id="wolf", role=LairMemberRole.MEMBER)
    entities = EntitiesLayer(entities=[actor], seed=7, dice_rng=random.Random(7))
    world = World(
        layers=[EcologyLayer(location_graph=flee_graph, seed=7), entities],
        location_graph=flee_graph,
    )

    assert _npc_home(actor, flee_destinations(flee_graph, actor.location_id), world) is None


@pytest.mark.parametrize(
    ("home", "expected_destination"),
    [("isolated", "ridge"), ("missing", "ridge"), ("road", "road")],
    ids=["disconnected-home", "unknown-home", "reachable-home-takes-priority"],
)
def test_npc_flees_away_from_enemies_unless_it_can_head_home(
    flee_graph: LocationGraph, home: str, expected_destination: str
) -> None:
    actor = Npc(
        id="fleeing",
        name="Fleeing",
        location_id="arena",
        faction_id="vale",
        in_combat=True,
        schedule=[ScheduleEntry(8, 20, NpcActivity.WORKING, home)],
    )
    enemy = Creature(id="enemy", name="Enemy", location_id="arena", faction_id="bandits")
    patrol = Creature(id="patrol", name="Patrol", location_id="road", faction_id="bandits")
    entities = EntitiesLayer(entities=[actor, enemy, patrol], seed=7, dice_rng=random.Random(7))
    world = World(layers=[entities], location_graph=flee_graph, time=GameDateTime(hour=12))
    ctx = ActionContext(
        is_combat=True,
        combat_state=CombatState(location_id="arena", turn_order=[actor.id, enemy.id]),
        get_entity=entities.get_entity,
    )

    result = handle_flee(
        actor,
        Action(name=ActionType.FLEE, params={"destination_id": "isolated"}),
        world.make_emit_fn("entities"),
        ctx,
        world,
    )

    assert result.success is True
    assert actor.current_intent == TravelIntent(
        started_at_seconds=world.time.to_total_seconds(),
        destination_id=expected_destination,
        remaining_route=(expected_destination,),
        next_arrival_seconds=world.time.to_total_seconds() + flee_graph.travel_seconds("arena", expected_destination),
        fleeing=True,
    )
    assert actor.location_id == "arena"
    assert actor.location_override == expected_destination
    assert actor.active is False
    assert actor.in_combat is False
