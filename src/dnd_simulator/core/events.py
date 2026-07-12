"""Typed payload contracts for world events."""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, ClassVar, cast

from dnd_simulator.core.models import EventType


class TypedPayload:
    """Typed fields with a temporary read-only mapping facade for unmigrated consumers."""

    legacy_aliases: ClassVar[dict[str, str]] = {}
    legacy_type: ClassVar[str | None] = None

    def __getitem__(self, key: str) -> object:
        value = self.get(key, None)
        if value is None and key not in self:
            raise KeyError(key)
        return value

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return (key == "type" and self.legacy_type is not None) or any(
            field.name == self.legacy_aliases.get(key, key) for field in fields(cast(Any, self))
        )

    def keys(self) -> tuple[str, ...]:
        reverse_aliases = {value: key for key, value in self.legacy_aliases.items()}
        names = tuple(reverse_aliases.get(field.name, field.name) for field in fields(cast(Any, self)))
        return ("type", *names) if self.legacy_type is not None else names

    def get(self, key: str, default: object = None) -> object:
        if key == "type" and self.legacy_type is not None:
            return self.legacy_type
        name = self.legacy_aliases.get(key, key)
        return getattr(self, name, default)


@dataclass(frozen=True)
class WeatherChangedPayload(TypedPayload):
    region_id: str
    old_weather: str
    new_weather: str
    temperature: float


@dataclass(frozen=True)
class SquadMovePayload(TypedPayload):
    legacy_aliases: ClassVar[dict[str, str]] = {"from": "from_location_id", "to": "to_location_id"}
    squad_id: str
    squad_name: str
    from_location_id: str
    to_location_id: str


@dataclass(frozen=True)
class SquadCombatPayload(TypedPayload):
    location_id: str
    winner_id: str
    winner_name: str
    loser_id: str
    loser_name: str
    winner_strength: int
    loser_strength: int


@dataclass(frozen=True)
class SquadMaterializedPayload(TypedPayload):
    squad_id: str
    squad_name: str
    location_id: str
    creature_count: int


@dataclass(frozen=True)
class SquadDematerializedPayload(TypedPayload):
    squad_id: str
    squad_name: str
    location_id: str
    new_strength: int


@dataclass(frozen=True)
class LairDematerializedPayload(TypedPayload):
    lair_id: str
    core_alive: bool
    alive_members: tuple[str, ...]
    at_seconds: int


@dataclass(frozen=True)
class WarDeclaredPayload(TypedPayload):
    legacy_type: ClassVar[str] = "war_declared"
    legacy_aliases: ClassVar[dict[str, str]] = {"aggressor": "aggressor_id", "target": "target_id"}
    aggressor_id: str
    target_id: str


@dataclass(frozen=True)
class PeaceDeclaredPayload(TypedPayload):
    legacy_type: ClassVar[str] = "peace"
    legacy_aliases: ClassVar[dict[str, str]] = {"nation_a": "nation_a_id", "nation_b": "nation_b_id"}
    nation_a_id: str
    nation_b_id: str


@dataclass(frozen=True)
class TradeAgreementPayload(TypedPayload):
    legacy_type: ClassVar[str] = "trade_agreement"
    legacy_aliases: ClassVar[dict[str, str]] = {"nation_a": "nation_a_id", "nation_b": "nation_b_id"}
    nation_a_id: str
    nation_b_id: str


@dataclass(frozen=True)
class RegionConqueredPayload(TypedPayload):
    legacy_type: ClassVar[str] = "region_conquered"
    legacy_aliases: ClassVar[dict[str, str]] = {
        "winner": "winner_id",
        "loser": "loser_id",
        "region": "region_id",
    }
    winner_id: str
    loser_id: str
    region_id: str


@dataclass(frozen=True)
class RebellionPayload(TypedPayload):
    legacy_type: ClassVar[str] = "rebellion"
    legacy_aliases: ClassVar[dict[str, str]] = {"nation": "nation_id"}
    nation_id: str


@dataclass(frozen=True)
class LeaderDiedPayload(TypedPayload):
    legacy_type: ClassVar[str] = "leader_died"
    legacy_aliases: ClassVar[dict[str, str]] = {"nation": "nation_id"}
    nation_id: str
    old_leader: str
    new_leader: str


@dataclass(frozen=True)
class NationDestroyedPayload(TypedPayload):
    legacy_type: ClassVar[str] = "nation_destroyed"
    legacy_aliases: ClassVar[dict[str, str]] = {"nation": "nation_id"}
    nation_id: str


@dataclass(frozen=True)
class SettlementDamagedPayload(TypedPayload):
    legacy_type: ClassVar[str] = "settlement_damaged"
    legacy_aliases: ClassVar[dict[str, str]] = {"settlement": "settlement_id", "region": "region_id"}
    settlement_id: str
    region_id: str


EventPayload = (
    WeatherChangedPayload
    | SquadMovePayload
    | SquadCombatPayload
    | SquadMaterializedPayload
    | SquadDematerializedPayload
    | LairDematerializedPayload
    | WarDeclaredPayload
    | PeaceDeclaredPayload
    | TradeAgreementPayload
    | RegionConqueredPayload
    | RebellionPayload
    | LeaderDiedPayload
    | NationDestroyedPayload
    | SettlementDamagedPayload
)


EVENT_PAYLOAD_TYPES: dict[EventType, type[object]] = {
    EventType.WEATHER_CHANGED: WeatherChangedPayload,
    EventType.SQUAD_MOVE: SquadMovePayload,
    EventType.SQUAD_COMBAT: SquadCombatPayload,
    EventType.SQUAD_MATERIALIZED: SquadMaterializedPayload,
    EventType.SQUAD_DEMATERIALIZED: SquadDematerializedPayload,
    EventType.LAIR_DEMATERIALIZED: LairDematerializedPayload,
    EventType.WAR_DECLARED: WarDeclaredPayload,
    EventType.PEACE_DECLARED: PeaceDeclaredPayload,
    EventType.TRADE_AGREEMENT: TradeAgreementPayload,
    EventType.REGION_CONQUERED: RegionConqueredPayload,
    EventType.REBELLION: RebellionPayload,
    EventType.LEADER_DIED: LeaderDiedPayload,
    EventType.NATION_DESTROYED: NationDestroyedPayload,
    EventType.SETTLEMENT_DAMAGED: SettlementDamagedPayload,
}
