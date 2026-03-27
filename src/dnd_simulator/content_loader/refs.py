"""Cross-layer reference data for dropdown fields.

Each RefType maps to a specific entity type + layer. The ref resolver
reads entities from the appropriate layer and returns ID+name pairs.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path
from typing import Any

from dnd_simulator.content_loader.crud import EntityType, list_entities
from dnd_simulator.content_loader.manifest import resolve_manifest
from dnd_simulator.content_loader.utils import resolve_text


class RefType(StrEnum):
    LOCATIONS = "locations"
    REGIONS = "regions"
    SETTLEMENTS = "settlements"
    NATIONS = "nations"
    FACTIONS = "factions"


# Map ref types to entity types for simple cases
_REF_TO_ENTITY: dict[RefType, EntityType] = {
    RefType.LOCATIONS: EntityType.LOCATION,
    RefType.REGIONS: EntityType.REGION,
    RefType.SETTLEMENTS: EntityType.SETTLEMENT,
    RefType.NATIONS: EntityType.NATION,
}


def get_ref_entries(
    ref_type: RefType,
    world_id: str,
    content_dir: Path,
    lang: str = "en",
) -> list[dict[str, str]]:
    """Return ID+name pairs for a ref type from a world's layers."""
    world_path = content_dir / "worlds" / world_id
    if not world_path.is_dir():
        raise FileNotFoundError(f"World '{world_id}' not found")

    if ref_type == RefType.FACTIONS:
        return _collect_factions(world_path, content_dir, lang)

    entity_type = _REF_TO_ENTITY[ref_type]
    layer_paths = resolve_manifest(world_path, content_dir)

    from dnd_simulator.content_loader.crud import get_registry_entry

    entry = get_registry_entry(entity_type)
    assert entry.layer_type is not None
    layer_dir = layer_paths[entry.layer_type]

    entities = list_entities(entity_type, layer_dir)
    return [{"id": eid, "name": _resolve_name(model, lang)} for eid, model in entities.items()]


def _resolve_name(model: Any, lang: str) -> str:
    """Extract the localized name from a model."""
    name = getattr(model, "name", None)
    if name is None:
        return ""
    return resolve_text(name, lang)


def _collect_factions(
    world_path: Path,
    content_dir: Path,
    lang: str,
) -> list[dict[str, str]]:
    """Collect unique faction values across NPCs, squads, and monster templates."""
    layer_paths = resolve_manifest(world_path, content_dir)

    factions: set[str] = set()

    # NPCs
    for _eid, model in list_entities(EntityType.NPC, layer_paths["entities"]).items():
        val = getattr(model, "faction", "")
        if val:
            factions.add(val)

    # Squads
    if "ecology" in layer_paths:
        for _eid, model in list_entities(EntityType.SQUAD, layer_paths["ecology"]).items():
            val = getattr(model, "faction", "")
            if val:
                factions.add(val)

    # Monster templates
    if "ecology" in layer_paths:
        for _eid, model in list_entities(EntityType.MONSTER_TEMPLATE, layer_paths["ecology"]).items():
            val = getattr(model, "faction", "")
            if val:
                factions.add(val)

    return [{"id": f, "name": f} for f in sorted(factions)]
