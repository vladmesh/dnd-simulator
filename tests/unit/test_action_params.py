"""Tests for typed action-parameter validation and integer parsing (rules/action_params.py)."""

from __future__ import annotations

import pytest

from dnd_simulator.core.action import Action, ActionRejectedError, ActionType
from dnd_simulator.rules.action_params import integer_param, validate_action_params


class TestValidateActionParams:
    def test_valid_params_pass(self) -> None:
        validate_action_params(Action(ActionType.MOVE_TO, {"x": 10, "y": "15"}))
        validate_action_params(Action(ActionType.SAY, {"text": "hello"}))

    def test_missing_optional_param_allowed(self) -> None:
        validate_action_params(Action(ActionType.ATTACK, {"target_id": "goblin"}))

    def test_missing_required_param_rejected(self) -> None:
        with pytest.raises(ActionRejectedError, match="text"):
            validate_action_params(Action(ActionType.SAY, {}))

    def test_non_string_for_string_param_rejected(self) -> None:
        with pytest.raises(ActionRejectedError, match="text"):
            validate_action_params(Action(ActionType.SAY, {"text": 42}))

    @pytest.mark.parametrize("bad", [True, "ten", 1.5, None, [1]])
    def test_non_integer_for_integer_param_rejected(self, bad: object) -> None:
        with pytest.raises(ActionRejectedError, match="x"):
            validate_action_params(Action(ActionType.MOVE_TO, {"x": bad, "y": 0}))


class TestIntegerParam:
    def test_int_value_returned(self) -> None:
        assert integer_param(Action(ActionType.MOVE_TO, {"x": 25}), "x") == 25

    def test_integer_string_parsed(self) -> None:
        assert integer_param(Action(ActionType.MOVE_TO, {"x": "-5"}), "x") == -5

    def test_missing_with_default_returns_default(self) -> None:
        assert integer_param(Action(ActionType.MOVE_TO, {}), "x", default=7) == 7

    def test_missing_with_zero_default_returns_zero(self) -> None:
        assert integer_param(Action(ActionType.MOVE_TO, {}), "x", default=0) == 0

    def test_missing_without_default_rejected(self) -> None:
        with pytest.raises(ActionRejectedError, match="x"):
            integer_param(Action(ActionType.MOVE_TO, {}), "x")

    def test_bool_rejected(self) -> None:
        with pytest.raises(ActionRejectedError):
            integer_param(Action(ActionType.MOVE_TO, {"x": False}), "x")

    def test_non_numeric_string_rejected_with_cause(self) -> None:
        with pytest.raises(ActionRejectedError) as excinfo:
            integer_param(Action(ActionType.MOVE_TO, {"x": "abc"}), "x")
        assert isinstance(excinfo.value.__cause__, ValueError)

    def test_other_type_rejected(self) -> None:
        with pytest.raises(ActionRejectedError):
            integer_param(Action(ActionType.MOVE_TO, {"x": 2.0}), "x")
