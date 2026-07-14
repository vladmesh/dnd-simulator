"""Tests for NPC tool schemas and LLM brain turn orchestration."""

from __future__ import annotations

from typing import cast
from unittest.mock import MagicMock

from dnd_simulator.core.character import Ability, Attack, DamageComponent, DamageType, NpcRole
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, GameDateTime, Query
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.client import LlmResponse, ToolCall
from dnd_simulator.llm.tools import build_npc_tools
from dnd_simulator.rules.validation import ActionContext
from dnd_simulator.service.action_dispatcher import create_dispatcher

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)

_TIME = GameDateTime(year=1, month=1, day=1, hour=12)


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


_STUB_WORLD = cast(World, MagicMock(spec=World))


def _run_turn(layer: EntitiesLayer, npc: Npc, emit_fn: object = None) -> None:
    """Run a single brain→execute turn via dispatcher."""
    if npc.brain is None:
        return
    awareness = layer.build_awareness(npc, _TIME, _noop_query_fn)
    events = layer.get_perceived_events(npc)
    action = npc.brain.choose_action(npc, awareness, events)
    ctx = ActionContext(is_combat=npc.in_combat, current_turn_entity_id=npc.id)
    dispatcher = create_dispatcher(_STUB_WORLD)
    dispatcher.dispatch(npc, action, ctx, emit_fn or _noop_emit_fn)


class TestBuildNpcTools:
    def test_always_has_say_idle_attack(self) -> None:
        tools = build_npc_tools()
        names = [t["function"]["name"] for t in tools]
        assert "say" in names
        assert "idle" in names
        assert "attack" in names

    def test_attack_has_only_target_id(self) -> None:
        tools = build_npc_tools()
        attack_tool = next(t for t in tools if t["function"]["name"] == "attack")
        params = attack_tool["function"]["parameters"]["properties"]
        assert "target_id" in params
        assert "weapon" not in params


class TestNpcTurnOrchestration:
    def test_no_brain_does_nothing(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role=NpcRole.BLACKSMITH)
        layer = EntitiesLayer([npc])

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        _run_turn(layer, npc, capture_emit)
        assert emit_calls == []

    def test_llm_say_sends_event(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role=NpcRole.BLACKSMITH)
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        say_tc = ToolCall(id="tc_1", name="say", arguments={"text": "Привет!"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=say_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        _run_turn(layer, npc, capture_emit)
        assert len(emit_calls) == 1
        assert emit_calls[0].event_type == EventType.ENTITY_SAY
        assert emit_calls[0].data.text == "Привет!"

    def test_llm_idle_no_event(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role=NpcRole.BLACKSMITH)
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        idle_tc = ToolCall(id="tc_1", name="idle", arguments={})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=idle_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        _run_turn(layer, npc, capture_emit)
        assert emit_calls == []

    def test_llm_attack_sends_event(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="r1", role=NpcRole.GUARD, attacks=(_SWORD,))
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        atk_tc = ToolCall(id="tc_1", name="attack", arguments={"target_id": "player"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=atk_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        _run_turn(layer, npc, capture_emit)
        assert len(emit_calls) == 1
        assert emit_calls[0].event_type == EventType.ENTITY_ATTACK_REQUESTED
        assert emit_calls[0].data.attacker_id == "n1"
        assert emit_calls[0].data.target_id == "player"

    def test_llm_text_response_retries(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role=NpcRole.BLACKSMITH)
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        idle_tc = ToolCall(id="tc_1", name="idle", arguments={})
        mock_llm.generate_with_tools.side_effect = [
            LlmResponse(text="Hmm...", tool_call=None, raw_message=None),
            LlmResponse(text=None, tool_call=idle_tc, raw_message=None),
        ]
        npc.brain = LlmBrain(mock_llm)

        _run_turn(layer, npc)
        assert mock_llm.generate_with_tools.call_count == 2

    def test_llm_exhausts_retries_does_nothing(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role=NpcRole.BLACKSMITH)
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        mock_llm.generate_with_tools.return_value = LlmResponse(text="I don't know", tool_call=None, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        _run_turn(layer, npc, capture_emit)
        assert mock_llm.generate_with_tools.call_count == 3
        assert emit_calls == []
