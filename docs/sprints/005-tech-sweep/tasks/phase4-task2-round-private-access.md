# Task: Eliminate Round's private EntitiesLayer access

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 4 — Architecture Violations + Type Safety

## Description

`round.py` accesses `self._entities._entities` (a private dict) in two places:

1. `_build_merchants()` (line ~137) — iterates all entities to find merchants at the same location.
2. `_fast_forward()` (line ~498) — iterates all entities to find the nearest `wake_at_seconds`.

These bypass EntitiesLayer's public API. Add proper public methods to EntitiesLayer and call those instead.

Scope: only the 2 private-dict accesses. The ~15 public method calls (`get_combat`, `build_awareness`, etc.) stay as-is — Round is an orchestrator above layers, not a peer.

## Tests First

- `test_get_merchants_at_location`: EntitiesLayer with 3 NPCs (1 merchant at location A, 1 merchant at location B, 1 non-merchant at A) — returns only the merchant at location A with correct items/gold.
- `test_get_nearest_wake_time`: EntitiesLayer with 3 creatures (wake_at 100, wake_at 50, None) — returns 50. With all None — returns None.

## Implementation

1. Add `get_merchants_at(location_id, hour) -> list[Npc]` to EntitiesLayer — filters by `is_merchant`, `active`, `is_alive`, `current_location`.
2. Add `get_nearest_wake_time() -> int | None` to EntitiesLayer — scans for minimum `wake_at_seconds`.
3. Update `round.py:_build_merchants()` to call `self._entities.get_merchants_at(...)` and build `MerchantInfo` from the result.
4. Update `round.py:_fast_forward()` to call `self._entities.get_nearest_wake_time()`.
5. Remove the `from dnd_simulator.layers.entities.models import Npc` import in `_build_merchants` (no longer needed in round.py).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `round.py` has zero references to `._entities` (private dict access)
- [ ] `make typecheck` passes

## Status

`pending`
