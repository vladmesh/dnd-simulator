"""DND_SAVES_DIR selects the directory the API's save store writes to."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from dnd_simulator.adapters.api import app as app_module
from dnd_simulator.adapters.api.app import DEFAULT_SAVES_DIR, _saves_dir_from_env, lifespan


class _Service:
    def autosave_all_sessions(self) -> None:
        pass


async def _store_path_from_lifespan(monkeypatch: pytest.MonkeyPatch) -> Path:
    paths: list[Path] = []

    class Store:
        def __init__(self, path: Path) -> None:
            paths.append(path)

    monkeypatch.setattr(app_module, "load_dotenv", lambda: None)
    monkeypatch.setattr(app_module, "JsonFileStore", Store)
    monkeypatch.setattr(app_module, "GameService", lambda **_: _Service())
    monkeypatch.setattr(app_module, "set_service", lambda service: None)
    monkeypatch.setattr(app_module, "configure_logging", lambda **_: None)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    async with lifespan(MagicMock()):
        pass

    assert len(paths) == 1
    return paths[0]


def test_saves_dir_defaults_to_repo_saves(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DND_SAVES_DIR", raising=False)
    assert _saves_dir_from_env() == DEFAULT_SAVES_DIR
    assert DEFAULT_SAVES_DIR.name == "saves"


def test_empty_saves_dir_falls_back_to_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DND_SAVES_DIR", "")
    assert _saves_dir_from_env() == DEFAULT_SAVES_DIR


async def test_lifespan_store_uses_saves_dir_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("DND_SAVES_DIR", str(tmp_path / "custom_saves"))
    assert await _store_path_from_lifespan(monkeypatch) == tmp_path / "custom_saves"


async def test_lifespan_store_uses_default_saves_dir_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DND_SAVES_DIR", raising=False)
    assert await _store_path_from_lifespan(monkeypatch) == DEFAULT_SAVES_DIR
