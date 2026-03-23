"""Load authored game content from YAML files.

Supports two formats:
- Legacy: single YAML file with all sections (regions, nations, npcs, player)
- Directory: folder with separate files (world.yaml, regions.yaml, nations.yaml, npcs.yaml, player.yaml)
"""

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


def resolve_text(value: object, lang: str = "en") -> str:
    """Resolve a localizable text field.

    If value is a plain string, return it as-is (backward compat).
    If value is a dict (e.g. {en: "Sword Vale", ru: "Долина Мечей"}),
    pick *lang* with fallback to 'en', then first available.
    """
    if isinstance(value, dict):
        return str(value.get(lang) or value.get("en") or next(iter(value.values()), ""))
    return str(value)


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


def load_world(path: Path, lang: str = "en") -> list[Region]:
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
                name=resolve_text(rdata["name"], lang),
                latitude=float(rdata["latitude"]),
                longitude=float(rdata["longitude"]),
                elevation=float(rdata["elevation"]),
                terrain=TerrainType(rdata["terrain"]),
                water_proximity=float(rdata.get("water_proximity", 0.0)),
                connections=connections,
            )
        )

    return regions


def load_locations(path: Path, regions: list[Region], lang: str = "en") -> list[Location]:
    """Load locations from a world YAML file or directory.

    Every world must define at least one location explicitly.
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

    if not locations_data:
        raise RuntimeError(f"No locations defined in world at {path}. Add a 'locations:' section.")

    return _parse_locations(locations_data, lang)


def _parse_locations(data: dict[str, Any], lang: str = "en") -> list[Location]:
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
                name=resolve_text(ldata["name"], lang),
                region_id=str(ldata["region"]),
                settlement_id=str(ldata.get("settlement", "")),
                edges=edges,
                description=resolve_text(ldata.get("description", ""), lang),
            )
        )
    return locations


def load_nations(path: Path, lang: str = "en") -> list[Nation]:
    """Load nations from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    nations_data = _load_section(path, is_dir, "nations")

    nations: list[Nation] = []
    for nation_id, ndata in nations_data.items():
        leader = None
        leader_data = ndata.get("leader")
        if leader_data:
            leader = Leader(
                name=resolve_text(leader_data["name"], lang),
                age=int(leader_data["age"]),
                trait=LeaderTrait(leader_data["trait"]),
            )

        nations.append(
            Nation(
                id=str(nation_id),
                name=resolve_text(ndata["name"], lang),
                regions=[str(r) for r in ndata.get("regions", [])],
                wealth=float(ndata.get("wealth", 50.0)),
                military=float(ndata.get("military", 50.0)),
                stability=float(ndata.get("stability", 70.0)),
                leader=leader,
            )
        )

    return nations


def load_settlements(path: Path, lang: str = "en") -> list[Settlement]:
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
                    name=resolve_text(sdata["name"], lang),
                    region_id=str(region_id),
                    type=SettlementType(sdata["type"]),
                    population=int(sdata.get("population", 100)),
                    prosperity=float(sdata.get("prosperity", 50.0)),
                    defenses=float(sdata.get("defenses", 30.0)),
                )
            )

    return settlements


def load_npcs(path: Path, lang: str = "en", known_locations: set[str] | None = None) -> list[Npc]:
    """Load NPCs from a world YAML file or directory."""
    is_dir, path = _resolve_source(path)
    npcs_data = _load_section(path, is_dir, "npcs")

    npcs: list[Npc] = []
    for npc_id, ndata in npcs_data.items():
        npcs.append(parse_npc(str(npc_id), ndata, lang=lang, known_locations=known_locations))

    return npcs


def parse_npc(npc_id: str, ndata: dict[str, Any], lang: str = "en", known_locations: set[str] | None = None) -> Npc:
    """Parse a single NPC from YAML data."""
    role = str(ndata.get("role", ""))
    settlement_id = str(ndata.get("settlement_id", ""))

    # Resolve schedule: role-based template with settlement prefix
    schedule = resolve_schedule(role, settlement_id, known_locations=known_locations)

    race = Race(ndata["race"]) if "race" in ndata else Race.HUMAN
    char_class = CharClass(ndata["class"]) if "class" in ndata else CharClass.COMMONER

    attacks = parse_attacks(ndata.get("attacks") or [])
    max_hp = int(ndata.get("hp", 4))
    ai_type = str(ndata.get("ai", "rule_based"))

    # Location: start_location is required (or legacy region_id fallback)
    location_id = str(ndata.get("start_location", "") or ndata.get("region_id", ""))
    if known_locations is not None and location_id and location_id not in known_locations:
        raise RuntimeError(
            f"NPC '{npc_id}' has start_location '{location_id}' which is not a known location. "
            f"Known: {sorted(known_locations)}"
        )

    # Parse initial memory from YAML (optional)
    memory_data = ndata.get("memory")
    memory = NpcMemory.from_dict(memory_data) if isinstance(memory_data, dict) else NpcMemory()

    npc = Npc(
        id=npc_id,
        name=resolve_text(ndata["name"], lang),
        location_id=location_id,
        race=race,
        char_class=char_class,
        role=role,
        personality=resolve_text(ndata.get("personality", ""), lang),
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
    # Brain is assigned by BrainFactory in GameService, not here.
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
    """Parse player character from YAML data dict.

    If ``pdata`` does not contain an ``id`` field a unique one is generated
    (``player_<hex8>``).  Callers may supply an explicit ``id`` to preserve
    identity across save/load cycles.
    """
    import uuid

    max_hp = int(pdata.get("hp", 10))
    attacks = parse_attacks(pdata.get("attacks") or [])

    # Support both start_location and legacy start_region
    location_id = str(pdata.get("start_location", pdata.get("start_region", pdata.get("location_id", ""))))

    player_id = str(pdata.get("id", "")) or f"player_{uuid.uuid4().hex[:8]}"

    return PlayerCharacter(
        id=player_id,
        name=str(pdata.get("name", "Adventurer")),
        location_id=location_id,
        race=Race(pdata["race"]) if "race" in pdata else Race.HUMAN,
        char_class=CharClass(pdata["class"]) if "class" in pdata else CharClass.FIGHTER,
        level=int(pdata.get("level", 1)),
        alignment=Alignment(pdata["alignment"]) if "alignment" in pdata else Alignment.TRUE_NEUTRAL,
        appearance=str(pdata.get("appearance", "")),
        ability_scores=parse_ability_scores(pdata),
        max_hp=max_hp,
        current_hp=int(pdata.get("current_hp", max_hp)),
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


def load_world_meta(path: Path, lang: str = "en") -> dict[str, str]:
    """Load world metadata (name, description) from directory format."""
    is_dir, path = _resolve_source(path)
    if is_dir:
        meta = _read_yaml(path / "world.yaml")
        return {
            "name": resolve_text(meta.get("name", path.name), lang),
            "description": resolve_text(meta.get("description", ""), lang),
        }
    data = _read_yaml(path)
    return {
        "name": resolve_text(data.get("name", path.stem), lang),
        "description": resolve_text(data.get("description", ""), lang),
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
