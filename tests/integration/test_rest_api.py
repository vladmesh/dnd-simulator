"""REST API integration tests.

Tests run against a live backend in docker compose with:
- DND_DICE_SEED=42 (deterministic rolls)
- Test content (arena, village, sneak_test worlds, all rule-based)
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import requests

# ── Session lifecycle ─────────────────────────────────────────────────


class TestSessionLifecycle:
    def test_create_session(self, api_url: str) -> None:
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": "arena", "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert "session_id" in data
        session_id = data["session_id"]

        # Cleanup
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)

    def test_list_sessions(self, api_url: str, arena_session: str) -> None:
        resp = requests.get(f"{api_url}/sessions", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        sessions = resp.json()
        session_ids = [s["session_id"] for s in sessions]
        assert arena_session in session_ids

    def test_get_world_state(self, api_url: str, arena_session: str) -> None:
        resp = requests.get(f"{api_url}/sessions/{arena_session}", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["session_id"] == arena_session
        assert "time" in data
        assert len(data["entities"]) >= 4  # 4 arena NPCs

    def test_delete_session(self, api_url: str) -> None:
        # Create a throwaway session
        create = requests.post(
            f"{api_url}/sessions",
            json={"world_name": "sneak_test", "lang": "en"},
            timeout=10,
        )
        session_id = create.json()["session_id"]

        resp = requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)
        assert resp.status_code == HTTPStatus.OK

        # Verify gone
        resp = requests.get(f"{api_url}/sessions/{session_id}", timeout=5)
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_invalid_session_404(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/sessions/nonexistent", timeout=5)
        assert resp.status_code == HTTPStatus.NOT_FOUND


# ── World listing ─────────────────────────────────────────────────────


class TestWorldListing:
    def test_list_worlds(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/worlds", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        worlds = resp.json()
        world_ids = [w["id"] for w in worlds]
        assert "arena" in world_ids
        assert "village" in world_ids
        assert "sneak_test" in world_ids


# ── Player ────────────────────────────────────────────────────────────


class TestPlayer:
    def test_create_and_get_status(self, player_api_url: str, arena_session: str, arena_player: dict[str, Any]) -> None:
        assert arena_player["name"] == "Test Hero"
        assert arena_player["race"] == "human"
        assert arena_player["char_class"] == "fighter"

        # GET status should return same data
        resp = requests.get(
            f"{player_api_url}/sessions/{arena_session}/status",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        status = resp.json()
        assert status["player_id"] == arena_player["player_id"]
        # Fighter L1: CON 14 (+2) → HP = 10 + 2 = 12
        assert status["hp"] == 12
        # Chain mail (16) + shield (+2) = 18
        assert status["ac"] == 18
        assert status["location_id"] == "arena_floor"
        assert status["ability_scores"]["str"] == 15


# ── Paladin player creation ──────────────────────────────────────────


class TestPaladinPlayer:
    """Phase 2: Paladin class — character creation via API."""

    def test_create_paladin_player(self, api_url: str, player_api_url: str) -> None:
        """Create a Paladin player — verify HP, AC, class, starting equipment."""
        # Create a fresh session
        resp = requests.post(f"{api_url}/sessions", json={"world_name": "arena", "lang": "en"}, timeout=10)
        resp.raise_for_status()
        sid = resp.json()["session_id"]

        try:
            resp = requests.post(
                f"{player_api_url}/sessions/{sid}/character",
                json={
                    "name": "Sir Test",
                    "race": "human",
                    "char_class": "paladin",
                    "alignment": "lawful_good",
                    "start_location": "arena_floor",
                    "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 14},
                },
                timeout=10,
            )
            assert resp.status_code == HTTPStatus.OK
            data = resp.json()
            assert data["char_class"] == "paladin"

            # GET status — verify derived stats
            resp = requests.get(f"{player_api_url}/sessions/{sid}/status", timeout=5)
            assert resp.status_code == HTTPStatus.OK
            status = resp.json()
            # Paladin L1: d10 + CON 14 (+2) = 12
            assert status["hp"] == 12
            # Chain mail (16) + shield (+2) = 18
            assert status["ac"] == 18
            assert status["char_class"] == "paladin"
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)

    def test_paladin_npc_has_resource_pools(self, api_url: str, arena_session: str) -> None:
        """Paladin NPC loaded from YAML has lay_on_hands resource pool."""
        resp = requests.get(f"{api_url}/sessions/{arena_session}/creatures/paladin", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["char_class"] == "paladin"

        pools = data["resource_pools"]
        pool_ids = [p["id"] for p in pools]
        assert "lay_on_hands" in pool_ids

        loh = next(p for p in pools if p["id"] == "lay_on_hands")
        # Level 1 Paladin: 5 * 1 = 5
        assert loh["max_uses"] == 5
        assert loh["current_uses"] == 5
        assert loh["reset_on"] == "long_rest"


# ── Creatures (hot controls) ─────────────────────────────────────────


class TestCreatures:
    def test_list_creatures_arena(self, api_url: str, arena_session: str) -> None:
        resp = requests.get(
            f"{api_url}/sessions/{arena_session}/creatures",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        creatures = resp.json()
        ids = [c["id"] for c in creatures]
        assert "razor" in ids
        assert "shadow" in ids
        assert "iron" in ids
        assert "paladin" in ids

    def test_get_creature(self, api_url: str, arena_session: str) -> None:
        resp = requests.get(
            f"{api_url}/sessions/{arena_session}/creatures/razor",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["id"] == "razor"
        assert data["name"] == "Разор Безумный"
        assert data["hp"] == 35
        assert data["ac"] == 13

    def test_spawn_and_delete_creature(self, api_url: str, arena_session: str) -> None:
        # Spawn
        resp = requests.post(
            f"{api_url}/sessions/{arena_session}/creatures",
            json={
                "id": "test_goblin",
                "name": "Test Goblin",
                "entity_type": "npc",
                "start_location": "arena_floor",
                "hp": 7,
                "ac": 13,
                "speed": 30,
            },
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # Verify exists
        resp = requests.get(
            f"{api_url}/sessions/{arena_session}/creatures/test_goblin",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["name"] == "Test Goblin"

        # Delete
        resp = requests.delete(
            f"{api_url}/sessions/{arena_session}/creatures/test_goblin",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK

        # Verify gone
        resp = requests.get(
            f"{api_url}/sessions/{arena_session}/creatures/test_goblin",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_patch_creature_hp(self, api_url: str, arena_session: str) -> None:
        # Patch razor's HP
        resp = requests.patch(
            f"{api_url}/sessions/{arena_session}/creatures/razor",
            json={"current_hp": 10},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK

        # Verify
        resp = requests.get(
            f"{api_url}/sessions/{arena_session}/creatures/razor",
            timeout=5,
        )
        assert resp.json()["hp"] == 10

        # Restore
        requests.patch(
            f"{api_url}/sessions/{arena_session}/creatures/razor",
            json={"current_hp": 35},
            timeout=5,
        )


# ── Village: creatures with schedules ─────────────────────────────────


class TestVillageCreatures:
    def test_list_village_npcs(self, api_url: str, village_session: str, village_player: dict[str, Any]) -> None:
        resp = requests.get(
            f"{api_url}/sessions/{village_session}/creatures",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        creatures = resp.json()
        ids = [c["id"] for c in creatures]
        assert "olga" in ids
        assert "sergei" in ids
        assert "tanya" in ids

    def test_npc_has_role_and_settlement(
        self, api_url: str, village_session: str, village_player: dict[str, Any]
    ) -> None:
        resp = requests.get(
            f"{api_url}/sessions/{village_session}/creatures/olga",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["role"] == "blacksmith"
        assert data["settlement_id"] == "millbrook"


# ── Saves ─────────────────────────────────────────────────────────────


class TestSaves:
    def test_save_list_load_delete(self, api_url: str, village_session: str, village_player: dict[str, Any]) -> None:
        # Save
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/save?name=test_save",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # List
        resp = requests.get(
            f"{api_url}/sessions/{village_session}/saves",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        saves = resp.json()["saves"]
        assert "test_save" in saves

        # Load
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/saves/test_save/load",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # Delete
        resp = requests.delete(
            f"{api_url}/sessions/{village_session}/saves/test_save",
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK


# ── Time advancement ──────────────────────────────────────────────────


class TestTimeAdvancement:
    def test_advance_time(self, api_url: str, village_session: str, village_player: dict[str, Any]) -> None:
        # Get initial time
        resp = requests.get(f"{api_url}/sessions/{village_session}", timeout=5)
        initial_time = resp.json()["time"]

        # Advance 1 hour
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/time/advance",
            json={"hours": 1},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # Verify time changed
        resp = requests.get(f"{api_url}/sessions/{village_session}", timeout=5)
        new_time = resp.json()["time"]
        assert new_time != initial_time
