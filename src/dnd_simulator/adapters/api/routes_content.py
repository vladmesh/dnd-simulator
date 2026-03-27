"""Content CRUD API — entity-level CRUD for world layers and catalogs."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import ValidationError

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.content_loader.crud import EntityType, get_registry_entry

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


# ---------------------------------------------------------------------------
# World entity endpoints
# ---------------------------------------------------------------------------


@content_router.get("/worlds/{world_id}/entities/{entity_type}")
def list_entities(world_id: str, entity_type: str) -> list[dict[str, Any]]:
    et = _parse_entity_type(entity_type)
    if et not in _LAYER_ENTITY_TYPES:
        raise HTTPException(
            status_code=HTTPStatus.BAD_REQUEST,
            detail=f"{et.value} is a catalog type, not a layer entity",
        )
    try:
        return get_service().list_content_entities(world_id, et)
    except FileNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e


@content_router.get("/worlds/{world_id}/entities/{entity_type}/{entity_id}")
def get_entity(world_id: str, entity_type: str, entity_id: str) -> dict[str, Any]:
    et = _parse_entity_type(entity_type)
    if et not in _LAYER_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is a catalog type")
    try:
        return get_service().get_content_entity(world_id, et, entity_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e


@content_router.post(
    "/worlds/{world_id}/entities/{entity_type}/{entity_id}",
    status_code=HTTPStatus.CREATED,
)
def create_entity(world_id: str, entity_type: str, entity_id: str, body: dict[str, Any]) -> dict[str, Any]:
    et = _parse_entity_type(entity_type)
    if et not in _LAYER_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is a catalog type")
    try:
        return get_service().create_content_entity(world_id, et, entity_id, body)
    except FileNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e


@content_router.put("/worlds/{world_id}/entities/{entity_type}/{entity_id}")
def update_entity(world_id: str, entity_type: str, entity_id: str, body: dict[str, Any]) -> dict[str, Any]:
    et = _parse_entity_type(entity_type)
    if et not in _LAYER_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is a catalog type")
    try:
        return get_service().update_content_entity(world_id, et, entity_id, body)
    except FileNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e


@content_router.delete("/worlds/{world_id}/entities/{entity_type}/{entity_id}")
def delete_entity(world_id: str, entity_type: str, entity_id: str) -> dict[str, str]:
    et = _parse_entity_type(entity_type)
    if et not in _LAYER_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is a catalog type")
    try:
        get_service().delete_content_entity(world_id, et, entity_id)
        return {"message": "deleted"}
    except FileNotFoundError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e


# ---------------------------------------------------------------------------
# Catalog endpoints
# ---------------------------------------------------------------------------


@content_router.get("/catalogs/{catalog_type}")
def list_catalog_entries(catalog_type: str) -> list[dict[str, Any]]:
    et = _parse_entity_type(catalog_type)
    if et not in _CATALOG_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is not a catalog type")
    return get_service().list_catalog_entries(et)


@content_router.get("/catalogs/{catalog_type}/{entry_id}")
def get_catalog_entry(catalog_type: str, entry_id: str) -> dict[str, Any]:
    et = _parse_entity_type(catalog_type)
    if et not in _CATALOG_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is not a catalog type")
    try:
        return get_service().get_catalog_entry(et, entry_id)
    except KeyError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e


@content_router.post("/catalogs/{catalog_type}/{entry_id}", status_code=HTTPStatus.CREATED)
def create_catalog_entry(catalog_type: str, entry_id: str, body: dict[str, Any]) -> dict[str, Any]:
    et = _parse_entity_type(catalog_type)
    if et not in _CATALOG_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is not a catalog type")
    try:
        return get_service().create_catalog_entry(et, entry_id, body)
    except ValidationError as e:
        raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e


@content_router.put("/catalogs/{catalog_type}/{entry_id}")
def update_catalog_entry(catalog_type: str, entry_id: str, body: dict[str, Any]) -> dict[str, Any]:
    et = _parse_entity_type(catalog_type)
    if et not in _CATALOG_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is not a catalog type")
    try:
        return get_service().update_catalog_entry(et, entry_id, body)
    except KeyError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(status_code=HTTPStatus.UNPROCESSABLE_ENTITY, detail=str(e)) from e


@content_router.delete("/catalogs/{catalog_type}/{entry_id}")
def delete_catalog_entry(catalog_type: str, entry_id: str) -> dict[str, str]:
    et = _parse_entity_type(catalog_type)
    if et not in _CATALOG_ENTITY_TYPES:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=f"{et.value} is not a catalog type")
    try:
        get_service().delete_catalog_entry(et, entry_id)
        return {"message": "deleted"}
    except KeyError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
