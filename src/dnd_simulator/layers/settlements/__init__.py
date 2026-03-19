"""Settlements layer — cities, towns, and villages."""

from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.layers.settlements.models import Settlement, SettlementType

__all__ = ["Settlement", "SettlementType", "SettlementsLayer"]
