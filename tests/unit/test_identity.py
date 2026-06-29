"""Tests for the identity/role resolution seam (Sprint 020 phase 1 task 2).

`resolve_identity` is a pure validator (service layer); `get_identity` is the
FastAPI dependency that reads X-User-Id / X-Role headers and maps a bad role to
HTTP 400. Identity drives `creator` on world-create/fork and `meta.created_by`
on session-create — attribution only, no enforcement this sprint.
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.content_loader.manifest import LayerType
from dnd_simulator.service import GameService
from dnd_simulator.service.identity import Identity, Role, resolve_identity
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


# ---------------------------------------------------------------------------
# Pure resolver
# ---------------------------------------------------------------------------


class TestResolveIdentity:
    def test_parses_user_and_role(self) -> None:
        assert resolve_identity("alice", "dm") == Identity("alice", Role.DM)
        assert resolve_identity("alice", "worldbuilder").role == Role.WORLDBUILDER

    def test_invalid_role_raises(self) -> None:
        with pytest.raises(ValueError):
            resolve_identity("alice", "wizard")

    def test_defaults_when_missing(self) -> None:
        ident = resolve_identity(None, None)
        assert ident.user_id == "local"
        assert ident.role == Role.ADMIN  # documented default

    def test_blank_strings_default(self) -> None:
        ident = resolve_identity("", "")
        assert ident.user_id == "local"
        assert ident.role == Role.ADMIN

    def test_explicit_default_role_honored(self) -> None:
        ident = resolve_identity(None, None, default_role=Role.PLAYER)
        assert ident.role == Role.PLAYER


# ---------------------------------------------------------------------------
# HTTP seam — world routes
# ---------------------------------------------------------------------------


def _with_library(tmp_path: Path) -> Path:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "worlds").mkdir()
    (content_dir / "library").symlink_to(CONTENT_DIR / "library")
    catalogs_src = CONTENT_DIR / "catalogs"
    if catalogs_src.exists():
        (content_dir / "catalogs").symlink_to(catalogs_src)
    return content_dir


def _make_client(tmp_path: Path) -> tuple[TestClient, GameService]:
    content_dir = _with_library(tmp_path)
    service = GameService(store=JsonFileStore(content_dir.parent / "saves"), content_dir=content_dir)
    set_service(service)
    return TestClient(app), service


def _full_selections() -> dict[str, str]:
    return {lt.value: "sword_vale" for lt in LayerType}


class TestWorldSeam:
    def test_invalid_role_header_returns_400_no_world(self, tmp_path: Path) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post(
            "/api/master/worlds",
            json={"id": "bad_role_world", "name": "Bad"},
            headers={"X-Role": "wizard"},
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST
        # No world created
        listed = client.get("/api/master/worlds").json()
        assert not any(w["id"] == "bad_role_world" for w in listed)

    def test_headerless_create_is_local(self, tmp_path: Path) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post("/api/master/worlds", json={"id": "anon_world", "name": "Anon"})
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json()["creator"] == "local"

    def test_caller_creates_world(self, tmp_path: Path) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post(
            "/api/master/worlds",
            json={"id": "alice_world", "name": "Alice"},
            headers={"X-User-Id": "alice"},
        )
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json()["creator"] == "alice"
        # Surfaced in the list too
        listed = client.get("/api/master/worlds").json()
        alice_world = next(w for w in listed if w["id"] == "alice_world")
        assert alice_world["creator"] == "alice"

    def test_body_creator_is_ignored_identity_wins(self, tmp_path: Path) -> None:
        """The caller identity is authoritative — a body-passed creator is ignored."""
        client, _ = _make_client(tmp_path)
        resp = client.post(
            "/api/master/worlds",
            json={"id": "spoof_world", "name": "Spoof", "creator": "attacker"},
            headers={"X-User-Id": "alice"},
        )
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json()["creator"] == "alice"

    def test_assemble_stamps_caller(self, tmp_path: Path) -> None:
        client, _ = _make_client(tmp_path)
        resp = client.post(
            "/api/master/worlds/assemble",
            json={"id": "alice_assembled", "name": "AA", "layer_selections": _full_selections()},
            headers={"X-User-Id": "alice"},
        )
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json()["creator"] == "alice"

    def test_fork_reattributes_source_untouched(self, tmp_path: Path) -> None:
        client, _ = _make_client(tmp_path)
        client.post(
            "/api/master/worlds/assemble",
            json={"id": "src_world", "name": "Src", "layer_selections": _full_selections()},
            headers={"X-User-Id": "alice"},
        )
        resp = client.post(
            "/api/master/worlds/src_world/fork",
            json={"new_id": "bob_fork"},
            headers={"X-User-Id": "bob"},
        )
        assert resp.status_code == HTTPStatus.CREATED
        assert resp.json()["creator"] == "bob"
        # Source unchanged
        listed = client.get("/api/master/worlds").json()
        src = next(w for w in listed if w["id"] == "src_world")
        assert src["creator"] == "alice"


# ---------------------------------------------------------------------------
# HTTP seam — session attribution
# ---------------------------------------------------------------------------


class TestSessionSeam:
    def test_session_create_stamps_created_by(self, tmp_path: Path) -> None:
        client, service = _make_client(tmp_path)
        # A startable world owned by alice
        client.post(
            "/api/master/worlds/assemble",
            json={"id": "play_world", "name": "Play", "layer_selections": _full_selections()},
            headers={"X-User-Id": "alice"},
        )
        resp = client.post(
            "/api/master/sessions",
            json={"world_name": "play_world"},
            headers={"X-User-Id": "alice"},
        )
        assert resp.status_code == HTTPStatus.OK
        sid = resp.json()["session_id"]

        # created_by lands in the autosave meta
        service.autosave_session(sid)
        saved = service._store.load(f"session_{sid}", world="play_world")
        assert saved["meta"]["created_by"] == "alice"

    def test_headerless_session_created_by_local(self, tmp_path: Path) -> None:
        client, service = _make_client(tmp_path)
        client.post(
            "/api/master/worlds/assemble",
            json={"id": "anon_play", "name": "AnonPlay", "layer_selections": _full_selections()},
        )
        resp = client.post("/api/master/sessions", json={"world_name": "anon_play"})
        sid = resp.json()["session_id"]
        service.autosave_session(sid)
        saved = service._store.load(f"session_{sid}", world="anon_play")
        assert saved["meta"]["created_by"] == "local"
