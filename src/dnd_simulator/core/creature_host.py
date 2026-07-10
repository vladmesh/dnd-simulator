"""Protocol for the layer that hosts entities/creatures and drives combat.

The `Round` orchestrator needs access to entity lookup, awareness building,
combat state, and activation — all provided by `EntitiesLayer`. This Protocol
isolates `Round` from the concrete `EntitiesLayer` type, keeping `round.py`
layer-agnostic and `core/` free of upward imports.

Any object implementing these methods structurally satisfies the protocol;
`EntitiesLayer` does so by virtue of its public API.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from dnd_simulator.core.awareness import (
        CombatAwareness,
        EquippedInfo,
        ItemInfo,
        MerchantInfo,
        PeacefulAwareness,
        PerceivedEvent,
    )
    from dnd_simulator.core.character import Character, Creature, Entity
    from dnd_simulator.core.combat import CombatState
    from dnd_simulator.core.models import EmitFn, GameDateTime, QueryFn
    from dnd_simulator.core.turn_budget import TurnBudget


@runtime_checkable
class CreatureHost(Protocol):
    """Layer-agnostic interface that `Round` uses to orchestrate creature turns."""

    def get_entity(self, entity_id: str) -> Entity | None:
        """Return the entity with the given id, or None."""
        ...

    def get_active_creatures(self) -> list[Creature]:
        """Return all currently active creatures across the world."""
        ...

    def get_merchants_at(self, location_id: str, hour: int) -> list[Character]:
        """Return active merchant Characters at a location at a given in-game hour."""
        ...

    def get_nearest_wake_time(self) -> int | None:
        """Return the earliest timed-intent wake point, or None."""
        ...

    def update_activation(
        self,
        time: GameDateTime,
        query_fn: QueryFn | None = None,
        emit_fn: EmitFn | None = None,
    ) -> None:
        """Refresh active/dormant state based on proximity to player anchors."""
        ...

    def get_combat_locations(self) -> list[str]:
        """Return location ids where an active combat exists."""
        ...

    def get_combat(self, location_id: str) -> CombatState | None:
        """Return the CombatState at a location, or None if no combat is active."""
        ...

    def log_round_start(self, location_id: str, round_number: int) -> None:
        """Append a ROUND_START marker to the location's event log."""
        ...

    def reset_combat_turn_state(self, creature_id: str) -> None:
        """Clear per-turn combat flags (e.g. sneak attack availability) for a creature."""
        ...

    def end_combat_round(self, location_id: str) -> None:
        """Run end-of-round bookkeeping for a location's combat (auto-exit, cleanup)."""
        ...

    def build_awareness(
        self,
        creature: Creature,
        time: GameDateTime,
        query_fn: QueryFn,
    ) -> PeacefulAwareness | CombatAwareness:
        """Build awareness for a creature — combat or peaceful based on state."""
        ...

    def build_peaceful_awareness(
        self,
        creature: Creature,
        time: GameDateTime,
        query_fn: QueryFn,
    ) -> PeacefulAwareness:
        """Build peaceful awareness explicitly (used on peaceful turns)."""
        ...

    def build_available_items(self, creature: Creature) -> list[ItemInfo]:
        """Build the creature's available-items list for awareness."""
        ...

    def build_equipped(self, creature: Creature) -> list[EquippedInfo]:
        """Build the creature's equipped-items list for awareness."""
        ...

    def compute_reachable(
        self, creature: Creature, combat_state: CombatState | None, budget: TurnBudget
    ) -> frozenset[tuple[int, int]]:
        """Compute reachable battle-map cells for the current turn-taker."""
        ...

    def build_merchants(self, creature: Creature, hour: int) -> list[MerchantInfo]:
        """Build merchant info for merchant NPCs at the creature's location."""
        ...

    def get_perceived_events(self, creature: Creature) -> list[PerceivedEvent]:
        """Return new events perceivable by this creature since last check."""
        ...
