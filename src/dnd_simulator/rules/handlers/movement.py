"""Movement action handlers — move, move_to, dash, disengage, wait."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.combat import Position
from dnd_simulator.core.events import EntityActorPayload, EntityDashPayload, EntityMovePayload
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.i18n import _
from dnd_simulator.rules.action_params import integer_param
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
        return ActionResult(success=False, error=_("Move requires a direction"))
    direction = str(action.params["direction"])
    ft = integer_param(action, "ft", default=5)
    logger.info("move", direction=direction, ft=ft)

    # In combat with OA callback: resolve directly (not via event)
    if ctx.combat_state is not None and ctx.on_leave_reach is not None:
        bm = ctx.combat_state.battle_map
        cur_pos = bm.get_position(actor.id)
        if cur_pos is None:
            return ActionResult(success=False, error=_("Not on the battle map"))

        new_pos = move_direction(cur_pos, direction, ft, bm, actor.id)
        if new_pos == cur_pos:
            return ActionResult(success=False, error=_("Cannot move there, blocked"))

        # Grid distance of this single compass step (no diagonal 5/10 alternation, unlike MOVE_TO — fine per step).
        moved_ft = grid_distance(cur_pos, new_pos)

        # Movement budget lives here, not in the dispatcher (MOVE is cost_type=FREE). Reject the whole
        # step if it can't be paid for — no partial placement, so the mover never lands where it can't afford.
        budget = ctx.turn_budget
        if budget is not None and moved_ft > budget.movement_remaining:
            return ActionResult(success=False, error=_("Not enough movement"))

        # Check OA triggers
        triggers = find_oa_triggers([cur_pos, new_pos], actor, _get_combatants(ctx), bm, ctx.combat_state)
        for _step_idx, reactors in triggers:
            alive = ctx.on_leave_reach(actor, cur_pos, new_pos, reactors)
            if not alive:
                # Mover died mid-step: nothing committed, so no budget spent.
                return ActionResult()

        bm.set_position(actor.id, new_pos)
        if budget is not None:
            budget.movement_remaining -= moved_ft

        emit_fn(
            Event(
                event_type=EventType.ENTITY_MOVE,
                source_layer="entities",
                data=EntityMovePayload(
                    actor.id, actor.location_id, cur_pos.x, cur_pos.y, new_pos.x, new_pos.y, moved_ft
                ),
            )
        )
        return ActionResult()

    # Non-combat or no OA callback: emit event for CombatManager resolution
    return emit_fn(
        Event(
            event_type=EventType.ENTITY_MOVE,
            source_layer="entities",
            data=EntityMovePayload(actor.id, actor.location_id, direction=str(direction), ft=ft),
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
        return ActionResult(success=False, error=_("No movement remaining"))

    combat_state = ctx.combat_state
    if combat_state is None:
        return ActionResult(success=False, error=_("Not in combat"))

    bm = combat_state.battle_map
    start_pos = bm.get_position(actor.id)
    if start_pos is None:
        return ActionResult(success=False, error=_("Not on the battle map"))

    target_x = integer_param(action, "x")
    target_y = integer_param(action, "y")
    target = Position(target_x, target_y)

    if target == start_pos:
        return ActionResult(success=False, error=_("Already at that position"))

    reachable = compute_reachable(start_pos, budget.movement_remaining, bm, actor.id)
    path = reachable.get(target)
    if not path:
        # Distinguish "sealed off by walls" from "reachable but past this turn's budget" so the
        # brain/player gets an actionable reason. Only pay the extra Dijkstra on the failure path.
        unbounded = compute_reachable(start_pos, bm.width * bm.height * 15, bm, actor.id)
        if target in unbounded:
            return ActionResult(success=False, error=_("Not enough movement to reach there"))
        return ActionResult(success=False, error=_("No path to target"))

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
            triggers = find_oa_triggers([cur_pos, next_pos], actor, combatants, bm, ctx.combat_state)
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
        return ActionResult(success=False, error=_("Cannot move, insufficient budget"))

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
            data=EntityMovePayload(
                actor.id, actor.location_id, start_pos.x, start_pos.y, cur_pos.x, cur_pos.y, moved_ft
            ),
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
        return ActionResult(success=False, error=_("Dash requires a turn budget"))
    speed = effective_speed(actor)
    budget.movement_remaining += speed
    logger.info("dash", extra_movement_ft=speed)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_DASH,
            source_layer="entities",
            data=EntityDashPayload(actor.id, speed),
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
            data=EntityActorPayload(actor.id),
        )
    )
    return ActionResult()


def handle_wait(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Wait in place until the requested wake boundary."""
    from dnd_simulator.core.intent import IntentType, TimedIntent

    hours = integer_param(action, "hours", default=1)
    if hours > 0:
        now = world.time.to_total_seconds()
        actor.current_intent = TimedIntent(IntentType.WAIT, now, now + hours * 3600)
        actor.active = False
        logger.info("wait_sleep", hours=hours, wake_at=actor.current_intent.wake_at_seconds)
    return ActionResult()


def handle_travel(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Start a persisted journey without moving or advancing world time inline."""
    from dnd_simulator.core.intent import TravelIntent

    destination_raw = action.params.get("destination_id")
    if destination_raw is None:
        return ActionResult(success=False, error=_("Travel requires a destination"))
    destination_id = str(destination_raw)
    try:
        route = world.location_graph.shortest_route(actor.location_id, destination_id)
    except ValueError:
        return ActionResult(success=False, error=_("No route to destination"))
    if not route:
        return ActionResult(success=False, error=_("Already at destination"))

    now = world.time.to_total_seconds()
    next_arrival = now + world.location_graph.travel_seconds(actor.location_id, route[0])
    actor.current_intent = TravelIntent(now, destination_id, route, next_arrival)
    actor.active = False
    logger.info(
        "travel_start",
        entity_id=actor.id,
        destination_id=destination_id,
        route=route,
        next_arrival=next_arrival,
    )
    return ActionResult()
