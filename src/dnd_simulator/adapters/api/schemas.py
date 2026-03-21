from __future__ import annotations

from pydantic import BaseModel, Field

# -- Requests --


class CreateSessionRequest(BaseModel):
    world_name: str = "sword_vale"
    lang: str = "en"


class CreatePlayerRequest(BaseModel):
    name: str = "Adventurer"
    race: str = "human"
    char_class: str = "fighter"
    level: int = Field(default=1, ge=1, le=20)
    alignment: str = "true_neutral"
    appearance: str = ""
    hp: int = Field(default=10, ge=1, le=999)
    ac: int = Field(default=10, ge=0, le=30)
    gold: int = Field(default=0, ge=0)
    start_region: str = ""
    ability_scores: dict[str, int] | None = None
    attacks: list[dict[str, object]] | None = None


class SpawnNpcRequest(BaseModel):
    id: str
    name: str
    region_id: str = ""  # backward compat
    start_location: str = ""
    role: str = ""
    personality: str = ""
    settlement_id: str = ""
    hp: int = Field(default=4, ge=1, le=999)
    ac: int = Field(default=10, ge=0, le=30)
    ai: str = "rule_based"
    attacks: list[dict[str, object]] | None = None


class PatchNpcRequest(BaseModel):
    current_hp: int | None = Field(default=None, ge=0, le=999)
    ac: int | None = Field(default=None, ge=0, le=30)
    personality: str | None = None
    location_id: str | None = None
    gold: int | None = Field(default=None, ge=0)


class SetBrainRequest(BaseModel):
    type: str  # "rule_based" or "llm"
    model: str = ""


class PatchNationRequest(BaseModel):
    wealth: float | None = Field(default=None, ge=0.0)
    military: float | None = Field(default=None, ge=0.0)
    stability: float | None = Field(default=None, ge=0.0, le=1.0)


class PatchSettlementRequest(BaseModel):
    population: int | None = Field(default=None, ge=0)
    prosperity: float | None = Field(default=None, ge=0.0, le=1.0)
    defenses: float | None = Field(default=None, ge=0.0, le=1.0)


class CreateWorldRequest(BaseModel):
    """Full world definition for the world builder."""

    id: str = Field(..., pattern=r"^[a-z0-9_]+$", min_length=1, max_length=64)
    name: str
    description: str = ""
    regions: dict[str, object] = Field(default_factory=dict)
    locations: dict[str, object] = Field(default_factory=dict)
    nations: dict[str, object] = Field(default_factory=dict)
    npcs: dict[str, object] = Field(default_factory=dict)


class AdvanceTimeRequest(BaseModel):
    hours: int = Field(default=1, ge=1, le=8760)


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
    location_id: str
    appearance: str
    ability_scores: dict[str, int]


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
    location_id: str
    role: str
    personality: str
    hp: int
    max_hp: int
    ac: int
    ai_type: str
    active: bool


class MessageResponse(BaseModel):
    message: str
