"""ActionDispatcher — single entry point for all action execution.

Validate → check budget → execute handler → consume budget.
Error = no mutation happened, budget untouched.
Ok = action applied, budget consumed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.world import World
from dnd_simulator.rules.action_handlers import (
    handle_attack,
    handle_dash,
    handle_dodge,
    handle_flee,
    handle_idle,
    handle_move,
    handle_say,
    handle_wait,
)
from dnd_simulator.rules.actions import action_cost
from dnd_simulator.rules.validation import ActionContext, validate_action

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn

logger = logging.getLogger("dnd_simulator.action_dispatcher")

# Handler: receives actor, action, emit_fn, context, world; returns result.
# Preconditions already validated by dispatcher — handler just executes.
ActionHandler = Callable[["Creature", "Action", "EmitFn", ActionContext, World], ActionResult]


class ActionDispatcher:
    """Validate → route → execute. Single entry point for all actions.

    Holds a reference to World — gives handlers access to layers, maps, time.
    """

    def __init__(self, world: World) -> None:
        self._world = world
        self._handlers: dict[ActionType, ActionHandler] = {}

    @property
    def world(self) -> World:
        return self._world

    def register(self, action_name: ActionType, handler: ActionHandler) -> None:
        """Register a handler for an action type."""
        self._handlers[action_name] = handler

    def dispatch(
        self,
        actor: Creature,
        action: Action,
        ctx: ActionContext,
        emit_fn: EmitFn,
    ) -> ActionResult:
        """Validate preconditions → check budget → execute handler → consume budget.

        Raises KeyError if action has no registered handler (programming error).
        """
        # 1. Precondition validation (alive, active, mode)
        error = validate_action(actor, action, ctx)
        if error:
            return ActionResult(success=False, error=error.message)

        # 2. Budget check (combat only)
        cost = action_cost(action)
        if ctx.turn_budget and not ctx.turn_budget.can_afford(cost):
            return ActionResult(success=False, error=f"Insufficient budget for '{action.name}'")

        # 3. Execute handler
        handler = self._handlers[action.name]  # KeyError = unknown action = bug
        result = handler(actor, action, emit_fn, ctx, self._world)

        # 4. Consume budget only on success
        if result.success and ctx.turn_budget:
            ctx.turn_budget.consume(cost)

        return result

    def has_handler(self, action_name: ActionType) -> bool:
        """Check if a handler is registered for this action type."""
        return action_name in self._handlers

    def get_available_actions(self, actor: Creature, ctx: ActionContext) -> list[ActionType]:
        """Return action types available to actor given current context.

        Checks: handler registered, validate_action passes, budget can afford.
        Same logic as dispatch() but without executing — soft filter for awareness.
        """
        available: list[ActionType] = []
        for action_type in self._handlers:
            probe = Action(name=action_type)
            error = validate_action(actor, probe, ctx)
            if error:
                continue
            cost = action_cost(probe)
            if ctx.turn_budget and not ctx.turn_budget.can_afford(cost):
                continue
            available.append(action_type)
        return available


def create_dispatcher(world: World) -> ActionDispatcher:
    """Create an ActionDispatcher with all standard handlers registered."""
    dispatcher = ActionDispatcher(world)
    dispatcher.register(ActionType.IDLE, handle_idle)
    dispatcher.register(ActionType.SAY, handle_say)
    dispatcher.register(ActionType.ATTACK, handle_attack)
    dispatcher.register(ActionType.DODGE, handle_dodge)
    dispatcher.register(ActionType.FLEE, handle_flee)
    dispatcher.register(ActionType.MOVE, handle_move)
    dispatcher.register(ActionType.DASH, handle_dash)
    dispatcher.register(ActionType.WAIT, handle_wait)
    return dispatcher
