"""Integration tests for library catalog, world assembly, and fork APIs.

Tests run against a live backend in docker compose with test content
that includes a library/ directory with test_geo/test_pol/test_set/test_eco/test_ent templates.
"""

from __future__ import annotations

from http import HTTPStatus

import requests

ALL_LAYER_SELECTIONS = {
    "geography": "test_geo",
    "politics": "test_pol",
    "settlements": "test_set",
    "ecology": "test_eco",
    "entities": "test_ent",
}


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
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json={
                "id": "assembled_test",
                "name": "Assembled Test World",
                "description": "A world assembled from library templates",
                "layer_selections": ALL_LAYER_SELECTIONS,
            },
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.CREATED
        data = resp.json()
        assert data["id"] == "assembled_test"
        assert data["name"] == "Assembled Test World"

        # Verify it appears in world listing
        list_resp = requests.get(f"{api_url}/worlds", timeout=5)
        world_ids = [w["id"] for w in list_resp.json()]
        assert "assembled_test" in world_ids

    def test_assemble_duplicate_409(self, api_url: str) -> None:
        # assembled_test was created in the previous test; creating again should 409
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json={
                "id": "assembled_test",
                "name": "Duplicate",
                "layer_selections": ALL_LAYER_SELECTIONS,
            },
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.CONFLICT

    def test_assemble_missing_layer_400(self, api_url: str) -> None:
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json={
                "id": "bad_world",
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
                "id": "bad_world_2",
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
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": "assembled_test", "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]

        # Cleanup
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)


class TestForkLayer:
    def test_fork_entities_layer(self, api_url: str) -> None:
        # Create a fresh world to fork from
        requests.post(
            f"{api_url}/worlds/assemble",
            json={
                "id": "fork_test_world",
                "name": "Fork Test",
                "layer_selections": ALL_LAYER_SELECTIONS,
            },
            timeout=10,
        )

        resp = requests.post(
            f"{api_url}/worlds/fork_test_world/fork/entities",
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK

    def test_fork_already_custom_409(self, api_url: str) -> None:
        # fork_test_world entities is already custom from the previous test
        resp = requests.post(
            f"{api_url}/worlds/fork_test_world/fork/entities",
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
        # fork_test_world has entities forked to custom, rest library
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": "fork_test_world", "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]

        # Cleanup
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)
