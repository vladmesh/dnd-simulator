from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException

from dnd_simulator.adapters.api.deps import get_service
from dnd_simulator.adapters.api.schemas import CreateSessionRequest, SessionResponse, WorldStateResponse
from dnd_simulator.core.models import Query

router = APIRouter(prefix="/api/master", tags=["master"])


@router.post("/sessions", response_model=SessionResponse)
def create_session(body: CreateSessionRequest) -> SessionResponse:
    """Start a new game session from a world file."""
    service = get_service()
    session = service.start_game(body.world_file)
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


def _format_time(session: Any) -> str:
    t = session.world.time
    return f"Y{t.year} M{t.month} D{t.day} {t.hour:02d}:{t.minute:02d}"


def _get_session(service: Any, session_id: str) -> Any:
    try:
        return service.get_session(session_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
