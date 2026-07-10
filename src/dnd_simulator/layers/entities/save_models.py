"""Pydantic save-state models for EntitiesLayer."""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class EntitySaveBase(BaseModel):
    model_config = ConfigDict(extra="allow")

    id: str
    name: str
    location_id: str
    active: bool


class CreatureFields(EntitySaveBase):
    max_hp: int
    current_hp: int
    ac: int
    speed: int
    ability_scores: dict[str, int]
    attacks: list[dict[str, Any]] = Field(default_factory=list)


class CreatureSave(CreatureFields):
    entity_type: Literal["creature"]


class PlayerSave(CreatureFields):
    entity_type: Literal["player"]
    race: str
    class_: str = Field(alias="class")
    level: int
    alignment: str
    hp: int
    gold: int
    start_location: str
    experience: int
    level_up_available: bool


class NpcSave(CreatureFields):
    entity_type: Literal["npc"]
    role: str
    personality: str
    settlement_id: str
    memory: dict[str, Any]
    ai_type: str
    hp: int
    ai: str
    start_location: str
    race: str
    class_: str = Field(alias="class")


class ContainerSave(EntitySaveBase):
    entity_type: Literal["container"]
    is_open: bool
    gold: int
    inventory: list[dict[str, Any]] = Field(default_factory=list)


EntitySave = Annotated[PlayerSave | NpcSave | CreatureSave | ContainerSave, Field(discriminator="entity_type")]
EntitySaveAdapter: TypeAdapter[EntitySave] = TypeAdapter(EntitySave)


class PositionSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: int
    y: int


class WallSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x1: int
    y1: int
    x2: int
    y2: int


class BattleMapSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    width: int
    height: int
    positions: dict[str, PositionSave]
    walls: list[WallSave]


class CombatStateSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    location_id: str
    turn_order: list[str]
    round_number: int
    rounds_without_attack: int
    battle_map: BattleMapSave


class EntitiesState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: dict[str, EntitySave]
    combats: dict[str, CombatStateSave]
    rng_state: list[Any]
