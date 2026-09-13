"""Inner-self perception buffering and its four digest boundaries."""

from __future__ import annotations

import random

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Alignment, Creature, NpcRole
from dnd_simulator.core.events import (
    AttackRequestedPayload,
    AttackResolvedPayload,
    AttackRollPayload,
    EntityDiedPayload,
    EntitySayPayload,
    OpportunityAttackPayload,
)
from dnd_simulator.core.inner_self import (
    PERCEIVED_EVENT_BUFFER_CAPACITY,
    AlignmentAccumulation,
    BufferedPerceivedEvent,
    DigestBoundary,
    GoalType,
    InnerSelf,
    Mood,
    Relationship,
    RelationshipType,
    TypedGoal,
)
from dnd_simulator.core.intent import IntentInterruptReason, IntentType, TimedIntent
from dnd_simulator.core.models import Event, EventType, GameDateTime
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.event_log import EventLog
from dnd_simulator.layers.entities.inner_self_digest import digest
from dnd_simulator.layers.entities.intent_completion import interrupt_intent
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.rules.handlers.movement import handle_wait
from dnd_simulator.rules.handlers.reactions import handle_opportunity_attack
from dnd_simulator.rules.handlers.rest import handle_long_rest
from dnd_simulator.rules.rule_brain import RuleBrain
from dnd_simulator.rules.validation import ActionContext


def _npc(**kwargs: object) -> Npc:
    fields: dict[str, object] = {
        "id": "npc",
        "name": "Witness",
        "location_id": "square",
        "role": NpcRole.GUARD,
        "personality": "Alert.",
        "settlement_id": "town",
    }
    fields.update(kwargs)
    return Npc(**fields)  # type: ignore[arg-type]


def _buffer_event(description: str = "Something happened") -> BufferedPerceivedEvent:
    return BufferedPerceivedEvent(EventType.ENTITY_SAY, "speaker", None, description, 123)


def _say(text: str = "Hello", observer_ids: frozenset[str] | None = None) -> Event:
    return Event(
        event_type=EventType.ENTITY_SAY,
        source_layer="entities",
        data=EntitySayPayload(entity_id="speaker", text=text),
        observer_ids=observer_ids,
    )


def _opportunity_attack(attacker_id: str, target_id: str) -> Event:
    return Event(
        event_type=EventType.OPPORTUNITY_ATTACK,
        source_layer="entities",
        data=OpportunityAttackPayload(attacker_id, target_id),
    )


def _resolved_attack(attacker_id: str, target_id: str) -> Event:
    return Event(
        event_type=EventType.ENTITY_ATTACK,
        source_layer="entities",
        data=AttackResolvedPayload(
            attacker_id=attacker_id,
            target_id=target_id,
            hit=True,
            weapon="fists",
            critical=False,
            ac=10,
            attack_roll=AttackRollPayload(10, (), 10, False, False),
        ),
    )


def _death(entity_id: str, killer_id: str | None = None) -> Event:
    return Event(
        event_type=EventType.ENTITY_DIED,
        source_layer="entities",
        data=EntityDiedPayload(entity_id, "square", killer_id),
    )


def test_active_to_dormant_digests_once_and_clears_buffer() -> None:
    npc = _npc()
    speaker = Creature(id="speaker", name="Speaker", location_id="square")
    layer = EntitiesLayer([npc, speaker])
    layer._event_log.record(_say())

    layer.update_activation(GameDateTime())

    assert npc.inner_self is not None
    assert npc.inner_self.perceived_event_buffer == []


def test_combat_end_digests_each_core_participant_once() -> None:
    npc = _npc()
    foe = Creature(id="foe", name="Foe", location_id="square", inner_self=InnerSelf())
    layer = EntitiesLayer([npc, foe])

    assert layer._combat.start_combat("square") is not None
    layer.end_combat_round("square")
    layer.end_combat_round("square")

    assert npc.inner_self is not None
    assert npc.inner_self.perceived_event_buffer == []
    assert foe.inner_self is not None
    assert foe.inner_self.perceived_event_buffer == []


def test_timed_intent_completion_digests_once_and_clears_buffer() -> None:
    now = GameDateTime().to_total_seconds()
    npc = _npc(is_anchor=True, current_intent=TimedIntent(IntentType.WAIT, now - 1, now))
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())
    layer = EntitiesLayer([npc])

    layer.update_activation(GameDateTime())

    assert npc.inner_self.perceived_event_buffer == []


def test_intent_interruption_digests_once_and_clears_buffer() -> None:
    npc = _npc(current_intent=TimedIntent(IntentType.WAIT, 0, 3600))
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())

    assert interrupt_intent(
        npc,
        IntentInterruptReason.DAMAGE,
        digest,
    )

    assert npc.inner_self.perceived_event_buffer == []


def test_buffer_overflow_digests_before_accepting_next_event() -> None:
    npc = _npc()
    log = EventLog(
        {npc.id: npc, "speaker": Creature(id="speaker", name="Speaker", location_id="square")},
        digest=digest,
    )
    log.set_current_time(456)

    for index in range(PERCEIVED_EVENT_BUFFER_CAPACITY + 1):
        log.record(_say(str(index)))

    assert npc.inner_self is not None
    assert [event.description for event in npc.inner_self.perceived_event_buffer] == ['Speaker says: "20"']
    assert npc.inner_self.perceived_event_buffer[0].at_seconds == 456


def test_wait_dormifies_through_digest_boundary_once() -> None:
    npc = _npc()
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())
    layer = EntitiesLayer([npc])
    world = World([layer], time=GameDateTime())

    result = handle_wait(npc, Action(ActionType.WAIT, {"hours": 1}), lambda _event: None, ActionContext(False), world)

    assert result.success
    assert npc.inner_self.perceived_event_buffer == []
    layer.update_activation(GameDateTime())


def test_long_rest_dormifies_through_digest_boundary_once() -> None:
    npc = _npc()
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())
    layer = EntitiesLayer([npc])
    world = World([layer], time=GameDateTime())

    result = handle_long_rest(npc, Action(ActionType.LONG_REST), lambda _event: None, ActionContext(False), world)

    assert result.success
    assert npc.inner_self.perceived_event_buffer == []
    layer.update_activation(GameDateTime())


def test_empty_and_coincident_boundaries_call_digest_body_once() -> None:
    empty = _npc()
    digest(empty, DigestBoundary.COMBAT_ENDED)

    now = GameDateTime().to_total_seconds()
    npc = _npc(current_intent=TimedIntent(IntentType.WAIT, now - 1, now))
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())
    layer = EntitiesLayer([npc])
    layer.update_activation(GameDateTime())  # completes intent, then makes the creature dormant

    assert npc.inner_self.perceived_event_buffer == []


def test_only_active_eligible_observers_buffer_events_without_moving_brain_cursor() -> None:
    npc = _npc()
    dormant = _npc(id="dormant", active=False)
    player = PlayerCharacter(id="player", name="Player", location_id="square")
    temporary = Creature(id="temporary", name="Temporary", location_id="square", temporary=True, inner_self=InnerSelf())
    speaker = Creature(id="speaker", name="Speaker", location_id="square")
    log = EventLog({e.id: e for e in (npc, dormant, player, temporary, speaker)})

    log.record(_say())
    log.record(_say("Secret", frozenset({"someone-else"})))

    assert npc.inner_self is not None
    assert len(npc.inner_self.perceived_event_buffer) == 1
    assert dormant.inner_self is not None
    assert dormant.inner_self.perceived_event_buffer == []
    assert player.inner_self is None
    assert temporary.inner_self is not None
    assert temporary.inner_self.perceived_event_buffer == []
    assert npc._last_seen_log_index == 0


def test_perception_buffer_round_trips_and_missing_v2_field_defaults_empty() -> None:
    npc = _npc()
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(
        BufferedPerceivedEvent(EventType.ENTITY_SAY, "speaker", None, "Heard a speaker", 123, heard=True)
    )
    state = EntitiesLayer([npc]).get_state()

    restored_layer = EntitiesLayer()
    restored_layer.load_state(state)
    restored = restored_layer.get_entity("npc")
    assert isinstance(restored, Npc)
    assert restored.inner_self == npc.inner_self

    legacy_v2 = EntitiesLayer([npc]).get_state()
    entity = legacy_v2["entities"]["npc"]  # type: ignore[index]
    entity["inner_self"].pop("perceived_event_buffer")  # type: ignore[index,union-attr]
    restored_layer = EntitiesLayer()
    restored_layer.load_state(legacy_v2)
    restored = restored_layer.get_entity("npc")
    assert isinstance(restored, Npc)
    assert restored.inner_self is not None
    assert restored.inner_self.perceived_event_buffer == []


def test_foreign_speech_is_buffered_as_heard_but_own_speech_is_not() -> None:
    npc = _npc()
    speaker = Creature(id="speaker", name="Speaker", location_id="square")
    log = EventLog({npc.id: npc, speaker.id: speaker})

    log.record(_say("Foreign words"))
    log.record(
        Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data=EntitySayPayload(entity_id=npc.id, text="My own words"),
        )
    )

    assert npc.inner_self is not None
    assert [event.heard for event in npc.inner_self.perceived_event_buffer] == [True, False]


def test_event_log_normalizes_death_as_killer_and_dead_target() -> None:
    npc = _npc()
    killer = Creature(id="killer", name="Killer", location_id="square")
    dead = Creature(id="dead", name="Dead", location_id="square")
    log = EventLog({entity.id: entity for entity in (npc, killer, dead)})

    log.record(_death("dead", "killer"))

    assert npc.inner_self is not None
    participants = [(event.actor_id, event.target_id) for event in npc.inner_self.perceived_event_buffer]
    assert participants == [("killer", "dead")]


def test_rule_brain_digest_applies_battle_outcome_and_round_trips() -> None:
    npc = _npc(
        brain=RuleBrain(),
        inner_self=InnerSelf(
            relations=[Relationship("ally", RelationshipType.LOVES)],
            goals=[TypedGoal(GoalType.KILL, "enemy"), TypedGoal(GoalType.PROTECT, "ward")],
        ),
    )
    attacker = Creature(id="attacker", name="Attacker", location_id="square")
    ally = Creature(id="ally", name="Ally", location_id="square")
    enemy = Creature(id="enemy", name="Enemy", location_id="square")
    ward = Creature(id="ward", name="Ward", location_id="square")
    log = EventLog({entity.id: entity for entity in (npc, attacker, ally, enemy, ward)})

    log.record(_resolved_attack("attacker", "npc"))
    log.record(_opportunity_attack("attacker", "npc"))
    log.record(_death("ally"))
    log.record(_death("enemy"))
    log.record(_death("ward"))
    digest(npc, DigestBoundary.COMBAT_ENDED)

    assert npc.inner_self is not None
    assert npc.inner_self.relation_targets(RelationshipType.HATES) == {"attacker"}
    assert npc.inner_self.mood is Mood.GRIEVING
    assert [goal.status.value for goal in npc.inner_self.goals] == ["achieved", "failed"]
    assert npc.inner_self.perceived_event_buffer == []
    restored_layer = EntitiesLayer()
    restored_layer.load_state(EntitiesLayer([npc]).get_state())
    restored = restored_layer.get_entity("npc")
    assert isinstance(restored, Npc)
    assert restored.inner_self == npc.inner_self


def test_digest_shifts_npc_alignment_and_round_trips_shifted_state() -> None:
    npc = _npc(
        alignment=Alignment.TRUE_NEUTRAL,
        inner_self=InnerSelf(
            relations=[Relationship("ally", RelationshipType.TRUSTS)],
            alignment=AlignmentAccumulation(law_chaos=2, good_evil=2),
            perceived_event_buffer=[
                BufferedPerceivedEvent(EventType.ENTITY_ATTACK, "npc", "ally", "Attack", 1),
            ],
        ),
    )

    digest(npc, DigestBoundary.COMBAT_ENDED)

    assert npc.alignment is Alignment.CHAOTIC_EVIL
    assert npc.inner_self is not None
    assert npc.inner_self.alignment == AlignmentAccumulation(law_chaos=1, good_evil=1)
    restored_layer = EntitiesLayer()
    restored_layer.load_state(EntitiesLayer([npc]).get_state())
    restored = restored_layer.get_entity("npc")
    assert isinstance(restored, Npc)
    assert restored.alignment is Alignment.CHAOTIC_EVIL
    assert restored.inner_self is not None
    assert restored.inner_self.alignment == AlignmentAccumulation(law_chaos=1, good_evil=1)


def test_player_alignment_never_shifts_even_with_artificial_inner_self() -> None:
    player = PlayerCharacter(
        id="player",
        name="Player",
        location_id="square",
        alignment=Alignment.LAWFUL_GOOD,
        inner_self=InnerSelf(
            relations=[Relationship("ally", RelationshipType.TRUSTS)],
            alignment=AlignmentAccumulation(law_chaos=2, good_evil=2),
            perceived_event_buffer=[
                BufferedPerceivedEvent(EventType.ENTITY_ATTACK, "player", "ally", "Attack", 1),
            ],
        ),
    )

    digest(player, DigestBoundary.COMBAT_ENDED)

    assert player.alignment is Alignment.LAWFUL_GOOD
    assert player.inner_self is not None
    assert player.inner_self.alignment == AlignmentAccumulation(law_chaos=3, good_evil=3)


def test_core_bearing_creature_without_alignment_still_accumulates() -> None:
    monster = Creature(
        id="monster",
        name="Monster",
        location_id="square",
        inner_self=InnerSelf(
            relations=[Relationship("ally", RelationshipType.TRUSTS)],
            perceived_event_buffer=[
                BufferedPerceivedEvent(EventType.ENTITY_ATTACK, "monster", "ally", "Attack", 1),
            ],
        ),
    )

    digest(monster, DigestBoundary.COMBAT_ENDED)

    assert monster.inner_self is not None
    assert monster.inner_self.alignment == AlignmentAccumulation(law_chaos=1, good_evil=1)


def test_real_combat_chain_digests_outcome_without_llm_client() -> None:
    npc = _npc(
        max_hp=10,
        current_hp=10,
        inner_self=InnerSelf(
            relations=[
                Relationship("ally", RelationshipType.LOVES),
                Relationship("attacker", RelationshipType.HATES),
            ],
            goals=[TypedGoal(GoalType.KILL, "enemy"), TypedGoal(GoalType.PROTECT, "ward")],
        ),
    )
    attacker = Creature(
        id="attacker",
        name="Attacker",
        location_id="square",
        inner_self=InnerSelf(relations=[Relationship("npc", RelationshipType.TRUSTS)]),
    )
    ally = Creature(id="ally", name="Ally", location_id="square", max_hp=1, current_hp=1)
    enemy = Creature(id="enemy", name="Enemy", location_id="square", max_hp=1, current_hp=1)
    ward = Creature(id="ward", name="Ward", location_id="square", max_hp=1, current_hp=1)
    layer = EntitiesLayer([npc, attacker, ally, enemy, ward], dice_rng=random.Random(0))
    world = World([layer], time=GameDateTime())
    layer._combat._rng.randint = lambda _a, b: b  # type: ignore[method-assign]

    result = handle_opportunity_attack(
        attacker,
        Action(ActionType.OPPORTUNITY_ATTACK, {"target_id": "npc"}),
        world.handle_event,
        ActionContext(False),
        world,
    )
    assert result.success
    for target_id in ("ally", "enemy", "ward"):
        world.handle_event(
            Event(
                EventType.ENTITY_ATTACK_REQUESTED,
                "entities",
                AttackRequestedPayload("attacker", target_id),
            )
        )

    assert layer.get_combat("square") is not None
    layer.end_combat_round("square")
    layer.end_combat_round("square")
    layer.end_combat_round("square")

    assert npc.inner_self is not None
    assert npc.inner_self.relation_targets(RelationshipType.HATES) == {"attacker"}
    assert (
        next(relation for relation in npc.inner_self.relations if relation.type is RelationshipType.HATES).intensity
        == 60
    )
    assert npc.inner_self.mood is Mood.GRIEVING
    assert [goal.status.value for goal in npc.inner_self.goals] == ["achieved", "failed"]
    assert npc.inner_self.perceived_event_buffer == []
    assert attacker.inner_self is not None
    assert attacker.inner_self.alignment == AlignmentAccumulation(law_chaos=1, good_evil=1)
