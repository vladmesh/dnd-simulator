"""Entity hierarchy."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, TypeVar

import structlog

from dnd_simulator.core.class_features import ClassFeatures
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.items import Item
from dnd_simulator.core.resource import ResourcePool
from dnd_simulator.i18n import _

if TYPE_CHECKING:
    from dnd_simulator.core.brain import Brain

_F = TypeVar("_F", bound=ClassFeatures)

logger = structlog.get_logger(domain="entity")

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Race(Enum):
    """Playable races."""

    HUMAN = "human"
    ELF = "elf"
    DWARF = "dwarf"
    HALFLING = "halfling"
    GNOME = "gnome"
    HALF_ELF = "half_elf"
    HALF_ORC = "half_orc"
    TIEFLING = "tiefling"
    DRAGONBORN = "dragonborn"


class CharClass(Enum):
    """Character classes (including NPC commoner)."""

    COMMONER = "commoner"
    FIGHTER = "fighter"
    WIZARD = "wizard"
    ROGUE = "rogue"
    CLERIC = "cleric"
    RANGER = "ranger"
    PALADIN = "paladin"
    BARBARIAN = "barbarian"
    BARD = "bard"
    DRUID = "druid"
    MONK = "monk"
    SORCERER = "sorcerer"
    WARLOCK = "warlock"


class NpcRole(Enum):
    """NPC roles — determines schedule, dialogue, and merchant status."""

    COMMONER = "commoner"
    BLACKSMITH = "blacksmith"
    TAVERN_KEEPER = "tavern_keeper"
    GUARD = "guard"
    MERCHANT = "merchant"
    FARMER = "farmer"
    GLADIATOR = "gladiator"


class Alignment(Enum):
    """Nine classic alignments."""

    LAWFUL_GOOD = "lawful_good"
    NEUTRAL_GOOD = "neutral_good"
    CHAOTIC_GOOD = "chaotic_good"
    LAWFUL_NEUTRAL = "lawful_neutral"
    TRUE_NEUTRAL = "true_neutral"
    CHAOTIC_NEUTRAL = "chaotic_neutral"
    LAWFUL_EVIL = "lawful_evil"
    NEUTRAL_EVIL = "neutral_evil"
    CHAOTIC_EVIL = "chaotic_evil"


class Ability(Enum):
    """Six ability scores."""

    STR = "str"
    DEX = "dex"
    CON = "con"
    INT = "int"
    WIS = "wis"
    CHA = "cha"


class DamageType(Enum):
    """All D&D damage types."""

    # Physical
    SLASHING = "slashing"
    PIERCING = "piercing"
    BLUDGEONING = "bludgeoning"
    # Elemental
    FIRE = "fire"
    COLD = "cold"
    LIGHTNING = "lightning"
    THUNDER = "thunder"
    ACID = "acid"
    POISON = "poison"
    # Other
    RADIANT = "radiant"
    NECROTIC = "necrotic"
    FORCE = "force"
    PSYCHIC = "psychic"


class ResolveType(Enum):
    """How an attack is resolved."""

    ATTACK_ROLL = "attack_roll"  # d20 + mod vs AC
    SAVING_THROW = "saving_throw"  # target rolls save vs DC
    AUTO_HIT = "auto_hit"  # no roll, just damage


@dataclass(frozen=True)
class DamageComponent:
    """One damage term: dice expression + type."""

    dice: str  # "1d8", "2d6+1"
    type: DamageType


@dataclass(frozen=True)
class Attack:
    """A single-target damaging action — weapon or spell."""

    name: str  # "longsword", "fire_bolt"
    ability: Ability  # modifier source
    damage: tuple[DamageComponent, ...]  # base damage components
    reach: int = 5  # feet
    is_finesse: bool = False
    resolve: ResolveType = ResolveType.ATTACK_ROLL
    save_ability: Ability | None = None  # for SAVING_THROW targets


# ---------------------------------------------------------------------------
# Ability scores
# ---------------------------------------------------------------------------

DEFAULT_SCORES: dict[Ability, int] = {
    Ability.STR: 10,
    Ability.DEX: 10,
    Ability.CON: 10,
    Ability.INT: 10,
    Ability.WIS: 10,
    Ability.CHA: 10,
}


@dataclass
class AbilityScores:
    """Container for the six ability scores."""

    scores: dict[Ability, int] = field(default_factory=lambda: dict(DEFAULT_SCORES))

    def __getitem__(self, ability: Ability) -> int:
        return self.scores[ability]

    def __setitem__(self, ability: Ability, value: int) -> None:
        self.scores[ability] = value

    def modifier(self, ability: Ability) -> int:
        """D&D modifier: (score - 10) // 2."""
        return (self.scores[ability] - 10) // 2

    def to_dict(self) -> dict[str, int]:
        return {a.value: v for a, v in self.scores.items()}

    @classmethod
    def from_dict(cls, data: dict[str, int]) -> AbilityScores:
        return cls(scores={Ability(k): v for k, v in data.items()})


# ---------------------------------------------------------------------------
# Entity / Creature / Character hierarchy
# ---------------------------------------------------------------------------


@dataclass
class Entity:
    """Anything that exists in the game world."""

    id: str
    name: str
    location_id: str
    active: bool = True
    temporary: bool = False
    _last_seen_log_index: int = field(default=0, repr=False)

    def on_tick(self, hour: int) -> None:
        """Update state based on time of day. Override in subclasses."""


@dataclass
class Creature(Entity):
    """A living being with physical stats — animals, monsters, humanoids.

    Has ability scores, HP, and AC but no class, race, or alignment.
    Pure data + brain. Action execution goes through ActionDispatcher.
    """

    ability_scores: AbilityScores = field(default_factory=AbilityScores)
    max_hp: int = 4
    current_hp: int = 4
    ac: int = 10  # natural armor; 10 = unarmored default
    speed: int = 30  # movement speed in feet per turn
    attacks: tuple[Attack, ...] = ()
    in_combat: bool = False
    is_dodging: bool = False
    conditions: dict[Condition, int | None] = field(default_factory=dict)
    inventory: list[Item] = field(default_factory=list)
    equipped_weapon: Item | None = None
    equipped_armor: Item | None = None
    equipped_shield: Item | None = None
    equipped_head: Item | None = None
    equipped_feet: Item | None = None
    equipped_ring: Item | None = None
    resource_pools: list[ResourcePool] = field(default_factory=list)
    wake_at_seconds: int | None = None  # absolute game-time seconds; None = not waiting
    brain: Brain | None = field(default=None, repr=False)

    @property
    def memory_tags(self) -> list[str]:
        """Structured tags for brain decisions. Override in subclasses with memory."""
        return []

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    def take_damage(self, amount: int) -> int:
        """Apply damage, return actual damage dealt (after clamping to 0)."""
        actual = min(amount, self.current_hp)
        self.current_hp -= actual
        return actual

    def heal(self, amount: int) -> int:
        """Restore HP, return actual amount healed (capped at max_hp)."""
        actual = min(amount, self.max_hp - self.current_hp)
        self.current_hp += actual
        return actual

    def get_canned_response(self, hour: int) -> str | None:
        """Return a canned dialogue line, or None. Override in NPC subclasses."""
        return None


@dataclass
class Character(Creature):
    """A sentient being with D&D class, race, and social attributes."""

    race: Race = Race.HUMAN
    char_class: CharClass = CharClass.COMMONER
    level: int = 1
    alignment: Alignment = Alignment.TRUE_NEUTRAL
    appearance: str = ""
    gold: int = 0
    class_features: list[ClassFeatures] = field(default_factory=list)

    def get_feature(self, feature_type: type[_F]) -> _F | None:
        """Return the first class feature of the given type, or None."""
        for f in self.class_features:
            if isinstance(f, feature_type):
                return f
        return None

    @property
    def is_merchant(self) -> bool:
        """Whether this character can trade. Always False for base Character."""
        return False

    def get_npc_data(self) -> dict[str, str]:
        """Return NPC metadata for LLM prompts. Override in Npc."""
        return {}

    def perceive(self, target: Entity) -> str:
        """What this character sees when looking at target.

        Characters from the same settlement know each other by name.
        Strangers are described by race + appearance.
        Visible conditions are appended.
        """
        if isinstance(target, Character):
            known = self._knows_by_name(target)
            parts: list[str] = []
            if known:
                parts.append(target.name)
            else:
                race_label = _(target.race.value.replace("_", " "))
                parts.append(race_label)
                if target.appearance:
                    parts.append(target.appearance)
            # Wound status
            if target.current_hp < target.max_hp // 2:
                parts.append(_("looks wounded"))
            # Visible conditions
            if target.conditions:
                parts.extend(_(c.value) for c in sorted(target.conditions, key=lambda c: c.value))
            return ", ".join(parts)
        if isinstance(target, Creature):
            parts = [target.name]
            if target.current_hp < target.max_hp // 2:
                parts.append(_("looks wounded"))
            if target.conditions:
                parts.extend(_(c.value) for c in sorted(target.conditions, key=lambda c: c.value))
            return ", ".join(parts)
        return target.name

    def _knows_by_name(self, target: Character) -> bool:
        """Check if this character knows the target by name."""
        self_settlement = getattr(self, "settlement_id", None)
        target_settlement = getattr(target, "settlement_id", None)
        if self_settlement and target_settlement:
            return bool(self_settlement == target_settlement)
        return False
