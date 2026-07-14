"""Equipment action handlers — generic slot-based equip/unequip."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.events import EquipmentPayload
from dnd_simulator.core.items import EquipmentSlot, Item, ItemType
from dnd_simulator.core.models import ActionResult, Event, EventType
from dnd_simulator.i18n import _

if TYPE_CHECKING:
    from collections.abc import Callable

    from dnd_simulator.core.action import Action
    from dnd_simulator.core.character import Creature
    from dnd_simulator.core.models import EmitFn
    from dnd_simulator.core.world import World
    from dnd_simulator.rules.validation import ActionContext

    EquipmentHandler = Callable[[Creature, Action, EmitFn, ActionContext, World], ActionResult]

logger = structlog.get_logger(domain="action")


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
        return ActionResult(success=False, error=_("Item {id} not in inventory").format(id=item_id))
    if item.item_type != cfg.item_type:
        return ActionResult(
            success=False,
            error=_("Item {id} is not a {item_type}").format(id=item_id, item_type=cfg.item_type.value),
        )
    # Accessory slot validation: ring can't go in head slot, etc.
    if item.item_type == ItemType.ACCESSORY and item.accessory_def is not None and item.accessory_def.slot != cfg.slot:
        return ActionResult(
            success=False,
            error=_("Item {id} is a {slot} accessory, not {expected}").format(
                id=item_id, slot=item.accessory_def.slot.value, expected=cfg.slot.value
            ),
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
            data=EquipmentPayload(actor.id, item.name, item.id),
        )
    )
    return ActionResult()


def _handle_unequip_slot(cfg: SlotConfig, actor: Creature, action: Action, emit_fn: EmitFn) -> ActionResult:
    """Generic unequip: remove from slot → return to inventory → emit event."""
    item: Item | None = getattr(actor, cfg.creature_field)
    if item is None:
        return ActionResult(success=False, error=_("No {item_type} equipped").format(item_type=cfg.item_type.value))

    actor.inventory.append(item)
    setattr(actor, cfg.creature_field, None)

    logger.info("unequip", slot=cfg.creature_field, item=item.name)
    emit_fn(
        Event(
            event_type=EventType.ENTITY_UNEQUIP,
            source_layer="entities",
            data=EquipmentPayload(actor.id, item.name, item.id),
        )
    )
    return ActionResult()


# Factory-built handlers — one per slot per direction, generated from SLOT_CONFIGS.
# Each adapts the 5-arg dispatcher signature to the 4-arg generic mechanism.


def make_equip_handler(cfg: SlotConfig) -> EquipmentHandler:
    """Build the equip handler for a slot. Free action (D&D 5e object interaction)."""

    def handler(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
        return _handle_equip_slot(cfg, actor, action, emit_fn)

    return handler


def make_unequip_handler(cfg: SlotConfig) -> EquipmentHandler:
    """Build the unequip handler for a slot. Free action."""

    def handler(actor: Creature, action: Action, emit_fn: EmitFn, ctx: ActionContext, world: World) -> ActionResult:
        return _handle_unequip_slot(cfg, actor, action, emit_fn)

    return handler


#: ActionType → handler for all equip/unequip slots. Consumed by the dispatcher's register loop.
EQUIPMENT_HANDLERS: dict[ActionType, EquipmentHandler] = {}
for _cfg in SLOT_CONFIGS.values():
    EQUIPMENT_HANDLERS[_cfg.equip_action] = make_equip_handler(_cfg)
    EQUIPMENT_HANDLERS[_cfg.unequip_action] = make_unequip_handler(_cfg)

# Backward-compat named handlers for the weapon slot (used directly in tests).
handle_equip = EQUIPMENT_HANDLERS[ActionType.EQUIP]
handle_unequip = EQUIPMENT_HANDLERS[ActionType.UNEQUIP]
