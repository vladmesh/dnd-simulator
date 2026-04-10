# Task: Skip Dead Creatures in Round Loop

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 4 — Bug Fixes

## Description

After killing an NPC in combat, the event log shows 3x "Мёртвые существа не могут действовать" (Dead creatures cannot act). The messages are visible to the player and clutter the UI.

**Root cause:** In `round.py:run_combat_turn()`, the `while True` action loop at line 328 never checks if the creature is still alive. When creature A's turn is running and creature A moves, triggering an opportunity attack from the player that kills A, the loop continues calling `brain.choose_action()` for the now-dead creature. The brain returns IDLE (no nearby enemies for a dead creature), validation rejects with DEAD_ACTOR, `consecutive_failures` increments to 3, then breaks.

The outer round loop at line 539 checks `entity.is_alive` before starting a turn, but this doesn't help when a creature dies MID-TURN from a reaction (opportunity attack).

**Fix:** Add `if not creature.is_alive: break` at the top of the `while True` loop in `run_combat_turn()` (after line 328). This matches the pattern from commit 8df78cd which added a similar liveness check in the OA reactor loop.

## Tests First

1. **Unit test: creature killed by OA mid-turn produces no dead-creature actions** — Set up a combat where creature A moves, triggering OA from creature B. The OA kills A. Verify that after the OA resolves, no further actions are attempted for A (no DEAD_ACTOR validation errors in the round's action log).

2. **Unit test: combat ends cleanly after OA kill** — Same setup. Verify combat ends properly (COMBAT_ENDED event emitted) without dead-creature warnings.

## Implementation

In `round.py:run_combat_turn()`, add a liveness check at the top of the action loop:

```python
while True:
    if not creature.is_alive:
        break
    awareness = self._build_combat_awareness(creature, ctx, time, query_fn)
    ...
```

Also check `run_peaceful_turn()` for the same pattern — if a creature can die during peaceful turn processing, add the same guard.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] No "dead creature" warnings in event log after killing an NPC
- [ ] Combat ends cleanly after OA kill

## Status

`pending`
