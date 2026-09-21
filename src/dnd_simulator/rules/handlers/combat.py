"""Combat action handlers — attack, dodge, flee."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import ActionRejectedError
from dnd_simulator.core.events import ActionFlavorPayload, AttackRequestedPayload, EntityFleePayload
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.i18n import _
from dnd_simulator.rules.action_params import integer_param

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.awareness import FleeDestination
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="action")


def handle_attack(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Attack: emit attack event. CombatManager resolves via handle_event."""
    logger.info("attack", target=str(action.params["target_id"]))
    smite_slot_level = integer_param(action, "smite_slot_level") if "smite_slot_level" in action.params else None
    return emit_fn(
        Event(
            event_type=EventType.ENTITY_ATTACK_REQUESTED,
            source_layer="entities",
            data=AttackRequestedPayload(actor.id, str(action.params["target_id"]), smite_slot_level),
        )
    )


def handle_dodge(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Dodge: emit dodge event."""
    logger.info("dodge")
    emit_fn(
        Event(
            event_type=EventType.ENTITY_DODGE,
            source_layer="entities",
            data=ActionFlavorPayload(actor.id, str(action.params.get("description", ""))),
        )
    )
    return ActionResult()


def handle_flee(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Flee: leave the fight and the scene along one edge to a neighbouring location.

    Eligibility (no enemy within 15 ft) is already enforced by validation. Here the
    destination is fixed: a player must name an adjacent location; an NPC picks one
    by rule. The entities layer resolves the event — the exit itself happens there.
    """
    from dnd_simulator.core.player import PlayerCharacter
    from dnd_simulator.rules.flee import flee_destinations

    graph = world.location_graph
    destinations = flee_destinations(graph, actor.location_id)
    raw_destination = action.params.get("destination_id")
    if raw_destination is None:
        if isinstance(actor, PlayerCharacter):
            raise ActionRejectedError(_("Choose a neighbouring location to flee to"))
        destination_id = _npc_flee_destination(actor, destinations, ctx, world)
        if destination_id is None:
            raise ActionRejectedError(_("There is nowhere to flee"))
    else:
        destination_id = str(raw_destination)
    destination = next((d for d in destinations if d.id == destination_id), None)
    if destination is None:
        raise ActionRejectedError(_("You can only flee to a neighbouring location"))

    now = world.time.to_total_seconds()
    logger.info("flee", destination_id=destination.id, travel_seconds=destination.travel_seconds)
    return emit_fn(
        Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data=EntityFleePayload(
                entity_id=actor.id,
                destination_id=destination.id,
                departed_at_seconds=now,
                arrival_at_seconds=now + destination.travel_seconds,
                destination_name=destination.name,
                entity_name=actor.name,
                description=str(action.params.get("description", "")),
            ),
        )
    )


def _npc_flee_destination(
    actor: Creature, destinations: tuple[FleeDestination, ...], ctx: ActionContext, world: World
) -> str | None:
    """Towards home when there is one, else away from the enemies of this fight."""
    from dnd_simulator.core.character import Creature as CreatureType
    from dnd_simulator.rules.flee import choose_flee_destination, is_enemy

    home_first_hop: str | None = None
    # Named NPCs carry a daily schedule (``Npc.scheduled_location``); rules/ must not
    # import the entities layer, so the schedule is read structurally.
    scheduled_location = getattr(actor, "scheduled_location", None)
    if callable(scheduled_location):
        home = str(scheduled_location(world.time.hour))
        if home != actor.location_id:
            try:
                route = world.location_graph.shortest_route(actor.location_id, home)
            except ValueError:
                route = ()
            home_first_hop = route[0] if route else None

    enemy_factions: set[str] = set()
    combat = ctx.combat_state
    if combat is not None and ctx.get_entity is not None:
        for other_id in combat.turn_order:
            other = ctx.get_entity(other_id)
            if (
                isinstance(other, CreatureType)
                and other.id != actor.id
                and other.faction_id
                and is_enemy(combat, actor, other)
            ):
                enemy_factions.add(other.faction_id)
    presence: dict[str, int] = {}
    for creature in world.creature_host.get_active_creatures():
        if creature.is_alive and creature.faction_id in enemy_factions:
            presence[creature.location_id] = presence.get(creature.location_id, 0) + 1
    return choose_flee_destination(destinations, home_first_hop, presence)
