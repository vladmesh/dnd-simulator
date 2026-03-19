from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.world import World
from dnd_simulator.storage.store import SaveStore


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

    def __init__(self, store: SaveStore) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._store = store

    def start_game(self) -> GameSession:
        """Create a new game session with default world."""
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

    def save_game(self, session_id: str, name: str | None = None) -> str:
        """Save game state. Returns the save name."""
        session = self._get_session(session_id)
        save_name = name or f"save_{session_id}"
        data: dict[str, Any] = session.world.save()
        self._store.save(save_name, data)
        return save_name

    def load_game(self, session_id: str, name: str) -> None:
        """Load game state into session."""
        session = self._get_session(session_id)
        data = self._store.load(name)
        session.world.load(data)

    def list_saves(self) -> list[str]:
        """List available saves."""
        return self._store.list_saves()

    def _get_session(self, session_id: str) -> GameSession:
        if session_id not in self._sessions:
            raise ValueError(f"Session '{session_id}' not found")
        return self._sessions[session_id]
