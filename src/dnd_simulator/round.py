"""Round orchestrator — runs all active creatures each round.

Combat turns use a multi-action loop with D&D 5e turn budget enforcement.
Peaceful turns have no budget — meaningful actions auto-end the turn,
while queries (look/status/map) loop without ending.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from dnd_simulator.core.action import SKIP, Action
from dnd_simulator.core.awareness import PerceivedEvent
from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import EmitFn, Event, EventType, GameDateTime, QueryFn, TimeDelta
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.actions import (
    DASH_ACTION_COST,
    action_cost,
    ends_peaceful_turn,
    get_num_actions,
    get_num_bonus_actions,
)
from dnd_simulator.rules.conditions import effective_speed, is_incapacitated
from dnd_simulator.rules.validation import ActionContext, validate_action

logger = logging.getLogger("dnd_simulator.round")

# Callback fired after each individual action within a turn.
# (creature, action, budget, error) — budget is None for peaceful turns, error is "" on success.
OnActionCallback = Callable[[Creature, Action, TurnBudget | None, str], None]


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

    Combat: multi-action loop with budget (actions, bonus, movement).
    Peaceful: no budget — turn-ending actions auto-end, queries loop.
    """

    def __init__(self, world: World, entities_layer: EntitiesLayer | None = None) -> None:
        self._world = world
        self._entities = entities_layer or get_entities_layer(world)
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

    def get_perceived_events(self, creature: Creature) -> list[PerceivedEvent]:
        """Return perceived events for a creature (delegates to EntitiesLayer)."""
        return self._entities.get_perceived_events(creature)

    def run_creature_turn(
        self,
        creature: Creature,
        time: GameDateTime,
        query_fn: QueryFn,
        emit_fn: EmitFn,
    ) -> list[Action]:
        """Dispatch to combat or peaceful turn based on creature state."""
        if creature.in_combat:
            return self.run_combat_turn(creature, time, query_fn, emit_fn)
        return self.run_peaceful_turn(creature, time, query_fn, emit_fn)

    def run_combat_turn(
        self,
        creature: Creature,
        time: GameDateTime,
        query_fn: QueryFn,
        emit_fn: EmitFn,
    ) -> list[Action]:
        """Run one creature's combat turn as a multi-action loop with budget.

        Returns the list of actions taken (excluding end_turn).
        """
        if creature.brain is None:
            return []

        # Incapacitated creatures (stunned, paralyzed, etc.) skip their turn entirely
        if is_incapacitated(creature.conditions):
            logger.info("[Round] %s is incapacitated, skipping turn", creature.name)
            reasons = sorted(c.value for c in creature.conditions if is_incapacitated({c}))
            emit_fn(
                Event(
                    event_type=EventType.TURN_SKIPPED,
                    source_layer="entities",
                    data={
                        "entity_id": creature.id,
                        "reason": "incapacitated",
                        "conditions": reasons,
                    },
                )
            )
            return []

        speed = effective_speed(creature.speed, creature.conditions)
        if speed != creature.speed:
            logger.debug(
                "[Round] %s speed reduced %d→%d by conditions: %s",
                creature.name,
                creature.speed,
                speed,
                ", ".join(c.value for c in creature.conditions),
            )
        budget = TurnBudget(
            actions=get_num_actions(creature),
            bonus_actions=get_num_bonus_actions(creature),
            movement_remaining=speed,
            reaction=1,
        )
        actions: list[Action] = []
        consecutive_failures = 0

        while True:
            awareness = self._entities.build_awareness(creature, time, query_fn)
            awareness.turn_budget = budget
            events = self._entities.get_perceived_events(creature)

            action = creature.brain.choose_action(creature, awareness, events)

            if action.name == "end_turn":
                break

            # Validate preconditions (alive, active, combat/peaceful mode)
            ctx = ActionContext(is_combat=True, current_turn_entity_id=creature.id)
            validation_error = validate_action(creature, action, ctx)
            if validation_error:
                logger.warning(
                    "[Round] %s action '%s' rejected: %s",
                    creature.name,
                    action.name,
                    validation_error.message,
                )
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    break
                continue

            # Dash is special: costs 1 action, adds speed to movement pool, no world event
            if action.name == "dash":
                if not budget.can_afford(DASH_ACTION_COST):
                    logger.warning("[Round] %s tried dash but no actions left", creature.name)
                    break
                budget.consume(DASH_ACTION_COST)
                budget.movement_remaining += speed
                actions.append(action)
                if self._on_action:
                    self._on_action(creature, action, budget, "")
                continue

            # Enforce budget (check only, consume after success)
            cost = action_cost(action)
            if not budget.can_afford(cost):
                logger.warning(
                    "[Round] %s tried %s but insufficient budget, forcing end_turn",
                    creature.name,
                    action.name,
                )
                break

            result = creature.execute_action(action, emit_fn)

            # Only consume budget if the action actually succeeded
            if result.success:
                budget.consume(cost)
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                if consecutive_failures >= 3:
                    logger.warning(
                        "[Round] %s failed %d actions in a row, ending turn",
                        creature.name,
                        consecutive_failures,
                    )
                    break

            actions.append(action)

            if self._on_action:
                self._on_action(creature, action, budget, result.error)

            # Special: wait action advances time immediately
            if action.name == "wait":
                self._handle_wait(action, creature)

            # If budget exhausted, end turn automatically
            if budget.turn_over:
                break

        return actions

    def run_peaceful_turn(
        self,
        creature: Creature,
        time: GameDateTime,
        query_fn: QueryFn,
        emit_fn: EmitFn,
    ) -> list[Action]:
        """Run one creature's peaceful turn — no budget.

        Turn-ending actions (say, attack, move, etc.) execute and auto-end.
        Queries (idle = look/status/map) execute, fire on_action, and loop.
        Returns the list of actions taken (excluding end_turn).
        """
        if creature.brain is None:
            return []

        actions: list[Action] = []

        while True:
            awareness = self._entities.build_awareness(creature, time, query_fn)
            # No budget in peaceful mode — awareness.turn_budget stays None
            events = self._entities.get_perceived_events(creature)

            action = creature.brain.choose_action(creature, awareness, events)

            if action.name == "end_turn":
                break

            # Validate preconditions (alive, active, combat/peaceful mode)
            ctx = ActionContext(is_combat=False, current_turn_entity_id=creature.id)
            validation_error = validate_action(creature, action, ctx)
            if validation_error:
                logger.warning(
                    "[Round] %s action '%s' rejected: %s",
                    creature.name,
                    action.name,
                    validation_error.message,
                )
                break

            result = creature.execute_action(action, emit_fn)
            actions.append(action)

            if self._on_action:
                self._on_action(creature, action, None, result.error)

            # Special: wait action advances time immediately
            if action.name == "wait":
                self._handle_wait(action, creature)

            # Turn-ending actions auto-end the peaceful turn
            if ends_peaceful_turn(action):
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
        that will be called from the appropriate places in run_combat_turn.
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

            # Validate preconditions
            ctx = ActionContext(is_combat=True, current_turn_entity_id=creature.id)
            validation_error = validate_action(creature, action, ctx)
            if validation_error:
                logger.warning(
                    "[Round] %s reaction '%s' rejected: %s",
                    creature.name,
                    action.name,
                    validation_error.message,
                )
                continue

            reaction_result = creature.execute_action(action, emit_fn)
            if reaction_result.success:
                reactions.append(action)

        return reactions

    def run_round(self) -> RoundResult:
        """Execute one round: combat turns (initiative order), then peaceful turns, then advance time."""
        query_fn = self._world._make_query_fn("entities")
        emit_fn = self._world._make_emit_fn("entities")
        time = self._world.time

        # Activate creatures near players, dormify the rest
        self._entities.update_activation(time)

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

    def run_loop(self, max_rounds: int | None = None) -> None:
        """Run rounds until no active creatures remain or stop() is called."""
        rounds_run = 0
        while not self._stop_flag:
            # Update activation before checking — resolves stale state from previous round
            self._entities.update_activation(self._world.time)
            active = self._entities.get_active_creatures()
            if not active:
                if not self._fast_forward():
                    break
                continue  # re-check active after fast-forward
            result = self.run_round()
            rounds_run += 1
            if self._on_round_end:
                self._on_round_end(result)
            if result.should_stop:
                break
            if max_rounds is not None and rounds_run >= max_rounds:
                break

    def _fast_forward(self) -> bool:
        """Advance time to the nearest wake_at when no creatures are active.

        Returns True if time was advanced (loop should continue), False if
        there's nobody to wake up (loop should exit).
        """
        nearest_wake: int | None = None
        for e in self._entities._entities.values():
            if (
                isinstance(e, Creature)
                and e.wake_at_seconds is not None
                and (nearest_wake is None or e.wake_at_seconds < nearest_wake)
            ):
                nearest_wake = e.wake_at_seconds

        if nearest_wake is None:
            return False

        now = self._world.time.to_total_seconds()
        delta_seconds = nearest_wake - now
        if delta_seconds <= 0:
            # Timer already expired — just run update_activation
            self._entities.update_activation(self._world.time)
            return True

        logger.info("[FastForward] Advancing %d seconds to next wake_at", delta_seconds)
        tick_events = self._world.advance_time(TimeDelta(seconds=delta_seconds))
        self._entities.update_activation(self._world.time)

        if self._on_round_end:
            self._on_round_end(RoundResult(events=tick_events))

        return True

    def _handle_wait(self, action: Action, creature: Creature | None = None) -> None:
        """Handle a 'wait' action — creature goes dormant until wake_at.

        Travel: immediate move + advance (legacy, will be refactored).
        Plain wait: set wake_at, creature becomes dormant. Fast-forward in run_loop
        handles the actual time advancement.
        """
        travel_to = action.params.get("travel_to")
        if travel_to and creature:
            target_id = str(travel_to)
            graph = self._world.location_graph
            try:
                seconds = graph.travel_seconds(creature.location_id, target_id)
                creature.location_id = target_id
                self._world.advance_time(TimeDelta(seconds=seconds))
            except ValueError:
                # No direct path — try by name match
                for loc_id in graph.all_ids():
                    loc = graph.get(loc_id)
                    if loc.name.lower() == target_id.lower():
                        try:
                            seconds = graph.travel_seconds(creature.location_id, loc_id)
                            creature.location_id = loc_id
                            self._world.advance_time(TimeDelta(seconds=seconds))
                        except ValueError:
                            pass
                        break
        elif creature:
            raw = action.params.get("hours", 1)
            hours = int(str(raw))
            if hours > 0:
                now = self._world.time.to_total_seconds()
                creature.wake_at_seconds = now + hours * 3600
                creature.active = False
                logger.info(
                    "[Wait] %s sleeps for %dh (wake_at=%d)",
                    creature.name,
                    hours,
                    creature.wake_at_seconds,
                )
