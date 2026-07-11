# Task: Travel route contract

**Date:** 2026-07-11
**Sprint:** 022-intents-travel
**Phase:** 3 — Travel as an intent

## Description

Introduce a first-class travel intent that records a creature's destination, ordered route, current leg, and next arrival boundary. Travel state must be strict, typed, and persisted for every creature kind alongside the existing wait and sleep intents. Add deterministic weighted routing over `LocationGraph`, using edge distance as cost, so a destination several edges away produces one concrete route rather than an immediate teleport.

Keep route calculation in the graph/core boundary and intent state in `core/`. This task establishes the contract and save/load behavior only. It does not start travel from an action or advance creatures through the route.

## Tests First

- On a branching graph, requesting a distant destination selects the reachable route with the shortest total distance and returns each intermediate location in order.
- An unreachable or unknown destination is rejected instead of producing a partial route; equal-cost alternatives resolve deterministically.
- A player, NPC, and generic creature saved during different legs of travel restore the same destination, remaining route, and next leg arrival boundary.
- The strict entity save schema rejects malformed travel state, including an empty remaining route, unknown fields, or a travel payload shaped like wait/sleep.

## Implementation

Extend the intent model to a typed union: keep the existing timed wait/sleep representation and add a focused travel representation with enough state to resume without recalculating a possibly changed route. Extend the strict Pydantic save union and entity serialization/restoration accordingly. Add shortest-path routing to `LocationGraph`; do not reuse battle-map pathfinding, which operates on combat grid cells and different costs.

Likely files: `core/intent.py`, `core/location.py`, `layers/entities/save_models.py`, `layers/entities/entity_serialization.py`, `layers/entities/layer.py`, graph tests, and entity serialization tests.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Multi-edge routes are selected by total edge distance with deterministic tie-breaking.
- [ ] Travel progress has one strict runtime and save representation for all creature kinds.
- [ ] A mid-route save restores the exact remaining journey without recomputing it.

## Status

`pending`
