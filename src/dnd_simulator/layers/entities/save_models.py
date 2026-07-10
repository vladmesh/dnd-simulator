"""Pydantic save-state models for EntitiesLayer."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

from dnd_simulator.core.action import ActionType
from dnd_simulator.core.brain import BrainType
from dnd_simulator.core.character import Ability, Alignment, CharClass, DamageType, NpcRole, Race
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.intent import IntentType
from dnd_simulator.core.items import ArmorCategory, EquipmentSlot, ItemType, WeaponCategory
from dnd_simulator.core.models import EntityKind
from dnd_simulator.core.modifiers import ModifierOp, StatType
from dnd_simulator.core.resource import RestType


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


class NpcMemorySave(SaveModel):
    tags: list[str] = Field(default_factory=list)
    recent: str = ""
    inner_state: str = ""
    current_conversation: str = ""


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
    kind: IntentType
    started_at_seconds: int
    wake_at_seconds: int


class EntitySaveBase(SaveModel):
    id: str
    name: str
    location_id: str
    active: bool
    temporary: bool = False
    faction_id: str = ""


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
    is_anchor: bool = False
    current_intent: TimedIntentSave | None = None
    combat_position: tuple[int, int] | None = None


class CreatureSave(CreatureFields):
    entity_type: Literal[EntityKind.CREATURE]


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
    role: NpcRole
    personality: str
    description: str = ""
    settlement_id: str
    location_override: str | None = None
    memory: NpcMemorySave
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
    battle_map: BattleMapSave
    sides: dict[int, set[str]] = Field(default_factory=dict)
    entity_to_side: dict[str, int] = Field(default_factory=dict)


class EntitiesState(SaveModel):
    entities: dict[str, EntitySave]
    combats: dict[str, CombatStateSave]
    rng_state: list[Any]
