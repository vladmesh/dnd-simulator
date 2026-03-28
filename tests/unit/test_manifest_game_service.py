"""Tests for GameService loading worlds through manifest resolution."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.service.game_service import GameService
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


def _make_service(tmp_path: Path) -> GameService:
    store = JsonFileStore(tmp_path / "saves")
    return GameService(store=store, content_dir=CONTENT_DIR)


class TestStartGameSwordVale:
    """sword_vale loads via manifest (all layers from library)."""

    def test_regions(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        geo = session.world.layers[0]
        assert len(geo._regions) == 7  # type: ignore[attr-defined]

    def test_nations(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        politics = session.world.layers[1]
        assert len(politics._nations) == 3  # type: ignore[attr-defined]

    def test_settlements(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        settlements = session.world.layers[2]
        assert len(settlements._settlements) == 10  # type: ignore[attr-defined]

    def test_locations(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        assert len(session.world.location_graph.all_ids()) == 32

    def test_npcs(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        entities = session.world.layers[4]
        npcs = [e for e in entities._entities.values() if hasattr(e, "role")]  # type: ignore[attr-defined]
        assert len(npcs) == 6

    def test_squads(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        ecology = session.world.layers[3]
        assert len(ecology._squads) == 3  # type: ignore[attr-defined]


class TestStartGameTestVale:
    """test_vale loads via manifest (all layers custom)."""

    def test_regions(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("test_vale")
        geo = session.world.layers[0]
        assert len(geo._regions) == 2  # type: ignore[attr-defined]

    def test_nations(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("test_vale")
        politics = session.world.layers[1]
        assert len(politics._nations) == 1  # type: ignore[attr-defined]

    def test_settlements(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("test_vale")
        settlements = session.world.layers[2]
        assert len(settlements._settlements) == 1  # type: ignore[attr-defined]

    def test_locations(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("test_vale")
        assert len(session.world.location_graph.all_ids()) == 5

    def test_npcs(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("test_vale")
        entities = session.world.layers[4]
        npcs = [e for e in entities._entities.values() if hasattr(e, "role")]  # type: ignore[attr-defined]
        assert len(npcs) == 4

    def test_squads(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("test_vale")
        ecology = session.world.layers[3]
        assert len(ecology._squads) == 1  # type: ignore[attr-defined]


class TestListWorlds:
    def test_lists_both_worlds(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        worlds = svc.list_worlds()
        ids = {w["id"] for w in worlds}
        assert "sword_vale" in ids
        assert "test_vale" in ids

    def test_world_names_correct(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        worlds = svc.list_worlds()
        by_id = {w["id"]: w for w in worlds}
        assert by_id["sword_vale"]["name"] == "Sword Vale"
        assert by_id["test_vale"]["name"] == "Test Vale"


class TestNoManifestWorld:
    def test_directory_without_manifest_not_listed(self, tmp_path: Path) -> None:
        """A world directory without manifest.yaml is not returned by list_worlds."""
        store = JsonFileStore(tmp_path / "saves")
        content_dir = tmp_path / "content"
        worlds_dir = content_dir / "worlds"
        worlds_dir.mkdir(parents=True)

        # Create a dir with world.yaml (old format) but no manifest
        old_world = worlds_dir / "old_world"
        old_world.mkdir()
        (old_world / "world.yaml").write_text("name: Old World\n")

        svc = GameService(store=store, content_dir=content_dir)
        worlds = svc.list_worlds()
        assert len(worlds) == 0

    def test_start_game_without_manifest_raises(self, tmp_path: Path) -> None:
        store = JsonFileStore(tmp_path / "saves")
        content_dir = tmp_path / "content"
        worlds_dir = content_dir / "worlds"
        (worlds_dir / "broken_world").mkdir(parents=True)

        svc = GameService(store=store, content_dir=content_dir)
        with pytest.raises(RuntimeError, match=r"manifest\.yaml"):
            svc.start_game("broken_world")
