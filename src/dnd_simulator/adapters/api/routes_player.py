from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.adapters.api.schemas import (
    CreatePlayerRequest,
    LevelUpRequest,
    PlayerStatusResponse,
    SetupConfigResponse,
)
from dnd_simulator.core.class_features import FightingStyle
from dnd_simulator.rules.character_creation import POINT_BUY_BUDGET, STARTING_GOLD
from dnd_simulator.service.dto import PlayerStatusData
from dnd_simulator.service.errors import PlayerNotFoundError, SessionNotFoundError

router = APIRouter(prefix="/api/player", tags=["player"])


@router.get("/setup-config", response_model=SetupConfigResponse)
def get_setup_config() -> SetupConfigResponse:
    """Get character creation rules and limits."""
    return SetupConfigResponse(
        starting_gold=STARTING_GOLD,
        point_buy_budget=POINT_BUY_BUDGET,
    )


@router.post("/sessions/{session_id}/character", response_model=PlayerStatusResponse)
def create_character(session_id: str, body: CreatePlayerRequest) -> PlayerStatusResponse:
    """Create a player character in a session."""
    service = get_service()
    data = body.model_dump(exclude_none=True)
    data["class"] = data.pop("char_class")
    try:
        player = service.create_player(session_id, data)
    except (SessionNotFoundError, PlayerNotFoundError):
        raise
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    return _to_response(service.player_status(session_id, player_id=player.id))


@router.get("/sessions/{session_id}/status", response_model=PlayerStatusResponse)
def get_status(session_id: str) -> PlayerStatusResponse:
    """Player's own character info."""
    service = get_service()
    try:
        status = service.player_status(session_id)
    except (SessionNotFoundError, PlayerNotFoundError):
        raise
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.NOT_FOUND, detail=str(e)) from e
    return _to_response(status)


@router.post("/sessions/{session_id}/level-up", response_model=PlayerStatusResponse)
def level_up(session_id: str, body: LevelUpRequest) -> PlayerStatusResponse:
    """Apply a pending level-up to the player character."""
    service = get_service()
    try:
        style = FightingStyle(body.fighting_style) if body.fighting_style is not None else None
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    try:
        service.level_up_player(session_id, fighting_style=style)
    except (SessionNotFoundError, PlayerNotFoundError):
        raise
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    return _to_response(service.player_status(session_id))


def _to_response(data: PlayerStatusData) -> PlayerStatusResponse:
    return PlayerStatusResponse(
        player_id=data.player_id,
        name=data.name,
        race=data.race,
        char_class=data.char_class,
        level=data.level,
        experience=data.experience,
        level_up_available=data.level_up_available,
        xp_to_next_level=data.xp_to_next_level,
        alignment=data.alignment,
        hp=data.hp,
        max_hp=data.max_hp,
        ac=data.ac,
        gold=data.gold,
        location_id=data.location_id,
        appearance=data.appearance,
        ability_scores=data.ability_scores,
        resource_pools=[
            {"id": p.id, "max_uses": p.max_uses, "current_uses": p.current_uses} for p in data.resource_pools
        ],
        equipped=data.equipped,
        inventory=data.inventory,
    )
