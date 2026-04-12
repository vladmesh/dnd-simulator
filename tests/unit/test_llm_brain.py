"""Tests for LlmBrain — primarily protocol-based schedule access."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.awareness import PeacefulAwareness
from dnd_simulator.layers.entities.models import Npc, NpcActivity, ScheduleEntry
from dnd_simulator.llm.brain import LlmBrain


def _awareness(hour: int) -> PeacefulAwareness:
    return PeacefulAwareness(
        hour=hour,
        day=1,
        month=1,
        year=1,
        weather={"condition": "clear", "temperature": 20},
        region_name="Silverport",
        location_name="smithy",
        settlements=[],
        territory_owner="",
        nation_info={},
        nearby=[],
        available_actions=(),
        available_items=[],
    )


def _mock_llm_with_tool_call(tool_name: str, args: dict[str, object]) -> MagicMock:
    llm = MagicMock()
    resp = MagicMock()
    resp.is_tool_call = True
    tc = MagicMock()
    tc.name = tool_name
    tc.arguments = args
    resp.tool_call = tc
    llm.generate_with_tools.return_value = resp
    return llm


class TestLlmBrainScheduledActivity:
    """LlmBrain must read scheduled_activity via the Protocol path, not via isinstance(Npc)."""

    def test_scheduled_activity_reaches_prompt_builder(self) -> None:
        npc = Npc(
            id="smith",
            name="Smith",
            location_id="silverport_smithy",
            schedule=[
                ScheduleEntry(start_hour=8, end_hour=18, activity=NpcActivity.WORKING, location_id="silverport_smithy"),
            ],
        )
        llm = _mock_llm_with_tool_call(ActionType.IDLE.value, {})
        captured: dict[str, object] = {}

        import dnd_simulator.llm.brain as brain_module

        original_builder = brain_module.build_npc_system_prompt

        def spy(npc_data: dict[str, object], *args: object, **kwargs: object) -> str:
            captured.update(npc_data)
            return original_builder(npc_data, *args, **kwargs)

        brain_module.build_npc_system_prompt = spy  # type: ignore[assignment]
        try:
            brain = LlmBrain(llm)
            brain.choose_action(npc, _awareness(hour=10), [])
        finally:
            brain_module.build_npc_system_prompt = original_builder  # type: ignore[assignment]

        assert captured["activity"] == NpcActivity.WORKING.value
        assert captured["location_label"] == "smithy"
