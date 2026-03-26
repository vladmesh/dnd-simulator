# Task: Full Layer Round-Trip Integration Tests

**Date:** 2026-03-26
**Sprint:** 007-world-session
**Phase:** 1 — Save/Load Completeness

## Description

Comprehensive save → load → assert-identical tests covering all layers through `World.save()`/`World.load()`. The existing tests in `test_npc_layer.py` cover individual fields but there's no test that exercises the full pipeline: build a world with realistic state, save it, load it, and verify every mutable field matches.

This is the "safety net" task — it validates that tasks 1 and 2 actually work end-to-end through the World serialization path, and catches any gaps we missed.

## Tests First

In `tests/unit/test_save_roundtrip.py`:

1. **Full world round-trip** — Build a World with all 5 layers populated. Set non-default state on each: geography (advance time so weather/day-night differ from defaults), entities (player with spent resource pool, NPC with `ai_type="llm"` and non-empty memory, creature with conditions and inventory, active combat with positioned entities). Save → load → assert every mutable field matches on every entity.

2. **Player with full state** — PlayerCharacter with gold, inventory (weapon + potion), conditions (poisoned, 3 rounds remaining), spent resource pool, specific location. Save through World → load → all fields identical.

3. **Combat + resource pool combined** — Fighter in active combat, Second Wind already used. Save → load → fighter still in combat at same map position, Second Wind still spent. This tests the interaction between task 1 and task 2.

## Implementation

These are pure test files — no production code changes. Build helpers to construct realistic test worlds if needed. Use `World.save()` and `World.load()` directly (not layer-level get_state/load_state).

## Acceptance Criteria

- [ ] Tests pass (GREEN — they validate tasks 1 and 2)
- [ ] Existing tests still pass (`make check`)
- [ ] Tests cover: time, entity locations, conditions, inventory, resource pools, ai_type, combat state, NPC memory
- [ ] Tests use World.save()/load() — full pipeline, not layer-level shortcuts

## Status

`pending`
