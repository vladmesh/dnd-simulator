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

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from dnd_simulator.core.brain import BrainType
from dnd_simulator.core.character import (
    Ability,
    Alignment,
    CharClass,
    DamageType,
    NpcRole,
    Race,
)
from dnd_simulator.core.items import ItemType
from dnd_simulator.core.models import TerrainType, TimeOfDay
from dnd_simulator.core.squad import SquadBehavior, SquadType
from dnd_simulator.layers.geography.models import Direction
from dnd_simulator.layers.politics.models import LeaderTrait
from dnd_simulator.layers.settlements.models import SettlementType

# ---------------------------------------------------------------------------
# Localizable text type
# ---------------------------------------------------------------------------


def _coerce_localized_text(v: object) -> dict[str, str]:
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


def _coerce_ability_scores(v: object) -> AbilityScoresContent:
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

    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    ref: str | None = None
    id: str | None = None
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
    # YAML uses "modifiers"; save data emits "grant_modifiers" — both accepted via alias
    modifiers: list[dict[str, Any]] | None = Field(None, alias="grant_modifiers")
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


class BattleMapContent(BaseModel):
    """Battle map geometry for a region or location.

    width and height are in feet (1 cell = 5 feet); both must be multiples
    of 5 to align the grid. Walls are axis-aligned segments encoded as
    [x1, y1, x2, y2] with both endpoints inside the grid.
    """

    width: int = Field(ge=10, le=500)
    height: int = Field(ge=10, le=500)
    walls: list[list[int]] = []

    @field_validator("width", "height")
    @classmethod
    def _multiple_of_five(cls, v: int) -> int:
        if v % 5 != 0:
            raise ValueError(f"battle_map width/height must be a multiple of 5 (feet); got {v}")
        return v

    @field_validator("walls")
    @classmethod
    def _walls_shape(cls, v: list[list[int]]) -> list[list[int]]:
        for w in v:
            if len(w) != 4:
                raise ValueError(f"wall must have 4 ints [x1,y1,x2,y2], got {w}")
        return v

    def validate_walls_within(self) -> None:
        """Verify each wall's endpoints are within the grid. Call after construction."""
        for w in self.walls:
            x1, y1, x2, y2 = w
            if not (0 <= x1 <= self.width and 0 <= x2 <= self.width):
                raise ValueError(f"wall x out of grid 0..{self.width}: {w}")
            if not (0 <= y1 <= self.height and 0 <= y2 <= self.height):
                raise ValueError(f"wall y out of grid 0..{self.height}: {w}")

    def model_post_init(self, _context: object) -> None:
        self.validate_walls_within()


class RegionContent(BaseModel):
    """A geographic region from YAML."""

    name: LocalizedText
    latitude: float
    longitude: float
    elevation: float
    terrain: TerrainType
    water_proximity: float = 0.0
    connections: list[ConnectionContent] = []
    battle_map: BattleMapContent | None = None


class LocationContent(BaseModel):
    """A location (point of interest) from YAML."""

    name: LocalizedText
    region: str
    settlement: str = ""
    description: LocalizedText = {}
    neighbors: list[NeighborContent] = []
    battle_map: BattleMapContent | None = None


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
    time_of_day: TimeOfDay | None = None  # "day"/"night"; omitted == any time


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

    def model_post_init(self, __context: object) -> None:
        if self.max_strength is None:
            object.__setattr__(self, "max_strength", self.strength)


class LairTreasureContent(BaseModel):
    """A lair's treasury block — explicit item refs + gold, optionally gated behind the core.

    Item dicts may carry a ``ref`` to a catalog entry (resolved at load). Random
    loot tables are out of scope: contents are deterministic.
    """

    items: list[ItemContent] = []
    gold: int = 0
    behind_core: bool = True


class LairContent(BaseModel):
    """A lair definition from YAML — a fixed monster home at one location."""

    name: LocalizedText
    faction: str
    location: str
    members: list[str] = []
    core: str | None = None
    respawn_interval: int = 86400
    depletion_chance: float = 0.0
    treasure: LairTreasureContent | None = None


# ---------------------------------------------------------------------------
# Entity models
# ---------------------------------------------------------------------------


def _validate_combat_position(value: list[int] | None) -> list[int] | None:
    """Canonical combat_position = (x, y) in FEET on the battle grid.

    Grid cells are 5 ft by 5 ft (D&D 5e). Values must be non-negative multiples of 5.
    A frequent authoring mistake is using cell indices (e.g. ``[5, 5]`` meaning
    "cell (5,5)") where the engine expects feet (``[25, 25]``). Fail fast to prevent
    silently misplaced creatures.
    """
    if value is None:
        return None
    if len(value) != 2:
        raise ValueError(f"combat_position must be [x, y] with 2 values in feet, got {value!r}")
    for v in value:
        if v < 0:
            raise ValueError(f"combat_position values must be non-negative (feet), got {value!r}")
        if v % 5 != 0:
            raise ValueError(
                f"combat_position values must be multiples of 5 (feet, not cell indices), got {value!r}. "
                f"For cell (col, row), pass [col*5, row*5]."
            )
    return value


class NpcContent(BaseModel):
    """An NPC definition from YAML."""

    model_config = ConfigDict(populate_by_name=True)

    name: LocalizedText
    race: Race = Race.HUMAN
    char_class: CharClass = Field(CharClass.COMMONER, alias="class")
    level: int = 1
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
    ai: BrainType = BrainType.RULE_BASED
    attacks: list[AttackContent] = []
    items: list[ItemContent] = []
    ability_scores: CoercedAbilityScores = AbilityScoresContent()
    class_features: dict[str, Any] = {}
    combat_position: list[int] | None = None
    reputation: dict[str, int] = {}
    memory: NpcMemoryContent | None = None
    xp_value: int = 0

    _validate_combat_position = field_validator("combat_position")(_validate_combat_position)


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
    combat_position: list[int] | None = None
    reputation: dict[str, int] = {}
    experience: int = 0
    level_up_available: bool = False

    _validate_combat_position = field_validator("combat_position")(_validate_combat_position)
