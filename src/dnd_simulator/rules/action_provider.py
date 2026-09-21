"""ActionProvider — dynamic sources of available actions.

Providers are pure: given a creature and context, return which action types
are currently available. No state, no I/O.

BaseActionProvider covers the static action set (idle, say, attack, etc.).
InventoryActionProvider adds USE_ITEM when the creature has usable items.

I/O-coupled providers (MerchantActionProvider, LootActionProvider) live in
service/contextual_providers — they hold world-query callbacks and must not
live in rules/.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.rules.validation import validate_action

if TYPE_CHECKING:
    from dnd_simulator.core.character import Creature
    from dnd_simulator.rules.validation import ActionContext, ValidationError


class ActionProvider(Protocol):
    """Source of available action types for a creature."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]: ...


@dataclass(frozen=True)
class BaseActionProvider:
    """Provides static base actions — everything except provider-managed types."""

    action_types: frozenset[ActionType]

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        result: list[ActionType] = []
        for at in self.action_types:
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


class TriggerActionProvider:
    """Provides self-completion only while an armed trigger is active."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        from dnd_simulator.core.player import PlayerCharacter

        if isinstance(creature, PlayerCharacter):
            return []
        if not any(trigger.armed and trigger.active for trigger in creature.triggers):
            return []
        probe = Action(name=ActionType.COMPLETE_TRIGGER)
        if validate_action(creature, probe, ctx) is not None:
            return []
        return [ActionType.COMPLETE_TRIGGER]


def _equipment_candidates(creature: Creature) -> list[ActionType]:
    """Equip actions for slots with a matching bag item, unequip actions for occupied slots."""
    from dnd_simulator.rules.handlers import SLOT_CONFIGS

    result: list[ActionType] = []
    for cfg in SLOT_CONFIGS.values():
        if any(i.item_type == cfg.item_type for i in creature.inventory):
            result.append(cfg.equip_action)
        if getattr(creature, cfg.creature_field) is not None:
            result.append(cfg.unequip_action)
    return result


class EquipmentActionProvider:
    """Slot-driven equipment provider — handles all equipment slots generically."""

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        return [a for a in _equipment_candidates(creature) if validate_action(creature, Action(name=a), ctx) is None]


def blocked_equipment_actions(creature: Creature, ctx: ActionContext) -> list[tuple[ActionType, ValidationError]]:
    """The equipment actions the creature has the items for but cannot take now, each with why.

    The complement of ``EquipmentActionProvider`` over the same candidates, so a UI can
    disable a control with the validation's own reason (wrong mode, no Action left, ...).
    """
    blocked: list[tuple[ActionType, ValidationError]] = []
    for action_type in _equipment_candidates(creature):
        error = validate_action(creature, Action(name=action_type), ctx)
        if error is not None:
            blocked.append((action_type, error))
    return blocked


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

        # Fighter L2+: Action Surge (pool only exists at L2+, so L1 is gated implicitly)
        if creature.char_class == CharClass.FIGHTER and any(
            p.id == "action_surge" and p.current_uses > 0 for p in creature.resource_pools
        ):
            probe = Action(name=ActionType.ACTION_SURGE)
            if validate_action(creature, probe, ctx) is None:
                result.append(ActionType.ACTION_SURGE)

        # Paladin: Lay on Hands (requires resource pool)
        if creature.char_class == CharClass.PALADIN and has_resource(creature, "lay_on_hands"):
            probe = Action(name=ActionType.LAY_ON_HANDS)
            if validate_action(creature, probe, ctx) is None:
                result.append(ActionType.LAY_ON_HANDS)

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
