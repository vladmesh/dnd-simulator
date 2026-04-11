"""Integration tests: Long Rest and Short Rest actions.

Tests run against a live backend in docker compose with:
- DND_DICE_SEED=42 (deterministic rolls)
- village world: peaceful mode, fighter with Second Wind resource

Each test creates its own session to avoid state pollution.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import requests
from conftest import ws_connect, ws_recv, ws_send_action

WORLD = "village"
LOCATION = "village_square"


def _create_fighter_session(api_url: str, player_api_url: str) -> tuple[str, str]:
    """Create village session + fighter character. Returns (session_id, player_id)."""
    resp = requests.post(
        f"{api_url}/sessions",
        json={"world_name": WORLD, "lang": "en"},
        timeout=10,
    )
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    resp = requests.post(
        f"{player_api_url}/sessions/{sid}/character",
        json={
            "name": "Rest Fighter",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "start_location": LOCATION,
            "ability_scores": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
        },
        timeout=10,
    )
    resp.raise_for_status()
    return sid, resp.json()["player_id"]


def _get_creature(api_url: str, sid: str, entity_id: str) -> dict[str, Any]:
    """Get creature details via master REST API."""
    resp = requests.get(f"{api_url}/sessions/{sid}/creatures/{entity_id}", timeout=10)
    assert resp.status_code == HTTPStatus.OK
    return resp.json()


def _get_turn(sock: Any, max_msgs: int = 30) -> dict[str, Any]:
    """Receive messages until a turn message arrives."""
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        if msg["type"] == "turn":
            return msg
    raise AssertionError("Never received turn message")


def _collect_until_turn(
    sock: Any,
    max_msgs: int = 40,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Collect all messages until next turn. Returns (messages, turn_msg)."""
    messages: list[dict[str, Any]] = []
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        messages.append(msg)
        if msg["type"] == "turn":
            return messages, msg
    raise AssertionError("Never received next turn message")


class TestRestActions:
    def test_long_rest_restores_hp_and_resources(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Long rest heals to full HP and resets resource pools (Second Wind)."""
        sid, pid = _create_fighter_session(api_url, player_api_url)
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                assert turn["mode"] == "peaceful"

                # Damage the fighter and deplete Second Wind via PATCH + action
                requests.patch(
                    f"{api_url}/sessions/{sid}/creatures/{pid}",
                    json={"current_hp": 5},
                    timeout=10,
                ).raise_for_status()

                # Use Second Wind to deplete the resource
                ws_send_action(sock, "second_wind")
                _, _ = _collect_until_turn(sock)

                # Verify resource is exhausted
                creature = _get_creature(api_url, sid, pid)
                pools = {p["id"]: p for p in creature["resource_pools"]}
                assert pools["second_wind"]["current_uses"] == 0

                # Damage again so long rest has something to heal
                requests.patch(
                    f"{api_url}/sessions/{sid}/creatures/{pid}",
                    json={"current_hp": 5},
                    timeout=10,
                ).raise_for_status()

                # Take a long rest
                ws_send_action(sock, "long_rest")
                _, _ = _collect_until_turn(sock)

                # Verify HP restored to max
                creature2 = _get_creature(api_url, sid, pid)
                assert creature2["hp"] == creature2["max_hp"], (
                    f"Long rest should heal to full: {creature2['hp']}/{creature2['max_hp']}"
                )

                # Verify Second Wind resource restored (short_rest pool, long rest resets all)
                pools2 = {p["id"]: p for p in creature2["resource_pools"]}
                assert pools2["second_wind"]["current_uses"] == pools2["second_wind"]["max_uses"], (
                    f"Long rest should reset Second Wind: {pools2['second_wind']}"
                )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_short_rest_restores_short_rest_resources(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """Short rest resets short-rest pools (Second Wind) but does NOT heal."""
        sid, pid = _create_fighter_session(api_url, player_api_url)
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                assert turn["mode"] == "peaceful"

                # Damage the fighter and use Second Wind
                requests.patch(
                    f"{api_url}/sessions/{sid}/creatures/{pid}",
                    json={"current_hp": 5},
                    timeout=10,
                ).raise_for_status()

                ws_send_action(sock, "second_wind")
                _, _ = _collect_until_turn(sock)

                # Verify resource exhausted
                creature = _get_creature(api_url, sid, pid)
                pools = {p["id"]: p for p in creature["resource_pools"]}
                assert pools["second_wind"]["current_uses"] == 0

                # Record current HP (Second Wind healed some, but not full)
                hp_before_rest = creature["hp"]

                # Take a short rest
                ws_send_action(sock, "short_rest")
                _, _ = _collect_until_turn(sock)

                # Verify resource restored
                creature2 = _get_creature(api_url, sid, pid)
                pools2 = {p["id"]: p for p in creature2["resource_pools"]}
                assert pools2["second_wind"]["current_uses"] == pools2["second_wind"]["max_uses"], (
                    f"Short rest should reset Second Wind: {pools2['second_wind']}"
                )

                # Verify HP NOT restored (short rest doesn't heal in our implementation)
                assert creature2["hp"] == hp_before_rest, (
                    f"Short rest should not heal: expected {hp_before_rest}, got {creature2['hp']}"
                )
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_rest_actions_available_in_peaceful_mode(self, api_url: str, player_api_url: str, ws_base_url: str) -> None:
        """Rest actions appear in available_actions during peaceful mode."""
        sid, pid = _create_fighter_session(api_url, player_api_url)
        try:
            sock = ws_connect(ws_base_url, sid, pid)
            try:
                turn = _get_turn(sock)
                assert turn["mode"] == "peaceful"

                actions = {a["name"] for a in turn["awareness"]["available_actions"]}
                assert "long_rest" in actions, f"long_rest should be available, got: {actions}"
                assert "short_rest" in actions, f"short_rest should be available, got: {actions}"
            finally:
                sock.close()
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
