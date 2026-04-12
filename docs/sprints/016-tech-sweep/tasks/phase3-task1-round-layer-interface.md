# Task: Decouple round.py from EntitiesLayer via Layer interface

**Date:** 2026-04-12
**Sprint:** 016-tech-sweep
**Phase:** 3 — Core Boundaries

## Description

`round.py:32` directly imports `EntitiesLayer` and calls 18 of its methods (awareness building, combat state, activation, active-creature lookup). The game-loop orchestrator reaches into a specific layer by concrete type, bypassing the `Layer` ABC and the `query_layer` / query-fn abstractions.

The `Layer.query()` method exists but isn't rich enough — `round.py` needs `get_active_creatures`, `get_combat_locations`, `get_combat`, `build_awareness`, `update_activation`, `reset_combat_turn_state`, `log_round_start`, `end_combat_round`, `get_nearest_wake_time`, `get_merchants_at`, `get_perceived_events`, `build_peaceful_awareness`, `get_entity`.

Design: introduce a dedicated protocol / interface `CreatureHost` (or extend Layer with combat/activation semantics in a separate protocol) that `EntitiesLayer` implements. `round.py` obtains it via `world.get_creature_host()` or equivalent lookup that returns `Layer` typed as the protocol. The concrete `EntitiesLayer` import disappears from `round.py`.

Alternative considered: expand `Layer.query()` with enum-keyed queries for all 18 needs. Rejected — it bloats the query enum and loses method signatures. Protocol is cleaner.

## Tests First

1. **Integration test: a full combat round still drives turns correctly after refactor** — set up a 2-creature combat (one player, one NPC), run `Round.run_loop()` for one round, assert initiative advances, turn budget resets, combat state updates. Exercises most of the 18 EntitiesLayer methods through the new interface.

2. **Integration test: activation fast-forward still works** — world with a sleeping NPC (wake_at in future) and no active creatures, call `Round.run_loop()`, assert time advances to wake time and NPC becomes active. Exercises `get_nearest_wake_time` + `update_activation` through the interface.

3. **Architecture test (grep-based assertion):** after refactor, `grep "from.*layers" src/dnd_simulator/round.py` returns empty. Write this as a pytest that reads the file and asserts no `from dnd_simulator.layers` line exists.

## Implementation

1. Define `CreatureHost` protocol in `core/creature_host.py` (or `core/layer.py`) with the 13–18 methods `round.py` actually uses. Use `typing.Protocol` with `@runtime_checkable` optional.
2. Add `World.creature_host` property that returns the registered `EntitiesLayer` typed as `CreatureHost`. Raises a clear `RuntimeError` if no host registered (fail-fast).
3. Replace `round.py:32` import with `from dnd_simulator.core.creature_host import CreatureHost`. Replace every `entities_layer` access with `self.world.creature_host`.
4. `EntitiesLayer` itself doesn't need to change — Python's structural typing makes it a `CreatureHost` automatically. Optionally add explicit inheritance for clarity.
5. Verify no new cycles: `core/` cannot import from `layers/` — `CreatureHost` is just a Protocol, defines no concrete types from layers.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `grep -rn "from dnd_simulator.layers" src/dnd_simulator/round.py` → empty
- [ ] `grep -rn "EntitiesLayer" src/dnd_simulator/round.py` → empty
- [ ] `CreatureHost` protocol documents every method with a one-line docstring

## Status

`pending`
