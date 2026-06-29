"""Pure lair-depletion rule.

No state, no I/O — takes lair data and an injected roll, returns a bool.
The caller (EcologyLayer) is responsible for generating the roll and applying
the state transition.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from dnd_simulator.core.lair import Lair


def should_deplete(lair: Lair, roll: float) -> bool:
    """Return True if the lair should transition to DEPLETED after a visit.

    Rules:
    - Cored lair: depletes when and only when the core/boss is dead.
    - Coreless lair: depletes when wiped (no survivors) AND depletion_chance > 0
      AND roll < depletion_chance.
    - alive_members=None means full roster (not wiped) — never depletes via chance.
    """
    if lair.core is not None:
        return not lair.core_alive

    if lair.alive_members is None:
        return False

    return len(lair.alive_members) == 0 and lair.depletion_chance > 0.0 and roll < lair.depletion_chance
