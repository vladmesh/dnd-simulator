from __future__ import annotations

from http import HTTPStatus

from fastapi import APIRouter, HTTPException

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.adapters.api.schemas import (
    CreatePlayerRequest,
    PlayerStatusResponse,
    SetupConfigResponse,
)
from dnd_simulator.core.character import Ability
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.i18n import _
from dnd_simulator.rules.character_creation import POINT_BUY_BUDGET, STARTING_GOLD
from dnd_simulator.rules.modifiers import effective_ac
from dnd_simulator.service.game_service import GameService
from dnd_simulator.service.session import GameSession

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
    except ValueError as e:
        raise HTTPException(status_code=HTTPStatus.BAD_REQUEST, detail=str(e)) from e
    return _player_status(player)


@router.get("/sessions/{session_id}/status", response_model=PlayerStatusResponse)
def get_status(session_id: str) -> PlayerStatusResponse:
    """Player's own character info."""
    service = get_service()
    session = _get_session(service, session_id)
    p = session.get_player()
    if not p:
        raise HTTPException(status_code=404, detail=_("No player in this session"))
    return _player_status(p)


# -- Helpers --


def _get_session(service: GameService, session_id: str) -> GameSession:
    try:
        return service.get_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e


def _player_status(p: PlayerCharacter) -> PlayerStatusResponse:
    scores = p.ability_scores
    return PlayerStatusResponse(
        player_id=p.id,
        name=p.name,
        race=p.race.value,
        char_class=p.char_class.value,
        level=p.level,
        alignment=p.alignment.value,
        hp=p.current_hp,
        max_hp=p.max_hp,
        ac=effective_ac(p),
        gold=p.gold,
        location_id=p.location_id,
        appearance=p.appearance,
        ability_scores={
            "str": scores[Ability.STR],
            "dex": scores[Ability.DEX],
            "con": scores[Ability.CON],
            "int": scores[Ability.INT],
            "wis": scores[Ability.WIS],
            "cha": scores[Ability.CHA],
        },
        resource_pools=[
            {"id": pool.id, "max_uses": pool.max_uses, "current_uses": pool.current_uses} for pool in p.resource_pools
        ],
    )
