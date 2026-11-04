"""Rejections from speech and Lay on Hands handlers must not change state or emit events."""

from __future__ import annotations

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Character, CharClass, Entity, Race
from dnd_simulator.core.class_features import PaladinFeatures
from dnd_simulator.core.models import ActionResult, EmitFn, Event
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.world import World
from dnd_simulator.rules.handlers.items import handle_lay_on_hands, handle_say
from dnd_simulator.rules.validation import ActionContext


@pytest.fixture
def paladin() -> Character:
    return Character(
        id="paladin",
        name="Paladin",
        location_id="arena",
        max_hp=25,
        current_hp=20,
        ac=18,
        race=Race.HUMAN,
        char_class=CharClass.PALADIN,
        class_features=[PaladinFeatures()],
        resource_pools=[ResourcePool("lay_on_hands", 5, 5, RestType.LONG_REST)],
    )


@pytest.fixture
def events() -> list[Event]:
    return []


@pytest.fixture
def emit_fn(events: list[Event]) -> EmitFn:
    def emit(event: Event) -> ActionResult:
        events.append(event)
        return ActionResult()

    return emit


@pytest.mark.parametrize("params", [{}, {"text": ""}, {"text": "   "}, {"text": "\t\n"}])
def test_say_rejects_missing_or_blank_text(
    params: dict[str, object], paladin: Character, emit_fn: EmitFn, events: list[Event]
) -> None:
    result = handle_say(
        paladin, Action(name=ActionType.SAY, params=params), emit_fn, ActionContext(is_combat=False), World([])
    )

    assert result.success is False
    assert result.error == "Nothing to say (text is empty)"
    assert events == []


@pytest.mark.parametrize("amount", [0, -1, "0", "-2"])
def test_lay_on_hands_rejects_nonpositive_amount(
    amount: int | str, paladin: Character, emit_fn: EmitFn, events: list[Event]
) -> None:
    result = handle_lay_on_hands(
        paladin,
        Action(name=ActionType.LAY_ON_HANDS, params={"amount": amount}),
        emit_fn,
        ActionContext(is_combat=False),
        World([]),
    )

    assert result.success is False
    assert result.error == "Amount must be at least 1"
    assert paladin.current_hp == 20
    assert paladin.resource_pools[0].current_uses == 5
    assert events == []


def test_lay_on_hands_rejects_missing_pool(paladin: Character, emit_fn: EmitFn, events: list[Event]) -> None:
    paladin.resource_pools.clear()
    result = handle_lay_on_hands(
        paladin,
        Action(name=ActionType.LAY_ON_HANDS, params={"amount": 1}),
        emit_fn,
        ActionContext(is_combat=False),
        World([]),
    )

    assert result.success is False
    assert result.error == "No lay_on_hands pool"
    assert paladin.current_hp == 20
    assert paladin.resource_pools == []
    assert events == []


def test_lay_on_hands_rejects_target_without_resolver(paladin: Character, emit_fn: EmitFn, events: list[Event]) -> None:
    result = handle_lay_on_hands(
        paladin,
        Action(name=ActionType.LAY_ON_HANDS, params={"amount": 1, "target_id": "ally"}),
        emit_fn,
        ActionContext(is_combat=False),
        World([]),
    )

    assert result.success is False
    assert result.error == "Cannot resolve target"
    assert paladin.current_hp == 20
    assert paladin.resource_pools[0].current_uses == 5
    assert events == []


@pytest.mark.parametrize(
    "target",
    [
        pytest.param(None, id="missing"),
        pytest.param(Entity(id="target", name="Statue", location_id="arena"), id="non-creature"),
    ],
)
def test_lay_on_hands_rejects_missing_or_non_creature_target(
    target: Entity | None, paladin: Character, emit_fn: EmitFn, events: list[Event]
) -> None:
    entities = {"target": target}
    result = handle_lay_on_hands(
        paladin,
        Action(name=ActionType.LAY_ON_HANDS, params={"amount": 1, "target_id": "target"}),
        emit_fn,
        ActionContext(is_combat=False, get_entity=entities.get),
        World([]),
    )

    assert result.success is False
    assert result.error == "Target 'target' not found"
    assert paladin.current_hp == 20
    assert paladin.resource_pools[0].current_uses == 5
    assert events == []
