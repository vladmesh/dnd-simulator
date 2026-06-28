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
from dnd_simulator.core.action_defs import get_action_def
from dnd_simulator.core.models import ActionResult
from dnd_simulator.core.world import World
from dnd_simulator.rules.action_provider import (
    BaseActionProvider,
    ClassFeatureActionProvider,
    EquipmentActionProvider,
    InventoryActionProvider,
    LootActionProvider,
    MerchantActionProvider,
    NearbyLootablesFn,
    NearbyMerchantsFn,
    WeaponActionProvider,
)
from dnd_simulator.rules.actions import action_cost
from dnd_simulator.rules.handlers import (
    handle_action_surge,
    handle_attack,
    handle_bless,
    handle_buy,
    handle_dash,
    handle_disengage,
    handle_dodge,
    handle_equip,
    handle_equip_armor,
    handle_equip_feet,
    handle_equip_head,
    handle_equip_ring,
    handle_equip_shield,
    handle_flee,
    handle_idle,
    handle_lay_on_hands,
    handle_long_rest,
    handle_move,
    handle_move_to,
    handle_opportunity_attack,
    handle_say,
    handle_second_wind,
    handle_sell,
    handle_short_rest,
    handle_take,
    handle_unequip,
    handle_unequip_armor,
    handle_unequip_feet,
    handle_unequip_head,
    handle_unequip_ring,
    handle_unequip_shield,
    handle_use_item,
    handle_wait,
)
from dnd_simulator.rules.validation import ActionContext, validate_action

if TYPE_CHECKING:
    from dnd_simulator.core.character import Character, Creature
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
        Raises ValueError if a required param declared in ActionDef is missing.
        """
        # 1. Required-param check (fail fast before validation/handler).
        action_def = get_action_def(action.name)
        for p in action_def.params:
            if p.required and p.name not in action.params:
                raise ValueError(f"Action {action.name} missing required param: {p.name}")

        # 2. Full validation chain (alive, active, mode, budget, item, target, reach)
        error = validate_action(actor, action, ctx)
        if error:
            return ActionResult(success=False, error=error.message)

        # 2. Execute handler
        handler = self._handlers[action.name]  # KeyError = unknown action = bug
        result = handler(actor, action, emit_fn, ctx, self._world)

        # 3. Consume budget only on success
        cost = action_cost(action, creature=actor)
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
    dispatcher.register(ActionType.MOVE_TO, handle_move_to)
    dispatcher.register(ActionType.DASH, handle_dash)
    dispatcher.register(ActionType.DISENGAGE, handle_disengage)
    dispatcher.register(ActionType.WAIT, handle_wait)
    dispatcher.register(ActionType.USE_ITEM, handle_use_item)
    dispatcher.register(ActionType.BLESS, handle_bless)
    dispatcher.register(ActionType.EQUIP, handle_equip)
    dispatcher.register(ActionType.UNEQUIP, handle_unequip)
    dispatcher.register(ActionType.EQUIP_ARMOR, handle_equip_armor)
    dispatcher.register(ActionType.UNEQUIP_ARMOR, handle_unequip_armor)
    dispatcher.register(ActionType.EQUIP_SHIELD, handle_equip_shield)
    dispatcher.register(ActionType.UNEQUIP_SHIELD, handle_unequip_shield)
    dispatcher.register(ActionType.EQUIP_HEAD, handle_equip_head)
    dispatcher.register(ActionType.UNEQUIP_HEAD, handle_unequip_head)
    dispatcher.register(ActionType.EQUIP_FEET, handle_equip_feet)
    dispatcher.register(ActionType.UNEQUIP_FEET, handle_unequip_feet)
    dispatcher.register(ActionType.EQUIP_RING, handle_equip_ring)
    dispatcher.register(ActionType.UNEQUIP_RING, handle_unequip_ring)
    dispatcher.register(ActionType.SECOND_WIND, handle_second_wind)
    dispatcher.register(ActionType.ACTION_SURGE, handle_action_surge)
    dispatcher.register(ActionType.LAY_ON_HANDS, handle_lay_on_hands)
    dispatcher.register(ActionType.TAKE, handle_take)
    dispatcher.register(ActionType.BUY, handle_buy)
    dispatcher.register(ActionType.SELL, handle_sell)
    dispatcher.register(ActionType.LONG_REST, handle_long_rest)
    dispatcher.register(ActionType.SHORT_REST, handle_short_rest)
    dispatcher.register(ActionType.OPPORTUNITY_ATTACK, handle_opportunity_attack)

    # Register providers — base types exclude provider-managed actions
    base_types = frozenset(at for at in dispatcher._handlers if not get_action_def(at).provider_managed)
    dispatcher.add_provider(BaseActionProvider(base_types))
    dispatcher.add_provider(InventoryActionProvider())
    dispatcher.add_provider(EquipmentActionProvider())
    dispatcher.add_provider(WeaponActionProvider())
    dispatcher.add_provider(ClassFeatureActionProvider())
    dispatcher.add_provider(MerchantActionProvider(_build_nearby_merchants_fn(world)))
    dispatcher.add_provider(LootActionProvider(_build_nearby_lootables_fn(world)))

    return dispatcher


def _build_nearby_merchants_fn(world: World) -> NearbyMerchantsFn:
    """Build a callable that returns merchant NPCs at a given location."""
    from dnd_simulator.layers.entities.layer import EntitiesLayer
    from dnd_simulator.layers.entities.models import Npc

    # Resolve the entities layer once at creation time
    entities_layer: EntitiesLayer | None = None
    for layer in world.layers:
        if isinstance(layer, EntitiesLayer):
            entities_layer = layer
            break

    def get_nearby_merchants(location_id: str) -> list[Character]:
        if entities_layer is None:
            return []
        hour = world.time.hour
        return [
            e
            for e in entities_layer._entities.values()
            if isinstance(e, Npc)
            and e.is_merchant
            and e.current_location(hour) == location_id
            and e.active
            and e.is_alive
        ]

    return get_nearby_merchants


def _build_nearby_lootables_fn(world: World) -> NearbyLootablesFn:
    """Build a callable that returns lootable holders (corpses, open containers) at a location."""
    from dnd_simulator.core.character import Entity
    from dnd_simulator.layers.entities.layer import EntitiesLayer
    from dnd_simulator.rules.loot import is_lootable

    entities_layer: EntitiesLayer | None = None
    for layer in world.layers:
        if isinstance(layer, EntitiesLayer):
            entities_layer = layer
            break

    def get_nearby_lootables(location_id: str) -> list[Entity]:
        if entities_layer is None:
            return []
        # Corpses are dormant (active=False) — surface by location + lootable state, not activity.
        return [e for e in entities_layer._entities.values() if e.location_id == location_id and is_lootable(e)]

    return get_nearby_lootables
