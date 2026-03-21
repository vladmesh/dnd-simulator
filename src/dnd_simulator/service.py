from __future__ import annotations

import uuid
from dataclasses import dataclass
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
    parse_npc,
)
from dnd_simulator.core.brain import RuleBrain
from dnd_simulator.core.character import Ability, Entity
from dnd_simulator.core.location import LocationGraph
from dnd_simulator.core.models import GameDateTime, Query, TimeDelta
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.rules.geography import is_daylight
from dnd_simulator.storage.store import SaveStore

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


@dataclass(frozen=True)
class MasterResponse:
    """What the DM tells the player."""

    text: str
    events_summary: list[str] | None = None


@dataclass
class GameSession:
    """An active game session."""

    session_id: str
    world: World
    player: PlayerCharacter | None = None
    lang: str = "en"

    @property
    def player_location(self) -> str:
        """Shortcut for player's current location."""
        return self.player.location_id if self.player else ""

    @player_location.setter
    def player_location(self, value: str) -> None:
        if self.player:
            self.player.location_id = value


class GameService:
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
        entities_layer = EntitiesLayer(entities=entities)

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

    def save_game(self, session_id: str, name: str | None = None) -> str:
        """Save game state. Returns the save name."""
        session = self._get_session(session_id)
        save_name = name or f"save_{session_id}"
        data: dict[str, Any] = {
            "world": session.world.save(),
            "player": session.player.to_save_data() if session.player else {},
        }
        self._store.save(save_name, data)
        return save_name

    def load_game(self, session_id: str, name: str) -> None:
        """Load game state into session."""
        session = self._get_session(session_id)
        data = self._store.load(name)

        # Support both old format (flat world data) and new format (world + player)
        if "world" in data:
            session.world.load(data["world"])
            player_data = data.get("player", {})
            assert isinstance(player_data, dict)
            if session.player:
                session.player.load_save_data(player_data)
        else:
            session.world.load(data)

    def list_saves(self) -> list[str]:
        """List available saves."""
        return self._store.list_saves()

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

    def delete_session(self, session_id: str) -> None:
        """Stop and remove a session."""
        self._get_session(session_id)
        del self._sessions[session_id]

    # -- Master hot controls (live session edits) --

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

    def spawn_npc(self, session_id: str, npc_data: dict[str, Any]) -> Npc:
        """Spawn an NPC into a live session."""
        session = self._get_session(session_id)
        npc = parse_npc(str(npc_data["id"]), npc_data)
        self._get_entities_layer(session).add_entity(npc)
        return npc

    def remove_npc(self, session_id: str, npc_id: str) -> None:
        """Remove an NPC from a live session."""
        session = self._get_session(session_id)
        layer = self._get_entities_layer(session)
        entity = layer.get_entity(npc_id)
        if entity is None:
            raise ValueError(f"NPC '{npc_id}' not found")
        layer.remove_entity(npc_id)

    def patch_npc(self, session_id: str, npc_id: str, updates: dict[str, Any]) -> None:
        """Update mutable NPC fields in a live session."""
        session = self._get_session(session_id)
        entity = self._get_entities_layer(session).get_entity(npc_id)
        if entity is None or not isinstance(entity, Npc):
            raise ValueError(f"NPC '{npc_id}' not found")

        if "current_hp" in updates:
            entity.current_hp = int(updates["current_hp"])
        if "ac" in updates:
            entity.ac = int(updates["ac"])
        if "personality" in updates:
            entity.personality = str(updates["personality"])
        if "location_id" in updates:
            entity.location_id = str(updates["location_id"])
        if "gold" in updates:
            entity.gold = int(updates["gold"])

    def set_npc_brain(self, session_id: str, npc_id: str, brain_type: str, model: str = "") -> None:
        """Switch NPC brain (rule_based or llm)."""
        session = self._get_session(session_id)
        entity = self._get_entities_layer(session).get_entity(npc_id)
        if entity is None or not isinstance(entity, Npc):
            raise ValueError(f"NPC '{npc_id}' not found")

        if brain_type == "rule_based":
            entity.brain = RuleBrain()
            entity.ai_type = "rule_based"
        elif brain_type == "llm":
            if not self._llm:
                raise ValueError("LLM not configured")
            from dnd_simulator.llm.brain import LlmBrain

            entity.brain = LlmBrain(self._llm)
            entity.ai_type = "llm"
        else:
            raise ValueError(f"Unknown brain type: {brain_type}")

    def patch_nation(self, session_id: str, nation_id: str, updates: dict[str, Any]) -> None:
        """Update mutable nation fields in a live session."""
        session = self._get_session(session_id)
        layer = self._get_politics_layer(session)
        nation = layer.get_nation(nation_id)

        if "wealth" in updates:
            nation.wealth = float(updates["wealth"])
        if "military" in updates:
            nation.military = float(updates["military"])
        if "stability" in updates:
            nation.stability = float(updates["stability"])

    def patch_settlement(self, session_id: str, settlement_id: str, updates: dict[str, Any]) -> None:
        """Update mutable settlement fields in a live session."""
        session = self._get_session(session_id)
        layer = self._get_settlements_layer(session)
        settlement = layer.get_settlement(settlement_id)

        if "population" in updates:
            settlement.population = int(updates["population"])
        if "prosperity" in updates:
            settlement.prosperity = float(updates["prosperity"])
        if "defenses" in updates:
            settlement.defenses = float(updates["defenses"])

    def advance_time(self, session_id: str, hours: int) -> list[str]:
        """Advance game time by given hours. Returns event descriptions."""
        session = self._get_session(session_id)
        events = session.world.advance_time(TimeDelta.from_hours(hours))
        return [e.description for e in events if e.description]

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

    def get_perception(self, session_id: str) -> dict[str, Any]:
        """Get what the player's character perceives — awareness of surroundings."""
        from dnd_simulator.core.character import build_awareness

        session = self._get_session(session_id)
        player = self._require_player(session)
        world = session.world

        awareness = build_awareness(world, player.location_id)

        # Entities at location, perceived through player's eyes
        entities_answer = world.query_layer(
            "entities",
            Query(
                question="entities_at_location",
                params={"location_id": player.location_id, "hour": world.time.hour},
            ),
        )
        perceived_entities: list[dict[str, str]] = []
        for e in entities_answer.value:
            if e["id"] != player.id:
                desc = player.perceive_by_id(str(e["id"]), world)
                perceived_entities.append({"id": str(e["id"]), "description": desc})

        # Neighbors from location graph
        graph = world.location_graph
        location = graph.get(player.location_id)
        neighbors = [
            {"target_id": edge.target_id, "name": graph.get(edge.target_id).name, "distance_m": edge.distance_m}
            for edge in location.edges
        ]

        return {
            **awareness,
            "entities": perceived_entities,
            "neighbors": neighbors,
        }

    def get_new_events(self, session_id: str) -> list[str]:
        """Get events since the player last checked."""
        session = self._get_session(session_id)
        player = self._require_player(session)
        answer = session.world.query_layer(
            "entities", Query(question="new_perceived_events", params={"entity_id": player.id})
        )
        result: list[str] = answer.value if answer.value else []
        return result

    def get_combat_state(self, session_id: str) -> dict[str, Any] | None:
        """Get combat state from the player's perspective. Returns None if not in combat."""
        from dnd_simulator.core.character import build_combat_awareness

        session = self._get_session(session_id)
        player = self._require_player(session)

        if not player.in_combat:
            return None

        return build_combat_awareness(session.world, player)

    def get_map(self, session_id: str) -> dict[str, Any]:
        """Get map data: current location neighbors with travel info."""
        session = self._get_session(session_id)
        player = self._require_player(session)
        world = session.world
        graph = world.location_graph
        loc = player.location_id

        location = graph.get(loc)
        region_id = location.region_id
        region_info = world.query_layer("geography", Query(question="region_info", params={"region_id": region_id}))

        paths: list[dict[str, object]] = []
        for edge in location.edges:
            target = graph.get(edge.target_id)
            travel_secs = graph.travel_seconds(loc, edge.target_id)
            paths.append(
                {
                    "target_id": edge.target_id,
                    "target_name": target.name,
                    "distance_m": edge.distance_m,
                    "travel_seconds": travel_secs,
                }
            )

        return {
            "current_location": {"id": location.id, "name": location.name, "region_id": region_id},
            "current_region": region_info.value,
            "paths": paths,
        }

    def _require_player(self, session: GameSession) -> PlayerCharacter:
        if session.player is None:
            raise ValueError("No player in this session")
        return session.player

    # -- simple commands (placeholder until Master exists) --

    def _cmd_look(self, session: GameSession) -> MasterResponse:
        """Describe current location."""
        world = session.world
        graph = world.location_graph
        loc_id = session.player_location

        location = graph.get(loc_id)
        region_id = location.region_id

        info = world.query_layer("geography", Query(question="region_info", params={"region_id": region_id}))
        weather = world.query_layer("geography", Query(question="weather", params={"region_id": region_id}))

        lat = float(info.value["latitude"])
        day_or_night = "Day" if is_daylight(lat, world.time.month, world.time.hour) else "Night"

        owner = world.query_layer("politics", Query(question="region_owner", params={"region_id": region_id}))
        territory = ""
        if owner.value:
            nation_info = world.query_layer(
                "politics", Query(question="nation_info", params={"nation_id": owner.value})
            )
            territory = f"  |  Territory: {nation_info.value['name']}"
        else:
            territory = "  |  Territory: Independent"

        settlements = world.query_layer(
            "settlements", Query(question="region_settlements", params={"region_id": region_id})
        )

        lines = [
            f"=== {location.name} ===",
            f"Terrain: {info.value['terrain']}  |  Elevation: {info.value['elevation']}m{territory}",
            f"Weather: {weather.value['condition'].replace('_', ' ')}  |  {weather.value['temperature']}°C",
            f"Time: {world.time.hour:02d}:{world.time.minute:02d} ({day_or_night})",
        ]

        if location.description:
            lines.append(location.description)

        if settlements.value:
            lines.append("")
            lines.append("Settlements:")
            for s in settlements.value:
                lines.append(f"  {s['name']} ({s['type']}, pop {s['population']}, prosperity {s['prosperity']:.0f})")

        entities = world.query_layer(
            "entities",
            Query(
                question="entities_at_location",
                params={"location_id": loc_id, "hour": world.time.hour},
            ),
        )
        others = [e for e in entities.value if e["id"] != (session.player.id if session.player else "")]
        if others:
            lines.append("")
            lines.append("People:")
            for e in others:
                if "role" in e:
                    lines.append(f"  {e['name']} ({e['role']}) - {e['activity']}")
                else:
                    lines.append(f"  {e['name']}")

        lines.append("")
        lines.append("Paths:")
        for edge in location.edges:
            target = graph.get(edge.target_id)
            dist_str = f"{edge.distance_m / 1000:.1f} km" if edge.distance_m >= 1000 else f"{edge.distance_m} m"
            travel_secs = graph.travel_seconds(loc_id, edge.target_id)
            time_str = f"~{travel_secs / 3600:.1f}h" if travel_secs >= 3600 else f"~{travel_secs // 60}min"
            lines.append(f"  {target.name} ({edge.target_id}) — {dist_str}, {time_str}")

        return MasterResponse(text="\n".join(lines))

    def _cmd_map(self, session: GameSession) -> MasterResponse:
        """List all regions with weather."""
        world = session.world
        regions = world.query_layer("geography", Query(question="regions", params={}))

        lines = [f"=== World Map (Year {world.time.year}, Month {world.time.month}, Day {world.time.day}) ==="]
        current_region = world.location_graph.region_of(session.player_location) if session.player_location else ""
        for rid in regions.value:
            weather = world.query_layer("geography", Query(question="weather", params={"region_id": rid}))
            marker = " ← you are here" if rid == current_region else ""
            lines.append(
                f"  {rid}: {weather.value['condition'].replace('_', ' ')}, {weather.value['temperature']}°C{marker}"
            )

        return MasterResponse(text="\n".join(lines))

    def _cmd_wait(self, session: GameSession, hours: int = 4) -> MasterResponse:
        """Wait specified hours, advancing time."""
        events = session.world.advance_time(TimeDelta.from_hours(hours))
        t = session.world.time

        lines = [f"Time passes... It is now {t.hour:02d}:{t.minute:02d}, day {t.day}, month {t.month}."]
        for e in events:
            if e.description:
                lines.append(f"  • {e.description}")

        return MasterResponse(text="\n".join(lines), events_summary=[e.description for e in events])

    def _cmd_go(self, session: GameSession, target: str) -> MasterResponse:
        """Move to a neighboring location."""
        world = session.world
        graph = world.location_graph
        loc_id = session.player_location

        edge = graph.edge_between(loc_id, target)
        if edge is None:
            # List available neighbors
            location = graph.get(loc_id)
            available = ", ".join(e.target_id for e in location.edges)
            return MasterResponse(text=f"Can't go to '{target}'. Available: {available}")

        # Calculate travel time with terrain/weather modifiers
        target_region = graph.region_of(target)
        region_info = world.query_layer("geography", Query(question="region_info", params={"region_id": target_region}))
        weather = world.query_layer("geography", Query(question="weather", params={"region_id": target_region}))

        # Use rules/geography for proper speed calculation
        from dnd_simulator.rules.geography import calculate_travel_hours

        terrain_type = region_info.value["terrain"]
        weather_condition = weather.value["condition"]
        from dnd_simulator.core.models import TerrainType, WeatherCondition

        distance_km = edge.distance_m / 1000.0
        travel_hours = calculate_travel_hours(
            distance_km,
            TerrainType(terrain_type),
            WeatherCondition(weather_condition),
        )
        travel_hours = max(travel_hours, 1 / 60)  # minimum 1 minute

        session.player_location = target
        travel_seconds = int(travel_hours * 3600)
        events = world.advance_time(TimeDelta(seconds=travel_seconds))
        look = self._cmd_look(session)

        if travel_hours >= 1:
            header = f"You travel to {graph.get(target).name} ({distance_km:.1f} km, ~{travel_hours:.1f}h)..."
        else:
            header = f"You walk to {graph.get(target).name} ({edge.distance_m}m, ~{int(travel_hours * 60)}min)..."

        travel_notes = [e.description for e in events if e.description]
        if travel_notes:
            return MasterResponse(
                text=header + "\n" + "\n".join(f"  • {n}" for n in travel_notes) + f"\n\n{look.text}",
                events_summary=travel_notes,
            )
        return MasterResponse(text=f"{header}\n\n{look.text}")

    def _cmd_nations(self, session: GameSession) -> MasterResponse:
        """List all nations with summary stats."""
        world = session.world
        nation_ids = world.query_layer("politics", Query(question="nations", params={}))

        lines = [f"=== Nations of the World (Year {world.time.year}) ==="]
        current_region = world.location_graph.region_of(session.player_location) if session.player_location else ""
        for nid in nation_ids.value:
            info = world.query_layer("politics", Query(question="nation_info", params={"nation_id": nid}))
            n = info.value
            leader = n["leader"]
            leader_str = f"{leader['name']} ({leader['trait']})" if leader else "none"
            marker = ""
            owner = world.query_layer("politics", Query(question="region_owner", params={"region_id": current_region}))
            if owner.value == nid:
                marker = " ← you are here"
            lines.append(
                f"  {n['name']}: W={n['wealth']:.0f} M={n['military']:.0f} S={n['stability']:.0f}"
                f"  Leader: {leader_str}  Regions: {len(n['regions'])}{marker}"
            )

        return MasterResponse(text="\n".join(lines))

    def _cmd_nation_info(self, session: GameSession, nation_id: str) -> MasterResponse:
        """Detailed info about a specific nation."""
        world = session.world

        try:
            info = world.query_layer("politics", Query(question="nation_info", params={"nation_id": nation_id}))
        except KeyError:
            nations = world.query_layer("politics", Query(question="nations", params={}))
            return MasterResponse(text=f"Nation '{nation_id}' not found. Known: {', '.join(nations.value)}")

        n = info.value
        leader = n["leader"]

        lines = [
            f"=== {n['name']} ===",
            f"Wealth: {n['wealth']:.0f}  |  Military: {n['military']:.0f}  |  Stability: {n['stability']:.0f}",
        ]
        if leader:
            lines.append(f"Leader: {leader['name']}, age {leader['age']} ({leader['trait']})")

        lines.append(f"Regions: {', '.join(n['regions'])}")

        # Relations
        rels = world.query_layer("politics", Query(question="relations", params={"nation_id": nation_id}))
        if rels.value:
            lines.append("\nDiplomacy:")
            for r in rels.value:
                other_info = world.query_layer(
                    "politics", Query(question="nation_info", params={"nation_id": r["nation"]})
                )
                status_str = r["status"].replace("_", " ").title()
                lines.append(f"  {other_info.value['name']}: {status_str}")

        return MasterResponse(text="\n".join(lines))

    def _cmd_status(self, session: GameSession) -> MasterResponse:
        """Show player character info."""
        p = session.player
        if not p:
            return MasterResponse(text="No player character.")

        race_label = p.race.value.replace("_", " ").title()
        class_label = p.char_class.value.title()
        alignment_label = p.alignment.value.replace("_", " ").title()
        scores = p.ability_scores

        lines = [
            f"=== {p.name} ===",
            f"Race: {race_label}  |  Class: {class_label} {p.level}  |  Alignment: {alignment_label}",
            f"HP: {p.current_hp}/{p.max_hp}  |  Gold: {p.gold}",
            f"STR {scores[Ability.STR]}  DEX {scores[Ability.DEX]}  CON {scores[Ability.CON]}"
            f"  INT {scores[Ability.INT]}  WIS {scores[Ability.WIS]}  CHA {scores[Ability.CHA]}",
        ]
        if p.appearance:
            lines.append(f"Appearance: {p.appearance}")

        return MasterResponse(text="\n".join(lines))

    def _cmd_settlements(self, session: GameSession) -> MasterResponse:
        """List all settlements in current region."""
        world = session.world
        region_id = world.location_graph.region_of(session.player_location)

        settlements = world.query_layer(
            "settlements", Query(question="region_settlements", params={"region_id": region_id})
        )

        info = world.query_layer("geography", Query(question="region_info", params={"region_id": region_id}))
        lines = [f"=== Settlements in {info.value['name']} ==="]

        if not settlements.value:
            lines.append("  No settlements here.")
        else:
            for s in settlements.value:
                lines.append(
                    f"  {s['name']} ({s['type']})"
                    f"  Pop: {s['population']}  Prosperity: {s['prosperity']:.0f}"
                    f"  Defenses: {s['defenses']:.0f}"
                )

        return MasterResponse(text="\n".join(lines))

    def _cmd_attack(self, session: GameSession, target_id: str) -> MasterResponse:
        """Attack a target entity."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        if not target_id:
            return MasterResponse(text="Usage: attack <target_id>")

        result = session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": player.id, "target_id": target_id},
            )
        )
        if not result.success:
            return MasterResponse(text=result.error)

        descriptions = [e.description for e in result.events if e.description]
        return MasterResponse(text="\n".join(descriptions) if descriptions else "Attack!", events_summary=descriptions)

    def _cmd_say(self, session: GameSession, text: str) -> MasterResponse:
        """Say something in the current location."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data={"entity_id": player.id, "text": text},
            )
        )
        return MasterResponse(text=f'{player.name} says: "{text}"')

    def _cmd_dodge(self, session: GameSession) -> MasterResponse:
        """Take the dodge action."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_DODGE,
                source_layer="entities",
                data={"entity_id": player.id},
            )
        )
        return MasterResponse(text=f"{player.name} takes the Dodge action.")

    def _cmd_move(self, session: GameSession, text: str, dash: bool = False) -> MasterResponse:
        """Move or dash in combat."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        args = text[5:].strip().split()
        if not args:
            return MasterResponse(text="Usage: move/dash <toward|away|north|south|...> [target]")

        event_data: dict[str, object] = {"entity_id": player.id}
        keyword = args[0].lower()
        if keyword == "toward" and len(args) > 1:
            event_data["toward"] = args[1]
        elif keyword == "away" and len(args) > 1:
            event_data["away_from"] = args[1]
        else:
            event_data["direction"] = keyword

        result = session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_DASH if dash else EventType.ENTITY_MOVE,
                source_layer="entities",
                data=event_data,
            )
        )
        if not result.success:
            return MasterResponse(text=result.error)
        descriptions = [e.description for e in result.events if e.description]
        return MasterResponse(text="\n".join(descriptions) if descriptions else "Moved.")

    def _cmd_flee(self, session: GameSession) -> MasterResponse:
        """Attempt to flee combat."""
        from dnd_simulator.core.models import Event, EventType

        player = self._require_player(session)
        result = session.world.handle_event(
            Event(
                event_type=EventType.ENTITY_FLEE,
                source_layer="entities",
                data={"entity_id": player.id},
            )
        )
        if not result.success:
            return MasterResponse(text=result.error)
        descriptions = [e.description for e in result.events if e.description]
        return MasterResponse(text="\n".join(descriptions) if descriptions else "You flee!")

    def _get_session(self, session_id: str) -> GameSession:
        if session_id not in self._sessions:
            raise ValueError(f"Session '{session_id}' not found")
        return self._sessions[session_id]
