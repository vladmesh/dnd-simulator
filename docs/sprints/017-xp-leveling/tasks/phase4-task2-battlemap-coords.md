# Task: Battle map coordinates vs combat_position mismatch

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 4 — E2E follow-up bug sweep

## Symptom

In the phase 3 E2E, the player was created with `combat_position: [5, 5]` (and the two NPCs at `[6, 5]` / `[4, 5]`), but the rendered battle map placed the player marker `@` at `data-testid="cell-11-7"`, with the two NPCs not visible on the map at all (yet adjacency was correct: action picker showed `Attack xp_dummy(5ft)`).

This means at least one of the following is broken:
- The YAML `combat_position` is interpreted by a different coord system than the renderer reads.
- The renderer flips axes, offsets origin, or uses a different units (feet vs cells, 0-based vs 1-based).
- NPCs are placed but not rendered if outside the player's visible range / FoV / culling logic.

Distance computation appears to use one consistent system (5 ft adjacency reported correctly), so the bug is most likely in the **render pipeline**, not the rules layer.

## Investigation scope

Trace the path from YAML → backend state → WS payload → frontend store → grid render. Document each transform in Developer Notes.

Specifically:
1. **YAML parse**: `src/dnd_simulator/content_loader/creatures.py::_to_npc` line `combat_position=tuple(model.combat_position)` — what's the convention here? Is `[x, y]` documented anywhere? Convention should be a comment-pinned invariant.
2. **Backend placement**: `src/dnd_simulator/layers/entities/combat_manager.py::start_combat` line `battle_map.set_position(c.id, Position(c.combat_position[0], c.combat_position[1]))`. `Position(x, y)` — but is it x=col/y=row, or x=col/y=cell-index-from-top? Check `BattleMap` class definition.
3. **WS serialization**: How `battle_map.positions` lands in the `turn` event payload. Look in `src/dnd_simulator/adapters/api/` and serializers.
4. **Frontend render**: Where `data-testid="cell-{col}-{row}"` is generated and how positions are mapped onto cells. Likely `frontend/src/components/game/BattleMap.tsx` or similar.

Identify the **single** transform that breaks the invariant. Don't compensate downstream — fix the layer that's wrong.

## Possible directions

- Make the YAML field explicitly typed (`combat_position: {x: int, y: int}` instead of `[5, 5]`) so there's no list-order ambiguity. Backwards-compat shim NOT acceptable per project rule (fail fast); existing content needs migration.
- Document the canonical coord system in `core/battle_map.py` (or wherever `Position` lives) with a doctring + ASCII diagram, and add a unit test that pins the invariant: YAML `[5, 5]` → render cell `[5, 5]`.
- If NPCs aren't rendered due to FoV/visibility, that's a separate bug; capture as a sub-finding (do not silently expand scope, ask user).

## Tests First

1. `test_battle_map_position_round_trip` — load a creature with `combat_position: [3, 4]` from YAML, start combat, assert `battle_map.positions[creature_id]` equals `Position(3, 4)` (or whatever the invariant is — pick one and commit).
2. Frontend: `BattleMap.test.tsx` — given a `turn` payload with `entity at (3, 4)`, assert the entity is rendered in `data-testid="cell-3-4"`.
3. Phase 3 E2E re-run: player at `[5,5]` → cell `cell-5-5` (run after fix).

## Implementation

- One canonical convention. Pick **(x, y) where x = column index from left (0-based), y = row index from top (0-based)** unless the grid math everywhere already implies something else — if so, document that and use it consistently.
- Update YAML / Pydantic schema doc.
- Update render component if it was the offender.
- Add the invariant-pinning unit test mentioned above.

## Acceptance Criteria

- [ ] Developer Notes show the trace of where the offset/flip happens, with file:line refs
- [ ] One canonical coord convention documented in `core/battle_map.py` (or wherever `Position` is defined)
- [ ] YAML `[5, 5]` round-trips to render cell `[5, 5]` in both unit tests and live E2E
- [ ] All existing battle map / movement / pathfinding tests still pass
- [ ] `make check` green

## Status

`pending`
