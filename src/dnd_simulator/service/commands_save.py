from __future__ import annotations

import structlog
from pydantic import ValidationError

from dnd_simulator.layers.common.rng_state import load_rng_state
from dnd_simulator.service.base import GameServiceProtocol
from dnd_simulator.service.session import GameSession
from dnd_simulator.storage.save_schema import SaveGame

logger = structlog.get_logger(domain="save")


class SaveCommands(GameServiceProtocol):
    """Mixin: save/load game commands."""

    def _build_save_game(self, session_id: str) -> SaveGame:
        session: GameSession = self._get_session(session_id)
        return session.build_save_game()

    @staticmethod
    def _validate_save(data: object) -> SaveGame:
        try:
            return SaveGame.model_validate(data)
        except ValidationError as exc:
            raise ValueError("incompatible save: expected schema_version=1") from exc

    def save_game(self, session_id: str, name: str | None = None) -> str:
        """Save game state. Returns the save name."""
        session: GameSession = self._get_session(session_id)
        save_name = name or f"save_{session_id}"
        data = self._build_save_game(session_id).model_dump(mode="json", by_alias=True)
        self._store.save(save_name, data, world=session.world_name)
        return save_name

    def autosave_session(self, session_id: str) -> None:
        """Autosave a session with metadata needed for restore."""
        session: GameSession = self._get_session(session_id)
        self._autosave_active_session(session)

    def _autosave_active_session(self, session: GameSession) -> bool:
        """Snapshot and persist a session if the registry still owns this exact object."""
        snapshot = session.build_save_game()
        data = snapshot.model_dump(mode="json", by_alias=True)
        with self._sessions_lock:
            if self._sessions.get(session.session_id) is not session:
                return False
            self._store.save(f"session_{session.session_id}", data, world=session.world_name)
            return True

    def autosave_all_sessions(self) -> None:
        """Autosave all active sessions. One failing session does not block the others."""
        with self._sessions_lock:
            sessions = list(self._sessions.items())
        for sid, session in sessions:
            try:
                self._autosave_active_session(session)
            except Exception:
                logger.exception("autosave_failed", session_id=sid)

    def load_game(self, session_id: str, name: str) -> None:
        """Load game state into session."""
        session: GameSession = self._get_session(session_id)
        data = self._store.load(name, world=session.world_name)
        save = self._validate_save(data)

        def restore() -> None:
            load_rng_state(session.dice_rng, save.world.dice_rng_state)
            session.world.load(save.world.to_world_dict())

            # Reassign brains based on restored ai_type (may differ from pre-load state)
            self._assign_brains(self._get_entities_layer(session))

        session.replace_world_state(restore)

    def delete_save(self, session_id: str, name: str) -> None:
        """Delete a save file."""
        session: GameSession = self._get_session(session_id)
        self._store.delete(name, world=session.world_name)

    def list_saves(self, session_id: str) -> list[str]:
        """List available saves for the session's world."""
        session: GameSession = self._get_session(session_id)
        result: list[str] = self._store.list_saves(world=session.world_name)
        return result
