"""Trade action handlers — buy, sell."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.i18n import _

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Character, Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="action")


def _resolve_merchant(merchant_id: str, ctx: ActionContext) -> Character | None:
    """Look up merchant NPC via context entity lookup."""
    from dnd_simulator.core.character import Character as _Character

    if ctx.get_entity is None:
        return None
    entity = ctx.get_entity(merchant_id)
    if isinstance(entity, _Character) and entity.is_merchant:
        return entity
    return None


def handle_buy(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Buy an item from a merchant."""
    from dnd_simulator.core.character import Character
    from dnd_simulator.rules.trade import execute_buy, validate_buy

    merchant_id = str(action.params["merchant_id"])
    item_id = str(action.params["item_id"])

    merchant = _resolve_merchant(merchant_id, ctx)
    if merchant is None:
        return ActionResult(success=False, error=_("Merchant '{id}' not found").format(id=merchant_id))

    if not isinstance(actor, Character):
        return ActionResult(success=False, error=_("Only characters can trade"))

    error = validate_buy(buyer=actor, seller=merchant, item_id=item_id)
    if error is not None:
        return ActionResult(success=False, error=error)

    item = next(i for i in merchant.inventory if i.id == item_id)
    execute_buy(buyer=actor, seller=merchant, item=item)

    logger.info("buy", buyer=actor.id, merchant=merchant_id, item=item.name, price=item.price)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_BUY,
            source_layer="entities",
            data={
                "buyer_id": actor.id,
                "merchant_id": merchant_id,
                "item_id": item_id,
                "item_name": item.name,
                "price": item.price,
            },
        )
    )
    return ActionResult()


def handle_sell(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Sell an item to a merchant."""
    from dnd_simulator.core.character import Character
    from dnd_simulator.rules.trade import execute_sell, validate_sell

    merchant_id = str(action.params["merchant_id"])
    item_id = str(action.params["item_id"])

    merchant = _resolve_merchant(merchant_id, ctx)
    if merchant is None:
        return ActionResult(success=False, error=_("Merchant '{id}' not found").format(id=merchant_id))

    if not isinstance(actor, Character):
        return ActionResult(success=False, error=_("Only characters can trade"))

    error = validate_sell(seller=actor, buyer=merchant, item_id=item_id)
    if error is not None:
        return ActionResult(success=False, error=error)

    item = next(i for i in actor.inventory if i.id == item_id)
    execute_sell(seller=actor, buyer=merchant, item=item)

    logger.info("sell", seller=actor.id, merchant=merchant_id, item=item.name, price=item.price)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_SELL,
            source_layer="entities",
            data={
                "seller_id": actor.id,
                "merchant_id": merchant_id,
                "item_id": item_id,
                "item_name": item.name,
                "price": item.price,
            },
        )
    )
    return ActionResult()
