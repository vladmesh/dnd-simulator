"""Lair provenance carried by concrete creature deaths."""

from __future__ import annotations

import random

from dnd_simulator.core.character import Ability, AbilityScores, Attack, DamageComponent, DamageType
from dnd_simulator.core.combat import Position
from dnd_simulator.core.events import AttackRequestedPayload, EntityDiedPayload
from dnd_simulator.core.lair import Lair, LairMemberRole
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, FactionRelation, GameDateTime, Query
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer

TIME = GameDateTime(year=1490, month=6, day=1, hour=10)


def _scores(strength: int = 10) -> AbilityScores:
    scores = AbilityScores()
    scores[Ability.STR] = strength
    return scores


def _template(template_id: str) -> MonsterTemplate:
    return MonsterTemplate(
        id=template_id,
        name=template_id.replace("_", " ").title(),
        hp=1,
        ac=1,
        speed=30,
        ability_scores=_scores(),
        attacks=(),
        cr=0.25,
        faction_id="goblins",
    )


def _player() -> PlayerCharacter:
    return PlayerCharacter(
        id="hero",
        name="Hero",
        location_id="warren",
        ability_scores=_scores(20),
        attacks=(Attack("greatsword", Ability.STR, (DamageComponent("2d6", DamageType.SLASHING),)),),
        faction_id="heroes",
        race="human",
        char_class="fighter",
    )


def _layers() -> tuple[EntitiesLayer, object, object]:
    ecology = EcologyLayer(
        lairs=[
            Lair(
                id="goblin_warren",
                name="Goblin Warren",
                faction_id="goblins",
                location_id="warren",
                members=["goblin", "goblin"],
                core="goblin_chieftain",
            )
        ]
    )
    entities = EntitiesLayer(
        entities=[_player()],
        monster_templates={"goblin": _template("goblin"), "goblin_chieftain": _template("goblin_chieftain")},
        dice_rng=random.Random(3),
    )

    def query_fn(layer_name: str, query: Query) -> Answer:
        if layer_name == "politics":
            return Answer(value=FactionRelation.HOSTILE)
        return ecology.query(query)

    def emit_fn(event: Event) -> ActionResult:
        return ActionResult()

    entities.update_activation(TIME, query_fn, emit_fn)
    return entities, query_fn, emit_fn


def _kill(entities: EntitiesLayer, target_id: str, query_fn: object, emit_fn: object) -> EntityDiedPayload:
    combat = entities.get_combat("warren")
    if combat is not None:
        combat.battle_map.set_position("hero", Position(30, 30))
        combat.battle_map.set_position(target_id, Position(35, 30))
    event = Event(
        EventType.ENTITY_ATTACK_REQUESTED,
        "entities",
        AttackRequestedPayload(attacker_id="hero", target_id=target_id),
    )
    for _ in range(20):
        result = entities.handle_event(event, query_fn, emit_fn)  # type: ignore[arg-type]
        deaths = [candidate for candidate in result.events if candidate.event_type is EventType.ENTITY_DIED]
        if deaths:
            payload = deaths[0].data
            assert isinstance(payload, EntityDiedPayload)
            return payload
    raise AssertionError("deterministic attacker did not kill 1 HP target")


def test_core_death_carries_lair_identity_role_and_template() -> None:
    entities, query_fn, emit_fn = _layers()
    core = next(creature for creature in entities.get_active_creatures() if creature.name == "Goblin Chieftain")

    payload = _kill(entities, core.id, query_fn, emit_fn)

    assert payload.lair_origin is not None
    assert payload.lair_origin.lair_id == "goblin_warren"
    assert payload.lair_origin.role is LairMemberRole.CORE
    assert payload.lair_origin.template_id == "goblin_chieftain"


def test_minion_death_carries_member_role_and_template() -> None:
    entities, query_fn, emit_fn = _layers()
    minion = next(creature for creature in entities.get_active_creatures() if creature.name == "Goblin")

    payload = _kill(entities, minion.id, query_fn, emit_fn)

    assert payload.lair_origin is not None
    assert payload.lair_origin.lair_id == "goblin_warren"
    assert payload.lair_origin.role is LairMemberRole.MEMBER
    assert payload.lair_origin.template_id == "goblin"


def test_unrelated_temporary_creature_death_has_no_lair_origin() -> None:
    hero = _player()
    wolf = _template("wolf").spawn("warren", "wolf_1")
    entities = EntitiesLayer(entities=[hero, wolf], dice_rng=random.Random(3))

    payload = _kill(
        entities,
        wolf.id,
        lambda _layer, _query: Answer(value=FactionRelation.HOSTILE),
        lambda _e: ActionResult(),
    )

    assert payload.lair_origin is None


def test_lair_origin_survives_entity_save_load_before_death() -> None:
    entities, query_fn, emit_fn = _layers()
    core = next(creature for creature in entities.get_active_creatures() if creature.name == "Goblin Chieftain")
    saved = entities.get_state()
    restored = EntitiesLayer(entities=[_player()], dice_rng=random.Random(3))
    restored.load_state(saved)

    payload = _kill(restored, core.id, query_fn, emit_fn)

    assert payload.lair_origin is not None
    assert payload.lair_origin.lair_id == "goblin_warren"
    assert payload.lair_origin.role is LairMemberRole.CORE
    assert payload.lair_origin.template_id == "goblin_chieftain"
