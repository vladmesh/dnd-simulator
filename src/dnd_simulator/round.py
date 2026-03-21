"""Round orchestrator — runs all active creatures uniformly each round.

Multi-action turn loop: each creature's turn is a loop of
choose_action → budget check → execute → rebuild awareness → repeat
until the brain returns end_turn or budget is exhausted.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from dnd_simulator.core.action import SKIP, Action
from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import EmitFn, Event, GameDateTime, QueryFn, TimeDelta
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.actions import action_cost, get_num_actions, get_num_bonus_actions

logger = logging.getLogger("dnd_simulator.round")

# Callback fired after each individual action within a turn.
# (creature, action, budget) — used by WS to send action_result.
OnActionCallback = Callable[[Creature, Action, TurnBudget], None]


@dataclass
class RoundResult:
    """Result of a single round."""

    events: list[Event] = field(default_factory=list)
    should_stop: bool = False


def get_entities_layer(world: World) -> EntitiesLayer:
    """Find the entities layer in the world."""
    for layer in world.layers:
        if isinstance(layer, EntitiesLayer):
            return layer
    raise RuntimeError("World has no EntitiesLayer")


class Round:
    """Orchestrates one game round: all active creatures act, then time advances.

    Each creature's turn is a multi-action loop: the brain is called repeatedly
    until it returns end_turn or the turn budget is exhausted.
    """

    def __init__(self, world: World, entities_layer: EntitiesLayer) -> None:
        self._world = world
        self._entities = entities_layer
        self._stop_flag = False
        self._on_round_end: Callable[[RoundResult], None] | None = None
        self._on_action: OnActionCallback | None = None

    def stop(self) -> None:
        """Signal the run_loop to exit after current round completes."""
        self._stop_flag = True

    def set_on_round_end(self, callback: Callable[[RoundResult], None]) -> None:
        """Set callback invoked after each round with the round result."""
        self._on_round_end = callback

    def set_on_action(self, callback: OnActionCallback) -> None:
        """Set callback invoked after each action within a turn."""
        self._on_action = callback

    def run_creature_turn(
        self,
        creature: Creature,
        time: GameDateTime,
        query_fn: QueryFn,
        emit_fn: EmitFn,
    ) -> list[Action]:
        """Run one creature's full turn as a multi-action loop.

        Returns the list of actions taken (excluding end_turn).
        """
        if creature.brain is None:
            return []

        budget = TurnBudget(
            actions=get_num_actions(creature),
            bonus_actions=get_num_bonus_actions(creature),
            movement_remaining=creature.speed,
            reaction=1,
        )
        actions: list[Action] = []

        while True:
            awareness = self._entities.build_awareness(creature, time, query_fn)
            awareness.turn_budget = budget
            events = self._entities.get_perceived_events(creature)

            action = creature.brain.choose_action(creature, awareness, events)

            if action.name == "end_turn":
                break

            # Enforce budget
            cost = action_cost(action)
            if not budget.can_afford(cost):
                logger.warning(
                    "[Round] %s tried %s but insufficient budget, forcing end_turn",
                    creature.name,
                    action.name,
                )
                break

            budget.consume(cost)
            creature.execute_action(action, emit_fn)
            actions.append(action)

            if self._on_action:
                self._on_action(creature, action, budget)

            # Special: wait action advances time immediately
            if action.name == "wait":
                self._handle_wait(action)

            # If budget exhausted, end turn automatically
            if budget.turn_over:
                break

        return actions

    def check_reactions(
        self,
        trigger_event: Event,
        candidates: list[Creature],
        time: GameDateTime,
        query_fn: QueryFn,
        emit_fn: EmitFn,
    ) -> list[Action]:
        """Check if any candidates want to use a reaction to the trigger event.

        This is the interrupt mini-turn: each candidate with reaction budget gets
        a choose_action call with available reactions + skip. If not skip, execute.

        Returns list of reaction actions taken.

        Note: actual reaction trigger points (opportunity attacks during move,
        counterspell on cast, etc.) are not wired yet — this is the skeleton
        that will be called from the appropriate places in run_creature_turn.
        """
        reactions: list[Action] = []

        for creature in candidates:
            if creature.brain is None or not creature.is_alive:
                continue

            # Build awareness for the reacting creature
            awareness = self._entities.build_awareness(creature, time, query_fn)
            # TODO: set awareness.available_actions to reaction list + skip
            # For now, just ask the brain
            perceived = self._entities.get_perceived_events(creature)

            action = creature.brain.choose_action(creature, awareness, perceived)

            if action.name == "skip" or action == SKIP:
                continue

            creature.execute_action(action, emit_fn)
            reactions.append(action)

        return reactions

    def run_round(self) -> RoundResult:
        """Execute one round: combat turns (initiative order), then peaceful turns, then advance time."""
        query_fn = self._world._make_query_fn("entities")
        emit_fn = self._world._make_emit_fn("entities")
        time = self._world.time

        # Combat rounds: iterate by initiative order per location
        for location_id in list(self._entities.get_combat_locations()):
            combat = self._entities.get_combat(location_id)
            if not combat:
                continue
            for entity_id in list(combat.turn_order):
                entity = self._entities.get_entity(entity_id)
                if isinstance(entity, Creature) and entity.is_alive and entity.active and entity.in_combat:
                    entity.is_dodging = False  # dodge lasts until start of next turn
                    self.run_creature_turn(entity, time, query_fn, emit_fn)
            # End of round — check for combat exit
            self._entities.end_combat_round(location_id)

        # Peaceful turns: creatures not in combat
        for creature in self._entities.get_active_creatures():
            if creature.in_combat or not creature.is_alive or not creature.active:
                continue
            self.run_creature_turn(creature, time, query_fn, emit_fn)

        # Advance time by one round (6 seconds)
        tick_events = self._world.advance_time(TimeDelta.from_rounds(1))

        return RoundResult(events=tick_events)

    def run_loop(self) -> None:
        """Run rounds until no active creatures remain or stop() is called."""
        while not self._stop_flag:
            active = self._entities.get_active_creatures()
            if not active:
                break
            result = self.run_round()
            if self._on_round_end:
                self._on_round_end(result)
            if result.should_stop:
                break

    def _handle_wait(self, action: Action) -> None:
        """Handle a 'wait' action by advancing time."""
        raw = action.params.get("hours", 1)
        hours = int(str(raw))
        if hours > 0:
            self._world.advance_time(TimeDelta.from_hours(hours))
