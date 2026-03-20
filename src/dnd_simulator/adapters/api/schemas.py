from __future__ import annotations

from pydantic import BaseModel

# -- Requests --


class CreateSessionRequest(BaseModel):
    world_name: str = "test_world.yaml"
    lang: str = "en"


class PlayerActionRequest(BaseModel):
    action: str


class CreatePlayerRequest(BaseModel):
    name: str = "Adventurer"
    race: str = "human"
    char_class: str = "fighter"
    level: int = 1
    alignment: str = "true_neutral"
    appearance: str = ""
    hp: int = 10
    ac: int = 10
    gold: int = 0
    start_region: str = ""
    ability_scores: dict[str, int] | None = None


class SpawnNpcRequest(BaseModel):
    id: str
    name: str
    region_id: str
    role: str = ""
    personality: str = ""
    settlement_id: str = ""
    hp: int = 4
    ac: int = 10
    ai: str = "rule_based"


class PatchNpcRequest(BaseModel):
    current_hp: int | None = None
    ac: int | None = None
    personality: str | None = None
    region_id: str | None = None
    gold: int | None = None


class SetBrainRequest(BaseModel):
    type: str  # "rule_based" or "llm"
    model: str = ""


class PatchNationRequest(BaseModel):
    wealth: float | None = None
    military: float | None = None
    stability: float | None = None


class PatchSettlementRequest(BaseModel):
    population: int | None = None
    prosperity: float | None = None
    defenses: float | None = None


class AdvanceTimeRequest(BaseModel):
    hours: int = 1


class SetLangRequest(BaseModel):
    lang: str


# -- Responses --


class SessionResponse(BaseModel):
    session_id: str
    player_name: str
    player_location: str
    time: str


class WorldListItem(BaseModel):
    id: str
    name: str
    description: str


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


class NpcResponse(BaseModel):
    id: str
    name: str
    region_id: str
    role: str
    personality: str
    hp: int
    max_hp: int
    ac: int
    ai_type: str
    active: bool


class MessageResponse(BaseModel):
    message: str
