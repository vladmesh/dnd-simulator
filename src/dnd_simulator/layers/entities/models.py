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

    def on_tick(self, hour: int) -> None:
        """Update activity based on daily schedule."""
        for entry in self.schedule:
            if hour_in_range(hour, entry.start_hour, entry.end_hour):
                self.activity = entry.activity
                self.location_label = entry.location_label
                return
        self.activity = NpcActivity.IDLE
        self.location_label = "wandering"


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
