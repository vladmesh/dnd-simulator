"""Tests for world authorship — the `creator` tag threaded through create/assemble/fork.

Pure attribution (Sprint 020 phase 1 task 1): records *who made* a template, not
who may access it (access is a separate concern, deferred to a future M2M model).
An absent creator reads as "" (unknown); shipped base worlds carry creator "system".
Exercised at the content_loader + service layer, no HTTP needed.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from dnd_simulator.content_loader.assembly import (
    assemble_world,
    create_empty_world,
    fork_world,
)
from dnd_simulator.content_loader.manifest import LayerType, load_world_meta_from_manifest
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


def _with_library(tmp_path: Path) -> Path:
    """Create a content dir that symlinks the real library for testing."""
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "worlds").mkdir()
    (content_dir / "library").symlink_to(CONTENT_DIR / "library")
    catalogs_src = CONTENT_DIR / "catalogs"
    if catalogs_src.exists():
        (content_dir / "catalogs").symlink_to(catalogs_src)
    return content_dir


def _service(content_dir: Path) -> GameService:
    return GameService(store=JsonFileStore(content_dir.parent / "saves"), content_dir=content_dir)


class TestCreateStampsCreator:
    def test_create_empty_world_stamps_creator(self, tmp_path: Path) -> None:
        """create_empty_world(creator=...) writes the creator to the manifest and list_worlds reports it."""
        content_dir = _with_library(tmp_path)
        world_path = create_empty_world(content_dir, "alices_world", "Alice's World", "", "", creator="alice")

        # On-disk manifest carries the creator
        with (world_path / "manifest.yaml").open() as f:
            manifest = yaml.safe_load(f)
        assert manifest["creator"] == "alice"

        # list_worlds surfaces it
        service = _service(content_dir)
        listed = next(w for w in service.list_worlds() if w["id"] == "alices_world")
        assert listed["creator"] == "alice"

    def test_create_empty_world_default_creator_is_empty(self, tmp_path: Path) -> None:
        """Without a creator arg the world's creator is unknown (creator == '')."""
        content_dir = _with_library(tmp_path)
        world_path = create_empty_world(content_dir, "anon", "Anon", "", "")
        with (world_path / "manifest.yaml").open() as f:
            manifest = yaml.safe_load(f)
        assert manifest["creator"] == ""


class TestAssembleStampsCreator:
    def test_assemble_stamps_creator_and_stays_startable(self, tmp_path: Path) -> None:
        """Assembling with creator persists it; creator is metadata so the world still starts."""
        content_dir = _with_library(tmp_path)
        assemble_world(
            content_dir=content_dir,
            world_id="alice_assembled",
            name="Alice Assembled",
            description="",
            layer_selections={lt.value: "sword_vale" for lt in LayerType},
            default_player_faction="kingdom",
            creator="alice",
        )

        meta = load_world_meta_from_manifest(content_dir / "worlds" / "alice_assembled")
        assert meta["creator"] == "alice"

        # creator is metadata, not a layer — the world is still startable
        service = _service(content_dir)
        session = service.start_game("alice_assembled")
        assert session.world is not None
        assert len(session.world.layers) == 5


class TestForkReAttributes:
    def test_fork_sets_creator_to_forker_source_untouched(self, tmp_path: Path) -> None:
        """Fork attributes the new world to the forking user; the source's creator is unchanged."""
        content_dir = _with_library(tmp_path)
        assemble_world(
            content_dir=content_dir,
            world_id="alice_src",
            name="Alice Source",
            description="",
            layer_selections={lt.value: "sword_vale" for lt in LayerType},
            default_player_faction="kingdom",
            creator="alice",
        )

        fork_world(content_dir, "alice_src", "bob_fork", creator="bob")

        forked_meta = load_world_meta_from_manifest(content_dir / "worlds" / "bob_fork")
        assert forked_meta["creator"] == "bob"

        # Source creator unchanged
        source_meta = load_world_meta_from_manifest(content_dir / "worlds" / "alice_src")
        assert source_meta["creator"] == "alice"


class TestListWorldsCreatorFilter:
    """list_worlds(creator=...) is a scoping helper for the worldbuilder lens (projection, not enforcement)."""

    def test_filter_returns_only_matching_creator(self, tmp_path: Path) -> None:
        """list_worlds(creator='alice') returns alice's worlds; system/other creators are excluded."""
        content_dir = _with_library(tmp_path)
        create_empty_world(content_dir, "alice_one", "Alice One", "", "", creator="alice")
        create_empty_world(content_dir, "alice_two", "Alice Two", "", "", creator="alice")
        create_empty_world(content_dir, "system_world", "System World", "", "", creator="system")
        create_empty_world(content_dir, "bob_one", "Bob One", "", "", creator="bob")
        service = _service(content_dir)

        assert {w["id"] for w in service.list_worlds(creator="alice")} == {"alice_one", "alice_two"}
        # A system/base creator is requestable the same way — not special-cased, just filtered.
        assert {w["id"] for w in service.list_worlds(creator="system")} == {"system_world"}

    def test_unfiltered_returns_all_creators(self, tmp_path: Path) -> None:
        """list_worlds() with no creator returns every world regardless of who made it."""
        content_dir = _with_library(tmp_path)
        create_empty_world(content_dir, "alice_one", "Alice One", "", "", creator="alice")
        create_empty_world(content_dir, "bob_one", "Bob One", "", "", creator="bob")
        service = _service(content_dir)

        assert {w["id"] for w in service.list_worlds()} == {"alice_one", "bob_one"}


class TestBackwardCompat:
    def test_manifest_without_creator_loads_as_empty(self, tmp_path: Path) -> None:
        """A manifest with no creator key returns creator == '' and does not raise."""
        world_path = tmp_path / "worlds" / "legacy"
        world_path.mkdir(parents=True)
        manifest = {"name": "Legacy", "description": "", "default_player_faction": "", "layers": {}}
        with (world_path / "manifest.yaml").open("w") as f:
            yaml.dump(manifest, f)

        meta = load_world_meta_from_manifest(world_path)
        assert meta["creator"] == ""

    def test_base_world_creator_is_system(self) -> None:
        """A shipped base world (sword_vale) carries creator == 'system'."""
        service = GameService(store=JsonFileStore(CONTENT_DIR.parent / "saves"), content_dir=CONTENT_DIR)
        sword_vale = next(w for w in service.list_worlds() if w["id"] == "sword_vale")
        assert sword_vale["creator"] == "system"
