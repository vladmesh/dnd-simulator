"""Immediate ecology write-back for deaths in materialized lairs."""

from __future__ import annotations

import random

from dnd_simulator.core.character import Ability, AbilityScores, Attack, DamageComponent, DamageType
from dnd_simulator.core.events import AttackRequestedPayload, EntityDiedPayload, LairDematerializedPayload
from dnd_simulator.core.lair import Lair, LairMemberRole, LairOrigin, LairState
from dnd_simulator.core.models import Event, EventType, FactionRelation, GameDateTime, Query, QueryType
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer

TIME = GameDateTime(year=1490, month=6, day=1, hour=10)


def _scores(strength: int = 10) -> AbilityScores:
    scores = AbilityScores()
    scores[Ability.STR] = strength
    return scores


def _template(template_id: str) -> MonsterTemplate:
    return MonsterTemplate(
        id=template_id,
        name=template_id,
        hp=1,
        ac=1,
        speed=30,
        ability_scores=_scores(),
        attacks=(),
        cr=0.25,
        faction_id="goblins",
    )


def _world() -> tuple[World, EcologyLayer, EntitiesLayer, Lair]:
    lair = Lair(
        id="warren",
        name="Warren",
        faction_id="goblins",
        location_id="cave",
        members=["goblin", "goblin"],
        core="chief",
    )
    ecology = EcologyLayer(lairs=[lair])
    hero = PlayerCharacter(
        id="hero",
        name="Hero",
        location_id="cave",
        ability_scores=_scores(20),
        attacks=(Attack("greatsword", Ability.STR, (DamageComponent("2d6", DamageType.SLASHING),)),),
        faction_id="heroes",
        race="human",
        char_class="fighter",
    )
    entities = EntitiesLayer(
        entities=[hero],
        monster_templates={"goblin": _template("goblin"), "chief": _template("chief")},
        dice_rng=random.Random(3),
    )
    politics = PoliticsLayer(
        faction_relations={("goblins", "heroes"): FactionRelation.HOSTILE},
        faction_names={"goblins": "Goblins", "heroes": "Heroes"},
    )
    world = World([politics, ecology, entities], time=TIME)
    entities.update_activation(TIME, world.make_query_fn("entities"), world.make_emit_fn("entities"))
    return world, ecology, entities, lair


def _kill(world: World, entities: EntitiesLayer, target_id: str) -> EntityDiedPayload:
    combat = entities.get_combat("cave")
    if combat is not None:
        from dnd_simulator.core.combat import Position

        combat.battle_map.set_position("hero", Position(30, 30))
        combat.battle_map.set_position(target_id, Position(35, 30))
    attack = Event(EventType.ENTITY_ATTACK_REQUESTED, "entities", AttackRequestedPayload("hero", target_id))
    for _ in range(20):
        result = world.handle_event(attack)
        for event in result.events:
            if event.event_type is EventType.ENTITY_DIED:
                world.handle_event(event)
                assert isinstance(event.data, EntityDiedPayload)
                return event.data
    raise AssertionError("deterministic attacker did not kill target")


def test_core_death_depletes_immediately_and_survives_save_load() -> None:
    world, ecology, entities, lair = _world()
    core = next(
        creature
        for creature in entities.get_active_creatures()
        if creature.lair_origin and creature.lair_origin.role is LairMemberRole.CORE
    )

    _kill(world, entities, core.id)

    assert lair.core_alive is False
    assert lair.state is LairState.DEPLETED
    assert ecology.query(Query(QueryType.LAIRS_AT_LOCATION, {"location_id": "cave"})).value[0].core is None
    saved = ecology.get_state()
    restored_lair = Lair("warren", "Warren", "goblins", "cave", ["goblin", "goblin"], core="chief")
    restored = EcologyLayer(lairs=[restored_lair])
    restored.load_state(saved)
    assert restored_lair.core_alive is False
    assert restored_lair.state is LairState.DEPLETED


def test_minion_death_removes_exactly_one_and_is_idempotent_across_save_load() -> None:
    world, ecology, entities, lair = _world()
    minion = next(
        creature
        for creature in entities.get_active_creatures()
        if creature.lair_origin and creature.lair_origin.role is LairMemberRole.MEMBER
    )

    payload = _kill(world, entities, minion.id)

    assert lair.alive_members == ["goblin"]
    saved = ecology.get_state()
    restored_lair = Lair("warren", "Warren", "goblins", "cave", ["goblin", "goblin"], core="chief")
    restored = EcologyLayer(lairs=[restored_lair])
    restored.load_state(saved)
    restored.handle_event(Event(EventType.ENTITY_DIED, "entities", payload), lambda *_: None, lambda *_: None)  # type: ignore[arg-type]
    assert restored_lair.alive_members == ["goblin"]
    assert restored_lair.state is LairState.ACTIVE


def test_unrelated_unknown_and_duplicate_deaths_are_safe_noops() -> None:
    world, _ecology, _entities, lair = _world()
    before = (lair.state, lair.core_alive, lair.alive_members)
    world.handle_event(Event(EventType.ENTITY_DIED, "entities", EntityDiedPayload("wolf")))
    world.handle_event(
        Event(
            EventType.ENTITY_DIED,
            "entities",
            EntityDiedPayload("ghost", lair_origin=LairOrigin("missing", "goblin", LairMemberRole.MEMBER)),
        )
    )
    assert (lair.state, lair.core_alive, lair.alive_members) == before


def test_dematerialize_cannot_undo_core_depletion() -> None:
    world, _ecology, entities, lair = _world()
    core = next(
        creature
        for creature in entities.get_active_creatures()
        if creature.lair_origin and creature.lair_origin.role is LairMemberRole.CORE
    )
    _kill(world, entities, core.id)

    world.handle_event(
        Event(
            EventType.LAIR_DEMATERIALIZED,
            "entities",
            LairDematerializedPayload("warren", True, ("goblin",), TIME.to_total_seconds()),
        )
    )

    assert lair.core_alive is False
    assert lair.state is LairState.DEPLETED
    assert lair.alive_members == ["goblin"]
