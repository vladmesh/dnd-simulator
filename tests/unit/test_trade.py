"""Tests for trade rules — buy/sell validation and execution."""

from __future__ import annotations

from pathlib import Path

from dnd_simulator.content_loader.catalogs import load_catalog
from dnd_simulator.content_loader.items import parse_items
from dnd_simulator.content_loader.schemas import ItemContent
from dnd_simulator.core.character import NpcRole
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.rules.trade import execute_buy, execute_sell, validate_buy, validate_sell

MARKET = "silverport_city_market"

CATALOG_DIR = Path(__file__).resolve().parents[2] / "content" / "catalogs" / "items"


def _merchant(*, gold: int = 100, items: list[Item] | None = None) -> Npc:
    npc = Npc(id="merchant_1", name="Gretta", role=NpcRole.MERCHANT, location_id=MARKET, gold=gold)
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

    def test_sell_rejects_unpriceable_item(self) -> None:
        gem = _unpriceable()
        merchant = _merchant(gold=100)
        player = _player(items=[gem])

        error = validate_sell(seller=player, buyer=merchant, item_id="quest_gem_0")
        assert error is not None
        assert "price" in error.lower()


class TestSellStartingEquipmentFromCatalog:
    """A starting item resolved from the catalog can be sold once it's in inventory.

    This is the live-playtest bug (`catalog-item-prices`): before prices were added to
    the catalog YAML, chain_mail resolved with price=None and the merchant rejected the sale.
    """

    def test_sell_catalog_chain_mail(self) -> None:
        catalog = load_catalog(CATALOG_DIR, ItemContent)
        chain_mail = parse_items([{"ref": "chain_mail"}], item_catalog=catalog)[0]
        assert chain_mail.price is not None  # resolved from catalog, not hand-built

        merchant = _merchant(gold=1000)
        player = _player(gold=0, items=[chain_mail])

        error = validate_sell(seller=player, buyer=merchant, item_id=chain_mail.id)
        assert error is None

        execute_sell(seller=player, buyer=merchant, item=chain_mail)

        assert chain_mail in merchant.inventory
        assert chain_mail not in player.inventory
        assert player.gold == chain_mail.price


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
        npc = Npc(id="guard_1", name="Rodrik", role=NpcRole.GUARD, location_id=MARKET)
        npc.inventory = [potion]
        player = _player(gold=100)

        error = validate_buy(buyer=player, seller=npc, item_id="health_potion_0")
        assert error is not None
        assert "merchant" in error.lower()

    def test_sell_rejects_non_merchant(self) -> None:
        dagger = _dagger(30)
        npc = Npc(id="guard_1", name="Rodrik", role=NpcRole.GUARD, location_id=MARKET)
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
        npc = Npc(id="m", name="M", role=NpcRole.MERCHANT, location_id="x")
        assert npc.is_merchant is True

    def test_other_role_returns_false(self) -> None:
        npc = Npc(id="g", name="G", role=NpcRole.GUARD, location_id="x")
        assert npc.is_merchant is False

    def test_default_role_returns_false(self) -> None:
        npc = Npc(id="x", name="X", location_id="x")
        assert npc.is_merchant is False


class TestCharacterIsNotMerchant:
    """Character base class always returns is_merchant=False."""

    def test_character_is_not_merchant(self) -> None:
        from dnd_simulator.core.character import Character

        char = Character(id="c", name="C", location_id="x")
        assert char.is_merchant is False

    def test_player_is_not_merchant(self) -> None:
        pc = PlayerCharacter(id="p", name="P", location_id="x")
        assert pc.is_merchant is False


class TestNpcRoleEnum:
    """NpcRole enum has correct values and is used throughout."""

    def test_enum_values_match_yaml_strings(self) -> None:
        assert NpcRole.MERCHANT.value == "merchant"
        assert NpcRole.BLACKSMITH.value == "blacksmith"
        assert NpcRole.GUARD.value == "guard"
        assert NpcRole.TAVERN_KEEPER.value == "tavern_keeper"
        assert NpcRole.FARMER.value == "farmer"

    def test_enum_parses_from_yaml_string(self) -> None:
        assert NpcRole("merchant") == NpcRole.MERCHANT
        assert NpcRole("guard") == NpcRole.GUARD


class TestTradeModuleHasNoLayersDependency:
    """rules/trade.py must not import from layers/."""

    def test_no_layers_import(self) -> None:
        import inspect

        import dnd_simulator.rules.trade as trade_module

        source = inspect.getsource(trade_module)
        assert "from dnd_simulator.layers" not in source
        assert "import dnd_simulator.layers" not in source
