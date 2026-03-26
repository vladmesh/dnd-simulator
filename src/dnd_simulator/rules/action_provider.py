"""ActionProvider — dynamic sources of available actions.

Providers are pure: given a creature and context, return which action types
are currently available. No state, no I/O.

BaseActionProvider covers the static action set (idle, say, attack, etc.).
InventoryActionProvider adds USE_ITEM when the creature has usable items.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Protocol

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.rules.validation import validate_action

if TYPE_CHECKING:
    from dnd_simulator.core.character import Character, Creature
    from dnd_simulator.rules.validation import ActionContext

# Callable that returns merchant NPCs at a given location ID.
NearbyMerchantsFn = Callable[[str], "list[Character]"]


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
    """Slot-driven equipment provider — handles all equipment slots generically."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        from dnd_simulator.rules.handlers import SLOT_CONFIGS

        result: list[ActionType] = []
        for cfg in SLOT_CONFIGS.values():
            has_items = any(i.item_type == cfg.item_type for i in creature.inventory)
            if has_items:
                probe = Action(name=cfg.equip_action)
                if validate_action(creature, probe, ctx) is None:
                    result.append(cfg.equip_action)
            equipped = getattr(creature, cfg.creature_field)
            if equipped is not None:
                probe = Action(name=cfg.unequip_action)
                if validate_action(creature, probe, ctx) is None:
                    result.append(cfg.unequip_action)
        return result


# Backward compatibility alias — remove after callers migrate.
ArmorEquipmentProvider = EquipmentActionProvider


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


class MerchantActionProvider:
    """Provides BUY/SELL when creature is at the same location as a merchant."""

    def __init__(self, get_nearby_merchants: NearbyMerchantsFn) -> None:
        self._get_nearby_merchants = get_nearby_merchants

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        merchants = self._get_nearby_merchants(creature.location_id)
        if not merchants:
            return []
        result: list[ActionType] = []
        for at in (ActionType.BUY, ActionType.SELL):
            probe = Action(name=at)
            if validate_action(creature, probe, ctx) is None:
                result.append(at)
        return result
