"""Region encounter-table integration tests (Sprint 018 phase 3).

Tests run against a live backend in docker compose with ``encounter_world``:
- region ``wilds`` carries a regional goblin table;
- ``wild_den`` (in wilds) overrides with its own wolf table;
- ``border_post`` (region ``borderlands``) has no table at all.

The player is factionless, so spawned monsters stay NEUTRAL (no auto-combat) and
simply appear at the location. Encounter rolls fire when a creature enters a
location, so connecting and reading the first ``turn`` (activation has run by
then) is enough to observe the spawn. The tables use ``chance: 1.0`` and
``count: [1, 1]`` so the roll is deterministic without seeding ``random``.
"""

from __future__ import annotations

import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv

# ── Fixtures & helpers ───────────────────────────────────────────────


def _create_session(backend_url: str, api_url: str, player_api_url: str, start_location: str) -> tuple[str, str, str]:
    """Create an encounter_world session with a factionless player. Returns (ws_base, sid, pid)."""
    ws_base = backend_url.replace("http://", "ws://") + "/api/ws"
    resp = requests.post(
        f"{api_url}/sessions",
        json={"world_name": "encounter_world", "lang": "en"},
        timeout=10,
    )
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    resp = requests.post(
        f"{player_api_url}/sessions/{sid}/character",
        json={
            "name": "Ranger",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "start_location": start_location,
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


def _monster_names_at(api_url: str, sid: str, location_id: str) -> list[str]:
    """Names of active non-player creatures at a location (the encounter spawns)."""
    resp = requests.get(
        f"{api_url}/sessions/{sid}/creatures",
        params={"location_id": location_id, "active": "true"},
        timeout=5,
    )
    resp.raise_for_status()
    return sorted(c["name"] for c in resp.json() if c["entity_type"] != "player")


# ── Fallthrough: tableless location rolls the region table ───────────


class TestRegionFallthrough:
    def test_tableless_location_rolls_region_table(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """wild_trail has no table of its own → it rolls the regional goblin table."""
        ws_base, sid, pid = _create_session(backend_url, api_url, player_api_url, "wild_trail")

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)
            names = _monster_names_at(api_url, sid, "wild_trail")
        finally:
            sock.close()

        assert "Goblin" in names, f"expected a regional goblin spawn, got {names}"

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_region_without_table_stays_empty(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """border_post is in a region with no table (and no own table) → nothing spawns."""
        ws_base, sid, pid = _create_session(backend_url, api_url, player_api_url, "border_post")

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)
            names = _monster_names_at(api_url, sid, "border_post")
        finally:
            sock.close()

        assert names == [], f"expected no spawns outside any table, got {names}"

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Override: own table beats the region default ─────────────────────


class TestRegionOverride:
    def test_own_table_overrides_region(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """wild_den has its own wolf table → it rolls wolves, never the regional goblins."""
        ws_base, sid, pid = _create_session(backend_url, api_url, player_api_url, "wild_den")

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)
            names = _monster_names_at(api_url, sid, "wild_den")
        finally:
            sock.close()

        assert "Wolf" in names, f"expected the location's own wolf spawn, got {names}"
        assert "Goblin" not in names, f"regional goblins must not leak into an overridden location: {names}"

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Time of day: night-only table fires after dark, not by day ───────


class TestTimeOfDayEncounter:
    """night_marsh (borderlands, latitude 45) has a night-only wolf table.

    The world starts at month 6, hour 10 (day). Encounter rolls happen in the
    round loop on connect, at the current world time; advancing the clock ticks
    layers without rolling. So advancing into the night before connecting makes
    the first activation roll at night.
    """

    def test_night_table_silent_by_day(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """At the default day start, the night-only marsh table does not fire."""
        ws_base, sid, pid = _create_session(backend_url, api_url, player_api_url, "night_marsh")

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)
            names = _monster_names_at(api_url, sid, "night_marsh")
        finally:
            sock.close()

        assert names == [], f"night-only table must stay empty by day, got {names}"

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_night_table_fires_after_dark(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """Advancing the clock into the night before connecting makes the night-only wolf spawn."""
        ws_base, sid, pid = _create_session(backend_url, api_url, player_api_url, "night_marsh")

        # 10:00 + 16h → 02:00 next day, still month 6 → night at latitude 45.
        resp = requests.post(f"{api_url}/sessions/{sid}/time/advance", json={"hours": 16}, timeout=10)
        resp.raise_for_status()

        sock = ws_connect(ws_base, sid, pid)
        try:
            _get_turn(sock)
            names = _monster_names_at(api_url, sid, "night_marsh")
        finally:
            sock.close()

        assert "Wolf" in names, f"expected the night-only wolf spawn after dark, got {names}"

        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
