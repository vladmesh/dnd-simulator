"""Tests for content CRUD operations — EntityRegistry + generic CRUD for layer entities and catalogs."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dnd_simulator.content_loader.crud import (
    EntityType,
    create_catalog_entry,
    create_entity,
    delete_catalog_entry,
    delete_entity,
    get_catalog_entry,
    get_entity,
    get_registry_entry,
    list_entities,
    update_catalog_entry,
    update_entity,
)
from dnd_simulator.content_loader.schemas import (
    ItemContent,
    MonsterTemplateContent,
    NpcContent,
    RegionContent,
    SettlementContent,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_layer_dir(tmp_path: Path, layer_type: str) -> Path:
    """Create a minimal layer directory with an empty YAML file."""
    layer_dir = tmp_path / layer_type
    layer_dir.mkdir(parents=True)
    return layer_dir


def _make_npc_data(**overrides: object) -> dict[str, object]:
    """Minimal valid NPC data."""
    base: dict[str, object] = {
        "name": {"en": "Test NPC"},
        "race": "human",
        "class": "commoner",
        "role": "commoner",
        "start_location": "town_square",
        "hp": 10,
        "ac": 10,
    }
    base.update(overrides)
    return base


def _make_settlement_data(**overrides: object) -> dict[str, object]:
    """Minimal valid settlement data."""
    base: dict[str, object] = {
        "name": {"en": "Testville"},
        "region": "plains",
        "type": "village",
        "population": 200,
        "prosperity": 50.0,
        "defenses": 20.0,
    }
    base.update(overrides)
    return base


def _make_monster_catalog_data(**overrides: object) -> dict[str, object]:
    """Minimal valid monster catalog entry."""
    base: dict[str, object] = {
        "name": {"en": "Test Monster"},
        "hp": 15,
        "ac": 12,
        "speed": 30,
        "cr": 0.5,
    }
    base.update(overrides)
    return base


def _make_item_catalog_data(**overrides: object) -> dict[str, object]:
    """Minimal valid item catalog entry."""
    base: dict[str, object] = {
        "name": "Test Sword",
        "type": "weapon",
        "weapon_id": "test_sword",
        "category": "simple",
        "damage": [{"dice": "1d6", "type": "slashing"}],
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Layer entity CRUD tests
# ---------------------------------------------------------------------------


class TestLayerEntityRoundTrip:
    """Test 1: create → get round-trip for layer entities."""

    def test_create_and_get_npc(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        data = _make_npc_data()

        result = create_entity(EntityType.NPC, "test_npc", data, layer_dir)

        assert isinstance(result, NpcContent)
        assert result.name == {"en": "Test NPC"}
        assert result.hp == 10

        fetched = get_entity(EntityType.NPC, "test_npc", layer_dir)
        assert isinstance(fetched, NpcContent)
        assert fetched.name == {"en": "Test NPC"}
        assert fetched.hp == 10


class TestLayerEntityList:
    """Test 2: list all entities in a layer YAML."""

    def test_list_npcs(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")

        for name_id, name_val in [("alice", "Alice"), ("bob", "Bob"), ("carol", "Carol")]:
            create_entity(EntityType.NPC, name_id, _make_npc_data(name={"en": name_val}), layer_dir)

        result = list_entities(EntityType.NPC, layer_dir)
        assert len(result) == 3
        assert set(result.keys()) == {"alice", "bob", "carol"}
        assert all(isinstance(v, NpcContent) for v in result.values())


class TestLayerEntityUpdate:
    """Test 3: update modifies target entity, leaves others untouched."""

    def test_update_npc(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        create_entity(EntityType.NPC, "npc_a", _make_npc_data(name={"en": "A"}, hp=10), layer_dir)
        create_entity(EntityType.NPC, "npc_b", _make_npc_data(name={"en": "B"}, hp=20), layer_dir)

        updated = update_entity(
            EntityType.NPC,
            "npc_a",
            _make_npc_data(name={"en": "A"}, hp=99, personality={"en": "Brave"}),
            layer_dir,
        )

        assert updated.hp == 99
        assert updated.personality == {"en": "Brave"}

        # Other NPC untouched
        npc_b = get_entity(EntityType.NPC, "npc_b", layer_dir)
        assert npc_b.hp == 20


class TestLayerEntityDelete:
    """Test 4: delete removes one entity, keeps others."""

    def test_delete_npc(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        create_entity(EntityType.NPC, "keep", _make_npc_data(name={"en": "Keep"}), layer_dir)
        create_entity(EntityType.NPC, "remove", _make_npc_data(name={"en": "Remove"}), layer_dir)

        delete_entity(EntityType.NPC, "remove", layer_dir)

        remaining = list_entities(EntityType.NPC, layer_dir)
        assert "keep" in remaining
        assert "remove" not in remaining


class TestLayerEntityDuplicate:
    """Test 5: creating with duplicate ID raises ValueError."""

    def test_duplicate_id_raises(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        create_entity(EntityType.NPC, "dup", _make_npc_data(), layer_dir)

        with pytest.raises(ValueError, match="already exists"):
            create_entity(EntityType.NPC, "dup", _make_npc_data(), layer_dir)


class TestLayerEntityValidation:
    """Test 6: invalid data raises ValidationError, file unchanged."""

    def test_invalid_create_no_write(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        create_entity(EntityType.NPC, "good", _make_npc_data(), layer_dir)

        with pytest.raises(ValidationError):
            create_entity(
                EntityType.NPC,
                "bad",
                {"name": {"en": "Bad"}, "race": "not_a_real_race"},
                layer_dir,
            )

        # File still has only the good NPC
        entities = list_entities(EntityType.NPC, layer_dir)
        assert list(entities.keys()) == ["good"]

    def test_invalid_update_no_write(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        create_entity(EntityType.NPC, "npc", _make_npc_data(hp=10), layer_dir)

        with pytest.raises(ValidationError):
            update_entity(
                EntityType.NPC,
                "npc",
                {"name": {"en": "X"}, "race": "not_a_real_race"},
                layer_dir,
            )

        # HP unchanged
        npc = get_entity(EntityType.NPC, "npc", layer_dir)
        assert npc.hp == 10


# ---------------------------------------------------------------------------
# Catalog CRUD tests
# ---------------------------------------------------------------------------


class TestCatalogEntryRoundTrip:
    """Test 7: create → get round-trip for catalog entries."""

    def test_monster_catalog_round_trip(self, tmp_path: Path) -> None:
        data = _make_monster_catalog_data()

        result = create_catalog_entry(EntityType.MONSTER_CATALOG, "test_monster", data, tmp_path)
        assert isinstance(result, MonsterTemplateContent)
        assert result.hp == 15

        fetched = get_catalog_entry(EntityType.MONSTER_CATALOG, "test_monster", tmp_path)
        assert isinstance(fetched, MonsterTemplateContent)
        assert fetched.hp == 15

    def test_item_catalog_round_trip(self, tmp_path: Path) -> None:
        data = _make_item_catalog_data()

        result = create_catalog_entry(EntityType.ITEM_CATALOG, "test_sword", data, tmp_path)
        assert isinstance(result, ItemContent)

        fetched = get_catalog_entry(EntityType.ITEM_CATALOG, "test_sword", tmp_path)
        assert isinstance(fetched, ItemContent)
        assert fetched.name == "Test Sword"


class TestCatalogEntryUpdateDelete:
    """Test 8: update + delete for catalog entries."""

    def test_update_catalog_entry(self, tmp_path: Path) -> None:
        create_catalog_entry(
            EntityType.MONSTER_CATALOG,
            "gobbo",
            _make_monster_catalog_data(hp=7),
            tmp_path,
        )

        updated = update_catalog_entry(
            EntityType.MONSTER_CATALOG,
            "gobbo",
            _make_monster_catalog_data(hp=20),
            tmp_path,
        )
        assert updated.hp == 20

        fetched = get_catalog_entry(EntityType.MONSTER_CATALOG, "gobbo", tmp_path)
        assert fetched.hp == 20

    def test_delete_catalog_entry(self, tmp_path: Path) -> None:
        create_catalog_entry(
            EntityType.MONSTER_CATALOG,
            "gobbo",
            _make_monster_catalog_data(),
            tmp_path,
        )

        delete_catalog_entry(EntityType.MONSTER_CATALOG, "gobbo", tmp_path)

        with pytest.raises(KeyError):
            get_catalog_entry(EntityType.MONSTER_CATALOG, "gobbo", tmp_path)


# ---------------------------------------------------------------------------
# EntityRegistry coverage
# ---------------------------------------------------------------------------


class TestEntityRegistryCoverage:
    """Test 9: every EntityType resolves to a valid registry entry."""

    def test_all_entity_types_have_registry_entries(self) -> None:
        for et in EntityType:
            entry = get_registry_entry(et)
            assert entry.schema is not None
            assert issubclass(entry.schema, object)

    def test_layer_entity_types_have_section(self) -> None:
        layer_types = [
            EntityType.REGION,
            EntityType.LOCATION,
            EntityType.NATION,
            EntityType.SETTLEMENT,
            EntityType.NPC,
            EntityType.SQUAD,
            EntityType.MONSTER_TEMPLATE,
        ]
        for et in layer_types:
            entry = get_registry_entry(et)
            assert entry.layer_type is not None
            assert entry.section is not None

    def test_catalog_entity_types_have_catalog_dir(self) -> None:
        catalog_types = [EntityType.MONSTER_CATALOG, EntityType.ITEM_CATALOG]
        for et in catalog_types:
            entry = get_registry_entry(et)
            assert entry.catalog_dir is not None

    def test_registry_maps_to_correct_models(self) -> None:
        assert get_registry_entry(EntityType.NPC).schema is NpcContent
        assert get_registry_entry(EntityType.REGION).schema is RegionContent
        assert get_registry_entry(EntityType.SETTLEMENT).schema is SettlementContent
        assert get_registry_entry(EntityType.MONSTER_CATALOG).schema is MonsterTemplateContent
        assert get_registry_entry(EntityType.ITEM_CATALOG).schema is ItemContent


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_get_nonexistent_entity_raises(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        with pytest.raises(KeyError):
            get_entity(EntityType.NPC, "nonexistent", layer_dir)

    def test_delete_nonexistent_entity_raises(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        with pytest.raises(KeyError):
            delete_entity(EntityType.NPC, "nonexistent", layer_dir)

    def test_update_nonexistent_entity_raises(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        with pytest.raises(KeyError):
            update_entity(EntityType.NPC, "nonexistent", _make_npc_data(), layer_dir)

    def test_get_nonexistent_catalog_entry_raises(self, tmp_path: Path) -> None:
        with pytest.raises(KeyError):
            get_catalog_entry(EntityType.MONSTER_CATALOG, "nonexistent", tmp_path)

    def test_list_entities_empty_file(self, tmp_path: Path) -> None:
        layer_dir = _make_layer_dir(tmp_path, "entities")
        result = list_entities(EntityType.NPC, layer_dir)
        assert result == {}

    def test_settlement_crud(self, tmp_path: Path) -> None:
        """Verify CRUD works for a non-NPC layer entity type."""
        layer_dir = _make_layer_dir(tmp_path, "settlements")
        data = _make_settlement_data()
        created = create_entity(EntityType.SETTLEMENT, "testville", data, layer_dir)
        assert isinstance(created, SettlementContent)
        assert created.population == 200

        fetched = get_entity(EntityType.SETTLEMENT, "testville", layer_dir)
        assert fetched.population == 200
