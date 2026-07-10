"""Pydantic save-state models for PoliticsLayer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from dnd_simulator.layers.politics.models import DiplomaticStatus, FactionRelation, LeaderTrait


class LeaderState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    age: int
    trait: LeaderTrait


class NationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    regions: list[str]
    wealth: float
    military: float
    stability: float
    leader: LeaderState | None


class DiplomaticRelationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: str
    b: str
    status: DiplomaticStatus


class WarDurationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: str
    b: str
    months: int


class FactionRelationState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    a: str
    b: str
    relation: FactionRelation


class PoliticsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    nations: dict[str, NationState]
    relations: list[DiplomaticRelationState]
    war_durations: list[WarDurationState]
    faction_relations: list[FactionRelationState]
    faction_names: dict[str, str]
    rng_state: list[Any]
