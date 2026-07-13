"""Tests for centralized ActionDef registry."""

from __future__ import annotations

import pytest

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.action_defs import ACTION_DEFS, CostType, get_action_def
from dnd_simulator.llm.tools import get_tools


class TestActionDefRegistry:
    def test_all_action_types_registered(self) -> None:
        """Every ActionType enum member must have an ActionDef."""
        for at in ActionType:
            assert at in ACTION_DEFS, f"ActionType.{at.name} not registered in ACTION_DEFS"

    def test_no_empty_descriptions(self) -> None:
        for ad in ACTION_DEFS.values():
            assert ad.description, f"{ad.action_type} has empty description"

    def test_get_action_def_crashes_on_unknown(self) -> None:
        """get_action_def must fail fast on unknown action types."""
        with pytest.raises(KeyError):
            get_action_def("nonexistent_action")  # type: ignore[arg-type]

    def test_internal_actions_have_no_standard_cost(self) -> None:
        """Internal actions are free or reaction-cost — never action/bonus/movement."""
        for ad in ACTION_DEFS.values():
            if ad.internal:
                assert ad.cost_type in (CostType.FREE, CostType.REACTION), (
                    f"Internal action {ad.action_type} has unexpected cost {ad.cost_type}"
                )

    def test_targeted_actions_have_target_id_param(self) -> None:
        for ad in ACTION_DEFS.values():
            if ad.targeted:
                param_names = [p.name for p in ad.params]
                assert "target_id" in param_names, f"Targeted action {ad.action_type} missing target_id param"


class TestToolSchemaGeneration:
    def test_internal_actions_excluded_from_tools(self) -> None:
        """END_TURN and SKIP should not appear as LLM tools."""
        all_actions = list(ActionType)
        tools = get_tools(all_actions)
        tool_names = {t["function"]["name"] for t in tools}
        assert "end_turn" not in tool_names
        assert "skip" not in tool_names

    def test_attack_schema_has_required_target_id(self) -> None:
        tools = get_tools([ActionType.ATTACK])
        assert len(tools) == 1
        schema = tools[0]
        assert schema["function"]["name"] == "attack"
        assert "target_id" in schema["function"]["parameters"]["properties"]
        assert "target_id" in schema["function"]["parameters"]["required"]

    def test_idle_schema_has_no_required_params(self) -> None:
        tools = get_tools([ActionType.IDLE])
        assert len(tools) == 1
        schema = tools[0]
        assert "required" not in schema["function"]["parameters"]

    def test_dash_schema_only_adds_movement_budget(self) -> None:
        schema = get_tools([ActionType.DASH])[0]["function"]

        assert set(schema["parameters"]["properties"]) == {"description", "cost_mode"}
        assert "movement budget" in schema["description"]
        assert "separate move" in schema["description"]

    def test_llm_hint_overrides_description(self) -> None:
        """When llm_hint is set, it should be used instead of description."""
        ad = get_action_def(ActionType.ATTACK)
        assert ad.llm_hint  # ATTACK has llm_hint
        tools = get_tools([ActionType.ATTACK])
        tool_desc = tools[0]["function"]["description"]
        assert tool_desc == ad.llm_hint

    def test_all_non_internal_actions_produce_schemas(self) -> None:
        """Every non-internal action should produce a valid tool schema."""
        all_actions = list(ActionType)
        tools = get_tools(all_actions)
        internal_count = sum(1 for ad in ACTION_DEFS.values() if ad.internal)
        assert len(tools) == len(all_actions) - internal_count
