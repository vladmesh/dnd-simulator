"""Trading integration tests.

Tests buy/sell actions through the WebSocket against a live backend
with a merchant NPC (Masha) at village_square who sells Health Potions (50g) and Daggers (10g).
Player starts at village_square with 100 gold.
"""

from __future__ import annotations

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action


def _recv_until(sock: ws_lib.WebSocket, target_type: str, max_msgs: int = 15) -> dict | None:
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == target_type:
            return msg
    return None


def _make_trade_session(urls: tuple[str, str, str], gold: int | None = None) -> tuple[str, str, str]:
    """Create a village session with a player at village_square (same loc as merchant).

    If *gold* is specified, patch player's gold to that amount after creation.
    """
    api, player_api, ws_base = urls
    resp = requests.post(f"{api}/sessions", json={"world_name": "village", "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    resp = requests.post(
        f"{player_api}/sessions/{sid}/character",
        json={
            "name": "Trader",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "start_location": "millbrook_market",
            "ability_scores": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
        },
        timeout=10,
    )
    resp.raise_for_status()
    pid = resp.json()["player_id"]

    if gold is not None:
        requests.patch(
            f"{api}/sessions/{sid}/creatures/{pid}",
            json={"gold": gold},
            timeout=10,
        ).raise_for_status()

    return ws_base, sid, pid


class TestTrading:
    """Phase 3: buy/sell items from merchants via WS."""

    @staticmethod
    def _urls(backend_url: str) -> tuple[str, str, str]:
        api = f"{backend_url}/api/master"
        player_api = f"{backend_url}/api/player"
        ws_base = backend_url.replace("http://", "ws://") + "/api/ws"
        return api, player_api, ws_base

    def test_merchants_in_awareness(self, backend_url: str) -> None:
        """Turn message includes merchants array when merchant is at same location."""
        urls = self._urls(backend_url)
        ws_base, sid, pid = _make_trade_session(urls)
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
            merchants = msg["awareness"]["merchants"]
            assert len(merchants) >= 1
            masha = next(m for m in merchants if m["id"] == "masha")
            assert masha["name"] == "Маша-торговка"
            assert masha["gold"] == 200
            assert len(masha["items"]) >= 2
            item_names = [i["name"] for i in masha["items"]]
            assert "Health Potion" in item_names
            assert "Dagger" in item_names
            # Items have prices
            for item in masha["items"]:
                assert "price" in item
                assert item["price"] > 0
        finally:
            sock.close()
            requests.delete(f"{urls[0]}/sessions/{sid}", timeout=10)

    def test_buy_item(self, backend_url: str) -> None:
        """Buy a dagger from merchant — gold decreases, item appears in inventory."""
        urls = self._urls(backend_url)
        ws_base, sid, pid = _make_trade_session(urls)
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"

            # Find dagger item_id from merchant
            merchants = msg["awareness"]["merchants"]
            masha = next(m for m in merchants if m["id"] == "masha")
            dagger = next(i for i in masha["items"] if i["name"] == "Dagger")
            dagger_id = dagger["id"]

            ws_send_action(sock, "buy", merchant_id="masha", item_id=dagger_id)

            # Should get action_result with updated gold and inventory
            result = _recv_until(sock, "action_result")
            assert result is not None, "Never received action_result for buy"
            assert result["action"] == "buy"
            assert result["player"]["gold"] == 990  # 1000 - 10
            inv_names = [i["name"] for i in result["player"]["inventory"]]
            assert "Dagger" in inv_names
        finally:
            sock.close()
            requests.delete(f"{urls[0]}/sessions/{sid}", timeout=10)

    def test_buy_insufficient_gold(self, backend_url: str) -> None:
        """Buying with insufficient gold doesn't deduct gold — next turn still shows original amount."""
        urls = self._urls(backend_url)
        ws_base, sid, pid = _make_trade_session(urls, gold=5)  # only 5 gold, dagger costs 10
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"

            merchants = msg["awareness"]["merchants"]
            masha = next(m for m in merchants if m["id"] == "masha")
            dagger = next(i for i in masha["items"] if i["name"] == "Dagger")
            dagger_id = dagger["id"]

            ws_send_action(sock, "buy", merchant_id="masha", item_id=dagger_id)

            # Failed buy in peaceful mode: server breaks the turn without sending action_result,
            # so the next message will be a new turn. Gold must be unchanged.
            turn = _recv_until(sock, "turn")
            assert turn is not None, "Never received next turn after failed buy"
            assert turn["player"]["gold"] == 5
            # Dagger should NOT be in player inventory
            inv_names = [i["name"] for i in turn["player"]["inventory"]]
            assert "Dagger" not in inv_names
        finally:
            sock.close()
            requests.delete(f"{urls[0]}/sessions/{sid}", timeout=10)

    def test_sell_item(self, backend_url: str) -> None:
        """Sell an item to merchant — gold increases, item removed from inventory."""
        urls = self._urls(backend_url)
        api, _, _ = urls
        ws_base, sid, pid = _make_trade_session(urls, gold=100)

        # Give player an item with a price to sell
        requests.post(
            f"{api}/sessions/{sid}/creatures/{pid}/items",
            json={
                "name": "Old Sword",
                "type": "weapon",
                "weapon_id": "old_sword",
                "category": "simple",
                "attack_name": "slash",
                "damage": [{"dice": "1d6", "type": "slashing"}],
                "ability": "str",
                "price": 25,
            },
            timeout=10,
        ).raise_for_status()

        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"

            # Find the Old Sword in inventory
            inventory = msg["player"]["inventory"]
            old_sword = next(i for i in inventory if i["name"] == "Old Sword")
            sword_id = old_sword["id"]

            ws_send_action(sock, "sell", merchant_id="masha", item_id=sword_id)

            result = _recv_until(sock, "action_result")
            assert result is not None, "Never received action_result for sell"
            assert result["action"] == "sell"
            assert result["player"]["gold"] == 1025  # 1000 + 25
            inv_names = [i["name"] for i in result["player"]["inventory"]]
            assert "Old Sword" not in inv_names
        finally:
            sock.close()
            requests.delete(f"{urls[0]}/sessions/{sid}", timeout=10)

    def test_buy_updates_merchant_inventory(self, backend_url: str) -> None:
        """After buying, next turn shows updated merchant inventory (item removed)."""
        urls = self._urls(backend_url)
        ws_base, sid, pid = _make_trade_session(urls)
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"

            merchants = msg["awareness"]["merchants"]
            masha = next(m for m in merchants if m["id"] == "masha")
            dagger = next(i for i in masha["items"] if i["name"] == "Dagger")
            dagger_id = dagger["id"]
            initial_item_count = len(masha["items"])

            ws_send_action(sock, "buy", merchant_id="masha", item_id=dagger_id)

            # Wait for next turn message
            turn = _recv_until(sock, "turn")
            assert turn is not None, "Never received next turn after buy"
            merchants = turn["awareness"]["merchants"]
            masha = next(m for m in merchants if m["id"] == "masha")
            # Merchant should have one fewer item
            assert len(masha["items"]) == initial_item_count - 1
        finally:
            sock.close()
            requests.delete(f"{urls[0]}/sessions/{sid}", timeout=10)
