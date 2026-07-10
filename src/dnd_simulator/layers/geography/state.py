"""Pydantic save-state models for GeographyLayer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict

from dnd_simulator.layers.geography.models import Direction, TerrainType, WeatherCondition


class ConnectionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_id: str
    direction: Direction


class RegionState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    latitude: float
    longitude: float
    elevation: float
    terrain: TerrainType
    water_proximity: float
    connections: list[ConnectionState]
    weather: WeatherCondition
    temperature: float


class GeographyState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    regions: dict[str, RegionState]
    rng_state: list[Any]
