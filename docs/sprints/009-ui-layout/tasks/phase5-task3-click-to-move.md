# Task: Click-to-Move

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 5 — Combat Layout + Click-to-Move

## Description

Click a cell on the battle map grid → character moves there, spending movement budget. Backend does BFS pathfinding; frontend shows reachable cells and sends `move_to(x, y)`. Remove the "Move toward/away" dropdown from ActionBar.

**Backend:**
- New `ActionType.MOVE_TO = "move_to"` in `core/action.py`
- New `ActionDef` for `MOVE_TO` with params `x: int, y: int` — `CostType.MOVEMENT`, `CombatMode.COMBAT_ONLY`
- New handler `handle_move_to()` in `rules/handlers/movement.py`: takes `(x, y)`, pathfinds via BFS in `rules/movement.py`, walks step-by-step spending budget, emits single `ENTITY_MOVE` event with final position
- New pure function `find_path(start, goal, battle_map, mover_id) -> list[Position]` in `rules/movement.py` — BFS respecting walls and occupied cells
- New pure function `walk_path(path, speed, battle_map, mover_id) -> tuple[Position, int]` — walk the path spending movement with diagonal cost, return (final_pos, feet_spent)
- Register `MOVE_TO` in action dispatcher
- `MOVE_TO` is NOT exposed to LLM tool schema — it's player-only. Add `player_only=True` flag to ActionDef or filter in tool schema builder.

**Frontend:**
- `BattleMap.tsx`: on cell click, send `move_to` action with `{x: col*5, y: row*5}`
- Movement range highlight: compute reachable cells client-side (BFS using grid dimensions, walls, occupied cells, remaining movement budget) and show them with a distinct background
- Hover on reachable cell: show path preview (optional, skip if complex)
- `ActionBar.tsx`: hide `DirectionalDropdown` for `move` action — movement is now via map click. Keep `move` in `available_actions` (RuleBrain/LLM still use it), but ActionBar skips rendering it
- Dash still shows in ActionBar (it adds movement budget, doesn't move itself). After dashing, reachable cells update

## Tests First

**Backend (unit):**
- `find_path((0,0), (15,10), empty_map)` returns a valid path of adjacent steps
- `find_path` respects walls: path goes around a wall, not through it
- `find_path` respects occupied cells: path goes around occupied cell
- `find_path` to unreachable cell returns empty list
- `walk_path` with 30ft budget on a 35ft path stops at 30ft mark
- `walk_path` correctly applies diagonal alternating cost (5/10/5/10...)
- `handle_move_to` with valid target: creature ends up at target position, movement budget deducted
- `handle_move_to` with unreachable target: returns error
- `handle_move_to` to occupied cell: returns error
- Existing `move` action (direction-based) still works (regression)

**Frontend (E2E):**
- Click reachable cell → character moves there, budget updates
- Click unreachable cell (beyond movement range) → nothing happens or error shown
- Click occupied cell → nothing happens
- Click cell blocked by wall → nothing happens
- After Dash, reachable area expands
- No "Move toward/away" dropdown in ActionBar during combat

## Implementation

### Backend

1. Add `MOVE_TO = "move_to"` to `ActionType` enum

2. Add `find_path()` to `rules/movement.py`:
   - BFS from start to goal on 5ft grid
   - Neighbors: 8 directions (N/S/E/W/NE/NW/SE/SW)
   - Skip: out of bounds, wall-blocked (`battle_map.is_step_blocked`), occupied by other entity
   - Return list of Positions from start to goal (inclusive)

3. Add `walk_path()` to `rules/movement.py`:
   - Walk the path step by step, tracking diagonal cost (alternating 5/10)
   - Stop when speed budget exhausted
   - Return (final_position, feet_spent)

4. Add `handle_move_to()` to `rules/handlers/movement.py`:
   - Extract `x`, `y` from params
   - Call `find_path(current_pos, Position(x, y), battle_map, mover_id)`
   - If no path → error
   - Call `walk_path(path, remaining_movement, battle_map, mover_id)`
   - Update battle map position
   - Emit `ENTITY_MOVE` event
   - Return result with feet spent

5. Register `ActionDef` for `MOVE_TO` in `core/action_defs.py`

6. Register handler in `service/action_dispatcher.py`

7. Filter `MOVE_TO` from LLM tool schemas (it's player-only)

### Frontend

8. Update `BattleMap.tsx`:
   - Add `onClick` handler on grid cells
   - On click: `sendAction("move_to", { x: col * 5, y: row * 5 })`
   - Only when `isMyTurn` and cell is in movement range
   - Compute reachable cells using BFS on the grid data (width, height, walls, occupied, remaining movement from budget)
   - Style reachable cells with a subtle highlight (e.g., `bg-blue-500/20`)
   - Style player cell distinctly, enemy cells distinctly

9. Update `ActionBar.tsx`:
   - In `renderAction`, skip `DirectionalDropdown` for `move` action — movement handled by map
   - Keep `move` in available_actions list (backend still needs it)
   - Dash button stays (adds budget, reachable cells update on next render)

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Click on reachable cell moves player there
- [ ] Movement budget correctly deducted (including diagonal alternating cost)
- [ ] Walls block pathfinding
- [ ] Occupied cells block pathfinding
- [ ] Reachable cells highlighted on the grid
- [ ] No "Move toward/away" dropdown in ActionBar
- [ ] Dash extends reachable range
- [ ] LLM/RuleBrain still use direction-based `move` (not affected)
- [ ] `move_to` not in LLM tool schema

## Status

`done`

## Developer Notes

Backend: Added `MOVE_TO` action type with BFS pathfinding (`find_path`) and budget-aware walking (`walk_path`) as pure functions in `rules/movement.py`. Handler manages movement budget directly (cost_type=FREE) since feet spent aren't known upfront. The handler accesses battle map via `ctx.combat_state`, does pathfinding, walks the path, updates position, and emits an ENTITY_MOVE log event. No new event types or combat_manager changes needed. LLM exclusion: `provider_managed=True` means MOVE_TO never appears in available_actions (no provider offers it), so LLM tool schemas never see it.

Frontend: BattleMap now computes reachable cells via client-side BFS matching D&D 5e diagonal cost rules. Reachable cells get `bg-blue-500/20` highlight and `cursor-pointer` on hover. Clicking sends `move_to` action with feet coordinates. `move` action hidden from ActionBar (added to ALWAYS_HIDDEN) — direction-based move still works for RuleBrain/LLM NPCs.
