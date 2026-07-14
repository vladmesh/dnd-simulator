from __future__ import annotations

import asyncio
import contextlib
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
from pydantic import ValidationError
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
from dnd_simulator.service.errors import PlayerNotFoundError, SessionNotFoundError
from dnd_simulator.service.game_service import DEFAULT_CONTENT_DIR
from dnd_simulator.storage.store import JsonFileStore

DEFAULT_SAVES_DIR = Path(__file__).resolve().parents[4] / "saves"
DEFAULT_AUTOSAVE_SECONDS = 120.0

_SESSION_ID_RE = re.compile(r"/api/(?:master|player)/sessions/([^/]+)")
logger = structlog.get_logger(domain="transport.api")


def _autosave_interval_from_env() -> float:
    raw = os.getenv("DND_AUTOSAVE_SECONDS")
    if raw is None:
        return DEFAULT_AUTOSAVE_SECONDS
    interval = float(raw)
    if interval <= 0:
        raise ValueError("DND_AUTOSAVE_SECONDS must be greater than 0")
    return interval


async def _periodic_autosave(service: GameService, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        save_task = asyncio.create_task(asyncio.to_thread(service.autosave_all_sessions))
        try:
            await asyncio.shield(save_task)
        except asyncio.CancelledError:
            await save_task
            raise
        except Exception:
            logger.exception("periodic_autosave_failed")


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
    autosave_interval = _autosave_interval_from_env()
    autosave_task = asyncio.create_task(_periodic_autosave(service, autosave_interval))
    try:
        yield
    finally:
        autosave_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await autosave_task
        try:
            service.autosave_all_sessions()
        except Exception:
            logger.exception("final_autosave_failed")


app = FastAPI(title="D&D Simulator", version="0.1.0", lifespan=lifespan)
app.add_middleware(I18nMiddleware)


@app.exception_handler(SessionNotFoundError)
async def _session_not_found(request: Request, exc: SessionNotFoundError) -> Response:
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PlayerNotFoundError)
async def _player_not_found(request: Request, exc: PlayerNotFoundError) -> Response:
    from fastapi.responses import JSONResponse

    return JSONResponse(status_code=404, content={"detail": str(exc)})


# App-level handlers for unambiguous exception types. Routes that need a
# non-standard status or a custom (localized) detail keep their own local
# try/except — those take precedence over these.
def _status_handler(status_code: int) -> Callable[[Request, Exception], Awaitable[Response]]:
    async def handler(request: Request, exc: Exception) -> Response:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler


app.add_exception_handler(FileNotFoundError, _status_handler(404))
app.add_exception_handler(KeyError, _status_handler(404))
app.add_exception_handler(FileExistsError, _status_handler(409))
app.add_exception_handler(ValidationError, _status_handler(422))


_cors_raw = os.getenv("CORS_ALLOWED_ORIGINS", "*").strip()
_cors_origins = ["*"] if _cors_raw == "*" else [o.strip() for o in _cors_raw.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials="*" not in _cors_origins,
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
