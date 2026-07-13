"""Event-driven creature activation through the live World event flow."""

from __future__ import annotations

import random

import pytest

from dnd_simulator.content_loader import parse_npc
from dnd_simulator.core.character import Ability, AbilityScores, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.events import (
    AttackRequestedPayload,
    EntityDiedPayload,
    PeaceDeclaredPayload,
    WarDeclaredPayload,
)
from dnd_simulator.core.intent import IntentType, TimedIntent, TravelIntent
from dnd_simulator.core.models import Event, EventType, GameDateTime
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.trigger_index import TriggerMatch
from dnd_simulator.layers.politics.layer import PoliticsLayer

TIME = GameDateTime(year=1490, month=6, day=1, hour=10)


def _trigger(
    trigger_id: str,
    *,
    on_event: str = "war_declared",
    on_match: dict[str, object] | None = None,
    until_event: str = "peace_declared",
    until_match: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "id": trigger_id,
        "on": {"event": on_event, "match": on_match or {}},
        "until": {"event": until_event, "match": until_match or {}},
    }


def _npc(
    npc_id: str,
    *,
    location: str = "far_keep",
    triggers: list[dict[str, object]] | None = None,
    always_active: bool = False,
) -> Creature:
    return parse_npc(
        npc_id,
        {
            "name": npc_id,
            "start_location": location,
            "always_active": always_active,
            "triggers": triggers or [],
        },
    )


def _war() -> Event:
    return Event(EventType.WAR_DECLARED, "politics", WarDeclaredPayload("north", "south"))


def _peace() -> Event:
    return Event(EventType.PEACE_DECLARED, "politics", PeaceDeclaredPayload("north", "south"))


def _war_duty(trigger_id: str = "war_duty") -> dict[str, object]:
    return _trigger(
        trigger_id,
        on_match={"aggressor_id": "north", "target_id": "south"},
        until_match={"nation_a_id": "north", "nation_b_id": "south"},
    )


def test_world_event_wakes_dormant_npc_and_until_dormifies_on_next_activation_pass() -> None:
    prince = _npc("prince", triggers=[_war_duty()])
    prince.active = False
    entities = EntitiesLayer([prince])
    world = World([entities], time=TIME)

    world.handle_event(_war())

    assert prince.active is True
    assert prince.triggers[0].active is True

    world.handle_event(_peace())

    assert prince.triggers[0].active is False
    entities.update_activation(TIME)
    assert prince.active is False


def test_on_interrupts_wait_and_travel_once_without_replaying_a_travel_leg() -> None:
    waiter = _npc("waiter", triggers=[_war_duty()])
    traveler = _npc("traveler", location="midpoint", triggers=[_war_duty()])
    now = TIME.to_total_seconds()
    waiter.current_intent = TimedIntent(IntentType.WAIT, now, now + 3600)
    traveler.current_intent = TravelIntent(now, "destination", ("destination",), now + 600)
    entities = EntitiesLayer([waiter, traveler])
    world = World([entities], time=TIME)

    world.handle_event(_war())
    world.handle_event(_war())

    assert waiter.current_intent is None
    assert traveler.current_intent is None
    assert traveler.location_id == "midpoint"
    assert waiter.active is True
    assert traveler.active is True


def test_until_only_removes_its_trigger_reason_and_never_wakes_the_dead() -> None:
    guard = _npc(
        "guard",
        triggers=[_war_duty("first"), _trigger("second", until_event="nation_destroyed")],
    )
    immortal = _npc("immortal", triggers=[_war_duty()], always_active=True)
    dead = _npc("dead", triggers=[_war_duty()])
    dead.current_hp = 0
    entities = EntitiesLayer([guard, immortal, dead])
    world = World([entities], time=TIME)

    world.handle_event(_war())
    world.handle_event(_peace())
    entities.update_activation(TIME)

    assert guard.triggers[0].active is False
    assert guard.triggers[1].active is True
    assert guard.active is True
    assert immortal.active is True
    assert dead.active is False
    assert dead.triggers[0].active is False


def test_trigger_activity_survives_activation_passes_without_creating_an_anchor_scene() -> None:
    triggered = _npc("triggered", location="remote", triggers=[_war_duty()])
    bystander = _npc("bystander", location="remote")
    anchor = _npc("anchor", location="village")
    anchor.is_anchor = True
    villager = _npc("villager", location="village")
    entities = EntitiesLayer([triggered, bystander, anchor, villager])
    world = World([entities], time=TIME)

    world.handle_event(_war())
    for _ in range(3):
        entities.update_activation(TIME)

    assert triggered.active is True
    assert bystander.active is False
    assert anchor.active is True
    assert villager.active is True


def test_entity_death_cascade_reaches_trigger_matcher_exactly_once(monkeypatch: pytest.MonkeyPatch) -> None:
    scores = AbilityScores()
    scores[Ability.STR] = 20
    attacker = Creature(
        id="hero",
        name="Hero",
        location_id="arena",
        ability_scores=scores,
        attacks=(Attack("blade", Ability.STR, (DamageComponent("1d1", DamageType.SLASHING),)),),
    )
    victim = Creature(id="victim", name="Victim", location_id="arena", max_hp=1, current_hp=1, ac=1)
    witness = _npc(
        "witness",
        triggers=[
            _trigger(
                "avenge",
                on_event="entity_died",
                on_match={"entity_id": "victim"},
                until_event="peace_declared",
            )
        ],
    )
    entities = EntitiesLayer([attacker, victim, witness], dice_rng=random.Random(1))
    politics = PoliticsLayer()
    world = World([politics, entities], time=TIME)
    original_match = entities._trigger_index.match
    matched_deaths = 0

    def count_death_matches(event: Event) -> list[TriggerMatch]:
        nonlocal matched_deaths
        if event.event_type is EventType.ENTITY_DIED:
            matched_deaths += 1
        return original_match(event)

    monkeypatch.setattr(entities._trigger_index, "match", count_death_matches)

    result = world.handle_event(
        Event(EventType.ENTITY_ATTACK_REQUESTED, "entities", AttackRequestedPayload("hero", "victim"))
    )

    assert any(isinstance(event.data, EntityDiedPayload) for event in result.events)
    assert witness.active is True
    assert witness.triggers[0].active is True
    assert matched_deaths == 1
