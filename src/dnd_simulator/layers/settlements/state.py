"""Pydantic save-state models for SettlementsLayer."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from dnd_simulator.layers.settlements.models import SettlementType


class SettlementState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    region_id: str
    type: SettlementType
    population: int
    prosperity: float
    defenses: float


class SettlementsState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    settlements: dict[str, SettlementState]
