from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum, StrEnum
from typing import Any


class EntityKind(StrEnum):
    """Runtime entity discriminator for save/load and query filtering.

    Distinct from content_loader.EntityType (which enumerates YAML content kinds).
    PLAYER / NPC / CREATURE / CONTAINER are used in EntitiesLayer save data;
    PLAYER / NPC / MONSTER are used by the detail/query API surface.
    """

    PLAYER = "player"
    NPC = "npc"
    CREATURE = "creature"
    CONTAINER = "container"
    MONSTER = "monster"


class TerrainType(Enum):
    """Types of terrain a region can have."""

    PLAINS = "plains"
    FOREST = "forest"
    HILLS = "hills"
    MOUNTAINS = "mountains"
    DESERT = "desert"
    SWAMP = "swamp"
    COAST = "coast"
    TUNDRA = "tundra"


class WeatherCondition(Enum):
    """Possible weather states."""

    CLEAR = "clear"
    CLOUDY = "cloudy"
    LIGHT_RAIN = "light_rain"
    HEAVY_RAIN = "heavy_rain"
    STORM = "storm"
    SNOW = "snow"
    BLIZZARD = "blizzard"
    FOG = "fog"


class Season(Enum):
    """Seasons of the year."""

    SPRING = "spring"
    SUMMER = "summer"
    AUTUMN = "autumn"
    WINTER = "winter"


class QueryType(Enum):
    """Types of queries that can be sent to layers."""

    # Geography
    WEATHER = "weather"
    CONNECTIONS = "connections"
    TRAVEL_TIME = "travel_time"
    DAYLIGHT = "daylight"
    IS_DAYLIGHT = "is_daylight"
    REGION_INFO = "region_info"
    REGIONS = "regions"
    LOCATION_REGION = "location_region"

    # Politics
    NATIONS = "nations"
    NATION_INFO = "nation_info"
    RELATIONS = "relations"
    REGION_OWNER = "region_owner"
    FACTION_RELATION = "faction_relation"
    FACTION_NAME = "faction_name"

    # Settlements
    SETTLEMENTS = "settlements"
    SETTLEMENT_INFO = "settlement_info"
    REGION_SETTLEMENTS = "region_settlements"
    REGION_INCOME = "region_income"

    # Ecology
    SQUADS_AT_LOCATION = "squads_at_location"
    SQUAD_INFO = "squad_info"
    LAIRS_AT_LOCATION = "lairs_at_location"

    # Entities
    PLAYERS = "players"
    PLAYER = "player"
    ENTITIES_AT_LOCATION = "entities_at_location"
    ENTITY_INFO = "entity_info"
    ALL_ENTITIES = "all_entities"
    ALL_CREATURES = "all_creatures"
    ALL_NPCS = "all_npcs"
    NPC_INFO = "npc_info"
    PERCEIVED_LOG = "perceived_log"
    NEW_PERCEIVED_EVENTS = "new_perceived_events"
    NEW_RAW_EVENTS = "new_raw_events"
    COMBAT_INFO = "combat_info"
    PERCEIVE_ENTITY = "perceive_entity"


class EventType(Enum):
    """Types of events that can flow between layers."""

    ENTITY_DIED = "entity_died"
    ENTITY_SAY = "entity_say"
    ENTITY_ATTACK = "entity_attack"
    ENTITY_DODGE = "entity_dodge"
    ENTITY_FLEE = "entity_flee"
    ENTITY_MOVE = "entity_move"
    ENTITY_DASH = "entity_dash"
    ENTITY_DISENGAGE = "entity_disengage"
    ENTITY_USE_ITEM = "entity_use_item"
    ENTITY_BLESS = "entity_bless"
    ENTITY_SECOND_WIND = "entity_second_wind"
    ENTITY_ACTION_SURGE = "entity_action_surge"
    ENTITY_LAY_ON_HANDS = "entity_lay_on_hands"
    ENTITY_EQUIP = "entity_equip"
    ENTITY_UNEQUIP = "entity_unequip"
    ENTITY_BUY = "entity_buy"
    ENTITY_SELL = "entity_sell"
    ENTITY_TAKE = "entity_take"
    TURN_SKIPPED = "turn_skipped"
    COMBAT_STARTED = "combat_started"
    COMBAT_ENDED = "combat_ended"
    ENCOUNTER_SPAWNED = "encounter_spawned"
    WEATHER_CHANGED = "weather_changed"
    WAR_DECLARED = "war_declared"
    PEACE_DECLARED = "peace_declared"
    TRADE_AGREEMENT = "trade_agreement"
    REGION_CONQUERED = "region_conquered"
    REBELLION = "rebellion"
    LEADER_DIED = "leader_died"
    NATION_DESTROYED = "nation_destroyed"
    SETTLEMENT_DAMAGED = "settlement_damaged"
    TIME_ADVANCED = "time_advanced"
    SQUAD_MOVE = "squad_move"
    SQUAD_COMBAT = "squad_combat"
    SQUAD_MATERIALIZED = "squad_materialized"
    SQUAD_DEMATERIALIZED = "squad_dematerialized"
    LAIR_DEMATERIALIZED = "lair_dematerialized"
    ROUND_START = "round_start"
    OPPORTUNITY_ATTACK = "opportunity_attack"
    REPUTATION_CHANGED = "reputation_changed"
    XP_GAINED = "xp_gained"
    CUSTOM = "custom"


class TimeOfDay(StrEnum):
    """Day/night phase tag for content that varies with the clock (e.g. encounters)."""

    DAY = "day"
    NIGHT = "night"


@dataclass(frozen=True)
class GameDateTime:
    """In-game date and time."""

    year: int = 1
    month: int = 1
    day: int = 1
    hour: int = 0
    minute: int = 0
    second: int = 0

    def advance(self, hours: int = 0, days: int = 0, seconds: int = 0) -> GameDateTime:
        total_seconds = self.second + seconds
        total_minutes = self.minute + total_seconds // 60
        second = total_seconds % 60

        total_hours = self.hour + hours + total_minutes // 60
        minute = total_minutes % 60

        total_days = self.day + days + total_hours // 24
        hour = total_hours % 24

        # Simplified: 30 days per month, 12 months per year
        month = self.month + (total_days - 1) // 30
        day = (total_days - 1) % 30 + 1
        year = self.year + (month - 1) // 12
        month = (month - 1) % 12 + 1

        return GameDateTime(year=year, month=month, day=day, hour=hour, minute=minute, second=second)

    def to_dict(self) -> dict[str, int]:
        """Serialize to a plain dict (save format)."""
        return {
            "year": self.year,
            "month": self.month,
            "day": self.day,
            "hour": self.hour,
            "minute": self.minute,
            "second": self.second,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameDateTime:
        """Restore from a save dict. Missing fields fall back to defaults (backward compat)."""
        return cls(
            year=int(data.get("year", 1)),
            month=int(data.get("month", 1)),
            day=int(data.get("day", 1)),
            hour=int(data.get("hour", 0)),
            minute=int(data.get("minute", 0)),
            second=int(data.get("second", 0)),
        )

    def to_total_seconds(self) -> int:
        """Convert to absolute seconds since epoch (year 1, month 1, day 1)."""
        return (
            ((self.year - 1) * 12 + (self.month - 1)) * 30 * 86400
            + (self.day - 1) * 86400
            + self.hour * 3600
            + self.minute * 60
            + self.second
        )


@dataclass(frozen=True)
class TimeDelta:
    """Duration of time in game, measured in seconds."""

    seconds: int = 0

    @property
    def rounds(self) -> int:
        """Number of complete D&D rounds (6 seconds each)."""
        return self.seconds // 6

    @property
    def total_hours(self) -> int:
        """Number of complete hours."""
        return self.seconds // 3600

    @classmethod
    def from_rounds(cls, rounds: int) -> TimeDelta:
        return cls(seconds=rounds * 6)

    @classmethod
    def from_hours(cls, hours: int) -> TimeDelta:
        return cls(seconds=hours * 3600)

    @classmethod
    def from_days(cls, days: int) -> TimeDelta:
        return cls(seconds=days * 86400)


@dataclass(frozen=True)
class Event:
    """An event that occurred in the world."""

    event_type: EventType
    source_layer: str
    # Transitional until every EventType is migrated in Phase 1 task 3.
    data: Any = field(default_factory=dict)
    description: str = ""
    observer_ids: frozenset[str] | None = None  # None = public (all in area see it)

    def __post_init__(self) -> None:
        from dnd_simulator.core.events import EVENT_PAYLOAD_TYPES

        expected = EVENT_PAYLOAD_TYPES.get(self.event_type)
        if expected is not None and isinstance(self.data, dict):
            values = dict(self.data)
            if self.event_type is EventType.SQUAD_MOVE:
                values["from_location_id"] = values.pop("from")
                values["to_location_id"] = values.pop("to")
            if self.event_type is EventType.ENCOUNTER_SPAWNED and "names" in values:
                values["spawned_names"] = values.pop("names")
            if self.event_type is EventType.LAIR_DEMATERIALIZED and isinstance(values.get("alive_members"), list):
                values["alive_members"] = tuple(values["alive_members"])
            tuple_fields = {
                EventType.COMBAT_STARTED: ("turn_order", "turn_order_names"),
                EventType.ENCOUNTER_SPAWNED: ("spawned_entity_ids", "spawned_names"),
                EventType.TURN_SKIPPED: ("conditions",),
            }
            for name in tuple_fields.get(self.event_type, ()):
                if isinstance(values.get(name), list):
                    values[name] = tuple(values[name])
            try:
                object.__setattr__(self, "data", expected(**values))
            except TypeError as exc:
                raise TypeError(f"invalid {self.event_type.name} payload: {exc}") from exc
        if expected is not None and not isinstance(self.data, expected):
            raise TypeError(f"{self.event_type.name} requires {expected.__name__}, got {type(self.data).__name__}")


@dataclass(frozen=True)
class ActionResult:
    """Outcome of an action submitted to the world.

    success=True means the action was executed (even if attack missed).
    success=False means it was rejected (invalid target, wrong region, etc.)
    and the actor should try something else.
    """

    success: bool = True
    error: str = ""
    events: list[Event] = field(default_factory=list)


@dataclass(frozen=True)
class Query:
    """A question to a specific layer."""

    question: QueryType
    params: dict[str, Any] = field(default_factory=dict)


class FactionRelation(Enum):
    """Creature-level faction relation. Drives hostility/alliance."""

    HOSTILE = "hostile"
    NEUTRAL = "neutral"
    FRIENDLY = "friendly"


@dataclass(frozen=True)
class Answer:
    """Response from a layer to a query."""

    value: object
    description: str = ""


# Callback types for layer isolation — layers receive these instead of World
QueryFn = Callable[[str, Query], Answer]
"""Query another layer: (target_layer_name, query) -> answer. Only layers below the caller."""

EmitFn = Callable[[Event], ActionResult]
"""Emit an event into the world: (event) -> action_result."""
