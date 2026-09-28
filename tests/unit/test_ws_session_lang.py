"""The game session speaks the player's language from the first WS message on."""

from __future__ import annotations

import json
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_client(tmp_path: Path) -> tuple[TestClient, GameService]:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    set_service(service)
    return TestClient(app), service


def _create_session(client: TestClient, lang: str) -> str:
    resp = client.post("/api/master/sessions", json={"lang": lang})
    assert resp.status_code == HTTPStatus.OK
    sid = str(resp.json()["session_id"])
    resp = client.post(
        f"/api/player/sessions/{sid}/character",
        json={
            "name": "Tester",
            "race": "human",
            "char_class": "fighter",
            "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
        },
    )
    assert resp.status_code == HTTPStatus.OK
    return sid


def _has_cyrillic(value: Any) -> bool:
    return any("Ѐ" <= ch <= "ӿ" for ch in json.dumps(value, ensure_ascii=False))


def _descriptions(turn: dict[str, Any]) -> list[str]:
    """Rendered (gettext) descriptions of nearby creatures; content fields such as names keep the world's language."""
    nearby = turn["awareness"]["nearby"]
    assert nearby
    return [str(n["description"]) for n in nearby]


def _first_turn(client: TestClient, url: str) -> dict[str, Any]:
    with client.websocket_connect(url) as ws:
        msg: dict[str, Any] = ws.receive_json()
    assert msg["type"] == "turn"
    return msg


class TestTurnRendersInSessionLanguage:
    def test_round_thread_renders_awareness_in_session_language_not_process_default(self, tmp_path: Path) -> None:
        """A round started from a context in the process default (`en` in tests) still speaks the session's `ru`.

        On a real server the WS handler's context never had the session language set (the i18n
        middleware covers HTTP only), and the round thread copies that context.
        """
        _, service = _make_client(tmp_path)
        session = service.start_game("sword_vale", lang="ru")
        service.create_player(
            session.session_id,
            {
                "name": "Tester",
                "race": "human",
                "class": "fighter",
                "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
            },
        )
        player = session.get_player()
        assert player is not None
        turns: list[dict[str, Any]] = []
        got_turn = threading.Event()

        class _Listener:
            def on_turn(self, msg: dict[str, Any]) -> None:
                turns.append(msg)
                got_turn.set()

            def on_action_result(self, msg: dict[str, Any]) -> None: ...
            def on_round_result(self, msg: dict[str, Any]) -> None: ...
            def on_reaction(self, msg: dict[str, Any]) -> None: ...
            def on_game_over(self) -> None: ...

        session.add_listener(_Listener())
        # A fresh thread starts with an empty context, i.e. the process-default language.
        starter = threading.Thread(target=session.start_round, args=(player,))
        starter.start()
        starter.join()
        try:
            assert got_turn.wait(timeout=10)
        finally:
            session.stop_round()

        assert _has_cyrillic(_descriptions(turns[0]))

    def test_ws_lang_becomes_session_language_before_the_first_turn(self, tmp_path: Path) -> None:
        client, service = _make_client(tmp_path)
        sid = _create_session(client, "en")

        turn = _first_turn(client, f"/api/ws/{sid}?lang=ru")

        assert service.get_session(sid).lang == "ru"
        assert _has_cyrillic(_descriptions(turn))

    def test_unsupported_ws_lang_is_ignored(self, tmp_path: Path) -> None:
        client, service = _make_client(tmp_path)
        sid = _create_session(client, "en")

        turn = _first_turn(client, f"/api/ws/{sid}?lang=xx")

        assert service.get_session(sid).lang == "en"
        assert not _has_cyrillic(_descriptions(turn))

    def test_spectator_lang_does_not_change_session_language(self, tmp_path: Path) -> None:
        client, service = _make_client(tmp_path)
        sid = _create_session(client, "en")

        with client.websocket_connect(f"/api/ws/{sid}?spectate=true&lang=ru"):
            pass

        assert service.get_session(sid).lang == "en"


class TestStaleTurnReplay:
    def test_rejoin_in_another_language_gets_no_turn_rendered_in_the_old_one(self, tmp_path: Path) -> None:
        """Leave an English game, switch to Russian, rejoin: the first turn is Russian, not the cached English one."""
        client, _ = _make_client(tmp_path)
        sid = _create_session(client, "en")
        first = _first_turn(client, f"/api/ws/{sid}")
        assert not _has_cyrillic(_descriptions(first))

        assert client.put(f"/api/master/sessions/{sid}/lang", json={"lang": "ru"}).status_code == HTTPStatus.OK
        rejoined = _first_turn(client, f"/api/ws/{sid}")

        assert _has_cyrillic(_descriptions(rejoined))

    def test_turn_in_another_language_is_still_replayed_while_its_round_runs(self, tmp_path: Path) -> None:
        """A running round will not re-issue the waiting turn, so its cached message is the only one there is."""
        _, service = _make_client(tmp_path)
        session = service.start_game("sword_vale", lang="en")
        session._last_turn_msg = {"type": "turn"}
        session._last_turn_lang = "en"
        session.lang = "ru"

        assert session.get_last_turn_msg() is None

        session._round_thread = MagicMock()
        session._round_thread.is_alive.return_value = True
        assert session.get_last_turn_msg() == {"type": "turn"}
        session._round_thread = None
