"""Tests for LlmBrain — primarily protocol-based schedule access."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity, PeacefulAwareness
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.entities.models import Npc, NpcActivity, ScheduleEntry
from dnd_simulator.llm.brain import LlmBrain, _combat_awareness_to_dict


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


def _combat_awareness(movement_remaining: int, *, near_dist: int, far_dist: int) -> CombatAwareness:
    return CombatAwareness(
        self_hp=20,
        self_max_hp=20,
        self_ac=12,
        self_speed=30,
        self_weapon="sword",
        self_weapon_damage="1d8",
        turn_budget=TurnBudget(actions=1, bonus_actions=0, movement_remaining=movement_remaining, reaction=1),
        nearby=[
            CombatEntity(id="near", description="A wolf", distance_ft=near_dist, direction="north"),
            CombatEntity(id="far", description="A bear", distance_ft=far_dist, direction="east"),
        ],
    )


class TestCombatAwarenessDictMovement:
    """The LLM prompt dict must expose remaining movement and which targets are reachable this turn."""

    def test_dict_carries_movement_remaining(self) -> None:
        aw = _combat_awareness(15, near_dist=10, far_dist=40)
        d = _combat_awareness_to_dict(aw)
        assert d["movement_remaining"] == 15

    def test_dict_falls_back_to_speed_without_budget(self) -> None:
        aw = _combat_awareness(15, near_dist=10, far_dist=40)
        aw = replace_turn_budget_none(aw)
        d = _combat_awareness_to_dict(aw)
        assert d["movement_remaining"] == aw.self_speed

    def test_reachable_targets_flagged_within_budget(self) -> None:
        aw = _combat_awareness(15, near_dist=10, far_dist=40)
        d = _combat_awareness_to_dict(aw)
        by_id = {e["id"]: e for e in d["nearby"]}  # type: ignore[union-attr]
        assert by_id["near"].get("reachable") is True  # 10ft ≤ 15ft budget
        assert by_id["far"].get("reachable") is not True  # 40ft > 15ft budget


def replace_turn_budget_none(aw: CombatAwareness) -> CombatAwareness:
    from dataclasses import replace

    return replace(aw, turn_budget=None)


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
