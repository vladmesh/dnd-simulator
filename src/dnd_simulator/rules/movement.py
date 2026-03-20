"""Movement rules — D&D 5e diagonal distance and grid movement.

Pure functions: takes positions in, returns positions/distances out.
Uses DMG optional diagonal rule: first diagonal = 5 ft, second = 10 ft, alternating.
"""

from __future__ import annotations

from dnd_simulator.core.combat import BattleMap, Position

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
    """Convert a (dx, dy) vector into a Russian compass label.

    Returns e.g. "на севере", "на юго-западе", "здесь".
    """
    if dx == 0 and dy == 0:
        return "здесь"
    ns = "север" if dy > 0 else ("юг" if dy < 0 else "")
    ew = "восток" if dx > 0 else ("запад" if dx < 0 else "")
    if ns and ew:
        return f"на {ns}о-{ew}е"
    if ns:
        return f"на {ns}е"
    return f"на {ew}е"


def move_toward(origin: Position, target: Position, speed: int, battle_map: BattleMap) -> Position:
    """Move from *origin* toward *target*, up to *speed* feet.

    Steps one 5-ft square at a time toward target, spending movement
    according to D&D 5e diagonal rules, clamped to map bounds.
    """
    return _step_toward(origin, target, speed, battle_map)


def move_away_from(origin: Position, target: Position, speed: int, battle_map: BattleMap) -> Position:
    """Move from *origin* directly away from *target*, up to *speed* feet."""
    # Mirror target through origin to get an "away" destination
    dx = origin.x - target.x
    dy = origin.y - target.y
    # If on top of each other, pick arbitrary direction
    if dx == 0 and dy == 0:
        away_target = Position(origin.x, origin.y + speed)
    else:
        # Scale to put away_target far beyond origin
        away_target = Position(origin.x + dx * 100, origin.y + dy * 100)
    return _step_toward(origin, away_target, speed, battle_map)


def move_direction(origin: Position, direction: str, speed: int, battle_map: BattleMap) -> Position:
    """Move from *origin* in a compass direction, up to *speed* feet."""
    vec = _DIRECTIONS.get(direction.lower())
    if vec is None:
        return origin
    far_target = Position(origin.x + vec[0] * speed * 2, origin.y + vec[1] * speed * 2)
    return _step_toward(origin, far_target, speed, battle_map)


def _step_toward(origin: Position, target: Position, speed: int, battle_map: BattleMap) -> Position:
    """Step one square at a time toward target, tracking diagonal cost."""
    cur = origin
    spent = 0
    diag_count = 0

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
        cur = new_pos
        spent += cost

    return cur
