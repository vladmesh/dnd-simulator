"""Entity hierarchy and world awareness."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dnd_simulator.core.models import Query
from dnd_simulator.core.world import World

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
    region_id: str


@dataclass
class Creature(Entity):
    """A living being with physical stats — animals, monsters, humanoids.

    Has ability scores, HP, and AC but no class, race, or alignment.
    """

    ability_scores: AbilityScores = field(default_factory=AbilityScores)
    max_hp: int = 4
    current_hp: int = 4
    ac: int = 10  # natural armor; 10 = unarmored default


@dataclass
class Character(Creature):
    """A sentient being with D&D class, race, and social attributes."""

    race: Race = Race.HUMAN
    char_class: CharClass = CharClass.COMMONER
    level: int = 1
    alignment: Alignment = Alignment.TRUE_NEUTRAL
    appearance: str = ""
    gold: int = 0

    def perceive(self, target: Entity) -> str:
        """What this character sees when looking at target.

        Static for now — all observers see the same thing.
        Later: observer's WIS/INT affects depth of perception.
        """
        if isinstance(target, Character):
            parts: list[str] = []
            # Race is always visible
            race_label = target.race.value.replace("_", " ")
            parts.append(race_label)
            # Appearance text
            if target.appearance:
                parts.append(target.appearance)
            # Wound status
            if target.current_hp < target.max_hp // 2:
                parts.append("выглядит раненым")
            return ", ".join(parts)
        if isinstance(target, Creature):
            parts = [target.name]
            if target.current_hp < target.max_hp // 2:
                parts.append("выглядит раненым")
            return ", ".join(parts)
        return target.name


# ---------------------------------------------------------------------------
# World awareness (unchanged)
# ---------------------------------------------------------------------------


def build_awareness(world: World, region_id: str) -> dict[str, Any]:
    """Gather what a character in a region knows about the world."""
    time = world.time

    weather = world.query_layer("geography", Query(question="weather", params={"region_id": region_id}))
    region = world.query_layer("geography", Query(question="region_info", params={"region_id": region_id}))
    settlements = world.query_layer(
        "settlements", Query(question="region_settlements", params={"region_id": region_id})
    )
    owner = world.query_layer("politics", Query(question="region_owner", params={"region_id": region_id}))

    nation_info = None
    if owner.value:
        nation_info = world.query_layer("politics", Query(question="nation_info", params={"nation_id": owner.value}))

    return {
        "time": {
            "hour": time.hour,
            "day": time.day,
            "month": time.month,
            "year": time.year,
        },
        "weather": weather.value,
        "location": region.value,
        "settlements": settlements.value,
        "territory": owner.value,
        "nation": nation_info.value if nation_info else None,
    }
