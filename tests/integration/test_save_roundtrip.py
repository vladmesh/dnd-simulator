"""Save/load round-trip integration tests.

Validates that save → load preserves session state through the full HTTP API pipeline:
time, creature HP/locations, NPC ai_type, player gold.
"""

from __future__ import annotations

import time
from http import HTTPStatus

import requests
from conftest import ws_connect, ws_recv, ws_send_action


class TestSaveLoadRoundTrip:
    """Save a village session, mutate state, save again, load first save, verify restored."""

    def test_load_combat_save_resumes_saved_player_turn_after_websocket_reconnect(
        self, api_url: str, player_api_url: str, ws_base_url: str
    ) -> None:
        """A loaded player turn resumes before any earlier initiative actor can run."""
        from test_combat_turns import _create_session, _ensure_combat, _get_turn

        session_id, player_id = _create_session(api_url, player_api_url, "fighter")
        save_name = "resume_player_turn"
        try:
            sock = ws_connect(ws_base_url, session_id, player_id)
            try:
                turn = _ensure_combat(sock, _get_turn(sock), "target_dummy")
                saved_round = turn["awareness"]["round_number"]
                assert turn["player"]["player_id"] == player_id

                response = requests.post(f"{api_url}/sessions/{session_id}/save?name={save_name}", timeout=10)
                assert response.status_code == HTTPStatus.OK

                # Let the live game diverge before replacing it with the save.
                ws_send_action(sock, "end_turn")
                _get_turn(sock)
            finally:
                sock.close()

            response = requests.post(f"{api_url}/sessions/{session_id}/saves/{save_name}/load", timeout=10)
            assert response.status_code == HTTPStatus.OK

            # A restored world remains stopped until this listener is registered.
            time.sleep(0.5)
            reconnected = ws_connect(ws_base_url, session_id, player_id)
            try:
                for _ in range(10):
                    message = ws_recv(reconnected)
                    assert message["type"] not in {"action_result", "round_result"}
                    if message["type"] == "turn":
                        assert message["player"]["player_id"] == player_id
                        assert message["awareness"]["round_number"] == saved_round
                        break
                else:
                    raise AssertionError("Reconnect did not resume the saved player turn")
            finally:
                reconnected.close()
        finally:
            requests.delete(f"{api_url}/sessions/{session_id}/saves/{save_name}", timeout=5)
            requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)

    def test_save_load_preserves_state(
        self,
        api_url: str,
        player_api_url: str,
        village_session: str,
        village_player: dict[str, object],
    ) -> None:
        # 1. Get initial state
        resp = requests.get(f"{api_url}/sessions/{village_session}", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        initial = resp.json()
        initial_time = initial["time"]

        # Get a specific NPC's initial HP
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        olga_initial = resp.json()
        olga_hp_before = olga_initial["hp"]
        olga_ai_type = olga_initial["ai_type"]

        # Get player status before
        resp = requests.get(f"{player_api_url}/sessions/{village_session}/status", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        player_before = resp.json()
        player_hp_before = player_before["hp"]
        player_gold_before = player_before["gold"]

        # 2. Save current state
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/save?name=roundtrip_test",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # 3. Mutate state — change NPC HP, advance time
        requests.patch(
            f"{api_url}/sessions/{village_session}/creatures/olga",
            json={"current_hp": 1},
            timeout=5,
        )
        requests.post(
            f"{api_url}/sessions/{village_session}/time/advance",
            json={"hours": 3},
            timeout=10,
        )

        # Verify mutation took effect
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.json()["hp"] == 1

        resp = requests.get(f"{api_url}/sessions/{village_session}", timeout=5)
        mutated_time = resp.json()["time"]
        assert mutated_time != initial_time

        # 4. Load the save — should restore pre-mutation state
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/saves/roundtrip_test/load",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # 5. Verify state is restored
        # Time restored
        resp = requests.get(f"{api_url}/sessions/{village_session}", timeout=5)
        restored = resp.json()
        assert restored["time"] == initial_time

        # NPC HP restored
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        olga_restored = resp.json()
        assert olga_restored["hp"] == olga_hp_before
        assert olga_restored["ai_type"] == olga_ai_type

        # Player state restored
        resp = requests.get(f"{player_api_url}/sessions/{village_session}/status", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        player_restored = resp.json()
        assert player_restored["hp"] == player_hp_before
        assert player_restored["gold"] == player_gold_before

        # All creatures still present
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        creature_ids = [c["id"] for c in resp.json()]
        assert "olga" in creature_ids
        assert "sergei" in creature_ids
        assert "tanya" in creature_ids

        # 6. Cleanup
        requests.delete(
            f"{api_url}/sessions/{village_session}/saves/roundtrip_test",
            timeout=5,
        )

    def test_save_load_preserves_brain_switch(
        self,
        api_url: str,
        village_session: str,
        village_player: dict[str, object],
    ) -> None:
        """Switch NPC brain, save, switch again, load — ai_type restored.

        Without OPENROUTER_API_KEY the endpoint returns warning and keeps
        rule_based, so we test the roundtrip with rule_based explicitly.
        """
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        original_ai_type = resp.json()["ai_type"]

        # Without LLM key, switching to llm returns a warning and stays rule_based
        resp = requests.put(
            f"{api_url}/sessions/{village_session}/creatures/olga/brain",
            json={"type": "llm"},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        body = resp.json()
        assert body["brain_type"] == "rule_based"
        assert body["warning"] == "no_llm_key"

        # Ensure the creature is rule_based (set explicitly for the save roundtrip)
        resp = requests.put(
            f"{api_url}/sessions/{village_session}/creatures/olga/brain",
            json={"type": "rule_based"},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["brain_type"] == "rule_based"
        assert resp.json()["warning"] is None

        # Save with rule_based brain
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/save?name=roundtrip_brain",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # Load — should restore the saved ai_type
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/saves/roundtrip_brain/load",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.json()["ai_type"] == "rule_based"

        # Cleanup
        requests.put(
            f"{api_url}/sessions/{village_session}/creatures/olga/brain",
            json={"type": original_ai_type},
            timeout=5,
        )
        requests.delete(
            f"{api_url}/sessions/{village_session}/saves/roundtrip_brain",
            timeout=5,
        )

    def test_spawned_npc_survives_save_load(
        self,
        api_url: str,
        village_session: str,
        village_player: dict[str, object],
    ) -> None:
        """NPC spawned at runtime via POST /creatures survives save → load."""
        # Spawn a goblin NPC
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/creatures",
            json={
                "id": "test_goblin",
                "name": "Gruk",
                "entity_type": "npc",
                "start_location": "village_square",
                "hp": 15,
                "ac": 13,
                "speed": 30,
                "role": "guard",
                "personality": "Sneaky.",
                "settlement_id": "haven",
            },
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK

        # Verify it exists
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/test_goblin", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["name"] == "Gruk"

        # Save
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/save?name=roundtrip_spawn",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # Delete the goblin to prove load brings it back
        requests.delete(f"{api_url}/sessions/{village_session}/creatures/test_goblin", timeout=5)
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/test_goblin", timeout=5)
        assert resp.status_code == HTTPStatus.NOT_FOUND

        # Load — goblin should be back
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/saves/roundtrip_spawn/load",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/test_goblin", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        goblin = resp.json()
        assert goblin["name"] == "Gruk"
        assert goblin["hp"] == 15

        # Cleanup
        requests.delete(f"{api_url}/sessions/{village_session}/creatures/test_goblin", timeout=5)
        requests.delete(f"{api_url}/sessions/{village_session}/saves/roundtrip_spawn", timeout=5)

    def test_spawned_creature_with_mutations_survives_save_load(
        self,
        api_url: str,
        village_session: str,
        village_player: dict[str, object],
    ) -> None:
        """Spawn creature, patch HP, save, load — patched HP is restored (not max_hp)."""
        # Spawn
        requests.post(
            f"{api_url}/sessions/{village_session}/creatures",
            json={
                "id": "test_wolf",
                "name": "Dire Wolf",
                "entity_type": "monster",
                "start_location": "village_square",
                "hp": 37,
                "ac": 14,
                "speed": 50,
            },
            timeout=5,
        )

        # Patch HP down
        requests.patch(
            f"{api_url}/sessions/{village_session}/creatures/test_wolf",
            json={"current_hp": 12},
            timeout=5,
        )
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/test_wolf", timeout=5)
        assert resp.json()["hp"] == 12

        # Save
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/save?name=roundtrip_mutated",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # Delete + load
        requests.delete(f"{api_url}/sessions/{village_session}/creatures/test_wolf", timeout=5)
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/saves/roundtrip_mutated/load",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # HP should be 12 (mutated), not 37 (max)
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/test_wolf", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["hp"] == 12

        # Cleanup
        requests.delete(f"{api_url}/sessions/{village_session}/creatures/test_wolf", timeout=5)
        requests.delete(f"{api_url}/sessions/{village_session}/saves/roundtrip_mutated", timeout=5)
