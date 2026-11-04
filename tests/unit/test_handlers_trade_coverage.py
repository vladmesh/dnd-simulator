"""Trade handlers reject invalid participants and transfer items, gold, and events."""

from collections.abc import Callable

import pytest

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Character, Creature, NpcRole
from dnd_simulator.core.events import BuyPayload, SellPayload
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.models import ActionResult, EmitFn, Event, EventType
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.rules.handlers.trade import handle_buy, handle_sell
from dnd_simulator.rules.validation import ActionContext

type TradeHandler = Callable[[Creature, Action, EmitFn, ActionContext, World], ActionResult]


@pytest.fixture(params=[(handle_buy, ActionType.BUY), (handle_sell, ActionType.SELL)], ids=["buy", "sell"])
def trade(request: pytest.FixtureRequest) -> tuple[TradeHandler, ActionType]:
    return request.param


@pytest.fixture
def actor() -> Character:
    return Character(id="trader", name="Trader", location_id="market", max_hp=20, current_hp=20, gold=30)


@pytest.fixture
def merchant() -> Npc:
    return Npc(
        id="merchant",
        name="Merchant",
        location_id="market",
        max_hp=20,
        current_hp=20,
        role=NpcRole.MERCHANT,
        gold=100,
    )


@pytest.fixture
def emitted_events() -> list[Event]:
    return []


@pytest.fixture
def emit_fn(emitted_events: list[Event]) -> EmitFn:
    def emit(event: Event) -> ActionResult:
        emitted_events.append(event)
        return ActionResult()

    return emit


@pytest.mark.parametrize("lookup", ["unavailable", "missing", "non_character", "non_merchant"])
def test_trade_rejects_unresolved_merchant(
    trade: tuple[TradeHandler, ActionType],
    actor: Character,
    emit_fn: EmitFn,
    emitted_events: list[Event],
    lookup: str,
) -> None:
    handler, action_type = trade
    contexts = {
        "unavailable": ActionContext(is_combat=False),
        "missing": ActionContext(is_combat=False, get_entity={}.get),
        "non_character": ActionContext(
            is_combat=False,
            get_entity={"merchant": Creature(id="merchant", name="Creature", location_id="market")}.get,
        ),
        "non_merchant": ActionContext(is_combat=False, get_entity={"merchant": actor}.get),
    }
    action = Action(name=action_type, params={"merchant_id": "merchant", "item_id": "potion_0"})

    result = handler(actor, action, emit_fn, contexts[lookup], World(layers=[]))

    assert not result.success
    assert result.error == "Merchant 'merchant' not found"
    assert actor.gold == 30
    assert actor.inventory == []
    assert emitted_events == []


def test_trade_rejects_non_character_actor(
    trade: tuple[TradeHandler, ActionType],
    merchant: Npc,
    emit_fn: EmitFn,
    emitted_events: list[Event],
) -> None:
    handler, action_type = trade
    actor = Creature(id="creature", name="Creature", location_id="market", max_hp=20, current_hp=20, gold=30)
    item = Item(id="potion_0", name="Potion", item_type=ItemType.POTION, price=10)
    seller = merchant if action_type == ActionType.BUY else actor
    seller.inventory = [item]
    action = Action(name=action_type, params={"merchant_id": merchant.id, "item_id": item.id})
    ctx = ActionContext(is_combat=False, get_entity={merchant.id: merchant}.get)

    result = handler(actor, action, emit_fn, ctx, World(layers=[]))

    assert not result.success
    assert result.error == "Only characters can trade"
    assert actor.gold == 30
    assert merchant.gold == 100
    assert seller.inventory == [item]
    assert (actor if seller is merchant else merchant).inventory == []
    assert emitted_events == []


def test_trade_returns_validation_error_without_transferring_gold(
    trade: tuple[TradeHandler, ActionType],
    actor: Character,
    merchant: Npc,
    emit_fn: EmitFn,
    emitted_events: list[Event],
) -> None:
    handler, action_type = trade
    action = Action(name=action_type, params={"merchant_id": merchant.id, "item_id": "missing"})
    ctx = ActionContext(is_combat=False, get_entity={merchant.id: merchant}.get)

    result = handler(actor, action, emit_fn, ctx, World(layers=[]))

    assert not result.success
    assert result.error == (
        "Merchant does not have that item" if action_type == ActionType.BUY else "You don't have that item"
    )
    assert actor.gold == 30
    assert merchant.gold == 100
    assert actor.inventory == []
    assert merchant.inventory == []
    assert emitted_events == []


def test_trade_transfers_item_and_gold_and_emits_event(
    trade: tuple[TradeHandler, ActionType],
    actor: Character,
    merchant: Npc,
    emit_fn: EmitFn,
    emitted_events: list[Event],
) -> None:
    handler, action_type = trade
    item = Item(id="potion_0", name="Potion", item_type=ItemType.POTION, price=10)
    seller, buyer = (merchant, actor) if action_type == ActionType.BUY else (actor, merchant)
    seller.inventory = [item]
    action = Action(name=action_type, params={"merchant_id": merchant.id, "item_id": item.id})
    ctx = ActionContext(is_combat=False, get_entity={merchant.id: merchant}.get)

    result = handler(actor, action, emit_fn, ctx, World(layers=[]))

    assert result.success
    assert result.error == ""
    assert seller.inventory == []
    assert buyer.inventory == [item]
    assert actor.gold == (20 if action_type == ActionType.BUY else 40)
    assert merchant.gold == (110 if action_type == ActionType.BUY else 90)
    expected_payload = (
        BuyPayload(actor.id, merchant.id, item.name, 10, item.id)
        if action_type == ActionType.BUY
        else SellPayload(actor.id, merchant.id, item.name, 10, item.id)
    )
    assert emitted_events == [
        Event(
            event_type=EventType.ENTITY_BUY if action_type == ActionType.BUY else EventType.ENTITY_SELL,
            source_layer="entities",
            data=expected_payload,
        )
    ]
