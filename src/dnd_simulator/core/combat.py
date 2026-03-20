"""Combat state — tracks initiative order, round progression, and battle map."""

from __future__ import annotations

import random
from dataclasses import dataclass, field


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
        """Add perimeter walls so the arena boundary blocks movement properly."""
        w, h = self.width, self.height
        self._inner_wall_count = len(self.walls)
        perimeter = [
            Wall(0, 0, 0, h),  # west
            Wall(w, 0, w, h),  # east
            Wall(0, 0, w, 0),  # south
            Wall(0, h, w, h),  # north
        ]
        self.walls = list(self.walls) + perimeter

    def set_position(self, entity_id: str, pos: Position) -> None:
        """Place or move an entity on the map, clamping to bounds."""
        clamped = Position(
            x=max(0, min(pos.x, self.width)),
            y=max(0, min(pos.y, self.height)),
        )
        self.positions[entity_id] = clamped

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
        # All valid 5-ft-aligned positions
        all_cells = [Position(x, y) for x in range(0, self.width + 1, 5) for y in range(0, self.height + 1, 5)]
        r.shuffle(all_cells)

        placed: list[Position] = []
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
        descriptions: list[str] = [f"Арена ограничена стенами: {self.width}x{self.height} ft"]
        # Only describe inner walls (not perimeter)
        for wall in self.walls[: self._inner_wall_count]:
            if wall.x1 == wall.x2:
                descriptions.append(
                    f"вертикальная стена x={wall.x1} от y={min(wall.y1, wall.y2)} до y={max(wall.y1, wall.y2)}"
                )
            elif wall.y1 == wall.y2:
                descriptions.append(
                    f"горизонтальная стена y={wall.y1} от x={min(wall.x1, wall.x2)} до x={max(wall.x1, wall.x2)}"
                )
        return descriptions


def _chebyshev_ft(a: Position, b: Position) -> int:
    """Chebyshev (max of dx, dy) distance in feet — used for spacing only."""
    return max(abs(a.x - b.x), abs(a.y - b.y))


@dataclass
class CombatState:
    """Active combat in a region.

    Tracks turn order (by initiative), round counter, and
    rounds-without-attack for automatic combat exit.
    """

    region_id: str
    turn_order: list[str] = field(default_factory=list)  # entity IDs in initiative order
    round_number: int = 1
    rounds_without_attack: int = 0
    battle_map: BattleMap = field(default_factory=lambda: BattleMap(width=60, height=60))
