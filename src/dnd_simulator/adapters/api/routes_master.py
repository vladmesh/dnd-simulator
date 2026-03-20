from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.adapters.api.schemas import (
    AdvanceTimeRequest,
    CreateSessionRequest,
    MessageResponse,
    NpcResponse,
    PatchNationRequest,
    PatchNpcRequest,
    PatchSettlementRequest,
    SessionResponse,
    SetBrainRequest,
    SpawnNpcRequest,
    WorldListItem,
    WorldStateResponse,
)
from dnd_simulator.core.models import Query
from dnd_simulator.layers.entities.models import Npc

router = APIRouter(prefix="/api/master", tags=["master"])


# -- Worlds (templates) --


@router.get("/worlds", response_model=list[WorldListItem])
def list_worlds() -> list[WorldListItem]:
    """List available world templates."""
    service = get_service()
    worlds = service.list_worlds()
    return [WorldListItem(**w) for w in worlds]


# -- Sessions --


@router.post("/sessions", response_model=SessionResponse)
def create_session(body: CreateSessionRequest) -> SessionResponse:
    """Start a new game session from a world template."""
    service = get_service()
    session = service.start_game(body.world_name)
    player = session.player
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
    session = _get_session(service, session_id)
    world = session.world

    regions_answer = world.query_layer("geography", Query(question="regions", params={}))
    region_list: list[dict[str, object]] = []
    for rid in regions_answer.value:
        info = world.query_layer("geography", Query(question="region_info", params={"region_id": rid}))
        weather = world.query_layer("geography", Query(question="weather", params={"region_id": rid}))
        region_list.append({**info.value, "weather": weather.value})

    nations_answer = world.query_layer("politics", Query(question="nations", params={}))
    nation_list: list[dict[str, object]] = []
    for nid in nations_answer.value:
        info = world.query_layer("politics", Query(question="nation_info", params={"nation_id": nid}))
        nation_list.append(info.value)

    all_settlements: list[dict[str, object]] = []
    for rid in regions_answer.value:
        answer = world.query_layer("settlements", Query(question="region_settlements", params={"region_id": rid}))
        for s in answer.value:
            all_settlements.append(s)

    entities_list: list[dict[str, object]] = []
    for rid in regions_answer.value:
        answer = world.query_layer("entities", Query(question="entities_in_region", params={"region_id": rid}))
        for e in answer.value:
            entities_list.append(e)

    return WorldStateResponse(
        session_id=session.session_id,
        time=_format_time(session),
        regions=region_list,
        nations=nation_list,
        settlements=all_settlements,
        entities=entities_list,
    )


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
def delete_session(session_id: str) -> MessageResponse:
    """Stop and remove a session."""
    service = get_service()
    try:
        service.delete_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=f"Session {session_id} deleted")


# -- NPC hot controls --


@router.get("/sessions/{session_id}/npcs", response_model=list[NpcResponse])
def list_npcs(session_id: str) -> list[NpcResponse]:
    """List all NPCs in a session."""
    service = get_service()
    session = _get_session(service, session_id)
    world = session.world

    regions_answer = world.query_layer("geography", Query(question="regions", params={}))
    npcs: list[NpcResponse] = []
    for rid in regions_answer.value:
        answer = world.query_layer("entities", Query(question="entities_in_region", params={"region_id": rid}))
        for e in answer.value:
            entity = world.query_layer("entities", Query(question="entity_info", params={"entity_id": e["id"]}))
            info = entity.value
            if "role" in info:
                npcs.append(_npc_response_from_info(info, session))
    return npcs


@router.post("/sessions/{session_id}/npcs", response_model=NpcResponse)
def spawn_npc(session_id: str, body: SpawnNpcRequest) -> NpcResponse:
    """Spawn a new NPC into a live session."""
    service = get_service()
    try:
        npc = service.spawn_npc(session_id, body.model_dump())
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _npc_response(npc)


@router.get("/sessions/{session_id}/npcs/{npc_id}", response_model=NpcResponse)
def get_npc(session_id: str, npc_id: str) -> NpcResponse:
    """Get NPC details."""
    service = get_service()
    session = _get_session(service, session_id)
    entity = _get_npc(session, npc_id)
    return _npc_response(entity)


@router.patch("/sessions/{session_id}/npcs/{npc_id}", response_model=MessageResponse)
def patch_npc(session_id: str, npc_id: str, body: PatchNpcRequest) -> MessageResponse:
    """Update mutable NPC fields."""
    service = get_service()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        service.patch_npc(session_id, npc_id, updates)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=f"NPC {npc_id} updated")


@router.delete("/sessions/{session_id}/npcs/{npc_id}", response_model=MessageResponse)
def delete_npc(session_id: str, npc_id: str) -> MessageResponse:
    """Remove an NPC from a live session."""
    service = get_service()
    try:
        service.remove_npc(session_id, npc_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=f"NPC {npc_id} removed")


@router.put("/sessions/{session_id}/npcs/{npc_id}/brain", response_model=MessageResponse)
def set_brain(session_id: str, npc_id: str, body: SetBrainRequest) -> MessageResponse:
    """Switch NPC brain type."""
    service = get_service()
    try:
        service.set_npc_brain(session_id, npc_id, body.type, body.model)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return MessageResponse(message=f"NPC {npc_id} brain set to {body.type}")


# -- Nation/Settlement hot controls --


@router.patch("/sessions/{session_id}/nations/{nation_id}", response_model=MessageResponse)
def patch_nation(session_id: str, nation_id: str, body: PatchNationRequest) -> MessageResponse:
    """Update mutable nation fields."""
    service = get_service()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        service.patch_nation(session_id, nation_id, updates)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=f"Nation {nation_id} updated")


@router.patch("/sessions/{session_id}/settlements/{settlement_id}", response_model=MessageResponse)
def patch_settlement(session_id: str, settlement_id: str, body: PatchSettlementRequest) -> MessageResponse:
    """Update mutable settlement fields."""
    service = get_service()
    updates = body.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    try:
        service.patch_settlement(session_id, settlement_id, updates)
    except (ValueError, KeyError) as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=f"Settlement {settlement_id} updated")


# -- Time --


@router.post("/sessions/{session_id}/time/advance", response_model=MessageResponse)
def advance_time(session_id: str, body: AdvanceTimeRequest) -> MessageResponse:
    """Advance game time."""
    service = get_service()
    try:
        events = service.advance_time(session_id, body.hours)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    msg = f"Advanced {body.hours}h."
    if events:
        msg += " Events: " + "; ".join(events)
    return MessageResponse(message=msg)


# -- Saves --


@router.get("/sessions/{session_id}/saves")
def list_saves(session_id: str) -> dict[str, list[str]]:
    """List saves for this session."""
    service = get_service()
    _get_session(service, session_id)
    saves = service.list_saves()
    return {"saves": saves}


@router.post("/sessions/{session_id}/save", response_model=MessageResponse)
def save_game(session_id: str, name: str | None = None) -> MessageResponse:
    """Save current session state to disk."""
    service = get_service()
    try:
        save_name = service.save_game(session_id, name)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return MessageResponse(message=f"Saved as '{save_name}'")


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
    return MessageResponse(message=f"Loaded '{save_name}'")


# -- Helpers --


def _format_time(session: Any) -> str:
    t = session.world.time
    return f"Y{t.year} M{t.month} D{t.day} {t.hour:02d}:{t.minute:02d}"


def _get_session(service: Any, session_id: str) -> Any:
    try:
        return service.get_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


def _get_npc(session: Any, npc_id: str) -> Npc:
    from dnd_simulator.layers.entities.layer import EntitiesLayer

    for layer in session.world.layers:
        if isinstance(layer, EntitiesLayer):
            entity = layer.get_entity(npc_id)
            if entity is not None and isinstance(entity, Npc):
                return entity
    raise HTTPException(status_code=404, detail=f"NPC '{npc_id}' not found")


def _npc_response(npc: Npc) -> NpcResponse:
    return NpcResponse(
        id=npc.id,
        name=npc.name,
        region_id=npc.region_id,
        role=npc.role,
        personality=npc.personality,
        hp=npc.current_hp,
        max_hp=npc.max_hp,
        ac=npc.ac,
        ai_type=npc.ai_type,
        active=npc.active,
    )


def _npc_response_from_info(info: dict[str, object], session: Any) -> NpcResponse:
    npc = _get_npc(session, str(info["id"]))
    return _npc_response(npc)
