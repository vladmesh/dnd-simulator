"""Coverage for worldbuilder validation, library write guards, and catalog listing."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from dnd_simulator.content_loader.assembly import assemble_world
from dnd_simulator.content_loader.crud import EntityType
from dnd_simulator.content_loader.manifest import LayerType
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


@pytest.fixture
def service(tmp_path: Path) -> GameService:
    return GameService(store=JsonFileStore(tmp_path / "saves"), content_dir=tmp_path / "content")


@pytest.fixture
def library_service(service: GameService, tmp_path: Path) -> GameService:
    content_dir = tmp_path / "content"
    content_dir.mkdir()
    (content_dir / "library").symlink_to(CONTENT_DIR / "library")
    assemble_world(
        content_dir=content_dir,
        world_id="test_world",
        name="Test World",
        description="A test world",
        layer_selections={lt.value: "sword_vale" for lt in LayerType},
        default_player_faction="kingdom",
    )
    return service


def test_list_worlds_without_worlds_directory(service: GameService, tmp_path: Path) -> None:
    content_dir = tmp_path / "content"
    content_dir.mkdir()

    assert service.list_worlds() == []
    assert not (content_dir / "worlds").exists()


@pytest.mark.parametrize(
    "world_id", ["", "../outside", "/absolute", r"..\outside", "nested/world", "UPPER", "-leading"]
)
def test_invalid_world_ids_are_rejected(service: GameService, world_id: str) -> None:
    with pytest.raises(ValueError, match=f"^{re.escape(f'Invalid world_id: {world_id!r}')}$"):
        service.get_layer_files(world_id, LayerType.ENTITIES)


@pytest.mark.parametrize("operation", ["update", "delete"])
def test_library_entities_are_read_only_until_forked(library_service: GameService, operation: str) -> None:
    service = library_service
    entity = service.list_content_entities("test_world", EntityType.NPC)[0]
    entity_id = entity["id"]
    data = entity["data"]
    assert isinstance(entity_id, str)
    assert isinstance(data, dict)
    updated_data = {**data, "hp": 99}
    original_files = service.get_layer_files("test_world", LayerType.ENTITIES)

    with pytest.raises(ValueError, match=r"^Cannot write to library layer — fork it first$"):
        if operation == "update":
            service.update_content_entity("test_world", EntityType.NPC, entity_id, updated_data)
        else:
            service.delete_content_entity("test_world", EntityType.NPC, entity_id)

    assert service.get_content_entity("test_world", EntityType.NPC, entity_id) == entity
    assert service.get_layer_files("test_world", LayerType.ENTITIES) == original_files

    service.fork_layer("test_world", LayerType.ENTITIES)
    if operation == "update":
        result = service.update_content_entity("test_world", EntityType.NPC, entity_id, updated_data)
        assert result["id"] == entity_id
        assert result["data"]["hp"] == 99
        assert service.get_content_entity("test_world", EntityType.NPC, entity_id) == result
    else:
        service.delete_content_entity("test_world", EntityType.NPC, entity_id)
        with pytest.raises(KeyError, match=re.escape(f"npc '{entity_id}' not found")):
            service.get_content_entity("test_world", EntityType.NPC, entity_id)

    assert service.get_layer_files("test_world", LayerType.ENTITIES) != original_files
    library_files = CONTENT_DIR / "library" / "entities" / "sword_vale"
    assert all((library_files / name).read_text(encoding="utf-8") == text for name, text in original_files.items())


def test_list_catalog_entries_reads_empty_and_populated_catalog(service: GameService, tmp_path: Path) -> None:
    assert service.list_catalog_entries(EntityType.MONSTER_CATALOG) == []
    (tmp_path / "content" / "catalogs" / "monsters").mkdir(parents=True)
    assert service.list_catalog_entries(EntityType.MONSTER_CATALOG) == []

    for entry_id, name, hp in [("zebra", "Zebra", 20), ("antelope", "Antelope", 12)]:
        service.create_catalog_entry(
            EntityType.MONSTER_CATALOG,
            entry_id,
            {"name": {"en": name}, "hp": hp, "ac": 13, "speed": 40, "cr": 1.0},
        )

    entries = service.list_catalog_entries(EntityType.MONSTER_CATALOG)
    assert [entry["id"] for entry in entries] == ["antelope", "zebra"]
    assert [entry["data"]["name"] for entry in entries] == [{"en": "Antelope"}, {"en": "Zebra"}]
    assert [entry["data"]["hp"] for entry in entries] == [12, 20]
    assert all(entry["data"]["ac"] == 13 and entry["data"]["speed"] == 40 for entry in entries)
