"""Player character model."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from dnd_simulator.core.character import (
    Ability,
    Character,
    build_awareness,
)

if TYPE_CHECKING:
    from dnd_simulator.core.world import World


@dataclass
class PlayerCharacter(Character):
    """The player's avatar in the world."""

    input_fn: Callable[[str], str] = field(default=input, repr=False)
    output_fn: Callable[[str], object] = field(default=print, repr=False)

    def take_turn(self, world: World) -> None:
        """Show awareness + recent events, prompt for action, execute."""
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
            if cmd == "idle" or cmd == "wait":
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
                    self.output_fn("Использование: attack <цель>")
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

            self.output_fn("Команды: look, status, say <текст>, attack <цель>, idle")

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
            f"Местность: {info.value['terrain']}  |  "
            f"Погода: {weather.value['condition'].replace('_', ' ')}, {weather.value['temperature']}°C"
        )

        others = [e for e in entities.value if e["id"] != self.id]
        if others:
            lines.append("\nСущества:")
            for e in others:
                if "role" in e:
                    lines.append(f"  {e['name']} [{e['id']}] ({e['role']}) — {e['activity']}")
                else:
                    lines.append(f"  {e['name']} [{e['id']}]")

        if conns.value:
            lines.append("\nПути:")
            for c in conns.value:
                lines.append(f"  {c['direction'].upper()} → {c['target_id']}")

        self.output_fn("\n".join(lines))

    def _cmd_status(self) -> None:
        """Show player stats."""
        scores = self.ability_scores
        lines = [
            f"=== {self.name} ===",
            f"HP: {self.current_hp}/{self.max_hp}  |  AC: {self.ac}  |  Золото: {self.gold}",
            f"STR {scores[Ability.STR]}  DEX {scores[Ability.DEX]}  CON {scores[Ability.CON]}"
            f"  INT {scores[Ability.INT]}  WIS {scores[Ability.WIS]}  CHA {scores[Ability.CHA]}",
        ]
        if self.attacks:
            lines.append("Атаки: " + ", ".join(a.name for a in self.attacks))
        self.output_fn("\n".join(lines))

    def _format_awareness(self, awareness: dict[str, Any], recent_events: list[str] | None = None) -> str:
        """Format world awareness for display to the player."""
        t = awareness["time"]
        lines = [f"\n--- Ваш ход (HP: {self.current_hp}/{self.max_hp}, время: {t['hour']:02d}:00, день {t['day']}) ---"]

        if recent_events:
            lines.append("")
            lines.append("Что произошло:")
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
