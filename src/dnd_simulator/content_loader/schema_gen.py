"""JSON Schema generation for content entity types.

Wraps Pydantic's model_json_schema() with enrichments:
- x-ref-type annotations on cross-layer reference fields
- Human-readable labels for entity types
"""

from __future__ import annotations

from typing import Any

from dnd_simulator.content_loader.crud import EntityType, get_registry_entry

# ---------------------------------------------------------------------------
# Cross-ref metadata: field_name → ref_type for each entity type
# ---------------------------------------------------------------------------

_REF_ANNOTATIONS: dict[EntityType, dict[str, str]] = {
    EntityType.NPC: {
        "start_location": "locations",
        "settlement_id": "settlements",
        "faction": "factions",
    },
    EntityType.SQUAD: {
        "start_location": "locations",
        "faction": "factions",
    },
    EntityType.LOCATION: {
        "region": "regions",
        "settlement": "settlements",
    },
    EntityType.SETTLEMENT: {
        "region": "regions",
    },
    EntityType.NATION: {},
    EntityType.REGION: {},
    EntityType.MONSTER_TEMPLATE: {
        "faction": "factions",
    },
    EntityType.MONSTER_CATALOG: {},
    EntityType.ITEM_CATALOG: {},
}

# Human-readable labels for entity types
_LABELS: dict[EntityType, str] = {
    EntityType.REGION: "Region",
    EntityType.LOCATION: "Location",
    EntityType.NATION: "Nation",
    EntityType.SETTLEMENT: "Settlement",
    EntityType.NPC: "NPC",
    EntityType.SQUAD: "Squad",
    EntityType.MONSTER_TEMPLATE: "Monster Template",
    EntityType.MONSTER_CATALOG: "Monster (Catalog)",
    EntityType.ITEM_CATALOG: "Item (Catalog)",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def get_entity_schema(entity_type: EntityType) -> dict[str, Any]:
    """Return enriched JSON Schema for an entity type.

    Adds x-ref-type to properties that reference other entities.
    """
    entry = get_registry_entry(entity_type)
    schema: dict[str, Any] = entry.schema.model_json_schema(by_alias=True)

    # Inject x-ref-type annotations into properties
    refs = _REF_ANNOTATIONS.get(entity_type, {})
    properties: dict[str, Any] = schema.get("properties", {})
    for field_name, ref_type in refs.items():
        if field_name in properties:
            properties[field_name]["x-ref-type"] = ref_type

    return schema


def list_entity_schemas() -> list[dict[str, str]]:
    """Return all entity type names with human-readable labels."""
    return [{"entity_type": et.value, "label": _LABELS[et]} for et in EntityType]
