"""Tests for each ActionProvider class in isolation."""

from __future__ import annotations

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.character import Character, CharClass, Creature
from dnd_simulator.core.items import (
    ArmorCategory,
    ArmorDef,
    EquipmentSlot,
    Item,
    ItemType,
    ShieldDef,
    WeaponCategory,
    WeaponDef,
)
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.action_provider import (
    BaseActionProvider,
    ClassFeatureActionProvider,
    EquipmentActionProvider,
    InventoryActionProvider,
    WeaponActionProvider,
)
from dnd_simulator.rules.validation import ActionContext
from dnd_simulator.service.contextual_providers import MerchantActionProvider

# Base action types that are NOT provider-managed — matching how the real dispatcher builds them.
_COMBAT_BASE = frozenset(
    {
        ActionType.ATTACK,
        ActionType.DODGE,
        ActionType.FLEE,
        ActionType.MOVE,
        ActionType.DASH,
        ActionType.DISENGAGE,
        ActionType.END_TURN,
        ActionType.SKIP,
    }
)
_PEACEFUL_BASE = frozenset(
    {
        ActionType.IDLE,
        ActionType.SAY,
        ActionType.WAIT,
        ActionType.TRAVEL,
        ActionType.ATTACK,
        ActionType.END_TURN,
        ActionType.SKIP,
    }
)
_ALL_BASE = _COMBAT_BASE | _PEACEFUL_BASE


class TestBaseActionProvider:
    """BaseActionProvider filters by validation (combat mode, budget)."""

    def test_in_combat_returns_combat_actions(self) -> None:
        creature = Character(id="c1", name="Fighter", location_id="arena", in_combat=True)
        ctx = ActionContext(
            is_combat=True,
            current_turn_entity_id="c1",
            turn_budget=TurnBudget(),
        )
        provider = BaseActionProvider(_ALL_BASE)
        actions = provider.get_action_types(creature, ctx)

        # Combat-only actions should be present
        assert ActionType.ATTACK in actions
        assert ActionType.DODGE in actions
        assert ActionType.FLEE in actions
        # Peaceful-only actions should be filtered
        assert ActionType.WAIT not in actions
        assert ActionType.IDLE not in actions

    def test_out_of_combat_returns_peaceful_actions(self) -> None:
        creature = Character(id="c1", name="Wanderer", location_id="road")
        ctx = ActionContext(is_combat=False)
        provider = BaseActionProvider(_ALL_BASE)
        actions = provider.get_action_types(creature, ctx)

        assert ActionType.SAY in actions
        assert ActionType.WAIT in actions
        # attack probe passes without target (probe behavior)
        assert ActionType.ATTACK in actions
        # Combat-only should be excluded
        assert ActionType.DODGE not in actions
        assert ActionType.FLEE not in actions
        assert ActionType.MOVE not in actions


class TestInventoryActionProvider:
    """InventoryActionProvider provides USE_ITEM when creature has usable items."""

    def test_creature_with_potion_gets_use_item(self) -> None:
        potion = Item(id="pot1", name="Healing Potion", item_type=ItemType.POTION, params={"heal_dice": "2d4+2"})
        creature = Character(id="c1", name="Fighter", location_id="arena", inventory=[potion])
        ctx = ActionContext(is_combat=False)
        provider = InventoryActionProvider()
        actions = provider.get_action_types(creature, ctx)
        assert ActionType.USE_ITEM in actions

    def test_creature_with_empty_inventory_gets_nothing(self) -> None:
        creature = Character(id="c1", name="Fighter", location_id="arena")
        ctx = ActionContext(is_combat=False)
        provider = InventoryActionProvider()
        assert provider.get_action_types(creature, ctx) == []

    def test_creature_with_only_weapon_items_still_gets_use_item(self) -> None:
        # InventoryActionProvider only checks if inventory is non-empty — it doesn't
        # filter by item type. The validation probe passes for any non-empty inventory.
        weapon = Item(id="w1", name="Sword", item_type=ItemType.WEAPON)
        creature = Character(id="c1", name="Fighter", location_id="arena", inventory=[weapon])
        ctx = ActionContext(is_combat=False)
        provider = InventoryActionProvider()
        assert ActionType.USE_ITEM in provider.get_action_types(creature, ctx)


class TestEquipmentActionProvider:
    """EquipmentActionProvider handles weapon/armor/shield equip/unequip."""

    def test_weapon_in_inventory_offers_equip(self) -> None:
        weapon = Item(id="w1", name="Longsword", item_type=ItemType.WEAPON)
        creature = Character(id="c1", name="Fighter", location_id="arena", inventory=[weapon])
        ctx = ActionContext(is_combat=False)
        provider = EquipmentActionProvider()
        actions = provider.get_action_types(creature, ctx)
        assert ActionType.EQUIP in actions

    def test_equipped_weapon_offers_unequip(self) -> None:
        weapon = Item(id="w1", name="Longsword", item_type=ItemType.WEAPON)
        creature = Character(id="c1", name="Fighter", location_id="arena", equipped={EquipmentSlot.WEAPON: weapon})
        ctx = ActionContext(is_combat=False)
        provider = EquipmentActionProvider()
        actions = provider.get_action_types(creature, ctx)
        assert ActionType.UNEQUIP in actions

    def test_armor_in_inventory_offers_equip_armor(self) -> None:
        armor = Item(
            id="a1",
            name="Chain Mail",
            item_type=ItemType.ARMOR,
            armor_def=ArmorDef(armor_id="chain_mail", category=ArmorCategory.HEAVY, base_ac=16, max_dex_bonus=0),
        )
        creature = Character(id="c1", name="Fighter", location_id="arena", inventory=[armor])
        ctx = ActionContext(is_combat=False)
        provider = EquipmentActionProvider()
        actions = provider.get_action_types(creature, ctx)
        assert ActionType.EQUIP_ARMOR in actions

    def test_equipped_shield_offers_unequip_shield(self) -> None:
        shield = Item(
            id="s1", name="Shield", item_type=ItemType.SHIELD, shield_def=ShieldDef(shield_id="shield", ac_bonus=2)
        )
        creature = Character(id="c1", name="Fighter", location_id="arena", equipped={EquipmentSlot.SHIELD: shield})
        ctx = ActionContext(is_combat=False)
        provider = EquipmentActionProvider()
        actions = provider.get_action_types(creature, ctx)
        assert ActionType.UNEQUIP_SHIELD in actions


class TestClassFeatureActionProvider:
    """ClassFeatureActionProvider provides class-specific actions when resources available."""

    def test_fighter_with_second_wind_available(self) -> None:
        pool = ResourcePool(id="second_wind", max_uses=1, current_uses=1, reset_on=RestType.SHORT_REST)
        creature = Character(
            id="c1",
            name="Fighter",
            location_id="arena",
            char_class=CharClass.FIGHTER,
            resource_pools=[pool],
        )
        ctx = ActionContext(is_combat=False)
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(creature, ctx)
        assert ActionType.SECOND_WIND in actions

    def test_fighter_with_exhausted_second_wind_gets_nothing(self) -> None:
        pool = ResourcePool(id="second_wind", max_uses=1, current_uses=0, reset_on=RestType.SHORT_REST)
        creature = Character(
            id="c1",
            name="Fighter",
            location_id="arena",
            char_class=CharClass.FIGHTER,
            resource_pools=[pool],
        )
        ctx = ActionContext(is_combat=False)
        provider = ClassFeatureActionProvider()
        assert provider.get_action_types(creature, ctx) == []

    def test_rogue_gets_nothing(self) -> None:
        creature = Character(
            id="c1",
            name="Rogue",
            location_id="arena",
            char_class=CharClass.ROGUE,
        )
        ctx = ActionContext(is_combat=False)
        provider = ClassFeatureActionProvider()
        assert provider.get_action_types(creature, ctx) == []

    def test_non_character_creature_gets_nothing(self) -> None:
        creature = Creature(id="c1", name="Wolf", location_id="forest")
        ctx = ActionContext(is_combat=False)
        provider = ClassFeatureActionProvider()
        assert provider.get_action_types(creature, ctx) == []


class TestWeaponActionProvider:
    """WeaponActionProvider provides extra actions from equipped weapon."""

    def test_weapon_with_grant_actions_returns_them(self) -> None:
        weapon_def = WeaponDef(
            weapon_id="holy_sword",
            attack_name="Holy Sword Strike",
            category=WeaponCategory.MARTIAL,
            damage=(),
            reach=5,
            grant_actions=(ActionType.BLESS,),
        )
        weapon = Item(id="w1", name="Holy Sword", item_type=ItemType.WEAPON, weapon_def=weapon_def)
        creature = Character(id="c1", name="Paladin", location_id="arena", equipped={EquipmentSlot.WEAPON: weapon})
        ctx = ActionContext(is_combat=False)
        provider = WeaponActionProvider()
        actions = provider.get_action_types(creature, ctx)
        assert ActionType.BLESS in actions

    def test_weapon_without_grant_actions_returns_empty(self) -> None:
        weapon_def = WeaponDef(
            weapon_id="plain_sword",
            attack_name="Sword Strike",
            category=WeaponCategory.MARTIAL,
            damage=(),
            reach=5,
        )
        weapon = Item(id="w1", name="Plain Sword", item_type=ItemType.WEAPON, weapon_def=weapon_def)
        creature = Character(id="c1", name="Fighter", location_id="arena", equipped={EquipmentSlot.WEAPON: weapon})
        ctx = ActionContext(is_combat=False)
        provider = WeaponActionProvider()
        assert provider.get_action_types(creature, ctx) == []

    def test_no_equipped_weapon_returns_empty(self) -> None:
        creature = Character(id="c1", name="Monk", location_id="arena")
        ctx = ActionContext(is_combat=False)
        provider = WeaponActionProvider()
        assert provider.get_action_types(creature, ctx) == []


class TestMerchantActionProvider:
    """MerchantActionProvider provides BUY/SELL when merchants are nearby."""

    def test_merchant_nearby_returns_buy_sell(self) -> None:
        merchant = Character(id="m1", name="Shopkeeper", location_id="market")
        creature = Character(id="c1", name="Hero", location_id="market")
        provider = MerchantActionProvider(get_nearby_merchants=lambda loc: [merchant])
        ctx = ActionContext(is_combat=False)
        actions = provider.get_action_types(creature, ctx)
        assert ActionType.BUY in actions
        assert ActionType.SELL in actions

    def test_no_merchants_returns_empty(self) -> None:
        creature = Character(id="c1", name="Hero", location_id="wilderness")
        provider = MerchantActionProvider(get_nearby_merchants=lambda loc: [])
        ctx = ActionContext(is_combat=False)
        assert provider.get_action_types(creature, ctx) == []
