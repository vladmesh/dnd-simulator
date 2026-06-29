"""Action providers that require world/layer I/O.

These providers hold callbacks that query live layer state (entity positions,
merchant roles, loot states) and belong in service/, not rules/.

The ActionProvider protocol is satisfied — callers use them identically to
the pure providers in rules/action_provider.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.rules.validation import validate_action

if TYPE_CHECKING:
    from dnd_simulator.core.character import Character, Creature, Entity
    from dnd_simulator.rules.validation import ActionContext

NearbyMerchantsFn = Callable[[str], "list[Character]"]
NearbyLootablesFn = Callable[[str], "list[Entity]"]


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


class LootActionProvider:
    """Provides TAKE when a lootable holder (corpse/container) is at the actor's location."""

    def __init__(self, get_nearby_lootables: NearbyLootablesFn) -> None:
        self._get_nearby_lootables = get_nearby_lootables

    def get_action_types(self, creature: Creature, ctx: ActionContext) -> list[ActionType]:
        if not self._get_nearby_lootables(creature.location_id):
            return []
        probe = Action(name=ActionType.TAKE)
        if validate_action(creature, probe, ctx) is not None:
            return []
        return [ActionType.TAKE]
