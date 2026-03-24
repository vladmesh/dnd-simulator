from __future__ import annotations

import contextlib
import uuid
from pathlib import Path
from typing import Any

from dnd_simulator.content_loader import (
    extract_region_adjacency,
    extract_region_terrains,
    load_locations,
    load_nations,
    load_npcs,
    load_settlements,
    load_world,
    load_world_meta,
)
from dnd_simulator.core.character import Entity
from dnd_simulator.core.location import LocationGraph
from dnd_simulator.core.models import GameDateTime, TimeDelta
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.i18n import _
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.rules.modifiers import effective_ac
from dnd_simulator.storage.store import SaveStore

from .brain_factory import BrainFactory
from .commands_creatures import CreatureCommands
from .commands_politics import PoliticsCommands
from .commands_save import SaveCommands
from .commands_time import TimeCommands
from .session import GameSession

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"


class GameService(
    CreatureCommands,
    PoliticsCommands,
    SaveCommands,
    TimeCommands,
):
    """Session management, world templates, hot controls. No turn execution."""

    def __init__(
        self,
        store: SaveStore,
        content_dir: Path = DEFAULT_CONTENT_DIR,
        llm: LlmClient | None = None,
    ) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._store = store
        self._content_dir = content_dir
        self._llm = llm
        self._brain_factory = BrainFactory(llm=llm)

    def start_game(self, world_name: str = "sword_vale", lang: str = "en") -> GameSession:
        """Create a new game session with a world loaded from content.

        Accepts either a legacy filename (arena.yaml) or a directory name (sword_vale).
        """
        session_id = uuid.uuid4().hex[:8]

        world_path = self._content_dir / "worlds" / world_name
        regions = load_world(world_path, lang=lang)
        nations = load_nations(world_path, lang=lang)
        settlements = load_settlements(world_path, lang=lang)
        locations = load_locations(world_path, regions, lang=lang)
        location_graph = LocationGraph(locations)
        npcs = load_npcs(world_path, lang=lang, known_locations=set(location_graph.all_ids()))
        region_terrains = extract_region_terrains(regions)

        # Players are created via API (create_player), not from templates
        entities: list[Entity] = [*npcs]

        geography = GeographyLayer(regions=regions, location_graph=location_graph)
        settlements_layer = SettlementsLayer(settlements=settlements, region_terrains=region_terrains)
        politics = PoliticsLayer(
            nations=nations,
            region_terrains=region_terrains,
            region_adjacency=extract_region_adjacency(regions),
            region_income_fn=settlements_layer.get_region_income,
        )
        summarizer = None
        if self._llm:
            from dnd_simulator.llm.summarizer import MemorySummarizer

            summarizer = MemorySummarizer(self._llm)
        entities_layer = EntitiesLayer(entities=entities, summarizer=summarizer)

        # Assign brains via factory (content_loader only parses data, not brains)
        from dnd_simulator.layers.entities.models import Npc

        for entity in entities:
            if isinstance(entity, Npc):
                entity.brain = self._brain_factory.create(entity.ai_type)

        world = World(
            layers=[geography, politics, settlements_layer, entities_layer],
            time=GameDateTime(year=1490, month=6, day=1, hour=10),
            location_graph=location_graph,
        )

        # Initial tick to set weather/temperature
        world.advance_time(TimeDelta(seconds=0))

        session = GameSession(
            session_id=session_id,
            world=world,
            lang=lang,
            world_name=world_name,
        )
        self._sessions[session_id] = session
        return session

    def list_sessions(self) -> list[dict[str, str]]:
        """List all active sessions (in-memory + saved on disk)."""
        result: dict[str, dict[str, str]] = {}

        # In-memory sessions
        for sid, s in self._sessions.items():
            players = s.get_players()
            player_name = players[0].name if players else ""
            result[sid] = {"session_id": sid, "player_name": player_name, "world_name": s.world_name}

        # Saved sessions on disk (not yet loaded) — scan all world subdirs
        from dnd_simulator.storage.store import JsonFileStore

        if isinstance(self._store, JsonFileStore):
            for world_name in self._store.list_worlds():
                for save_name in self._store.list_saves(world=world_name):
                    if save_name.startswith("session_"):
                        sid = save_name[len("session_") :]
                        if sid not in result:
                            result[sid] = {"session_id": sid, "player_name": "(saved)", "world_name": world_name}

        return list(result.values())

    def get_session(self, session_id: str) -> GameSession:
        """Get session info."""
        return self._get_session(session_id)

    def delete_session(self, session_id: str) -> None:
        """Stop and remove a session."""
        self._get_session(session_id)
        del self._sessions[session_id]

    def list_worlds(self, lang: str = "en") -> list[dict[str, str]]:
        """List available world templates."""
        worlds_dir = self._content_dir / "worlds"
        result: list[dict[str, str]] = []
        if not worlds_dir.exists():
            return result
        for entry in sorted(worlds_dir.iterdir()):
            is_world_dir = entry.is_dir() and (entry / "world.yaml").exists()
            is_world_file = entry.suffix in (".yaml", ".yml") and entry.is_file()
            if is_world_dir or is_world_file:
                meta = load_world_meta(entry, lang=lang)
                result.append({"id": entry.name, **meta})
        return result

    def get_world_template(self, world_id: str) -> dict[str, Any]:
        """Read a world template from disk (YAML data, not a live session)."""
        from dnd_simulator.content_loader import load_battle_maps

        world_path = self._content_dir / "worlds" / world_id
        if not world_path.exists():
            raise FileNotFoundError(f"World '{world_id}' not found")

        meta = load_world_meta(world_path)
        regions = load_world(world_path)
        nations = load_nations(world_path)
        settlements = load_settlements(world_path)
        locations = load_locations(world_path, regions)
        npcs_list = load_npcs(world_path, known_locations={loc.id for loc in locations})
        battle_maps = load_battle_maps(world_path)

        return {
            "id": world_id,
            "name": meta["name"],
            "description": meta.get("description", ""),
            "regions": [
                {
                    "id": r.id,
                    "name": r.name,
                    "terrain": r.terrain.value,
                    "latitude": r.latitude,
                    "longitude": r.longitude,
                    "elevation": r.elevation,
                    "water_proximity": r.water_proximity,
                    "connections": [{"target": c.target_id, "direction": c.direction.value} for c in r.connections],
                    "has_battle_map": r.id in battle_maps,
                }
                for r in regions
            ],
            "settlements": [
                {
                    "id": s.id,
                    "name": s.name,
                    "region_id": s.region_id,
                    "type": s.type.value,
                    "population": s.population,
                    "prosperity": s.prosperity,
                    "defenses": s.defenses,
                }
                for s in settlements
            ],
            "locations": [
                {
                    "id": loc.id,
                    "name": loc.name,
                    "region_id": loc.region_id,
                    "settlement_id": loc.settlement_id,
                    "description": loc.description,
                    "neighbors": [{"target": e.target_id, "distance": e.distance_m} for e in loc.edges],
                }
                for loc in locations
            ],
            "nations": [
                {
                    "id": n.id,
                    "name": n.name,
                    "regions": n.regions,
                    "wealth": n.wealth,
                    "military": n.military,
                    "stability": n.stability,
                    "leader": {"name": n.leader.name, "age": n.leader.age, "trait": n.leader.trait.value}
                    if n.leader
                    else None,
                }
                for n in nations
            ],
            "npcs": [
                {
                    "id": npc.id,
                    "name": npc.name,
                    "role": npc.role,
                    "location_id": npc.location_id,
                    "settlement_id": npc.settlement_id,
                    "personality": npc.personality,
                    "race": npc.race.value,
                    "char_class": npc.char_class.value,
                    "hp": npc.max_hp,
                    "ac": effective_ac(npc),
                    "ai_type": npc.ai_type,
                }
                for npc in npcs_list
            ],
        }

    def create_world(self, data: dict[str, Any]) -> dict[str, str]:
        """Create a new world template from structured data.

        Saves YAML files to content/worlds/{id}/ and returns world metadata.
        """
        from dnd_simulator.content_saver import save_world

        save_world(self._content_dir, str(data["id"]), data)
        return {"id": str(data["id"]), "name": str(data.get("name", data["id"]))}

    def update_world(self, world_id: str, data: dict[str, Any]) -> dict[str, str]:
        """Update an existing world template on disk (full replace).

        Overwrites all YAML files in content/worlds/{world_id}/.
        """
        from dnd_simulator.content_saver import save_world

        world_path = self._content_dir / "worlds" / world_id
        if not world_path.exists():
            raise FileNotFoundError(f"World '{world_id}' not found")

        data["id"] = world_id
        save_world(self._content_dir, world_id, data, overwrite=True)
        return {"id": world_id, "name": str(data.get("name", world_id))}

    # -- Layer accessors --

    def _get_entities_layer(self, session: GameSession) -> EntitiesLayer:
        for layer in session.world.layers:
            if isinstance(layer, EntitiesLayer):
                return layer
        raise RuntimeError("EntitiesLayer not found")

    def _get_politics_layer(self, session: GameSession) -> PoliticsLayer:
        for layer in session.world.layers:
            if isinstance(layer, PoliticsLayer):
                return layer
        raise RuntimeError("PoliticsLayer not found")

    def _get_settlements_layer(self, session: GameSession) -> SettlementsLayer:
        for layer in session.world.layers:
            if isinstance(layer, SettlementsLayer):
                return layer
        raise RuntimeError("SettlementsLayer not found")

    # -- Player --

    def create_player(self, session_id: str, player_data: dict[str, Any]) -> PlayerCharacter:
        """Create a new player character in a session.

        Returns the created PlayerCharacter (with a unique id like ``player_<hex>``).
        """
        from dnd_simulator.content_loader import parse_player

        session = self._get_session(session_id)

        player = parse_player(player_data)

        # Default to first location if not specified
        if not player.location_id:
            graph = session.world.location_graph
            ids = graph.all_ids()
            if ids:
                player.location_id = ids[0]

        self._get_entities_layer(session).add_entity(player)
        with contextlib.suppress(Exception):
            self.autosave_session(session_id)
        return player

    def _require_player(self, session: GameSession, player_id: str | None = None) -> PlayerCharacter:
        player = session.get_player(player_id)
        if player is None:
            raise ValueError(_("No player in this session"))
        return player

    def _get_session(self, session_id: str) -> GameSession:
        if session_id not in self._sessions:
            # Try to restore from autosave on disk
            self._try_restore_session(session_id)
        if session_id not in self._sessions:
            raise ValueError(f"Session '{session_id}' not found")
        return self._sessions[session_id]

    def _try_restore_session(self, session_id: str) -> None:
        """Attempt to restore a session from its autosave file."""
        save_name = f"session_{session_id}"

        # Search across all world subdirectories
        data: dict[str, object] | None = None
        from dnd_simulator.storage.store import JsonFileStore

        if isinstance(self._store, JsonFileStore):
            for world_name in self._store.list_worlds():
                try:
                    data = self._store.load(save_name, world=world_name)
                    break
                except KeyError:
                    continue

        # Fallback: try root directory (backward compat)
        if data is None:
            try:
                data = self._store.load(save_name)
            except KeyError:
                return

        meta = data.get("meta", {})
        assert isinstance(meta, dict)
        world_name = str(meta.get("world_name", ""))
        lang = str(meta.get("lang", "en"))

        if not world_name:
            return

        # Recreate session from the same world template, then load saved state
        try:
            session = self.start_game(world_name, lang=lang)
        except Exception:
            return

        # Reassign to the original session_id
        del self._sessions[session.session_id]
        session.session_id = session_id

        # Load saved world state (player state is restored as part of entities layer)
        if "world" in data:
            world_data = data["world"]
            assert isinstance(world_data, dict)
            session.world.load(world_data)

            # Backward compat: old saves have separate "player" block
            player_data = data.get("player", {})
            assert isinstance(player_data, dict)
            if player_data:
                player = session.get_player()
                if player:
                    player.load_save_data(player_data)
                else:
                    # Player was created after session start — recreate
                    from dnd_simulator.content_loader import parse_player

                    new_player = parse_player(player_data)
                    self._get_entities_layer(session).add_entity(new_player)

        self._sessions[session_id] = session
