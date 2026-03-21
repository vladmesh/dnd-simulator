from __future__ import annotations

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
            "player": session.player.to_save_data() if session.player else {},
        }
        self._store.save(save_name, data)  # type: ignore[attr-defined]
        return save_name

    def load_game(self, session_id: str, name: str) -> None:
        """Load game state into session."""
        session: GameSession = self._get_session(session_id)  # type: ignore[attr-defined]
        data = self._store.load(name)  # type: ignore[attr-defined]

        # Support both old format (flat world data) and new format (world + player)
        if "world" in data:
            session.world.load(data["world"])
            player_data = data.get("player", {})
            assert isinstance(player_data, dict)
            if session.player:
                session.player.load_save_data(player_data)
        else:
            session.world.load(data)

    def list_saves(self) -> list[str]:
        """List available saves."""
        result: list[str] = self._store.list_saves()  # type: ignore[attr-defined]
        return result
