"""Data models for the entities layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from dnd_simulator.core.character import Character


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
    location_id: str  # resolved location ID (e.g. "silverport_city_smithy")


@dataclass
class Npc(Character):
    """A non-player character with role, personality, and daily routine.

    Defaults to Human Commoner — override via YAML for special NPCs.
    Decision-making is delegated to the brain field (inherited from Creature).
    """

    role: str = ""
    personality: str = ""
    settlement_id: str = ""
    schedule: list[ScheduleEntry] = field(default_factory=list)
    location_override: str | None = None
    conversation_summary: str = ""
    ai_type: str = "rule_based"

    def scheduled_location(self, hour: int) -> str:
        """Compute where this NPC should be at a given hour, from schedule."""
        for entry in self.schedule:
            if hour_in_range(hour, entry.start_hour, entry.end_hour):
                return entry.location_id
        return self.location_id  # fallback to home/default location

    def scheduled_activity(self, hour: int) -> NpcActivity:
        """Compute what this NPC should be doing at a given hour."""
        for entry in self.schedule:
            if hour_in_range(hour, entry.start_hour, entry.end_hour):
                return entry.activity
        return NpcActivity.IDLE

    def current_location(self, hour: int) -> str:
        """Where the NPC actually is: override if set, else schedule."""
        if self.location_override is not None:
            return self.location_override
        return self.scheduled_location(hour)

    def get_npc_data(self) -> dict[str, str]:
        """Return NPC metadata for LLM prompts."""
        return {
            "name": self.name,
            "role": self.role,
            "personality": self.personality,
            "conversation_summary": self.conversation_summary,
        }


# Default schedules by role — uses relative location labels.
# At NPC creation, these are resolved to "{settlement_id}_{label}" IDs.
DEFAULT_SCHEDULE_TEMPLATES: dict[str, list[tuple[int, int, NpcActivity, str]]] = {
    "blacksmith": [
        (21, 7, NpcActivity.SLEEPING, "home"),
        (7, 19, NpcActivity.WORKING, "smithy"),
        (19, 21, NpcActivity.IDLE, "tavern"),
    ],
    "tavern_keeper": [
        (3, 10, NpcActivity.SLEEPING, "home"),
        (10, 3, NpcActivity.WORKING, "tavern"),
    ],
    "guard": [
        (22, 6, NpcActivity.SLEEPING, "barracks"),
        (6, 22, NpcActivity.WORKING, "patrol"),
    ],
    "merchant": [
        (22, 7, NpcActivity.SLEEPING, "home"),
        (7, 18, NpcActivity.WORKING, "market"),
        (18, 22, NpcActivity.IDLE, "tavern"),
    ],
    "farmer": [
        (20, 5, NpcActivity.SLEEPING, "home"),
        (5, 18, NpcActivity.WORKING, "fields"),
        (18, 20, NpcActivity.IDLE, "home"),
    ],
}


def resolve_schedule(role: str, settlement_id: str) -> list[ScheduleEntry]:
    """Build a schedule from a role template, resolving relative location labels."""
    template = DEFAULT_SCHEDULE_TEMPLATES.get(role)
    if not template:
        return []
    return [
        ScheduleEntry(
            start_hour=start,
            end_hour=end,
            activity=activity,
            location_id=f"{settlement_id}_{label}" if settlement_id else label,
        )
        for start, end, activity, label in template
    ]


def hour_in_range(hour: int, start: int, end: int) -> bool:
    """Check if hour falls within [start, end), handling midnight wrap."""
    if start <= end:
        return start <= hour < end
    else:
        return hour >= start or hour < end
