"""Integration tests for library catalog, world assembly, and fork APIs.

Tests run against a live backend in docker compose with test content
that includes a library/ directory with test_geo/test_pol/test_set/test_eco/test_ent templates.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import pytest
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


# ---------------------------------------------------------------------------
# Fixture: world factory with automatic cleanup
# ---------------------------------------------------------------------------


class WorldFactory:
    """Creates worlds via API and tracks them for cleanup."""

    def __init__(self, api_url: str) -> None:
        self._api_url = api_url
        self._created: list[str] = []

    def assemble(
        self,
        prefix: str,
        name: str = "Test World",
        *,
        description: str = "",
        layer_selections: dict[str, str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str:
        """Assemble a world and register for cleanup. Returns world_id."""
        world_id = _uid(prefix)
        body: dict[str, Any] = {
            "id": world_id,
            "name": name,
            "layer_selections": layer_selections or ALL_LAYER_SELECTIONS,
        }
        if description:
            body["description"] = description
        if extra:
            body.update(extra)
        resp = requests.post(f"{self._api_url}/worlds/assemble", json=body, timeout=10)
        resp.raise_for_status()
        self._created.append(world_id)
        return world_id

    def cleanup(self) -> None:
        for world_id in self._created:
            requests.delete(f"{self._api_url}/worlds/{world_id}", timeout=5)


@pytest.fixture()
def worlds(api_url: str) -> Iterator[WorldFactory]:
    """Provide a WorldFactory that cleans up all created worlds on teardown."""
    factory = WorldFactory(api_url)
    yield factory
    factory.cleanup()


# ---------------------------------------------------------------------------
# Library catalog (read-only, no worlds created)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# World assembly
# ---------------------------------------------------------------------------


class TestWorldAssembly:
    def test_assemble_world(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble(
            "asm", "Assembled Test World", description="A world assembled from library templates"
        )

        # Verify it appears in world listing
        list_resp = requests.get(f"{api_url}/worlds", timeout=5)
        world_ids = [w["id"] for w in list_resp.json()]
        assert world_id in world_ids

    def test_assemble_duplicate_409(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("dup", "First")
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

    def test_assembled_world_starts_session(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("sess", "Session Test")
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": world_id, "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]

        # Cleanup session (world cleaned up by fixture)
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)


# ---------------------------------------------------------------------------
# Wizard flow
# ---------------------------------------------------------------------------


class TestWizardFlow:
    """Tests that mirror the exact API call sequence the WorldBuilder wizard makes."""

    def test_full_wizard_sequence(self, api_url: str, player_api_url: str, worlds: WorldFactory) -> None:
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
        world_id = worlds.assemble(
            "wizard",
            "Wizard Flow World",
            description="Built by the wizard flow test",
            layer_selections={
                "geography": selected_geo,
                "politics": selected_pol,
                "settlements": selected_set,
                "ecology": selected_eco,
                "entities": selected_ent,
            },
        )

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
                "alignment": "true_neutral",
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

        # Cleanup session (world cleaned up by fixture)
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


# ---------------------------------------------------------------------------
# Fork layer
# ---------------------------------------------------------------------------


class TestForkLayer:
    def test_fork_entities_layer(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("fork", "Fork Test")

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

    def test_forked_world_starts_session(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("forkrun", "Fork Run Test")
        requests.post(f"{api_url}/worlds/{world_id}/fork/entities", timeout=10)

        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": world_id, "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]

        # Cleanup session (world cleaned up by fixture)
        requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)


# ---------------------------------------------------------------------------
# Layer files
# ---------------------------------------------------------------------------


def _first_filename(files_dict: dict[str, str]) -> str:
    """Get the first filename from a files dict response."""
    return next(iter(files_dict))


class TestLayerFiles:
    def test_read_library_layer_files(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("lf_read", "LayerFiles Read")

        resp = requests.get(f"{api_url}/worlds/{world_id}/layers/geography/files", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        files = resp.json()["files"]
        assert len(files) > 0
        # files is dict[str, str] — filename → content
        filename = _first_filename(files)
        assert filename.endswith(".yaml") or filename.endswith(".yml")
        assert len(files[filename]) > 0

    def test_read_single_file(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("lf_single", "LayerFiles Single")

        list_resp = requests.get(f"{api_url}/worlds/{world_id}/layers/geography/files", timeout=5)
        filename = _first_filename(list_resp.json()["files"])

        resp = requests.get(f"{api_url}/worlds/{world_id}/layers/geography/files/{filename}", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["filename"] == filename
        assert len(data["content"]) > 0

    def test_read_nonexistent_file_404(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("lf_404", "LayerFiles 404")

        resp = requests.get(f"{api_url}/worlds/{world_id}/layers/geography/files/nonexistent.yaml", timeout=5)
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_write_custom_layer_file(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("lf_write", "LayerFiles Write")

        requests.post(f"{api_url}/worlds/{world_id}/fork/entities", timeout=10)

        list_resp = requests.get(f"{api_url}/worlds/{world_id}/layers/entities/files", timeout=5)
        filename = _first_filename(list_resp.json()["files"])

        orig = requests.get(f"{api_url}/worlds/{world_id}/layers/entities/files/{filename}", timeout=5)
        original_content = orig.json()["content"]

        modified = original_content + "\n# integration test comment\n"
        resp = requests.put(
            f"{api_url}/worlds/{world_id}/layers/entities/files/{filename}",
            json={"content": modified},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.OK

        verify = requests.get(f"{api_url}/worlds/{world_id}/layers/entities/files/{filename}", timeout=5)
        assert verify.json()["content"] == modified

    def test_write_library_layer_rejected(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("lf_lib_wr", "LayerFiles LibWrite")

        list_resp = requests.get(f"{api_url}/worlds/{world_id}/layers/geography/files", timeout=5)
        filename = _first_filename(list_resp.json()["files"])

        resp = requests.put(
            f"{api_url}/worlds/{world_id}/layers/geography/files/{filename}",
            json={"content": "test: true\n"},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_write_invalid_yaml_422(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("lf_badyml", "LayerFiles BadYAML")

        requests.post(f"{api_url}/worlds/{world_id}/fork/entities", timeout=10)

        list_resp = requests.get(f"{api_url}/worlds/{world_id}/layers/entities/files", timeout=5)
        filename = _first_filename(list_resp.json()["files"])

        resp = requests.put(
            f"{api_url}/worlds/{world_id}/layers/entities/files/{filename}",
            json={"content": "invalid: yaml: [unterminated"},
            timeout=5,
        )
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY

    def test_path_traversal_rejected(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("lf_trav", "LayerFiles Traversal")

        resp = requests.get(
            f"{api_url}/worlds/{world_id}/layers/geography/files/../../../etc/passwd",
            timeout=5,
        )
        assert resp.status_code in (HTTPStatus.BAD_REQUEST, HTTPStatus.NOT_FOUND)


# ---------------------------------------------------------------------------
# World editable flag, fork-world, delete-world
# ---------------------------------------------------------------------------


class TestWorldEditableFlag:
    def test_assembled_world_is_editable(self, api_url: str, worlds: WorldFactory) -> None:
        world_id = worlds.assemble("ed_yes", "Editable World")

        resp = requests.get(f"{api_url}/worlds", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        world = next(w for w in resp.json() if w["id"] == world_id)
        assert world["editable"] is True

    def test_base_world_is_not_editable(self, api_url: str) -> None:
        resp = requests.get(f"{api_url}/worlds", timeout=5)
        assert resp.status_code == HTTPStatus.OK
        sword_vale = next((w for w in resp.json() if w["id"] == "sword_vale"), None)
        if sword_vale is not None:
            assert sword_vale["editable"] is False


class TestForkWorld:
    def test_fork_world(self, api_url: str, worlds: WorldFactory) -> None:
        source_id = worlds.assemble("fk_src", "Fork Source")
        fork_id = _uid("fk_dst")
        worlds._created.append(fork_id)  # register for cleanup

        resp = requests.post(
            f"{api_url}/worlds/{source_id}/fork",
            json={"new_id": fork_id},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.CREATED
        data = resp.json()
        assert data["id"] == fork_id
        assert data["editable"] is True

        # Forked world appears in listing
        list_resp = requests.get(f"{api_url}/worlds", timeout=5)
        world_ids = [w["id"] for w in list_resp.json()]
        assert fork_id in world_ids

    def test_fork_nonexistent_world_404(self, api_url: str) -> None:
        resp = requests.post(
            f"{api_url}/worlds/nonexistent_world_xyz/fork",
            json={"new_id": "whatever"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.NOT_FOUND

    def test_fork_duplicate_id_409(self, api_url: str, worlds: WorldFactory) -> None:
        source_id = worlds.assemble("fk_dup", "Fork Dup Source")
        fork_id = _uid("fk_dup2")
        worlds._created.append(fork_id)

        requests.post(
            f"{api_url}/worlds/{source_id}/fork",
            json={"new_id": fork_id},
            timeout=10,
        )
        # Second fork with same ID should 409
        resp = requests.post(
            f"{api_url}/worlds/{source_id}/fork",
            json={"new_id": fork_id},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.CONFLICT


class TestDeleteWorld:
    def test_delete_assembled_world(self, api_url: str) -> None:
        # Create without factory so we control deletion manually
        world_id = _uid("del_ok")
        requests.post(
            f"{api_url}/worlds/assemble",
            json={"id": world_id, "name": "Deletable", "layer_selections": ALL_LAYER_SELECTIONS},
            timeout=10,
        )

        resp = requests.delete(f"{api_url}/worlds/{world_id}", timeout=5)
        assert resp.status_code == HTTPStatus.OK

        # Verify gone
        list_resp = requests.get(f"{api_url}/worlds", timeout=5)
        world_ids = [w["id"] for w in list_resp.json()]
        assert world_id not in world_ids

    def test_delete_base_world_403(self, api_url: str) -> None:
        resp = requests.delete(f"{api_url}/worlds/sword_vale", timeout=5)
        assert resp.status_code == HTTPStatus.FORBIDDEN

    def test_delete_nonexistent_world_404(self, api_url: str) -> None:
        resp = requests.delete(f"{api_url}/worlds/nonexistent_xyz_999", timeout=5)
        assert resp.status_code == HTTPStatus.NOT_FOUND
