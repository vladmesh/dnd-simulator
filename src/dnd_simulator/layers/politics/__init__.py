"""Politics layer — nations, diplomacy, warfare, economy, faction relations.

Organized into submodules: diplomacy (treaties, wars), warfare (conquest, military),
economy (income, trade, upkeep). Models: Nation, Leader, DiplomaticStatus, LeaderTrait.
"""

from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.politics.models import (
    DiplomaticStatus,
    Leader,
    LeaderTrait,
    Nation,
)

__all__ = [
    "DiplomaticStatus",
    "Leader",
    "LeaderTrait",
    "Nation",
    "PoliticsLayer",
]
