# Task: World layer isolation & event propagation unit tests

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 5 — Test Gaps

## Description

World (182 LOC) has zero dedicated unit tests. The "layers depend down" invariant is enforced by `_make_query_fn` and `_make_emit_fn` but never explicitly tested. Event propagation, advance_time tick gating, and save/load round-trip also lack coverage.

No code changes — only new test file `tests/unit/test_world.py`.

## Tests First

### Layer isolation — query direction enforcement

Use 3 stub layers (geography index 0, politics index 1, entities index 2) that implement the Layer ABC with minimal stubs.

- Entities (index 2) queries geography (index 0) → succeeds, returns answer
- Entities (index 2) queries politics (index 1) → succeeds (lower index)
- Entities (index 2) queries itself → raises `LayerError`
- Geography (index 0) queries entities (index 2) → raises `LayerError` (upward query)
- Politics (index 1) queries entities (index 2) → raises `LayerError` (upward query)
- Query to non-existent layer name → raises `LayerError`

### Layer isolation — emit source validation

- Layer emits event with matching source_layer → event propagated
- Layer emits event with mismatched source_layer → raises `LayerError`

### Event propagation

- Layer A emits event during tick → event delivered to layers B and C via handle_event, but NOT back to layer A
- Verify propagation order: events go to all other layers

### advance_time — tick interval gating

- Layer with tick_interval=0 → ticked on every advance_time call
- Layer with tick_interval=100 seconds → NOT ticked when only 50 seconds have passed
- Layer with tick_interval=100 seconds → ticked when 100+ seconds have passed
- After tick, last_tick_time updated → next advance of 50s doesn't re-tick

### save/load round-trip

- Create World with 2 stub layers, advance time, save → load into fresh World with same layers → time matches, last_tick_times match, layer get_state/load_state called correctly

### query_layer — public API

- query_layer("geography", query) → delegates to geography layer's query method
- query_layer("nonexistent", query) → raises ValueError

## Implementation

New file `tests/unit/test_world.py`. Create a minimal `StubLayer` implementing the `Layer` ABC (name, tick_interval, tick returns events, handle_event records calls, query returns configurable answers, get_state/load_state for save/load). All tests use `World([stub1, stub2, stub3])` directly.

## Acceptance Criteria

- [ ] Tests written and GREEN immediately (testing existing behavior)
- [ ] All new tests pass
- [ ] Existing tests still pass (`make check`)
- [ ] StubLayer is minimal — no unnecessary complexity
- [ ] Tests cover all 6 `LayerError` scenarios in `_make_query_fn`

## Status

`done`

## Developer Notes

Created `tests/unit/test_world.py` with 17 tests across 7 test classes. All GREEN immediately — testing existing behavior. StubLayer implements the full Layer ABC with tracking for tick calls, handled events, and load_state calls.

Test classes:
- **TestLayerIsolationQueryDirection** (6 tests): all 6 LayerError scenarios from `_make_query_fn`
- **TestLayerIsolationEmitValidation** (2 tests): matching/mismatched source_layer
- **TestEventPropagation** (2 tests): events reach all non-source layers
- **TestAdvanceTimeTickGating** (4 tests): interval=0, not elapsed, elapsed, re-tick prevention
- **TestSaveLoadRoundTrip** (1 test): full round-trip including last_tick_time restoration
- **TestQueryLayerPublicAPI** (2 tests): delegation and ValueError for missing layer

Pre-existing flaky test `test_sneak_attack_adds_extra_damage_with_ally_adjacent` fails intermittently due to dice randomness — unrelated to this task.
