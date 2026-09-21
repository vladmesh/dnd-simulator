"""Data models for the entities layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from dnd_simulator.core.brain import BrainType
from dnd_simulator.core.character import Character, NpcRole
from dnd_simulator.core.inner_self import InnerSelf, Mood
from dnd_simulator.core.intent import TravelIntent
from dnd_simulator.i18n import _


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

    role: NpcRole = NpcRole.COMMONER
    personality: str = ""
    description: str = ""
    settlement_id: str = ""
    schedule: list[ScheduleEntry] = field(default_factory=list)
    location_override: str | None = None
    inner_self: InnerSelf | None = field(default_factory=InnerSelf)
    ai_type: BrainType = BrainType.RULE_BASED

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
        """Where the NPC actually is: on the road where the journey has reached, else override, else schedule.

        A pending journey beats both: a fleeing NPC's override names its destination,
        and it must not appear there before the journey's arrival boundary.
        """
        if isinstance(self.current_intent, TravelIntent):
            return self.location_id
        if self.location_override is not None:
            return self.location_override
        return self.scheduled_location(hour)

    @property
    def is_merchant(self) -> bool:
        """Whether this NPC is a merchant (derived from role)."""
        return self.role == NpcRole.MERCHANT

    def get_canned_response(self, hour: int) -> str | None:
        """Return a canned dialogue line based on role, activity, and mood."""
        activity = self.scheduled_activity(hour)
        return canned_line(self.role, activity, self.inner_self.mood if self.inner_self else Mood.NEUTRAL)

    def get_npc_data(self) -> dict[str, Any]:
        """Return NPC metadata for LLM prompts."""
        return {
            "name": self.name,
            "role": self.role.value,
            "personality": self.personality,
            "inner_self": self.inner_self.to_dict() if self.inner_self else None,
        }


def resolve_schedule(role: NpcRole, settlement_id: str, known_locations: set[str] | None = None) -> list[ScheduleEntry]:
    """Build a schedule from a role template, resolving relative location labels.

    If *known_locations* is provided, every resolved location_id must exist in the
    set — entries pointing at non-existent locations are silently dropped.
    """
    from dnd_simulator.layers.entities.npc_behaviors import get_schedule_templates

    template = get_schedule_templates().get(role)
    if not template:
        return []
    entries: list[ScheduleEntry] = []
    for start, end, activity, label in template:
        loc = f"{settlement_id}_{label}" if settlement_id else label
        if known_locations is not None and loc not in known_locations:
            continue
        entries.append(ScheduleEntry(start_hour=start, end_hour=end, activity=activity, location_id=loc))
    return entries


def activity_flavor(role: NpcRole, activity: NpcActivity) -> str:
    """Get a short flavor description of what an NPC is doing."""
    from dnd_simulator.layers.entities.npc_behaviors import get_activity_flavor, get_activity_generic

    return get_activity_flavor().get((role, activity), get_activity_generic().get(activity, activity.value))


# Canned dialogue for RuleBrain NPCs — response when someone talks to them.
# Priority: mood override > (role, activity) > activity-only > generic fallback.
CANNED_DIALOGUE: dict[tuple[NpcRole, NpcActivity], str] = {
    # Blacksmith
    (NpcRole.BLACKSMITH, NpcActivity.WORKING): _("Need something forged?"),
    (NpcRole.BLACKSMITH, NpcActivity.IDLE): _("Hm? Oh, I'm off duty."),
    # Tavern keeper
    (NpcRole.TAVERN_KEEPER, NpcActivity.WORKING): _("What'll it be?"),
    (NpcRole.TAVERN_KEEPER, NpcActivity.IDLE): _("Kitchen's closed. Come back later."),
    # Guard
    (NpcRole.GUARD, NpcActivity.WORKING): _("Move along, citizen."),
    (NpcRole.GUARD, NpcActivity.IDLE): _("Quiet night, eh?"),
    # Merchant
    (NpcRole.MERCHANT, NpcActivity.WORKING): _("Looking to buy something?"),
    (NpcRole.MERCHANT, NpcActivity.IDLE): _("Shop's closed. Try tomorrow."),
    # Farmer
    (NpcRole.FARMER, NpcActivity.WORKING): _("Can't talk, crops won't tend themselves."),
    (NpcRole.FARMER, NpcActivity.IDLE): _("Fine evening, isn't it?"),
}

_DIALOGUE_GENERIC: dict[NpcActivity, str] = {
    NpcActivity.WORKING: _("I'm busy."),
    NpcActivity.IDLE: _("Hm?"),
    NpcActivity.SLEEPING: _("Zzz..."),
}

# Mood overrides — if NPC has this tag, use this line regardless of role/activity.
MOOD_DIALOGUE: dict[Mood, str] = {
    Mood.ANGRY: _("Leave me alone!"),
    Mood.SCARED: _("Shh... Something's not right."),
    Mood.GRIEVING: _("I... I can't talk right now."),
    Mood.SUSPICIOUS: _("What do you want?"),
}


def canned_line(role: NpcRole, activity: NpcActivity, mood: Mood = Mood.NEUTRAL) -> str:
    """Pick a canned dialogue line. Mood overrides role+activity."""
    if mood in MOOD_DIALOGUE:
        return MOOD_DIALOGUE[mood]
    return CANNED_DIALOGUE.get((role, activity), _DIALOGUE_GENERIC.get(activity, "..."))


def hour_in_range(hour: int, start: int, end: int) -> bool:
    """Check if hour falls within [start, end), handling midnight wrap."""
    if start <= end:
        return start <= hour < end
    else:
        return hour >= start or hour < end
