"""ActionDispatcher — single entry point for all action execution.

Validate → execute handler → consume budget.
Error = no mutation happened, budget untouched.
Ok = action applied, budget consumed.

Available actions are determined by ActionProviders — pluggable sources
that declare which action types a creature can perform given its state.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.world import World
from dnd_simulator.rules.action_handlers import (
    handle_attack,
    handle_bless,
    handle_dash,
    handle_dodge,
    handle_equip,
    handle_equip_armor,
    handle_equip_shield,
    handle_flee,
    handle_idle,
    handle_move,
    handle_say,
    handle_unequip,
    handle_unequip_armor,
    handle_unequip_shield,
    handle_use_item,
    handle_wait,
)
from dnd_simulator.rules.action_provider import (
    ArmorEquipmentProvider,
    BaseActionProvider,
    EquipmentActionProvider,
    InventoryActionProvider,
    WeaponActionProvider,
)
from dnd_simulator.rules.actions import action_cost
from dnd_simulator.rules.validation import ActionContext, validate_action

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.rules.action_provider import ActionProvider

logger = structlog.get_logger(domain="action")

# Handler: receives actor, action, emit_fn, context, world; returns result.
# Preconditions already validated by dispatcher — handler just executes.
ActionHandler = Callable[["Creature", "Action", "EmitFn", ActionContext, World], ActionResult]


class ActionDispatcher:
    """Validate → route → execute. Single entry point for all actions.

    Holds a reference to World — gives handlers access to layers, maps, time.
    Available actions are determined by registered ActionProviders.
    """

    def __init__(self, world: World) -> None:
        self._world = world
        self._handlers: dict[ActionType, ActionHandler] = {}
        self._providers: list[ActionProvider] = []

    @property
    def world(self) -> World:
        return self._world

    def register(self, action_name: ActionType, handler: ActionHandler) -> None:
        """Register a handler for an action type."""
        self._handlers[action_name] = handler

    def add_provider(self, provider: ActionProvider) -> None:
        """Add an action provider that contributes to available actions."""
        self._providers.append(provider)

    def dispatch(
        self,
        actor: Creature,
        action: Action,
        ctx: ActionContext,
        emit_fn: EmitFn,
    ) -> ActionResult:
        """Validate all preconditions → execute handler → consume budget.

        Raises KeyError if action has no registered handler (programming error).
        """
        # 1. Full validation chain (alive, active, mode, budget, item, target, reach)
        error = validate_action(actor, action, ctx)
        if error:
            return ActionResult(success=False, error=error.message)

        # 2. Execute handler
        handler = self._handlers[action.name]  # KeyError = unknown action = bug
        result = handler(actor, action, emit_fn, ctx, self._world)

        # 3. Consume budget only on success
        cost = action_cost(action)
        if result.success and ctx.turn_budget:
            ctx.turn_budget.consume(cost)

        return result

    def has_handler(self, action_name: ActionType) -> bool:
        """Check if a handler is registered for this action type."""
        return action_name in self._handlers

    def get_available_actions(self, actor: Creature, ctx: ActionContext) -> list[ActionType]:
        """Return action types available to actor given current context.

        Delegates to registered providers. Each provider returns action types
        it considers available; results are deduplicated and order-preserved.
        """
        seen: set[ActionType] = set()
        result: list[ActionType] = []
        for provider in self._providers:
            for at in provider.get_action_types(actor, ctx):
                if at not in seen:
                    seen.add(at)
                    result.append(at)
        return result


# Provider-managed action types — excluded from BaseActionProvider
_PROVIDER_MANAGED: frozenset[ActionType] = frozenset(
    {
        ActionType.USE_ITEM,
        ActionType.BLESS,
        ActionType.EQUIP,
        ActionType.UNEQUIP,
        ActionType.EQUIP_ARMOR,
        ActionType.UNEQUIP_ARMOR,
        ActionType.EQUIP_SHIELD,
        ActionType.UNEQUIP_SHIELD,
    }
)


def create_dispatcher(world: World) -> ActionDispatcher:
    """Create an ActionDispatcher with all standard handlers and providers."""
    dispatcher = ActionDispatcher(world)

    # Register handlers
    dispatcher.register(ActionType.IDLE, handle_idle)
    dispatcher.register(ActionType.SAY, handle_say)
    dispatcher.register(ActionType.ATTACK, handle_attack)
    dispatcher.register(ActionType.DODGE, handle_dodge)
    dispatcher.register(ActionType.FLEE, handle_flee)
    dispatcher.register(ActionType.MOVE, handle_move)
    dispatcher.register(ActionType.DASH, handle_dash)
    dispatcher.register(ActionType.WAIT, handle_wait)
    dispatcher.register(ActionType.USE_ITEM, handle_use_item)
    dispatcher.register(ActionType.BLESS, handle_bless)
    dispatcher.register(ActionType.EQUIP, handle_equip)
    dispatcher.register(ActionType.UNEQUIP, handle_unequip)
    dispatcher.register(ActionType.EQUIP_ARMOR, handle_equip_armor)
    dispatcher.register(ActionType.UNEQUIP_ARMOR, handle_unequip_armor)
    dispatcher.register(ActionType.EQUIP_SHIELD, handle_equip_shield)
    dispatcher.register(ActionType.UNEQUIP_SHIELD, handle_unequip_shield)

    # Register providers
    base_types = frozenset(dispatcher._handlers) - _PROVIDER_MANAGED
    dispatcher.add_provider(BaseActionProvider(base_types))
    dispatcher.add_provider(InventoryActionProvider())
    dispatcher.add_provider(EquipmentActionProvider())
    dispatcher.add_provider(ArmorEquipmentProvider())
    dispatcher.add_provider(WeaponActionProvider())

    return dispatcher
