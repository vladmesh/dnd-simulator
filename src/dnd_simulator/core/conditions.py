"""D&D 5e Conditions — status effects that modify creature capabilities."""

from __future__ import annotations

from enum import Enum


class Condition(Enum):
    """Standard D&D 5e conditions."""

    BLINDED = "blinded"
    CHARMED = "charmed"
    DEAFENED = "deafened"
    FRIGHTENED = "frightened"
    GRAPPLED = "grappled"
    INCAPACITATED = "incapacitated"
    INVISIBLE = "invisible"
    PARALYZED = "paralyzed"
    PETRIFIED = "petrified"
    POISONED = "poisoned"
    PRONE = "prone"
    RESTRAINED = "restrained"
    STUNNED = "stunned"
    UNCONSCIOUS = "unconscious"
    BLESSED = "blessed"
    DODGING = "dodging"


# Mapping: Condition → remaining rounds (int) or permanent (None).
ConditionsMap = dict[Condition, int | None]
