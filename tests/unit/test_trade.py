"""Tests for trade rules — buy/sell validation and execution."""

from __future__ import annotations

from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.rules.trade import execute_buy, execute_sell, validate_buy, validate_sell

MARKET = "silverport_city_market"


def _merchant(*, gold: int = 100, items: list[Item] | None = None) -> Npc:
    npc = Npc(id="merchant_1", name="Gretta", role="merchant", location_id=MARKET, gold=gold)
    if items is not None:
        npc.inventory = items
    return npc


def _player(*, gold: int = 100, location: str = MARKET, items: list[Item] | None = None) -> PlayerCharacter:
    pc = PlayerCharacter(id="player_1", name="Aldric", location_id=location, gold=gold)
    if items is not None:
        pc.inventory = items
    return pc


def _potion(price: int = 50) -> Item:
    return Item(id="health_potion_0", name="Health Potion", item_type=ItemType.POTION, price=price)


def _dagger(price: int = 30) -> Item:
    return Item(id="dagger_0", name="Dagger", item_type=ItemType.WEAPON, price=price)


def _unpriceable() -> Item:
    return Item(id="quest_gem_0", name="Quest Gem", item_type=ItemType.POTION, price=None)


# --- Buy validation & execution ---


class TestBuySuccess:
    def test_buy_transfers_item_and_gold(self) -> None:
        potion = _potion(50)
        merchant = _merchant(gold=200, items=[potion])
        player = _player(gold=100)

        error = validate_buy(buyer=player, seller=merchant, item_id="health_potion_0")
        assert error is None

        execute_buy(buyer=player, seller=merchant, item=potion)

        assert potion in player.inventory
        assert potion not in merchant.inventory
        assert player.gold == 50
        assert merchant.gold == 250


class TestBuyInsufficientGold:
    def test_rejects_when_buyer_cannot_afford(self) -> None:
        potion = _potion(50)
        merchant = _merchant(items=[potion])
        player = _player(gold=10)

        error = validate_buy(buyer=player, seller=merchant, item_id="health_potion_0")
        assert error is not None
        assert "gold" in error.lower()


class TestBuyItemNotInInventory:
    def test_rejects_missing_item(self) -> None:
        merchant = _merchant(items=[])
        player = _player(gold=100)

        error = validate_buy(buyer=player, seller=merchant, item_id="bogus_item")
        assert error is not None


class TestBuyItemWithoutPrice:
    def test_rejects_unpriceable_item(self) -> None:
        gem = _unpriceable()
        merchant = _merchant(items=[gem])
        player = _player(gold=100)

        error = validate_buy(buyer=player, seller=merchant, item_id="quest_gem_0")
        assert error is not None
        assert "price" in error.lower()


# --- Sell validation & execution ---


class TestSellSuccess:
    def test_sell_transfers_item_and_gold(self) -> None:
        dagger = _dagger(30)
        merchant = _merchant(gold=100)
        player = _player(gold=50, items=[dagger])

        error = validate_sell(seller=player, buyer=merchant, item_id="dagger_0")
        assert error is None

        execute_sell(seller=player, buyer=merchant, item=dagger)

        assert dagger in merchant.inventory
        assert dagger not in player.inventory
        assert player.gold == 80
        assert merchant.gold == 70


class TestSellInsufficientMerchantGold:
    def test_rejects_when_merchant_cannot_afford(self) -> None:
        dagger = _dagger(30)
        merchant = _merchant(gold=5)
        player = _player(items=[dagger])

        error = validate_sell(seller=player, buyer=merchant, item_id="dagger_0")
        assert error is not None
        assert "gold" in error.lower()


# --- Shared checks ---


class TestNotAMerchant:
    def test_buy_rejects_non_merchant(self) -> None:
        potion = _potion(50)
        npc = Npc(id="guard_1", name="Rodrik", role="guard", location_id=MARKET)
        npc.inventory = [potion]
        player = _player(gold=100)

        error = validate_buy(buyer=player, seller=npc, item_id="health_potion_0")
        assert error is not None
        assert "merchant" in error.lower()

    def test_sell_rejects_non_merchant(self) -> None:
        dagger = _dagger(30)
        npc = Npc(id="guard_1", name="Rodrik", role="guard", location_id=MARKET)
        player = _player(items=[dagger])

        error = validate_sell(seller=player, buyer=npc, item_id="dagger_0")
        assert error is not None
        assert "merchant" in error.lower()


class TestDifferentLocation:
    def test_buy_rejects_different_location(self) -> None:
        potion = _potion(50)
        merchant = _merchant(items=[potion])
        player = _player(gold=100, location="silverport_city_tavern")

        error = validate_buy(buyer=player, seller=merchant, item_id="health_potion_0")
        assert error is not None
        assert "location" in error.lower()

    def test_sell_rejects_different_location(self) -> None:
        dagger = _dagger(30)
        merchant = _merchant(gold=100)
        player = _player(items=[dagger], location="silverport_city_tavern")

        error = validate_sell(seller=player, buyer=merchant, item_id="dagger_0")
        assert error is not None
        assert "location" in error.lower()


# --- is_merchant property ---


class TestIsMerchant:
    def test_merchant_role_returns_true(self) -> None:
        npc = Npc(id="m", name="M", role="merchant", location_id="x")
        assert npc.is_merchant is True

    def test_other_role_returns_false(self) -> None:
        npc = Npc(id="g", name="G", role="guard", location_id="x")
        assert npc.is_merchant is False

    def test_empty_role_returns_false(self) -> None:
        npc = Npc(id="x", name="X", location_id="x")
        assert npc.is_merchant is False
