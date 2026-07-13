"""Focused unit tests for rules/handlers/reactions.py — handle_opportunity_attack.

Sprint 012, Phase 4, Task 3.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.handlers.reactions import handle_opportunity_attack
from dnd_simulator.rules.validation import ActionContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creature(id: str, *, hp: int = 20) -> Creature:
    c = Creature(id=id, name=id.capitalize(), location_id="arena", max_hp=hp, current_hp=hp)
    c.turn_budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30, reaction=1)
    return c


def _oa_action(target_id: str) -> Action:
    return Action(name=ActionType.OPPORTUNITY_ATTACK, params={"target_id": target_id})


def _ctx(actor: Creature) -> ActionContext:
    return ActionContext(is_combat=True, current_turn_entity_id=actor.id)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestHandleOpportunityAttack:
    def test_emits_entity_attack_event(self) -> None:
        """OA emits ENTITY_ATTACK_REQUESTED with is_opportunity_attack=True."""
        actor = _creature("guard")
        action = _oa_action("goblin")
        events: list[Event] = []

        def emit_fn(event: Event) -> ActionResult:
            events.append(event)
            return ActionResult(success=True)

        world = MagicMock()
        ctx = _ctx(actor)
        handle_opportunity_attack(actor, action, emit_fn, ctx, world)

        attack_events = [e for e in events if e.event_type == EventType.ENTITY_ATTACK_REQUESTED]
        assert len(attack_events) == 1
        assert attack_events[0].data.attacker_id == "guard"
        assert attack_events[0].data.target_id == "goblin"
        assert attack_events[0].data.is_opportunity_attack is True

    def test_emits_opportunity_attack_log_event(self) -> None:
        """OA emits a separate OPPORTUNITY_ATTACK event for combat log."""
        actor = _creature("guard")
        action = _oa_action("goblin")
        events: list[Event] = []

        def emit_fn(event: Event) -> ActionResult:
            events.append(event)
            return ActionResult(success=True)

        world = MagicMock()
        ctx = _ctx(actor)
        handle_opportunity_attack(actor, action, emit_fn, ctx, world)

        oa_events = [e for e in events if e.event_type == EventType.OPPORTUNITY_ATTACK]
        assert len(oa_events) == 1
        assert oa_events[0].data.attacker_id == "guard"
        assert oa_events[0].data.target_id == "goblin"

    def test_returns_result_from_attack_event(self) -> None:
        """Handler returns the ActionResult from the ENTITY_ATTACK emit."""
        actor = _creature("guard")
        action = _oa_action("goblin")

        expected_result = ActionResult(success=True)

        def emit_fn(event: Event) -> ActionResult:
            if event.event_type == EventType.ENTITY_ATTACK_REQUESTED:
                return expected_result
            return ActionResult()

        world = MagicMock()
        ctx = _ctx(actor)
        result = handle_opportunity_attack(actor, action, emit_fn, ctx, world)

        # The handler returns the result of the first emit (ENTITY_ATTACK)
        assert result is expected_result

    def test_target_id_from_params(self) -> None:
        """Handler reads target_id from action params."""
        actor = _creature("guard")
        action = _oa_action("specific_target")
        events: list[Event] = []

        def emit_fn(event: Event) -> ActionResult:
            events.append(event)
            return ActionResult(success=True)

        world = MagicMock()
        ctx = _ctx(actor)
        handle_opportunity_attack(actor, action, emit_fn, ctx, world)

        attack_events = [e for e in events if e.event_type == EventType.ENTITY_ATTACK_REQUESTED]
        assert attack_events[0].data.target_id == "specific_target"

    def test_source_layer_is_entities(self) -> None:
        """Both events have source_layer='entities'."""
        actor = _creature("guard")
        action = _oa_action("goblin")
        events: list[Event] = []

        def emit_fn(event: Event) -> ActionResult:
            events.append(event)
            return ActionResult(success=True)

        world = MagicMock()
        ctx = _ctx(actor)
        handle_opportunity_attack(actor, action, emit_fn, ctx, world)

        assert all(e.source_layer == "entities" for e in events)
