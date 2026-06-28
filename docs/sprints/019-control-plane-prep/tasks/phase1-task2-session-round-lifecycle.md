# Task: Session round lifecycle tests (start/stop idempotency + brain wiring)

**Date:** 2026-06-28
**Sprint:** 019-control-plane-prep
**Phase:** 1 — Session lifecycle test net

## Description

`GameSession.start_round` / `stop_round` own the Round thread lifecycle and the
PlayerBrain wiring. Zero coverage today. Phase 2's peel and the next sprint's
spectator-listener both lean on this staying correct, so pin it now.

Behaviour to characterize:

- `start_round(player)` creates a Round, wires a fresh `PlayerBrain` onto
  `player.brain`, starts a background thread, and returns the Round. The loop blocks
  on the player's turn (PlayerBrain waits on its queue), so the thread stays alive
  without racing to completion.
- `start_round` is **idempotent**: a second call while the thread is alive returns the
  same Round instance and does not start a second thread.
- After `start_round`, `submit_player_action` reaches the brain (no `RuntimeError`).
- `stop_round` stops the Round, clears `_round` / `_player_brain` / `_round_thread`,
  and joins the thread (it actually dies). Calling `stop_round` when no round is
  running is safe (no-op, no raise).

## Tests First

Extend `tests/unit/test_session_lifecycle.py`. Build a real session with a player:

```
svc = GameService(store=MagicMock(spec=SaveStore))
session = svc.start_game("sword_vale")
player = svc.create_player(session.session_id, {...minimal fighter...})
```

(reuse the player-creation shape from `test_game_service_player.py` /
`test_session_round_state.py` so the fixture stays consistent.)

- `start_round`: assert it returns a `Round`, `player.brain` is a `PlayerBrain`,
  and `session._round_thread.is_alive()`.
- Idempotency: capture `r1 = start_round(player)`, then `r2 = start_round(player)`;
  assert `r1 is r2` and the thread object is unchanged (no second thread spawned).
- `submit_player_action` after start does not raise.
- `stop_round`: after it, `session._round is None`, `_player_brain is None`,
  `_round_thread is None`, and the prior thread is no longer alive
  (`thread.join` already happened inside `stop_round`).
- `stop_round` on a never-started session does not raise.

Determinism: PlayerBrain blocks on its queue, so the loop will not advance past the
player's first turn — no sleeps needed. Always `stop_round` in a `finally` (or fixture
teardown) so a failing assertion never leaks a live thread.

## Implementation

Test-only. No product code changes expected. If the loop proves racy to observe,
gate assertions on state that `start_round` sets synchronously before returning
(`_round`, `_round_thread`) rather than on thread-internal progress.

## Acceptance Criteria

- [ ] Tests cover start (return + brain wired + thread alive), idempotency (same Round, no 2nd thread), submit-after-start, stop (state cleared + thread joined), stop-when-idle
- [ ] Tests GREEN on first run (characterization)
- [ ] No leaked threads — every started round is stopped in teardown
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Test-only, no product code, as planned. Extended `tests/unit/test_session_lifecycle.py`
with 5 round-lifecycle tests (16 total in the file now), all GREEN on first run.

Approach:
- A `session_with_player` fixture builds a real `sword_vale` session + fighter
  (`GameService(store=MagicMock(spec=SaveStore))` — start_game/create_player never touch
  the store) and always calls `stop_round` in teardown, so no test can leak a live thread.
- `start_round`: returns a `Round`, wires a `PlayerBrain` onto `player.brain`,
  `_round_thread.is_alive()` (loop parks on the player's blocking `queue.get`).
- Idempotency: `r1 is r2`, `_round_thread` unchanged on a second call.
- `submit_player_action(END_TURN)` after start reaches the live brain without raising.
- `stop_round`: clears `_round` / `_player_brain` / `_round_thread` and the captured
  thread is dead after the in-method `join`.
- `stop_round` on a never-started session is a safe no-op.

Determinism confirmed: PlayerBrain blocks on its queue so the loop never races to
completion; ran the file 5× back-to-back with no flakes and no leaked threads. `make
check` fully green (ruff + mypy 146 files clean, 2263 backend tests, 238 frontend).
