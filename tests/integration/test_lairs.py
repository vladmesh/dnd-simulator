"""Lair / EcologyLayer integration tests.

Tests run against a live backend in docker compose with:
- DND_DICE_SEED=42 (deterministic rolls)
- lair_world: cave + cave_mouth, a goblin warren (boss core + 2 minions),
  faction "goblins" with no relations so a factionless player stays NEUTRAL
  (the roster materializes without auto-combat).

Activation (materialize / dematerialize) runs at the start of each round loop
iteration, so the tests keep one WS connection open and drive the loop with
``end_turn`` actions: ending a turn lets the loop advance and re-run activation
with the player's current location. Disconnecting and reconnecting would replay
the cached turn instead of re-activating, so it can't drive movement.
"""

from __future__ import annotations

from http import HTTPStatus

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

# ── Fixtures & helpers ───────────────────────────────────────────────


def _create_lair_session(backend_url: str, api_url: str, player_api_url: str) -> tuple[str, str, str]:
    """Create a lair_world session with a player at the cave. Returns (ws_base, session_id, player_id)."""
    ws_base = backend_url.replace("http://", "ws://") + "/api/ws"
    resp = requests.post(
        f"{api_url}/sessions",
        json={"world_name": "lair_world", "lang": "en"},
        timeout=10,
    )
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    resp = requests.post(
        f"{player_api_url}/sessions/{sid}/character",
        json={
            "name": "Lair Tester",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "start_location": "cave",
            "ability_scores": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
            "fighting_style": "defense",
        },
        timeout=10,
    )
    resp.raise_for_status()
    pid = resp.json()["player_id"]
    return ws_base, sid, pid


def _get_turn(sock: ws_lib.WebSocket, max_msgs: int = 40) -> dict[str, object]:
    """Drain messages until the player's turn arrives (activation has run by then)."""
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == "turn":
            return msg
    raise AssertionError("Never received a turn message")


def _advance_turn(sock: ws_lib.WebSocket) -> dict[str, object]:
    """End the player's turn and wait for the next — forces a fresh activation pass."""
    ws_send_action(sock, "end_turn")
    return _get_turn(sock)


def _recv_until(sock: ws_lib.WebSocket, msg_type: str, max_msgs: int = 40) -> dict[str, object]:
    """Drain messages until one of `msg_type` arrives."""
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == msg_type:
            return msg
    raise AssertionError(f"Never received a '{msg_type}' message")


def _nearby(turn: dict[str, object], entity_id: str) -> dict[str, object] | None:
    """Find a nearby entity in a turn message's peaceful awareness."""
    awareness = turn["awareness"]
    assert isinstance(awareness, dict)
    nearby = awareness.get("nearby", [])
    assert isinstance(nearby, list)
    return next((n for n in nearby if n["id"] == entity_id), None)


def _monsters_at(api_url: str, sid: str, location_id: str = "cave") -> list[dict[str, object]]:
    """Active non-player creatures at a location (the materialized lair roster)."""
    resp = requests.get(
        f"{api_url}/sessions/{sid}/creatures",
        params={"location_id": location_id, "active": "true"},
        timeout=5,
    )
    resp.raise_for_status()
    return [c for c in resp.json() if c["entity_type"] != "player"]


def _move_player(api_url: str, sid: str, pid: str, location_id: str) -> None:
    """Teleport the player to a location via the master patch control."""
    resp = requests.patch(
        f"{api_url}/sessions/{sid}/creatures/{pid}",
        json={"location_id": location_id},
        timeout=5,
    )
    resp.raise_for_status()


# ── Lair world loads ─────────────────────────────────────────────────


class TestLairWorldLoads:
    """Verify lair_world loads and the EcologyLayer accepts lairs."""

    def test_create_session_with_lair(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """EcologyLayer + lair + factions load without errors."""
        _ws_base, sid, _pid = _create_lair_session(backend_url, api_url, player_api_url)

        resp = requests.get(f"{api_url}/sessions/{sid}", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["session_id"] == sid
        assert [r["id"] for r in data["regions"]] == ["caverns"]

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Materialization ──────────────────────────────────────────────────


class TestLairMaterialization:
    """Entering a lair location spawns its full roster (core + minions)."""

    def test_lair_materializes_core_and_minions(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """Player at the cave triggers the warren to spawn the boss and both goblins."""
        ws_base, sid, pid = _create_lair_session(backend_url, api_url, player_api_url)

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)
            monsters = _monsters_at(api_url, sid, "cave")
        finally:
            sock.close()

        names = sorted(c["name"] for c in monsters)
        assert names == ["Goblin", "Goblin", "Goblin Boss"], f"Expected full roster, got {names}"

        # Core/boss carries its own template stats (distinct from the minions).
        boss = next(c for c in monsters if c["name"] == "Goblin Boss")
        assert boss["max_hp"] == 21
        assert boss["ac"] == 17

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Depletion (core death) ───────────────────────────────────────────


class TestLairDepletion:
    """Killing the core depletes the lair permanently — no respawn on return."""

    def test_core_death_depletes_lair(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """Boss dies → leave → return → the warren is empty (depleted, not respawned)."""
        ws_base, sid, pid = _create_lair_session(backend_url, api_url, player_api_url)

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)  # enter: roster materializes
            boss = next(c for c in _monsters_at(api_url, sid, "cave") if c["name"] == "Goblin Boss")

            # Kill the core while the round is blocked on the player's turn.
            resp = requests.delete(f"{api_url}/sessions/{sid}/creatures/{boss['id']}", timeout=5)
            assert resp.status_code == HTTPStatus.OK

            # Leave: the next activation dematerializes the lair and, core dead, depletes it.
            _move_player(api_url, sid, pid, "cave_mouth")
            _advance_turn(sock)

            # Return: a depleted lair spawns nothing.
            _move_player(api_url, sid, pid, "cave")
            _advance_turn(sock)
            assert _monsters_at(api_url, sid, "cave") == []
        finally:
            sock.close()

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Save/load persistence ────────────────────────────────────────────


class TestLairSaveLoad:
    """Depleted state survives a save/load round-trip."""

    def test_depleted_state_survives_save_load(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """Deplete the warren, save+load, and confirm it stays empty on return."""
        ws_base, sid, pid = _create_lair_session(backend_url, api_url, player_api_url)

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)
            boss = next(c for c in _monsters_at(api_url, sid, "cave") if c["name"] == "Goblin Boss")
            requests.delete(f"{api_url}/sessions/{sid}/creatures/{boss['id']}", timeout=5).raise_for_status()
            _move_player(api_url, sid, pid, "cave_mouth")
            _advance_turn(sock)  # dematerialize + deplete

            # Save and load while the round is blocked on the player's turn.
            resp = requests.post(f"{api_url}/sessions/{sid}/save?name=lair_depleted", timeout=10)
            assert resp.status_code == HTTPStatus.OK
            resp = requests.post(f"{api_url}/sessions/{sid}/saves/lair_depleted/load", timeout=10)
            assert resp.status_code == HTTPStatus.OK

            # Return after load: depletion persisted, nothing spawns.
            _move_player(api_url, sid, pid, "cave")
            _advance_turn(sock)
            assert _monsters_at(api_url, sid, "cave") == []
        finally:
            sock.close()

        requests.delete(f"{api_url}/sessions/{sid}/saves/lair_depleted", timeout=5)
        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Treasury (loot gated behind the core) ────────────────────────────

TREASURY_ID = "goblin_warren_treasury"


class TestLairTreasury:
    """A lair treasury: spawned from content, locked until the boss dies, lootable after."""

    def test_treasury_gated_then_looted_on_core_death(
        self, backend_url: str, api_url: str, player_api_url: str
    ) -> None:
        """Boss alive → treasury locked. Kill boss → treasury unlocks → take grants the sword + 100 gold."""
        ws_base, sid, pid = _create_lair_session(backend_url, api_url, player_api_url)

        sock = ws_connect(ws_base, sid, pid)
        try:
            turn = _get_turn(sock)  # enter: roster + treasury spawn
            chest = _nearby(turn, TREASURY_ID)
            assert chest is not None, "treasury should be visible at the lair"
            assert chest["lootable"] is False, "treasury is locked while the boss lives"

            # Kill the core via master control (no combat needed).
            boss = next(c for c in _monsters_at(api_url, sid, "cave") if c["name"] == "Goblin Boss")
            requests.delete(f"{api_url}/sessions/{sid}/creatures/{boss['id']}", timeout=5).raise_for_status()

            # Next activation pass recomputes the gate from the (now dead) core.
            turn = _advance_turn(sock)
            chest = _nearby(turn, TREASURY_ID)
            assert chest is not None and chest["lootable"] is True
            assert chest["loot_gold"] == 100
            assert "Flaming Longsword" in [i["name"] for i in chest["loot_items"]]

            gold_before = turn["player"]["gold"]
            ws_send_action(sock, "take", target_id=TREASURY_ID)
            result = _recv_until(sock, "action_result")
            assert result["action"] == "take"
            assert result["player"]["gold"] == gold_before + 100
            assert "Flaming Longsword" in [i["name"] for i in result["player"]["inventory"]]
        finally:
            sock.close()

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_treasury_does_not_refill_on_return(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """Loot the treasury, leave, return → it's still present and empty (no refill)."""
        ws_base, sid, pid = _create_lair_session(backend_url, api_url, player_api_url)

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)
            boss = next(c for c in _monsters_at(api_url, sid, "cave") if c["name"] == "Goblin Boss")
            requests.delete(f"{api_url}/sessions/{sid}/creatures/{boss['id']}", timeout=5).raise_for_status()
            _advance_turn(sock)  # unlock
            ws_send_action(sock, "take", target_id=TREASURY_ID)
            _recv_until(sock, "action_result")

            # Leave and return — the depleted lair spawns nothing, treasury persists empty.
            _move_player(api_url, sid, pid, "cave_mouth")
            _advance_turn(sock)
            _move_player(api_url, sid, pid, "cave")
            turn = _advance_turn(sock)

            chest = _nearby(turn, TREASURY_ID)
            assert chest is not None, "treasury persists across leave/return"
            assert chest["loot_gold"] == 0
            assert chest["loot_items"] == []
        finally:
            sock.close()

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_looted_treasury_survives_save_load(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """Loot, save+load → the treasury stays empty (looted state persisted via the Container entity)."""
        ws_base, sid, pid = _create_lair_session(backend_url, api_url, player_api_url)

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)
            boss = next(c for c in _monsters_at(api_url, sid, "cave") if c["name"] == "Goblin Boss")
            requests.delete(f"{api_url}/sessions/{sid}/creatures/{boss['id']}", timeout=5).raise_for_status()
            _advance_turn(sock)
            ws_send_action(sock, "take", target_id=TREASURY_ID)
            _recv_until(sock, "action_result")

            resp = requests.post(f"{api_url}/sessions/{sid}/save?name=lair_looted", timeout=10)
            assert resp.status_code == HTTPStatus.OK
            resp = requests.post(f"{api_url}/sessions/{sid}/saves/lair_looted/load", timeout=10)
            assert resp.status_code == HTTPStatus.OK

            turn = _advance_turn(sock)
            chest = _nearby(turn, TREASURY_ID)
            assert chest is not None
            assert chest["loot_gold"] == 0
            assert chest["loot_items"] == []
        finally:
            sock.close()

        requests.delete(f"{api_url}/sessions/{sid}/saves/lair_looted", timeout=5)
        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
