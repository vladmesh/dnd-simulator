"""Tests for buy/sell action handlers and trade pipeline."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.awareness import ItemInfo, MerchantInfo
from dnd_simulator.core.character import NpcRole
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.entities.perception import perceive_event
from dnd_simulator.rules.handlers import handle_buy, handle_sell
from dnd_simulator.rules.validation import ActionContext
from dnd_simulator.service.contextual_providers import MerchantActionProvider

if TYPE_CHECKING:
    from dnd_simulator.core.character import Entity

MARKET = "silverport_city_market"
TAVERN = "silverport_city_tavern"


def _merchant(*, gold: int = 500, items: list[Item] | None = None) -> Npc:
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


def _peaceful_ctx(entities: dict[str, Entity]) -> ActionContext:
    return ActionContext(
        is_combat=False,
        current_turn_entity_id="player_1",
        get_entity=lambda eid: entities.get(eid),
    )


class TestHandleBuy:
    def test_full_buy_flow(self) -> None:
        potion = _potion(50)
        merchant = _merchant(gold=200, items=[potion])
        player = _player(gold=100)
        entities: dict[str, Entity] = {"merchant_1": merchant, "player_1": player}
        ctx = _peaceful_ctx(entities)

        events: list[Event] = []

        action = Action(name=ActionType.BUY, params={"merchant_id": "merchant_1", "item_id": "health_potion_0"})
        result = handle_buy(player, action, events.append, ctx, None)  # type: ignore[arg-type]

        assert result.success
        assert potion in player.inventory
        assert potion not in merchant.inventory
        assert player.gold == 50
        assert merchant.gold == 250
        assert len(events) == 1
        assert events[0].event_type == EventType.ENTITY_BUY
        assert events[0].data["buyer_id"] == "player_1"
        assert events[0].data["merchant_id"] == "merchant_1"
        assert events[0].data["item_name"] == "Health Potion"
        assert events[0].data["price"] == 50


class TestHandleSell:
    def test_full_sell_flow(self) -> None:
        dagger = _dagger(30)
        merchant = _merchant(gold=200)
        player = _player(gold=50, items=[dagger])
        entities: dict[str, Entity] = {"merchant_1": merchant, "player_1": player}
        ctx = _peaceful_ctx(entities)

        events: list[Event] = []

        action = Action(name=ActionType.SELL, params={"merchant_id": "merchant_1", "item_id": "dagger_0"})
        result = handle_sell(player, action, events.append, ctx, None)  # type: ignore[arg-type]

        assert result.success
        assert dagger in merchant.inventory
        assert dagger not in player.inventory
        assert player.gold == 80
        assert merchant.gold == 170
        assert len(events) == 1
        assert events[0].event_type == EventType.ENTITY_SELL
        assert events[0].data["seller_id"] == "player_1"
        assert events[0].data["merchant_id"] == "merchant_1"
        assert events[0].data["item_name"] == "Dagger"
        assert events[0].data["price"] == 30


class TestBuyValidationRejects:
    def test_insufficient_gold_returns_error(self) -> None:
        potion = _potion(50)
        merchant = _merchant(items=[potion])
        player = _player(gold=10)
        entities: dict[str, Entity] = {"merchant_1": merchant, "player_1": player}
        ctx = _peaceful_ctx(entities)

        events: list[Event] = []

        action = Action(name=ActionType.BUY, params={"merchant_id": "merchant_1", "item_id": "health_potion_0"})
        result = handle_buy(player, action, events.append, ctx, None)  # type: ignore[arg-type]

        assert not result.success
        assert result.error is not None
        assert "gold" in result.error.lower()
        # No mutation
        assert player.gold == 10
        assert potion in merchant.inventory
        assert len(events) == 0


class TestTradeActionProvider:
    def _provider(self, entities: dict[str, Npc | PlayerCharacter]) -> MerchantActionProvider:
        def get_nearby_merchants(location_id: str) -> list[Npc]:
            return [
                e for e in entities.values() if isinstance(e, Npc) and e.is_merchant and e.location_id == location_id
            ]

        return MerchantActionProvider(get_nearby_merchants)

    def test_merchant_at_same_location(self) -> None:
        merchant = _merchant()
        player = _player()
        provider = self._provider({"merchant_1": merchant, "player_1": player})
        ctx = ActionContext(is_combat=False, current_turn_entity_id="player_1")

        actions = provider.get_action_types(player, ctx)
        assert ActionType.BUY in actions
        assert ActionType.SELL in actions

    def test_no_merchant_nearby(self) -> None:
        player = _player()
        provider = self._provider({"player_1": player})
        ctx = ActionContext(is_combat=False, current_turn_entity_id="player_1")

        actions = provider.get_action_types(player, ctx)
        assert ActionType.BUY not in actions
        assert ActionType.SELL not in actions

    def test_merchant_at_different_location(self) -> None:
        merchant = _merchant()  # at MARKET
        player = _player(location=TAVERN)
        provider = self._provider({"merchant_1": merchant, "player_1": player})
        ctx = ActionContext(is_combat=False, current_turn_entity_id="player_1")

        actions = provider.get_action_types(player, ctx)
        assert ActionType.BUY not in actions
        assert ActionType.SELL not in actions


class TestTradePerception:
    def test_buy_perceived_by_buyer(self) -> None:
        merchant = _merchant()
        player = _player()
        entities: dict[str, Entity] = {"merchant_1": merchant, "player_1": player}

        event = Event(
            event_type=EventType.ENTITY_BUY,
            source_layer="entities",
            data={
                "buyer_id": "player_1",
                "merchant_id": "merchant_1",
                "item_name": "Health Potion",
                "price": 50,
            },
        )
        text = perceive_event(event, player, lambda eid: entities.get(eid))
        assert "Health Potion" in text
        assert "50" in text

    def test_sell_perceived_by_seller(self) -> None:
        merchant = _merchant()
        player = _player()
        entities: dict[str, Entity] = {"merchant_1": merchant, "player_1": player}

        event = Event(
            event_type=EventType.ENTITY_SELL,
            source_layer="entities",
            data={
                "seller_id": "player_1",
                "merchant_id": "merchant_1",
                "item_name": "Dagger",
                "price": 30,
            },
        )
        text = perceive_event(event, player, lambda eid: entities.get(eid))
        assert "Dagger" in text
        assert "30" in text


class TestMerchantAwareness:
    def test_merchant_info_dataclass(self) -> None:
        items = [
            ItemInfo(id="potion_0", name="Health Potion", description="heals 2d4+2", price=50),
        ]
        info = MerchantInfo(id="merchant_1", name="Gretta", gold=500, items=items)
        assert info.id == "merchant_1"
        assert info.name == "Gretta"
        assert info.gold == 500
        assert len(info.items) == 1
        assert info.items[0].price == 50
