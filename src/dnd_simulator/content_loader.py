"""Load authored game content from YAML files.

Supports two formats:
- Legacy: single YAML file with all sections (regions, nations, npcs, player)
- Directory: folder with separate files (world.yaml, regions.yaml, nations.yaml, npcs.yaml, player.yaml)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from dnd_simulator.core.brain import RuleBrain
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
from dnd_simulator.core.combat import BattleMap, Wall
from dnd_simulator.core.location import Location, LocationEdge
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc, NpcMemory, resolve_schedule
from dnd_simulator.layers.geography.models import (
    Connection,
    Direction,
    Region,
    TerrainType,
)
from dnd_simulator.layers.politics.models import Leader, LeaderTrait, Nation
from dnd_simulator.layers.settlements.models import Settlement, SettlementType
from dnd_simulator.rules.geography import calculate_distance_km


def _read_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file, returning empty dict if file doesn't exist."""
    if not path.exists():
        return {}
    with path.open() as f:
        return yaml.safe_load(f) or {}


def _resolve_source(path: Path) -> tuple[bool, Path]:
    """Determine if path is a directory or legacy single file.

    Returns (is_directory, resolved_path).
    """
    if path.is_dir():
        return True, path
    return False, path


def _load_section(path: Path, is_dir: bool, section: str) -> dict[str, Any]:
    """Load a section from either directory format or legacy single file."""
    if is_dir:
        return _read_yaml(path / f"{section}.yaml")
    data = _read_yaml(path)
    section_data = data.get(section, {})
    assert isinstance(section_data, dict)
    return section_data


# -- Parsing helpers --


def parse_attacks(attacks_data: list[dict[str, Any]]) -> tuple[Attack, ...]:
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


def parse_ability_scores(data: dict[str, Any], key: str = "ability_scores") -> AbilityScores:
    """Parse ability scores from YAML data."""
    scores = data.get(key)
    if scores:
        return AbilityScores.from_dict(scores)
    return AbilityScores()


# -- Public loaders --


def load_world(path: Path) -> list[Region]:
    """Load regions from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    regions_data = _load_section(path, is_dir, "regions")

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


def load_locations(path: Path, regions: list[Region]) -> list[Location]:
    """Load locations from a world YAML file or directory.

    If locations.yaml exists, load from it.
    Otherwise, auto-generate one location per region from region data
    (backward compat for worlds without explicit locations).
    """
    is_dir, resolved = _resolve_source(path)

    locations_data: dict[str, Any] = {}
    if is_dir:
        loc_path = resolved / "locations.yaml"
        if loc_path.exists():
            locations_data = _read_yaml(loc_path)
    else:
        data = _read_yaml(resolved)
        locations_data = data.get("locations", {})
        assert isinstance(locations_data, dict)

    if locations_data:
        return _parse_locations(locations_data)

    # Fallback: auto-generate from regions
    return _generate_locations_from_regions(regions)


def _parse_locations(data: dict[str, Any]) -> list[Location]:
    """Parse locations from YAML data."""
    locations: list[Location] = []
    for loc_id, ldata in data.items():
        edges = tuple(
            LocationEdge(
                target_id=str(n["target"]),
                distance_m=int(n["distance"]),
            )
            for n in ldata.get("neighbors", [])
        )
        locations.append(
            Location(
                id=str(loc_id),
                name=str(ldata["name"]),
                region_id=str(ldata["region"]),
                settlement_id=str(ldata.get("settlement", "")),
                edges=edges,
                description=str(ldata.get("description", "")),
            )
        )
    return locations


def _generate_locations_from_regions(regions: list[Region]) -> list[Location]:
    """Auto-generate one Location per Region for backward compat."""
    region_map = {r.id: r for r in regions}
    locations: list[Location] = []

    for region in regions:
        edges: list[LocationEdge] = []
        for conn in region.connections:
            target = region_map.get(conn.target_id)
            if target:
                dist_km = calculate_distance_km(region.latitude, region.longitude, target.latitude, target.longitude)
                edges.append(LocationEdge(target_id=conn.target_id, distance_m=int(dist_km * 1000)))

        locations.append(
            Location(
                id=region.id,
                name=region.name,
                region_id=region.id,
                edges=tuple(edges),
            )
        )

    return locations


def load_nations(path: Path) -> list[Nation]:
    """Load nations from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    nations_data = _load_section(path, is_dir, "nations")

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
    """Load settlements from a world YAML file or directory.

    In directory mode, settlements are nested under regions in regions.yaml.
    """
    is_dir, path = _resolve_source(path)
    regions_data = _load_section(path, is_dir, "regions")

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
    """Load NPCs from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    npcs_data = _load_section(path, is_dir, "npcs")

    npcs: list[Npc] = []
    for npc_id, ndata in npcs_data.items():
        npcs.append(parse_npc(str(npc_id), ndata))

    return npcs


def parse_npc(npc_id: str, ndata: dict[str, Any]) -> Npc:
    """Parse a single NPC from YAML data."""
    role = str(ndata.get("role", ""))
    settlement_id = str(ndata.get("settlement_id", ""))

    # Resolve schedule: role-based template with settlement prefix
    schedule = resolve_schedule(role, settlement_id)

    race = Race(ndata["race"]) if "race" in ndata else Race.HUMAN
    char_class = CharClass(ndata["class"]) if "class" in ndata else CharClass.COMMONER

    attacks = parse_attacks(ndata.get("attacks") or [])
    max_hp = int(ndata.get("hp", 4))
    ai_type = str(ndata.get("ai", "rule_based"))

    # Location: prefer start_location, fall back to settlement default, then region
    location_id = str(ndata.get("start_location", ""))
    if not location_id and settlement_id:
        # Default: NPC starts at their settlement's home location
        location_id = f"{settlement_id}_home"
    if not location_id:
        location_id = str(ndata.get("region_id", ""))

    # Parse initial memory from YAML (optional)
    memory_data = ndata.get("memory")
    memory = NpcMemory.from_dict(memory_data) if isinstance(memory_data, dict) else NpcMemory()

    npc = Npc(
        id=npc_id,
        name=str(ndata["name"]),
        location_id=location_id,
        race=race,
        char_class=char_class,
        role=role,
        personality=str(ndata.get("personality", "")),
        settlement_id=settlement_id,
        schedule=schedule,
        speed=int(ndata.get("speed", 30)),
        attacks=attacks,
        max_hp=max_hp,
        current_hp=max_hp,
        ac=int(ndata.get("ac", 10)),
        ability_scores=parse_ability_scores(ndata),
        ai_type=ai_type,
        memory=memory,
    )
    if ai_type == "rule_based":
        npc.brain = RuleBrain()
    return npc


def load_player(path: Path) -> PlayerCharacter:
    """Load player character from a world YAML file or directory.

    Raises FileNotFoundError if no player data exists (directory format without player.yaml).
    """
    is_dir, path = _resolve_source(path)
    if is_dir:
        player_path = path / "player.yaml"
        if not player_path.exists():
            raise FileNotFoundError(f"No player.yaml in {path}")
        pdata = _read_yaml(player_path)
    else:
        data = _read_yaml(path)
        if "player" not in data:
            raise KeyError("No 'player' section in world file")
        pdata = data["player"]
        assert isinstance(pdata, dict)

    return parse_player(pdata)


def parse_player(pdata: dict[str, Any]) -> PlayerCharacter:
    """Parse player character from YAML data dict."""
    max_hp = int(pdata.get("hp", 10))
    attacks = parse_attacks(pdata.get("attacks") or [])

    # Support both start_location and legacy start_region
    location_id = str(pdata.get("start_location", pdata.get("start_region", "")))

    return PlayerCharacter(
        id="player",
        name=str(pdata.get("name", "Adventurer")),
        location_id=location_id,
        race=Race(pdata["race"]) if "race" in pdata else Race.HUMAN,
        char_class=CharClass(pdata["class"]) if "class" in pdata else CharClass.FIGHTER,
        level=int(pdata.get("level", 1)),
        alignment=Alignment(pdata["alignment"]) if "alignment" in pdata else Alignment.TRUE_NEUTRAL,
        appearance=str(pdata.get("appearance", "")),
        ability_scores=parse_ability_scores(pdata),
        max_hp=max_hp,
        current_hp=max_hp,
        ac=int(pdata.get("ac", 10)),
        gold=int(pdata.get("gold", 0)),
        attacks=attacks,
    )


def load_battle_maps(path: Path) -> dict[str, BattleMap]:
    """Load per-region battle map configs (size + walls) from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    regions_data = _load_section(path, is_dir, "regions")

    result: dict[str, BattleMap] = {}
    for region_id, rdata in regions_data.items():
        bm_data = rdata.get("battle_map")
        if not bm_data:
            continue
        walls: list[Wall] = []
        for w in bm_data.get("walls", []):
            walls.append(Wall(x1=int(w[0]), y1=int(w[1]), x2=int(w[2]), y2=int(w[3])))
        result[str(region_id)] = BattleMap(
            width=int(bm_data.get("width", 60)),
            height=int(bm_data.get("height", 60)),
            walls=walls,
        )

    return result


def load_world_meta(path: Path) -> dict[str, str]:
    """Load world metadata (name, description) from directory format."""
    is_dir, path = _resolve_source(path)
    if is_dir:
        meta = _read_yaml(path / "world.yaml")
        return {
            "name": str(meta.get("name", path.name)),
            "description": str(meta.get("description", "")),
        }
    data = _read_yaml(path)
    return {
        "name": str(data.get("name", path.stem)),
        "description": str(data.get("description", "")),
    }


def extract_region_adjacency(regions: list[Region]) -> dict[str, list[str]]:
    """Build adjacency map from region connections."""
    adjacency: dict[str, list[str]] = {}
    for region in regions:
        adjacency[region.id] = [c.target_id for c in region.connections]
    return adjacency


def extract_region_terrains(regions: list[Region]) -> dict[str, str]:
    """Build terrain map from regions."""
    return {region.id: region.terrain.value for region in regions}
