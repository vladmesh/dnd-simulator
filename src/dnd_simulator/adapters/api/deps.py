from __future__ import annotations

from dnd_simulator.service import GameService

_service: GameService | None = None


def set_service(service: GameService) -> None:
    global _service
    _service = service


def get_service() -> GameService:
    if _service is None:
        raise RuntimeError("GameService not initialized")
    return _service
