"""Combat state — tracks initiative order, round progression, and battle map."""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from dnd_simulator.i18n import _


@dataclass(frozen=True)
class Position:
    """A point on the battle grid, in feet (multiples of 5)."""

    x: int
    y: int


@dataclass(frozen=True)
class Wall:
    """Axis-aligned wall segment on the battle grid.

    Walls sit on grid edges — between cells, not on cells.
    Must be horizontal (y1 == y2) or vertical (x1 == x2).
    A vertical wall at x=W blocks east/west movement across x=W.
    A horizontal wall at y=W blocks north/south movement across y=W.
    """

    x1: int
    y1: int
    x2: int
    y2: int


@dataclass
class BattleMap:
    """2D combat grid for a single fight.

    Coordinates are in feet.  Width/height define the arena bounds.
    Each entity participating in combat has a position on this map.
    Walls block movement between adjacent cells.
    """

    width: int  # feet
    height: int  # feet
    positions: dict[str, Position] = field(default_factory=dict)
    walls: list[Wall] = field(default_factory=list)
    _blocked_edges: set[frozenset[Position]] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Cache inner walls for serialization; bounds enforced by find_path / _step_toward."""
        self._inner_walls: list[Wall] = list(self.walls)

    def set_position(self, entity_id: str, pos: Position) -> None:
        """Place or move an entity on the map."""
        if pos.x < 0 or pos.x > self.width or pos.y < 0 or pos.y > self.height:
            raise ValueError(
                f"Position ({pos.x}, {pos.y}) out of bounds for {entity_id} on {self.width}x{self.height} map"
            )
        self.positions[entity_id] = pos

    def remove(self, entity_id: str) -> None:
        """Remove an entity from the map."""
        self.positions.pop(entity_id, None)

    def get_position(self, entity_id: str) -> Position | None:
        """Get an entity's position, or None if not on the map."""
        return self.positions.get(entity_id)

    def is_step_blocked(self, from_pos: Position, to_pos: Position) -> bool:
        """Check if a single 5-ft step between adjacent cells is blocked by a wall.

        For diagonal steps: there are two L-shaped paths through the corner.
        The diagonal is blocked only if BOTH paths are fully blocked
        (i.e., you can't reach the destination via either intermediate square).
        """
        if not self.walls:
            return False
        edges = self._get_blocked_edges()
        dx = to_pos.x - from_pos.x
        dy = to_pos.y - from_pos.y
        is_diag = dx != 0 and dy != 0
        if is_diag:
            # Path 1: go horizontal first, then vertical
            mid_h = Position(to_pos.x, from_pos.y)
            path_h_ok = frozenset({from_pos, mid_h}) not in edges and frozenset({mid_h, to_pos}) not in edges
            # Path 2: go vertical first, then horizontal
            mid_v = Position(from_pos.x, to_pos.y)
            path_v_ok = frozenset({from_pos, mid_v}) not in edges and frozenset({mid_v, to_pos}) not in edges
            # Blocked only if neither path is fully open
            return not path_h_ok and not path_v_ok
        return frozenset({from_pos, to_pos}) in edges

    def _get_blocked_edges(self) -> set[frozenset[Position]]:
        """Lazy-build and cache the set of blocked edges from walls."""
        if self._blocked_edges is not None:
            return self._blocked_edges
        edges: set[frozenset[Position]] = set()
        for wall in self.walls:
            if wall.x1 == wall.x2:
                # Vertical wall at x=W, from y_min to y_max
                wx = wall.x1
                y_min = min(wall.y1, wall.y2)
                y_max = max(wall.y1, wall.y2)
                for y in range(y_min, y_max, 5):
                    # Blocks crossing from (wx-5, y) to (wx, y)
                    left = Position(wx - 5, y)
                    right = Position(wx, y)
                    edges.add(frozenset({left, right}))
            elif wall.y1 == wall.y2:
                # Horizontal wall at y=W, from x_min to x_max
                wy = wall.y1
                x_min = min(wall.x1, wall.x2)
                x_max = max(wall.x1, wall.x2)
                for x in range(x_min, x_max, 5):
                    # Blocks crossing from (x, wy-5) to (x, wy)
                    below = Position(x, wy - 5)
                    above = Position(x, wy)
                    edges.add(frozenset({below, above}))
        self._blocked_edges = edges
        return edges

    def place_randomly(
        self,
        entity_ids: list[str],
        *,
        min_spacing: int = 10,
        rng: random.Random | None = None,
    ) -> None:
        """Scatter entities on random grid-aligned positions.

        Tries to keep at least *min_spacing* feet between entities.
        Falls back to any free cell if spacing can't be satisfied.
        """
        r = rng or random.Random()
        # All valid 5-ft-aligned positions (exclude perimeter — walls block movement there)
        all_cells = [Position(x, y) for x in range(5, self.width, 5) for y in range(5, self.height, 5)]
        r.shuffle(all_cells)

        placed: list[Position] = list(self.positions.values())
        for eid in entity_ids:
            best: Position | None = None
            # First pass: find a cell far enough from all placed entities
            for cell in all_cells:
                if all(_chebyshev_ft(cell, p) >= min_spacing for p in placed):
                    best = cell
                    break
            # Fallback: any cell not already occupied
            if best is None:
                occupied = set(placed)
                for cell in all_cells:
                    if cell not in occupied:
                        best = cell
                        break
            if best is None:
                best = Position(0, 0)
            self.positions[eid] = best
            placed.append(best)

    def describe_walls(self) -> list[str]:
        """Human-readable wall descriptions for awareness prompts."""
        descriptions: list[str] = [_("Arena bounded by walls: {w}x{h} ft").format(w=self.width, h=self.height)]
        # Only describe inner walls (not perimeter)
        for wall in self._inner_walls:
            if wall.x1 == wall.x2:
                descriptions.append(
                    _("vertical wall x={x} from y={y1} to y={y2}").format(
                        x=wall.x1, y1=min(wall.y1, wall.y2), y2=max(wall.y1, wall.y2)
                    )
                )
            elif wall.y1 == wall.y2:
                descriptions.append(
                    _("horizontal wall y={y} from x={x1} to x={x2}").format(
                        y=wall.y1, x1=min(wall.x1, wall.x2), x2=max(wall.x1, wall.x2)
                    )
                )
        return descriptions

    def render_ascii(self, observer_id: str | None = None) -> str:
        """Render an ASCII top-down view of the battle map.

        Each cell is 5 ft.  Legend:
        - ``@`` = observer (observer_id)
        - ``1``-``9`` = other entities (keyed in legend below the map)
        - ``#`` = wall segment between cells
        - ``.`` = empty cell
        """
        cols = self.width // 5 + 1
        rows = self.height // 5 + 1

        # Build entity lookup: grid (col, row) → entity_id
        pos_lookup: dict[tuple[int, int], str] = {}
        for eid, pos in self.positions.items():
            col = pos.x // 5
            row = pos.y // 5
            pos_lookup[(col, row)] = eid

        # Assign glyphs: observer = @, others numbered 1-9
        glyph_map: dict[str, str] = {}
        legend: list[str] = []
        counter = 1
        for eid in self.positions:
            if eid == observer_id:
                glyph_map[eid] = "@"
            else:
                g = str(counter) if counter <= 9 else "+"
                glyph_map[eid] = g
                legend.append(f"  {g} = {eid}")
                counter += 1

        # Build blocked-edge set for wall rendering (inner walls only, skip perimeter)
        inner_edges: set[frozenset[Position]] = set()
        for wall in self._inner_walls:
            if wall.x1 == wall.x2:
                wx = wall.x1
                y_min, y_max = min(wall.y1, wall.y2), max(wall.y1, wall.y2)
                for y in range(y_min, y_max, 5):
                    inner_edges.add(frozenset({Position(wx - 5, y), Position(wx, y)}))
            elif wall.y1 == wall.y2:
                wy = wall.y1
                x_min, x_max = min(wall.x1, wall.x2), max(wall.x1, wall.x2)
                for x in range(x_min, x_max, 5):
                    inner_edges.add(frozenset({Position(x, wy - 5), Position(x, wy)}))
        edges = inner_edges

        lines: list[str] = []
        # Render top-down: row 0 = top (max y), going down
        for row in range(rows - 1, -1, -1):
            cell_line = ""
            for col in range(cols):
                cell_eid = pos_lookup.get((col, row))
                cell_line += glyph_map[cell_eid] if cell_eid is not None else "."
                # Vertical wall between (col,row) and (col+1,row)?
                if col < cols - 1:
                    left = Position(col * 5, row * 5)
                    right = Position((col + 1) * 5, row * 5)
                    cell_line += "|" if frozenset({left, right}) in edges else " "
            lines.append(cell_line)
            # Horizontal wall between rows
            if row > 0:
                wall_line = ""
                for col in range(cols):
                    above = Position(col * 5, row * 5)
                    below = Position(col * 5, (row - 1) * 5)
                    wall_line += "-" if frozenset({above, below}) in edges else " "
                    if col < cols - 1:
                        wall_line += " "
                lines.append(wall_line)

        result = "\n".join(lines)
        if legend:
            result += "\n" + "\n".join(legend)
        return result


def _chebyshev_ft(a: Position, b: Position) -> int:
    """Chebyshev (max of dx, dy) distance in feet — used for spacing only."""
    return max(abs(a.x - b.x), abs(a.y - b.y))


@dataclass
class CombatState:
    """Active combat in a region.

    Tracks turn order (by initiative), round counter, and
    rounds-without-attack for automatic combat exit.
    """

    location_id: str
    turn_order: list[str] = field(default_factory=list)  # entity IDs in initiative order
    round_number: int = 1
    rounds_without_attack: int = 0
    battle_map: BattleMap = field(default_factory=lambda: BattleMap(width=60, height=60))
    sides: dict[int, set[str]] = field(default_factory=dict)  # side index → entity IDs
    entity_to_side: dict[str, int] = field(default_factory=dict)  # entity ID → side index
