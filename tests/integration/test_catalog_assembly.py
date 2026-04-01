"""Integration tests for catalog assembly — full pipeline through live backend.

Tests that catalog references (monster 'base' and item 'ref') resolve correctly
when starting a game session via the API. Uses catalog_world test content which
references catalogs/monsters/goblin and catalogs/items/{dagger,health_potion}.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import requests


def _create_catalog_session(api_url: str) -> str:
    """Create a catalog_world session. Returns session_id."""
    resp = requests.post(
        f"{api_url}/sessions",
        json={"world_name": "catalog_world", "lang": "en"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["session_id"]


def _get_entities(api_url: str, session_id: str) -> list[dict[str, Any]]:
    """Get all entities from a session."""
    resp = requests.get(f"{api_url}/sessions/{session_id}", timeout=5)
    resp.raise_for_status()
    return resp.json()["entities"]


class TestCatalogWorldLoads:
    """catalog_world uses catalog refs — verify it starts and resolves them."""

    def test_session_starts_successfully(self, api_url: str) -> None:
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": "catalog_world", "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)

    def test_shopkeeper_has_catalog_items(self, api_url: str) -> None:
        """NPC items resolved via 'ref' from item catalog."""
        session_id = _create_catalog_session(api_url)
        entities = _get_entities(api_url, session_id)

        shopkeeper = next(e for e in entities if e["id"] == "shopkeeper")
        inventory = shopkeeper["inventory"]
        assert len(inventory) == 2

        item_names = {item["name"] for item in inventory}
        assert "Dagger" in item_names
        assert "Health Potion" in item_names

        # Verify item types resolved correctly from catalog
        by_name = {item["name"]: item for item in inventory}
        assert by_name["Dagger"]["item_type"] == "weapon"
        assert by_name["Health Potion"]["item_type"] == "potion"

        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)

    def test_time_advance_with_catalog_squads(self, api_url: str, player_api_url: str) -> None:
        """Squads referencing catalog monsters tick without errors."""
        session_id = _create_catalog_session(api_url)

        # Create a player so time advance works
        requests.post(
            f"{player_api_url}/sessions/{session_id}/character",
            json={
                "name": "Tester",
                "race": "human",
                "char_class": "fighter",
                "alignment": "true_neutral",
                "start_location": "town_square",
                "ability_scores": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
            },
            timeout=10,
        )

        # Advance time — this ticks ecology layer with catalog-resolved squad member CRs
        resp = requests.post(
            f"{api_url}/sessions/{session_id}/time/advance",
            json={"hours": 2},
            timeout=30,
        )
        assert resp.status_code == HTTPStatus.OK

        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)


class TestInlineWorldStillWorks:
    """arena uses fully inline items (no catalog refs) — must still work."""

    def test_arena_loads_without_catalogs(self, api_url: str) -> None:
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": "arena", "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]

        entities = _get_entities(api_url, session_id)
        # Arena has 4 NPCs with inline items
        assert len(entities) >= 4

        # Razor has inline items (no catalog ref)
        razor = next(e for e in entities if e["id"] == "razor")
        assert len(razor["inventory"]) == 2  # potion + sword

        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)


class TestCatalogOverrideResolution:
    """Verify that monster catalog overrides produce correct stats via API."""

    def test_save_load_preserves_catalog_resolved_data(self, api_url: str, player_api_url: str) -> None:
        """Save and load a catalog_world session — catalog-resolved data persists."""
        session_id = _create_catalog_session(api_url)

        # Create player
        requests.post(
            f"{player_api_url}/sessions/{session_id}/character",
            json={
                "name": "Saver",
                "race": "human",
                "char_class": "fighter",
                "alignment": "true_neutral",
                "start_location": "town_square",
                "ability_scores": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
            },
            timeout=10,
        )

        # Save
        resp = requests.post(f"{api_url}/sessions/{session_id}/save?name=catalog_test", timeout=10)
        assert resp.status_code == HTTPStatus.OK

        # Load
        resp = requests.post(f"{api_url}/sessions/{session_id}/saves/catalog_test/load", timeout=10)
        assert resp.status_code == HTTPStatus.OK

        # Verify shopkeeper items survived round-trip
        entities = _get_entities(api_url, session_id)
        shopkeeper = next(e for e in entities if e["id"] == "shopkeeper")
        item_names = {item["name"] for item in shopkeeper["inventory"]}
        assert "Dagger" in item_names
        assert "Health Potion" in item_names

        # Cleanup
        requests.delete(f"{api_url}/sessions/{session_id}/saves/catalog_test", timeout=5)
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)
