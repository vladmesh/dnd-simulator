"""Data models for the politics layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# FactionRelation moved to core/models.py — re-export for backward compatibility
from dnd_simulator.core.models import FactionRelation as FactionRelation


class LeaderTrait(Enum):
    """Leader personality — affects nation behavior."""

    MILITARIST = "militarist"
    MERCHANT = "merchant"
    DIPLOMAT = "diplomat"


class DiplomaticStatus(Enum):
    """Relationship between two nations."""

    PEACE = "peace"
    WAR = "war"
    TRADE_AGREEMENT = "trade_agreement"
    ALLIANCE = "alliance"


@dataclass
class Leader:
    """A nation's ruler.

    Mutable on purpose: the politics tick ages the leader in place.
    """

    name: str
    age: int
    trait: LeaderTrait


@dataclass
class Nation:
    """A political entity controlling regions.

    Mutable on purpose: the politics tick drifts stability, wealth and military and replaces the leader in place.
    """

    id: str
    name: str
    regions: list[str]
    wealth: float = 50.0
    military: float = 50.0
    stability: float = 70.0
    leader: Leader | None = None
