"""Pydantic save-state models for EntitiesLayer."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.brain import BrainType
from dnd_simulator.core.character import Ability, Alignment, CharClass, DamageType, NpcRole, Race
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.inner_self import (
    DEFAULT_RELATIONSHIP_INTENSITY,
    RELATIONSHIP_INTENSITY_MAX,
    RELATIONSHIP_INTENSITY_MIN,
    GoalStatus,
    GoalType,
    Mood,
    RelationshipType,
)
from dnd_simulator.core.intent import IntentType
from dnd_simulator.core.items import ArmorCategory, EquipmentSlot, ItemType, WeaponCategory
from dnd_simulator.core.lair import LairMemberRole
from dnd_simulator.core.models import EntityKind, EventType
from dnd_simulator.core.modifiers import ModifierOp, StatType
from dnd_simulator.core.resource import RestType
from dnd_simulator.core.triggers import ActivationTrigger, EventCondition, GmActivationOverride, TriggerDefinition


class SaveModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class DamageComponentSave(SaveModel):
    dice: str
    type: DamageType


class AttackSave(SaveModel):
    name: str
    ability: Ability
    damage: list[DamageComponentSave] = Field(default_factory=list)
    reach: int = 5
    is_finesse: bool = False


class AbilityScoresSave(SaveModel):
    str_: int = Field(10, alias="str")
    dex: int = 10
    con: int = 10
    int_: int = Field(10, alias="int")
    wis: int = 10
    cha: int = 10


class ModifierSave(SaveModel):
    stat: StatType
    op: ModifierOp
    value: int = 0
    source: str = ""


class ItemSave(SaveModel):
    id: str | None = None
    name: str = ""
    type: ItemType = ItemType.WEAPON
    equipped: bool = False
    price: int | None = None
    weapon_id: str | None = None
    attack_name: str | None = None
    category: WeaponCategory | ArmorCategory | None = None
    damage: list[DamageComponentSave] | None = None
    reach: int | None = None
    ability: Ability | None = None
    modifier: int | None = None
    is_magic: bool | None = None
    is_finesse: bool | None = None
    is_two_handed: bool | None = None
    is_light: bool | None = None
    is_heavy: bool | None = None
    grant_conditions: list[Condition] | None = None
    grant_actions: list[ActionType] | None = None
    armor_id: str | None = None
    base_ac: int | None = None
    max_dex_bonus: int | None = None
    strength_req: int | None = None
    shield_id: str | None = None
    ac_bonus: int | None = None
    accessory_id: str | None = None
    slot: EquipmentSlot | None = None
    modifiers: list[ModifierSave] | None = Field(None, alias="grant_modifiers")
    heal_dice: str | None = None


class ClassFeaturesSave(SaveModel):
    fighting_style: str | None = None
    sneak_attack_dice: int | None = None


class RelationshipSave(SaveModel):
    target_id: str = Field(min_length=1)
    type: RelationshipType
    intensity: int = Field(DEFAULT_RELATIONSHIP_INTENSITY, ge=RELATIONSHIP_INTENSITY_MIN, le=RELATIONSHIP_INTENSITY_MAX)


class GoalSave(SaveModel):
    type: GoalType | None = None
    target_id: str | None = None
    text: str | None = None
    status: GoalStatus = GoalStatus.ACTIVE

    @model_validator(mode="after")
    def validate_shape(self) -> GoalSave:
        if self.type is not None and self.target_id and self.text is None:
            return self
        if self.type is None and self.target_id is None and self.text:
            return self
        raise ValueError("goal must be typed (type + target_id) or freeform (text)")


class AlignmentAccumulationSave(SaveModel):
    law_chaos: int = 0
    good_evil: int = 0


class BufferedPerceivedEventSave(SaveModel):
    event_type: EventType
    actor_id: str | None = None
    target_id: str | None = None
    description: str
    at_seconds: int
    heard: bool = False


class InnerSelfSave(SaveModel):
    relations: list[RelationshipSave] = Field(default_factory=list)
    mood: Mood = Mood.NEUTRAL
    goals: list[GoalSave] = Field(default_factory=list)
    alignment: AlignmentAccumulationSave = Field(default_factory=AlignmentAccumulationSave)
    journal: str = ""
    thoughts: list[str] = Field(default_factory=list)
    current_conversation: str = ""
    perceived_event_buffer: list[BufferedPerceivedEventSave] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_relations(self) -> InnerSelfSave:
        keys = [(relation.target_id, relation.type) for relation in self.relations]
        if len(keys) != len(set(keys)):
            raise ValueError("duplicate relationship type for target")
        return self


class ResourcePoolSave(SaveModel):
    id: str
    max_uses: int
    current_uses: int
    reset_on: RestType


class TurnBudgetSave(SaveModel):
    actions: int
    bonus_actions: int
    movement_remaining: int
    reaction: int


class TimedIntentSave(SaveModel):
    kind: Literal[IntentType.WAIT, IntentType.SLEEP]
    started_at_seconds: int
    wake_at_seconds: int
    rest_type: RestType | None = None


class TravelIntentSave(SaveModel):
    kind: Literal[IntentType.TRAVEL]
    started_at_seconds: int
    destination_id: str
    remaining_route: tuple[str, ...] = Field(min_length=1)
    next_arrival_seconds: int

    @model_validator(mode="after")
    def validate_route(self) -> TravelIntentSave:
        if self.remaining_route[-1] != self.destination_id:
            raise ValueError("travel destination must be the final route node")
        if self.next_arrival_seconds < self.started_at_seconds:
            raise ValueError("arrival time cannot precede journey start time")
        return self


IntentSave = Annotated[TimedIntentSave | TravelIntentSave, Field(discriminator="kind")]


class EventConditionSave(SaveModel):
    event: EventType
    match: dict[str, object] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_payload_fields(self) -> EventConditionSave:
        EventCondition.from_mapping(self.event, self.match)
        return self


class ActivationTriggerSave(SaveModel):
    id: str = Field(min_length=1)
    on: EventConditionSave
    until: EventConditionSave
    armed: bool = True
    active: bool = False

    def to_domain(self) -> ActivationTrigger:
        return ActivationTrigger(
            definition=TriggerDefinition(
                id=self.id,
                on=EventCondition.from_mapping(self.on.event, self.on.match),
                until=EventCondition.from_mapping(self.until.event, self.until.match),
            ),
            armed=self.armed,
            active=self.active,
        )


class EntitySaveBase(SaveModel):
    id: str
    name: str
    location_id: str
    active: bool
    temporary: bool = False
    faction_id: str = ""


class LairOriginSave(SaveModel):
    lair_id: str
    template_id: str
    role: LairMemberRole


class CreatureFields(EntitySaveBase):
    max_hp: int
    current_hp: int
    ac: int
    speed: int
    ability_scores: AbilityScoresSave
    attacks: list[AttackSave] = Field(default_factory=list)
    in_combat: bool = False
    is_dodging: bool = False
    is_disengaging: bool = False
    turn_budget: TurnBudgetSave | None = None
    conditions: dict[Condition, int | None] = Field(default_factory=dict)
    inventory: list[ItemSave] = Field(default_factory=list)
    gold: int = 0
    equipped_weapon: ItemSave | None = None
    equipped_armor: ItemSave | None = None
    equipped_shield: ItemSave | None = None
    equipped_head: ItemSave | None = None
    equipped_feet: ItemSave | None = None
    equipped_ring: ItemSave | None = None
    resource_pools: list[ResourcePoolSave] = Field(default_factory=list)
    reputation: dict[str, int] = Field(default_factory=dict)
    xp_value: int = 0
    squad_id: str | None = None
    lair_origin: LairOriginSave | None = None
    is_anchor: bool = False
    always_active: bool = False
    gm_activation_override: GmActivationOverride = GmActivationOverride.AUTOMATIC
    triggers: list[ActivationTriggerSave] = Field(default_factory=list)
    current_intent: IntentSave | None = None
    combat_position: tuple[int, int] | None = None

    @model_validator(mode="after")
    def validate_trigger_ids(self) -> CreatureFields:
        ids = [trigger.id for trigger in self.triggers]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate trigger id")
        return self


class CreatureSave(CreatureFields):
    entity_type: Literal[EntityKind.CREATURE]
    inner_self: InnerSelfSave | None = None


class PlayerSave(CreatureFields):
    entity_type: Literal[EntityKind.PLAYER]
    race: Race
    class_: CharClass = Field(alias="class")
    level: int
    alignment: Alignment
    appearance: str = ""
    hp: int
    start_location: str
    experience: int
    level_up_available: bool
    items: list[ItemSave] = Field(default_factory=list)
    class_features: ClassFeaturesSave = Field(default_factory=ClassFeaturesSave)


class NpcSave(CreatureFields):
    entity_type: Literal[EntityKind.NPC]
    race: Race
    class_: CharClass = Field(alias="class")
    level: int = 1
    alignment: Alignment = Alignment.TRUE_NEUTRAL
    role: NpcRole
    personality: str
    description: str = ""
    settlement_id: str
    location_override: str | None = None
    inner_self: InnerSelfSave
    ai_type: BrainType
    hp: int
    ai: BrainType
    start_location: str
    items: list[ItemSave] = Field(default_factory=list)
    class_features: ClassFeaturesSave = Field(default_factory=ClassFeaturesSave)


class ContainerSave(EntitySaveBase):
    entity_type: Literal[EntityKind.CONTAINER]
    is_open: bool
    gold: int
    inventory: list[ItemSave] = Field(default_factory=list)


EntitySave = Annotated[PlayerSave | NpcSave | CreatureSave | ContainerSave, Field(discriminator="entity_type")]
EntitySaveAdapter: TypeAdapter[EntitySave] = TypeAdapter(EntitySave)


class PositionSave(SaveModel):
    x: int
    y: int


class WallSave(SaveModel):
    x1: int
    y1: int
    x2: int
    y2: int


class BattleMapSave(SaveModel):
    width: int
    height: int
    positions: dict[str, PositionSave]
    walls: list[WallSave]


class CombatStateSave(SaveModel):
    location_id: str
    turn_order: list[str]
    round_number: int
    rounds_without_attack: int
    resume_turn_index: int | None = None
    battle_map: BattleMapSave
    sides: dict[int, set[str]] = Field(default_factory=dict)
    entity_to_side: dict[str, int] = Field(default_factory=dict)


class MaterializedSquadSave(SaveModel):
    creature_ids: list[str]
    original_strength: int
    spawn_count: int


class MaterializedLairSave(SaveModel):
    creature_ids: list[str]
    core_creature_id: str | None = None
    minion_templates: list[str]


class MaterializationSave(SaveModel):
    """Roster trackers of materialized squads/lairs; older saves load with empty trackers."""

    spawn_counter: int = 0
    squads: dict[str, MaterializedSquadSave] = Field(default_factory=dict)
    lairs: dict[str, MaterializedLairSave] = Field(default_factory=dict)
    withdrawn_survivors: list[str] = Field(default_factory=list)


class EntitiesState(SaveModel):
    entities: dict[str, EntitySave]
    combats: dict[str, CombatStateSave]
    rng_state: list[Any]
    materialization: MaterializationSave = Field(default_factory=MaterializationSave)
