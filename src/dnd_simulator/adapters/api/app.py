from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.adapters.api.routes_master import router as master_router
from dnd_simulator.adapters.api.routes_player import router as player_router
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

DEFAULT_SAVES_DIR = Path(__file__).resolve().parents[4] / "saves"


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
    yield


app = FastAPI(title="D&D Simulator", version="0.1.0", lifespan=lifespan)
app.include_router(master_router)
app.include_router(player_router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
