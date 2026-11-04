from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.service.errors import SessionNotFoundError
from dnd_simulator.service.game_service import GameService
from dnd_simulator.storage.save_schema import SaveGame
from dnd_simulator.storage.store import JsonFileStore


@pytest.mark.parametrize("world_name", ["", "missing_world"], ids=["empty-world-name", "missing-world-template"])
def test_restore_rejects_unusable_world_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, world_name: str
) -> None:
    monkeypatch.setenv("DND_WORLD_SEED", "42")
    monkeypatch.setenv("DND_DICE_SEED", "42")
    store = JsonFileStore(tmp_path / "saves")
    original_service = GameService(store=store)
    session = original_service.start_game()
    original_service.autosave_session(session.session_id)
    save_name = f"session_{session.session_id}"
    original_data = store.load(save_name, world=session.world_name)
    save = SaveGame.model_validate(original_data)
    save.meta.world_name = world_name
    unusable_data = save.model_dump(mode="json", by_alias=True)
    store.save(save_name, unusable_data, world=session.world_name)
    service = GameService(store=store)

    with pytest.raises(SessionNotFoundError, match=rf"^Session '{session.session_id}' not found$"):
        service.get_session(session.session_id)

    assert service.list_sessions() == []
    assert store.load(save_name, world=session.world_name) == unusable_data

    store.save(save_name, original_data, world=session.world_name)
    restored = service.get_session(session.session_id)

    assert restored.session_id == session.session_id
    assert restored.world_name == session.world_name
    assert restored.build_save_game().model_dump(mode="json", by_alias=True) == original_data
    assert service.get_session(session.session_id) is restored
