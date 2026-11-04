"""Coverage for typed-goal target validation."""

import pytest

from dnd_simulator.core.inner_self import GoalType, TypedGoal


def test_typed_goal_rejects_empty_target_id() -> None:
    with pytest.raises(ValueError, match=r"^typed goal target_id must not be empty$"):
        TypedGoal(GoalType.PROTECT, "")
