# Task: Spectator-listener primitive in GameSession

**Date:** 2026-06-29
**Sprint:** 020-control-interfaces
**Phase:** 3 — Spectator-listener + disconnect-debounce

## Description

Today every `SessionEventListener` lives in one flat `GameSession._listeners` list, and the round lifecycle keys off that list being empty: when the last listener disconnects, `remove_listener` stops the round and fires `_on_empty` (autosave + evict). There is no way to watch a session without being the player who drives it.

Add a read-only **spectator** registration alongside the existing (player) listener:

- A spectator receives the full event broadcast (`on_turn`, `on_action_result`, `on_round_result`, `on_reaction`, `on_game_over`) exactly like a player listener does. `_fire` reaches both.
- A spectator does **not** drive the round (no `start_round` is triggered by spectators; that stays player-only at the call site) and does **not** keep the session alive. The "session empty" decision that triggers `stop_round` + `_on_empty` keys on **player** listeners only. A lone spectator with no player present is treated as empty.
- Adding/removing a spectator never fires `_on_empty` and never stops the round.
- Spectators see the player's-eye event stream that is already built in `start_round`'s closures (`_player_to_dict(player)`, `_build_round_state(player, …)`). No per-spectator/omniscient awareness in this phase. Privacy-per-viewer is the multiplayer sprint, out of scope here.

This is the cheap primitive the brainstorm calls out (control-interfaces.md §3): extracted once, used by DM observation, admin park, and future player-spectators. Projection-only, no role enforcement — anyone may register as a spectator (consistent with phase 1/2 decisions).

The WS endpoint that registers spectators is task 3; the grace-period deferral of the empty handler is task 2. This task is purely the `GameSession` model + unit tests.

## Tests First

Product-level, against `GameSession` directly with the existing `RecordingListener` double (no background round needed — `_fire`/`add`/`remove` are synchronous). In `tests/unit/test_session_lifecycle.py`:

- **Spectator receives the broadcast.** Register a player listener and a spectator. `_fire("on_turn", msg)` reaches both; `_fire("on_action_result", msg)` reaches both. A spectator registered after a player still gets subsequent events.
- **Spectator alone does not keep the session alive.** With only spectators registered (no player listener) and a wired `_on_empty`, the session is considered empty: a configured probe (the empty-check that task 2 will defer; here assert the synchronous predicate) reports empty. Concretely: `has_player_listeners()` (or equivalent) is `False` when only spectators are present.
- **Removing a spectator never fires `_on_empty`.** Register one player + one spectator, wire `_on_empty`. `remove_spectator(spectator)` does not call `_on_empty` and does not stop the round; the player listener still receives a later `_fire`.
- **Last player leaving with a spectator still present fires the empty path.** Register one player + one spectator, wire `_on_empty`. `remove_listener(player)` triggers the empty handler (the session is player-empty even though a spectator remains). The spectator is still in the broadcast set up to that point.
- **Existing player-listener behavior unchanged.** The current `TestListenerDispatch` / `TestEmptyListeners` cases still pass byte-for-byte (player path is the old `add_listener`/`remove_listener`).

## Implementation

- `service/session.py`:
  - Add `_spectators: list[SessionEventListener]` field (mirrors `_listeners`, lock-guarded).
  - `add_spectator(listener)` / `remove_spectator(listener)`: append/remove under `_lock`, log a count. Neither touches the round or `_on_empty`.
  - `_fire`: snapshot `self._listeners + self._spectators` under the lock, then dispatch outside the lock (keep the existing error-isolation try/except per listener).
  - Introduce a single source of truth for "is this session player-empty?" — e.g. `def has_player_listeners(self) -> bool: return bool(self._listeners)`. `remove_listener`'s empty check uses it. (Task 2 reuses this predicate for the deferred re-check.)
- Keep `add_listener`/`remove_listener` as the player path with their current semantics (still drive `stop_round` + `_on_empty` on empty). Only the internal empty test routes through the new predicate so task 2 has one place to hook.

Gotchas: `_fire` must broadcast to spectators too, but the empty/evict logic must ignore them. Don't let a raising spectator block player listeners (same `_fire` isolation already covers it). No change to `start_round` — spectators simply never call it.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Spectators receive the full event broadcast via `_fire`
- [ ] Spectator add/remove never stops the round and never fires `_on_empty`
- [ ] "Session empty" (round-stop + `_on_empty` trigger) keys on player listeners only; a lone spectator counts as empty
- [ ] No role enforcement added (projection-only)

## Status

`pending`
