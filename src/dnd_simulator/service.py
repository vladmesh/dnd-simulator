from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from dnd_simulator.content_loader import load_world
from dnd_simulator.core.models import GameDateTime, Query, TimeDelta
from dnd_simulator.core.world import World
from dnd_simulator.layers.geography.formulas import is_daylight
from dnd_simulator.layers.geography.layer import GeographyLayer
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
    player_location: str = ""


class GameService:
    """Main interface to the game. Transport-agnostic."""

    def __init__(
        self,
        store: SaveStore,
        content_dir: Path = DEFAULT_CONTENT_DIR,
    ) -> None:
        self._sessions: dict[str, GameSession] = {}
        self._store = store
        self._content_dir = content_dir

    def start_game(self, world_file: str = "test_world.yaml") -> GameSession:
        """Create a new game session with a world loaded from content."""
        session_id = uuid.uuid4().hex[:8]

        regions = load_world(self._content_dir / "worlds" / world_file)
        geography = GeographyLayer(regions=regions)
        world = World(layers=[geography], time=GameDateTime(year=1490, month=6, day=1, hour=10))

        # Initial tick to set weather/temperature
        world.advance_time(TimeDelta(hours=0))

        session = GameSession(
            session_id=session_id,
            world=world,
            player_location=regions[0].id if regions else "",
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

        if cmd == "wait":
            return self._cmd_wait(session)

        if cmd.startswith("go "):
            return self._cmd_go(session, cmd[3:].strip())

        return MasterResponse(text=f"Unknown command: '{text}'. Try: look, map, go <direction>, wait")

    def get_session(self, session_id: str) -> GameSession:
        """Get session info."""
        return self._get_session(session_id)

    def save_game(self, session_id: str, name: str | None = None) -> str:
        """Save game state. Returns the save name."""
        session = self._get_session(session_id)
        save_name = name or f"save_{session_id}"
        data: dict[str, Any] = {
            "world": session.world.save(),
            "player": {"location": session.player_location},
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
            session.player_location = str(player_data.get("location", session.player_location))
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

        lines = [
            f"=== {info.value['name']} ===",
            f"Terrain: {info.value['terrain']}  |  Elevation: {info.value['elevation']}m",
            f"Weather: {weather.value['condition'].replace('_', ' ')}  |  {weather.value['temperature']}°C",
            f"Time: {world.time.hour:02d}:{world.time.minute:02d} ({day_or_night})",
            "",
            "Paths:",
        ]
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

    def _cmd_wait(self, session: GameSession) -> MasterResponse:
        """Wait a few hours, advancing time."""
        events = session.world.advance_time(TimeDelta(hours=4))
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
                events = world.advance_time(TimeDelta(hours=travel_hours))
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

    def _get_session(self, session_id: str) -> GameSession:
        if session_id not in self._sessions:
            raise ValueError(f"Session '{session_id}' not found")
        return self._sessions[session_id]
