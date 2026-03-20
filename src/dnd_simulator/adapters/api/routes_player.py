from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.adapters.api.schemas import ActionResponse, PlayerActionRequest, PlayerStatusResponse
from dnd_simulator.core.character import Ability

router = APIRouter(prefix="/api/player", tags=["player"])


@router.get("/sessions/{session_id}/status", response_model=PlayerStatusResponse)
def get_status(session_id: str) -> PlayerStatusResponse:
    """Player's own character info."""
    service = get_service()
    session = _get_session(service, session_id)
    p = session.player
    if not p:
        raise HTTPException(status_code=404, detail="No player in this session")

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


@router.post("/sessions/{session_id}/action", response_model=ActionResponse)
def player_action(session_id: str, body: PlayerActionRequest) -> ActionResponse:
    """Execute a player action (look, go, wait, etc.)."""
    service = get_service()
    _get_session(service, session_id)  # validate session exists

    response = service.player_action(session_id, body.action)
    return ActionResponse(
        text=response.text,
        events=response.events_summary or [],
    )


def _get_session(service: Any, session_id: str) -> Any:
    try:
        return service.get_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
