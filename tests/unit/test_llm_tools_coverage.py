"""Tests for reserved parameter validation in LLM tool schemas."""

from __future__ import annotations

import pytest

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.reactions import ReactionOption
from dnd_simulator.llm.tools import get_reaction_tools


def test_reaction_tool_rejects_reserved_thought_parameter() -> None:
    option = ReactionOption(
        action_type=ActionType.ATTACK,
        description="Make an opportunity attack.",
        params={"thought": "Strike now."},
    )

    with pytest.raises(ValueError, match=r"^tool parameter conflicts with reserved LLM field: attack\.thought$"):
        get_reaction_tools([option])
