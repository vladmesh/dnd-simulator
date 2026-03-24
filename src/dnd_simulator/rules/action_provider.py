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


class ArmorEquipmentProvider:
    """Provides armor/shield equip/unequip actions based on inventory and slots."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        from dnd_simulator.core.items import ItemType

        result: list[ActionType] = []
        has_armor = any(i.item_type == ItemType.ARMOR for i in creature.inventory)
        if has_armor:
            probe = Action(name=ActionType.EQUIP_ARMOR)
            if validate_action(creature, probe, ctx) is None:
                result.append(ActionType.EQUIP_ARMOR)
        if creature.equipped_armor is not None:
            probe = Action(name=ActionType.UNEQUIP_ARMOR)
            if validate_action(creature, probe, ctx) is None:
                result.append(ActionType.UNEQUIP_ARMOR)
        has_shield = any(i.item_type == ItemType.SHIELD for i in creature.inventory)
        if has_shield:
            probe = Action(name=ActionType.EQUIP_SHIELD)
            if validate_action(creature, probe, ctx) is None:
                result.append(ActionType.EQUIP_SHIELD)
        if creature.equipped_shield is not None:
            probe = Action(name=ActionType.UNEQUIP_SHIELD)
            if validate_action(creature, probe, ctx) is None:
                result.append(ActionType.UNEQUIP_SHIELD)
        return result


class ClassFeatureActionProvider:
    """Provides class-feature actions (Second Wind, etc.) when available."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        from dnd_simulator.core.character import Character, CharClass
        from dnd_simulator.rules.resources import has_resource

        if not isinstance(creature, Character):
            return []

        result: list[ActionType] = []

        # Fighter: Second Wind (requires resource pool)
        if creature.char_class == CharClass.FIGHTER and has_resource(creature, "second_wind"):
            probe = Action(name=ActionType.SECOND_WIND)
            if validate_action(creature, probe, ctx) is None:
                result.append(ActionType.SECOND_WIND)

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
