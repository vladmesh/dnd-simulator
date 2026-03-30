"""Movement action handlers — move, move_to, dash, disengage, wait."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.combat import Position
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.rules.modifiers import effective_speed
from dnd_simulator.rules.movement import compute_reachable, grid_distance, move_direction, step_cost
from dnd_simulator.rules.reactions import find_oa_triggers

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="action")


def _get_combatants(ctx: ActionContext) -> list[Creature]:
    """Get all creatures in the current combat from ActionContext."""
    from dnd_simulator.core.character import Creature as CreatureType

    if ctx.combat_state is None or ctx.get_entity is None:
        return []
    result: list[CreatureType] = []
    for eid in ctx.combat_state.turn_order:
        entity = ctx.get_entity(eid)
        if isinstance(entity, CreatureType):
            result.append(entity)
    return result


def handle_move(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Move in a compass direction. In combat, resolves movement directly with OA checks."""
    if "direction" not in action.params:
        return ActionResult(success=False, error="Move requires a direction")
    direction = str(action.params["direction"])
    ft = int(str(action.params.get("ft", 5)))
    logger.info("move", direction=direction, ft=ft)

    # In combat with OA callback: resolve directly (not via event)
    if ctx.combat_state is not None and ctx.on_leave_reach is not None:
        bm = ctx.combat_state.battle_map
        cur_pos = bm.get_position(actor.id)
        if cur_pos is None:
            return ActionResult(success=False, error="Not on the battle map")

        new_pos = move_direction(cur_pos, direction, ft, bm, actor.id)
        if new_pos == cur_pos:
            return ActionResult(success=False, error="Cannot move there — blocked")

        # Check OA triggers
        triggers = find_oa_triggers([cur_pos, new_pos], actor, _get_combatants(ctx), bm)
        for _step_idx, reactors in triggers:
            alive = ctx.on_leave_reach(actor, cur_pos, new_pos, reactors)
            if not alive:
                return ActionResult()

        bm.set_position(actor.id, new_pos)
        moved_ft = grid_distance(cur_pos, new_pos)

        emit_fn(
            Event(
                event_type=EventType.ENTITY_MOVE,
                source_layer="entities",
                data={
                    "entity_id": actor.id,
                    "from_x": cur_pos.x,
                    "from_y": cur_pos.y,
                    "to_x": new_pos.x,
                    "to_y": new_pos.y,
                    "distance_ft": moved_ft,
                },
            )
        )
        return ActionResult()

    # Non-combat or no OA callback: emit event for CombatManager resolution
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
    Finds a path, walks it step-by-step checking for opportunity attacks
    at each step. Movement stops if the mover dies from an OA.
    """
    budget = ctx.turn_budget
    if budget is None or budget.movement_remaining <= 0:
        return ActionResult(success=False, error="No movement remaining")

    combat_state = ctx.combat_state
    if combat_state is None:
        return ActionResult(success=False, error="Not in combat")

    bm = combat_state.battle_map
    start_pos = bm.get_position(actor.id)
    if start_pos is None:
        return ActionResult(success=False, error="Not on the battle map")

    target_x = int(str(action.params["x"]))
    target_y = int(str(action.params["y"]))
    target = Position(target_x, target_y)

    if target == start_pos:
        return ActionResult(success=False, error="Already at that position")

    reachable = compute_reachable(start_pos, budget.movement_remaining, bm, actor.id)
    path = reachable.get(target)
    if not path:
        return ActionResult(success=False, error="No path to target")

    # Walk step-by-step, checking OA triggers at each step
    combatants = _get_combatants(ctx)
    cur_pos = path[0]
    spent = 0
    diag_count = 0

    for next_pos in path[1:]:
        cost, diag_count = step_cost(cur_pos, next_pos, diag_count)
        if spent + cost > budget.movement_remaining:
            break

        # Check OA triggers before moving to next_pos
        if ctx.on_leave_reach is not None:
            triggers = find_oa_triggers([cur_pos, next_pos], actor, combatants, bm)
            for _step_idx, reactors in triggers:
                alive = ctx.on_leave_reach(actor, cur_pos, next_pos, reactors)
                if not alive:
                    # Mover died — stay at current position
                    budget.movement_remaining -= spent
                    return ActionResult()

        cur_pos = next_pos
        spent += cost
        bm.set_position(actor.id, cur_pos)

    if cur_pos == start_pos:
        return ActionResult(success=False, error="Cannot move — insufficient budget")

    budget.movement_remaining -= spent
    moved_ft = grid_distance(start_pos, cur_pos)

    logger.info(
        "move_to", entity_id=actor.id, from_pos=(start_pos.x, start_pos.y), to_pos=(cur_pos.x, cur_pos.y), ft=moved_ft
    )

    # Emit log event for combat history
    emit_fn(
        Event(
            event_type=EventType.ENTITY_MOVE,
            source_layer="entities",
            data={
                "entity_id": actor.id,
                "from_x": start_pos.x,
                "from_y": start_pos.y,
                "to_x": cur_pos.x,
                "to_y": cur_pos.y,
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
