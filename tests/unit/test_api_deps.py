"""Tests for the API service dependency holder (``adapters/api/deps.py``)."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import dnd_simulator.adapters.api.deps as deps
from dnd_simulator.i18n import current_lang, set_language
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


@pytest.fixture(autouse=True)
def _restore_state() -> Iterator[None]:
    previous_service = deps._service
    previous_lang = current_lang.get()
    yield
    deps._service = previous_service
    set_language(previous_lang)


def test_get_service_uninitialized_raises() -> None:
    deps._service = None
    with pytest.raises(RuntimeError, match="GameService not initialized"):
        deps.get_service()


def test_set_then_get_returns_same_service(tmp_path: Path) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    deps.set_service(service)
    assert deps.get_service() is service


def test_apply_session_lang_sets_session_language(tmp_path: Path) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    deps.set_service(service)
    session_id = service.start_game("sword_vale", lang="ru").session_id
    try:
        set_language("en")
        deps.apply_session_lang(session_id)
        assert current_lang.get() == "ru"
    finally:
        service.delete_session(session_id)


def test_apply_session_lang_unknown_session_keeps_language(tmp_path: Path) -> None:
    deps.set_service(GameService(store=JsonFileStore(tmp_path / "saves")))
    set_language("en")
    deps.apply_session_lang("no-such-session")
    assert current_lang.get() == "en"


def test_apply_session_lang_uninitialized_raises() -> None:
    deps._service = None
    with pytest.raises(RuntimeError):
        deps.apply_session_lang("anything")
