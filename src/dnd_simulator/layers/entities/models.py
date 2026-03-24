"""Data models for the entities layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dnd_simulator.core.character import Character
from dnd_simulator.core.tags import NpcTag, has_tag
from dnd_simulator.i18n import _


@dataclass
class NpcMemory:
    """Structured memory for an NPC — readable by both LLM and RuleBrain.

    Fields:
        tags: structured emotional/relational tags (e.g. "angry", "hates:orc_chief")
        recent: summarized recent events
        inner_state: current emotional/mental state
        current_conversation: summary of ongoing conversation
    """

    tags: list[str] = field(default_factory=list)
    recent: str = ""
    inner_state: str = ""
    current_conversation: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tags": list(self.tags),
            "recent": self.recent,
            "inner_state": self.inner_state,
            "current_conversation": self.current_conversation,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NpcMemory:
        return cls(
            tags=list(data.get("tags", [])),
            recent=str(data.get("recent", "")),
            inner_state=str(data.get("inner_state", "")),
            current_conversation=str(data.get("current_conversation", "")),
        )


class NpcActivity(Enum):
    """What an NPC is currently doing."""

    SLEEPING = "sleeping"
    WORKING = "working"
    IDLE = "idle"


@dataclass(frozen=True)
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
    memory: NpcMemory = field(default_factory=NpcMemory)
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

    @property
    def memory_tags(self) -> list[str]:
        return self.memory.tags

    def get_canned_response(self, hour: int) -> str | None:
        """Return a canned dialogue line based on role, activity, and mood."""
        activity = self.scheduled_activity(hour)
        return canned_line(self.role, activity, self.memory.tags)

    def get_npc_data(self) -> dict[str, Any]:
        """Return NPC metadata for LLM prompts."""
        return {
            "name": self.name,
            "role": self.role,
            "personality": self.personality,
            "memory": self.memory.to_dict(),
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


def resolve_schedule(role: str, settlement_id: str, known_locations: set[str] | None = None) -> list[ScheduleEntry]:
    """Build a schedule from a role template, resolving relative location labels.

    If *known_locations* is provided, every resolved location_id must exist in the
    set — entries pointing at non-existent locations are silently dropped.
    """
    template = DEFAULT_SCHEDULE_TEMPLATES.get(role)
    if not template:
        return []
    entries: list[ScheduleEntry] = []
    for start, end, activity, label in template:
        loc = f"{settlement_id}_{label}" if settlement_id else label
        if known_locations is not None and loc not in known_locations:
            continue
        entries.append(ScheduleEntry(start_hour=start, end_hour=end, activity=activity, location_id=loc))
    return entries


# Flavor text: what the NPC looks like they're doing.
# Keyed by (role, activity). Falls back to activity-only, then generic.
ACTIVITY_FLAVOR: dict[tuple[str, NpcActivity], str] = {
    # Blacksmith
    ("blacksmith", NpcActivity.WORKING): "hammering at the anvil",
    ("blacksmith", NpcActivity.IDLE): "sitting with a mug of ale",
    ("blacksmith", NpcActivity.SLEEPING): "sleeping",
    # Tavern keeper
    ("tavern_keeper", NpcActivity.WORKING): "wiping down the bar",
    ("tavern_keeper", NpcActivity.IDLE): "resting behind the counter",
    ("tavern_keeper", NpcActivity.SLEEPING): "sleeping",
    # Guard
    ("guard", NpcActivity.WORKING): "standing watch",
    ("guard", NpcActivity.IDLE): "leaning against the wall",
    ("guard", NpcActivity.SLEEPING): "sleeping in the barracks",
    # Merchant
    ("merchant", NpcActivity.WORKING): "hawking wares to passersby",
    ("merchant", NpcActivity.IDLE): "counting coins at a table",
    ("merchant", NpcActivity.SLEEPING): "sleeping",
    # Farmer
    ("farmer", NpcActivity.WORKING): "tending the fields",
    ("farmer", NpcActivity.IDLE): "resting on the porch",
    ("farmer", NpcActivity.SLEEPING): "sleeping",
}

# Generic fallbacks by activity (when role has no specific entry)
_ACTIVITY_GENERIC: dict[NpcActivity, str] = {
    NpcActivity.WORKING: "busy at work",
    NpcActivity.IDLE: "standing around",
    NpcActivity.SLEEPING: "sleeping",
}


def activity_flavor(role: str, activity: NpcActivity) -> str:
    """Get a short flavor description of what an NPC is doing."""
    return ACTIVITY_FLAVOR.get((role, activity), _ACTIVITY_GENERIC.get(activity, activity.value))


# Canned dialogue for RuleBrain NPCs — response when someone talks to them.
# Priority: mood tag override > (role, activity) > activity-only > generic fallback.
# Future: add relationship overrides (hates:player → hostile line, trusts:player → friendly).
CANNED_DIALOGUE: dict[tuple[str, NpcActivity], str] = {
    # Blacksmith
    ("blacksmith", NpcActivity.WORKING): _("Need something forged?"),
    ("blacksmith", NpcActivity.IDLE): _("Hm? Oh, I'm off duty."),
    # Tavern keeper
    ("tavern_keeper", NpcActivity.WORKING): _("What'll it be?"),
    ("tavern_keeper", NpcActivity.IDLE): _("Kitchen's closed. Come back later."),
    # Guard
    ("guard", NpcActivity.WORKING): _("Move along, citizen."),
    ("guard", NpcActivity.IDLE): _("Quiet night, eh?"),
    # Merchant
    ("merchant", NpcActivity.WORKING): _("Looking to buy something?"),
    ("merchant", NpcActivity.IDLE): _("Shop's closed. Try tomorrow."),
    # Farmer
    ("farmer", NpcActivity.WORKING): _("Can't talk, crops won't tend themselves."),
    ("farmer", NpcActivity.IDLE): _("Fine evening, isn't it?"),
}

_DIALOGUE_GENERIC: dict[NpcActivity, str] = {
    NpcActivity.WORKING: _("I'm busy."),
    NpcActivity.IDLE: _("Hm?"),
    NpcActivity.SLEEPING: _("Zzz..."),
}

# Mood overrides — if NPC has this tag, use this line regardless of role/activity.
MOOD_DIALOGUE: dict[str, str] = {
    NpcTag.ANGRY: _("Leave me alone!"),
    NpcTag.SCARED: _("Shh... Something's not right."),
    NpcTag.GRIEVING: _("I... I can't talk right now."),
    NpcTag.SUSPICIOUS: _("What do you want?"),
}


def canned_line(role: str, activity: NpcActivity, tags: list[str]) -> str:
    """Pick a canned dialogue line. Mood overrides role+activity."""
    for tag, line in MOOD_DIALOGUE.items():
        if has_tag(tags, tag):
            return line
    return CANNED_DIALOGUE.get((role, activity), _DIALOGUE_GENERIC.get(activity, "..."))


def hour_in_range(hour: int, start: int, end: int) -> bool:
    """Check if hour falls within [start, end), handling midnight wrap."""
    if start <= end:
        return start <= hour < end
    else:
        return hour >= start or hour < end
