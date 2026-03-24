"""ActionProvider — dynamic sources of available actions.

Providers are pure: given a creature and context, return which action types
are currently available. No state, no I/O.

BaseActionProvider covers the static action set (idle, say, attack, etc.).
InventoryActionProvider adds USE_ITEM when the creature has usable items.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.rules.validation import validate_action

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.rules.validation import ActionContext


class ActionProvider(Protocol):
    """Source of available action types for a creature."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]: ...


class BaseActionProvider:
    """Provides static base actions — everything except provider-managed types."""

    def __init__(self, action_types: frozenset[ActionType]) -> None:
        self._types = action_types

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        result: list[ActionType] = []
        for at in self._types:
            probe = Action(name=at)
            if validate_action(creature, probe, ctx) is None:
                result.append(at)
        return result


class InventoryActionProvider:
    """Provides USE_ITEM when creature has usable items in inventory."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        if not creature.inventory:
            return []
        probe = Action(name=ActionType.USE_ITEM)
        if validate_action(creature, probe, ctx) is not None:
            return []
        return [ActionType.USE_ITEM]


class EquipmentActionProvider:
    """Provides EQUIP if creature has weapons in inventory, UNEQUIP if weapon equipped."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        from dnd_simulator.core.items import ItemType

        result: list[ActionType] = []
        has_inventory_weapons = any(i.item_type == ItemType.WEAPON for i in creature.inventory)
        if has_inventory_weapons:
            probe = Action(name=ActionType.EQUIP)
            if validate_action(creature, probe, ctx) is None:
                result.append(ActionType.EQUIP)
        if creature.equipped_weapon is not None:
            probe = Action(name=ActionType.UNEQUIP)
            if validate_action(creature, probe, ctx) is None:
                result.append(ActionType.UNEQUIP)
        return result


class WeaponActionProvider:
    """Provides extra actions granted by equipped weapon (e.g. Bless)."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        weapon = creature.equipped_weapon
        if weapon is None or weapon.weapon_def is None or not weapon.weapon_def.grant_actions:
            return []
        result: list[ActionType] = []
        for at in weapon.weapon_def.grant_actions:
            probe = Action(name=at)
            if validate_action(creature, probe, ctx) is None:
                result.append(at)
        return result
