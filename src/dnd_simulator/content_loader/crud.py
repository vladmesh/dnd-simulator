"""Content CRUD — generic create/read/update/delete for layer entities and catalog entries.

EntityRegistry maps EntityType → storage metadata (layer_type, yaml section, Pydantic schema).
Generic CRUD functions use the registry to locate, validate, and persist entities.

Two storage patterns:
- **Layer entities** — keyed dict in a YAML file (e.g. npcs.yaml: {edgar: {...}, marta: {...}}).
- **Catalog entries** — one YAML file per entry in a directory (e.g. catalogs/monsters/goblin.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from dnd_simulator.content_loader.schemas import (
    ItemContent,
    LocationContent,
    MonsterTemplateContent,
    MonsterTemplateEntryContent,
    NationContent,
    NpcContent,
    RegionContent,
    SettlementContent,
    SquadContent,
)
from dnd_simulator.content_loader.utils import _read_yaml, _write_yaml

# ---------------------------------------------------------------------------
# EntityType enum
# ---------------------------------------------------------------------------


class EntityType(StrEnum):
    """All content entity types — both layer entities and catalog entries."""

    # Layer entities (keyed dict in a YAML file within a layer directory)
    REGION = "region"
    LOCATION = "location"
    NATION = "nation"
    SETTLEMENT = "settlement"
    NPC = "npc"
    SQUAD = "squad"
    MONSTER_TEMPLATE = "monster_template"

    # Catalog entries (one file per entry in a catalog directory)
    MONSTER_CATALOG = "monster_catalog"
    ITEM_CATALOG = "item_catalog"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RegistryEntry:
    """Metadata for locating and validating an entity type.

    For layer entities: layer_type + section identify the YAML file and key structure.
    For catalog entries: catalog_dir identifies the directory name under catalogs/.
    """

    schema: type[BaseModel]
    layer_type: str | None = None
    section: str | None = None
    subsection: str | None = None  # e.g. "templates" for monsters.yaml nested structure
    catalog_dir: str | None = None


_REGISTRY: dict[EntityType, RegistryEntry] = {
    EntityType.REGION: RegistryEntry(
        schema=RegionContent,
        layer_type="geography",
        section="regions",
    ),
    EntityType.LOCATION: RegistryEntry(
        schema=LocationContent,
        layer_type="geography",
        section="locations",
    ),
    EntityType.NATION: RegistryEntry(
        schema=NationContent,
        layer_type="politics",
        section="nations",
    ),
    EntityType.SETTLEMENT: RegistryEntry(
        schema=SettlementContent,
        layer_type="settlements",
        section="settlements",
    ),
    EntityType.NPC: RegistryEntry(
        schema=NpcContent,
        layer_type="entities",
        section="npcs",
    ),
    EntityType.SQUAD: RegistryEntry(
        schema=SquadContent,
        layer_type="ecology",
        section="squads",
    ),
    EntityType.MONSTER_TEMPLATE: RegistryEntry(
        schema=MonsterTemplateEntryContent,
        layer_type="ecology",
        section="monsters",
        subsection="templates",
    ),
    EntityType.MONSTER_CATALOG: RegistryEntry(
        schema=MonsterTemplateContent,
        catalog_dir="monsters",
    ),
    EntityType.ITEM_CATALOG: RegistryEntry(
        schema=ItemContent,
        catalog_dir="items",
    ),
}


def get_registry_entry(entity_type: EntityType) -> RegistryEntry:
    """Look up registry metadata for an entity type."""
    return _REGISTRY[entity_type]


# ---------------------------------------------------------------------------
# Layer entity CRUD
# ---------------------------------------------------------------------------


def _yaml_path(entry: RegistryEntry, layer_dir: Path) -> Path:
    """Resolve the YAML file path for a layer entity type."""
    return layer_dir / f"{entry.section}.yaml"


def _read_entities_dict(entry: RegistryEntry, layer_dir: Path) -> dict[str, Any]:
    """Read the raw dict of entities from the YAML file, handling subsections."""
    raw = _read_yaml(_yaml_path(entry, layer_dir))
    if entry.subsection:
        return raw.get(entry.subsection, {}) or {}
    return raw


def _write_entities_dict(
    entry: RegistryEntry,
    layer_dir: Path,
    entities: dict[str, Any],
) -> None:
    """Write the entities dict back to the YAML file, preserving subsections."""
    path = _yaml_path(entry, layer_dir)
    if entry.subsection:
        raw = _read_yaml(path)
        raw[entry.subsection] = entities
        _write_yaml(path, raw)
    else:
        _write_yaml(path, entities)


def list_entities(entity_type: EntityType, layer_dir: Path) -> dict[str, BaseModel]:
    """List all entities of a given type from a layer directory.

    Returns dict of entity_id → validated Pydantic model.
    """
    entry = _REGISTRY[entity_type]
    raw = _read_entities_dict(entry, layer_dir)
    return {eid: entry.schema.model_validate(edata) for eid, edata in raw.items()}


def get_entity(entity_type: EntityType, entity_id: str, layer_dir: Path) -> BaseModel:
    """Get a single entity by ID. Raises KeyError if not found."""
    entry = _REGISTRY[entity_type]
    raw = _read_entities_dict(entry, layer_dir)
    if entity_id not in raw:
        raise KeyError(f"{entity_type.value} '{entity_id}' not found in {_yaml_path(entry, layer_dir)}")
    return entry.schema.model_validate(raw[entity_id])


def create_entity(
    entity_type: EntityType,
    entity_id: str,
    data: dict[str, object],
    layer_dir: Path,
) -> BaseModel:
    """Create a new entity. Validates before writing. Raises ValueError on duplicate ID."""
    entry = _REGISTRY[entity_type]

    # Validate first — no disk writes on failure
    validated = entry.schema.model_validate(data)

    raw = _read_entities_dict(entry, layer_dir)
    if entity_id in raw:
        raise ValueError(f"{entity_type.value} '{entity_id}' already exists")

    raw[entity_id] = validated.model_dump(mode="json", by_alias=True)
    _write_entities_dict(entry, layer_dir, raw)
    return validated


def update_entity(
    entity_type: EntityType,
    entity_id: str,
    data: dict[str, object],
    layer_dir: Path,
) -> BaseModel:
    """Update an existing entity. Validates before writing. Raises KeyError if not found."""
    entry = _REGISTRY[entity_type]

    # Validate first
    validated = entry.schema.model_validate(data)

    raw = _read_entities_dict(entry, layer_dir)
    if entity_id not in raw:
        raise KeyError(f"{entity_type.value} '{entity_id}' not found")

    raw[entity_id] = validated.model_dump(mode="json", by_alias=True)
    _write_entities_dict(entry, layer_dir, raw)
    return validated


def delete_entity(
    entity_type: EntityType,
    entity_id: str,
    layer_dir: Path,
) -> None:
    """Delete an entity by ID. Raises KeyError if not found."""
    entry = _REGISTRY[entity_type]
    raw = _read_entities_dict(entry, layer_dir)
    if entity_id not in raw:
        raise KeyError(f"{entity_type.value} '{entity_id}' not found")

    del raw[entity_id]
    _write_entities_dict(entry, layer_dir, raw)


# ---------------------------------------------------------------------------
# Catalog CRUD
# ---------------------------------------------------------------------------


def _catalog_path(entry: RegistryEntry, entry_id: str, content_root: Path) -> Path:
    """Resolve path for a catalog entry YAML file."""
    assert entry.catalog_dir is not None
    return content_root / "catalogs" / entry.catalog_dir / f"{entry_id}.yaml"


def _catalog_dir_path(entry: RegistryEntry, content_root: Path) -> Path:
    """Resolve the catalog directory path."""
    assert entry.catalog_dir is not None
    return content_root / "catalogs" / entry.catalog_dir


def list_catalog_entries(entity_type: EntityType, content_root: Path) -> dict[str, BaseModel]:
    """List all catalog entries of a given type.

    Returns dict of entry_id → validated Pydantic model.
    """
    entry = _REGISTRY[entity_type]
    catalog_dir = _catalog_dir_path(entry, content_root)
    if not catalog_dir.exists():
        return {}

    result: dict[str, BaseModel] = {}
    for yaml_path in sorted(catalog_dir.glob("*.yaml")):
        raw = _read_yaml(yaml_path)
        result[yaml_path.stem] = entry.schema.model_validate(raw)
    return result


def get_catalog_entry(entity_type: EntityType, entry_id: str, content_root: Path) -> BaseModel:
    """Get a single catalog entry by ID. Raises KeyError if not found."""
    entry = _REGISTRY[entity_type]
    path = _catalog_path(entry, entry_id, content_root)
    if not path.exists():
        raise KeyError(f"{entity_type.value} '{entry_id}' not found at {path}")
    return entry.schema.model_validate(_read_yaml(path))


def create_catalog_entry(
    entity_type: EntityType,
    entry_id: str,
    data: dict[str, object],
    content_root: Path,
) -> BaseModel:
    """Create a new catalog entry. Validates before writing. Raises ValueError on duplicate."""
    entry = _REGISTRY[entity_type]
    path = _catalog_path(entry, entry_id, content_root)

    # Validate first
    validated = entry.schema.model_validate(data)

    if path.exists():
        raise ValueError(f"{entity_type.value} '{entry_id}' already exists at {path}")

    path.parent.mkdir(parents=True, exist_ok=True)
    _write_yaml(path, validated.model_dump(mode="json", by_alias=True))
    return validated


def update_catalog_entry(
    entity_type: EntityType,
    entry_id: str,
    data: dict[str, object],
    content_root: Path,
) -> BaseModel:
    """Update an existing catalog entry. Validates before writing. Raises KeyError if not found."""
    entry = _REGISTRY[entity_type]
    path = _catalog_path(entry, entry_id, content_root)

    # Validate first
    validated = entry.schema.model_validate(data)

    if not path.exists():
        raise KeyError(f"{entity_type.value} '{entry_id}' not found at {path}")

    _write_yaml(path, validated.model_dump(mode="json", by_alias=True))
    return validated


def delete_catalog_entry(
    entity_type: EntityType,
    entry_id: str,
    content_root: Path,
) -> None:
    """Delete a catalog entry. Raises KeyError if not found."""
    entry = _REGISTRY[entity_type]
    path = _catalog_path(entry, entry_id, content_root)
    if not path.exists():
        raise KeyError(f"{entity_type.value} '{entry_id}' not found at {path}")
    path.unlink()
