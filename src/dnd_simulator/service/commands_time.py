from __future__ import annotations

from dnd_simulator.core.models import TimeDelta
from dnd_simulator.service.session import GameSession


class TimeCommands:
    """Mixin: time advancement commands."""

    def advance_time(self, session_id: str, hours: int) -> list[str]:
        """Advance game time by given hours. Returns event descriptions."""
        session: GameSession = self._get_session(session_id)  # type: ignore[attr-defined]
        events = session.world.advance_time(TimeDelta.from_hours(hours))
        return [e.description for e in events if e.description]
