"""Monster template and encounter table models."""

from __future__ import annotations

from dataclasses import dataclass

from dnd_simulator.core.character import AbilityScores, Attack, Creature
from dnd_simulator.core.models import TimeOfDay


@dataclass(frozen=True)
class MonsterTemplate:
    """Blueprint for spawning monster Creatures. Not an Entity — just data."""

    id: str
    name: str
    hp: int
    ac: int
    speed: int
    ability_scores: AbilityScores
    attacks: tuple[Attack, ...]
    cr: float
    faction_id: str = ""
    description: str = ""

    def spawn(self, location_id: str, instance_id: str) -> Creature:
        """Create a temporary Creature from this template."""
        from dnd_simulator.rules.leveling import xp_for_cr

        return Creature(
            id=instance_id,
            name=self.name,
            location_id=location_id,
            temporary=True,
            faction_id=self.faction_id,
            ability_scores=AbilityScores.from_dict(self.ability_scores.to_dict()),
            max_hp=self.hp,
            current_hp=self.hp,
            ac=self.ac,
            speed=self.speed,
            attacks=self.attacks,
            xp_value=xp_for_cr(self.cr),
        )


@dataclass(frozen=True)
class EncounterEntry:
    """One possible monster spawn in an encounter table."""

    template_id: str
    chance: float  # 0.0-1.0
    count_min: int
    count_max: int
    time_of_day: TimeOfDay | None = None  # None == any time; else rolls only in the matching phase
