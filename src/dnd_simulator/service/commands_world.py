from __future__ import annotations

from typing import TYPE_CHECKING, Any

from dnd_simulator.core.models import Query, TimeDelta
from dnd_simulator.rules.geography import is_daylight
from dnd_simulator.service.session import GameSession, MasterResponse

if TYPE_CHECKING:
    from dnd_simulator.core.player import PlayerCharacter


class WorldCommands:
    """Mixin: world exploration commands and queries."""

    def _require_player(self, session: GameSession) -> PlayerCharacter:
        raise NotImplementedError

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
                if "activity_flavor" in e:
                    lines.append(f"  {e['name']} — {e['activity_flavor']}")
                elif "role" in e:
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

    def _cmd_status(self, session: GameSession) -> MasterResponse:
        """Show player character info."""
        from dnd_simulator.core.character import Ability

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

    def get_perception(self, session_id: str) -> dict[str, Any]:
        """Get what the player's character perceives — awareness of surroundings."""
        from dnd_simulator.core.character import build_awareness

        session = self._get_session(session_id)  # type: ignore[attr-defined]
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

    def get_map(self, session_id: str) -> dict[str, Any]:
        """Get map data: current location neighbors with travel info."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
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

    def get_new_events(self, session_id: str) -> list[str]:
        """Get events since the player last checked."""
        session = self._get_session(session_id)  # type: ignore[attr-defined]
        player = self._require_player(session)
        answer = session.world.query_layer(
            "entities", Query(question="new_perceived_events", params={"entity_id": player.id})
        )
        result: list[str] = answer.value if answer.value else []
        return result
