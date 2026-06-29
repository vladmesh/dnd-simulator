from __future__ import annotations

import os

from fastapi import HTTPException, Request

from dnd_simulator.i18n import set_language
from dnd_simulator.service import GameService
from dnd_simulator.service.identity import Identity, Role, resolve_identity

_service: GameService | None = None


def set_service(service: GameService) -> None:
    global _service
    _service = service


def get_service() -> GameService:
    if _service is None:
        raise RuntimeError("GameService not initialized")
    return _service


def _default_role() -> Role:
    """Server-wide default role for header-less requests (env-configurable).

    Defaults to ADMIN so single-user localhost dev and existing header-less
    callers keep full access. Phase 2 tightens this.
    """
    raw = os.getenv("DND_DEFAULT_ROLE", "").strip()
    if not raw:
        return Role.ADMIN
    try:
        return Role(raw)
    except ValueError:
        return Role.ADMIN


def get_identity(request: Request) -> Identity:
    """FastAPI dependency: resolve caller identity from X-User-Id / X-Role headers.

    An unparseable X-Role becomes HTTP 400. Header-less requests resolve to the
    default identity (user "local", role from ``_default_role``).
    """
    try:
        return resolve_identity(
            request.headers.get("X-User-Id"),
            request.headers.get("X-Role"),
            default_role=_default_role(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def apply_session_lang(session_id: str) -> None:
    """Set i18n language from session context. Call before processing requests."""
    service = get_service()
    try:
        session = service.get_session(session_id)
        set_language(session.lang)
    except ValueError:
        pass  # session not found — will be caught by route handler
