"""Squad / EcologyLayer integration tests.

Tests run against a live backend in docker compose with:
- DND_DICE_SEED=42 (deterministic rolls)
- squad_world.yaml: 3 locations, patrol squad, factions
"""

from __future__ import annotations

import time
from http import HTTPStatus

import requests
from conftest import ws_connect, ws_recv

# ── Fixtures ─────────────────────────────────────────────────────────


def _create_squad_session(backend_url: str, api_url: str, player_api_url: str) -> tuple[str, str, str]:
    """Create a squad_world session with a player. Returns (ws_base, session_id, player_id)."""
    ws_base = backend_url.replace("http://", "ws://") + "/api/ws"
    resp = requests.post(
        f"{api_url}/sessions",
        json={"world_name": "squad_world", "lang": "en"},
        timeout=10,
    )
    resp.raise_for_status()
    sid = resp.json()["session_id"]

    resp = requests.post(
        f"{player_api_url}/sessions/{sid}/character",
        json={
            "name": "Squad Tester",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "start_location": "road_center",
            "ability_scores": {"str": 15, "dex": 14, "con": 14, "int": 10, "wis": 10, "cha": 8},
            "fighting_style": "defense",
        },
        timeout=10,
    )
    resp.raise_for_status()
    pid = resp.json()["player_id"]
    return ws_base, sid, pid


# ── Squad world loads ────────────────────────────────────────────────


class TestSquadWorldLoads:
    """Verify the squad_world.yaml loads and the session is functional."""

    def test_create_session_with_squads(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """EcologyLayer + squads + factions load without errors."""
        _ws_base, sid, _pid = _create_squad_session(backend_url, api_url, player_api_url)

        # World state endpoint works
        resp = requests.get(f"{api_url}/sessions/{sid}", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["session_id"] == sid
        assert len(data["regions"]) == 1
        assert data["regions"][0]["id"] == "testland"

        # Cleanup
        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_time_advancement_with_squads(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """Advancing time ticks EcologyLayer without crashing."""
        _ws_base, sid, _pid = _create_squad_session(backend_url, api_url, player_api_url)

        # Get initial time
        resp = requests.get(f"{api_url}/sessions/{sid}", timeout=5)
        initial_time = resp.json()["time"]

        # Advance 2 hours — enough for patrol tick_interval (3600s)
        resp = requests.post(
            f"{api_url}/sessions/{sid}/time/advance",
            json={"hours": 2},
            timeout=30,
        )
        assert resp.status_code == HTTPStatus.OK

        # Time actually advanced
        resp = requests.get(f"{api_url}/sessions/{sid}", timeout=5)
        assert resp.json()["time"] != initial_time

        # Cleanup
        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


# ── Save/load with squads ───────────────────────────────────────────


class TestSquadMaterialization:
    """Verify that squads materialize into creatures with correct stats."""

    def test_patrol_materializes_guards_at_player_location(
        self, backend_url: str, api_url: str, player_api_url: str
    ) -> None:
        """Patrol moves to player location and spawns guard creatures."""
        ws_base, sid, pid = _create_squad_session(backend_url, api_url, player_api_url)

        # Advance 1 hour — patrol (tick_interval=3600) moves road_west → road_center
        resp = requests.post(
            f"{api_url}/sessions/{sid}/time/advance",
            json={"hours": 1},
            timeout=30,
        )
        assert resp.status_code == HTTPStatus.OK

        # Connect via WS to trigger the round → update_activation → materialization
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
        finally:
            sock.close()

        time.sleep(0.5)  # let round thread finish activation

        # Query creatures at player location — should have materialized guards
        resp = requests.get(
            f"{api_url}/sessions/{sid}/creatures",
            params={"location_id": "road_center", "active": "true"},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        creatures = resp.json()

        # Filter out the player — guards are the remaining creatures
        guards = [c for c in creatures if c["entity_type"] != "player"]
        assert len(guards) >= 1, f"Expected materialized guards, got {creatures}"

        # All materialized creatures should be guards, not bandits
        for guard in guards:
            assert guard["name"] == "Guard", f"Expected 'Guard', got '{guard['name']}'"

    def test_materialized_guard_has_correct_stats(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """Materialized guard creature has SRD guard HP and AC."""
        ws_base, sid, pid = _create_squad_session(backend_url, api_url, player_api_url)

        resp = requests.post(
            f"{api_url}/sessions/{sid}/time/advance",
            json={"hours": 1},
            timeout=30,
        )
        assert resp.status_code == HTTPStatus.OK

        # Connect via WS to trigger the round → materialization
        sock = ws_connect(ws_base, sid, pid)
        try:
            msg = ws_recv(sock)
            assert msg["type"] == "turn"
        finally:
            sock.close()

        time.sleep(0.5)

        resp = requests.get(
            f"{api_url}/sessions/{sid}/creatures",
            params={"location_id": "road_center", "active": "true"},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        guards = [c for c in resp.json() if c["entity_type"] != "player"]
        assert len(guards) >= 1

        guard = guards[0]
        assert guard["max_hp"] == 11, f"Guard HP should be 11, got {guard['max_hp']}"
        assert guard["ac"] == 16, f"Guard AC should be 16, got {guard['ac']}"

        # Cleanup
        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


class TestSquadSaveLoad:
    """Verify squad state persists through save/load cycle."""

    def test_save_and_load_with_squads(self, backend_url: str, api_url: str, player_api_url: str) -> None:
        """Save and load a session with active squads."""
        _ws_base, sid, _pid = _create_squad_session(backend_url, api_url, player_api_url)

        # Advance time so squads have moved
        resp = requests.post(
            f"{api_url}/sessions/{sid}/time/advance",
            json={"hours": 2},
            timeout=30,
        )
        assert resp.status_code == HTTPStatus.OK

        # Save
        resp = requests.post(f"{api_url}/sessions/{sid}/save?name=squad_test", timeout=10)
        assert resp.status_code == HTTPStatus.OK

        # Load
        resp = requests.post(f"{api_url}/sessions/{sid}/saves/squad_test/load", timeout=10)
        assert resp.status_code == HTTPStatus.OK

        # Session still functional after load — advance time again
        resp = requests.post(
            f"{api_url}/sessions/{sid}/time/advance",
            json={"hours": 1},
            timeout=30,
        )
        assert resp.status_code == HTTPStatus.OK

        # Cleanup
        requests.delete(f"{api_url}/sessions/{sid}/saves/squad_test", timeout=5)
        requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
