"""Loot action handler — take items and gold from a lootable holder."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.i18n import _

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="action")


def handle_take(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Move all items and gold from a lootable holder (corpse/container) to the actor.

    Take-all semantics — selective taking is out of scope. Preconditions
    (existence, location, lootable state) are validated by check_lootable_target;
    the handler re-resolves the target and reuses the transfer_items primitive.
    """
    from dnd_simulator.core.loot import InventoryHolder
    from dnd_simulator.rules.inventory import transfer_items
    from dnd_simulator.rules.loot import is_lootable

    target_id = str(action.params["target_id"])
    target = ctx.get_entity(target_id) if ctx.get_entity is not None else None
    if target is None or not is_lootable(target):
        return ActionResult(success=False, error=_("Target '{target_id}' cannot be looted").format(target_id=target_id))
    assert isinstance(target, InventoryHolder)  # is_lootable ⇒ Creature or Container, both holders

    taken_items = list(target.inventory)
    item_names = [i.name for i in taken_items]
    taken_gold = target.gold
    transfer_items(src=target, dst=actor, items=taken_items, gold=taken_gold)

    logger.info("take", actor=actor.id, target=target_id, items=item_names, gold=taken_gold)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_TAKE,
            source_layer="entities",
            data={
                "actor_id": actor.id,
                "target_id": target_id,
                "item_names": item_names,
                "gold": taken_gold,
            },
        )
    )
    return ActionResult()
