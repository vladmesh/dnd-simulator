"""Save/load round-trip integration tests.

Validates that save → load preserves session state through the full HTTP API pipeline:
time, creature HP/locations, NPC ai_type, player gold.
"""

from __future__ import annotations

from http import HTTPStatus

import requests


class TestSaveLoadRoundTrip:
    """Save a village session, mutate state, save again, load first save, verify restored."""

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
        """Switch NPC brain type to llm, save, switch back, load — ai_type restored."""
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        original_ai_type = resp.json()["ai_type"]

        # Switch to llm (BrainFactory falls back to RuleBrain without LLM key, but ai_type is set)
        new_type = "llm" if original_ai_type == "rule_based" else "rule_based"
        resp = requests.put(
            f"{api_url}/sessions/{village_session}/creatures/olga/brain",
            json={"type": new_type},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK

        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.json()["ai_type"] == new_type

        # Save with switched brain
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/save?name=roundtrip_brain",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # Switch back to original
        requests.put(
            f"{api_url}/sessions/{village_session}/creatures/olga/brain",
            json={"type": original_ai_type},
            timeout=5,
        )

        # Load — should restore the switched ai_type
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/saves/roundtrip_brain/load",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.json()["ai_type"] == new_type

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
