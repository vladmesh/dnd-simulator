"""Inner-self perception buffering and its four digest boundaries."""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature, NpcRole
from dnd_simulator.core.events import EntitySayPayload
from dnd_simulator.core.inner_self import (
    PERCEIVED_EVENT_BUFFER_CAPACITY,
    BufferedPerceivedEvent,
    DigestBoundary,
    InnerSelf,
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
from dnd_simulator.rules.handlers.rest import handle_long_rest
from dnd_simulator.rules.validation import ActionContext


class FakeSummarizer:
    def __init__(self) -> None:
        self.calls: list[tuple[list[str], str]] = []

    def summarize(self, inner_self: InnerSelf, events: list[str], trigger: str) -> InnerSelf:
        self.calls.append((events, trigger))
        return inner_self

    def needs_compression(self, inner_self: InnerSelf) -> bool:
        return False


class ReplacingSummarizer(FakeSummarizer):
    def summarize(self, inner_self: InnerSelf, events: list[str], trigger: str) -> InnerSelf:
        self.calls.append((events, trigger))
        return InnerSelf(perceived_event_buffer=[_buffer_event("stale")])


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


def test_active_to_dormant_digests_once_and_clears_buffer() -> None:
    summarizer = FakeSummarizer()
    npc = _npc()
    speaker = Creature(id="speaker", name="Speaker", location_id="square")
    layer = EntitiesLayer([npc, speaker], summarizer=summarizer)  # type: ignore[arg-type]
    layer._event_log.record(_say())

    layer.update_activation(GameDateTime())

    assert summarizer.calls == [(['Speaker says: "Hello"'], DigestBoundary.DORMANT.value)]
    assert npc.inner_self is not None
    assert npc.inner_self.perceived_event_buffer == []


def test_combat_end_digests_each_core_participant_once() -> None:
    summarizer = FakeSummarizer()
    npc = _npc()
    foe = Creature(id="foe", name="Foe", location_id="square", inner_self=InnerSelf())
    layer = EntitiesLayer([npc, foe], summarizer=summarizer)  # type: ignore[arg-type]

    assert layer._combat.start_combat("square") is not None
    layer.end_combat_round("square")
    layer.end_combat_round("square")

    assert len(summarizer.calls) == 1
    events, boundary = summarizer.calls[0]
    assert events[-1] == "Combat ended."
    assert events[0].startswith("Combat started! Initiative order:")
    assert boundary == DigestBoundary.COMBAT_ENDED.value
    assert npc.inner_self is not None
    assert npc.inner_self.perceived_event_buffer == []
    assert foe.inner_self is not None
    assert foe.inner_self.perceived_event_buffer == []


def test_timed_intent_completion_digests_once_and_clears_buffer() -> None:
    summarizer = FakeSummarizer()
    now = GameDateTime().to_total_seconds()
    npc = _npc(is_anchor=True, current_intent=TimedIntent(IntentType.WAIT, now - 1, now))
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())
    layer = EntitiesLayer([npc], summarizer=summarizer)  # type: ignore[arg-type]

    layer.update_activation(GameDateTime())

    assert summarizer.calls == [(["Something happened"], DigestBoundary.INTENT_COMPLETED.value)]
    assert npc.inner_self.perceived_event_buffer == []


def test_intent_interruption_digests_once_and_clears_buffer() -> None:
    summarizer = FakeSummarizer()
    npc = _npc(current_intent=TimedIntent(IntentType.WAIT, 0, 3600))
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())

    assert interrupt_intent(
        npc,
        IntentInterruptReason.DAMAGE,
        lambda creature, boundary: digest(creature, boundary, summarizer),  # type: ignore[arg-type]
    )

    assert summarizer.calls == [(["Something happened"], DigestBoundary.INTENT_INTERRUPTED.value)]
    assert npc.inner_self.perceived_event_buffer == []


def test_buffer_overflow_digests_before_accepting_next_event() -> None:
    summarizer = FakeSummarizer()
    npc = _npc()
    log = EventLog(
        {npc.id: npc, "speaker": Creature(id="speaker", name="Speaker", location_id="square")},
        digest=lambda creature, boundary: digest(creature, boundary, summarizer),  # type: ignore[arg-type]
    )
    log.set_current_time(456)

    for index in range(PERCEIVED_EVENT_BUFFER_CAPACITY + 1):
        log.record(_say(str(index)))

    assert len(summarizer.calls) == 1
    assert len(summarizer.calls[0][0]) == PERCEIVED_EVENT_BUFFER_CAPACITY
    assert summarizer.calls[0][1] == DigestBoundary.BUFFER_FULL.value
    assert npc.inner_self is not None
    assert [event.description for event in npc.inner_self.perceived_event_buffer] == ['Speaker says: "20"']
    assert npc.inner_self.perceived_event_buffer[0].at_seconds == 456


def test_buffer_overflow_appends_to_replaced_inner_self() -> None:
    summarizer = ReplacingSummarizer()
    npc = _npc()
    log = EventLog(
        {npc.id: npc, "speaker": Creature(id="speaker", name="Speaker", location_id="square")},
        digest=lambda creature, boundary: digest(creature, boundary, summarizer),  # type: ignore[arg-type]
    )

    for index in range(PERCEIVED_EVENT_BUFFER_CAPACITY + 1):
        log.record(_say(str(index)))

    expected_events = [f'Speaker says: "{index}"' for index in range(PERCEIVED_EVENT_BUFFER_CAPACITY)]
    assert summarizer.calls == [(expected_events, DigestBoundary.BUFFER_FULL.value)]
    assert npc.inner_self is not None
    assert [event.description for event in npc.inner_self.perceived_event_buffer] == ['Speaker says: "20"']


def test_wait_dormifies_through_digest_boundary_once() -> None:
    summarizer = FakeSummarizer()
    npc = _npc()
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())
    layer = EntitiesLayer([npc], summarizer=summarizer)  # type: ignore[arg-type]
    world = World([layer], time=GameDateTime())

    result = handle_wait(npc, Action(ActionType.WAIT, {"hours": 1}), lambda _event: None, ActionContext(False), world)

    assert result.success
    assert summarizer.calls == [(["Something happened"], DigestBoundary.DORMANT.value)]
    assert npc.inner_self.perceived_event_buffer == []
    layer.update_activation(GameDateTime())
    assert len(summarizer.calls) == 1


def test_long_rest_dormifies_through_digest_boundary_once() -> None:
    summarizer = FakeSummarizer()
    npc = _npc()
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())
    layer = EntitiesLayer([npc], summarizer=summarizer)  # type: ignore[arg-type]
    world = World([layer], time=GameDateTime())

    result = handle_long_rest(npc, Action(ActionType.LONG_REST), lambda _event: None, ActionContext(False), world)

    assert result.success
    assert summarizer.calls == [(["Something happened"], DigestBoundary.DORMANT.value)]
    assert npc.inner_self.perceived_event_buffer == []
    layer.update_activation(GameDateTime())
    assert len(summarizer.calls) == 1


def test_empty_and_coincident_boundaries_call_digest_body_once() -> None:
    summarizer = FakeSummarizer()
    empty = _npc()
    digest(empty, DigestBoundary.COMBAT_ENDED, summarizer)  # type: ignore[arg-type]
    assert summarizer.calls == []

    now = GameDateTime().to_total_seconds()
    npc = _npc(current_intent=TimedIntent(IntentType.WAIT, now - 1, now))
    assert npc.inner_self is not None
    npc.inner_self.perceived_event_buffer.append(_buffer_event())
    layer = EntitiesLayer([npc], summarizer=summarizer)  # type: ignore[arg-type]
    layer.update_activation(GameDateTime())  # completes intent, then makes the creature dormant

    assert summarizer.calls == [(["Something happened"], DigestBoundary.INTENT_COMPLETED.value)]


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
    npc.inner_self.perceived_event_buffer.append(_buffer_event())
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
