"""Tests for trade UI: merchant awareness via WS, buy/sell actions."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.core.character import NpcRole
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_client(tmp_path: object) -> tuple[TestClient, GameService]:
    store = JsonFileStore(Path(str(tmp_path)) / "saves")
    service = GameService(store=store)
    set_service(service)
    return TestClient(app), service


def _create_session_with_player(client: TestClient) -> str:
    resp = client.post("/api/master/sessions", json={})
    assert resp.status_code == 200
    sid = resp.json()["session_id"]
    resp = client.post(
        f"/api/player/sessions/{sid}/character",
        json={"name": "Tester", "race": "human", "char_class": "fighter"},
    )
    assert resp.status_code == 200
    return sid


def _get_entities_layer(service: GameService, session_id: str) -> EntitiesLayer:
    session = service.get_session(session_id)
    for layer in session.world.layers:
        if isinstance(layer, EntitiesLayer):
            return layer
    raise RuntimeError("No EntitiesLayer found")


def _get_player(service: GameService, session_id: str) -> object:
    session = service.get_session(session_id)
    player = session.get_player()
    assert player is not None
    return player


def _inject_merchant(service: GameService, session_id: str, gold: int = 500, items: list[Item] | None = None) -> Npc:
    """Add a merchant NPC at the player's location."""
    player = _get_player(service, session_id)
    entities_layer = _get_entities_layer(service, session_id)

    merchant = Npc(
        id="test_merchant",
        name="Gretta the Trader",
        role=NpcRole.MERCHANT,
        location_id=player.location_id,  # type: ignore[attr-defined]
        gold=gold,
    )
    if items is not None:
        merchant.inventory = items
    merchant.active = True

    entities_layer.add_entity(merchant)
    return merchant


def _health_potion(price: int = 50) -> Item:
    return Item(
        id="health_potion_test",
        name="Health Potion",
        item_type=ItemType.POTION,
        price=price,
        params={"heal_dice": "2d4+2"},
    )


def _dagger(price: int = 30) -> Item:
    return Item(id="dagger_test", name="Dagger", item_type=ItemType.WEAPON, price=price)


class TestMerchantAwarenessWs:
    def test_turn_awareness_contains_merchants(self, tmp_path: object) -> None:
        """When a merchant is co-located, turn awareness includes merchants list."""
        client, service = _make_client(tmp_path)
        sid = _create_session_with_player(client)
        potion = _health_potion(50)
        _inject_merchant(service, sid, gold=200, items=[potion])

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "turn"
            awareness = msg["awareness"]
            assert "merchants" in awareness
            merchants = awareness["merchants"]
            assert len(merchants) >= 1

            merchant = next(m for m in merchants if m["id"] == "test_merchant")
            assert merchant["name"] == "Gretta the Trader"
            assert merchant["gold"] == 200
            assert len(merchant["items"]) == 1
            assert merchant["items"][0]["id"] == "health_potion_test"
            assert merchant["items"][0]["price"] == 50

    def test_no_merchants_when_none_nearby(self, tmp_path: object) -> None:
        """Without a merchant at location, merchants list is empty."""
        client, _ = _make_client(tmp_path)
        sid = _create_session_with_player(client)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "turn"
            awareness = msg["awareness"]
            merchants = awareness.get("merchants", [])
            assert len(merchants) == 0


class TestBuyViaWs:
    def test_buy_item_updates_gold_and_inventory(self, tmp_path: object) -> None:
        """Buy via WS: player gold decreases, item appears in player inventory."""
        client, service = _make_client(tmp_path)
        sid = _create_session_with_player(client)
        potion = _health_potion(50)
        _inject_merchant(service, sid, gold=200, items=[potion])

        # Give player enough gold
        player = _get_player(service, sid)
        player.gold = 100  # type: ignore[attr-defined]

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "turn"

            ws.send_json(
                {
                    "type": "action",
                    "name": "buy",
                    "params": {"merchant_id": "test_merchant", "item_id": "health_potion_test"},
                }
            )

            msg = ws.receive_json()
            assert msg["type"] == "action_result"
            assert msg["action"] == "buy"

            # Player gold decreased by potion price
            assert msg["player"]["gold"] == 100 - 50
            # Potion in player inventory
            inv_ids = [i["id"] for i in (msg["player"].get("inventory") or [])]
            assert "health_potion_test" in inv_ids


class TestSellViaWs:
    def test_sell_item_updates_gold_and_inventory(self, tmp_path: object) -> None:
        """Sell via WS: player gold increases, item removed from player inventory."""
        client, service = _make_client(tmp_path)
        sid = _create_session_with_player(client)
        dagger = _dagger(30)

        # Give player the dagger
        player = _get_player(service, sid)
        player.inventory.append(dagger)  # type: ignore[attr-defined]

        _inject_merchant(service, sid, gold=200)

        with client.websocket_connect(f"/api/ws/{sid}") as ws:
            msg = ws.receive_json()
            assert msg["type"] == "turn"
            player_gold_before = msg["player"]["gold"]

            ws.send_json(
                {
                    "type": "action",
                    "name": "sell",
                    "params": {"merchant_id": "test_merchant", "item_id": "dagger_test"},
                }
            )

            msg = ws.receive_json()
            assert msg["type"] == "action_result"
            assert msg["action"] == "sell"

            # Player gold increased by dagger price
            assert msg["player"]["gold"] == player_gold_before + 30
            # Dagger no longer in player inventory
            inv_ids = [i["id"] for i in (msg["player"].get("inventory") or [])]
            assert "dagger_test" not in inv_ids
