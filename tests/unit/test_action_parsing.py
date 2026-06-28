"""Boundary behavior of the WS action-parsing seam (service/action_parsing.py)."""

from __future__ import annotations

import pytest

from dnd_simulator.core.action import ActionType
from dnd_simulator.service.action_parsing import ActionParseError, parse_action


def test_parse_action_builds_typed_action_with_params() -> None:
    action = parse_action({"name": "attack", "params": {"target_id": "x"}}, default_name="idle")
    assert action.name is ActionType.ATTACK
    assert action.params == {"target_id": "x"}


def test_parse_action_defaults_to_idle_when_name_missing() -> None:
    action = parse_action({}, default_name="idle")
    assert action.name is ActionType.IDLE
    assert action.params == {}


def test_parse_action_defaults_to_skip_for_reactions() -> None:
    action = parse_action({"params": {}}, default_name="skip")
    assert action.name is ActionType.SKIP


def test_parse_action_missing_params_defaults_to_empty_dict() -> None:
    action = parse_action({"name": "dodge"}, default_name="idle")
    assert action.name is ActionType.DODGE
    assert action.params == {}


def test_parse_action_unknown_name_raises_with_offending_name() -> None:
    with pytest.raises(ActionParseError) as exc_info:
        parse_action({"name": "not_a_real_action"}, default_name="idle")
    assert exc_info.value.name == "not_a_real_action"
