"""Turn budget — tracks available resources within a single turn."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ActionCost:
    """Cost of a single action in budget terms."""

    actions: int = 0
    bonus_actions: int = 0
    movement_ft: int = 0
    reaction: int = 0


@dataclass
class TurnBudget:
    """Resources available during a creature's turn.

    All fields are ints (not bools) — some features grant extra uses.
    Round creates this at the start of each turn from creature stats + rules.
    """

    actions: int = 1
    bonus_actions: int = 1
    movement_remaining: int = 30
    reaction: int = 1

    @property
    def turn_over(self) -> bool:
        """True if no meaningful resources remain."""
        return self.actions <= 0 and self.bonus_actions <= 0 and self.movement_remaining <= 0

    def can_afford(self, cost: ActionCost) -> bool:
        """Check if the budget can cover the given cost."""
        return (
            self.actions >= cost.actions
            and self.bonus_actions >= cost.bonus_actions
            and self.movement_remaining >= cost.movement_ft
            and self.reaction >= cost.reaction
        )

    def consume(self, cost: ActionCost) -> None:
        """Deduct cost from budget. Raises ValueError if insufficient."""
        if not self.can_afford(cost):
            raise ValueError(
                f"Insufficient budget: need {cost}, have "
                f"actions={self.actions}, bonus={self.bonus_actions}, "
                f"move={self.movement_remaining}, reaction={self.reaction}"
            )
        self.actions -= cost.actions
        self.bonus_actions -= cost.bonus_actions
        self.movement_remaining -= cost.movement_ft
        self.reaction -= cost.reaction

    def refund(self, cost: ActionCost) -> None:
        """Return cost to budget after a failed action."""
        self.actions += cost.actions
        self.bonus_actions += cost.bonus_actions
        self.movement_remaining += cost.movement_ft
        self.reaction += cost.reaction
