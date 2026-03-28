# Task: Backend Reachability Engine

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 1 — BattleMap Reachability

## Description

Add `compute_reachable()` to `rules/movement.py` — a Dijkstra-based function that computes all cells reachable within a movement budget, respecting D&D 5e diagonal costs (5/10 alternation), walls, and occupied cells. Returns a map of `Position -> list[Position]` (destination → shortest path).

Refactor `find_path()` to become a thin wrapper over `compute_reachable()` — eliminating the separate BFS that doesn't account for diagonal costs (the root cause of the move-to-edge-cell bug).

Update `handle_move_to()` to use `compute_reachable()` directly: look up the target in the reachable map, walk the pre-computed path. This guarantees that any cell the frontend highlights as reachable is actually reachable with exactly the expected cost.

## Tests First

1. **Open field reachability** — creature at (15, 15) with 30ft budget on empty 60x60 map. Verify that cells at grid_distance exactly 30 are reachable, cells at 35 are not. Check a diagonal-heavy target (e.g. (30, 30) = 5 diag steps = 5+10+5+10+5 = 35ft → unreachable at 30ft budget).

2. **Wall-aware reachability** — vertical wall blocks direct east path. Cell directly east at 10ft is NOT reachable, but cell at same position via detour around wall IS reachable (if within budget). Verify path goes around the wall.

3. **Occupied cell blocking** — enemy at (20, 15). Verify (20, 15) is not in reachable set. Verify cells beyond the enemy are reachable via detour around the occupied cell.

4. **Edge-of-range bug fix** — the original bug: creature at (15, 15), budget 30ft. Target (30, 30) is 35ft via 3-diagonal path. Target (25, 30) should be exactly reachable at 30ft. Verify `compute_reachable` includes it AND the path cost equals exactly 30. Then verify `find_path` returns this same path (not a cheaper step-count path that costs more in feet).

5. **find_path wrapper** — `find_path(start, goal, bm, mover_id)` returns the same path as `compute_reachable(start, budget=999, bm, mover_id)[goal]` (with large budget, both should find optimal cost path).

6. **handle_move_to uses reachable** — creature with 30ft budget clicks edge cell. Verify position updates to target and budget decremented by exact path cost. No "stopped short" behavior.

## Implementation

- `rules/movement.py`: add `compute_reachable(start: Position, budget: int, battle_map: BattleMap, mover_id: str) -> dict[Position, list[Position]]`
  - Priority queue (heapq) with `(cost, counter, position, diag_count, path)`
  - `best_cost: dict[Position, int]` to skip worse paths
  - Diagonal cost: `10 if diag_count % 2 == 1 else 5`
  - Skip walls via `battle_map.is_step_blocked()`
  - Skip occupied cells (except start) via positions dict
  - Return `{pos: path}` for all reachable positions

- `rules/movement.py`: refactor `find_path(start, goal, bm, mover_id)` to call `compute_reachable(start, large_budget, bm, mover_id)` and return `result.get(goal, [])`. Or: add optional `goal` early-exit to `compute_reachable` for efficiency when only one target needed.

- `rules/handlers/movement.py`: `handle_move_to()` — call `compute_reachable(cur_pos, budget, bm, actor.id)`, look up target, walk the returned path (walk_path still needed to track actual feet spent for budget deduction, but path is guaranteed valid).

- `walk_path()` stays as-is — it's the "execute path" function, not the "find path" function. Its diagonal cost logic must match `compute_reachable` (both use same alternation).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `compute_reachable` uses Dijkstra with D&D 5e diagonal costs
- [ ] `find_path` delegates to `compute_reachable` (no separate BFS)
- [ ] Edge-of-range cells that frontend shows as reachable actually work in `handle_move_to`
- [ ] No new dependencies added

## Status

`pending`
