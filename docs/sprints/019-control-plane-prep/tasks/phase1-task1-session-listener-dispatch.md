# Task: Session listener dispatch + abstract-move resolution tests

**Date:** 2026-06-28
**Sprint:** 019-control-plane-prep
**Phase:** 1 — Session lifecycle test net

## Description

`service/session.py` has zero dedicated coverage on its listener-dispatch and
input-resolution surface — the exact code the next sprint's spectator-listener
extends and Phase 2's GameService peel could break silently. The serialization
helpers are covered (`test_session_round_state.py`, `test_session_awareness.py`),
the lifecycle is not.

This task pins the **synchronous** (no background thread) behaviour of `GameSession`:

- `add_listener` / `remove_listener` — registration, and the empty-listeners path:
  removing the last listener with no round running fires `_on_empty`; removing a
  listener that was never registered is a silent no-op (suppressed `ValueError`).
- `_fire` — a listener whose handler raises does not block the other listeners
  (error swallowed + logged), and every other listener still receives the call.
- `submit_player_action` / `submit_player_reaction` — raise `RuntimeError` when no
  round is running (brain is `None`).
- `resolve_abstract_move` — `toward`/`away_from` params resolve to a concrete
  `MOVE` with `direction` + `ft`; returns the action unchanged when there is no
  combat at the location, no battle-map position for the mover, or no position
  for the target.

These are characterization tests: they describe current behaviour and should pass
on first run. A failure means a real bug, not a missing feature.

## Tests First

New file `tests/unit/test_session_lifecycle.py` (or extend if a better home exists).
Build a `GameSession` directly (it's a dataclass: `GameSession(session_id=..., world=...)`)
or via `GameService(store=MagicMock(spec=SaveStore)).start_game("sword_vale")` for a
real world — whichever keeps the test honest without a running round.

Listener dispatch:
- Define a tiny `RecordingListener` implementing `SessionEventListener` (records
  which methods fired) and a `RaisingListener` (raises in `on_turn`).
- Adding two listeners then `_fire("on_turn", {...})` calls both; the recording one
  still fires even when registered after a raising one.
- With a session that has one listener and `_round is None`, set `session._on_empty`
  to a recorder; `remove_listener(last)` invokes `_on_empty(session)` exactly once and
  does **not** raise. `remove_listener` of an unregistered listener is a no-op.

Submit-without-round:
- Fresh session (no `start_round`): `submit_player_action(Action(MOVE, ...))` raises
  `RuntimeError`; same for `submit_player_reaction`.

`resolve_abstract_move` (call the module function directly with a stub `CreatureHost`):
- Stub host where `get_combat(loc)` returns an object with a `battle_map` exposing
  `get_position(id)`. Mover at (2,2), target at (5,2), `params={"toward": "tgt", "ft": 10}`
  → returns `Action(MOVE, {"direction": <toward>, "ft": 10})` (assert direction points
  toward target via `rules/movement.calculate_direction`).
- `away_from` → direction is the away vector.
- `get_combat` returns `None` → action returned unchanged (identity).
- Mover/target has no battle-map position → action returned unchanged.

## Implementation

Test-only. No product code changes. If a test is awkward to write, prefer fixing the
test harness over loosening the assertion — the behaviour under test already exists.
Mock only the boundary (`CreatureHost`, listeners); let `GameSession` / the real world
run.

## Acceptance Criteria

- [ ] Tests written, exercising listener dispatch, empty-listener `_on_empty`, submit-raises, and all `resolve_abstract_move` branches
- [ ] Tests GREEN on first run (characterization — existing behaviour)
- [ ] No background round thread started in these tests (deterministic, no sleeps)
- [ ] Existing tests still pass (`make check`)

## Status

`done`

## Developer Notes

Test-only, as planned. New `tests/unit/test_session_lifecycle.py` with 11 tests, all
GREEN on first run (characterization confirmed):

- Listener dispatch: `_fire` calls every listener; a `RaisingListener` registered
  before a `RecordingListener` does not block it (error swallowed + logged).
- Empty-listeners: removing the last listener with no round running fires `_on_empty`
  once; removing an unregistered listener is a silent no-op (suppressed `ValueError`,
  existing listener untouched, `_on_empty` not fired since list is non-empty).
- Submit guards: `submit_player_action` / `submit_player_reaction` raise `RuntimeError`
  when `_player_brain is None`.
- `resolve_abstract_move`: called as a module function with a stub `CreatureHost`
  (`get_combat → combat.battle_map.get_position`). `toward`/`away_from` resolve to a
  concrete `MOVE` with `direction` (asserted via `rules/movement.calculate_direction`
  / `calculate_away_direction`) + `ft`; identity return on no-combat, no-mover-position,
  no-target-position.

No product code changed. Listener/submit tests use a `MagicMock(spec=World)` (no real
world needed — guards trip before any world access). No background round thread started,
so fully deterministic with no sleeps.

`make check`: backend fully green (ruff + ruff-format clean, mypy 146 files clean, 2258
tests pass). One frontend vitest flake (`SchemaForm.test.tsx`) failed under the full
parallel run but passes 22/22 in isolation — pre-existing flakiness (cf. commit 5830ba4),
unrelated to this backend-only change.
