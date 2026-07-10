# Task: Wait and sleep intent lifecycle

**Date:** 2026-07-11
**Sprint:** 022-intents-travel
**Phase:** 2 — Anchors, wait and sleep intents

## Description

Move WAIT, SHORT_REST, and LONG_REST from ad hoc dormancy fields to the timed intent lifecycle. Starting an action records the intent and duration; reaching its wake point completes it exactly once and returns an eligible anchor to play. Rest benefits must be applied at successful completion, not granted up front before elapsed time or save/load.

Cover the real session path so wait/sleep remains correct across save, load, reconnect, and websocket turn delivery. Keep the legacy `WAIT + travel_to` branch isolated for removal in Phase 3; it must not create a wait intent or share the new completion path.

## Tests First

- WAIT creates a wait intent for the requested duration, yields the turn, and clears the intent when its timer completes.
- SHORT_REST and LONG_REST create sleep intents with one-hour and eight-hour wake points; resources, healing, and other completion effects are applied once at wake, not when sleep begins.
- Saving during wait or sleep and loading the session preserves the remaining intent; reconnect resumes from the saved game time and completes it once.
- Through the websocket action path, a player waiting beside a rule NPC receives the next playable turn after a fast jump to the wake time, with no intermediate NPC-turn flood.
- The existing `WAIT + travel_to` compatibility path still reports invalid destinations and does not leave a timed intent behind.

## Implementation

Make the wait/rest handlers start typed intents only. Add a focused completion operation used by activation at the wake boundary; centralize rest rewards there so repeated activation cannot apply them twice. Update handler tests and add a session/websocket regression test for `test-gap-ws-fastforward`.

Retain the current action names and UI contract in Phase 2. Do not add `ActionType.TRAVEL`, route progress, general interruptions, or Brain gate/decide; those belong to later phases.

Likely files: `rules/handlers/movement.py`, `rules/handlers/rest.py`, the intent model/completion helper, action and rest tests, session lifecycle tests, and websocket integration tests.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] WAIT, SHORT_REST, and LONG_REST use the persisted intent lifecycle.
- [ ] Rest effects happen once, after elapsed game time.
- [ ] Save/load/reconnect preserves an in-progress timed intent.
- [ ] The websocket wait-with-NPC regression reaches the next player turn via fast-forward.
- [ ] Travel compatibility remains isolated for Phase 3 removal.

## Status

`pending`
