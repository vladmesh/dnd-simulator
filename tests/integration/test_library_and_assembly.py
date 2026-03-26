"""Integration tests for library catalog, world assembly, and fork APIs.

Tests run against a live backend in docker compose with test content
that includes a library/ directory with test_geo/test_pol/test_set/test_eco/test_ent templates.

World IDs use UUID suffixes to avoid collisions with leftover data from previous runs
(the test content directory is a docker volume mount that persists).
"""

from __future__ import annotations

import uuid
from http import HTTPStatus

import requests

ALL_LAYER_SELECTIONS = {
    "geography": "test_geo",
    "politics": "test_pol",
    "settlements": "test_set",
    "ecology": "test_eco",
    "entities": "test_ent",
}


def _uid(prefix: str) -> str:
    """Generate a unique world ID with prefix to avoid collisions across test runs."""
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class TestLibraryCatalog:
    def test_list_geography_templates(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/library/geography", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        templates = resp.json()
        slugs = [t["slug"] for t in templates]
        assert "test_geo" in slugs

    def test_list_politics_templates(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/library/politics", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        templates = resp.json()
        slugs = [t["slug"] for t in templates]
        assert "test_pol" in slugs

    def test_template_has_metadata_fields(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/library/geography", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        templates = resp.json()
        geo = next(t for t in templates if t["slug"] == "test_geo")
        assert geo["name"] == "Test Geography"
        assert geo["layer_type"] == "geography"
        assert geo["version"] == "1.0"

    def test_compatibility_filter_returns_matching(self, api_url: str) -> None:
        resp = requests.get(
            f"{api_url}/library/politics",
            params={"geography": "test_geo"},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        templates = resp.json()
        slugs = [t["slug"] for t in templates]
        assert "test_pol" in slugs

    def test_compatibility_filter_excludes_incompatible(self, api_url: str) -> None:
        resp = requests.get(
            f"{api_url}/library/politics",
            params={"geography": "nonexistent_geo"},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK
        templates = resp.json()
        slugs = [t["slug"] for t in templates]
        assert "test_pol" not in slugs

    def test_invalid_layer_type_422(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/library/invalid_type", timeout=5)
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


class TestWorldAssembly:
    def test_assemble_world(self, api_url: str) -> None:
        world_id = _uid("asm")
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json={
                "id": world_id,
                "name": "Assembled Test World",
                "description": "A world assembled from library templates",
                "layer_selections": ALL_LAYER_SELECTIONS,
            },
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.CREATED
        data = resp.json()
        assert data["id"] == world_id
        assert data["name"] == "Assembled Test World"

        # Verify it appears in world listing
        list_resp = requests.get(f"{api_url}/worlds", timeout=5)
        world_ids = [w["id"] for w in list_resp.json()]
        assert world_id in world_ids

    def test_assemble_duplicate_409(self, api_url: str) -> None:
        world_id = _uid("dup")
        # Create first
        requests.post(
            f"{api_url}/worlds/assemble",
            json={"id": world_id, "name": "First", "layer_selections": ALL_LAYER_SELECTIONS},
            timeout=10,
        )
        # Creating again should 409
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json={"id": world_id, "name": "Duplicate", "layer_selections": ALL_LAYER_SELECTIONS},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.CONFLICT

    def test_assemble_missing_layer_400(self, api_url: str) -> None:
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json={
                "id": _uid("bad"),
                "name": "Bad",
                "layer_selections": {"geography": "test_geo"},  # missing 4 layers
            },
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_assemble_nonexistent_template_400(self, api_url: str) -> None:
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json={
                "id": _uid("bad2"),
                "name": "Bad",
                "layer_selections": {
                    "geography": "nonexistent",
                    "politics": "test_pol",
                    "settlements": "test_set",
                    "ecology": "test_eco",
                    "entities": "test_ent",
                },
            },
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_assembled_world_starts_session(self, api_url: str) -> None:
        world_id = _uid("sess")
        requests.post(
            f"{api_url}/worlds/assemble",
            json={"id": world_id, "name": "Session Test", "layer_selections": ALL_LAYER_SELECTIONS},
            timeout=10,
        )
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": world_id, "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]

        # Cleanup
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)


class TestWizardFlow:
    """Tests that mirror the exact API call sequence the WorldBuilder wizard makes."""

    def test_full_wizard_sequence(self, api_url: str, player_api_url: str) -> None:
        """Step through all 5 layers, assemble world, create session, create player."""
        # Step 1: Geography (unfiltered)
        resp = requests.get(f"{api_url}/library/geography", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        geo_templates = resp.json()
        assert len(geo_templates) > 0
        selected_geo = geo_templates[0]["slug"]

        # Step 2: Politics (filtered by geography)
        resp = requests.get(f"{api_url}/library/politics", params={"geography": selected_geo}, timeout=5)
        assert resp.status_code == HTTPStatus.OK
        pol_templates = resp.json()
        assert len(pol_templates) > 0
        selected_pol = pol_templates[0]["slug"]

        # Step 3: Settlements (filtered by geography)
        resp = requests.get(f"{api_url}/library/settlements", params={"geography": selected_geo}, timeout=5)
        assert resp.status_code == HTTPStatus.OK
        set_templates = resp.json()
        assert len(set_templates) > 0
        selected_set = set_templates[0]["slug"]

        # Step 4: Ecology (filtered by geography)
        resp = requests.get(f"{api_url}/library/ecology", params={"geography": selected_geo}, timeout=5)
        assert resp.status_code == HTTPStatus.OK
        eco_templates = resp.json()
        assert len(eco_templates) > 0
        selected_eco = eco_templates[0]["slug"]

        # Step 5: Entities (filtered by geography)
        resp = requests.get(f"{api_url}/library/entities", params={"geography": selected_geo}, timeout=5)
        assert resp.status_code == HTTPStatus.OK
        ent_templates = resp.json()
        assert len(ent_templates) > 0
        selected_ent = ent_templates[0]["slug"]

        # Step 6: Assemble
        world_id = _uid("wizard")
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json={
                "id": world_id,
                "name": "Wizard Flow World",
                "description": "Built by the wizard flow test",
                "layer_selections": {
                    "geography": selected_geo,
                    "politics": selected_pol,
                    "settlements": selected_set,
                    "ecology": selected_eco,
                    "entities": selected_ent,
                },
            },
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.CREATED

        # Step 7: Create session from assembled world
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": world_id, "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]

        # Step 8: Create player character in the new session
        resp = requests.post(
            f"{player_api_url}/sessions/{session_id}/character",
            json={
                "name": "Wizard Hero",
                "race": "human",
                "char_class": "fighter",
                "level": 1,
                "alignment": "true_neutral",
                "hp": 20,
                "ac": 12,
                "gold": 10,
                "ability_scores": {"str": 14, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
            },
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        player_data = resp.json()
        assert player_data["name"] == "Wizard Hero"
        assert player_data["player_id"]

        # Verify session shows in listing with correct world
        resp = requests.get(f"{api_url}/sessions", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        sessions = resp.json()
        wizard_session = next(s for s in sessions if s["session_id"] == session_id)
        assert wizard_session["world_name"] == world_id

        # Cleanup
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)

    def test_compatibility_cascade_filters_all_upper_layers(self, api_url: str) -> None:
        """All upper layers (politics, settlements, ecology, entities) filter by selected geography."""
        for layer_type in ("politics", "settlements", "ecology", "entities"):
            # Compatible geography returns templates
            resp = requests.get(
                f"{api_url}/library/{layer_type}",
                params={"geography": "test_geo"},
                timeout=5,
            )
            assert resp.status_code == HTTPStatus.OK
            assert len(resp.json()) > 0, f"{layer_type} should have compatible templates for test_geo"

            # Nonexistent geography returns empty
            resp = requests.get(
                f"{api_url}/library/{layer_type}",
                params={"geography": "nonexistent_geo"},
                timeout=5,
            )
            assert resp.status_code == HTTPStatus.OK
            assert len(resp.json()) == 0, f"{layer_type} should have no templates for nonexistent_geo"


class TestForkLayer:
    def test_fork_entities_layer(self, api_url: str) -> None:
        world_id = _uid("fork")
        requests.post(
            f"{api_url}/worlds/assemble",
            json={"id": world_id, "name": "Fork Test", "layer_selections": ALL_LAYER_SELECTIONS},
            timeout=10,
        )

        resp = requests.post(
            f"{api_url}/worlds/{world_id}/fork/entities",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

        # Forking again should 409 (already custom)
        resp = requests.post(
            f"{api_url}/worlds/{world_id}/fork/entities",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.CONFLICT

    def test_fork_nonexistent_world_404(self, api_url: str) -> None:
        resp = requests.post(
            f"{api_url}/worlds/nonexistent_world/fork/geography",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_forked_world_starts_session(self, api_url: str) -> None:
        world_id = _uid("forkrun")
        requests.post(
            f"{api_url}/worlds/assemble",
            json={"id": world_id, "name": "Fork Run Test", "layer_selections": ALL_LAYER_SELECTIONS},
            timeout=10,
        )
        requests.post(f"{api_url}/worlds/{world_id}/fork/entities", timeout=10)

        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": world_id, "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]

        # Cleanup
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)
