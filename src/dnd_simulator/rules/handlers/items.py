"""Miscellaneous action handlers — idle, say, use_item, bless, second_wind."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.items import ItemType
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.rules.dice import roll

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.items import Item
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

logger = structlog.get_logger(domain="action")


def handle_idle(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Idle: optionally inspect a target, otherwise do nothing."""
    inspect_target = action.params.get("inspect_target") if action.params else None
    if inspect_target:
        logger.info("inspect", target=str(inspect_target))
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
        logger.info("idle")
    return ActionResult()


def handle_say(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Say: emit speech event."""
    if "text" not in action.params or not str(action.params["text"]).strip():
        return ActionResult(success=False, error="Nothing to say (text is empty)")
    text = str(action.params["text"])
    logger.info("say", text=text[:80])
    emit_fn(
        Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data={"entity_id": actor.id, "text": text},
        )
    )
    return ActionResult()


def _find_item(actor: Creature, item_id: str) -> Item:
    """Find an item in actor's inventory by id. Raises KeyError if not found."""
    for item in actor.inventory:
        if item.id == item_id:
            return item
    raise KeyError(f"Item '{item_id}' not in {actor.name}'s inventory")


def _apply_potion(actor: Creature, item: Item) -> tuple[int, list[dict[str, object]]]:
    """Roll heal dice and apply healing. Returns (actual HP restored, dice_detail)."""
    heal_dice = str(item.params["heal_dice"])
    result = roll(heal_dice)
    healed = actor.heal(result.total)
    dice_detail: list[dict[str, object]] = [{"sides": d.sides, "result": d.result} for d in result.dice]
    return healed, dice_detail


def handle_use_item(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Use an item from inventory. Consumes the item on success."""
    item_id = str(action.params["item_id"])
    item = _find_item(actor, item_id)

    if item.item_type == ItemType.POTION:
        healed, dice_detail = _apply_potion(actor, item)
        actor.inventory.remove(item)
        logger.info("use_item", item=item.name, healed=healed)
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
                    "dice_detail": dice_detail,
                },
            )
        )
        return ActionResult()

    return ActionResult(success=False, error=f"Cannot use item of type '{item.item_type}' — try equipping it instead")


def handle_lay_on_hands(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Lay on Hands: Paladin spends pool HP to heal self or a touched creature."""
    from dnd_simulator.core.character import Character, CharClass
    from dnd_simulator.core.character import Creature as CreatureType
    from dnd_simulator.rules.resources import use_resource

    if not isinstance(actor, Character) or actor.char_class != CharClass.PALADIN:
        return ActionResult(success=False, error="Only Paladins can use Lay on Hands")

    amount = int(str(action.params["amount"]))
    if amount < 1:
        return ActionResult(success=False, error="Amount must be at least 1")

    # Check pool has enough
    pool = next((p for p in actor.resource_pools if p.id == "lay_on_hands"), None)
    if pool is None:
        return ActionResult(success=False, error="No lay_on_hands pool")
    if pool.current_uses < amount:
        return ActionResult(
            success=False,
            error=f"Insufficient pool: {pool.current_uses} remaining, need {amount}",
        )

    # Resolve target
    target_id = action.params.get("target_id")
    if target_id is not None:
        target_id = str(target_id)
        if ctx.get_entity is None:
            return ActionResult(success=False, error="Cannot resolve target")
        target_entity = ctx.get_entity(target_id)
        if target_entity is None or not isinstance(target_entity, CreatureType):
            return ActionResult(success=False, error=f"Target '{target_id}' not found")
        target = target_entity
    else:
        target = actor

    # Spend pool and heal
    use_resource(actor, "lay_on_hands", amount=amount)
    healed = target.heal(amount)

    logger.info("lay_on_hands", target=target.id, amount=amount, healed=healed)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_LAY_ON_HANDS,
            source_layer="entities",
            data={
                "entity_id": actor.id,
                "target_id": target.id,
                "amount": amount,
                "healed": healed,
            },
        )
    )
    return ActionResult()


_BLESS_DURATION_ROUNDS = 3


def handle_bless(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Bless: grant +d4 to attack rolls for several rounds."""
    from dnd_simulator.core.conditions import Condition

    existing = actor.conditions.get(Condition.BLESSED)
    # Don't stack — take max duration (None = permanent > any int)
    if existing is None or (isinstance(existing, int) and existing < _BLESS_DURATION_ROUNDS):
        actor.conditions[Condition.BLESSED] = _BLESS_DURATION_ROUNDS
    logger.info("bless", duration_rounds=_BLESS_DURATION_ROUNDS)
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


def handle_second_wind(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Second Wind: Fighter bonus action — heal 1d10 + level, 1/short rest."""
    from dnd_simulator.core.character import Character
    from dnd_simulator.rules.dice import roll as roll_dice
    from dnd_simulator.rules.resources import use_resource

    if not isinstance(actor, Character):
        return ActionResult(success=False, error="Only characters can use Second Wind")

    use_resource(actor, "second_wind")
    dice_result = roll_dice("1d10")
    healing = dice_result.total + actor.level
    healed = actor.heal(healing)
    dice_detail: list[dict[str, object]] = [{"sides": d.sides, "result": d.result} for d in dice_result.dice]

    logger.info("second_wind", rolled=healing, healed=healed, level=actor.level)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_SECOND_WIND,
            source_layer="entities",
            data={"entity_id": actor.id, "healed": healed, "dice_detail": dice_detail},
        )
    )
    return ActionResult()
