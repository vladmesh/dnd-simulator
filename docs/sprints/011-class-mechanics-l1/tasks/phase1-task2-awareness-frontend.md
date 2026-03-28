# Task: Awareness Pipeline + Frontend Simplification

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 1 — BattleMap Reachability

## Description

Thread the backend-computed reachable set through the awareness pipeline to the frontend. The frontend stops computing reachability itself and becomes a pure renderer of backend data.

Add `reachable` field to `CombatAwareness`. `AwarenessBuilder.build_combat_awareness()` calls `compute_reachable()` for the active creature and includes the result. Session serialization sends it as `list[[x, y]]`. Frontend `BattleMap.tsx` removes `computeReachable()` and uses the backend set directly.

Wall rendering (`buildBlockedEdges`, `getCellWalls`) stays on the frontend — that's a CSS rendering concern, not movement logic.

## Tests First

1. **CombatAwareness includes reachable** — build combat awareness for a creature with 30ft speed on a map with walls. Verify `awareness.reachable` contains expected positions and does NOT contain positions blocked by walls or beyond budget.

2. **Reachable empty when not creature's turn** — awareness built for a creature that is NOT the current turn-taker has empty reachable (no point computing movement for creatures that can't move).

3. **Serialization round-trip** — `_awareness_to_dict(awareness)` includes `reachable` as list of `[x, y]` pairs. Verify format matches what the frontend expects.

4. **Frontend renders backend reachable** — E2E: in combat, player's turn, verify that highlighted cells match the backend-computed reachable set (no independent BFS on frontend).

## Implementation

- `core/awareness.py`: add `reachable: frozenset[tuple[int, int]]` to `CombatAwareness` (default `frozenset()`)

- `layers/entities/awareness_builder.py`: in `build_combat_awareness()`:
  - Import `compute_reachable` from `rules/movement.py`
  - If creature is current turn-taker AND has movement budget > 0: compute reachable
  - Convert `dict[Position, list[Position]]` keys to `frozenset[tuple[int, int]]`
  - Pass to `CombatAwareness(reachable=...)`

- `service/session.py`: `_awareness_to_dict()` — serialize `reachable` as `[[x, y], ...]` list

- `frontend/src/types/game.ts`: add `reachable?: number[][]` to `CombatAwareness` type

- `frontend/src/components/game/BattleMap.tsx`:
  - Remove `computeReachable()` function (~65 lines)
  - Remove `isEdgeBlocked()` function (only used by computeReachable)
  - Build reachable `Set<string>` from `awareness.reachable` (convert `[x, y]` to `"col,row"` keys)
  - Keep `buildBlockedEdges()` and `getCellWalls()` — needed for wall border rendering

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Frontend `computeReachable()` removed — no movement BFS on client
- [ ] Frontend highlights exactly the cells backend computed
- [ ] Wall borders still render correctly
- [ ] Non-turn creatures get empty reachable set
- [ ] Awareness dict serialization includes reachable in correct format

## Status

`pending`
