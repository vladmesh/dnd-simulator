"""Cover cached-turn replay when a second player socket joins a running round."""

from pathlib import Path

from test_ws import _create_session_with_player, _make_client


def test_second_player_socket_replays_cached_turn(tmp_path: Path) -> None:
    client, service = _make_client(tmp_path)
    session_id = _create_session_with_player(client)
    session = service.get_session(session_id)

    with client.websocket_connect(f"/api/ws/{session_id}?lang=en") as first:
        turn = first.receive_json()
        assert turn["type"] == "turn"
        assert session.get_last_turn_msg() is not None

        with client.websocket_connect(f"/api/ws/{session_id}?lang=en") as second:
            assert second.receive_json() == turn
            second.send_json({"type": "bogus"})
            assert second.receive_json() == {"type": "error", "message": "Unknown message type: bogus"}
