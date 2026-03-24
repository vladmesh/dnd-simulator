"""Action handlers — pure functions that execute a single action type.

Each handler has the signature:
    (actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult

Handlers do NOT check preconditions — the dispatcher already validated.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.rules.conditions import effective_speed
from dnd_simulator.rules.dice import roll

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = logging.getLogger("dnd_simulator.action_handlers")


def handle_idle(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Idle: optionally inspect a target, otherwise do nothing."""
    inspect_target = action.params.get("inspect_target") if action.params else None
    if inspect_target:
        logger.info("[%s] → inspect %s", actor.name, inspect_target)
        emit_fn(
            Event(
                event_type=EventType.CUSTOM,
                source_layer="entities",
                data={
                    "entity_id": actor.id,
                    "inspect_target": str(inspect_target),
                },
            )
        )
    else:
        logger.info("[%s] → idle", actor.name)
    return ActionResult()


def handle_say(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Say: emit speech event."""
    emit_fn(
        Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data={"entity_id": actor.id, "text": action.params.get("text", "")},
        )
    )
    return ActionResult()


def handle_attack(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Attack: emit attack event. CombatManager resolves via handle_event."""
    return emit_fn(
        Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={
                "attacker_id": actor.id,
                "target_id": action.params.get("target_id", ""),
            },
        )
    )


def handle_dodge(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Dodge: emit dodge event."""
    logger.info("[%s] → dodge", actor.name)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data={
                "entity_id": actor.id,
                "description": action.params.get("description", ""),
            },
        )
    )
    return ActionResult()


def handle_flee(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Flee: emit flee event."""
    logger.info("[%s] → flee", actor.name)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={
                "entity_id": actor.id,
                "description": action.params.get("description", ""),
            },
        )
    )
    return ActionResult()


def handle_move(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Move: emit move event. CombatManager resolves via handle_event."""
    direction = action.params.get("direction", "")
    ft = int(str(action.params.get("ft", 5)))
    logger.info("[%s] → move %s %dft", actor.name, direction, ft)
    return emit_fn(
        Event(
            event_type=EventType.ENTITY_MOVE,
            source_layer="entities",
            data={"entity_id": actor.id, "direction": str(direction), "ft": ft},
        )
    )


def handle_dash(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Dash: no world event. Adds creature's effective speed to movement budget.

    Budget cost (1 action) is handled by the dispatcher; this handler only
    applies the movement bonus.
    """
    budget = ctx.turn_budget
    if budget is None:
        return ActionResult(success=False, error="Dash requires a turn budget")
    speed = effective_speed(actor.speed, actor.conditions)
    budget.movement_remaining += speed
    logger.info("[%s] → dash (+%dft movement)", actor.name, speed)
    return ActionResult()


def handle_wait(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Wait: creature goes dormant until wake_at, or travels to a location.

    Travel: immediate move + time advance.
    Plain wait: set wake_at_seconds, mark dormant. Fast-forward in run_loop
    handles the actual time advancement.
    """
    from dnd_simulator.core.models import TimeDelta

    travel_to = action.params.get("travel_to")
    if travel_to:
        target_id = str(travel_to)
        graph = world.location_graph
        try:
            seconds = graph.travel_seconds(actor.location_id, target_id)
            actor.location_id = target_id
            world.advance_time(TimeDelta(seconds=seconds))
        except ValueError:
            # No direct path — try by name match
            for loc_id in graph.all_ids():
                loc = graph.get(loc_id)
                if loc.name.lower() == target_id.lower():
                    try:
                        seconds = graph.travel_seconds(actor.location_id, loc_id)
                        actor.location_id = loc_id
                        world.advance_time(TimeDelta(seconds=seconds))
                    except ValueError:
                        pass
                    break
    else:
        raw = action.params.get("hours", 1)
        hours = int(str(raw))
        if hours > 0:
            now = world.time.to_total_seconds()
            actor.wake_at_seconds = now + hours * 3600
            actor.active = False
            logger.info(
                "[Wait] %s sleeps for %dh (wake_at=%d)",
                actor.name,
                hours,
                actor.wake_at_seconds,
            )
    return ActionResult()


def _find_item(actor: Creature, item_id: str) -> Item:
    """Find an item in actor's inventory by id. Raises KeyError if not found."""
    for item in actor.inventory:
        if item.id == item_id:
            return item
    raise KeyError(f"Item '{item_id}' not in {actor.name}'s inventory")


def _apply_potion(actor: Creature, item: Item) -> int:
    """Roll heal dice and apply healing. Returns actual HP restored."""
    heal_dice = str(item.params["heal_dice"])
    rolled = roll(heal_dice)
    return actor.heal(rolled)


def handle_use_item(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Use an item from inventory. Consumes the item on success."""
    item_id = str(action.params["item_id"])
    item = _find_item(actor, item_id)

    if item.item_type == ItemType.POTION:
        healed = _apply_potion(actor, item)
        actor.inventory.remove(item)
        logger.info("[%s] → use %s (healed %d HP)", actor.name, item.name, healed)
        emit_fn(
            Event(
                event_type=EventType.ENTITY_USE_ITEM,
                source_layer="entities",
                data={
                    "entity_id": actor.id,
                    "item_id": item_id,
                    "item_name": item.name,
                    "item_type": item.item_type.value,
                    "healed": healed,
                },
            )
        )
        return ActionResult()

    raise RuntimeError(f"Unhandled item type: {item.item_type}")


_BLESS_DURATION_ROUNDS = 3


def handle_bless(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Bless: grant +d4 to attack rolls for several rounds."""
    from dnd_simulator.core.conditions import Condition

    existing = actor.conditions.get(Condition.BLESSED)
    # Don't stack — take max duration (None = permanent > any int)
    if existing is None or (isinstance(existing, int) and existing < _BLESS_DURATION_ROUNDS):
        actor.conditions[Condition.BLESSED] = _BLESS_DURATION_ROUNDS
    logger.info("[%s] → bless (BLESSED for %d rounds)", actor.name, _BLESS_DURATION_ROUNDS)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_BLESS,
            source_layer="entities",
            data={
                "entity_id": actor.id,
                "duration_rounds": _BLESS_DURATION_ROUNDS,
            },
        )
    )
    return ActionResult()
