# Task: Spectator WS endpoint

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 3 — Spectator-listener + disconnect-debounce

## Description

Expose the task-1 spectator primitive over WebSocket so a non-player client can subscribe to a live session read-only. Reuse the existing `/api/ws/{session_id}` endpoint with a `spectate=true` query param rather than a new path, so the session validation, origin check, and rate-limit scaffolding are shared and the frontend client only appends a param.

When `spectate=true`:

- No `player_id` is required and the "no player in session" guard is skipped. The branch happens after `ws.accept()` + session validation, before player resolution / `start_round`, so the existing player path stays untouched.
- Register a `WsEventListener` as a **spectator** (`session.add_spectator`), not a player listener. Do **not** call `start_round` — a spectator never drives the round.
- Replay `session.get_last_turn_msg()` on connect (same as the player path) so a spectator joining mid-session gets current state immediately.
- The receive loop stays (to detect disconnect), but `action` / `reaction` messages are rejected with an error (`{"type": "error", "message": _("Spectators cannot submit actions")}`) instead of being forwarded. The rate limiter still applies.
- `finally` calls `session.remove_spectator(listener)` (run on a worker thread, like the player path). A spectator leaving never evicts the session.

Projection-only: no role check on who may spectate. The frontend decides who opens a spectator socket (task 4). Hard access enforcement waits for the M2M/DB sprint.

## Tests First

Integration, real server, in `tests/integration/test_websocket.py` (reuse the function-scoped `ws_arena` fixture):

- **Spectator receives the live event stream.** Open a player WS to an arena session and a second WS with `?spectate=true` to the same session. Drive one player action on the player socket; the spectator socket receives the resulting `action_result` / `turn` / `round_result` events (the same player's-eye payloads). The spectator never sent an action to get them.
- **Spectator join replays last turn.** With a session already running (player connected, first turn emitted), a freshly-connected spectator receives a `turn` (or the cached last-turn) message on connect without sending anything.
- **Spectator cannot submit.** Send an `action` message on the spectator socket; the response is an `error` ("Spectators cannot submit actions") and no game state changes (the player socket sees no resulting `action_result` from the spectator's attempt).
- **Spectator disconnect does not evict.** Connect player + spectator, then close the spectator socket. The session stays live (the player socket keeps receiving events; a subsequent `GET /api/master/sessions` still lists the session). Pairs with task 2's player-empty semantics — only the player leaving arms the grace timer.
- **No player_id needed.** A `?spectate=true` connect to a valid session with no `player_id` query param succeeds (does not close with 4004 no_player).

## Implementation

- `adapters/api/routes_ws.py::websocket_game`: add `spectate: bool = False` (FastAPI parses `?spectate=true`). After session validation and `await ws.accept()`:
  - If `spectate`: build `WsEventListener`, replay last turn, `await asyncio.to_thread(session.add_spectator, listener)` (or call directly — it's cheap and lock-guarded; match the player path's threading only where it joins). Enter a receive loop that rate-limits and rejects `action`/`reaction` with an error, ignores/errors unknown types. On disconnect, `finally: await asyncio.to_thread(session.remove_spectator, listener)`. `return` before the player block.
  - Else: the existing player path, unchanged.
- Factor the shared receive-loop scaffolding (rate limiter, JSON parse, disconnect handling) only if it stays readable; a small duplicated spectator loop is acceptable given the divergent message handling. Prefer clarity over premature extraction.
- The spectator `WsEventListener` is the same class — it is already pure-send/read-only.

Gotchas:
- Keep the origin check and `ws.accept()` shared and ahead of the branch.
- `add_spectator`/`remove_spectator` don't join threads, so they need not run on a worker thread, but keeping `remove_spectator` symmetric with the player path's `to_thread` is harmless.
- Make sure an action sent by a spectator never reaches `submit_player_action` (it would raise "Round not running" or, worse, mutate state if a round is live). Reject before dispatch.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `?spectate=true` registers a spectator, replays last turn, never calls `start_round`
- [ ] Spectator receives the live event broadcast read-only
- [ ] Spectator `action`/`reaction` messages are rejected; no state change
- [ ] Spectator disconnect does not evict the session
- [ ] Player path (`/api/ws/{session_id}` without `spectate`) behaves exactly as before

## Status

`done`

## Developer Notes

Implemented as planned. `websocket_game` got a `spectate: bool = False` param; FastAPI parses `?spectate=true`. The branch fires after session validation + `ws.accept()`, before player resolution / `start_round`, so the player path is byte-for-byte unchanged.

Factored the read-only loop into a module-level `_run_spectator(ws, session, session_id)` rather than inlining — the divergent message handling (reject `action`/`reaction`, no dispatch) reads cleaner as its own function and keeps `websocket_game` short. It replays `get_last_turn_msg()`, calls `add_spectator`, runs a rate-limited receive loop that rejects submissions, and `finally: to_thread(remove_spectator)` (symmetric with the player path, though `remove_spectator` never joins the round thread).

Tests (5, in `test_websocket.py::TestSpectator`, function-scoped `ws_arena`): added a `_spectate_connect` helper.
- `test_no_player_id_needed` — connecting without `player_id` stays open (no 4004); after a player joins, the spectator receives the broadcast (proves no `start_round` from the spectator, and registration works without a player).
- `test_join_replays_last_turn` — player drives the round to its turn (caches `_last_turn_msg`), then a fresh spectator gets the replay on connect without sending.
- `test_receives_event_stream` — player `end_turn` broadcasts to the spectator read-only.
- `test_cannot_submit` — spectator `attack` → `error` "Spectators cannot submit actions" (rejected before dispatch).
- `test_disconnect_does_not_evict` — close spectator → session still listed in `GET /api/master/sessions` AND the player socket keeps advancing (the strong signal: eviction autosaves+pops, so the list alone can't discriminate; the live round can).

`make check` green (backend 2303, frontend 256). `make test-integration` 166 passed (161 + 5 new). No old tests modified.
