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


@dataclass(frozen=True)
class EntityDiedPayload(TypedPayload):
    entity_id: str
    location_id: str = ""
    killer_id: str | None = None


@dataclass(frozen=True)
class EntityMovePayload(TypedPayload):
    entity_id: str
    location_id: str = ""
    from_x: int | None = None
    from_y: int | None = None
    to_x: int | None = None
    to_y: int | None = None
    distance_ft: int | None = None
    direction: str | None = None
    ft: int = 5


@dataclass(frozen=True)
class CombatStartedPayload(TypedPayload):
    location_id: str
    turn_order: tuple[str, ...]
    turn_order_names: tuple[str, ...]


@dataclass(frozen=True)
class CombatEndedPayload(TypedPayload):
    location_id: str


@dataclass(frozen=True)
class EncounterSpawnedPayload(TypedPayload):
    legacy_aliases: ClassVar[dict[str, str]] = {"names": "spawned_names"}
    location_id: str
    spawned_names: tuple[str, ...]
    spawned_entity_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoundStartPayload(TypedPayload):
    location_id: str
    round_number: int


@dataclass(frozen=True)
class OpportunityAttackPayload(TypedPayload):
    attacker_id: str
    target_id: str
    location_id: str = ""


@dataclass(frozen=True)
class ReputationChangedPayload(TypedPayload):
    entity_id: str
    faction_id: str
    old_rep: int
    new_rep: int
    delta: int
    reason: str
    faction_name: str | None = None
    location_id: str = ""


@dataclass(frozen=True)
class XpGainedPayload(TypedPayload):
    entity_id: str
    amount: int
    new_total: int
    source_entity_id: str
    level_up_available: bool
    location_id: str = ""


@dataclass(frozen=True)
class TurnSkippedPayload(TypedPayload):
    entity_id: str
    reason: str
    conditions: tuple[str, ...]
    location_id: str = ""


@dataclass(frozen=True)
class AttackRequestedPayload(TypedPayload):
    attacker_id: str
    target_id: str
    smite_slot_level: int | None = None
    is_opportunity_attack: bool = False


@dataclass(frozen=True)
class RollComponentPayload(TypedPayload):
    source: str
    value: int
    dice: str = ""


@dataclass(frozen=True)
class AttackRollPayload(TypedPayload):
    natural: int
    components: tuple[RollComponentPayload, ...]
    total: int
    advantage: bool
    disadvantage: bool
    d20: object | None = None
    d20_alt: object | None = None


@dataclass(frozen=True)
class DamageComponentPayload(TypedPayload):
    source: str
    dice: str
    dice_detail: tuple[object, ...]
    amount: int
    type: str


@dataclass(frozen=True)
class AttackResolvedPayload(TypedPayload):
    attacker_id: str
    target_id: str
    hit: bool
    weapon: str
    critical: bool
    ac: int
    attack_roll: AttackRollPayload
    is_opportunity_attack: bool = False
    damage: int | None = None
    total_damage: int | None = None
    damage_components: tuple[DamageComponentPayload, ...] = ()


@dataclass(frozen=True)
class EntitySayPayload(TypedPayload):
    entity_id: str
    text: str


@dataclass(frozen=True)
class ActionFlavorPayload(TypedPayload):
    entity_id: str
    description: str = ""


@dataclass(frozen=True)
class EntityDashPayload(TypedPayload):
    entity_id: str
    extra_movement_ft: int


@dataclass(frozen=True)
class EntityActorPayload(TypedPayload):
    entity_id: str


@dataclass(frozen=True)
class EntityUseItemPayload(TypedPayload):
    entity_id: str
    item_name: str
    healed: int
    item_id: str = ""
    item_type: str = ""
    dice_detail: tuple[object, ...] = ()


@dataclass(frozen=True)
class EntityBlessPayload(TypedPayload):
    entity_id: str
    duration_rounds: int


@dataclass(frozen=True)
class EntitySecondWindPayload(TypedPayload):
    entity_id: str
    healed: int
    dice_detail: tuple[object, ...] = ()


@dataclass(frozen=True)
class EntityLayOnHandsPayload(TypedPayload):
    entity_id: str
    target_id: str
    requested: int = 0
    spent: int = 0
    healed: int = 0
    pool_before: int = 0
    pool_after: int = 0
    hp_before: int = 0
    hp_after: int = 0
    hp_max: int = 0


@dataclass(frozen=True)
class EquipmentPayload(TypedPayload):
    entity_id: str
    item_name: str
    item_id: str = ""


@dataclass(frozen=True)
class BuyPayload(TypedPayload):
    buyer_id: str
    merchant_id: str
    item_name: str
    price: int
    item_id: str = ""


@dataclass(frozen=True)
class SellPayload(TypedPayload):
    seller_id: str
    merchant_id: str
    item_name: str
    price: int
    item_id: str = ""


@dataclass(frozen=True)
class TakePayload(TypedPayload):
    actor_id: str
    target_id: str
    item_names: tuple[str, ...] = ()
    gold: int = 0


@dataclass(frozen=True)
class TimeAdvancedPayload(TypedPayload):
    seconds: int = 0


@dataclass(frozen=True)
class InspectPayload(TypedPayload):
    entity_id: str = ""
    inspect_target: str | None = None


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
    | EntityDiedPayload
    | EntityMovePayload
    | CombatStartedPayload
    | CombatEndedPayload
    | EncounterSpawnedPayload
    | RoundStartPayload
    | OpportunityAttackPayload
    | ReputationChangedPayload
    | XpGainedPayload
    | TurnSkippedPayload
    | AttackRequestedPayload
    | AttackResolvedPayload
    | EntitySayPayload
    | ActionFlavorPayload
    | EntityDashPayload
    | EntityActorPayload
    | EntityUseItemPayload
    | EntityBlessPayload
    | EntitySecondWindPayload
    | EntityLayOnHandsPayload
    | EquipmentPayload
    | BuyPayload
    | SellPayload
    | TakePayload
    | TimeAdvancedPayload
    | InspectPayload
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
    EventType.ENTITY_DIED: EntityDiedPayload,
    EventType.ENTITY_MOVE: EntityMovePayload,
    EventType.COMBAT_STARTED: CombatStartedPayload,
    EventType.COMBAT_ENDED: CombatEndedPayload,
    EventType.ENCOUNTER_SPAWNED: EncounterSpawnedPayload,
    EventType.ROUND_START: RoundStartPayload,
    EventType.OPPORTUNITY_ATTACK: OpportunityAttackPayload,
    EventType.REPUTATION_CHANGED: ReputationChangedPayload,
    EventType.XP_GAINED: XpGainedPayload,
    EventType.TURN_SKIPPED: TurnSkippedPayload,
    EventType.ENTITY_ATTACK_REQUESTED: AttackRequestedPayload,
    EventType.ENTITY_ATTACK: AttackResolvedPayload,
    EventType.ENTITY_SAY: EntitySayPayload,
    EventType.ENTITY_DODGE: ActionFlavorPayload,
    EventType.ENTITY_FLEE: ActionFlavorPayload,
    EventType.ENTITY_DASH: EntityDashPayload,
    EventType.ENTITY_DISENGAGE: EntityActorPayload,
    EventType.ENTITY_USE_ITEM: EntityUseItemPayload,
    EventType.ENTITY_BLESS: EntityBlessPayload,
    EventType.ENTITY_SECOND_WIND: EntitySecondWindPayload,
    EventType.ENTITY_ACTION_SURGE: EntityActorPayload,
    EventType.ENTITY_LAY_ON_HANDS: EntityLayOnHandsPayload,
    EventType.ENTITY_EQUIP: EquipmentPayload,
    EventType.ENTITY_UNEQUIP: EquipmentPayload,
    EventType.ENTITY_BUY: BuyPayload,
    EventType.ENTITY_SELL: SellPayload,
    EventType.ENTITY_TAKE: TakePayload,
    EventType.TIME_ADVANCED: TimeAdvancedPayload,
    EventType.CUSTOM: InspectPayload,
}
