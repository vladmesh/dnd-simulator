from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.adapters.api.schemas import (
    ActionResponse,
    CreatePlayerRequest,
    PlayerActionRequest,
    PlayerStatusResponse,
)
from dnd_simulator.core.character import Ability

router = APIRouter(prefix="/api/player", tags=["player"])


@router.post("/sessions/{session_id}/character", response_model=PlayerStatusResponse)
def create_character(session_id: str, body: CreatePlayerRequest) -> PlayerStatusResponse:
    """Create a player character in a session."""
    service = get_service()
    data = body.model_dump()
    data["class"] = data.pop("char_class")
    try:
        player = service.create_player(session_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return _player_status(player)


@router.get("/sessions/{session_id}/status", response_model=PlayerStatusResponse)
def get_status(session_id: str) -> PlayerStatusResponse:
    """Player's own character info."""
    service = get_service()
    session = _get_session(service, session_id)
    p = session.player
    if not p:
        raise HTTPException(status_code=404, detail="No player in this session")
    return _player_status(p)


@router.post("/sessions/{session_id}/action", response_model=ActionResponse)
def player_action(session_id: str, body: PlayerActionRequest) -> ActionResponse:
    """Execute a player action (look, go, wait, etc.)."""
    service = get_service()
    _get_session(service, session_id)

    response = service.player_action(session_id, body.action)
    return ActionResponse(
        text=response.text,
        events=response.events_summary or [],
    )


@router.get("/sessions/{session_id}/perception")
def get_perception(session_id: str) -> dict[str, Any]:
    """What the player's character perceives — surroundings, entities, weather."""
    service = get_service()
    try:
        return service.get_perception(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


@router.get("/sessions/{session_id}/events")
def get_events(session_id: str) -> dict[str, list[str]]:
    """New events since player last checked."""
    service = get_service()
    try:
        events = service.get_new_events(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"events": events}


@router.get("/sessions/{session_id}/combat")
def get_combat(session_id: str) -> dict[str, Any]:
    """Combat state from player's perspective. Returns null if not in combat."""
    service = get_service()
    try:
        state = service.get_combat_state(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return {"in_combat": state is not None, "combat": state}


@router.get("/sessions/{session_id}/map")
def get_map(session_id: str) -> dict[str, Any]:
    """Map: current region info and paths to adjacent regions."""
    service = get_service()
    try:
        return service.get_map(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


# -- Helpers --


def _get_session(service: Any, session_id: str) -> Any:
    try:
        return service.get_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


def _player_status(p: Any) -> PlayerStatusResponse:
    scores = p.ability_scores
    return PlayerStatusResponse(
        name=p.name,
        race=p.race.value,
        char_class=p.char_class.value,
        level=p.level,
        alignment=p.alignment.value,
        hp=p.current_hp,
        max_hp=p.max_hp,
        ac=p.ac,
        gold=p.gold,
        region_id=p.region_id,
        appearance=p.appearance,
        ability_scores={
            "str": scores[Ability.STR],
            "dex": scores[Ability.DEX],
            "con": scores[Ability.CON],
            "int": scores[Ability.INT],
            "wis": scores[Ability.WIS],
            "cha": scores[Ability.CHA],
        },
    )
