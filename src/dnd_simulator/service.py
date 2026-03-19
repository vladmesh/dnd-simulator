from __future__ import annotations

from dataclasses import dataclass

from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.world import World


@dataclass
class MasterResponse:
    """What the DM tells the player."""

    text: str
    events_summary: list[str] | None = None


@dataclass
class GameSession:
    """An active game session."""

    session_id: str
    world: World


class GameService:
    """Main interface to the game. Transport-agnostic."""

    def __init__(self) -> None:
        self._sessions: dict[str, GameSession] = {}

    def start_game(self) -> GameSession:
        """Create a new game session with default world."""
        import uuid

        session_id = uuid.uuid4().hex[:8]

        # TODO: initialize layers, load content
        world = World(layers=[], time=GameDateTime(year=1490))

        session = GameSession(session_id=session_id, world=world)
        self._sessions[session_id] = session
        return session

    def player_action(self, session_id: str, text: str) -> MasterResponse:
        """Process player input and return DM response."""
        session = self._get_session(session_id)

        # TODO: pass to master LLM, which will:
        # 1. interpret player action
        # 2. query/update relevant layers
        # 3. decide time advancement
        # 4. compose narrative response
        _ = session

        return MasterResponse(text=f"[TODO: Master will process: '{text}']")

    def get_session(self, session_id: str) -> GameSession:
        """Get session info."""
        return self._get_session(session_id)

    def save_game(self, session_id: str) -> dict[str, object]:
        """Save game state."""
        session = self._get_session(session_id)
        return session.world.save()

    def load_game(self, session_id: str, data: dict[str, object]) -> None:
        """Load game state into session."""
        session = self._get_session(session_id)
        session.world.load(data)

    def _get_session(self, session_id: str) -> GameSession:
        if session_id not in self._sessions:
            raise ValueError(f"Session '{session_id}' not found")
        return self._sessions[session_id]
