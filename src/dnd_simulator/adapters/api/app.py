from __future__ import annotations

import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware

from dnd_simulator.adapters.api.deps import get_service, set_service
from dnd_simulator.adapters.api.routes_master import router as master_router
from dnd_simulator.adapters.api.routes_player import router as player_router
from dnd_simulator.adapters.api.routes_ws import router as ws_router
from dnd_simulator.i18n import set_language
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

DEFAULT_SAVES_DIR = Path(__file__).resolve().parents[4] / "saves"
_FRONTEND_DIST = Path(__file__).resolve().parents[4] / "frontend" / "dist"
_STATIC_DIR = Path(__file__).resolve().parent / "static"

_SESSION_ID_RE = re.compile(r"/api/(?:master|player)/sessions/([^/]+)")


class I18nMiddleware(BaseHTTPMiddleware):
    """Set i18n language from session before each request."""

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        match = _SESSION_ID_RE.match(request.url.path)
        if match:
            session_id = match.group(1)
            try:
                service = get_service()
                session = service.get_session(session_id)
                set_language(session.lang)
            except (ValueError, RuntimeError):
                pass  # session not found — route handler will return 404
        return await call_next(request)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    load_dotenv()

    store = JsonFileStore(DEFAULT_SAVES_DIR)

    llm: LlmClient | None = None
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    if api_key:
        model = os.getenv("LLM_MODEL", "deepseek/deepseek-chat-v3-0324")
        llm = LlmClient(api_key=api_key, model=model)

    service = GameService(store=store, llm=llm)
    set_service(service)
    try:
        yield
    finally:
        service.autosave_all_sessions()


app = FastAPI(title="D&D Simulator", version="0.1.0", lifespan=lifespan)
app.add_middleware(I18nMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(master_router)
app.include_router(player_router)
app.include_router(ws_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


import logging

_fe_log = logging.getLogger("frontend")


@app.post("/api/frontend-error")
async def frontend_error(request: Request) -> dict[str, str]:
    body = await request.json()
    _fe_log.error("FRONTEND ERROR: %s\n%s", body.get("message", "?"), body.get("stack", ""))
    return {"status": "logged"}


# Static files served AFTER API routes so /api/* takes priority.
# Prefer React frontend build if available, fall back to legacy debug UI.
_static_root = _FRONTEND_DIST if _FRONTEND_DIST.is_dir() else _STATIC_DIR
app.mount("/", StaticFiles(directory=str(_static_root), html=True), name="static")
