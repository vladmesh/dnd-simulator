"""Transport-agnostic creature action — what a brain decides to do."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Action:
    """A creature's chosen action for this turn.

    Name is one of: idle, say, attack, dodge, flee, move, dash, end_turn, skip.
    Params carry action-specific data (target_id, text, toward, etc.).
    """

    name: str
    params: dict[str, object] = field(default_factory=dict)


# Sentinel actions — used by the multi-action turn loop.
END_TURN = Action(name="end_turn")
SKIP = Action(name="skip")
