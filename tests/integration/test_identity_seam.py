"""Integration tests for the identity request-seam (Sprint 020 phase 1).

Exercises ``get_identity`` over real HTTP: ``X-Role`` validation (invalid → 400)
and ``X-User-Id`` → world ``creator`` attribution. Session ``created_by`` is
stamped but not surfaced over the API, so it stays unit-tested only.
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
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def _assemble_body(world_id: str) -> dict[str, object]:
    return {"id": world_id, "name": "Identity Test", "layer_selections": ALL_LAYER_SELECTIONS}


class TestIdentitySeam:
    def test_invalid_role_header_400(self, api_url: str) -> None:
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json=_assemble_body(_uid("id_badrole")),
            headers={"X-User-Id": "alice", "X-Role": "wizard"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_valid_role_and_user_stamps_creator(self, api_url: str) -> None:
        world_id = _uid("id_creator")
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json=_assemble_body(world_id),
            headers={"X-User-Id": "alice", "X-Role": "worldbuilder"},
            timeout=10,
        )
        try:
            assert resp.status_code == HTTPStatus.CREATED
            assert resp.json()["creator"] == "alice"
        finally:
            requests.delete(f"{api_url}/worlds/{world_id}", timeout=5)

    def test_headerless_creator_defaults_to_local(self, api_url: str) -> None:
        world_id = _uid("id_default")
        resp = requests.post(
            f"{api_url}/worlds/assemble",
            json=_assemble_body(world_id),
            timeout=10,
        )
        try:
            assert resp.status_code == HTTPStatus.CREATED
            assert resp.json()["creator"] == "local"
        finally:
            requests.delete(f"{api_url}/worlds/{world_id}", timeout=5)
