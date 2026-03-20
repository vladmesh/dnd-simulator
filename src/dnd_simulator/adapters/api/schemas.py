from __future__ import annotations

from pydantic import BaseModel

# -- Requests --


class CreateSessionRequest(BaseModel):
    world_file: str = "test_world.yaml"


class PlayerActionRequest(BaseModel):
    action: str


# -- Responses --


class SessionResponse(BaseModel):
    session_id: str
    player_name: str
    player_location: str
    time: str


class PlayerStatusResponse(BaseModel):
    name: str
    race: str
    char_class: str
    level: int
    alignment: str
    hp: int
    max_hp: int
    ac: int
    gold: int
    region_id: str
    appearance: str
    ability_scores: dict[str, int]


class ActionResponse(BaseModel):
    text: str
    events: list[str]


class WorldStateResponse(BaseModel):
    session_id: str
    time: str
    regions: list[dict[str, object]]
    nations: list[dict[str, object]]
    settlements: list[dict[str, object]]
    entities: list[dict[str, object]]
