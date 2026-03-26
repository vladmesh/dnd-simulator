"""Save/load round-trip integration tests.

Validates that save → load preserves session state through the full HTTP API pipeline:
time, creature HP/locations, NPC ai_type, player gold.
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
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

    @pytest.mark.xfail(reason="PUT brain type=llm requires OPENROUTER_API_KEY (strict=True in BrainFactory)")
    def test_save_load_preserves_brain_switch(
        self,
        api_url: str,
        village_session: str,
        village_player: dict[str, object],
    ) -> None:
        """Switch NPC brain type, save, switch back, load — original switch preserved."""
        # Check initial ai_type
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        original_ai_type = resp.json()["ai_type"]

        # Switch to the opposite type via PUT brain endpoint
        new_type = "llm" if original_ai_type == "rule_based" else "rule_based"
        resp = requests.put(
            f"{api_url}/sessions/{village_session}/creatures/olga/brain",
            json={"type": new_type},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK

        # Verify switch took effect
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
        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.json()["ai_type"] == original_ai_type

        # Load — should restore the switched brain
        resp = requests.post(
            f"{api_url}/sessions/{village_session}/saves/roundtrip_brain/load",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        resp = requests.get(f"{api_url}/sessions/{village_session}/creatures/olga", timeout=5)
        assert resp.json()["ai_type"] == new_type

        # Cleanup: restore original and delete save
        requests.put(
            f"{api_url}/sessions/{village_session}/creatures/olga/brain",
            json={"type": original_ai_type},
            timeout=5,
        )
        requests.delete(
            f"{api_url}/sessions/{village_session}/saves/roundtrip_brain",
            timeout=5,
        )
