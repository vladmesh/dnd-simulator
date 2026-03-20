from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dnd_simulator.content_loader import (
    extract_region_adjacency,
    extract_region_terrains,
    load_nations,
    load_npcs,
    load_player,
    load_settlements,
    load_world,
)
from dnd_simulator.core.character import Ability, build_awareness
from dnd_simulator.core.models import GameDateTime, Query, TimeDelta
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.llm.client import LlmClient
from dnd_simulator.llm.prompts import build_npc_system_prompt
from dnd_simulator.rules.geography import is_daylight
from dnd_simulator.storage.store import SaveStore

DEFAULT_CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"


@dataclass
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
    talking_to: str | None = None
    conversation_messages: list[dict[str, str]] = field(default_factory=list)

    @property
    def player_location(self) -> str:
        """Shortcut for player's current region."""
        return self.player.region_id if self.player else ""

    @player_location.setter
    def player_location(self, value: str) -> None:
        if self.player:
            self.player.region_id = value


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

    def start_game(self, world_file: str = "test_world.yaml") -> GameSession:
        """Create a new game session with a world loaded from content."""
        session_id = uuid.uuid4().hex[:8]

        world_path = self._content_dir / "worlds" / world_file
        regions = load_world(world_path)
        nations = load_nations(world_path)
        settlements = load_settlements(world_path)
        player = load_player(world_path)

        region_terrains = extract_region_terrains(regions)
        npcs = load_npcs(world_path)

        # Fall back to first region if player has no start_region
        if not player.region_id and regions:
            player.region_id = regions[0].id

        geography = GeographyLayer(regions=regions)
        settlements_layer = SettlementsLayer(settlements=settlements, region_terrains=region_terrains)
        politics = PoliticsLayer(
            nations=nations,
            region_terrains=region_terrains,
            region_adjacency=extract_region_adjacency(regions),
            region_income_fn=settlements_layer.get_region_income,
        )
        entities_layer = EntitiesLayer(entities=[*npcs, player])

        world = World(
            layers=[geography, settlements_layer, politics, entities_layer],
            time=GameDateTime(year=1490, month=6, day=1, hour=10),
        )

        # Initial tick to set weather/temperature
        world.advance_time(TimeDelta(seconds=0))

        session = GameSession(
            session_id=session_id,
            world=world,
            player=player,
        )
        self._sessions[session_id] = session
        return session

    def player_action(self, session_id: str, text: str) -> MasterResponse:
        """Process player input and return DM response."""
        session = self._get_session(session_id)

        # Conversation mode — forward input to NPC
        if session.talking_to:
            cmd_lower = text.strip().lower()
            if cmd_lower in ("bye", "leave", "exit"):
                return self._end_conversation(session)
            return self._continue_talk(session, text.strip())

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

        if cmd.startswith("talk "):
            return self._cmd_talk(session, cmd[5:].strip())

        if cmd == "status":
            return self._cmd_status(session)

        return MasterResponse(
            text=f"Unknown command: '{text}'. "
            "Try: look, map, go <dir>, wait [hours], nations, nation <id>, settlements, talk <npc>, status"
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

    # -- simple commands (placeholder until Master exists) --

    def _cmd_look(self, session: GameSession) -> MasterResponse:
        """Describe current location."""
        world = session.world
        loc = session.player_location

        info = world.query_layer("geography", Query(question="region_info", params={"region_id": loc}))
        weather = world.query_layer("geography", Query(question="weather", params={"region_id": loc}))
        conns = world.query_layer("geography", Query(question="connections", params={"region_id": loc}))

        lat = float(info.value["latitude"])
        day_or_night = "Day" if is_daylight(lat, world.time.month, world.time.hour) else "Night"

        owner = world.query_layer("politics", Query(question="region_owner", params={"region_id": loc}))
        territory = ""
        if owner.value:
            nation_info = world.query_layer(
                "politics", Query(question="nation_info", params={"nation_id": owner.value})
            )
            territory = f"  |  Territory: {nation_info.value['name']}"
        else:
            territory = "  |  Territory: Independent"

        settlements = world.query_layer("settlements", Query(question="region_settlements", params={"region_id": loc}))

        lines = [
            f"=== {info.value['name']} ===",
            f"Terrain: {info.value['terrain']}  |  Elevation: {info.value['elevation']}m{territory}",
            f"Weather: {weather.value['condition'].replace('_', ' ')}  |  {weather.value['temperature']}°C",
            f"Time: {world.time.hour:02d}:{world.time.minute:02d} ({day_or_night})",
        ]

        if settlements.value:
            lines.append("")
            lines.append("Settlements:")
            for s in settlements.value:
                lines.append(f"  {s['name']} ({s['type']}, pop {s['population']}, prosperity {s['prosperity']:.0f})")

        entities = world.query_layer("entities", Query(question="entities_in_region", params={"region_id": loc}))
        others = [e for e in entities.value if e["id"] != (session.player.id if session.player else "")]
        if others:
            lines.append("")
            lines.append("People:")
            for e in others:
                if "role" in e:
                    lines.append(f"  {e['name']} ({e['role']}) - {e['activity']}, at {e['location_label']}")
                else:
                    lines.append(f"  {e['name']}")

        lines.append("")
        lines.append("Paths:")
        for c in conns.value:
            travel = world.query_layer(
                "geography",
                Query(question="travel_time", params={"from_id": loc, "to_id": c["target_id"]}),
            )
            lines.append(
                f"  {c['direction'].upper()} → {c['target_id']}"
                f"  ({travel.value['distance_km']} km, ~{travel.value['hours']}h)"
            )

        return MasterResponse(text="\n".join(lines))

    def _cmd_map(self, session: GameSession) -> MasterResponse:
        """List all regions with weather."""
        world = session.world
        regions = world.query_layer("geography", Query(question="regions", params={}))

        lines = [f"=== World Map (Year {world.time.year}, Month {world.time.month}, Day {world.time.day}) ==="]
        for rid in regions.value:
            weather = world.query_layer("geography", Query(question="weather", params={"region_id": rid}))
            marker = " ← you are here" if rid == session.player_location else ""
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

    def _cmd_go(self, session: GameSession, direction: str) -> MasterResponse:
        """Move to a connected region."""
        world = session.world
        conns = world.query_layer(
            "geography", Query(question="connections", params={"region_id": session.player_location})
        )

        for c in conns.value:
            if c["direction"] == direction.lower():
                # Calculate actual travel time
                travel = world.query_layer(
                    "geography",
                    Query(
                        question="travel_time",
                        params={"from_id": session.player_location, "to_id": c["target_id"]},
                    ),
                )
                travel_hours = int(travel.value["hours"])
                travel_hours = max(1, travel_hours)  # minimum 1 hour

                session.player_location = c["target_id"]
                events = world.advance_time(TimeDelta.from_hours(travel_hours))
                look = self._cmd_look(session)

                header = f"You travel {direction.upper()} for ~{travel_hours}h ({travel.value['distance_km']} km)..."
                travel_notes = [e.description for e in events if e.description]
                if travel_notes:
                    return MasterResponse(
                        text=header + "\n" + "\n".join(f"  • {n}" for n in travel_notes) + f"\n\n{look.text}",
                        events_summary=travel_notes,
                    )
                return MasterResponse(text=f"{header}\n\n{look.text}")

        valid = ", ".join(c["direction"].upper() for c in conns.value)
        return MasterResponse(text=f"You can't go {direction.upper()}. Available: {valid}")

    def _cmd_nations(self, session: GameSession) -> MasterResponse:
        """List all nations with summary stats."""
        world = session.world
        nation_ids = world.query_layer("politics", Query(question="nations", params={}))

        lines = [f"=== Nations of the World (Year {world.time.year}) ==="]
        for nid in nation_ids.value:
            info = world.query_layer("politics", Query(question="nation_info", params={"nation_id": nid}))
            n = info.value
            leader = n["leader"]
            leader_str = f"{leader['name']} ({leader['trait']})" if leader else "none"
            marker = ""
            owner = world.query_layer(
                "politics", Query(question="region_owner", params={"region_id": session.player_location})
            )
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

    def _cmd_talk(self, session: GameSession, npc_query: str) -> MasterResponse:
        """Talk to an NPC. Finds NPC by name or id in current region."""
        world = session.world
        loc = session.player_location

        entities = world.query_layer("entities", Query(question="entities_in_region", params={"region_id": loc}))
        player_id = session.player.id if session.player else ""
        npcs = [e for e in entities.value if e["id"] != player_id and "role" in e]

        # Find NPC by id or partial name match
        target = None
        for npc in npcs:
            if npc["id"] == npc_query or npc_query.lower() in npc["name"].lower():
                target = npc
                break

        if not target:
            names = ", ".join(f"{n['name']} ({n['id']})" for n in npcs)
            if names:
                return MasterResponse(text=f"No one called '{npc_query}' here. Present: {names}")
            return MasterResponse(text="There's no one here to talk to.")

        # Check if NPC is sleeping
        if target.get("activity") == "sleeping":
            return MasterResponse(text=f"{target['name']} is sleeping. Best not to disturb.")

        if not self._llm:
            return MasterResponse(text="(LLM not configured — cannot start conversation)")

        # Get full NPC info and build prompt
        info = world.query_layer("entities", Query(question="entity_info", params={"entity_id": target["id"]}))
        npc_data = info.value
        awareness = build_awareness(world, loc)
        system_prompt = build_npc_system_prompt(npc_data, awareness)

        # Build player impression through NPC perception
        npc_obj = self._get_npc_object(session, target["id"])
        impression = ""
        if session.player and npc_obj:
            impression = npc_obj.perceive(session.player)
        greeting_prompt = (
            f"К тебе подходит {impression}. Поприветствуй его в образе."
            if impression
            else ("К тебе подходит незнакомец. Поприветствуй его в образе.")
        )

        # Enter conversation mode
        session.talking_to = target["id"]
        session.conversation_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": greeting_prompt},
        ]

        response = self._llm.generate(session.conversation_messages)
        session.conversation_messages.append({"role": "assistant", "content": response})

        return MasterResponse(
            text=f"You approach {npc_data['name']} at the {npc_data['location_label']}.\n\n"
            f"{npc_data['name']}: {response}\n\n"
            "(type 'bye' to end conversation)"
        )

    def _continue_talk(self, session: GameSession, text: str) -> MasterResponse:
        """Continue a conversation with an NPC."""
        assert session.talking_to
        assert self._llm

        npc_info = session.world.query_layer(
            "entities", Query(question="entity_info", params={"entity_id": session.talking_to})
        )
        npc_name = npc_info.value["name"]

        session.conversation_messages.append({"role": "user", "content": text})
        response = self._llm.generate(session.conversation_messages)
        session.conversation_messages.append({"role": "assistant", "content": response})

        return MasterResponse(text=f"{npc_name}: {response}")

    def _end_conversation(self, session: GameSession) -> MasterResponse:
        """End the current conversation."""
        assert session.talking_to

        npc_info = session.world.query_layer(
            "entities", Query(question="entity_info", params={"entity_id": session.talking_to})
        )
        npc_name = npc_info.value["name"]

        session.talking_to = None
        session.conversation_messages.clear()
        return MasterResponse(text=f"You end your conversation with {npc_name}.")

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
        loc = session.player_location

        settlements = world.query_layer("settlements", Query(question="region_settlements", params={"region_id": loc}))

        info = world.query_layer("geography", Query(question="region_info", params={"region_id": loc}))
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

    def _get_npc_object(self, session: GameSession, npc_id: str) -> Any:
        """Get the Npc object from the entities layer (for perceive calls)."""
        for layer in session.world.layers:
            if isinstance(layer, EntitiesLayer):
                return layer.get_entity(npc_id)
        return None

    def _get_session(self, session_id: str) -> GameSession:
        if session_id not in self._sessions:
            raise ValueError(f"Session '{session_id}' not found")
        return self._sessions[session_id]
