"""Load authored game content from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Alignment,
    Attack,
    CharClass,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import DEFAULT_SCHEDULES, Npc
from dnd_simulator.layers.geography.models import (
    Connection,
    Direction,
    Region,
    TerrainType,
)
from dnd_simulator.layers.politics.models import Leader, LeaderTrait, Nation
from dnd_simulator.layers.settlements.models import Settlement, SettlementType


def _parse_attacks(attacks_data: list[dict[str, Any]]) -> tuple[Attack, ...]:
    """Parse attack definitions from YAML."""
    attacks: list[Attack] = []
    for adata in attacks_data:
        damage = tuple(
            DamageComponent(dice=str(d["dice"]), type=DamageType(d["type"])) for d in adata.get("damage", [])
        )
        attacks.append(
            Attack(
                name=str(adata["name"]),
                ability=Ability(adata.get("ability", "str")),
                damage=damage,
                reach=int(adata.get("reach", 5)),
            )
        )
    return tuple(attacks)


def load_world(path: Path) -> list[Region]:
    """Load regions from a world YAML file."""
    with path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    regions_data: dict[str, Any] = data["regions"]
    regions: list[Region] = []

    for region_id, rdata in regions_data.items():
        connections = [
            Connection(
                target_id=str(c["target"]),
                direction=Direction(c["direction"]),
            )
            for c in rdata.get("connections", [])
        ]

        regions.append(
            Region(
                id=str(region_id),
                name=str(rdata["name"]),
                latitude=float(rdata["latitude"]),
                longitude=float(rdata["longitude"]),
                elevation=float(rdata["elevation"]),
                terrain=TerrainType(rdata["terrain"]),
                water_proximity=float(rdata.get("water_proximity", 0.0)),
                connections=connections,
            )
        )

    return regions


def load_nations(path: Path) -> list[Nation]:
    """Load nations from a world YAML file."""
    with path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    nations_data: dict[str, Any] = data.get("nations", {})
    nations: list[Nation] = []

    for nation_id, ndata in nations_data.items():
        leader = None
        leader_data = ndata.get("leader")
        if leader_data:
            leader = Leader(
                name=str(leader_data["name"]),
                age=int(leader_data["age"]),
                trait=LeaderTrait(leader_data["trait"]),
            )

        nations.append(
            Nation(
                id=str(nation_id),
                name=str(ndata["name"]),
                regions=[str(r) for r in ndata.get("regions", [])],
                wealth=float(ndata.get("wealth", 50.0)),
                military=float(ndata.get("military", 50.0)),
                stability=float(ndata.get("stability", 70.0)),
                leader=leader,
            )
        )

    return nations


def load_settlements(path: Path) -> list[Settlement]:
    """Load settlements from a world YAML file."""
    with path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    regions_data: dict[str, Any] = data.get("regions", {})
    settlements: list[Settlement] = []

    for region_id, rdata in regions_data.items():
        for sdata in rdata.get("settlements", []):
            settlements.append(
                Settlement(
                    id=str(sdata["id"]),
                    name=str(sdata["name"]),
                    region_id=str(region_id),
                    type=SettlementType(sdata["type"]),
                    population=int(sdata.get("population", 100)),
                    prosperity=float(sdata.get("prosperity", 50.0)),
                    defenses=float(sdata.get("defenses", 30.0)),
                )
            )

    return settlements


def load_npcs(path: Path) -> list[Npc]:
    """Load NPCs from a world YAML file."""
    with path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    npcs_data: dict[str, Any] = data.get("npcs", {})
    npcs: list[Npc] = []

    for npc_id, ndata in npcs_data.items():
        role = str(ndata.get("role", ""))
        schedule = list(DEFAULT_SCHEDULES.get(role, []))

        race = Race(ndata["race"]) if "race" in ndata else Race.HUMAN
        char_class = CharClass(ndata["class"]) if "class" in ndata else CharClass.COMMONER

        attacks = _parse_attacks(ndata.get("attacks", []))
        max_hp = int(ndata.get("hp", 4))

        npcs.append(
            Npc(
                id=str(npc_id),
                name=str(ndata["name"]),
                region_id=str(ndata["region_id"]),
                race=race,
                char_class=char_class,
                role=role,
                personality=str(ndata.get("personality", "")),
                settlement_id=str(ndata.get("settlement_id", "")),
                schedule=schedule,
                attacks=attacks,
                max_hp=max_hp,
                current_hp=max_hp,
                ac=int(ndata.get("ac", 10)),
            )
        )

    return npcs


def load_player(path: Path) -> PlayerCharacter:
    """Load player character from a world YAML file."""
    with path.open() as f:
        data: dict[str, Any] = yaml.safe_load(f)

    pdata: dict[str, Any] = data.get("player", {})

    ability_scores = AbilityScores()
    if "ability_scores" in pdata:
        ability_scores = AbilityScores.from_dict(pdata["ability_scores"])

    max_hp = int(pdata.get("hp", 10))
    attacks = _parse_attacks(pdata.get("attacks", []))

    return PlayerCharacter(
        id="player",
        name=str(pdata.get("name", "Adventurer")),
        region_id=str(pdata.get("start_region", "")),
        race=Race(pdata["race"]) if "race" in pdata else Race.HUMAN,
        char_class=CharClass(pdata["class"]) if "class" in pdata else CharClass.FIGHTER,
        level=int(pdata.get("level", 1)),
        alignment=Alignment(pdata["alignment"]) if "alignment" in pdata else Alignment.TRUE_NEUTRAL,
        appearance=str(pdata.get("appearance", "")),
        ability_scores=ability_scores,
        max_hp=max_hp,
        current_hp=max_hp,
        gold=int(pdata.get("gold", 0)),
        attacks=attacks,
    )


def extract_region_adjacency(regions: list[Region]) -> dict[str, list[str]]:
    """Build adjacency map from region connections."""
    adjacency: dict[str, list[str]] = {}
    for region in regions:
        adjacency[region.id] = [c.target_id for c in region.connections]
    return adjacency


def extract_region_terrains(regions: list[Region]) -> dict[str, str]:
    """Build terrain map from regions."""
    return {region.id: region.terrain.value for region in regions}
