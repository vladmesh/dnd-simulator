"""Data models for the settlements layer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SettlementType(Enum):
    """Types of settlement."""

    VILLAGE = "village"
    TOWN = "town"
    CITY = "city"


@dataclass
class Settlement:
    """A settlement within a region."""

    id: str
    name: str
    region_id: str
    type: SettlementType
    population: int = 100
    prosperity: float = 50.0
    defenses: float = 30.0
