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
    alignment: str = "true_neutral"
    appearance: str = ""
    start_location: str = ""
    ability_scores: dict[str, int]
    fighting_style: str | None = None
    combat_position: list[int] | None = None


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
    role: str | None = None
    personality: str | None = None
    settlement_id: str | None = None
    ai: str = "rule_based"


class PatchCreatureRequest(BaseModel):
    """Update mutable creature fields. Only applicable fields are applied."""

    current_hp: int | None = Field(default=None, ge=0, le=999)
    max_hp: int | None = Field(default=None, ge=1, le=999)
    ac: int | None = Field(default=None, ge=0, le=30)
    location_id: str | None = None
    conditions: list[str] | None = None  # D&D 5e condition names
    # Character-level
    gold: int | None = Field(default=None, ge=0)
    # Resource pools (add/replace pools by id)
    resource_pools: list[dict[str, object]] | None = None
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
    # Armor fields
    armor_id: str | None = None
    base_ac: int | None = None
    max_dex_bonus: int | None = None
    strength_req: int | None = None
    # Shield fields
    shield_id: str | None = None
    ac_bonus: int | None = None


class SetBrainRequest(BaseModel):
    type: str  # "rule_based" or "llm"
    model: str = ""


class SetBrainResponse(BaseModel):
    message: str
    brain_type: str
    warning: str | None = None


class PatchNationRequest(BaseModel):
    wealth: float | None = Field(default=None, ge=0.0, le=100.0)
    military: float | None = Field(default=None, ge=0.0, le=100.0)
    stability: float | None = Field(default=None, ge=0.0, le=100.0)


class PatchSettlementRequest(BaseModel):
    population: int | None = Field(default=None, ge=0)
    prosperity: float | None = Field(default=None, ge=0.0, le=100.0)
    defenses: float | None = Field(default=None, ge=0.0, le=100.0)


class ForkWorldRequest(BaseModel):
    """Fork a world, optionally truncating layers."""

    new_id: str = Field(..., pattern=r"^[a-z0-9_]+$", min_length=1, max_length=64)
    from_layer: str | None = None


class CreateWorldRequest(BaseModel):
    """Create an empty world (no layers defined)."""

    id: str = Field(..., pattern=r"^[a-z0-9_]+$", min_length=1, max_length=64)
    name: str
    description: str = ""
    default_player_faction: str = ""


class AssembleWorldRequest(BaseModel):
    """Assemble a new world from library templates."""

    id: str = Field(..., pattern=r"^[a-z0-9_]+$", min_length=1, max_length=64)
    name: str
    description: str = ""
    layer_selections: dict[str, str]
    default_player_faction: str = ""


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
    complete: bool
    editable: bool


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
    # Inventory & equipment
    inventory: list[dict[str, str]] = Field(default_factory=list)
    equipped_weapon: dict[str, str] | None = None
    resource_pools: list[dict[str, object]] = Field(default_factory=list)


class TemplateListItem(BaseModel):
    slug: str
    name: str
    layer_type: str
    version: str
    description: str
    tags: list[str]
    requires_geography: list[str]


class LayerInfo(BaseModel):
    layer_type: str
    source: str | None
    template: str | None
    version: str | None


class WorldManifestResponse(BaseModel):
    world_id: str
    name: str
    layers: list[LayerInfo]


class LayerFilesResponse(BaseModel):
    files: dict[str, str]


class LayerFileResponse(BaseModel):
    filename: str
    content: str


class UpdateLayerFileRequest(BaseModel):
    content: str


class MessageResponse(BaseModel):
    message: str
