"""Player character model."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dnd_simulator.core.character import (
    Ability,
    Character,
    build_awareness,
    build_combat_awareness,
)
from dnd_simulator.i18n import _

if TYPE_CHECKING:
    from dnd_simulator.core.world import World


@dataclass
class PlayerCharacter(Character):
    """The player's avatar in the world."""

    input_fn: Callable[[str], str] = field(default=input, repr=False)
    output_fn: Callable[[str], object] = field(default=print, repr=False)

    def take_turn(self, world: World) -> None:
        """Show awareness + recent events, prompt for action, execute."""
        if self.in_combat:
            self._combat_turn(world)
        else:
            self._peaceful_turn(world)

    def _peaceful_turn(self, world: World) -> None:
        """Peacetime turn: full awareness, all commands available."""
        from dnd_simulator.core.models import Event, EventType, Query

        awareness = build_awareness(world, self.region_id)

        # Get new events since player's last turn
        log_answer = world.query_layer(
            "entities", Query(question="new_perceived_events", params={"entity_id": self.id})
        )
        recent_events: list[str] = log_answer.value if log_answer.value else []

        self.output_fn(self._format_awareness(awareness, recent_events))

        while True:
            raw = self.input_fn("> ").strip()
            if not raw:
                continue

            cmd = raw.lower()

            # Informational commands — don't end turn
            if cmd == "look":
                self._cmd_look(world)
                continue
            if cmd == "status":
                self._cmd_status()
                continue

            # Action commands — end turn
            if cmd == "idle":
                return

            if cmd == "wait" or cmd.startswith("wait "):
                self._cmd_wait(cmd, world)
                return

            if cmd.startswith("say "):
                text = raw[4:].strip()
                world.handle_event(
                    Event(
                        event_type=EventType.ENTITY_SAY,
                        source_layer="entities",
                        data={"entity_id": self.id, "text": text},
                    )
                )
                return

            if cmd.startswith("attack "):
                target_id = raw[7:].strip().split()[0] if raw[7:].strip() else ""
                if not target_id:
                    self.output_fn(_("Usage: attack <target>"))
                    continue
                result = world.handle_event(
                    Event(
                        event_type=EventType.ENTITY_ATTACK,
                        source_layer="entities",
                        data={"attacker_id": self.id, "target_id": target_id},
                    )
                )
                if not result.success:
                    self.output_fn(result.error)
                    continue
                return

            self.output_fn(_("Commands: look, status, say <text>, attack <target>, wait [hours], idle"))

    def _combat_turn(self, world: World) -> None:
        """Combat turn: focused awareness, restricted commands."""
        from dnd_simulator.core.models import Event, EventType, Query

        combat_aw = build_combat_awareness(world, self)

        log_answer = world.query_layer(
            "entities", Query(question="new_perceived_events", params={"entity_id": self.id})
        )
        recent_events: list[str] = log_answer.value if log_answer.value else []

        self.output_fn(self._format_combat_awareness(combat_aw, recent_events))

        while True:
            raw = self.input_fn(_("combat> ")).strip()
            if not raw:
                continue

            cmd = raw.lower()

            if cmd == "status":
                self._cmd_status()
                continue

            if cmd == "idle":
                return

            if cmd == "dodge":
                world.handle_event(
                    Event(
                        event_type=EventType.ENTITY_DODGE,
                        source_layer="entities",
                        data={"entity_id": self.id},
                    )
                )
                return

            if cmd == "flee":
                world.handle_event(
                    Event(
                        event_type=EventType.ENTITY_FLEE,
                        source_layer="entities",
                        data={"entity_id": self.id},
                    )
                )
                return

            if cmd.startswith("attack "):
                target_id = raw[7:].strip().split()[0] if raw[7:].strip() else ""
                if not target_id:
                    self.output_fn(_("Usage: attack <target>"))
                    continue
                result = world.handle_event(
                    Event(
                        event_type=EventType.ENTITY_ATTACK,
                        source_layer="entities",
                        data={"attacker_id": self.id, "target_id": target_id},
                    )
                )
                if not result.success:
                    self.output_fn(result.error)
                    continue
                return

            if cmd.startswith("move ") or cmd.startswith("dash "):
                is_dash = cmd.startswith("dash ")
                args = raw[5:].strip().split()
                if not args:
                    self.output_fn(_("Usage: move/dash <toward|away|north|south|...> [target]"))
                    continue
                event_data: dict[str, object] = {"entity_id": self.id}
                keyword = args[0].lower()
                if keyword == "toward" and len(args) > 1:
                    event_data["toward"] = args[1]
                elif keyword == "away" and len(args) > 1:
                    event_data["away_from"] = args[1]
                else:
                    event_data["direction"] = keyword
                result = world.handle_event(
                    Event(
                        event_type=EventType.ENTITY_DASH if is_dash else EventType.ENTITY_MOVE,
                        source_layer="entities",
                        data=event_data,
                    )
                )
                if not result.success:
                    self.output_fn(result.error)
                    continue
                return

            self.output_fn(
                _(
                    "Commands: attack <target>, move <direction> [target], "
                    "dash <direction> [target], dodge, flee, status, idle"
                )
            )

    def _cmd_look(self, world: World) -> None:
        """Describe current location, entities, and paths."""
        from dnd_simulator.core.models import Query

        info = world.query_layer("geography", Query(question="region_info", params={"region_id": self.region_id}))
        weather = world.query_layer("geography", Query(question="weather", params={"region_id": self.region_id}))
        conns = world.query_layer("geography", Query(question="connections", params={"region_id": self.region_id}))
        entities = world.query_layer(
            "entities", Query(question="entities_in_region", params={"region_id": self.region_id})
        )

        lines = [f"=== {info.value['name']} ==="]
        lines.append(
            _("Terrain:")
            + f" {info.value['terrain']}  |  "
            + _("Weather:")
            + f" {weather.value['condition'].replace('_', ' ')}, {weather.value['temperature']}°C"
        )

        others = [e for e in entities.value if e["id"] != self.id]
        if others:
            lines.append("\n" + _("Creatures:"))
            for e in others:
                if "role" in e:
                    lines.append(f"  {e['name']} [{e['id']}] ({e['role']}) — {e['activity']}")
                else:
                    lines.append(f"  {e['name']} [{e['id']}]")

        if conns.value:
            lines.append("\n" + _("Paths:"))
            for c in conns.value:
                lines.append(f"  {c['direction'].upper()} → {c['target_id']}")

        self.output_fn("\n".join(lines))

    def _cmd_status(self) -> None:
        """Show player stats."""
        scores = self.ability_scores
        lines = [
            f"=== {self.name} ===",
            _("HP: {hp}/{max_hp} | AC: {ac} | Gold: {gold}").format(
                hp=self.current_hp, max_hp=self.max_hp, ac=self.ac, gold=self.gold
            ),
            f"STR {scores[Ability.STR]}  DEX {scores[Ability.DEX]}  CON {scores[Ability.CON]}"
            f"  INT {scores[Ability.INT]}  WIS {scores[Ability.WIS]}  CHA {scores[Ability.CHA]}",
        ]
        if self.attacks:
            lines.append(_("Attacks:") + " " + ", ".join(a.name for a in self.attacks))
        self.output_fn("\n".join(lines))

    def _cmd_wait(self, cmd: str, world: World) -> None:
        """Wait for N hours (default 1)."""
        from dnd_simulator.core.models import TimeDelta

        parts = cmd.split()
        hours = 1
        if len(parts) > 1:
            try:
                hours = int(parts[1])
            except ValueError:
                self.output_fn(_("Usage: wait [hours]"))
                return
            if hours < 1:
                self.output_fn(_("Minimum 1 hour."))
                return
        world.advance_time(TimeDelta.from_hours(hours))
        self.output_fn(_("Passed {hours} h.").format(hours=hours))

    def _format_combat_awareness(self, combat_aw: dict[str, Any], recent_events: list[str] | None = None) -> str:
        """Format combat awareness for display to the player."""
        hp = combat_aw["self_hp"]
        max_hp = combat_aw["self_max_hp"]
        weapon = combat_aw["self_weapon"]
        speed = combat_aw.get("self_speed", 30)
        round_num = combat_aw.get("round_number", 1)
        lines = [
            "\n--- "
            + _("Combat, round {round} (HP: {hp}/{max_hp}, weapon: {weapon}, speed: {speed} ft)").format(
                round=round_num, hp=hp, max_hp=max_hp, weapon=weapon, speed=speed
            )
            + " ---"
        ]

        nearby = combat_aw.get("nearby", [])
        if nearby:
            lines.append("\n" + _("Around:"))
            for e in nearby:
                dist = e.get("distance_ft")
                direction = e.get("direction")
                if dist is not None and direction is not None:
                    lines.append(f"  {e['description']} [{e['id']}] — {dist} ft {direction}")
                else:
                    lines.append(f"  {e['description']} [{e['id']}]")

        walls = combat_aw.get("walls", [])
        if walls:
            lines.append("\n" + _("Walls:"))
            for w in walls:
                lines.append(f"  {w}")

        if recent_events:
            lines.append("")
            lines.append(_("What happened:"))
            for event_text in recent_events:
                lines.append(f"  • {event_text}")

        return "\n".join(lines)

    def _format_awareness(self, awareness: dict[str, Any], recent_events: list[str] | None = None) -> str:
        """Format world awareness for display to the player."""
        t = awareness["time"]
        lines = [
            "\n--- "
            + _("Your turn (HP: {hp}/{max_hp}, time: {hour}:00, day {day})").format(
                hp=self.current_hp, max_hp=self.max_hp, hour=f"{t['hour']:02d}", day=t["day"]
            )
            + " ---"
        ]

        if recent_events:
            lines.append("")
            lines.append(_("What happened:"))
            for event_text in recent_events:
                lines.append(f"  • {event_text}")

        return "\n".join(lines)

    def to_save_data(self) -> dict[str, Any]:
        """Serialize mutable player state for saving."""
        return {
            "region_id": self.region_id,
            "current_hp": self.current_hp,
            "gold": self.gold,
        }

    def load_save_data(self, data: dict[str, Any]) -> None:
        """Restore mutable state from a save."""
        self.region_id = str(data.get("region_id", self.region_id))
        self.current_hp = int(data.get("current_hp", self.current_hp))
        self.gold = int(data.get("gold", self.gold))
