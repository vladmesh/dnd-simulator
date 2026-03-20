from __future__ import annotations

from dnd_simulator.i18n import set_language
from dnd_simulator.service import GameService

_service: GameService | None = None


def set_service(service: GameService) -> None:
    global _service
    _service = service


def get_service() -> GameService:
    if _service is None:
        raise RuntimeError("GameService not initialized")
    return _service


def apply_session_lang(session_id: str) -> None:
    """Set i18n language from session context. Call before processing requests."""
    service = get_service()
    try:
        session = service.get_session(session_id)
        set_language(session.lang)
    except ValueError:
        pass  # session not found — will be caught by route handler
