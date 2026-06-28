"""Movement rules — D&D 5e diagonal distance and grid movement.

Pure functions: takes positions in, returns positions/distances out.
Uses DMG optional diagonal rule: first diagonal = 5 ft, second = 10 ft, alternating.
"""

from __future__ import annotations

import heapq
from itertools import count

from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.i18n import _

# Compass direction vectors (dx, dy).  North = +y.
_DIRECTIONS: dict[str, tuple[int, int]] = {
    "north": (0, 1),
    "south": (0, -1),
    "east": (1, 0),
    "west": (-1, 0),
    "northeast": (1, 1),
    "northwest": (-1, 1),
    "southeast": (1, -1),
    "southwest": (-1, -1),
}


def grid_distance(a: Position, b: Position) -> int:
    """D&D 5e diagonal distance (DMG optional rule).

    Move along the longer axis, counting diagonals with alternating cost:
    first diagonal = 5 ft, second = 10 ft, third = 5 ft, etc.
    """
    dx = abs(a.x - b.x) // 5  # squares
    dy = abs(a.y - b.y) // 5
    straight = abs(dx - dy)
    diag = min(dx, dy)
    # Alternating diagonal cost: ceil(diag/2) diagonals cost 10, floor cost 5
    diag_cost = (diag // 2) * 15 + (diag % 2) * 5
    return straight * 5 + diag_cost


def direction_label(dx: int, dy: int) -> str:
    """Convert a (dx, dy) vector into a localized compass label."""
    if dx == 0 and dy == 0:
        return _("here")
    sx = 1 if dx > 0 else (-1 if dx < 0 else 0)
    sy = 1 if dy > 0 else (-1 if dy < 0 else 0)
    labels = {
        (0, 1): _("to the north"),
        (0, -1): _("to the south"),
        (1, 0): _("to the east"),
        (-1, 0): _("to the west"),
        (1, 1): _("to the northeast"),
        (-1, 1): _("to the northwest"),
        (1, -1): _("to the southeast"),
        (-1, -1): _("to the southwest"),
    }
    return labels.get((sx, sy), _("here"))


def calculate_direction(origin: Position, target: Position) -> str:
    """Return compass direction name from origin toward target (for a single step)."""
    dx = target.x - origin.x
    dy = target.y - origin.y
    if dx == 0 and dy == 0:
        return ""
    sx = 1 if dx > 0 else (-1 if dx < 0 else 0)
    sy = 1 if dy > 0 else (-1 if dy < 0 else 0)
    _reverse: dict[tuple[int, int], str] = {
        (0, 1): "north",
        (0, -1): "south",
        (1, 0): "east",
        (-1, 0): "west",
        (1, 1): "northeast",
        (-1, 1): "northwest",
        (1, -1): "southeast",
        (-1, -1): "southwest",
    }
    return _reverse.get((sx, sy), "")


def calculate_away_direction(origin: Position, target: Position) -> str:
    """Return compass direction name away from target (opposite of toward)."""
    dx = origin.x - target.x
    dy = origin.y - target.y
    if dx == 0 and dy == 0:
        return "north"  # arbitrary escape direction
    sx = 1 if dx > 0 else (-1 if dx < 0 else 0)
    sy = 1 if dy > 0 else (-1 if dy < 0 else 0)
    _reverse: dict[tuple[int, int], str] = {
        (0, 1): "north",
        (0, -1): "south",
        (1, 0): "east",
        (-1, 0): "west",
        (1, 1): "northeast",
        (-1, 1): "northwest",
        (1, -1): "southeast",
        (-1, -1): "southwest",
    }
    return _reverse.get((sx, sy), "north")


def move_direction(origin: Position, direction: str, speed: int, battle_map: BattleMap, mover_id: str = "") -> Position:
    """Move from *origin* in a compass direction, up to *speed* feet."""
    vec = _DIRECTIONS.get(direction.lower())
    if vec is None:
        return origin
    far_target = Position(origin.x + vec[0] * speed * 2, origin.y + vec[1] * speed * 2)
    return _step_toward(origin, far_target, speed, battle_map, mover_id)


def compute_reachable(
    start: Position, budget: int, battle_map: BattleMap, mover_id: str
) -> dict[Position, list[Position]]:
    """Compute all cells reachable within a movement budget using Dijkstra.

    Uses D&D 5e diagonal cost: first diagonal = 5 ft, second = 10 ft, alternating.
    Respects walls and occupied cells.

    Returns {position: path_from_start} for every reachable position (including start).
    """
    occupied = {pos for eid, pos in battle_map.positions.items() if eid != mover_id}

    # result: position → path (list of positions from start inclusive)
    result: dict[Position, list[Position]] = {start: [start]}
    best_cost: dict[Position, int] = {start: 0}

    # Priority queue: (cost, tiebreaker, position, diag_count, path)
    counter = count()
    heap: list[tuple[int, int, Position, int, list[Position]]] = [(0, next(counter), start, 0, [start])]

    _steps = ((-5, 0), (5, 0), (0, -5), (0, 5), (-5, -5), (-5, 5), (5, -5), (5, 5))

    while heap:
        cost, _, cur, diag_count, path = heapq.heappop(heap)

        # Skip if we already found a cheaper route to this cell
        if cost > best_cost.get(cur, budget + 1):
            continue

        for dx, dy in _steps:
            nx, ny = cur.x + dx, cur.y + dy
            if nx < 0 or nx > battle_map.width or ny < 0 or ny > battle_map.height:
                continue
            neighbor = Position(nx, ny)
            if battle_map.is_step_blocked(cur, neighbor):
                continue
            if neighbor in occupied:
                continue

            is_diag = dx != 0 and dy != 0
            if is_diag:
                step_cost = 10 if diag_count % 2 == 1 else 5
                new_diag = diag_count + 1
            else:
                step_cost = 5
                new_diag = diag_count

            new_cost = cost + step_cost
            if new_cost > budget:
                continue
            if new_cost < best_cost.get(neighbor, budget + 1):
                best_cost[neighbor] = new_cost
                new_path = [*path, neighbor]
                result[neighbor] = new_path
                heapq.heappush(heap, (new_cost, next(counter), neighbor, new_diag, new_path))

    return result


def find_path(start: Position, goal: Position, battle_map: BattleMap, mover_id: str) -> list[Position]:
    """Cost-aware pathfinding from start to goal on the battle map grid.

    Returns a list of Positions from start to goal (inclusive), or [] if unreachable.
    Delegates to compute_reachable with a budget large enough to cover the entire map.
    """
    if start == goal:
        return [start]
    # Budget: worst case is traversing the entire map diagonally
    max_budget = (battle_map.width + battle_map.height) * 2
    reachable = compute_reachable(start, max_budget, battle_map, mover_id)
    return reachable.get(goal, [])


def step_cost(current: Position, next_pos: Position, diag_count: int) -> tuple[int, int]:
    """Calculate movement cost for a single step using D&D 5e diagonal rules.

    Returns (cost_in_feet, new_diag_count).
    """
    dx = abs(next_pos.x - current.x)
    dy = abs(next_pos.y - current.y)
    is_diag = dx > 0 and dy > 0

    if is_diag:
        cost = 10 if diag_count % 2 == 1 else 5
        return cost, diag_count + 1
    return 5, diag_count


def _step_toward(origin: Position, target: Position, speed: int, battle_map: BattleMap, mover_id: str = "") -> Position:
    """Step one square at a time toward target, tracking diagonal cost."""
    cur = origin
    spent = 0
    diag_count = 0

    # Cells occupied by other entities (enemies block movement in D&D 5e)
    occupied = {pos for eid, pos in battle_map.positions.items() if eid != mover_id}

    while spent < speed:
        dx = target.x - cur.x
        dy = target.y - cur.y
        if dx == 0 and dy == 0:
            break

        # Determine step direction (one square = 5 ft)
        sx = 5 if dx > 0 else (-5 if dx < 0 else 0)
        sy = 5 if dy > 0 else (-5 if dy < 0 else 0)

        is_diag = sx != 0 and sy != 0
        if is_diag:
            cost = 10 if diag_count % 2 == 1 else 5
            diag_count += 1
        else:
            cost = 5

        if spent + cost > speed:
            break

        nx = cur.x + sx
        ny = cur.y + sy
        # Clamp to map bounds
        nx = max(0, min(nx, battle_map.width))
        ny = max(0, min(ny, battle_map.height))
        new_pos = Position(nx, ny)
        if new_pos == cur:
            break  # stuck at boundary
        if battle_map.is_step_blocked(cur, new_pos):
            break  # wall in the way
        if new_pos in occupied:
            break  # cell occupied by another entity
        cur = new_pos
        spent += cost

    return cur
