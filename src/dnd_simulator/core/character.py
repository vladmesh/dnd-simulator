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
    region_id: str
    active: bool = True
    _last_seen_log_index: int = field(default=0, repr=False)

    def on_tick(self, hour: int) -> None:
        """Update state based on time of day. Override in subclasses."""

    def take_turn(self, world: World) -> None:
        """React to the world: build awareness, decide, execute. Override in subclasses."""
        raise NotImplementedError


@dataclass
class Creature(Entity):
    """A living being with physical stats — animals, monsters, humanoids.

    Has ability scores, HP, and AC but no class, race, or alignment.
    """

    ability_scores: AbilityScores = field(default_factory=AbilityScores)
    max_hp: int = 4
    current_hp: int = 4
    ac: int = 10  # natural armor; 10 = unarmored default
    speed: int = 30  # movement speed in feet per turn
    attacks: tuple[Attack, ...] = ()
    in_combat: bool = False
    is_dodging: bool = False

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

        Characters from the same settlement know each other by name.
        Strangers are described by race + appearance.
        """
        if isinstance(target, Character):
            known = self._knows_by_name(target)
            parts: list[str] = []
            if known:
                parts.append(target.name)
            else:
                race_label = target.race.value.replace("_", " ")
                parts.append(race_label)
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

    def perceive_by_id(self, entity_id: str, world: World) -> str:
        """Perceive another entity by ID, looking it up from the entities layer."""
        from dnd_simulator.layers.entities.layer import EntitiesLayer

        for layer in world.layers:
            if isinstance(layer, EntitiesLayer):
                target = layer.get_entity(entity_id)
                if target and isinstance(target, Entity):
                    return self.perceive(target)
        return entity_id

    def _knows_by_name(self, target: Character) -> bool:
        """Check if this character knows the target by name."""
        # Import here to avoid circular dependency
        from dnd_simulator.layers.entities.models import Npc

        # NPCs from the same settlement know each other
        if isinstance(self, Npc) and isinstance(target, Npc):
            return bool(self.settlement_id and self.settlement_id == target.settlement_id)
        return False


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


def build_combat_awareness(world: World, entity: Character) -> dict[str, Any]:
    """Gather combat-focused awareness — only what matters in a fight."""
    from dnd_simulator.core.combat import Position
    from dnd_simulator.rules.movement import direction_label, grid_distance

    entities_answer = world.query_layer(
        "entities", Query(question="entities_in_region", params={"region_id": entity.region_id})
    )

    # Get battle map positions from combat info
    combat_answer = world.query_layer("entities", Query(question="combat_info", params={"region_id": entity.region_id}))
    round_number = combat_answer.value["round_number"] if combat_answer.value else 1
    battle_map_positions: dict[str, Position] = combat_answer.value.get("positions", {}) if combat_answer.value else {}
    my_pos = battle_map_positions.get(entity.id)

    nearby: list[dict[str, object]] = []
    for e in entities_answer.value:
        if e["id"] != entity.id:
            desc = entity.perceive_by_id(e["id"], world)
            entry: dict[str, object] = {"id": str(e["id"]), "description": desc}
            other_pos = battle_map_positions.get(str(e["id"]))
            if my_pos is not None and other_pos is not None:
                entry["distance_ft"] = grid_distance(my_pos, other_pos)
                dx = other_pos.x - my_pos.x
                dy = other_pos.y - my_pos.y
                entry["direction"] = direction_label(dx, dy)
            nearby.append(entry)

    weapon_name = "кулаки"
    weapon_damage = "1"
    if entity.attacks:
        weapon_name = entity.attacks[0].name
        weapon_damage = str(entity.attacks[0].damage[0].dice)

    wall_descriptions: list[str] = combat_answer.value.get("wall_descriptions", []) if combat_answer.value else []

    return {
        "self_hp": entity.current_hp,
        "self_max_hp": entity.max_hp,
        "self_ac": entity.ac,
        "self_speed": entity.speed,
        "self_weapon": weapon_name,
        "self_weapon_damage": weapon_damage,
        "nearby": nearby,
        "round_number": round_number,
        "walls": wall_descriptions,
    }
