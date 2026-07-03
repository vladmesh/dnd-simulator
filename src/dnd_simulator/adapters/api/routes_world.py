from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.adapters.api.schemas import (
    AssembleWorldRequest,
    CreateWorldRequest,
    ForkWorldRequest,
    LayerFileResponse,
    LayerFilesResponse,
    LayerInfo,
    MessageResponse,
    TemplateListItem,
    UpdateLayerFileRequest,
    WorldListItem,
    WorldManifestResponse,
)
from dnd_simulator.content_loader.manifest import LayerType
from dnd_simulator.i18n import _

router = APIRouter(prefix="/api/master", tags=["world-management"])


# -- Library (template catalog) --


@router.get("/library/{layer_type}", response_model=list[TemplateListItem])
def list_library_templates(layer_type: LayerType, geography: str | None = None) -> list[TemplateListItem]:
    """List available templates from the library for a given layer type."""
    service = get_service()
    if geography:
        templates = service.list_compatible_library_templates(layer_type, selected={"geography": geography})
    else:
        templates = service.list_library_templates(layer_type)
    return [
        TemplateListItem(
            slug=t.slug,
            name=t.name,
            layer_type=t.layer_type.value,
            version=t.version,
            description=t.description,
            tags=list(t.tags),
            requires_geography=list(t.requires_geography),
        )
        for t in templates
    ]


# -- Worlds (templates) --


@router.get("/worlds", response_model=list[WorldListItem])
def list_worlds(lang: str = "en") -> list[WorldListItem]:
    """List available world templates."""
    service = get_service()
    worlds = service.list_worlds(lang=lang)
    base_worlds = service.base_worlds
    return [
        WorldListItem(
            id=str(w["id"]),
            name=str(w["name"]),
            description=str(w["description"]),
            complete=bool(w["complete"]),
            editable=str(w["id"]) not in base_worlds,
        )
        for w in worlds
    ]


@router.post("/worlds", response_model=WorldListItem, status_code=201)
def create_world(req: CreateWorldRequest) -> WorldListItem:
    """Create a new empty world (no layers defined)."""
    service = get_service()
    try:
        result = service.create_empty_world(
            world_id=req.id,
            name=req.name,
            description=req.description,
            default_player_faction=req.default_player_faction,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=_("World '{}' already exists").format(req.id)) from exc
    return WorldListItem(
        id=result["id"],
        name=result["name"],
        description=req.description,
        complete=False,
        editable=True,
    )


@router.post("/worlds/assemble", response_model=WorldListItem, status_code=201)
def assemble_world(req: AssembleWorldRequest) -> WorldListItem:
    """Assemble a new world from library templates."""
    service = get_service()
    try:
        result = service.assemble_world(
            world_id=req.id,
            name=req.name,
            description=req.description,
            layer_selections=req.layer_selections,
            default_player_faction=req.default_player_faction,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=_("World '{}' already exists").format(req.id)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WorldListItem(
        id=result["id"],
        name=result["name"],
        description=req.description,
        complete=True,
        editable=True,
    )


@router.post("/worlds/{world_id}/fork", response_model=WorldListItem, status_code=201)
def fork_world(world_id: str, req: ForkWorldRequest) -> WorldListItem:
    """Fork a world, optionally truncating layers from a given type upward."""
    service = get_service()
    result = service.fork_world(
        source_world_id=world_id,
        new_world_id=req.new_id,
        from_layer=req.from_layer,
    )
    return WorldListItem(
        id=str(result["id"]),
        name=str(result["name"]),
        description="",
        complete=bool(result["complete"]),
        editable=True,
    )


@router.delete("/worlds/{world_id}", response_model=MessageResponse)
def delete_world(world_id: str) -> MessageResponse:
    """Delete a world (blocked for base worlds and worlds with active sessions)."""
    service = get_service()
    try:
        service.delete_world(world_id)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MessageResponse(message=_("World '{}' deleted").format(world_id))


@router.get("/worlds/{world_id}")
def get_world_template(world_id: str) -> dict[str, object]:
    """Get full world template contents (YAML on disk, not a session)."""
    service = get_service()
    try:
        return service.get_world_template(world_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_("World '{}' not found").format(world_id)) from exc


@router.get("/worlds/{world_id}/manifest", response_model=WorldManifestResponse)
def get_world_manifest(world_id: str, lang: str = "en") -> WorldManifestResponse:
    """Get world manifest — layer sources, templates, versions."""
    service = get_service()
    try:
        data = service.get_world_manifest(world_id, lang=lang)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=_("World '{}' not found").format(world_id)) from exc
    layers_raw = data["layers"]
    assert isinstance(layers_raw, list)
    return WorldManifestResponse(
        world_id=str(data["world_id"]),
        name=str(data["name"]),
        layers=[LayerInfo(**ly) for ly in layers_raw],
    )


@router.get("/worlds/{world_id}/layers/{layer_type}/files", response_model=LayerFilesResponse)
def get_layer_files(world_id: str, layer_type: LayerType) -> LayerFilesResponse:
    """List all data YAML files in a layer with their contents."""
    service = get_service()
    files = service.get_layer_files(world_id, layer_type)
    return LayerFilesResponse(files=files)


@router.get("/worlds/{world_id}/layers/{layer_type}/files/{filename}", response_model=LayerFileResponse)
def get_layer_file(world_id: str, layer_type: LayerType, filename: str) -> LayerFileResponse:
    """Read a single YAML file from a layer."""
    service = get_service()
    try:
        content = service.get_layer_file(world_id, layer_type, filename)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return LayerFileResponse(filename=filename, content=content)


@router.put("/worlds/{world_id}/layers/{layer_type}/files/{filename}", response_model=MessageResponse)
def update_layer_file(
    world_id: str, layer_type: LayerType, filename: str, body: UpdateLayerFileRequest
) -> MessageResponse:
    """Write content to a YAML file in a custom layer."""
    service = get_service()
    try:
        service.update_layer_file(world_id, layer_type, filename, body.content)
    except ValueError as exc:
        detail = str(exc)
        status = 422 if "YAML" in detail else 400
        raise HTTPException(status_code=status, detail=detail) from exc
    return MessageResponse(message=_("File '{}' updated").format(filename))


@router.post("/worlds/{world_id}/layers/{layer_type}/scaffold", response_model=MessageResponse, status_code=201)
def scaffold_layer(world_id: str, layer_type: LayerType) -> MessageResponse:
    """Create a minimal valid custom layer from scratch."""
    service = get_service()
    try:
        service.scaffold_layer(world_id, layer_type)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MessageResponse(message=_("Layer '{}' scaffolded in world '{}'").format(layer_type.value, world_id))


@router.post("/worlds/{world_id}/fork/{layer_type}", response_model=MessageResponse)
def fork_world_layer(world_id: str, layer_type: LayerType) -> MessageResponse:
    """Fork a library template layer into the world's custom directory."""
    service = get_service()
    try:
        service.fork_layer(world_id, layer_type)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MessageResponse(message=_("Layer '{}' forked to custom in world '{}'").format(layer_type.value, world_id))
