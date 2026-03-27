# Task: Interactive BattleMap — CSS Grid

**Date:** 2026-03-27
**Sprint:** 009-ui-layout
**Phase:** 5 — Combat Layout + Click-to-Move

## Description

Replace the ASCII `<pre>` battle map with an interactive CSS Grid. Each cell is a `<div>`, walls rendered as borders on cell edges, entities as glyphs/icons. This task adds the visual grid — click-to-move is task 3.

**Backend changes:**
- Add structured grid data to `CombatAwareness`: `battle_map_width`, `battle_map_height` (int, in feet), `battle_map_walls` (list of wall edge dicts for frontend border rendering)
- Keep `battle_map_ascii` for LLM prompts (no removal)

**Frontend changes:**
- Update `CombatAwareness` TS type: add `self_x`, `self_y`, `battle_map_width`, `battle_map_height`, `battle_map_walls`, and `x`/`y` on `CombatEntity`
- Rewrite `BattleMap.tsx`: CSS Grid with `grid-template-columns: repeat(cols, 1fr)`, one `<div>` per cell
- Cell rendering: empty = muted dot, player = `@` (highlighted), enemy = numbered (matching CombatPanel)
- Wall rendering: convert wall edge data to CSS `border-{top|right|bottom|left}` on adjacent cells
- Responsive sizing: grid fills the right column, cells are square (`aspect-square`)

**Wall edge format** (backend → frontend):
Each wall edge is `{x1, y1, x2, y2}` — a pair of adjacent cell coordinates (in feet). Frontend converts to: "cell at (x1,y1) gets border-right if wall is between it and cell to the east", etc.

## Tests First

**Backend (unit):**
- `CombatAwareness` includes `battle_map_width`, `battle_map_height`, `battle_map_walls` when combat is active
- `battle_map_walls` correctly lists inner wall edges (not perimeter — perimeter is implicit from grid bounds)
- Wall edges match the walls defined on the BattleMap

**Frontend (E2E):**
- Battle map renders as a grid (not `<pre>`) with correct dimensions
- Player position marked with `@` or distinct styling
- Enemy positions shown with numbers matching the enemies list
- Wall between two cells renders as a visible border on the grid
- Empty cells are visually distinct from entity cells

## Implementation

### Backend

1. Add fields to `CombatAwareness` in `core/awareness.py`:
   ```python
   battle_map_width: int = 0
   battle_map_height: int = 0
   battle_map_walls: list[dict[str, int]] = field(default_factory=list)
   ```

2. In `awareness_builder.py` `build_combat_awareness()`: populate from `combat.battle_map`:
   ```python
   battle_map_width=combat.battle_map.width,
   battle_map_height=combat.battle_map.height,
   battle_map_walls=[{"x1": w.x1, "y1": w.y1, "x2": w.x2, "y2": w.y2} for w in combat.battle_map._inner_walls],
   ```

### Frontend

3. Update `types/game.ts` — add missing fields to `CombatAwareness` and `CombatEntity`

4. Rewrite `BattleMap.tsx`:
   - Compute `cols = width / 5 + 1`, `rows = height / 5 + 1`
   - Build position lookup: `Map<"col,row", entityGlyph>`
   - Build wall-edge set from `battle_map_walls` → for each cell, determine which borders are walls
   - Render CSS Grid: `grid-template-columns: repeat(cols, minmax(0, 1fr))`
   - Each cell: `div` with conditional border classes, entity glyph if occupied
   - Coordinate system: backend y increases north, grid rows render top-down (row 0 = max y)

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Grid renders with correct dimensions matching battle map
- [ ] Player and enemy positions correct on grid
- [ ] Inner walls visible as borders between cells
- [ ] Grid fills right column, cells are roughly square
- [ ] `battle_map_ascii` still sent (LLM uses it)

## Status

`done`

## Developer Notes

**Backend:** Added `battle_map_width`, `battle_map_height`, `battle_map_walls` to `CombatAwareness` dataclass. Populated in `awareness_builder.py` from `combat.battle_map` — width/height directly, walls as list of `{x1, y1, x2, y2}` dicts from `_inner_walls`. `battle_map_ascii` preserved for LLM prompts.

**Frontend:** Updated TS types (`CombatEntity` gained `x`/`y`, `CombatAwareness` gained grid fields). Rewrote `BattleMap.tsx` from ASCII `<pre>` to CSS Grid. Wall segments converted to per-cell border classes using the same blocked-edge algorithm as the Python backend. Grid renders top-down (north at top), player as `@` in green, enemies numbered in red, empty cells as `·`. Walls render as yellow-600 borders between cells.

No old tests broken. 5 new backend tests for structured grid data.
