"""Validation coverage for trigger action availability."""

import pytest

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import EventType
from dnd_simulator.core.triggers import ActivationTrigger, EventCondition, TriggerDefinition
from dnd_simulator.rules.action_provider import TriggerActionProvider
from dnd_simulator.rules.validation import ActionContext


@pytest.mark.parametrize(
    ("current_hp", "active", "expected"),
    [
        pytest.param(4, True, [ActionType.COMPLETE_TRIGGER], id="living"),
        pytest.param(0, True, [], id="dead"),
        pytest.param(4, False, [], id="dormant"),
    ],
)
def test_trigger_actions_require_a_living_active_creature(
    current_hp: int, active: bool, expected: list[ActionType]
) -> None:
    trigger = ActivationTrigger(
        definition=TriggerDefinition(
            id="combat",
            on=EventCondition(EventType.COMBAT_STARTED),
            until=EventCondition(EventType.COMBAT_ENDED),
        ),
        armed=True,
        active=True,
    )
    creature = Creature(
        id="c1",
        name="Wolf",
        location_id="forest",
        current_hp=current_hp,
        active=active,
        triggers=[trigger],
    )

    assert TriggerActionProvider().get_action_types(creature, ActionContext(is_combat=False)) == expected
