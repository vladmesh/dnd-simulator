"""Transport-agnostic creature action — what a brain decides to do."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Action:
    """A creature's chosen action for this turn.

    Name is one of: idle, say, attack, dodge, flee, move, dash.
    Params carry action-specific data (target_id, text, toward, etc.).
    """

    name: str
    params: dict[str, object] = field(default_factory=dict)
