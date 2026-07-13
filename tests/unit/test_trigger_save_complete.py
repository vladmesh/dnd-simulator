"""Lossless trigger saves and the normal complete_trigger action path."""

from __future__ import annotations

from copy import deepcopy

import pytest
from pydantic import ValidationError

from dnd_simulator.content_loader import parse_npc
from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.events import PeaceDeclaredPayload, WarDeclaredPayload
from dnd_simulator.core.models import Event, EventType, GameDateTime
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.round import Round
from dnd_simulator.rules.validation import ActionContext
from dnd_simulator.service.action_dispatcher import create_dispatcher

TIME = GameDateTime(year=1490, month=6, day=1, hour=10)


def _trigger(
    trigger_id: str,
    *,
    armed: bool = True,
    aggressor_id: str = "north",
) -> dict[str, object]:
    return {
        "id": trigger_id,
        "armed": armed,
        "on": {
            "event": "war_declared",
            "match": {"aggressor_id": aggressor_id, "target_id": "south"},
        },
        "until": {
            "event": "peace_declared",
            "match": {"nation_a_id": "north", "nation_b_id": "south"},
        },
    }


def _npc(
    npc_id: str = "prince",
    *,
    triggers: list[dict[str, object]] | None = None,
    always_active: bool = False,
) -> Npc:
    return parse_npc(
        npc_id,
        {
            "name": npc_id,
            "start_location": "far_keep",
            "always_active": always_active,
            "triggers": triggers or [],
        },
    )


def _war(aggressor_id: str = "north") -> Event:
    return Event(EventType.WAR_DECLARED, "politics", WarDeclaredPayload(aggressor_id, "south"))


def _peace() -> Event:
    return Event(EventType.PEACE_DECLARED, "politics", PeaceDeclaredPayload("north", "south"))


def test_full_world_save_restores_active_definition_then_until_dormifies() -> None:
    npc = _npc(triggers=[_trigger("war_duty")])
    world = World([EntitiesLayer([npc])], time=TIME)
    world.handle_event(_war())
    assert npc.triggers[0].active is True

    state = world.save()
    restored_layer = EntitiesLayer([_npc()])
    restored_world = World([restored_layer], time=TIME)
    restored_world.load(state)
    restored = restored_layer.get_entity("prince")
    assert isinstance(restored, Npc)
    assert restored.triggers[0].definition.on.match_fields == (
        ("aggressor_id", "north"),
        ("target_id", "south"),
    )
    assert restored.triggers[0].active is True

    restored_world.handle_event(_peace())
    restored_layer.update_activation(TIME)

    assert restored.triggers[0].active is False
    assert restored.active is False


def test_pending_and_disarmed_trigger_states_round_trip_and_index_is_rebuilt() -> None:
    npc = _npc(triggers=[_trigger("ready"), _trigger("disabled", armed=False)])
    state = EntitiesLayer([npc]).get_state()
    restored_layer = EntitiesLayer([_npc(triggers=[_trigger("stale", aggressor_id="east")])])

    restored_layer.load_state(state)
    restored = restored_layer.get_entity("prince")
    assert isinstance(restored, Npc)
    assert [(trigger.definition.id, trigger.armed, trigger.active) for trigger in restored.triggers] == [
        ("ready", True, False),
        ("disabled", False, False),
    ]

    World([restored_layer], time=TIME).handle_event(_war())

    assert restored.triggers[0].active is True
    assert restored.triggers[1].active is False


def test_trigger_save_models_reject_unknown_fields() -> None:
    state = deepcopy(EntitiesLayer([_npc(triggers=[_trigger("war_duty")])]).get_state())
    entities = state["entities"]
    assert isinstance(entities, dict)
    npc_state = entities["prince"]
    assert isinstance(npc_state, dict)
    npc_state["triggers"] = [
        {
            **_trigger("war_duty"),
            "active": False,
            "unexpected": "not allowed",
        }
    ]

    with pytest.raises(ValidationError, match="unexpected"):
        EntitiesLayer([_npc()]).load_state(state)


def test_runtime_created_npc_restores_trigger_definitions_and_state_without_yaml() -> None:
    runtime_npc = _npc("runtime_herald", triggers=[_trigger("war_duty")], always_active=True)
    runtime_npc.triggers[0].active = True
    state = EntitiesLayer([runtime_npc]).get_state()
    restored_layer = EntitiesLayer()

    restored_layer.load_state(state)

    restored = restored_layer.get_entity("runtime_herald")
    assert isinstance(restored, Npc)
    assert restored.always_active is True
    assert len(restored.triggers) == 1
    assert restored.triggers[0].definition.id == "war_duty"
    assert restored.triggers[0].active is True
    assert restored_layer.find_trigger_matches(_peace())[0].creature is restored


class _CompleteTriggerBrain(Brain):
    def __init__(self, trigger_id: str) -> None:
        self.trigger_id = trigger_id
        self.available: list[ActionType] = []

    def choose_action(
        self,
        creature: Creature,
        awareness: PeacefulAwareness | CombatAwareness,
        events: list[PerceivedEvent],
    ) -> Action:
        self.available = list(awareness.available_actions)
        return Action(ActionType.COMPLETE_TRIGGER, {"trigger_id": self.trigger_id})


def test_scripted_brain_completes_trigger_through_round_and_dormifies_on_activation_pass() -> None:
    npc = _npc(triggers=[_trigger("war_duty")])
    npc.triggers[0].active = True
    brain = _CompleteTriggerBrain("war_duty")
    npc.brain = brain
    layer = EntitiesLayer([npc])
    world = World([layer], time=TIME)
    game_round = Round(world)

    actions = game_round.run_peaceful_turn(
        npc,
        TIME,
        world.make_query_fn("entities"),
        world.make_emit_fn("entities"),
    )

    assert brain.available.count(ActionType.COMPLETE_TRIGGER) == 1
    assert actions == [Action(ActionType.COMPLETE_TRIGGER, {"trigger_id": "war_duty"})]
    assert npc.triggers[0].active is False
    layer.update_activation(TIME)
    assert npc.active is False


@pytest.mark.parametrize("trigger_id", ["missing", "disabled", "pending"])
def test_invalid_complete_trigger_does_not_mutate_or_consume_budget(trigger_id: str) -> None:
    npc = _npc(triggers=[_trigger("active"), _trigger("disabled", armed=False), _trigger("pending")])
    npc.triggers[0].active = True
    npc.triggers[1].active = True
    layer = EntitiesLayer([npc])
    world = World([layer], time=TIME)
    dispatcher = create_dispatcher(world)
    budget = TurnBudget()
    before = [(trigger.armed, trigger.active) for trigger in npc.triggers]

    result = dispatcher.dispatch(
        npc,
        Action(ActionType.COMPLETE_TRIGGER, {"trigger_id": trigger_id}),
        ActionContext(is_combat=False, turn_budget=budget),
        world.make_emit_fn("entities"),
    )

    assert result.success is False
    assert [(trigger.armed, trigger.active) for trigger in npc.triggers] == before
    assert budget == TurnBudget()


def test_completing_one_of_two_active_triggers_leaves_other_activation_reason() -> None:
    npc = _npc(triggers=[_trigger("first"), _trigger("second")])
    for trigger in npc.triggers:
        trigger.active = True
    layer = EntitiesLayer([npc])
    world = World([layer], time=TIME)
    dispatcher = create_dispatcher(world)

    result = dispatcher.dispatch(
        npc,
        Action(ActionType.COMPLETE_TRIGGER, {"trigger_id": "first"}),
        ActionContext(is_combat=False),
        world.make_emit_fn("entities"),
    )
    layer.update_activation(TIME)

    assert result.success is True
    assert [trigger.active for trigger in npc.triggers] == [False, True]
    assert npc.active is True
