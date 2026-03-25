"""Action handlers — pure functions that execute a single action type.

Each handler has the signature:
    (actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult

Handlers do NOT check preconditions — the dispatcher already validated.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.items import EquipmentSlot, Item, ItemType
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.rules.dice import roll
from dnd_simulator.rules.modifiers import effective_speed

if TYPE_CHECKING:
    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.layers.entities.models import Npc
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
    logger.info("say", text=str(action.params.get("text", ""))[:80])
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
    logger.info("attack", target=str(action.params.get("target_id", "")))
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
    logger.info("dodge")
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
    logger.info("flee")
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
    logger.info("move", direction=direction, ft=ft)
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
    speed = effective_speed(actor)
    budget.movement_remaining += speed
    logger.info("dash", extra_movement_ft=speed)
    return ActionResult()


def handle_disengage(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Disengage: movement doesn't provoke opportunity attacks this turn.

    Currently a no-op since opportunity attacks aren't implemented.
    Budget cost is handled by the dispatcher.
    """
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
        raw = action.params.get("hours", 1)
        hours = int(str(raw))
        if hours > 0:
            now = world.time.to_total_seconds()
            actor.wake_at_seconds = now + hours * 3600
            actor.active = False
            logger.info("wait_sleep", hours=hours, wake_at=actor.wake_at_seconds)
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
    healing = roll_dice("1d10") + actor.level
    healed = actor.heal(healing)

    logger.info("second_wind", rolled=healing, healed=healed, level=actor.level)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_SECOND_WIND,
            source_layer="entities",
            data={"entity_id": actor.id, "healed": healed},
        )
    )
    return ActionResult()


# ---------------------------------------------------------------------------
# Generic slot-based equip/unequip
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SlotConfig:
    """Configuration for a single equipment slot."""

    slot: EquipmentSlot
    item_type: ItemType
    param_key: str  # action param name, e.g. "weapon_id"
    creature_field: str  # attribute on Creature, e.g. "equipped_weapon"
    event_field: str  # key in event data, e.g. "weapon_name"
    equip_action: ActionType
    unequip_action: ActionType


SLOT_CONFIGS: dict[EquipmentSlot, SlotConfig] = {
    EquipmentSlot.WEAPON: SlotConfig(
        slot=EquipmentSlot.WEAPON,
        item_type=ItemType.WEAPON,
        param_key="weapon_id",
        creature_field="equipped_weapon",
        event_field="weapon_name",
        equip_action=ActionType.EQUIP,
        unequip_action=ActionType.UNEQUIP,
    ),
    EquipmentSlot.ARMOR: SlotConfig(
        slot=EquipmentSlot.ARMOR,
        item_type=ItemType.ARMOR,
        param_key="armor_id",
        creature_field="equipped_armor",
        event_field="armor_name",
        equip_action=ActionType.EQUIP_ARMOR,
        unequip_action=ActionType.UNEQUIP_ARMOR,
    ),
    EquipmentSlot.SHIELD: SlotConfig(
        slot=EquipmentSlot.SHIELD,
        item_type=ItemType.SHIELD,
        param_key="shield_id",
        creature_field="equipped_shield",
        event_field="shield_name",
        equip_action=ActionType.EQUIP_SHIELD,
        unequip_action=ActionType.UNEQUIP_SHIELD,
    ),
    EquipmentSlot.HEAD: SlotConfig(
        slot=EquipmentSlot.HEAD,
        item_type=ItemType.ACCESSORY,
        param_key="head_id",
        creature_field="equipped_head",
        event_field="head_name",
        equip_action=ActionType.EQUIP_HEAD,
        unequip_action=ActionType.UNEQUIP_HEAD,
    ),
    EquipmentSlot.FEET: SlotConfig(
        slot=EquipmentSlot.FEET,
        item_type=ItemType.ACCESSORY,
        param_key="feet_id",
        creature_field="equipped_feet",
        event_field="feet_name",
        equip_action=ActionType.EQUIP_FEET,
        unequip_action=ActionType.UNEQUIP_FEET,
    ),
    EquipmentSlot.RING: SlotConfig(
        slot=EquipmentSlot.RING,
        item_type=ItemType.ACCESSORY,
        param_key="ring_id",
        creature_field="equipped_ring",
        event_field="ring_name",
        equip_action=ActionType.EQUIP_RING,
        unequip_action=ActionType.UNEQUIP_RING,
    ),
}


def _handle_equip_slot(cfg: SlotConfig, actor: Creature, action: Action, emit_fn: EmitFn) -> ActionResult:
    """Generic equip: find item in inventory → swap into slot → emit event."""
    item_id = str(action.params[cfg.param_key])
    item = next((i for i in actor.inventory if i.id == item_id), None)
    if item is None:
        return ActionResult(success=False, error=f"Item {item_id} not in inventory")
    if item.item_type != cfg.item_type:
        return ActionResult(success=False, error=f"Item {item_id} is not a {cfg.item_type.value}")
    # Accessory slot validation: ring can't go in head slot, etc.
    if item.item_type == ItemType.ACCESSORY and item.accessory_def is not None and item.accessory_def.slot != cfg.slot:
        return ActionResult(
            success=False,
            error=f"Item {item_id} is a {item.accessory_def.slot.value} accessory, not {cfg.slot.value}",
        )

    old: Item | None = getattr(actor, cfg.creature_field)
    if old is not None:
        actor.inventory.append(old)
    actor.inventory.remove(item)
    setattr(actor, cfg.creature_field, item)

    logger.info("equip", slot=cfg.creature_field, item=item.name)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_EQUIP,
            source_layer="entities",
            data={"entity_id": actor.id, cfg.event_field: item.name},
        )
    )
    return ActionResult()


def _handle_unequip_slot(cfg: SlotConfig, actor: Creature, action: Action, emit_fn: EmitFn) -> ActionResult:
    """Generic unequip: remove from slot → return to inventory → emit event."""
    item: Item | None = getattr(actor, cfg.creature_field)
    if item is None:
        return ActionResult(success=False, error=f"No {cfg.item_type.value} equipped")

    actor.inventory.append(item)
    setattr(actor, cfg.creature_field, None)

    logger.info("unequip", slot=cfg.creature_field, item=item.name)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_UNEQUIP,
            source_layer="entities",
            data={"entity_id": actor.id, cfg.event_field: item.name},
        )
    )
    return ActionResult()


# Public wrappers — thin delegates to the generic mechanism.

_WEAPON_CFG = SLOT_CONFIGS[EquipmentSlot.WEAPON]
_ARMOR_CFG = SLOT_CONFIGS[EquipmentSlot.ARMOR]
_SHIELD_CFG = SLOT_CONFIGS[EquipmentSlot.SHIELD]
_HEAD_CFG = SLOT_CONFIGS[EquipmentSlot.HEAD]
_FEET_CFG = SLOT_CONFIGS[EquipmentSlot.FEET]
_RING_CFG = SLOT_CONFIGS[EquipmentSlot.RING]


def handle_equip(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Equip a weapon from inventory. Free action (D&D 5e object interaction)."""
    return _handle_equip_slot(_WEAPON_CFG, actor, action, emit_fn)


def handle_unequip(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
    """Unequip current weapon → back to inventory. Free action."""
    return _handle_unequip_slot(_WEAPON_CFG, actor, action, emit_fn)


def handle_equip_armor(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Equip armor from inventory. Free action."""
    return _handle_equip_slot(_ARMOR_CFG, actor, action, emit_fn)


def handle_unequip_armor(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Unequip armor → back to inventory. Free action."""
    return _handle_unequip_slot(_ARMOR_CFG, actor, action, emit_fn)


def handle_equip_shield(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Equip shield from inventory. Free action."""
    return _handle_equip_slot(_SHIELD_CFG, actor, action, emit_fn)


def handle_unequip_shield(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Unequip shield → back to inventory. Free action."""
    return _handle_unequip_slot(_SHIELD_CFG, actor, action, emit_fn)


def handle_equip_head(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Equip headgear from inventory. Free action."""
    return _handle_equip_slot(_HEAD_CFG, actor, action, emit_fn)


def handle_unequip_head(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Unequip headgear → back to inventory. Free action."""
    return _handle_unequip_slot(_HEAD_CFG, actor, action, emit_fn)


def handle_equip_feet(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Equip footwear from inventory. Free action."""
    return _handle_equip_slot(_FEET_CFG, actor, action, emit_fn)


def handle_unequip_feet(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Unequip footwear → back to inventory. Free action."""
    return _handle_unequip_slot(_FEET_CFG, actor, action, emit_fn)


def handle_equip_ring(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Equip ring from inventory. Free action."""
    return _handle_equip_slot(_RING_CFG, actor, action, emit_fn)


def handle_unequip_ring(
    actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World
) -> ActionResult:
    """Unequip ring → back to inventory. Free action."""
    return _handle_unequip_slot(_RING_CFG, actor, action, emit_fn)


# ---------------------------------------------------------------------------
# Trade handlers
# ---------------------------------------------------------------------------


def _resolve_merchant(merchant_id: str, ctx: ActionContext) -> Npc | None:
    """Look up merchant NPC via context entity lookup."""
    from dnd_simulator.layers.entities.models import Npc as NpcModel

    if ctx.get_entity is None:
        return None
    entity = ctx.get_entity(merchant_id)
    if isinstance(entity, NpcModel):
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
        return ActionResult(success=False, error=f"Merchant '{merchant_id}' not found")

    if not isinstance(actor, Character):
        return ActionResult(success=False, error="Only characters can trade")

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
        return ActionResult(success=False, error=f"Merchant '{merchant_id}' not found")

    if not isinstance(actor, Character):
        return ActionResult(success=False, error="Only characters can trade")

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
