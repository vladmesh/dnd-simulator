"""Tests for NPC tool schemas and take_turn."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.character import Ability, Attack, DamageComponent, DamageType
from dnd_simulator.core.models import ActionResult, GameDateTime
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.llm.brain import LlmBrain
from dnd_simulator.llm.client import LlmResponse, ToolCall
from dnd_simulator.llm.tools import build_npc_tools

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)


def _mock_world() -> MagicMock:
    """Create a mock World with enough structure for build_awareness."""
    world = MagicMock()
    world.time = GameDateTime(year=1, month=1, day=1, hour=12)

    def fake_query(layer_name: str, query: object) -> MagicMock:
        answer = MagicMock()
        q = getattr(query, "question", "")
        if layer_name == "geography":
            if q == "weather":
                answer.value = {"condition": "clear", "temperature": 20}
            elif q == "region_info":
                answer.value = {"name": "Test Region"}
            else:
                answer.value = {}
        elif layer_name == "entities":
            if q == "entities_at_location" or q == "perceived_log" or q == "new_perceived_events":
                answer.value = []
            else:
                answer.value = None
        elif layer_name == "settlements" or layer_name == "politics":
            answer.value = None
        else:
            answer.value = None
        return answer

    world.query_layer.side_effect = fake_query
    world.handle_event.return_value = ActionResult()
    return world


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


class TestNpcTakeTurn:
    def test_no_llm_does_nothing(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        world = _mock_world()
        npc.take_turn(world)
        world.handle_event.assert_not_called()

    def test_llm_say_sends_event(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        world = _mock_world()
        mock_llm = MagicMock()
        say_tc = ToolCall(id="tc_1", name="say", arguments={"text": "Привет!"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=say_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)
        npc.take_turn(world)
        world.handle_event.assert_called_once()
        event = world.handle_event.call_args[0][0]
        assert event.event_type.value == "entity_say"
        assert event.data["text"] == "Привет!"

    def test_llm_idle_no_event(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        world = _mock_world()
        mock_llm = MagicMock()
        idle_tc = ToolCall(id="tc_1", name="idle", arguments={})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=idle_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)
        npc.take_turn(world)
        world.handle_event.assert_not_called()

    def test_llm_attack_sends_event(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="r1", role="guard", attacks=(_SWORD,))
        world = _mock_world()
        mock_llm = MagicMock()
        atk_tc = ToolCall(id="tc_1", name="attack", arguments={"target_id": "player"})
        mock_llm.generate_with_tools.return_value = LlmResponse(text=None, tool_call=atk_tc, raw_message=None)
        npc.brain = LlmBrain(mock_llm)
        npc.take_turn(world)
        world.handle_event.assert_called_once()
        event = world.handle_event.call_args[0][0]
        assert event.event_type.value == "entity_attack"
        assert event.data["attacker_id"] == "n1"
        assert event.data["target_id"] == "player"

    def test_llm_text_response_retries(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        world = _mock_world()
        mock_llm = MagicMock()
        idle_tc = ToolCall(id="tc_1", name="idle", arguments={})
        mock_llm.generate_with_tools.side_effect = [
            LlmResponse(text="Hmm...", tool_call=None, raw_message=None),
            LlmResponse(text=None, tool_call=idle_tc, raw_message=None),
        ]
        npc.brain = LlmBrain(mock_llm)
        npc.take_turn(world)
        assert mock_llm.generate_with_tools.call_count == 2

    def test_llm_exhausts_retries_does_nothing(self) -> None:
        npc = Npc(id="n1", name="Smith", location_id="r1", role="blacksmith")
        world = _mock_world()
        mock_llm = MagicMock()
        mock_llm.generate_with_tools.return_value = LlmResponse(text="I don't know", tool_call=None, raw_message=None)
        npc.brain = LlmBrain(mock_llm)
        npc.take_turn(world)
        assert mock_llm.generate_with_tools.call_count == 3
        world.handle_event.assert_not_called()
