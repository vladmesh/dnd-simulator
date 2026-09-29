"""Smoke tests for the production frontend container.

Run by `make test-frontend-container` (the `frontend-smoke` compose service): nginx serves
the built SPA and must proxy /api (REST + the game WebSocket) and /health to the backend
exactly as the Vite dev server proxy does (frontend/vite.config.ts).
"""

from __future__ import annotations

import json
import os
import re
from collections.abc import Iterator
from http import HTTPStatus
from typing import Any

import pytest
import requests
import websocket

FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://frontend")
BACKEND_URL = os.environ.get("BACKEND_URL", "http://backend:8001")
WS_BASE_URL = FRONTEND_URL.replace("http://", "ws://") + "/api/ws"


def _recv_json(ws: websocket.WebSocket) -> dict[str, Any]:
    raw = ws.recv()
    assert isinstance(raw, str)
    msg = json.loads(raw)
    assert isinstance(msg, dict)
    return msg


def test_index_serves_built_spa() -> None:
    resp = requests.get(f"{FRONTEND_URL}/", timeout=5)
    assert resp.status_code == HTTPStatus.OK
    assert resp.headers["content-type"].startswith("text/html")
    assert '<div id="root"></div>' in resp.text
    # The production build references hashed bundles, not the dev entry point.
    assert "/src/main.tsx" not in resp.text


def test_built_assets_are_served() -> None:
    index = requests.get(f"{FRONTEND_URL}/", timeout=5).text
    scripts = re.findall(r'<script[^>]+src="(/assets/[^"]+\.js)"', index)
    assert scripts, index
    resp = requests.get(f"{FRONTEND_URL}{scripts[0]}", timeout=5)
    assert resp.status_code == HTTPStatus.OK
    assert "javascript" in resp.headers["content-type"]


def test_client_side_route_falls_back_to_index() -> None:
    resp = requests.get(f"{FRONTEND_URL}/master", timeout=5)
    assert resp.status_code == HTTPStatus.OK
    assert '<div id="root"></div>' in resp.text


def test_missing_asset_is_404_not_index() -> None:
    resp = requests.get(f"{FRONTEND_URL}/assets/does-not-exist.js", timeout=5)
    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_health_is_proxied_to_backend() -> None:
    resp = requests.get(f"{FRONTEND_URL}/health", timeout=5)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["status"] == "ok"


def test_api_is_proxied_to_backend() -> None:
    via_frontend = requests.get(f"{FRONTEND_URL}/api/master/worlds", timeout=10)
    direct = requests.get(f"{BACKEND_URL}/api/master/worlds", timeout=10)
    assert via_frontend.status_code == HTTPStatus.OK
    assert via_frontend.json() == direct.json()


def test_api_errors_pass_through() -> None:
    resp = requests.get(f"{FRONTEND_URL}/api/master/sessions/no-such-session", timeout=5)
    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert resp.headers["content-type"].startswith("application/json")


def test_websocket_upgrade_is_proxied() -> None:
    ws = websocket.create_connection(f"{WS_BASE_URL}/no-such-session", timeout=10)
    try:
        msg = _recv_json(ws)
    finally:
        ws.close()
    assert msg["type"] == "error"
    assert "no-such-session" in msg["message"]


@pytest.fixture
def village_session() -> Iterator[tuple[str, str]]:
    """A session created entirely through the frontend proxy. Yields (session_id, player_id)."""
    resp = requests.post(
        f"{FRONTEND_URL}/api/master/sessions", json={"world_name": "village", "lang": "en"}, timeout=10
    )
    resp.raise_for_status()
    session_id = resp.json()["session_id"]
    try:
        resp = requests.post(
            f"{FRONTEND_URL}/api/player/sessions/{session_id}/character",
            json={
                "name": "Proxy Traveler",
                "race": "human",
                "char_class": "fighter",
                "alignment": "true_neutral",
                "start_location": "village_square",
                "ability_scores": {"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10},
            },
            timeout=10,
        )
        resp.raise_for_status()
        yield session_id, resp.json()["player_id"]
    finally:
        requests.delete(f"{FRONTEND_URL}/api/master/sessions/{session_id}", timeout=5)


def test_player_websocket_game_loop_through_proxy(village_session: tuple[str, str]) -> None:
    session_id, player_id = village_session
    ws = websocket.create_connection(f"{WS_BASE_URL}/{session_id}?player_id={player_id}", timeout=10)
    try:
        msg = _recv_json(ws)
        while msg["type"] != "turn":
            msg = _recv_json(ws)
        ws.send(json.dumps({"type": "action", "name": "end_turn"}))
        msg = _recv_json(ws)
        assert msg["type"] != "error", msg
    finally:
        ws.close()
