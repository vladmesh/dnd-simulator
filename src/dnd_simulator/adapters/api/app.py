from __future__ import annotations

import logging
import os
import re
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from dotenv import load_dotenv
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from dnd_simulator.adapters.api.deps import get_service, set_service
from dnd_simulator.adapters.api.routes_content import content_router
from dnd_simulator.adapters.api.routes_player import router as player_router
from dnd_simulator.adapters.api.routes_session import router as session_router
from dnd_simulator.adapters.api.routes_world import router as world_router
from dnd_simulator.adapters.api.routes_ws import router as ws_router
from dnd_simulator.i18n import set_language
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.logging_config import configure_logging
from dnd_simulator.service import GameService
from dnd_simulator.service.game_service import DEFAULT_CONTENT_DIR
from dnd_simulator.storage.store import JsonFileStore

DEFAULT_SAVES_DIR = Path(__file__).resolve().parents[4] / "saves"

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

    log_level_name = os.environ.get("LOG_LEVEL", "WARNING")
    log_level = getattr(logging, log_level_name.upper())
    log_dir_raw = os.getenv("LOG_DIR")
    configure_logging(log_level=log_level, log_dir=Path(log_dir_raw) if log_dir_raw else None)

    dice_seed = os.getenv("DND_DICE_SEED")
    if dice_seed is not None:
        from dnd_simulator.rules.dice import set_global_seed

        set_global_seed(int(dice_seed))

    store = JsonFileStore(DEFAULT_SAVES_DIR)

    llm: LlmClient | None = None
    api_key = os.getenv("OPENROUTER_API_KEY")
    if api_key:
        model = os.environ["LLM_MODEL"]  # no default — must be set explicitly
        llm = LlmClient(api_key=api_key, model=model)

    content_dir_env = os.getenv("DND_CONTENT_DIR")
    content_dir = Path(content_dir_env) if content_dir_env else DEFAULT_CONTENT_DIR
    service = GameService(store=store, llm=llm, content_dir=content_dir)
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
app.include_router(world_router)
app.include_router(session_router)
app.include_router(content_router)
app.include_router(player_router)
app.include_router(ws_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


_fe_log = structlog.get_logger(domain="transport.frontend")


@app.post("/api/frontend-error")
async def frontend_error(request: Request) -> dict[str, str]:
    body = await request.json()
    _fe_log.error("frontend_error", message=body.get("message", "?"), stack=body.get("stack", ""))
    return {"status": "logged"}
