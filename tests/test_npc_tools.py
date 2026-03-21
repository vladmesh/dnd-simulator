"""Tests for NPC tool schemas and LLM brain turn orchestration."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.character import Ability, Attack, DamageComponent, DamageType
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, GameDateTime, Query
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.client import LlmResponse, ToolCall
from dnd_simulator.llm.tools import build_npc_tools

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
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        layer = EntitiesLayer([npc])

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        layer.run_creature_turn(npc, _TIME, _noop_query_fn, capture_emit)
        assert emit_calls == []

    def test_llm_say_sends_event(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        say_tc = ToolCall(id="tc_1", name="say", arguments={"text": "Привет!"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=say_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        layer.run_creature_turn(npc, _TIME, _noop_query_fn, capture_emit)
        assert len(emit_calls) == 1
        assert emit_calls[0].event_type == EventType.ENTITY_SAY
        assert emit_calls[0].data["text"] == "Привет!"

    def test_llm_idle_no_event(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        idle_tc = ToolCall(id="tc_1", name="idle", arguments={})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=idle_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        layer.run_creature_turn(npc, _TIME, _noop_query_fn, capture_emit)
        assert emit_calls == []

    def test_llm_attack_sends_event(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="r1", role="guard", attacks=(_SWORD,))
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        atk_tc = ToolCall(id="tc_1", name="attack", arguments={"target_id": "player"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=atk_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        layer.run_creature_turn(npc, _TIME, _noop_query_fn, capture_emit)
        assert len(emit_calls) == 1
        assert emit_calls[0].event_type == EventType.ENTITY_ATTACK
        assert emit_calls[0].data["attacker_id"] == "n1"
        assert emit_calls[0].data["target_id"] == "player"

    def test_llm_text_response_retries(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        idle_tc = ToolCall(id="tc_1", name="idle", arguments={})
        mock_llm.generate_with_tools.side_effect = [
            LlmResponse(text="Hmm...", tool_call=None, raw_message=None),
            LlmResponse(text=None, tool_call=idle_tc, raw_message=None),
        ]
        npc.brain = LlmBrain(mock_llm)

        layer.run_creature_turn(npc, _TIME, _noop_query_fn, _noop_emit_fn)
        assert mock_llm.generate_with_tools.call_count == 2

    def test_llm_exhausts_retries_does_nothing(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        layer = EntitiesLayer([npc])
        mock_llm = MagicMock()
        mock_llm.generate_with_tools.return_value = LlmResponse(text="I don't know", tool_call=None, raw_message=None)
        npc.brain = LlmBrain(mock_llm)

        emit_calls: list[Event] = []

        def capture_emit(event: Event) -> ActionResult:
            emit_calls.append(event)
            return ActionResult()

        layer.run_creature_turn(npc, _TIME, _noop_query_fn, capture_emit)
        assert mock_llm.generate_with_tools.call_count == 3
        assert emit_calls == []
