"""Content CRUD API — entity-level CRUD for world layers and catalogs."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.content_loader.crud import EntityType, get_registry_entry
from dnd_simulator.content_loader.refs import RefType
from dnd_simulator.content_loader.schema_gen import get_entity_schema, list_entity_schemas

content_router = APIRouter(prefix="/api/master", tags=["content"])

# ---------------------------------------------------------------------------
# Layer entity types (those with layer_type in registry)
# ---------------------------------------------------------------------------

_LAYER_ENTITY_TYPES = frozenset(et for et in EntityType if get_registry_entry(et).layer_type is not None)

_CATALOG_ENTITY_TYPES = frozenset(et for et in EntityType if get_registry_entry(et).catalog_dir is not None)


def _parse_entity_type(raw: str) -> EntityType:
    """Parse and validate an entity type string."""
    try:
        return EntityType(raw)
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f"Unknown entity type: {raw!r}. Valid: {[e.value for e in EntityType]}",
        ) from None


def _require_entity_type(raw: str, *, catalog: bool) -> EntityType:
    """Parse an entity type and enforce it belongs to the requested kind (layer vs catalog)."""
    et = _parse_entity_type(raw)
    if catalog and et not in _CATALOG_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is not a catalog type")
    if not catalog and et not in _LAYER_ENTITY_TYPES:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{et.value} is a catalog type, not a layer entity",
        )
    return et


# ---------------------------------------------------------------------------
# World entity endpoints
# ---------------------------------------------------------------------------


@content_router.get("/worlds/{world_id}/entities/{entity_type}")
def list_entities(world_id: str, entity_type: str) -> list[dict[str, Any]]:
    et = _require_entity_type(entity_type, catalog=False)
    return get_service().list_content_entities(world_id, et)


@content_router.get("/worlds/{world_id}/entities/{entity_type}/{entity_id}")
def get_entity(world_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
    et = _require_entity_type(entity_type, catalog=False)
    return get_service().get_content_entity(world_id, et, entity_id)


@content_router.post(
    "/worlds/{world_id}/entities/{entity_type}/{entity_id}",
    status_code=HTTPStatus.CREATED,
)
def create_entity(world_id: str, entity_type: str, entity_id: str, body: dict[str, Any]) -> dict[str, Any]:
    et = _require_entity_type(entity_type, catalog=False)
    try:
        return get_service().create_content_entity(world_id, et, entity_id, body)
    except ValidationError as e:
        raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e


@content_router.put("/worlds/{world_id}/entities/{entity_type}/{entity_id}")
def update_entity(world_id: str, entity_type: str, entity_id: str, body: dict[str, Any]) -> dict[str, Any]:
    et = _require_entity_type(entity_type, catalog=False)
    try:
        return get_service().update_content_entity(world_id, et, entity_id, body)
    except ValidationError as e:
        raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e


@content_router.delete("/worlds/{world_id}/entities/{entity_type}/{entity_id}")
def delete_entity(world_id: str, entity_type: str, entity_id: str) -> dict[str, str]:
    et = _require_entity_type(entity_type, catalog=False)
    try:
        get_service().delete_content_entity(world_id, et, entity_id)
        return {"message": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Catalog endpoints
# ---------------------------------------------------------------------------


@content_router.get("/catalogs/{catalog_type}")
def list_catalog_entries(catalog_type: str) -> list[dict[str, Any]]:
    et = _require_entity_type(catalog_type, catalog=True)
    return get_service().list_catalog_entries(et)


@content_router.get("/catalogs/{catalog_type}/{entry_id}")
def get_catalog_entry(catalog_type: str, entry_id: str) -> dict[str, Any]:
    et = _require_entity_type(catalog_type, catalog=True)
    return get_service().get_catalog_entry(et, entry_id)


@content_router.post("/catalogs/{catalog_type}/{entry_id}", status_code=HTTPStatus.CREATED)
def create_catalog_entry(catalog_type: str, entry_id: str, body: dict[str, Any]) -> dict[str, Any]:
    et = _require_entity_type(catalog_type, catalog=True)
    try:
        return get_service().create_catalog_entry(et, entry_id, body)
    except ValidationError as e:
        raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e


@content_router.put("/catalogs/{catalog_type}/{entry_id}")
def update_catalog_entry(catalog_type: str, entry_id: str, body: dict[str, Any]) -> dict[str, Any]:
    et = _require_entity_type(catalog_type, catalog=True)
    return get_service().update_catalog_entry(et, entry_id, body)


@content_router.delete("/catalogs/{catalog_type}/{entry_id}")
def delete_catalog_entry(catalog_type: str, entry_id: str) -> dict[str, str]:
    et = _require_entity_type(catalog_type, catalog=True)
    get_service().delete_catalog_entry(et, entry_id)
    return {"message": "deleted"}


# ---------------------------------------------------------------------------
# JSON Schema endpoints
# ---------------------------------------------------------------------------


@content_router.get("/schemas")
def list_schemas() -> list[dict[str, str]]:
    return list_entity_schemas()


@content_router.get("/schemas/{entity_type}")
def get_schema(entity_type: str) -> dict[str, Any]:
    et = _parse_entity_type(entity_type)
    return get_entity_schema(et)


# ---------------------------------------------------------------------------
# Cross-layer refs endpoints
# ---------------------------------------------------------------------------


def _parse_ref_type(raw: str) -> RefType:
    """Parse and validate a ref type string."""
    try:
        return RefType(raw)
    except ValueError:
        raise HTTPException(
            status_code=HTTPStatus.UNPROCESSABLE_ENTITY,
            detail=f"Unknown ref type: {raw!r}. Valid: {[r.value for r in RefType]}",
        ) from None


@content_router.get("/worlds/{world_id}/refs/{ref_type}")
def list_refs(world_id: str, ref_type: str) -> list[dict[str, str]]:
    rt = _parse_ref_type(ref_type)
    return get_service().list_refs(world_id, rt.value)
