"""WebSocket protocol flows: reaction prompts, multi-action NPC turns, back-to-back
messages, and a disconnect in the middle of an NPC turn.

Runs against a live backend (DND_DICE_SEED=42, rule-based NPCs, no LLM) with the
``ws_test`` world: the player stands at (20, 30) next to a hostile Raider (15, 30); a
wounded, immobile Wounded Deer (40, 30) is hostile to the Raider and neutral to the player.
RuleBrain prefers the wounded target, so in its first combat turn the Raider equips its club,
walks out of the player's reach (the player gets a LEAVING_REACH reaction prompt in the middle
of that move), and attacks the Deer. Initiative with the fixed seed: Deer, player, Raider.

Each test creates its own session.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import requests
import websocket as ws_lib
from conftest import ws_connect, ws_recv, ws_send_action

WORLD = "ws_test"
LOCATION = "ws_floor"
RUNNER = "ws_runner"
RUNNER_HP = 100
PREY = "ws_prey"
PREY_HP = 30  # wounded below its 100 max so the Raider targets it
PLAYER_CELL = (20, 30)
PREY_CELL = (40, 30)

Msg = dict[str, Any]


@dataclass(frozen=True)
class WsGame:
    api: str
    ws_base: str
    sid: str
    pid: str


@pytest.fixture
def game(api_url: str, player_api_url: str, ws_base_url: str) -> Iterator[WsGame]:
    resp = requests.post(f"{api_url}/sessions", json={"world_name": WORLD, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]
    try:
        resp = requests.post(
            f"{player_api_url}/sessions/{sid}/character",
            json={
                "name": "WS Flow Fighter",
                "race": "human",
                "char_class": "fighter",
                "alignment": "true_neutral",
                "start_location": LOCATION,
                "combat_position": list(PLAYER_CELL),
                "ability_scores": {"str": 15, "dex": 11, "con": 14, "int": 10, "wis": 10, "cha": 9},
            },
            timeout=10,
        )
        resp.raise_for_status()
        requests.patch(
            f"{api_url}/sessions/{sid}/creatures/{PREY}", json={"current_hp": PREY_HP}, timeout=5
        ).raise_for_status()
        yield WsGame(api=api_url, ws_base=ws_base_url, sid=sid, pid=resp.json()["player_id"])
    finally:
        requests.delete(f"{api_url}/sessions/{sid}", timeout=10)


# ── Helpers ───────────────────────────────────────────────────────────────


def _connect(game: WsGame) -> ws_lib.WebSocket:
    return ws_connect(game.ws_base, game.sid, game.pid)


def _send_reaction(sock: ws_lib.WebSocket, name: str, **params: Any) -> None:
    msg: dict[str, Any] = {"type": "reaction", "name": name}
    if params:
        msg["params"] = params
    sock.send(json.dumps(msg))


def _recv_until(sock: ws_lib.WebSocket, pred: Callable[[Msg], bool], log: list[Msg], max_msgs: int = 60) -> Msg:
    """Receive (recording every message into ``log``) until ``pred`` matches; fail otherwise."""
    for _ in range(max_msgs):
        msg = ws_recv(sock)
        log.append(msg)
        assert msg["type"] not in ("error", "game_over"), f"unexpected {msg}"
        if pred(msg):
            return msg
    raise AssertionError(f"no matching message in {max_msgs}: {[m['type'] for m in log]}")


def _is(msg_type: str) -> Callable[[Msg], bool]:
    return lambda msg: msg["type"] == msg_type


def _first_turn(sock: ws_lib.WebSocket) -> Msg:
    turn = _recv_until(sock, _is("turn"), [])
    assert turn["mode"] == "combat", "the Raider attacks on sight, so the first player turn is a combat turn"
    assert turn["budget"]["actions"] == 1
    return turn


def _until_next_turn(sock: ws_lib.WebSocket, log: list[Msg], *, reaction: str = "skip") -> Msg:
    """Collect until the player's next turn, answering any reaction prompt with ``reaction``."""
    while True:
        msg = _recv_until(sock, lambda m: m["type"] in ("turn", "reaction_prompt"), log)
        if msg["type"] == "turn":
            return msg
        _send_reaction(sock, reaction)


def _assert_quiet(sock: ws_lib.WebSocket, seconds: float = 0.5) -> None:
    """The round is blocked on the player: nothing arrives."""
    sock.settimeout(seconds)
    try:
        with pytest.raises(ws_lib.WebSocketTimeoutException):
            msg = ws_recv(sock)
            raise AssertionError(f"round did not wait for the player, got {msg['type']}")
    finally:
        sock.settimeout(10)


def _events(log: list[Msg]) -> list[Msg]:
    return [event for msg in log for event in msg.get("events", [])]


def _hits_on(events: list[Msg], target_id: str) -> int:
    """Total damage dealt to ``target_id`` by the attacks in ``events``."""
    return sum(
        int(e["data"].get("total_damage", 0))
        for e in events
        if e["event_type"] == "entity_attack" and e["data"]["target_id"] == target_id and e["data"].get("hit")
    )


def _actions_by(log: list[Msg], actor: str) -> list[Msg]:
    return [m for m in log if m["type"] == "action_result" and m.get("actor") == actor]


def _pos(msg: Msg, entity_id: str) -> tuple[int, int]:
    entry = next(e for e in msg["awareness"]["nearby"] if e["id"] == entity_id)
    return entry["x"], entry["y"]


def _cells_apart(a: tuple[int, int], b: tuple[int, int]) -> int:
    """Grid cells between two positions (diagonals count as one): 1 = adjacent (5 ft reach)."""
    return max(abs(a[0] - b[0]), abs(a[1] - b[1])) // 5


def _hp(game: WsGame, entity_id: str) -> int:
    resp = requests.get(f"{game.api}/sessions/{game.sid}/creatures/{entity_id}", timeout=10)
    resp.raise_for_status()
    return int(resp.json()["hp"])


def _to_runner_prompt(sock: ws_lib.WebSocket, log: list[Msg]) -> Msg:
    """End the first player turn and wait for the Raider's move to trigger the reaction prompt."""
    _first_turn(sock)
    ws_send_action(sock, "end_turn")
    prompt = _recv_until(sock, lambda m: m["type"] in ("reaction_prompt", "turn"), log)
    assert prompt["type"] == "reaction_prompt", "the Raider's move out of reach must prompt the player first"
    return prompt


def _assert_consistent_with_rest(game: WsGame, turn: Msg) -> None:
    """A turn message agrees with the authoritative REST state."""
    assert turn["player"]["hp"] == _hp(game, game.pid)
    nearby = {e["id"]: e for e in turn["awareness"]["nearby"]}
    assert nearby[PREY]["is_wounded"] is True
    assert (nearby[RUNNER]["x"], nearby[RUNNER]["y"]) != (15, 30)


# ── 1. Reaction prompts over WS ───────────────────────────────────────────


class TestReactionPrompt:
    def test_enemy_leaving_reach_prompts_player_and_round_waits(self, game: WsGame) -> None:
        sock = _connect(game)
        try:
            prompt = _to_runner_prompt(sock, [])

            trigger = prompt["trigger"]
            assert trigger["trigger_type"] == "leaving_reach"
            assert trigger["source_creature_id"] == RUNNER
            assert trigger["data"]["mover_id"] == RUNNER
            assert _cells_apart(tuple(trigger["data"]["from_pos"]), PLAYER_CELL) == 1
            assert _cells_apart(tuple(trigger["data"]["to_pos"]), PLAYER_CELL) > 1
            assert [(o["action_type"], o["params"]) for o in prompt["options"]] == [
                ("opportunity_attack", {"target_id": RUNNER})
            ]

            # The Raider's turn is suspended mid-move until the player answers.
            _assert_quiet(sock)
            _send_reaction(sock, "skip")
            _until_next_turn(sock, [])
        finally:
            sock.close()

    def test_accept_makes_one_opportunity_attack(self, game: WsGame) -> None:
        sock = _connect(game)
        try:
            prompt = _to_runner_prompt(sock, [])
            _send_reaction(sock, "opportunity_attack", **prompt["options"][0]["params"])

            log: list[Msg] = []
            turn = _until_next_turn(sock, log)
            events = _events(log)

            oas = [e for e in events if e["event_type"] == "opportunity_attack"]
            assert [(e["data"]["attacker_id"], e["data"]["target_id"]) for e in oas] == [(game.pid, RUNNER)]
            player_attacks = [e for e in events if e["event_type"] == "entity_attack" and e["actor_id"] == game.pid]
            assert len(player_attacks) == 1
            assert player_attacks[0]["data"]["is_opportunity_attack"] is True

            # The reaction does not stop the move: the Raider still reaches the Deer.
            moves = [m for m in _actions_by(log, RUNNER) if m["action"] == "move_to"]
            assert len(moves) == 1
            assert _cells_apart(_pos(moves[0], RUNNER), PREY_CELL) == 1

            assert _hp(game, RUNNER) == RUNNER_HP - _hits_on(events, RUNNER)
            _assert_consistent_with_rest(game, turn)
        finally:
            sock.close()

    def test_decline_makes_no_opportunity_attack(self, game: WsGame) -> None:
        sock = _connect(game)
        try:
            _to_runner_prompt(sock, [])
            _send_reaction(sock, "skip")

            log: list[Msg] = []
            turn = _until_next_turn(sock, log)
            events = _events(log)

            assert [e for e in events if e["event_type"] == "opportunity_attack"] == []
            assert [e for e in events if e["event_type"] == "entity_attack" and e["actor_id"] == game.pid] == []
            assert [m["action"] for m in _actions_by(log, RUNNER)][:2] == ["move_to", "attack"]
            assert _hp(game, RUNNER) == RUNNER_HP - _hits_on(events, RUNNER)
            _assert_consistent_with_rest(game, turn)
        finally:
            sock.close()

    def test_stray_answer_is_rejected_and_does_not_answer_the_next_prompt(self, game: WsGame) -> None:
        """Regression: a reaction sent with no prompt pending was queued and silently
        consumed by the next prompt, making an attack the player never chose."""
        sock = _connect(game)
        try:
            _first_turn(sock)
            _send_reaction(sock, "opportunity_attack", target_id=RUNNER)
            error = ws_recv(sock)
            assert error == {"type": "error", "message": "No reaction prompt is pending"}

            ws_send_action(sock, "end_turn")
            _recv_until(sock, _is("reaction_prompt"), [])
            _assert_quiet(sock)  # the stray answer did not resolve the prompt
            _send_reaction(sock, "skip")

            log: list[Msg] = []
            _until_next_turn(sock, log)
            assert [e for e in _events(log) if e["event_type"] == "opportunity_attack"] == []
        finally:
            sock.close()

    def test_second_answer_to_one_prompt_is_rejected(self, game: WsGame) -> None:
        """Regression: a double-sent answer was queued for whatever prompt came next."""
        sock = _connect(game)
        try:
            _to_runner_prompt(sock, [])
            _send_reaction(sock, "skip")
            _send_reaction(sock, "opportunity_attack", target_id=RUNNER)

            log: list[Msg] = []
            error = None
            while error is None:
                msg = ws_recv(sock)
                if msg["type"] == "error":
                    error = msg
                else:
                    log.append(msg)
            assert error["message"] == "No reaction prompt is pending"
            _until_next_turn(sock, log)
            assert [e for e in _events(log) if e["event_type"] == "opportunity_attack"] == []
        finally:
            sock.close()


# ── 2. Multi-action NPC turn over WS ──────────────────────────────────────


class TestMultiActionNpcTurn:
    def test_move_then_attack_arrive_in_order_with_final_state(self, game: WsGame) -> None:
        sock = _connect(game)
        try:
            _first_turn(sock)
            ws_send_action(sock, "end_turn")

            log: list[Msg] = []
            turn = _until_next_turn(sock, log)
            end = next(i for i, m in enumerate(log) if m["type"] == "round_result")
            runner_turn = log[:end]  # the Raider acts last in the round

            actions = [m["action"] for m in runner_turn if m["type"] == "action_result"]
            assert all(m.get("actor") == RUNNER for m in runner_turn if m["type"] == "action_result")
            assert actions == ["equip", "move_to", "attack"]

            types = [m["type"] for m in runner_turn]
            move_i = next(i for i, m in enumerate(runner_turn) if m.get("action") == "move_to")
            # The prompt fires during the move, before the move's own result is broadcast.
            assert types.index("reaction_prompt") < move_i

            move, attack = runner_turn[move_i], runner_turn[move_i + 1]
            end_cell = _pos(move, RUNNER)
            assert _cells_apart(end_cell, PREY_CELL) == 1
            assert _cells_apart(end_cell, PLAYER_CELL) > 1
            [strike] = [e for e in attack["events"] if e["event_type"] == "entity_attack"]
            assert (strike["data"]["attacker_id"], strike["data"]["target_id"]) == (RUNNER, PREY)

            # Final state: the next turn shows the Raider where the move ended, and the Deer
            # has lost exactly what the Raider's attack dealt (no one else targets the Deer).
            assert _pos(turn, RUNNER) == end_cell
            assert _pos(attack, RUNNER) == end_cell
            assert _hp(game, PREY) == PREY_HP - _hits_on(_events(log), PREY)
            assert _hp(game, RUNNER) == RUNNER_HP - _hits_on(_events(log), RUNNER)
            _assert_consistent_with_rest(game, turn)
        finally:
            sock.close()


# ── 3. Back-to-back player messages ───────────────────────────────────────


class TestBackToBackMessages:
    def test_two_actions_sent_without_waiting_apply_once_each_in_order(self, game: WsGame) -> None:
        sock = _connect(game)
        try:
            _first_turn(sock)
            ws_send_action(sock, "dodge")
            ws_send_action(sock, "end_turn")

            log: list[Msg] = []
            turn = _recv_until(sock, _is("turn"), log)  # the multi-action loop asks again after dodge
            assert turn["budget"]["actions"] == 0
            rest: list[Msg] = []
            turn = _until_next_turn(sock, rest)  # end_turn was already queued: no input needed
            log += rest

            player_results = _actions_by(log, game.pid)
            assert [m["action"] for m in player_results] == ["dodge"]
            assert "error" not in player_results[0]
            dodges = [e for e in _events(log) if e["event_type"] == "entity_dodge"]
            assert [e["actor_id"] for e in dodges] == [game.pid]

            # end_turn ended the turn: the Raider acted, a round ended, and only then did
            # the player's next (fresh-budget) turn arrive.
            round_end = next(i for i, m in enumerate(rest) if m["type"] == "round_result")
            assert _actions_by(rest[:round_end], RUNNER), "the Raider never acted after end_turn"
            assert [m for m in rest[:round_end] if m["type"] == "turn"] == []
            assert turn["budget"]["actions"] == 1
        finally:
            sock.close()

    def test_duplicate_action_is_applied_once_and_the_copy_is_refused(self, game: WsGame) -> None:
        sock = _connect(game)
        try:
            _first_turn(sock)
            ws_send_action(sock, "dodge")
            ws_send_action(sock, "dodge")

            log: list[Msg] = []
            _recv_until(sock, _is("turn"), log)
            turn = _recv_until(sock, _is("turn"), log)

            first, second = _actions_by(log, game.pid)
            assert (first["action"], second["action"]) == ("dodge", "dodge")
            assert "error" not in first
            assert second["error"].startswith("Not enough budget")
            assert [e["actor_id"] for e in _events(log) if e["event_type"] == "entity_dodge"] == [game.pid]
            assert turn["budget"]["actions"] == 0

            # The turn is still the player's; it ends only on request, once.
            _assert_quiet(sock)
            ws_send_action(sock, "end_turn")
            after: list[Msg] = []
            turn = _until_next_turn(sock, after)
            assert _actions_by(after, game.pid) == []
            assert turn["budget"]["actions"] == 1
        finally:
            sock.close()


# ── 4. Disconnect during an NPC turn ──────────────────────────────────────


class TestDisconnectDuringNpcTurn:
    """The client drops while the Raider's turn is suspended mid-move on the player's
    reaction prompt, so the disconnect deterministically lands inside an NPC turn."""

    def test_quick_reconnect_resumes_the_interrupted_npc_turn(self, game: WsGame) -> None:
        sock = _connect(game)
        _to_runner_prompt(sock, [])
        sock.close()
        time.sleep(0.5)  # let the server process the disconnect (stops the round)

        sock = _connect(game)  # inside the eviction grace window
        try:
            log: list[Msg] = []
            turn = _until_next_turn(sock, log)
            events = _events(log)

            # The pending prompt was declined by the stop; the move completed; the Raider's
            # turn continued with its remaining budget (attack) instead of starting over.
            assert "reaction_prompt" not in [m["type"] for m in log]
            round_end = next(i for i, m in enumerate(log) if m["type"] == "round_result")
            assert [m["action"] for m in _actions_by(log[:round_end], RUNNER)] == ["attack"]
            assert [e for e in events if e["event_type"] == "opportunity_attack"] == []

            assert _cells_apart(_pos(turn, RUNNER), PREY_CELL) == 1
            assert _hp(game, PREY) == PREY_HP - _hits_on(events, PREY)
            assert _hp(game, RUNNER) == RUNNER_HP - _hits_on(events, RUNNER)
            _assert_consistent_with_rest(game, turn)
        finally:
            sock.close()

    def test_reconnect_before_old_socket_drops_replays_pending_prompt(self, game: WsGame) -> None:
        """Regression: a client that connects while the round waits on a reaction prompt
        (a reconnect that beats the old socket's close, a second tab) never got the prompt,
        so the round waited forever. The pending prompt is now replayed on connect."""
        old = _connect(game)
        _to_runner_prompt(old, [])

        sock = _connect(game)
        try:
            old.close()  # the new socket keeps the round alive: it is not stopped
            prompt = _recv_until(sock, _is("reaction_prompt"), [])
            assert prompt["trigger"]["source_creature_id"] == RUNNER
            _send_reaction(sock, "opportunity_attack", **prompt["options"][0]["params"])

            log: list[Msg] = []
            turn = _until_next_turn(sock, log)
            events = _events(log)
            oas = [e for e in events if e["event_type"] == "opportunity_attack"]
            assert [(e["data"]["attacker_id"], e["data"]["target_id"]) for e in oas] == [(game.pid, RUNNER)]
            assert _hp(game, RUNNER) == RUNNER_HP - _hits_on(events, RUNNER)
            _assert_consistent_with_rest(game, turn)
        finally:
            sock.close()

    def test_reconnect_after_eviction_restores_consistent_state(self, game: WsGame) -> None:
        """Regression: the autosave of a session with a styleless Fighter could not be
        restored, so reconnecting after the grace window found no session."""
        sock = _connect(game)
        _to_runner_prompt(sock, [])
        sock.close()

        deadline = time.monotonic() + 15
        while game.sid in {s["session_id"] for s in requests.get(f"{game.api}/sessions", timeout=10).json()}:
            assert time.monotonic() < deadline, "session was never evicted after the last player left"
            time.sleep(0.2)

        sock = _connect(game)  # restores the session from its autosave
        try:
            first = ws_recv(sock)
            assert first["type"] != "error", first
            log: list[Msg] = [first]
            turn = first if first["type"] == "turn" else _until_next_turn(sock, log)
            events = _events(log)

            assert turn["mode"] == "combat"
            assert _cells_apart(_pos(turn, RUNNER), PREY_CELL) == 1
            assert _hp(game, PREY) == PREY_HP - _hits_on(events, PREY)
            assert _hp(game, RUNNER) == RUNNER_HP - _hits_on(events, RUNNER)
            _assert_consistent_with_rest(game, turn)
        finally:
            sock.close()
