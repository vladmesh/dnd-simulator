"""Coverage for LLM brain fallbacks, malformed tool calls, and wounded targets."""

from dataclasses import replace
from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.action import SKIP, Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity
from dnd_simulator.core.character import Creature
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger, TriggerType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.llm.brain import LlmBrain, _action_from_tool_call, _combat_awareness_to_dict
from dnd_simulator.llm.client import LlmClient, LlmResponse


@pytest.fixture
def combat_awareness() -> CombatAwareness:
    return CombatAwareness(
        self_hp=20,
        self_max_hp=20,
        self_ac=12,
        self_speed=30,
        self_weapon="sword",
        self_weapon_damage="1d8",
        turn_budget=TurnBudget(actions=1, bonus_actions=0, movement_remaining=15, reaction=1),
        nearby=[
            CombatEntity(id="near", description="A wolf", distance_ft=10, direction="north"),
            CombatEntity(id="far", description="A bear", distance_ft=40, direction="east"),
        ],
    )


def test_non_character_idles_without_consulting_llm(combat_awareness: CombatAwareness) -> None:
    creature = Creature(id="wolf", name="Wolf", location_id="arena")
    llm = MagicMock(spec=LlmClient)

    action = LlmBrain(llm).choose_action(creature, combat_awareness, [])

    assert action == Action(name=ActionType.IDLE)
    llm.generate_with_tools.assert_not_called()


@pytest.mark.parametrize("has_options", [False, True])
def test_reaction_skips_without_options_or_tool_call(*, has_options: bool) -> None:
    npc = Npc(id="guard", name="Guard", location_id="arena")
    llm = MagicMock(spec=LlmClient)
    llm.generate_with_tools.return_value = LlmResponse(text="I will wait.", tool_call=None, raw_message=None)
    options = [ReactionOption(ActionType.OPPORTUNITY_ATTACK, "Strike", {"target_id": "thief"})] if has_options else []

    action = LlmBrain(llm).choose_reaction(npc, ReactionTrigger(TriggerType.LEAVING_REACH, "thief"), options)

    assert action is SKIP
    assert npc.inner_self is not None
    assert npc.inner_self.thoughts == []
    if has_options:
        llm.generate_with_tools.assert_called_once()
    else:
        llm.generate_with_tools.assert_not_called()


@pytest.mark.parametrize(
    ("name", "arguments", "reason"),
    [
        pytest.param(None, {"thought": "discard me"}, "tool name is not a string", id="nonstring-name"),
        pytest.param("idle", ["discard me"], "arguments are not a mapping", id="nonmapping-arguments"),
        pytest.param(
            "idle",
            {1: "invalid key", "thought": "discard me"},
            "argument names are not strings",
            id="nonstring-argument-name",
        ),
    ],
)
def test_malformed_tool_call_is_rejected_without_changing_thoughts(
    name: object, arguments: object, reason: str
) -> None:
    npc = Npc(id="guard", name="Guard", location_id="arena")
    assert npc.inner_self is not None
    npc.inner_self.add_thought("Keep watch.")

    resolution = _action_from_tool_call(npc, name, arguments, {ActionType.IDLE})

    assert resolution.action is None
    assert resolution.reason == reason
    assert npc.inner_self.thoughts == ["Keep watch."]


def test_combat_awareness_marks_only_wounded_entities(combat_awareness: CombatAwareness) -> None:
    awareness = replace(
        combat_awareness,
        nearby=[replace(combat_awareness.nearby[0], is_wounded=True), combat_awareness.nearby[1]],
    )

    result = _combat_awareness_to_dict(awareness)

    assert result["nearby"] == [
        {
            "id": "near",
            "description": "A wolf",
            "is_wounded": True,
            "distance_ft": 10,
            "reachable": True,
            "direction": "north",
        },
        {"id": "far", "description": "A bear", "distance_ft": 40, "direction": "east"},
    ]
