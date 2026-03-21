from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from dnd_simulator.content_loader import (
    extract_region_adjacency,
    extract_region_terrains,
    load_locations,
    load_nations,
    load_npcs,
    load_player,
    load_settlements,
    load_world,
    load_world_meta,
)
from dnd_simulator.core.character import Entity
from dnd_simulator.core.location import LocationGraph
from dnd_simulator.core.models import GameDateTime, TimeDelta
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.storage.store import SaveStore

from .commands_combat import CombatCommands
from .commands_npc import NpcCommands
from .commands_politics import PoliticsCommands
from .commands_save import SaveCommands
from .commands_time import TimeCommands
from .commands_world import WorldCommands
from .session import GameSession, MasterResponse

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[3] / "content"


class GameService(
    CombatCommands,
    WorldCommands,
    NpcCommands,
    PoliticsCommands,
    SaveCommands,
    TimeCommands,
):
    """Main interface to the game. Transport-agnostic."""

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

    def start_game(self, world_name: str = "test_world.yaml", lang: str = "en") -> GameSession:
        """Create a new game session with a world loaded from content.

        Accepts either a legacy filename (test_world.yaml) or a directory name (sword_vale).
        """
        session_id = uuid.uuid4().hex[:8]

        world_path = self._content_dir / "worlds" / world_name
        regions = load_world(world_path)
        nations = load_nations(world_path)
        settlements = load_settlements(world_path)
        npcs = load_npcs(world_path)
        locations = load_locations(world_path, regions)
        location_graph = LocationGraph(locations)
        region_terrains = extract_region_terrains(regions)

        # Player is optional in templates (created by player at session join)
        player: PlayerCharacter | None = None
        try:
            player = load_player(world_path)
            if player.location_id == "" and locations:
                player.location_id = locations[0].id
        except (KeyError, FileNotFoundError):
            pass

        entities: list[Entity] = [*npcs]
        if player:
            entities.append(player)

        geography = GeographyLayer(regions=regions)
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

        world = World(
            layers=[geography, settlements_layer, politics, entities_layer],
            time=GameDateTime(year=1490, month=6, day=1, hour=10),
            location_graph=location_graph,
        )

        # Initial tick to set weather/temperature
        world.advance_time(TimeDelta(seconds=0))

        session = GameSession(
            session_id=session_id,
            world=world,
            player=player,
            lang=lang,
        )
        self._sessions[session_id] = session
        return session

    def player_action(self, session_id: str, text: str) -> MasterResponse:
        """Process player input and return DM response."""
        session = self._get_session(session_id)
        cmd = text.strip().lower()

        # Simple command parser until we have a real Master
        if cmd == "look":
            return self._cmd_look(session)

        if cmd == "map":
            return self._cmd_map(session)

        if cmd == "wait" or cmd.startswith("wait "):
            hours = 4
            if cmd.startswith("wait "):
                try:
                    hours = int(cmd[5:].strip())
                except ValueError:
                    return MasterResponse(text="Usage: wait [hours]  (e.g. wait 12)")
                if hours < 1:
                    return MasterResponse(text="Must wait at least 1 hour.")
            return self._cmd_wait(session, hours)

        if cmd.startswith("go "):
            return self._cmd_go(session, cmd[3:].strip())

        if cmd == "nations":
            return self._cmd_nations(session)

        if cmd.startswith("nation "):
            return self._cmd_nation_info(session, cmd[7:].strip())

        if cmd == "settlements":
            return self._cmd_settlements(session)

        if cmd == "status":
            return self._cmd_status(session)

        if cmd.startswith("attack "):
            return self._cmd_attack(session, text[7:].strip())

        if cmd.startswith("say "):
            return self._cmd_say(session, text[4:].strip())

        if cmd == "dodge":
            return self._cmd_dodge(session)

        if cmd == "flee":
            return self._cmd_flee(session)

        if cmd.startswith("move ") or cmd.startswith("dash "):
            return self._cmd_move(session, text, dash=cmd.startswith("dash "))

        return MasterResponse(
            text=f"Unknown command: '{text}'. "
            "Try: look, map, go <location>, wait [hours], attack <target>, say <text>, "
            "move/dash toward <target>, dodge, flee, nations, nation <id>, settlements, status"
        )

    def get_session(self, session_id: str) -> GameSession:
        """Get session info."""
        return self._get_session(session_id)

    def delete_session(self, session_id: str) -> None:
        """Stop and remove a session."""
        self._get_session(session_id)
        del self._sessions[session_id]

    def list_worlds(self) -> list[dict[str, str]]:
        """List available world templates."""
        worlds_dir = self._content_dir / "worlds"
        result: list[dict[str, str]] = []
        if not worlds_dir.exists():
            return result
        for entry in sorted(worlds_dir.iterdir()):
            is_world_dir = entry.is_dir() and (entry / "world.yaml").exists()
            is_world_file = entry.suffix in (".yaml", ".yml") and entry.is_file()
            if is_world_dir or is_world_file:
                meta = load_world_meta(entry)
                result.append({"id": entry.name, **meta})
        return result

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
        """Create a player character in a session that doesn't have one yet."""
        from dnd_simulator.content_loader import parse_player

        session = self._get_session(session_id)
        if session.player is not None:
            raise ValueError("Session already has a player")

        player = parse_player(player_data)

        # Default to first location if not specified
        if not player.location_id:
            graph = session.world.location_graph
            ids = graph.all_ids()
            if ids:
                player.location_id = ids[0]

        self._get_entities_layer(session).add_entity(player)
        session.player = player
        return player

    def _require_player(self, session: GameSession) -> PlayerCharacter:
        if session.player is None:
            raise ValueError("No player in this session")
        return session.player

    def _get_session(self, session_id: str) -> GameSession:
        if session_id not in self._sessions:
            raise ValueError(f"Session '{session_id}' not found")
        return self._sessions[session_id]
