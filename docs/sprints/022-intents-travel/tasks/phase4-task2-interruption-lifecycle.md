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

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Save/load before and after interruption restores one internally consistent state.
- [ ] Reconnect resumes travel or the interrupted player turn exactly once.
- [ ] Snapshot and interruption remain atomic under the existing session mutation gate.

## Status

`pending`
