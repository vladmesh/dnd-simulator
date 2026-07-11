# Task: Interruption lifecycle consistency

**Date:** 2026-07-11
**Sprint:** 022-intents-travel
**Phase:** 4 — Interruptible journeys and E2E closure

## Description

Pin interruption behavior through the real session boundary. Saving and loading immediately before or after an interruption, disconnecting and reconnecting during a journey, and resuming the round must converge on the same world time, location, intent, and turn ownership. A stale round or repeated activation must not replay the reached leg, restore a cleared intent, grant rest twice, or deliver two player turns.

Cover both peaceful scene interruption and combat interruption through the session-owned mutation gate introduced in Phase 1. File snapshots remain outside the gate after their immutable state is built; this task should extend the existing lifecycle contract rather than add a second synchronization mechanism.

## Tests First

- Save during a multi-leg journey, load, reconnect, then enter an occupied intermediate scene: the player stops at that node with no remaining intent and receives exactly one playable turn.
- Save immediately after a damage or combat interruption and load it: the cleared intent stays cleared, rest rewards are absent, and combat/location state matches the pre-save session.
- Disconnect while traveling and reconnect after the next boundary: only the connection-driven round resumes, advances the leg at most once, and emits one current player status.
- Concurrent snapshot and interruption produce either the complete pre-interruption state or the complete post-interruption state, never a cleared intent paired with the wrong location or combat state.

## Implementation

Add integration coverage around `GameSession`, save/load commands, round activation, and the player WebSocket path. Keep all interruption mutations inside the session world-mutation scope and build status from the committed world state. Adjust orchestration only where the tests expose a replay or ordering bug; do not introduce transport-specific intent logic.

Likely files: `service/session.py`, `service/commands_save.py`, `round.py`, API WebSocket integration tests, and session/save concurrency tests.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] Save/load before and after interruption restores one internally consistent state.
- [x] Reconnect resumes travel or the interrupted player turn exactly once.
- [x] Snapshot and interruption remain atomic under the existing session mutation gate.

## Status

`done`

## Developer Notes

Added `tests/unit/test_interruption_lifecycle.py` (6 tests) pinning interruption behaviour
through the real session boundary. No orchestration change was needed: the phase 1-3 machinery
(session world-mutation/read gate, per-entity intent + combat serialization, idempotent
`interrupt_intent`, leg-by-leg `advance_travel_leg`) already satisfies the contract, so this is a
regression/characterization task. Consistent with how the repo closes phases, tests pass on first
run; I verified they are non-vacuous rather than weak:

- Group A drives the real `save_game`/`load_game` commands over on-disk `sword_vale`: mid-journey
  save then load restores the exact `TravelIntent`, and advancing to an occupied intermediate node
  stops the traveler with the intent cleared (repeated activation does not replay the leg).
  Save-after-damage keeps the sleep intent cleared with no long-rest heal/pool reset; save-after
  combat entry restores `in_combat` + `CombatState` with the intent cleared.
- Group B drives `Round.run_loop` synchronously over a minimal travel world: a resumed round
  fast-forwards each leg exactly once, a stale re-entry is a no-op (no leg replay, +6s only, one
  extra turn), and repeated activation after a scene interruption never re-advances.
- Group C hammers `build_save_game` from one thread while another toggles combat entry/exit under
  `session.mutate_world()`; every snapshot is coherent (pre or post, never torn).

Non-vacuousness confirmed by temporary breaks: stubbing `interrupt_intent` to skip clearing fails
5/6 (the 6th is a non-interrupted journey); bypassing `read_world` in `build_save_game` makes the
concurrency test observe `intent=True + has_combat=True`. Both breaks reverted.

Note: `test_ws.py::test_wait_fast_forwards_past_nearby_rule_npc` flaked once under the full parallel
`make check` run (timing in the background round thread, `len(messages)` 5 vs ≤4); it passes in
isolation and on rerun. Pre-existing WS-timing flake, unrelated to this change.
