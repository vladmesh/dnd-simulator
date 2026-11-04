"""Branch coverage for the WebSocket endpoint: origin check, rate limiting, malformed
messages, spectator mode, unexpected errors and the WsEventListener send bridge."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from test_ws import _create_session_with_player, _make_client

from dnd_simulator.adapters.api import routes_ws
from dnd_simulator.adapters.api.routes_ws import WsEventListener
from dnd_simulator.service import GameService
from dnd_simulator.service.action_parsing import MAX_ACTION_PARAMS

Ws = Any


def _setup(tmp_path: object) -> tuple[TestClient, GameService, str]:
    client, service = _make_client(tmp_path)
    sid = _create_session_with_player(client)
    service.get_session(sid).lang = "en"
    return client, service, sid


def _recv_error(ws: Ws) -> str:
    """Skip round traffic (turn/round_result) until the next error message."""
    while True:
        msg = ws.receive_json()
        if msg["type"] == "error":
            return str(msg["message"])


@pytest.fixture
def frozen_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """No token refill between messages: the bucket only drains."""
    monkeypatch.setattr(routes_ws, "time", SimpleNamespace(monotonic=lambda: 1000.0))


class TestOriginCheck:
    def test_disallowed_origin_closed_with_4003(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _service, sid = _setup(tmp_path)
        monkeypatch.setenv("WS_ALLOWED_ORIGINS", "https://good.example, ,https://other.example")
        with (
            pytest.raises(WebSocketDisconnect) as exc,
            client.websocket_connect(f"/api/ws/{sid}", headers={"origin": "https://evil.example"}),
        ):
            pass
        assert exc.value.code == 4003

    def test_allowed_origin_connects(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        client, _service, sid = _setup(tmp_path)
        monkeypatch.setenv("WS_ALLOWED_ORIGINS", "https://good.example,https://other.example")
        with client.websocket_connect(
            f"/api/ws/{sid}?spectate=true", headers={"origin": "https://other.example"}
        ) as ws:
            ws.send_json({"type": "ping"})
            assert _recv_error(ws) == "Unknown message type: ping"


class TestPlayerMessages:
    @pytest.mark.parametrize(
        ("payload", "expected"),
        [
            ({"type": "action", "name": "no_such_action"}, "Unknown action: no_such_action"),
            ({"type": "action", "name": "attack", "params": [1]}, "Action params must be a JSON object"),
            (
                {"type": "action", "name": "attack", "params": {f"k{i}": i for i in range(MAX_ACTION_PARAMS + 1)}},
                "Action params are too large",
            ),
            ({"type": "reaction", "name": "no_such_reaction"}, "Unknown reaction: no_such_reaction"),
            ({"type": "reaction", "name": "skip", "params": "x"}, "Action params must be a JSON object"),
            ({"type": "reaction", "name": "skip"}, "No reaction prompt is pending"),
            ({"type": "bogus"}, "Unknown message type: bogus"),
            ([1, 2], "JSON message must be an object"),
        ],
    )
    def test_rejected_message(self, tmp_path: object, payload: object, expected: str) -> None:
        client, _service, sid = _setup(tmp_path)
        with client.websocket_connect(f"/api/ws/{sid}?lang=en") as ws:
            ws.send_json(payload)
            assert _recv_error(ws) == expected

    def test_invalid_json(self, tmp_path: object) -> None:
        client, _service, sid = _setup(tmp_path)
        with client.websocket_connect(f"/api/ws/{sid}?lang=en") as ws:
            ws.send_text("{not json")
            assert _recv_error(ws) == "Invalid JSON"

    def test_rate_limited_after_burst(self, tmp_path: object, frozen_clock: None) -> None:
        client, _service, sid = _setup(tmp_path)
        with client.websocket_connect(f"/api/ws/{sid}?lang=en") as ws:
            for _ in range(21):
                ws.send_json({"type": "bogus"})
            errors = [_recv_error(ws) for _ in range(21)]
        assert errors[:20] == ["Unknown message type: bogus"] * 20
        assert errors[20] == "Rate limited, slow down"

    def test_pending_reaction_replayed_on_connect(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        client, service, sid = _setup(tmp_path)
        session = service.get_session(sid)
        prompt = {"type": "reaction_prompt", "trigger": {}, "options": []}
        monkeypatch.setattr(session, "get_last_turn_msg", lambda: None)
        monkeypatch.setattr(session, "get_pending_reaction_msg", lambda: prompt)
        with client.websocket_connect(f"/api/ws/{sid}?lang=en") as ws:
            assert ws.receive_json() == prompt

    def test_unexpected_error_closes_and_removes_listener(
        self, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, service, sid = _setup(tmp_path)
        session = service.get_session(sid)
        removed = threading.Event()
        original_remove = session.remove_listener

        def _remove(listener: Any) -> None:
            original_remove(listener)
            removed.set()

        monkeypatch.setattr(session, "remove_listener", _remove)

        def _boom(raw: str) -> tuple[None, None]:
            raise RuntimeError("boom")

        monkeypatch.setattr(routes_ws, "_parse_json_object_envelope", _boom)
        with client.websocket_connect(f"/api/ws/{sid}?lang=en") as ws:
            ws.send_text("{}")
            # The endpoint logs the error and cleans up without crashing the server.
            assert removed.wait(5)


class TestSpectator:
    def test_replays_last_turn_and_rejects_actions(self, tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
        client, service, sid = _setup(tmp_path)
        session = service.get_session(sid)
        last_turn = {"type": "turn", "mode": "peaceful"}
        monkeypatch.setattr(session, "get_last_turn_msg", lambda: last_turn)
        with client.websocket_connect(f"/api/ws/{sid}?spectate=true") as ws:
            assert ws.receive_json() == last_turn
            ws.send_json({"type": "action", "name": "attack"})
            assert _recv_error(ws) == "Spectators cannot submit actions"
            ws.send_json({"type": "reaction", "name": "skip"})
            assert _recv_error(ws) == "Spectators cannot submit actions"
            ws.send_text("[]")
            assert _recv_error(ws) == "JSON message must be an object"
            ws.send_text("x" * (routes_ws.MAX_WS_MESSAGE_BYTES + 1))
            assert _recv_error(ws) == f"Message too large (limit {routes_ws.MAX_WS_MESSAGE_BYTES} bytes)"

    def test_spectator_rate_limited(self, tmp_path: object, frozen_clock: None) -> None:
        client, _service, sid = _setup(tmp_path)
        with client.websocket_connect(f"/api/ws/{sid}?spectate=true") as ws:
            for _ in range(21):
                ws.send_json({"type": "bogus"})
            errors = [_recv_error(ws) for _ in range(21)]
        assert errors[:20] == ["Unknown message type: bogus"] * 20
        assert errors[20] == "Rate limited, slow down"

    def test_spectator_unexpected_error_removes_spectator(
        self, tmp_path: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        client, service, sid = _setup(tmp_path)
        session = service.get_session(sid)
        removed = threading.Event()
        original_remove = session.remove_spectator

        def _remove(listener: Any) -> None:
            original_remove(listener)
            removed.set()

        monkeypatch.setattr(session, "remove_spectator", _remove)

        def _boom(raw: str) -> tuple[None, None]:
            raise RuntimeError("boom")

        monkeypatch.setattr(routes_ws, "_parse_json_object_envelope", _boom)
        with client.websocket_connect(f"/api/ws/{sid}?spectate=true") as ws:
            ws.send_text("{}")
            # The endpoint logs the error and cleans up without crashing the server.
            assert removed.wait(5)


class _FakeWs:
    def __init__(self, error: BaseException | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self._error = error

    async def send_json(self, msg: dict[str, Any]) -> None:
        if self._error is not None:
            raise self._error
        self.sent.append(msg)


@pytest.fixture
def running_loop() -> Iterator[asyncio.AbstractEventLoop]:
    loop = asyncio.new_event_loop()
    thread = threading.Thread(target=loop.run_forever, daemon=True)
    thread.start()
    yield loop
    loop.call_soon_threadsafe(loop.stop)
    thread.join(5)
    loop.close()


class TestWsEventListener:
    def test_all_callbacks_forward_messages(self, running_loop: asyncio.AbstractEventLoop) -> None:
        ws = _FakeWs()
        listener = WsEventListener(ws, running_loop)  # type: ignore[arg-type]
        listener.on_turn({"type": "turn"})
        listener.on_action_result({"type": "action_result"})
        listener.on_round_result({"type": "round_result"})
        listener.on_reaction({"type": "reaction_prompt"})
        listener.on_game_over()
        assert [m["type"] for m in ws.sent] == ["turn", "action_result", "round_result", "reaction_prompt", "game_over"]

    def test_closed_listener_sends_nothing(self, running_loop: asyncio.AbstractEventLoop) -> None:
        ws = _FakeWs()
        listener = WsEventListener(ws, running_loop)  # type: ignore[arg-type]
        listener.close()
        listener.on_turn({"type": "turn"})
        assert ws.sent == []

    def test_send_scheduled_before_close_is_dropped_on_loop(self) -> None:
        ws = _FakeWs()
        loop = asyncio.new_event_loop()
        try:
            listener = WsEventListener(ws, loop)  # type: ignore[arg-type]
            coro = listener._send_if_open({"type": "turn"})
            listener.close()
            loop.run_until_complete(coro)
        finally:
            loop.close()
        assert ws.sent == []

    def test_closed_event_loop_sends_nothing(self) -> None:
        ws = _FakeWs()
        loop = asyncio.new_event_loop()
        loop.close()
        WsEventListener(ws, loop).on_game_over()  # type: ignore[arg-type]
        assert ws.sent == []

    @pytest.mark.parametrize("error", [WebSocketDisconnect(code=1001), ConnectionError("reset")])
    def test_send_failure_is_swallowed(self, running_loop: asyncio.AbstractEventLoop, error: BaseException) -> None:
        listener = WsEventListener(_FakeWs(error), running_loop)  # type: ignore[arg-type]
        listener.on_turn({"type": "turn"})  # must not raise
