"""Protocol declaring the shared interface that service mixins depend on."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from dnd_simulator.layers.entities.layer import EntitiesLayer
    from dnd_simulator.layers.politics.layer import PoliticsLayer
    from dnd_simulator.layers.settlements.layer import SettlementsLayer
    from dnd_simulator.service.brain_factory import BrainFactory
    from dnd_simulator.service.session import GameSession
    from dnd_simulator.storage.store import SaveStore


class GameServiceProtocol(Protocol):
    """Contract for attributes that service command mixins rely on."""

    _store: SaveStore
    _sessions: dict[str, GameSession]
    _sessions_lock: threading.RLock
    _brain_factory: BrainFactory
    _content_dir: Path

    def _get_session(self, session_id: str) -> GameSession: ...

    def autosave_session(self, session_id: str) -> None: ...

    def _get_entities_layer(self, session: GameSession) -> EntitiesLayer: ...

    def _assign_brains(self, entities_layer: EntitiesLayer) -> None: ...

    def _get_politics_layer(self, session: GameSession) -> PoliticsLayer: ...

    def _get_settlements_layer(self, session: GameSession) -> SettlementsLayer: ...
