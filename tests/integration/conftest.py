"""Integration test configuration.

Fixtures for testing against a live backend in docker compose.
Backend runs with DND_DICE_SEED=42 and test content (no LLM).
"""

from __future__ import annotations

import contextlib
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import requests
import websocket

SAVES_DIR = Path("/app/saves")


def _save_files_snapshot() -> set[Path]:
    if not SAVES_DIR.exists():
        return set()
    return {path.relative_to(SAVES_DIR) for path in SAVES_DIR.rglob("*") if path.is_file()}


@pytest.fixture(scope="session", autouse=True)
def cleanup_new_save_files() -> Iterator[None]:
    """Remove save files created by the docker integration run."""
    before = _save_files_snapshot()
    yield
    for relative_path in _save_files_snapshot() - before:
        (SAVES_DIR / relative_path).unlink(missing_ok=True)
    for path in sorted((p for p in SAVES_DIR.rglob("*") if p.is_dir()), reverse=True):
        with contextlib.suppress(OSError):
            path.rmdir()


@pytest.fixture(scope="session")
def backend_url() -> str:
    """Base URL of the running backend."""
    return os.environ.get("BACKEND_URL", "http://backend:8001")


@pytest.fixture(scope="session")
def api_url(backend_url: str) -> str:
    """Master API base URL."""
    return f"{backend_url}/api/master"


@pytest.fixture(scope="session")
def player_api_url(backend_url: str) -> str:
    """Player API base URL."""
    return f"{backend_url}/api/player"


@pytest.fixture(scope="session")
def ws_base_url(backend_url: str) -> str:
    """WebSocket base URL (ws:// scheme)."""
    return backend_url.replace("http://", "ws://") + "/api/ws"


# ── Arena session (combat tests) ──────────────────────────────────────


@pytest.fixture(scope="session")
def arena_session(api_url: str) -> Iterator[str]:
    """Create an arena session, yield session_id, delete on teardown."""
    resp = requests.post(
        f"{api_url}/sessions",
        json={"world_name": "arena", "lang": "en"},
        timeout=10,
    )
    resp.raise_for_status()
    session_id = resp.json()["session_id"]
    yield session_id
    requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)


@pytest.fixture(scope="session")
def arena_player(player_api_url: str, arena_session: str) -> dict[str, Any]:
    """Create a player character in the arena session."""
    resp = requests.post(
        f"{player_api_url}/sessions/{arena_session}/character",
        json={
            "name": "Test Hero",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "appearance": "A battle-worn warrior.",
            "start_location": "arena_floor",
            "ability_scores": {
                "str": 15,
                "dex": 14,
                "con": 14,
                "int": 10,
                "wis": 10,
                "cha": 8,
            },
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ── Village session (peaceful / schedule tests) ───────────────────────


@pytest.fixture(scope="session")
def village_session(api_url: str) -> Iterator[str]:
    """Create a village session, yield session_id, delete on teardown."""
    resp = requests.post(
        f"{api_url}/sessions",
        json={"world_name": "village", "lang": "en"},
        timeout=10,
    )
    resp.raise_for_status()
    session_id = resp.json()["session_id"]
    yield session_id
    requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)


@pytest.fixture(scope="session")
def village_player(player_api_url: str, village_session: str) -> dict[str, Any]:
    """Create a player character in the village session."""
    resp = requests.post(
        f"{player_api_url}/sessions/{village_session}/character",
        json={
            "name": "Traveler",
            "race": "human",
            "char_class": "fighter",
            "alignment": "true_neutral",
            "appearance": "A dusty traveler.",
            "start_location": "village_square",
            "ability_scores": {
                "str": 12,
                "dex": 12,
                "con": 12,
                "int": 10,
                "wis": 10,
                "cha": 10,
            },
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()


# ── WebSocket helpers ─────────────────────────────────────────────────


def ws_connect(ws_base_url: str, session_id: str, player_id: str) -> websocket.WebSocket:
    """Connect to the game WebSocket, return the connected socket."""
    url = f"{ws_base_url}/{session_id}?player_id={player_id}"
    ws = websocket.create_connection(url, timeout=10)
    return ws


def ws_recv(ws: websocket.WebSocket) -> dict[str, Any]:
    """Receive and parse a JSON message from WebSocket."""
    raw = ws.recv()
    assert isinstance(raw, str)
    return json.loads(raw)


def ws_send_action(ws: websocket.WebSocket, name: str, **params: Any) -> None:
    """Send an action message over WebSocket."""
    msg: dict[str, Any] = {"type": "action", "name": name}
    if params:
        msg["params"] = params
    ws.send(json.dumps(msg))
