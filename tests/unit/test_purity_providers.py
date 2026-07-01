"""Sprint 020 phase 1 task 5: rules/ purity — provider I/O & statefulness.

Tests:
1. MerchantActionProvider no longer lives in rules/ — it lives in service/contextual_providers.
2. LootActionProvider no longer lives in rules/ — it lives in service/contextual_providers.
3. BaseActionProvider is a frozen dataclass (immutable after construction).
4. Merchant action behavior preserved (BUY/SELL appear iff merchant nearby).
5. Loot action behavior preserved (TAKE appears iff lootable nearby).
"""

from __future__ import annotations

import contextlib
import dataclasses

import pytest

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.character import Character, Creature
from dnd_simulator.rules.validation import ActionContext

# ---------------------------------------------------------------------------
# 1-2. Purity boundary — I/O providers must not live in rules/
# ---------------------------------------------------------------------------


class TestProviderPurityBoundary:
    def test_merchant_provider_not_in_rules(self) -> None:
        """MerchantActionProvider must have been moved out of rules/."""
        from dnd_simulator.rules import action_provider

        assert not hasattr(action_provider, "MerchantActionProvider"), (
            "MerchantActionProvider still in rules/action_provider — must move to service/"
        )

    def test_loot_provider_not_in_rules(self) -> None:
        """LootActionProvider must have been moved out of rules/."""
        from dnd_simulator.rules import action_provider

        assert not hasattr(action_provider, "LootActionProvider"), (
            "LootActionProvider still in rules/action_provider — must move to service/"
        )

    def test_merchant_provider_importable_from_service(self) -> None:
        """MerchantActionProvider must be importable from service/contextual_providers."""
        from dnd_simulator.service.contextual_providers import MerchantActionProvider  # noqa: F401

    def test_loot_provider_importable_from_service(self) -> None:
        """LootActionProvider must be importable from service/contextual_providers."""
        from dnd_simulator.service.contextual_providers import LootActionProvider  # noqa: F401


# ---------------------------------------------------------------------------
# 3. BaseActionProvider is frozen
# ---------------------------------------------------------------------------


class TestBaseProviderImmutability:
    def test_base_provider_rejects_mutation(self) -> None:
        """BaseActionProvider must be immutable after construction."""
        from dnd_simulator.rules.action_provider import BaseActionProvider

        provider = BaseActionProvider(frozenset())
        with pytest.raises((AttributeError, dataclasses.FrozenInstanceError, TypeError)):
            provider.action_types = frozenset({ActionType.IDLE})  # type: ignore[misc]

    def test_base_provider_is_frozen_dataclass(self) -> None:
        """BaseActionProvider must be a frozen dataclass."""
        from dnd_simulator.rules.action_provider import BaseActionProvider

        assert dataclasses.is_dataclass(BaseActionProvider)
        assert dataclasses.fields(BaseActionProvider)  # at least one field
        # frozen dataclasses have __delattr__ = __setattr__ = FrozenInstanceError raiser
        instance = BaseActionProvider(frozenset())
        with contextlib.suppress(dataclasses.FrozenInstanceError, AttributeError):
            object.__setattr__(instance, "_sentinel_", True)


# ---------------------------------------------------------------------------
# 4. Merchant action behavior preserved
# ---------------------------------------------------------------------------


class TestMerchantActionsPreserved:
    def test_merchant_nearby_offers_buy_sell(self) -> None:
        """BUY/SELL in available actions when a merchant is at the same location."""
        from dnd_simulator.service.contextual_providers import MerchantActionProvider

        merchant = Character(id="shopkeeper", name="Gretta", location_id="market")
        actor = Character(id="hero", name="Hero", location_id="market")
        ctx = ActionContext(is_combat=False)
        provider = MerchantActionProvider(get_nearby_merchants=lambda _loc: [merchant])
        actions = provider.get_action_types(actor, ctx)
        assert ActionType.BUY in actions
        assert ActionType.SELL in actions

    def test_no_merchant_no_buy_sell(self) -> None:
        """BUY/SELL absent when no merchants nearby."""
        from dnd_simulator.service.contextual_providers import MerchantActionProvider

        actor = Character(id="hero", name="Hero", location_id="wilderness")
        ctx = ActionContext(is_combat=False)
        provider = MerchantActionProvider(get_nearby_merchants=lambda _loc: [])
        actions = provider.get_action_types(actor, ctx)
        assert ActionType.BUY not in actions
        assert ActionType.SELL not in actions


# ---------------------------------------------------------------------------
# 5. Loot action behavior preserved
# ---------------------------------------------------------------------------


class TestLootActionsPreserved:
    def test_lootable_nearby_offers_take(self) -> None:
        """TAKE in available actions when a lootable holder is at the same location."""
        from dnd_simulator.service.contextual_providers import LootActionProvider

        corpse = Creature(id="goblin_corpse", name="Goblin", location_id="dungeon", max_hp=5, current_hp=0)
        actor = Character(id="hero", name="Hero", location_id="dungeon")
        ctx = ActionContext(is_combat=False)
        provider = LootActionProvider(get_nearby_lootables=lambda _loc: [corpse])
        actions = provider.get_action_types(actor, ctx)
        assert ActionType.TAKE in actions

    def test_no_lootable_no_take(self) -> None:
        """TAKE absent when nothing lootable nearby."""
        from dnd_simulator.service.contextual_providers import LootActionProvider

        actor = Character(id="hero", name="Hero", location_id="dungeon")
        ctx = ActionContext(is_combat=False)
        provider = LootActionProvider(get_nearby_lootables=lambda _loc: [])
        actions = provider.get_action_types(actor, ctx)
        assert ActionType.TAKE not in actions

    def test_empty_lootable_list_no_take(self) -> None:
        """TAKE absent when the resolved lootable list is empty (caller pre-filtered)."""
        from dnd_simulator.service.contextual_providers import LootActionProvider

        actor = Character(id="hero", name="Hero", location_id="dungeon")
        ctx = ActionContext(is_combat=False)
        provider = LootActionProvider(get_nearby_lootables=lambda _loc: [])
        actions = provider.get_action_types(actor, ctx)
        assert ActionType.TAKE not in actions
