"""Integration tests: Reputation mechanics through the live API.

Tests run against a live backend in docker compose with:
- DND_DICE_SEED=42 (deterministic rolls)
- reputation_test world: 3x3 battle map, neutral NPC with 1 HP

Each test creates its own session to avoid state pollution.
"""

from __future__ import annotations

from typing import Any

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

WORLD = "reputation_test"
LOCATION = "test_floor"


# ── Helpers ──────────────────────────────────────────────────────────────


def _create_session(api_url: str, player_api_url: str) -> tuple[str, str]:
    """Create session + player character (fighter, hero_faction). Returns (session_id, player_id)."""
    resp = requests.post(f"{api_url}/sessions", json={"world_name": WORLD, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    resp = requests.post(
        f"{player_api_url}/sessions/{sid}/character",
        json={
            "name": "Test Fighter",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "start_location": LOCATION,
            "ability_scores": {"str": 15, "dex": 11, "con": 14, "int": 10, "wis": 10, "cha": 9},
        },
        timeout=10,
    )
    resp.raise_for_status()
    return sid, resp.json()["player_id"]


def _get_turn(sock: ws_lib.WebSocket, max_msgs: int = 30) -> dict[str, Any]:
    """Receive messages until a turn message arrives."""
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == "turn":
            return msg
    raise AssertionError("Never received turn message")


def _collect_all_until_turn(
    sock: ws_lib.WebSocket,
    max_msgs: int = 60,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collect all messages until next turn. Returns (all_messages, turn_msg)."""
    messages: list[dict[str, Any]] = []
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        messages.append(msg)
        if msg["type"] == "turn":
            return messages, msg
    raise AssertionError("Never received next turn message")


def _extract_events(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract all events from a list of WS messages."""
    events: list[dict[str, Any]] = []
    for msg in messages:
        events.extend(msg.get("events", []))
    return events


def _find_event(events: list[dict[str, Any]], event_type: str) -> dict[str, Any] | None:
    """Find first event of the given type."""
    for e in events:
        if e.get("event_type") == event_type:
            return e
    return None


# ── Tests ────────────────────────────────────────────────────────────────


class TestKillReputationDrop:
    """Killing a neutral NPC drops reputation with their faction."""

    def test_kill_neutral_npc_emits_reputation_changed(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """Attack a 1-HP neutral NPC → kill → reputation_changed event with negative delta."""
        sid, pid = _create_session(api_url, player_api_url)
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                assert turn["mode"] == "peaceful", f"Expected peaceful mode, got {turn['mode']}"

                # Find the neutral NPC
                nearby = turn["awareness"]["nearby"]
                npc = next((e for e in nearby if e["name"] == "Weak Neutral"), None)
                assert npc is not None, f"Expected Weak Neutral NPC, got: {[e['name'] for e in nearby]}"
                npc_id = npc["id"]

                # Attack the neutral NPC — triggers auto-hostility combat
                ws_send_action(sock, "attack", target_id=npc_id)

                # Collect all messages until we get our next turn (after NPC dies in 1 hit)
                # The flow: attack → combat starts → NPC dies → combat ends → peace turn
                messages: list[dict[str, Any]] = []
                final_turn = None
                for _ in range(80):
                    msg = ws_recv(sock)
                    messages.append(msg)
                    # We want to collect everything until combat is over
                    if msg["type"] == "turn" and msg.get("mode") == "peaceful":
                        final_turn = msg
                        break
                    # If we get a combat turn, NPC might still be alive (unlikely with 1 HP)
                    if msg["type"] == "turn" and msg.get("mode") == "combat":
                        # Attack again if combat continues
                        ws_send_action(sock, "attack", target_id=npc_id)

                assert final_turn is not None, "Never returned to peace mode after killing NPC"

                events = _extract_events(messages)
                event_types = [e.get("event_type") for e in events]

                # Should have entity_died
                died_event = _find_event(events, "entity_died")
                assert died_event is not None, f"Expected entity_died, got: {event_types}"

                # Should have reputation_changed
                rep_event = _find_event(events, "reputation_changed")
                assert rep_event is not None, f"Expected reputation_changed, got: {event_types}"

            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=15)
