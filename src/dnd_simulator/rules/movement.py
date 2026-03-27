"""Movement rules — D&D 5e diagonal distance and grid movement.

Pure functions: takes positions in, returns positions/distances out.
Uses DMG optional diagonal rule: first diagonal = 5 ft, second = 10 ft, alternating.
"""

from __future__ import annotations

from collections import deque

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


def find_path(start: Position, goal: Position, battle_map: BattleMap, mover_id: str) -> list[Position]:
    """BFS pathfinding from start to goal on the battle map grid.

    Returns a list of Positions from start to goal (inclusive), or [] if unreachable.
    Respects walls (is_step_blocked) and occupied cells (other entities).
    Steps are 5ft in all 8 directions.
    """
    if start == goal:
        return [start]

    occupied = {pos for eid, pos in battle_map.positions.items() if eid != mover_id}

    # BFS
    queue: deque[Position] = deque([start])
    came_from: dict[Position, Position | None] = {start: None}

    while queue:
        cur = queue.popleft()
        if cur == goal:
            # Reconstruct path
            path: list[Position] = []
            node: Position | None = goal
            while node is not None:
                path.append(node)
                node = came_from[node]
            path.reverse()
            return path

        for dx, dy in ((-5, 0), (5, 0), (0, -5), (0, 5), (-5, -5), (-5, 5), (5, -5), (5, 5)):
            nx, ny = cur.x + dx, cur.y + dy
            # Bounds check
            if nx < 0 or nx > battle_map.width or ny < 0 or ny > battle_map.height:
                continue
            neighbor = Position(nx, ny)
            if neighbor in came_from:
                continue
            if battle_map.is_step_blocked(cur, neighbor):
                continue
            if neighbor in occupied and neighbor != goal:
                continue
            # Goal occupied by another entity = unreachable
            if neighbor == goal and neighbor in occupied:
                continue
            came_from[neighbor] = cur
            queue.append(neighbor)

    return []  # unreachable


def walk_path(path: list[Position], speed: int) -> tuple[Position, int]:
    """Walk along a path spending movement budget with D&D 5e diagonal cost.

    Returns (final_position, feet_spent). Stops when speed budget is exhausted.
    """
    if not path:
        return Position(0, 0), 0
    if len(path) == 1:
        return path[0], 0

    cur = path[0]
    spent = 0
    diag_count = 0

    for next_pos in path[1:]:
        dx = abs(next_pos.x - cur.x)
        dy = abs(next_pos.y - cur.y)
        is_diag = dx > 0 and dy > 0

        if is_diag:
            cost = 10 if diag_count % 2 == 1 else 5
            diag_count += 1
        else:
            cost = 5

        if spent + cost > speed:
            break

        cur = next_pos
        spent += cost

    return cur, spent


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
