from __future__ import annotations

from fastapi import APIRouter, HTTPException

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.adapters.api.schemas import (
    AdvanceTimeRequest,
    AssembleWorldRequest,
    CreateSessionRequest,
    CreateWorldRequest,
    CreatureResponse,
    ForkWorldRequest,
    GiveItemRequest,
    LayerFileResponse,
    LayerFilesResponse,
    LayerInfo,
    MessageResponse,
    PatchCreatureRequest,
    PatchNationRequest,
    PatchSettlementRequest,
    SessionResponse,
    SetBrainRequest,
    SetBrainResponse,
    SetLangRequest,
    SpawnCreatureRequest,
    TemplateListItem,
    UpdateLayerFileRequest,
    WorldListItem,
    WorldManifestResponse,
    WorldStateResponse,
)
from dnd_simulator.content_loader.manifest import LayerType
from dnd_simulator.i18n import _
from dnd_simulator.service.game_service import GameService
from dnd_simulator.service.session import GameSession

router = APIRouter(prefix="/api/master", tags=["master"])


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
    try:
        result = service.fork_world(
            source_world_id=world_id,
            new_world_id=req.new_id,
            from_layer=req.from_layer,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    try:
        files = service.get_layer_files(world_id, layer_type)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return LayerFilesResponse(files=files)


@router.get("/worlds/{world_id}/layers/{layer_type}/files/{filename}", response_model=LayerFileResponse)
def get_layer_file(world_id: str, layer_type: LayerType, filename: str) -> LayerFileResponse:
    """Read a single YAML file from a layer."""
    service = get_service()
    try:
        content = service.get_layer_file(world_id, layer_type, filename)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MessageResponse(message=_("Layer '{}' scaffolded in world '{}'").format(layer_type.value, world_id))


@router.post("/worlds/{world_id}/fork/{layer_type}", response_model=MessageResponse)
def fork_world_layer(world_id: str, layer_type: LayerType) -> MessageResponse:
    """Fork a library template layer into the world's custom directory."""
    service = get_service()
    try:
        service.fork_layer(world_id, layer_type)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return MessageResponse(message=_("Layer '{}' forked to custom in world '{}'").format(layer_type.value, world_id))


# -- Sessions --


@router.get("/sessions")
def list_sessions() -> list[dict[str, str]]:
    """List all active sessions."""
    service = get_service()
    return service.list_sessions()


@router.post("/sessions", response_model=SessionResponse)
def create_session(body: CreateSessionRequest) -> SessionResponse:
    """Start a new game session from a world template."""
    service = get_service()
    session = service.start_game(body.world_name, lang=body.lang)
    player = session.get_player()
    return SessionResponse(
        session_id=session.session_id,
        player_name=player.name if player else "",
        player_location=session.player_location,
        time=_format_time(session),
    )


@router.get("/sessions/{session_id}", response_model=WorldStateResponse)
def get_session_state(session_id: str) -> WorldStateResponse:
    """God-mode: full world state."""
    service = get_service()
    _get_session(service, session_id)  # validates session exists → 404 if not
    state = service.get_world_state(session_id)
    return WorldStateResponse.model_validate(state)


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
def delete_session(session_id: str) -> MessageResponse:
    """Stop and remove a session."""
    service = get_service()
    try:
        service.delete_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=_("Session {} deleted").format(session_id))


# -- Creatures --


@router.get("/sessions/{session_id}/creatures", response_model=list[CreatureResponse])
def list_creatures(
    session_id: str,
    entity_type: str | None = None,
    location_id: str | None = None,
    active: bool | None = None,
) -> list[CreatureResponse]:
    """List all creatures in a session with optional filters."""
    service = get_service()
    creatures = service.list_creatures(session_id, entity_type=entity_type, location_id=location_id, active=active)
    return [CreatureResponse.model_validate(c) for c in creatures]


@router.get("/sessions/{session_id}/creatures/{entity_id}", response_model=CreatureResponse)
def get_creature(session_id: str, entity_id: str) -> CreatureResponse:
    """Get creature details."""
    service = get_service()
    try:
        info = service.get_creature_info(session_id, entity_id)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return CreatureResponse.model_validate(info)


@router.post("/sessions/{session_id}/creatures", response_model=CreatureResponse)
def spawn_creature(session_id: str, body: SpawnCreatureRequest) -> CreatureResponse:
    """Spawn a creature (NPC or monster) into a live session."""
    service = get_service()
    try:
        service.spawn_creature(session_id, body.model_dump(exclude_none=True))
        info = service.get_creature_info(session_id, body.id)
    except (ValueError, KeyError, RuntimeError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return CreatureResponse.model_validate(info)


@router.patch("/sessions/{session_id}/creatures/{entity_id}", response_model=MessageResponse)
def patch_creature(session_id: str, entity_id: str, body: PatchCreatureRequest) -> MessageResponse:
    """Update mutable creature fields."""
    service = get_service()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail=_("No fields to update"))
    try:
        service.patch_creature(session_id, entity_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message=_("Creature {} updated").format(entity_id))


@router.delete("/sessions/{session_id}/creatures/{entity_id}", response_model=MessageResponse)
def delete_creature(session_id: str, entity_id: str) -> MessageResponse:
    """Remove a creature from a live session."""
    service = get_service()
    try:
        service.remove_creature(session_id, entity_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message=_("Creature {} removed").format(entity_id))


@router.post("/sessions/{session_id}/creatures/{entity_id}/items")
def give_item(session_id: str, entity_id: str, body: GiveItemRequest) -> dict[str, str]:
    """Give an item (weapon, potion) to a creature."""
    service = get_service()
    item_data = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        return service.give_item(session_id, entity_id, item_data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@router.put("/sessions/{session_id}/creatures/{entity_id}/brain", response_model=SetBrainResponse)
def set_brain(session_id: str, entity_id: str, body: SetBrainRequest) -> SetBrainResponse:
    """Switch creature brain type."""
    service = get_service()
    try:
        actual_type = service.set_creature_brain(session_id, entity_id, body.type, body.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    warning = "no_llm_key" if body.type == "llm" and actual_type != "llm" else None
    return SetBrainResponse(
        message=_("Creature {} brain set to {}").format(entity_id, actual_type),
        brain_type=actual_type,
        warning=warning,
    )


# -- Nation/Settlement hot controls --


@router.patch("/sessions/{session_id}/nations/{nation_id}", response_model=MessageResponse)
def patch_nation(session_id: str, nation_id: str, body: PatchNationRequest) -> MessageResponse:
    """Update mutable nation fields."""
    service = get_service()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail=_("No fields to update"))
    try:
        service.patch_nation(session_id, nation_id, updates)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=_("Nation {} updated").format(nation_id))


@router.patch("/sessions/{session_id}/settlements/{settlement_id}", response_model=MessageResponse)
def patch_settlement(session_id: str, settlement_id: str, body: PatchSettlementRequest) -> MessageResponse:
    """Update mutable settlement fields."""
    service = get_service()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail=_("No fields to update"))
    try:
        service.patch_settlement(session_id, settlement_id, updates)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=_("Settlement {} updated").format(settlement_id))


# -- Time --


@router.post("/sessions/{session_id}/time/advance", response_model=MessageResponse)
def advance_time(session_id: str, body: AdvanceTimeRequest) -> MessageResponse:
    """Advance game time."""
    service = get_service()
    try:
        events = service.advance_time(session_id, body.hours)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    msg = _("Advanced {}h.").format(body.hours)
    if events:
        msg += " " + _("Events:") + " " + "; ".join(events)
    return MessageResponse(message=msg)


# -- Language --


@router.put("/sessions/{session_id}/lang", response_model=MessageResponse)
def set_session_lang(session_id: str, body: SetLangRequest) -> MessageResponse:
    """Change session language (affects NPC LLM prompts and translated strings)."""
    service = get_service()
    session = _get_session(service, session_id)
    session.lang = body.lang
    return MessageResponse(message=_("Language set to '{}'").format(body.lang))


# -- Saves --


@router.get("/sessions/{session_id}/saves")
def list_saves(session_id: str) -> dict[str, list[str]]:
    """List saves for this session."""
    service = get_service()
    _get_session(service, session_id)
    saves = service.list_saves(session_id)
    return {"saves": saves}


@router.post("/sessions/{session_id}/save", response_model=MessageResponse)
def save_game(session_id: str, name: str | None = None) -> MessageResponse:
    """Save current session state to disk."""
    service = get_service()
    try:
        save_name = service.save_game(session_id, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=_("Saved as '{}'").format(save_name))


@router.post("/sessions/{session_id}/saves/{save_name}/load", response_model=MessageResponse)
def load_save(session_id: str, save_name: str) -> MessageResponse:
    """Load a save into the current session."""
    service = get_service()
    try:
        service.load_game(session_id, save_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=_("Loaded '{}'").format(save_name))


@router.delete("/sessions/{session_id}/saves/{save_name}", response_model=MessageResponse)
def delete_save(session_id: str, save_name: str) -> MessageResponse:
    """Delete a save file."""
    service = get_service()
    try:
        service.delete_save(session_id, save_name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=_("Deleted '{}'").format(save_name))


# -- Helpers --


def _format_time(session: GameSession) -> str:
    t = session.world.time
    return f"Y{t.year} M{t.month} D{t.day} {t.hour:02d}:{t.minute:02d}"


def _get_session(service: GameService, session_id: str) -> GameSession:
    try:
        return service.get_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
