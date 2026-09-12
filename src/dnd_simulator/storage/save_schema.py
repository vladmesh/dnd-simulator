"""Versioned Pydantic save envelope."""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

import structlog
from pydantic import BaseModel, ConfigDict

from dnd_simulator.layers.ecology.state import EcologyState
from dnd_simulator.layers.entities.save_models import EntitiesState
from dnd_simulator.layers.geography.state import GeographyState
from dnd_simulator.layers.politics.state import PoliticsState
from dnd_simulator.layers.settlements.state import SettlementsState

SCHEMA_VERSION = 2

logger = structlog.get_logger(domain="save")


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

    schema_version: Literal[2]
    meta: SaveMeta
    world: WorldSave


_LEGACY_RELATIONS = {"loves", "hates", "trusts", "fears", "loyal_to"}
_LEGACY_MOODS = {"angry", "tired", "happy", "scared", "grieving", "suspicious", "alerted"}
_LEGACY_TAGS_KEY = "ta" + "gs"
# First matching mood in this order wins.  It favors immediate danger over the
# more ambient emotions that could coexist in a flat legacy list.
_LEGACY_MOOD_PRIORITY = ("scared", "alerted", "angry", "grieving", "suspicious", "tired", "happy")
_LEGACY_SITUATIONAL_MOODS = {"in_mourning": "grieving", "fleeing": "scared"}


def migrate_v1_save(data: object) -> object:
    """Convert released v1 NPC memory into the v2 inner-self save shape."""
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return data
    migrated = deepcopy(data)
    try:
        entities = migrated["world"]["layers"]["entities"]["entities"]
    except (KeyError, TypeError):
        return migrated
    if not isinstance(entities, dict):
        return migrated
    for entity_id, entity in entities.items():
        if not isinstance(entity, dict) or entity.get("entity_type") != "npc":
            continue
        legacy_memory = entity.pop("memory", {})
        if not isinstance(legacy_memory, dict):
            legacy_memory = {}
        raw_entries = legacy_memory.get(_LEGACY_TAGS_KEY, [])
        entries = raw_entries if isinstance(raw_entries, list) else []
        relations: list[dict[str, object]] = []
        moods: set[str] = set()
        for raw_tag in entries:
            if not isinstance(raw_tag, str):
                logger.warning("legacy_inner_self_tag_dropped", entity_id=entity_id, tag=raw_tag)
                continue
            if ":" in raw_tag:
                relation_type, target_id = raw_tag.split(":", 1)
                if relation_type in _LEGACY_RELATIONS and target_id:
                    relations.append({"type": relation_type, "target_id": target_id})
                    continue
            if raw_tag in _LEGACY_MOODS:
                moods.add(raw_tag)
                continue
            if raw_tag in _LEGACY_SITUATIONAL_MOODS:
                moods.add(_LEGACY_SITUATIONAL_MOODS[raw_tag])
                continue
            logger.warning("legacy_inner_self_tag_dropped", entity_id=entity_id, tag=raw_tag)
        mood = next((candidate for candidate in _LEGACY_MOOD_PRIORITY if candidate in moods), "neutral")
        journal_parts = [str(legacy_memory[key]) for key in ("recent", "inner_state") if legacy_memory.get(key)]
        entity["inner_self"] = {
            "relations": relations,
            "mood": mood,
            "goals": [],
            "alignment": {"law_chaos": 0, "good_evil": 0},
            "journal": "\n\n".join(journal_parts),
            "thoughts": [],
            "current_conversation": str(legacy_memory.get("current_conversation", "")),
        }
    migrated["schema_version"] = SCHEMA_VERSION
    return migrated
