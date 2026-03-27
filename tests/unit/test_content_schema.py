"""Tests for JSON Schema generation and cross-layer refs — unit level."""

from __future__ import annotations

from dnd_simulator.content_loader.crud import EntityType
from dnd_simulator.content_loader.schema_gen import (
    get_entity_schema,
    list_entity_schemas,
)
from dnd_simulator.core.character import NpcRole, Race

# ---------------------------------------------------------------------------
# Schema contains all fields
# ---------------------------------------------------------------------------


class TestNpcSchemaFields:
    """get_entity_schema('npc') returns a JSON Schema with all NpcContent fields."""

    def test_npc_schema_has_core_fields(self) -> None:
        schema = get_entity_schema(EntityType.NPC)
        props = schema["properties"]
        for field in ("name", "race", "role", "start_location", "hp", "ac", "faction"):
            assert field in props, f"Missing property: {field}"

    def test_npc_schema_has_class_via_alias(self) -> None:
        """NPC class field uses alias 'class' in the schema."""
        schema = get_entity_schema(EntityType.NPC)
        props = schema["properties"]
        assert "class" in props, "Expected alias 'class' in schema properties"


# ---------------------------------------------------------------------------
# Enum values in schema
# ---------------------------------------------------------------------------


class TestEnumValuesInSchema:
    """Enum constraints come from Pydantic models, not hardcoded strings."""

    def test_race_enum_values(self) -> None:
        schema = get_entity_schema(EntityType.NPC)
        race_prop = schema["properties"]["race"]
        # May be an allOf/$ref — resolve from $defs if needed
        enum_values = _resolve_enum(schema, race_prop)
        for r in Race:
            assert r.value in enum_values, f"Missing race: {r.value}"

    def test_role_enum_values(self) -> None:
        schema = get_entity_schema(EntityType.NPC)
        role_prop = schema["properties"]["role"]
        enum_values = _resolve_enum(schema, role_prop)
        for role in NpcRole:
            assert role.value in enum_values, f"Missing role: {role.value}"


def _resolve_enum(schema: dict[str, object], prop: dict[str, object]) -> list[str]:
    """Resolve enum values from a property, following $ref if needed."""
    if "enum" in prop:
        return prop["enum"]  # type: ignore[return-value]
    if "allOf" in prop:
        for item in prop["allOf"]:  # type: ignore[union-attr]
            resolved = _resolve_ref(schema, item)  # type: ignore[arg-type]
            if "enum" in resolved:
                return resolved["enum"]  # type: ignore[return-value]
    if "$ref" in prop:
        resolved = _resolve_ref(schema, prop)
        if "enum" in resolved:
            return resolved["enum"]  # type: ignore[return-value]
    # Check for default wrapping pattern
    if "default" in prop and "allOf" not in prop and "$ref" not in prop:
        raise AssertionError(f"Property has default but no enum/ref: {prop}")
    raise AssertionError(f"Cannot resolve enum from property: {prop}")


def _resolve_ref(schema: dict[str, object], prop: dict[str, object]) -> dict[str, object]:
    """Resolve a $ref to the actual definition."""
    ref = prop.get("$ref")
    if not ref:
        return prop
    assert isinstance(ref, str)
    # "#/$defs/Race" → ["$defs", "Race"]
    parts = ref.lstrip("#/").split("/")
    result: object = schema
    for part in parts:
        assert isinstance(result, dict)
        result = result[part]
    assert isinstance(result, dict)
    return result


# ---------------------------------------------------------------------------
# Defaults in schema
# ---------------------------------------------------------------------------


class TestDefaultsInSchema:
    """Default values from Pydantic models appear in the schema."""

    def test_npc_defaults(self) -> None:
        schema = get_entity_schema(EntityType.NPC)
        props = schema["properties"]
        assert props["hp"]["default"] == 4
        assert props["ac"]["default"] == 10
        assert props["ai"]["default"] == "rule_based"


# ---------------------------------------------------------------------------
# Cross-ref annotations
# ---------------------------------------------------------------------------


class TestCrossRefAnnotations:
    """Fields that reference other entities have x-ref-type."""

    def test_npc_start_location_ref(self) -> None:
        schema = get_entity_schema(EntityType.NPC)
        assert schema["properties"]["start_location"]["x-ref-type"] == "locations"

    def test_npc_settlement_id_ref(self) -> None:
        schema = get_entity_schema(EntityType.NPC)
        assert schema["properties"]["settlement_id"]["x-ref-type"] == "settlements"

    def test_npc_faction_ref(self) -> None:
        schema = get_entity_schema(EntityType.NPC)
        assert schema["properties"]["faction"]["x-ref-type"] == "factions"


# ---------------------------------------------------------------------------
# Schema list
# ---------------------------------------------------------------------------


class TestSchemaList:
    """list_entity_schemas returns all entity types with labels."""

    def test_lists_all_types(self) -> None:
        schemas = list_entity_schemas()
        type_names = {s["entity_type"] for s in schemas}
        for et in EntityType:
            assert et.value in type_names, f"Missing entity type: {et.value}"

    def test_has_label(self) -> None:
        schemas = list_entity_schemas()
        for s in schemas:
            assert "label" in s
            assert isinstance(s["label"], str)
            assert len(s["label"]) > 0
