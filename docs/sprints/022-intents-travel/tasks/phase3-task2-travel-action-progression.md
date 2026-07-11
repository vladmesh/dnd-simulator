# Task: Travel action and leg progression

**Date:** 2026-07-11
**Sprint:** 022-intents-travel
**Phase:** 3 — Travel as an intent

## Description

Replace the `WAIT + travel_to` compatibility branch with `ActionType.TRAVEL`. Starting travel resolves a route, records a travel intent, and leaves the creature at its origin until the first leg's game-time boundary. Each boundary moves the creature to exactly the next graph node and schedules the following leg; the final boundary clears the intent and returns an eligible anchor to play.

Route progression must use the same activation and fast-forward lifecycle as timed wait/sleep. It must never call `World.advance_time()` inside the action handler and must not teleport directly to the final destination.

## Tests First

- A creature starting a three-edge journey remains at the origin immediately after the action, then appears at each intermediate node only after that leg's travel time has elapsed.
- With no other awake anchor, the round loop fast-forwards one leg at a time and returns control after final arrival; with another awake anchor, normal rounds continue while the traveler remains dormant between boundaries.
- Saving after an intermediate arrival and loading the session continues along the stored remaining route and arrives once, without skipping or replaying a leg.
- Two traveling creatures whose routes share an intermediate node can occupy that node at the same game time without either being teleported to its destination.
- Unknown and unreachable destinations fail without changing location or leaving an intent; WAIT no longer accepts `travel_to`.

## Implementation

Add the action definition, dispatcher registration, provider exposure, and a travel handler that validates the destination and starts the first leg. Generalize the entities wake-boundary query and intent completion path so the next travel-leg arrival participates in `Round._fast_forward`. At a leg boundary, update `location_id`, then either schedule the next boundary through the graph's existing distance-to-travel-time contract or complete the intent.

Keep built-in interruption rules out of this task and Phase 3. Phase 4 will define what combat, bodily events, or scene entry do to an in-progress journey.

Likely files: `core/action.py`, `core/action_defs.py`, `service/action_dispatcher.py`, `rules/handlers/movement.py`, `layers/entities/intent_completion.py`, `layers/entities/activation_manager.py`, `layers/entities/layer.py`, `round.py`, and handler/round/session tests.

## Acceptance Criteria

- [x] Tests written and RED (before implementation)
- [x] Implementation makes tests GREEN
- [x] Existing tests still pass (`make check`)
- [x] `TRAVEL` is a peaceful action and `WAIT` has no travel parameter or teleport branch.
- [x] Location changes occur only at graph-edge time boundaries, one edge at a time.
- [x] Fast-forward, save/load, and concurrent travelers preserve route progress.
- [x] Invalid travel is atomic from the caller's perspective.

## Status

`done`

## Developer Notes

`ActionType.TRAVEL` now resolves and stores the route without moving the actor or advancing world time. Activation advances every elapsed leg boundary, schedules the next one from the persisted boundary, and clears the intent only on final arrival; the round loop passes the world graph into activation and treats travel arrivals as fast-forward wake points. Legacy `WAIT + travel_to` behavior and schema were removed. Product tests cover intermediate nodes, invalid atomic starts, multi-leg fast-forward, two travelers sharing a node, and save/load continuation.
