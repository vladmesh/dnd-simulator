"""Data models for the entities layer."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from dnd_simulator.core.character import Character, build_awareness, build_combat_awareness
from dnd_simulator.llm.client import LlmClient, ToolCall
from dnd_simulator.llm.prompts import build_npc_combat_prompt, build_npc_system_prompt
from dnd_simulator.llm.tools import build_npc_combat_tools, build_npc_tools

logger = logging.getLogger("dnd_simulator.npc")

if TYPE_CHECKING:
    from dnd_simulator.core.world import World

_MAX_RETRIES = 3


class NpcActivity(Enum):
    """What an NPC is currently doing."""

    SLEEPING = "sleeping"
    WORKING = "working"
    IDLE = "idle"


@dataclass
class ScheduleEntry:
    """A block of time in an NPC's daily routine."""

    start_hour: int  # 0-23
    end_hour: int  # 0-23, wraps around midnight if start > end
    activity: NpcActivity
    location_label: str  # "smithy", "home", "tavern", "patrol"


@dataclass
class Npc(Character):
    """A non-player character with role, personality, and daily routine.

    Defaults to Human Commoner — override via YAML for special NPCs.
    """

    role: str = ""
    personality: str = ""
    settlement_id: str = ""
    schedule: list[ScheduleEntry] = field(default_factory=list)
    activity: NpcActivity = NpcActivity.IDLE
    location_label: str = "home"
    conversation_summary: str = ""
    llm: LlmClient | None = field(default=None, repr=False)

    def on_tick(self, hour: int) -> None:
        """Update activity based on daily schedule."""
        for entry in self.schedule:
            if hour_in_range(hour, entry.start_hour, entry.end_hour):
                self.activity = entry.activity
                self.location_label = entry.location_label
                return
        self.activity = NpcActivity.IDLE
        self.location_label = "wandering"

    def _build_npc_data(self) -> dict[str, str]:
        return {
            "name": self.name,
            "role": self.role,
            "personality": self.personality,
            "activity": self.activity.value,
            "location_label": self.location_label,
            "conversation_summary": self.conversation_summary,
        }

    def take_turn(self, world: World) -> None:
        """Decide what to do this turn and execute it."""
        if self.llm is None:
            return

        from dnd_simulator.core.models import Query

        logger.info("[NPC:%s] === начинает ход (%s) ===", self.name, "бой" if self.in_combat else "мир")

        if self.in_combat:
            combat_awareness = build_combat_awareness(world, self)
            system_prompt = build_npc_combat_prompt(self._build_npc_data(), combat_awareness)
            tools = build_npc_combat_tools()
            retry_hint = "Ты должен выбрать действие: attack, dodge, flee или idle."
        else:
            awareness = build_awareness(world, self.region_id)
            # Build list of nearby entities with IDs so LLM knows valid targets
            entities_answer = world.query_layer(
                "entities", Query(question="entities_in_region", params={"region_id": self.region_id})
            )
            nearby: list[dict[str, str]] = []
            for e in entities_answer.value:
                if e["id"] != self.id:
                    desc = self.perceive_by_id(e["id"], world)
                    nearby.append({"id": str(e["id"]), "description": desc})
            system_prompt = build_npc_system_prompt(self._build_npc_data(), awareness, nearby)
            tools = build_npc_tools()
            retry_hint = "Ты должен выбрать действие: say, attack или idle."

        # Get recent events perceived by this NPC
        log_answer = world.query_layer("entities", Query(question="perceived_log", params={"entity_id": self.id}))
        recent_events: list[str] = log_answer.value if log_answer.value else []

        turn_prompt = "Твой ход. Выбери действие."
        if recent_events:
            events_text = "\n".join(f"- {e}" for e in recent_events)
            turn_prompt = f"Что произошло с твоего прошлого хода:\n{events_text}\n\nТвой ход. Выбери действие."

        messages: list[dict[str, object]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": turn_prompt},
        ]

        for _ in range(_MAX_RETRIES):
            response = self.llm.generate_with_tools(messages, tools)
            if response.is_tool_call:
                assert response.tool_call is not None
                success = self._execute_action(response.tool_call, world)
                if success:
                    return
                # Action failed (e.g. invalid target) — tell LLM and retry
                messages.append({"role": "assistant", "content": f"[tool: {response.tool_call.name}]"})
                messages.append({"role": "user", "content": "Действие не удалось. Выбери другое."})
                continue
            # No tool call — ask LLM to retry
            messages.append({"role": "assistant", "content": response.text or ""})
            messages.append({"role": "user", "content": retry_hint})

    def _execute_action(self, action: ToolCall, world: World) -> bool:
        """Execute a tool call against the world. Returns True if action succeeded."""
        from dnd_simulator.core.models import Event, EventType

        if action.name == "idle":
            logger.info("[NPC:%s] → idle", self.name)
            return True
        if action.name == "say":
            world.handle_event(
                Event(
                    event_type=EventType.ENTITY_SAY,
                    source_layer="entities",
                    data={"entity_id": self.id, "text": action.arguments.get("text", "")},
                )
            )
            return True
        if action.name == "attack":
            result = world.handle_event(
                Event(
                    event_type=EventType.ENTITY_ATTACK,
                    source_layer="entities",
                    data={
                        "attacker_id": self.id,
                        "target_id": action.arguments.get("target_id", ""),
                    },
                )
            )
            return result.success
        if action.name == "dodge":
            logger.info("[NPC:%s] → dodge", self.name)
            world.handle_event(
                Event(
                    event_type=EventType.ENTITY_DODGE,
                    source_layer="entities",
                    data={
                        "entity_id": self.id,
                        "description": action.arguments.get("description", ""),
                    },
                )
            )
            return True
        if action.name == "flee":
            logger.info("[NPC:%s] → flee", self.name)
            world.handle_event(
                Event(
                    event_type=EventType.ENTITY_FLEE,
                    source_layer="entities",
                    data={
                        "entity_id": self.id,
                        "description": action.arguments.get("description", ""),
                    },
                )
            )
            return True
        return False


# Default schedules by role — keeps YAML clean.
DEFAULT_SCHEDULES: dict[str, list[ScheduleEntry]] = {
    "blacksmith": [
        ScheduleEntry(21, 7, NpcActivity.SLEEPING, "home"),
        ScheduleEntry(7, 19, NpcActivity.WORKING, "smithy"),
        ScheduleEntry(19, 21, NpcActivity.IDLE, "tavern"),
    ],
    "tavern_keeper": [
        ScheduleEntry(3, 10, NpcActivity.SLEEPING, "home"),
        ScheduleEntry(10, 3, NpcActivity.WORKING, "tavern"),
    ],
    "guard": [
        ScheduleEntry(22, 6, NpcActivity.SLEEPING, "barracks"),
        ScheduleEntry(6, 22, NpcActivity.WORKING, "patrol"),
    ],
    "merchant": [
        ScheduleEntry(22, 7, NpcActivity.SLEEPING, "home"),
        ScheduleEntry(7, 18, NpcActivity.WORKING, "market"),
        ScheduleEntry(18, 22, NpcActivity.IDLE, "tavern"),
    ],
    "farmer": [
        ScheduleEntry(20, 5, NpcActivity.SLEEPING, "home"),
        ScheduleEntry(5, 18, NpcActivity.WORKING, "fields"),
        ScheduleEntry(18, 20, NpcActivity.IDLE, "home"),
    ],
}


def hour_in_range(hour: int, start: int, end: int) -> bool:
    """Check if hour falls within [start, end), handling midnight wrap."""
    if start <= end:
        return start <= hour < end
    else:
        return hour >= start or hour < end
