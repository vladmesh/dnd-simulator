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
    start_location: str = ""
    ability_scores: dict[str, int] | None = None
    attacks: list[dict[str, object]] | None = None


class SpawnCreatureRequest(BaseModel):
    """Spawn a creature into a live session. entity_type determines the class created."""

    id: str
    name: str
    entity_type: str  # "npc" or "monster"
    # Location
    start_location: str
    # Creature stats
    hp: int = Field(ge=1, le=999)
    ac: int = Field(ge=0, le=30)
    speed: int = Field(ge=0)
    attacks: list[dict[str, object]] | None = None
    ability_scores: dict[str, int] | None = None
    # NPC-specific (ignored for monsters)
    role: str = ""
    personality: str = ""
    settlement_id: str = ""
    ai: str = "rule_based"


class PatchCreatureRequest(BaseModel):
    """Update mutable creature fields. Only applicable fields are applied."""

    current_hp: int | None = Field(default=None, ge=0, le=999)
    ac: int | None = Field(default=None, ge=0, le=30)
    location_id: str | None = None
    conditions: list[str] | None = None  # D&D 5e condition names
    # Character-level
    gold: int | None = Field(default=None, ge=0)
    # NPC-level
    personality: str | None = None


class GiveItemRequest(BaseModel):
    name: str
    type: str  # "potion", "weapon", "armor", "shield"
    price: int | None = None
    # Potion fields
    heal_dice: str | None = None
    # Weapon fields
    weapon_id: str | None = None
    category: str | None = None
    attack_name: str | None = None
    damage: list[dict[str, str]] | None = None
    ability: str | None = None
    reach: int | None = None
    is_magic: bool | None = None
    is_finesse: bool | None = None
    grant_actions: list[str] | None = None


class SetBrainRequest(BaseModel):
    type: str  # "rule_based" or "llm"
    model: str = ""


class PatchNationRequest(BaseModel):
    wealth: float | None = Field(default=None, ge=0.0, le=100.0)
    military: float | None = Field(default=None, ge=0.0, le=100.0)
    stability: float | None = Field(default=None, ge=0.0, le=100.0)


class PatchSettlementRequest(BaseModel):
    population: int | None = Field(default=None, ge=0)
    prosperity: float | None = Field(default=None, ge=0.0, le=100.0)
    defenses: float | None = Field(default=None, ge=0.0, le=100.0)


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
    player_id: str
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


class CreatureResponse(BaseModel):
    """Any creature in the world — player, NPC, or monster."""

    id: str
    name: str
    location_id: str
    active: bool
    hp: int
    max_hp: int
    ac: int
    conditions: list[str] = Field(default_factory=list)
    entity_type: str = ""  # "player", "npc", or ""
    race: str = ""
    char_class: str = ""
    level: int = 0
    gold: int = 0
    # NPC-specific (optional)
    role: str = ""
    personality: str = ""
    ai_type: str = ""
    settlement_id: str = ""
    memory: dict[str, object] | None = None


class TemplateListItem(BaseModel):
    slug: str
    name: str
    layer_type: str
    version: str
    description: str
    tags: list[str]
    requires_geography: list[str]


class MessageResponse(BaseModel):
    message: str
