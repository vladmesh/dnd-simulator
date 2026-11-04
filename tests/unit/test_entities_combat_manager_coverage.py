"""Coverage for combat-manager side joining, membership queries, and action delegation."""

from __future__ import annotations

import random
from collections import defaultdict

import pytest

from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import Position
from dnd_simulator.core.events import EntityMovePayload
from dnd_simulator.core.models import Answer, Event, EventType, FactionRelation, Query, QueryType
from dnd_simulator.layers.entities.combat_manager import CombatManager


def _creature(creature_id: str, faction_id: str = "") -> Creature:
    return Creature(
        id=creature_id,
        name=creature_id,
        location_id="arena",
        max_hp=10,
        current_hp=10,
        ac=10,
        speed=30,
        faction_id=faction_id,
    )


def _manager(*creatures: Creature) -> CombatManager:
    return CombatManager(
        {creature.id: creature for creature in creatures},
        defaultdict(list),
        rng=random.Random(0),
    )


@pytest.mark.parametrize("relation", [FactionRelation.FRIENDLY, FactionRelation.NEUTRAL, FactionRelation.HOSTILE])
def test_join_combat_assigns_side_from_mutual_relations(relation: FactionRelation) -> None:
    hero = _creature("hero", "guild")
    enemy = _creature("enemy", "raiders")
    newcomer = _creature("newcomer", "visitors")
    newcomer.location_id = "waiting"
    newcomer.combat_position = (0, 0)
    hero.combat_position = (5, 5)
    enemy.combat_position = (15, 15)

    def query_fn(layer: str, query: Query) -> Answer:
        assert query.question is QueryType.FACTION_RELATION
        factions = {query.params["a"], query.params["b"]}
        return Answer(value=relation if factions == {"guild", "visitors"} else FactionRelation.HOSTILE)

    manager = _manager(hero, enemy, newcomer)
    combat = manager.start_combat("arena", query_fn)
    assert combat is not None
    original_order = list(combat.turn_order)
    newcomer.location_id = "arena"

    manager.join_combat("arena", newcomer, query_fn)

    assert combat.turn_order == [*original_order, "newcomer"]
    assert combat.battle_map.get_position("newcomer") == Position(0, 0)
    hero_side = combat.entity_to_side["hero"]
    newcomer_side = combat.entity_to_side["newcomer"]
    assert combat.entity_to_side["enemy"] != newcomer_side
    if relation is FactionRelation.FRIENDLY:
        assert newcomer_side == hero_side
        assert combat.sides[hero_side] == {"hero", "newcomer"}
    else:
        assert newcomer_side != hero_side
        assert combat.sides[newcomer_side] == {"newcomer"}
    assert newcomer.in_combat is True
    assert manager.get_active_combat_for("newcomer") is combat
    assert manager.scene_outsiders("arena") == []


def test_scene_outsiders_is_empty_before_combat_and_after_it_ends() -> None:
    hero = _creature("hero", "guild")
    enemy = _creature("enemy", "raiders")
    manager = _manager(hero, enemy)

    assert manager.scene_outsiders("arena") == []
    assert manager.start_combat("arena") is not None
    manager.remove_from_combat("arena", "enemy")

    assert manager.get_combat("arena") is None
    assert hero.in_combat is False
    assert enemy.in_combat is False
    assert manager.scene_outsiders("arena") == []


@pytest.mark.parametrize(
    ("hero_faction", "other_faction", "continues"),
    [
        ("", "guild", True),
        ("guild", "", True),
        ("", "", True),
        ("guild", "raiders", True),
        ("guild", "guild", False),
    ],
)
def test_removal_without_sides_keeps_potentially_hostile_creatures_in_combat(
    hero_faction: str, other_faction: str, continues: bool
) -> None:
    hero = _creature("hero", hero_faction)
    other = _creature("other", other_faction)
    departing = _creature("departing", "outsiders")
    manager = _manager(hero, other, departing)
    combat = manager.start_combat("arena")
    assert combat is not None

    manager.remove_from_combat("arena", "departing")

    assert set(combat.turn_order) == {"hero", "other"}
    assert combat.battle_map.get_position("departing") is None
    if continues:
        assert manager.get_combat("arena") is combat
        assert hero.in_combat is True
        assert other.in_combat is True
    else:
        assert manager.get_combat("arena") is None
        assert hero.in_combat is False
        assert other.in_combat is False
        assert set(manager.consume_last_ended_participants("arena")) == {"hero", "other", "departing"}


@pytest.mark.parametrize(
    ("direction", "destination", "success"),
    [("north", Position(5, 10), True), ("east", Position(5, 5), False)],
)
def test_resolve_move_updates_position_and_records_only_successful_moves(
    direction: str, destination: Position, success: bool
) -> None:
    hero = _creature("hero", "guild")
    enemy = _creature("enemy", "raiders")
    hero.combat_position = (5, 5)
    enemy.combat_position = (10, 5)
    location_log: dict[str, list[Event]] = defaultdict(list)
    manager = CombatManager({hero.id: hero, enemy.id: enemy}, location_log, rng=random.Random(0))
    combat = manager.start_combat("arena")
    assert combat is not None
    event = Event(
        event_type=EventType.ENTITY_MOVE,
        source_layer="entities",
        data=EntityMovePayload("hero", "arena", direction=direction, ft=5),
    )

    result = manager.resolve_move(event)

    assert result.success is success
    assert combat.battle_map.get_position("hero") == destination
    assert combat.battle_map.get_position("enemy") == Position(10, 5)
    move_events = [event for event in location_log["arena"] if event.event_type is EventType.ENTITY_MOVE]
    if success:
        assert len(move_events) == 1
        assert move_events[0].payload == EntityMovePayload(
            entity_id="hero",
            location_id="arena",
            from_x=5,
            from_y=5,
            to_x=5,
            to_y=10,
            distance_ft=5,
        )
    else:
        assert result.error == "Cannot move there — blocked."
        assert move_events == []
