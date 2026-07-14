"""Pydantic save-state models for EcologyLayer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from dnd_simulator.core.lair import LairState


class SquadRuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    current_location_id: str
    strength: int


class LairRuntimeState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: LairState
    alive_members: list[str] | None
    core_alive: bool
    last_respawn_time: int
    death_writebacks: set[str] = Field(default_factory=set)


class EcologyState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    squads: dict[str, SquadRuntimeState]
    lairs: dict[str, LairRuntimeState]
    last_move_time: dict[str, int]
    route_index: dict[str, int]
    route_direction: dict[str, int]
    rng_state: list[Any]
