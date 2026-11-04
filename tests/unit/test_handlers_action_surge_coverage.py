"""Coverage for Action Surge without an active turn."""

from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Character, CharClass, Race
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle
from dnd_simulator.core.models import Event
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.rules.handlers.action_surge import handle_action_surge
from dnd_simulator.rules.validation import ActionContext


def test_action_surge_without_active_turn_preserves_resource() -> None:
    pool = ResourcePool("action_surge", 1, 1, RestType.SHORT_REST)
    actor = Character(
        id="fighter2",
        name="FighterL2",
        location_id="arena",
        max_hp=22,
        current_hp=22,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=2,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        resource_pools=[pool],
    )
    events: list[Event] = []
    ctx = ActionContext(is_combat=True)

    result = handle_action_surge(
        actor,
        Action(name=ActionType.ACTION_SURGE, params={}),
        events.append,
        ctx,
        MagicMock(),
    )

    assert not result.success
    assert result.error == "Action Surge requires an active turn"
    assert pool.current_uses == 1
    assert events == []
