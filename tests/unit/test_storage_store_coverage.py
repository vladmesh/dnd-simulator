from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from dnd_simulator.storage.store import JsonFileStore


@pytest.mark.parametrize("world", ["", "sword_vale"])
def test_autosave_persists_under_utc_timestamped_name(tmp_path: Path, world: str) -> None:
    store = JsonFileStore(tmp_path / "saves")
    data = {"player": "Éowyn", "level": 3}
    timestamp = datetime(2025, 2, 3, 4, 5, 6, tzinfo=UTC)

    with patch("dnd_simulator.storage.store.datetime", wraps=datetime) as clock:
        clock.now.return_value = timestamp
        store.autosave(data, world=world)

    assert store.list_saves(world=world) == ["autosave_20250203_040506"]
    assert store.load("autosave_20250203_040506", world=world) == data
    assert store.list_worlds() == ([world] if world else [])
    if world:
        assert store.list_saves() == []


@pytest.mark.parametrize("has_world_save", [False, True])
def test_load_uses_legacy_root_save_only_when_world_save_is_missing(tmp_path: Path, has_world_save: bool) -> None:
    store = JsonFileStore(tmp_path / "saves")
    legacy_data = {"player": "Legacy", "level": 1}
    world_data = {"player": "Current", "level": 2}
    store.save("slot", legacy_data)
    if has_world_save:
        store.save("slot", world_data, world="sword_vale")

    assert store.load("slot", world="sword_vale") == (world_data if has_world_save else legacy_data)
    assert store.load("slot") == legacy_data
    assert store.list_saves(world="sword_vale") == (["slot"] if has_world_save else [])


def test_list_saves_for_missing_world_is_empty_without_creating_directory(tmp_path: Path) -> None:
    directory = tmp_path / "saves"
    store = JsonFileStore(directory)
    store.save("slot", {"level": 1})

    assert store.list_saves(world="unknown") == []
    assert not (directory / "unknown").exists()
    assert store.list_saves() == ["slot"]


@pytest.mark.parametrize(
    ("name", "world", "error"),
    [
        ("slot", "../outside", "Invalid world name"),
        ("../outside", "", "Invalid save name"),
        ("../../outside", "sword_vale", "Invalid save name"),
    ],
)
def test_save_rejects_paths_outside_store(tmp_path: Path, name: str, world: str, error: str) -> None:
    store = JsonFileStore(tmp_path / "saves")

    with pytest.raises(ValueError, match=f"^{error}:"):
        store.save(name, {"level": 1}, world=world)

    assert not (tmp_path / "outside.json").exists()
    assert not (tmp_path / "outside").exists()
    assert store.list_saves() == []
    assert store.list_worlds() == []
