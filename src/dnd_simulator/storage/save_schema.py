"""Versioned Pydantic save envelope."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from dnd_simulator.layers.ecology.state import EcologyState
from dnd_simulator.layers.entities.save_models import EntitiesState
from dnd_simulator.layers.geography.state import GeographyState
from dnd_simulator.layers.politics.state import PoliticsState
from dnd_simulator.layers.settlements.state import SettlementsState

SCHEMA_VERSION = 1


class SaveMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str
    world_name: str
    lang: str
    default_player_faction: str


class WorldLayersSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    geography: GeographyState
    politics: PoliticsState
    settlements: SettlementsState
    ecology: EcologyState
    entities: EntitiesState


class WorldSave(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seed: int | None
    dice_rng_state: list[Any]
    time: dict[str, int]
    last_tick_times: dict[str, dict[str, int]]
    layers: WorldLayersSave

    def to_world_dict(self) -> dict[str, object]:
        data = self.model_dump(mode="json", by_alias=True)
        data.pop("dice_rng_state")
        return data


class SaveGame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[1]
    meta: SaveMeta
    world: WorldSave
