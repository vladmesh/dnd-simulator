"""Combat action handlers — attack, dodge, flee."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.events import AttackRequestedPayload
from dnd_simulator.core.models import ActionResult, Event, EventType

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="action")


def handle_attack(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Attack: emit attack event. CombatManager resolves via handle_event."""
    logger.info("attack", target=str(action.params["target_id"]))
    smite_slot_level = int(str(action.params["smite_slot_level"])) if "smite_slot_level" in action.params else None
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
            data={
                "entity_id": actor.id,
                "description": str(action.params.get("description", "")),
            },
        )
    )
    return ActionResult()


def handle_flee(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Flee: emit flee event."""
    logger.info("flee")
    emit_fn(
        Event(
            event_type=EventType.ENTITY_FLEE,
            source_layer="entities",
            data={
                "entity_id": actor.id,
                "description": str(action.params.get("description", "")),
            },
        )
    )
    return ActionResult()
