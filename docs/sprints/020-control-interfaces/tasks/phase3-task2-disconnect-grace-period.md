# Task: Disconnect grace-period (debounce evict)

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 3 — Spectator-listener + disconnect-debounce

## Description

Closes backlog `session-disconnect-debounce`. Today `remove_listener`, on the last player leaving, **immediately** calls `stop_round()` + `_on_empty` → `_on_session_empty` (autosave + pop from the registry). A fast disconnect+reconnect (React StrictMode double-mount, a network blip) therefore evicts a live session: the reconnected WS finds the session gone, `_try_restore_session` rebuilds it from the autosave, and progress made since the last autosave is lost (this is also the dev-only trigger that surfaces `player-xp-not-persisted`, fixed properly in phase 4).

Fix with a grace-period. When the session goes player-empty, do not stop+evict synchronously. Schedule a deferred re-check (default ~1.5s, configurable) on a `threading.Timer`. When it fires, re-check under the lock: if the session is still player-empty, then stop the round and fire `_on_empty`; otherwise no-op. A player reconnect inside the window (`add_listener`) cancels the pending timer, so `start_round`'s idempotent guard finds the round still alive — no thread churn, no evict, no restore.

A previously-tried-and-reverted `has_listeners()` re-check inside `_on_session_empty` is superseded: the re-check lives in `session.py` (where this phase's listener lifecycle lives), keyed on the player-listener predicate from task 1, and is gated behind the timer so it cannot keep a genuinely-abandoned session alive.

## Tests First

The timer is the awkward part — design a seam so unit tests never sleep. Add `GameSession._evict_grace_seconds: float` (default ~1.5) and factor the post-window logic into a method tests call directly. Then in `tests/unit/test_session_lifecycle.py`:

- **Emptying schedules, does not evict synchronously.** Register a player listener, wire `_on_empty`. `remove_listener(player)` does **not** call `_on_empty` immediately and does **not** stop the round synchronously; a pending evict timer exists.
- **Deferred check on a still-empty session evicts.** After the above, invoke the post-window method directly (e.g. `_run_evict_check()`): now `_on_empty` fires exactly once and the round is stopped.
- **Reconnect inside the window cancels the evict.** `remove_listener(player)` (timer pending) → `add_listener(player2)` → the pending timer is cancelled; invoking the post-window method now no-ops (`_on_empty` never fires) because the session is no longer player-empty.
- **A spectator present does not save an abandoned session.** Player + spectator registered; `remove_listener(player)` schedules; with only the spectator left, the post-window check still finds the session player-empty and fires `_on_empty` (spectators do not cancel the timer — only a player reconnect does).
- **Update the existing characterization test.** `test_removing_last_listener_fires_on_empty` currently asserts a *synchronous* `_on_empty`. Rewrite it to assert the new contract: removing the last player schedules a deferred check, and `_on_empty` fires only when that check runs while still empty.

Integration (`tests/integration/test_websocket.py`) — one targeted case, real timer:

- **Reconnect within the window keeps the same session.** Connect a player WS to an arena session, receive the first turn, capture the session id. Disconnect, reconnect well within the grace window, and assert the session was not evicted+restored (e.g. the in-game clock / combat state continued rather than resetting to a fresh-start snapshot). Keep the real window short enough to stay under the suite's per-test budget, or shorten `_evict_grace_seconds` for the test session via the service.

## Implementation

- `service/session.py`:
  - Field `_evict_grace_seconds: float` (default ~1.5; allow override) and `_evict_timer: threading.Timer | None`.
  - `remove_listener`: when the player-listener predicate (task 1) reports empty and a round is running, do **not** stop+`_on_empty` inline. Instead cancel any existing `_evict_timer`, create a new `threading.Timer(self._evict_grace_seconds, self._run_evict_check)`, start it (daemon), store it. Keep the unregistered-listener / not-empty branches as-is.
  - `_run_evict_check()`: acquire `_lock`, clear `_evict_timer`, re-check player-empty; if still empty → release lock, then `stop_round()` + (`_on_empty(self)` if set). If not empty → no-op. Mind lock ordering: `stop_round` joins the round thread, so don't hold `_lock` across it (mirror the existing `remove_listener` pattern that computes flags under the lock and acts after release).
  - `add_listener` (player path): cancel and clear any pending `_evict_timer` before appending (reconnect cancels evict).
  - `stop_round` already runs on a worker thread from the WS `finally`; keep that. The timer callback runs on its own Timer thread, so `_run_evict_check` calling `stop_round` (which joins the round thread) is safe — it is not the event-loop thread.
- `service/game_service.py::_on_session_empty` stays as-is (autosave + pop); it just runs later, via the timer, and only when still empty. Do not add a second re-check there.

Gotchas:
- Don't defer for an administrative `stop_round` path or for `delete_session` — those evict deliberately. Only the player-empty-on-disconnect path gets the grace timer.
- The arena WS fixture is already function-scoped (`test_websocket.py:32`), so the old module-scoped `game_over` accumulation is not a concern. Still, audit the existing reconnect tests (`test_reconnect_replays_last_turn`) — with grace, a quick reconnect now keeps the same session rather than triggering evict→restore. Adjust any test that implicitly relied on immediate eviction.
- Keep the timer daemon so it never blocks process exit.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`); `test_removing_last_listener_fires_on_empty` updated to the deferred contract
- [ ] Last player leaving schedules a deferred evict, not a synchronous one
- [ ] Player reconnect inside the window cancels the evict; session and round survive
- [ ] After the window with the session still player-empty, `_on_empty` fires exactly once (autosave + evict)
- [ ] A lingering spectator does not prevent eviction of an otherwise-abandoned session
- [ ] Integration: disconnect+reconnect within the window does not evict/restore

## Status

`done`

## Developer Notes

Implemented as planned: deferred the **whole** empty-handler (stop_round + `_on_empty`), not just the evict, so a reconnect inside the window finds the round still alive and `start_round` stays a true idempotent no-op (no thread churn, no combat-state reset).

- `session.py`: added `_evict_timer: threading.Timer | None` and `_evict_grace_seconds` (default `1.5`, overridable per-instance; module constant reads `DND_EVICT_GRACE_SECONDS`). `remove_listener` now arms `_schedule_evict_check()` instead of stopping synchronously when player-empty. `_run_evict_check` (Timer thread) re-verifies player-empty under the lock and only then stops + fires `_on_empty`. `add_listener` and `stop_round` both call `_cancel_evict_check()` — a reconnect or a deliberate stop cancels the pending deferral. `_on_session_empty` in `game_service.py` untouched (no second re-check there, per task).
- Lock discipline mirrors the existing pattern: compute flags under `_lock`, act (stop_round joins the round thread) after release. The timer runs on its own daemon thread, so joining there is safe. `_cancel_evict_check` is called only while holding the lock (non-reentrant).
- **Old-test contract changes (intentional, this task changes the contract):**
  - `TestEmptyListeners.test_removing_last_listener_fires_on_empty` → `..._schedules_deferred_evict`: now asserts a deferred timer is armed and `_on_empty` is *not* synchronous.
  - `TestSpectatorListener.test_last_player_leaving_with_spectator_present_fires_on_empty` (added in task 1, assumed synchronous) → `..._is_player_empty`: asserts the predicate + deferred arming; the firing path moved to the new `TestEvictGracePeriod`.
- New `TestEvictGracePeriod` (4 unit tests) sets `_evict_grace_seconds = 3600` so the real timer never fires mid-test, and drives `_run_evict_check()` directly for the firing/cancel paths — deterministic, no sleeps. New integration `test_quick_reconnect_keeps_session_live` exercises the real ~1.5s timer end-to-end (fast reconnect → player still gets a turn and the round accepts an action), tolerant like `test_end_turn`.
- `test_reconnect_replays_last_turn` (0.5s gap) still green: 0.5s < 1.5s window, so the session now survives via the cached-turn replay instead of evict→restore. `ws_arena` teardown `DELETE` leaves a daemon round thread parked + a pending timer that self-cleans within the window; daemon, so it never blocks exit.

Verified: 29 unit tests in `test_session_lifecycle.py` green; `make check` green (backend 2303, frontend 256); `make test-integration` green (161 passed, +1).
