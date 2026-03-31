"""Pydantic content models — single source of truth for YAML content structure.

These models represent the YAML schema (not runtime state). They drive:
- Parsing (model_validate on raw YAML dicts)
- Validation (enum constraints, type checking)
- JSON Schema generation (for frontend forms)
- Serialization (model_dump for writing back to YAML)

Field names match YAML keys. Where Python name differs (e.g. ``class`` is reserved),
use ``alias`` + ``populate_by_name=True``.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

from dnd_simulator.core.character import (
    Ability,
    Alignment,
    CharClass,
    DamageType,
    NpcRole,
    Race,
)
from dnd_simulator.core.items import ItemType
from dnd_simulator.core.models import TerrainType
from dnd_simulator.core.squad import SquadBehavior, SquadType
from dnd_simulator.layers.geography.models import Direction
from dnd_simulator.layers.politics.models import LeaderTrait
from dnd_simulator.layers.settlements.models import SettlementType

# ---------------------------------------------------------------------------
# Localizable text type
# ---------------------------------------------------------------------------


def _coerce_localized_text(v: Any) -> dict[str, str]:
    """Accept plain string or dict; always return dict."""
    if isinstance(v, dict):
        return v
    if isinstance(v, str):
        return {"en": v}
    raise ValueError(f"Invalid localized text: {v}")


LocalizedText = Annotated[dict[str, str], BeforeValidator(_coerce_localized_text)]


# ---------------------------------------------------------------------------
# Shared / nested models
# ---------------------------------------------------------------------------


class DamageComponentContent(BaseModel):
    """One damage term: dice expression + type."""

    dice: str
    type: DamageType


class AttackContent(BaseModel):
    """A single attack definition from YAML."""

    name: str
    ability: Ability = Ability.STR
    damage: list[DamageComponentContent] = []
    reach: int = 5
    is_finesse: bool = False


class AbilityScoresContent(BaseModel):
    """Six ability scores with D&D defaults."""

    model_config = ConfigDict(populate_by_name=True)

    str_: int = Field(10, alias="str")
    dex: int = 10
    con: int = 10
    int_: int = Field(10, alias="int")
    wis: int = 10
    cha: int = 10


class NpcMemoryContent(BaseModel):
    """Structured NPC memory from YAML."""

    tags: list[str] = []
    recent: str = ""
    inner_state: str = ""
    current_conversation: str = ""


def _coerce_ability_scores(v: Any) -> AbilityScoresContent:
    """Accept raw dict or AbilityScoresContent; always return AbilityScoresContent."""
    if isinstance(v, AbilityScoresContent):
        return v
    if isinstance(v, dict):
        return AbilityScoresContent.model_validate(v)
    raise ValueError(f"Invalid ability_scores: {v}")


CoercedAbilityScores = Annotated[AbilityScoresContent, BeforeValidator(_coerce_ability_scores)]


# ---------------------------------------------------------------------------
# Item models
# ---------------------------------------------------------------------------


class ItemContent(BaseModel):
    """A single item from YAML — flat structure matching YAML layout.

    Items in YAML are flat dicts with type-specific fields mixed in.
    When ``ref`` is present, the item is resolved from a catalog entry;
    ``name`` and ``type`` become optional (provided by the catalog).
    """

    ref: str | None = None
    name: str = ""
    type: ItemType = ItemType.WEAPON
    equipped: bool = False
    price: int | None = None
    # Weapon fields
    weapon_id: str | None = None
    attack_name: str | None = None
    category: str | None = None
    damage: list[DamageComponentContent] | None = None
    reach: int | None = None
    ability: str | None = None
    modifier: int | None = None
    is_magic: bool | None = None
    is_finesse: bool | None = None
    is_two_handed: bool | None = None
    is_light: bool | None = None
    is_heavy: bool | None = None
    grant_conditions: list[str] | None = None
    grant_actions: list[str] | None = None
    # Armor fields
    armor_id: str | None = None
    base_ac: int | None = None
    max_dex_bonus: int | None = None
    strength_req: int | None = None
    # Shield fields
    shield_id: str | None = None
    ac_bonus: int | None = None
    # Accessory fields
    accessory_id: str | None = None
    slot: str | None = None
    modifiers: list[dict[str, Any]] | None = None
    # Potion fields
    heal_dice: str | None = None


# ---------------------------------------------------------------------------
# Geography models
# ---------------------------------------------------------------------------


class ConnectionContent(BaseModel):
    """A link between two regions."""

    target: str
    direction: Direction


class NeighborContent(BaseModel):
    """A link between two locations with distance."""

    target: str
    distance: int


class RegionContent(BaseModel):
    """A geographic region from YAML."""

    name: LocalizedText
    latitude: float
    longitude: float
    elevation: float
    terrain: TerrainType
    water_proximity: float = 0.0
    connections: list[ConnectionContent] = []
    battle_map: dict[str, Any] | None = None


class LocationContent(BaseModel):
    """A location (point of interest) from YAML."""

    name: LocalizedText
    region: str
    settlement: str = ""
    description: LocalizedText = {}
    neighbors: list[NeighborContent] = []


# ---------------------------------------------------------------------------
# Politics models
# ---------------------------------------------------------------------------


class LeaderContent(BaseModel):
    """A nation's leader from YAML."""

    name: LocalizedText
    age: int
    trait: LeaderTrait


class NationContent(BaseModel):
    """A nation from YAML."""

    name: LocalizedText
    regions: list[str] = []
    wealth: float = 50.0
    military: float = 50.0
    stability: float = 70.0
    leader: LeaderContent | None = None


# ---------------------------------------------------------------------------
# Settlements models
# ---------------------------------------------------------------------------


class SettlementContent(BaseModel):
    """A settlement from YAML."""

    name: LocalizedText
    region: str
    type: SettlementType
    population: int = 100
    prosperity: float = 50.0
    defenses: float = 30.0


# ---------------------------------------------------------------------------
# Ecology models
# ---------------------------------------------------------------------------


class MonsterTemplateContent(BaseModel):
    """A fully-specified monster template from YAML (inline or catalog entry)."""

    name: LocalizedText
    hp: int
    ac: int
    speed: int
    cr: float
    ability_scores: AbilityScoresContent = AbilityScoresContent()
    attacks: list[AttackContent] = []
    faction: str = ""
    description: LocalizedText = {}


class MonsterTemplateEntryContent(BaseModel):
    """A monster template entry in a world ecology layer.

    Can be either a full inline definition or a catalog reference (``base`` key).
    When ``base`` is set, all other fields are optional overrides resolved at assembly time.
    """

    base: str | None = None
    name: LocalizedText | None = None
    hp: int | None = None
    ac: int | None = None
    speed: int | None = None
    cr: float | None = None
    ability_scores: AbilityScoresContent | None = None
    attacks: list[AttackContent] | None = None
    faction: str | None = None


class EncounterEntryContent(BaseModel):
    """One encounter spawn rule from YAML."""

    template: str
    chance: float
    count: list[int]


class SquadContent(BaseModel):
    """A squad definition from YAML."""

    name: LocalizedText
    faction: str
    type: SquadType
    behavior: SquadBehavior
    start_location: str
    strength: int
    route: list[str] = []
    territory: list[str] = []
    max_strength: int | None = None
    members: list[str] = []
    tick_interval: int = 3600

    def model_post_init(self, __context: Any) -> None:
        if self.max_strength is None:
            object.__setattr__(self, "max_strength", self.strength)


# ---------------------------------------------------------------------------
# Entity models
# ---------------------------------------------------------------------------


class NpcContent(BaseModel):
    """An NPC definition from YAML."""

    model_config = ConfigDict(populate_by_name=True)

    name: LocalizedText
    race: Race = Race.HUMAN
    char_class: CharClass = Field(CharClass.COMMONER, alias="class")
    role: NpcRole = NpcRole.COMMONER
    start_location: str = ""
    settlement_id: str = ""
    faction: str = ""
    personality: LocalizedText = {}
    description: LocalizedText = {}
    hp: int = 4
    ac: int = 10
    speed: int = 30
    gold: int = 0
    ai: str = "rule_based"
    attacks: list[AttackContent] = []
    items: list[ItemContent] = []
    ability_scores: CoercedAbilityScores = AbilityScoresContent()
    class_features: dict[str, Any] = {}
    memory: NpcMemoryContent | None = None


class PlayerContent(BaseModel):
    """A player character definition from YAML."""

    model_config = ConfigDict(populate_by_name=True)

    id: str = ""
    name: LocalizedText
    race: Race = Race.HUMAN
    char_class: CharClass = Field(CharClass.FIGHTER, alias="class")
    level: int = 1
    alignment: Alignment = Alignment.TRUE_NEUTRAL
    appearance: LocalizedText = {}
    start_location: str = ""
    faction: str = ""
    hp: int = 10
    current_hp: int | None = None
    ac: int = 10
    gold: int = 0
    speed: int = 30
    attacks: list[AttackContent] = []
    items: list[ItemContent] = []
    ability_scores: CoercedAbilityScores = AbilityScoresContent()
    class_features: dict[str, Any] = {}
