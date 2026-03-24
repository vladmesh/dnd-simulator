"""Round orchestrator — runs all active creatures each round.

Combat turns use a multi-action loop with D&D 5e turn budget enforcement.
Peaceful turns have no budget — meaningful actions auto-end the turn,
while queries (look/status/map) loop without ending.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, ItemInfo, PerceivedEvent, describe_item
from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import ActionResult, EmitFn, Event, EventType, GameDateTime, QueryFn, TimeDelta
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.actions import (
    ends_peaceful_turn,
    get_num_actions,
    get_num_bonus_actions,
)
from dnd_simulator.rules.conditions import is_incapacitated, tick_conditions
from dnd_simulator.rules.modifiers import effective_speed
from dnd_simulator.rules.validation import ActionContext

if TYPE_CHECKING:
    from dnd_simulator.service.action_dispatcher import ActionDispatcher

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

    def __init__(
        self,
        world: World,
        entities_layer: EntitiesLayer | None = None,
        dispatcher: ActionDispatcher | None = None,
    ) -> None:
        self._world = world
        self._entities = entities_layer or get_entities_layer(world)
        if dispatcher is None:
            from dnd_simulator.service.action_dispatcher import create_dispatcher

            dispatcher = create_dispatcher(world)
        self._dispatcher = dispatcher
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

    @staticmethod
    def _build_available_items(creature: Creature, available_actions: list[ActionType]) -> list[ItemInfo]:
        """Build item info list for awareness when USE_ITEM or EQUIP is available."""
        if ActionType.USE_ITEM not in available_actions and ActionType.EQUIP not in available_actions:
            return []
        return [ItemInfo(id=item.id, name=item.name, description=describe_item(item)) for item in creature.inventory]

    def _execute_action(
        self,
        creature: Creature,
        action: Action,
        ctx: ActionContext,
        emit_fn: EmitFn,
    ) -> ActionResult:
        """Execute action via dispatcher. Validates, checks budget, executes, consumes budget."""
        return self._dispatcher.dispatch(creature, action, ctx, emit_fn)

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

        # Tick timed conditions at the start of each turn
        expired = tick_conditions(creature.conditions)
        if expired:
            logger.info("[Round] %s: conditions expired: %s", creature.name, ", ".join(c.value for c in expired))

        # Incapacitated creatures (stunned, paralyzed, etc.) skip their turn entirely
        if is_incapacitated(creature.conditions):
            logger.info("[Round] %s is incapacitated, skipping turn", creature.name)
            reasons = sorted(c.value for c in creature.conditions if is_incapacitated({c: None}))
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

        # Debug: log weapon and conditions at turn start
        weapon_info = "fists"
        if creature.equipped_weapon and creature.equipped_weapon.weapon_def:
            wd = creature.equipped_weapon.weapon_def
            grants = [a.value for a in wd.grant_actions] if wd.grant_actions else []
            weapon_info = f"{wd.attack_name} (grants: {grants})" if grants else wd.attack_name
        conds_info = {c.value: r for c, r in creature.conditions.items()} if creature.conditions else {}
        logger.debug(
            "[Round] %s turn start: weapon=%s, conditions=%s",
            creature.name,
            weapon_info,
            conds_info,
        )

        speed = effective_speed(creature)
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

        combat_state = self._entities.get_combat(creature.location_id)
        ctx = ActionContext(
            is_combat=True,
            current_turn_entity_id=creature.id,
            turn_budget=budget,
            combat_state=combat_state,
            get_entity=self._entities.get_entity,
        )

        while True:
            available = self._dispatcher.get_available_actions(creature, ctx)
            awareness = replace(
                self._entities.build_awareness(creature, time, query_fn),
                turn_budget=budget,
                available_actions=available,
                available_items=self._build_available_items(creature, available),
            )
            events = self._entities.get_perceived_events(creature)

            if isinstance(awareness, CombatAwareness):
                logger.debug(
                    "[Round] %s actions=%s weapon=%s conds=%s",
                    creature.name,
                    [a.value for a in awareness.available_actions],
                    awareness.self_weapon,
                    [c.value for c in awareness.self_conditions],
                )

            action = creature.brain.choose_action(creature, awareness, events)

            if action.name == ActionType.END_TURN:
                break

            # Dispatcher handles: validation → budget check → execute → budget consume
            result = self._execute_action(creature, action, ctx, emit_fn)

            if result.success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.info(
                    "[Round] %s action '%s' failed: %s",
                    creature.name,
                    action.name.value,
                    result.error,
                )
                # Notify client about failed action (so UI can show error)
                if self._on_action:
                    self._on_action(creature, action, budget, result.error)
                if consecutive_failures >= 3:
                    logger.warning(
                        "[Round] %s failed %d actions in a row, ending turn",
                        creature.name,
                        consecutive_failures,
                    )
                    break
                continue

            actions.append(action)

            if self._on_action:
                self._on_action(creature, action, budget, result.error)

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
        ctx = ActionContext(
            is_combat=False,
            current_turn_entity_id=creature.id,
            get_entity=self._entities.get_entity,
        )

        while True:
            available = self._dispatcher.get_available_actions(creature, ctx)
            awareness = replace(
                self._entities.build_awareness(creature, time, query_fn),
                available_actions=available,
                available_items=self._build_available_items(creature, available),
            )
            events = self._entities.get_perceived_events(creature)

            action = creature.brain.choose_action(creature, awareness, events)

            if action.name == ActionType.END_TURN:
                break

            # Dispatcher handles validation + execution
            result = self._execute_action(creature, action, ctx, emit_fn)
            if not result.success:
                logger.warning("[Round] %s action '%s' failed: %s", creature.name, action.name, result.error)
                break

            actions.append(action)

            if self._on_action:
                self._on_action(creature, action, None, result.error)

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

            if action.name == ActionType.SKIP:
                continue

            combat_state = self._entities.get_combat(creature.location_id)
            ctx = ActionContext(
                is_combat=True,
                current_turn_entity_id=creature.id,
                combat_state=combat_state,
                get_entity=self._entities.get_entity,
            )
            reaction_result = self._execute_action(creature, action, ctx, emit_fn)
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
