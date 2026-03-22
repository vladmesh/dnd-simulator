from __future__ import annotations

import contextlib
from typing import Any

from dnd_simulator.service.session import GameSession


class SaveCommands:
    """Mixin: save/load game commands."""

    def save_game(self, session_id: str, name: str | None = None) -> str:
        """Save game state. Returns the save name."""
        session: GameSession = self._get_session(session_id)  # type: ignore[attr-defined]
        save_name = name or f"save_{session_id}"
        data: dict[str, Any] = {
            "world": session.world.save(),
        }
        self._store.save(save_name, data, world=session.world_name)  # type: ignore[attr-defined]
        return save_name

    def autosave_session(self, session_id: str) -> None:
        """Autosave a session with metadata needed for restore."""
        session: GameSession = self._get_session(session_id)  # type: ignore[attr-defined]
        data: dict[str, Any] = {
            "meta": {
                "session_id": session_id,
                "world_name": session.world_name,
                "lang": session.lang,
            },
            "world": session.world.save(),
        }
        self._store.save(f"session_{session_id}", data, world=session.world_name)  # type: ignore[attr-defined]

    def autosave_all_sessions(self) -> None:
        """Autosave all active sessions."""
        sessions: dict[str, GameSession] = self._sessions  # type: ignore[attr-defined]
        for sid in list(sessions):
            with contextlib.suppress(Exception):
                self.autosave_session(sid)

    def load_game(self, session_id: str, name: str) -> None:
        """Load game state into session."""
        session: GameSession = self._get_session(session_id)  # type: ignore[attr-defined]
        data = self._store.load(name, world=session.world_name)  # type: ignore[attr-defined]

        # Support both old format (flat world data) and new format (world + player)
        if "world" in data:
            session.world.load(data["world"])
            # Backward compat: old saves have separate "player" block
            player_data = data.get("player", {})
            assert isinstance(player_data, dict)
            if player_data:
                player = session.get_player()
                if player:
                    player.load_save_data(player_data)
        else:
            session.world.load(data)

    def delete_save(self, session_id: str, name: str) -> None:
        """Delete a save file."""
        session: GameSession = self._get_session(session_id)  # type: ignore[attr-defined]
        self._store.delete(name, world=session.world_name)  # type: ignore[attr-defined]

    def list_saves(self, session_id: str) -> list[str]:
        """List available saves for the session's world."""
        session: GameSession = self._get_session(session_id)  # type: ignore[attr-defined]
        result: list[str] = self._store.list_saves(world=session.world_name)  # type: ignore[attr-defined]
        return result
