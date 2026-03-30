"""Movement action handlers — move, move_to, dash, disengage, wait."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.combat import Position
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.rules.modifiers import effective_speed
from dnd_simulator.rules.movement import compute_reachable, grid_distance, walk_path

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="action")


def handle_move(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Move: emit move event. CombatManager resolves via handle_event."""
    if "direction" not in action.params:
        return ActionResult(success=False, error="Move requires a direction")
    direction = str(action.params["direction"])
    ft = int(str(action.params.get("ft", 5)))
    logger.info("move", direction=direction, ft=ft)
    return emit_fn(
        Event(
            event_type=EventType.ENTITY_MOVE,
            source_layer="entities",
            data={"entity_id": actor.id, "direction": str(direction), "ft": ft},
        )
    )


def handle_move_to(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Move to a specific (x, y) position via BFS pathfinding.

    Player-only action triggered by clicking the battle map grid.
    Finds a path, walks it spending movement budget, updates battle map position.
    """
    budget = ctx.turn_budget
    if budget is None or budget.movement_remaining <= 0:
        return ActionResult(success=False, error="No movement remaining")

    combat_state = ctx.combat_state
    if combat_state is None:
        return ActionResult(success=False, error="Not in combat")

    bm = combat_state.battle_map
    cur_pos = bm.get_position(actor.id)
    if cur_pos is None:
        return ActionResult(success=False, error="Not on the battle map")

    target_x = int(str(action.params["x"]))
    target_y = int(str(action.params["y"]))
    target = Position(target_x, target_y)

    if target == cur_pos:
        return ActionResult(success=False, error="Already at that position")

    reachable = compute_reachable(cur_pos, budget.movement_remaining, bm, actor.id)
    path = reachable.get(target)
    if not path:
        return ActionResult(success=False, error="No path to target")

    final_pos, feet_spent = walk_path(path, budget.movement_remaining)

    if final_pos == cur_pos:
        return ActionResult(success=False, error="Cannot move — insufficient budget")

    bm.set_position(actor.id, final_pos)
    budget.movement_remaining -= feet_spent
    moved_ft = grid_distance(cur_pos, final_pos)

    logger.info(
        "move_to", entity_id=actor.id, from_pos=(cur_pos.x, cur_pos.y), to_pos=(final_pos.x, final_pos.y), ft=moved_ft
    )

    # Emit log event for combat history
    emit_fn(
        Event(
            event_type=EventType.ENTITY_MOVE,
            source_layer="entities",
            data={
                "entity_id": actor.id,
                "from_x": cur_pos.x,
                "from_y": cur_pos.y,
                "to_x": final_pos.x,
                "to_y": final_pos.y,
                "distance_ft": moved_ft,
            },
        )
    )
    return ActionResult()


def handle_dash(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Dash: adds creature's effective speed to movement budget.

    Budget cost (1 action) is handled by the dispatcher; this handler only
    applies the movement bonus and emits an ENTITY_DASH event for the log.
    """
    budget = ctx.turn_budget
    if budget is None:
        return ActionResult(success=False, error="Dash requires a turn budget")
    speed = effective_speed(actor)
    budget.movement_remaining += speed
    logger.info("dash", extra_movement_ft=speed)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_DASH,
            source_layer="entities",
            data={"entity_id": actor.id, "extra_movement_ft": speed},
        )
    )
    return ActionResult()


def handle_disengage(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Disengage: movement doesn't provoke opportunity attacks this turn.

    Sets is_disengaging flag so OA triggers skip this creature.
    Budget cost is handled by the dispatcher.
    """
    actor.is_disengaging = True
    logger.info("disengage", entity_id=actor.id)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_DISENGAGE,
            source_layer="entities",
            data={"entity_id": actor.id},
        )
    )
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
        hours = int(str(action.params.get("hours", 1)))
        if hours > 0:
            now = world.time.to_total_seconds()
            actor.wake_at_seconds = now + hours * 3600
            actor.active = False
            logger.info("wait_sleep", hours=hours, wake_at=actor.wake_at_seconds)
    return ActionResult()
