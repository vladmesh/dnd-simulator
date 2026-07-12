"""Round orchestrator — runs all active creatures each round.

Combat turns use a multi-action loop with D&D 5e turn budget enforcement.
Peaceful turns have no budget — meaningful actions auto-end the turn,
while queries (look/status/map) loop without ending.
"""

from __future__ import annotations

import random
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING

import structlog

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.awareness import (
    CombatAwareness,
    PeacefulAwareness,
    PerceivedEvent,
)
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState, Position
from dnd_simulator.core.creature_host import CreatureHost
from dnd_simulator.core.events import TurnSkippedPayload
from dnd_simulator.core.models import ActionResult, EmitFn, Event, EventType, GameDateTime, QueryFn, TimeDelta
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger, TriggerType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.rules.actions import (
    ends_peaceful_turn,
    get_num_actions,
    get_num_bonus_actions,
)
from dnd_simulator.rules.conditions import is_incapacitated, tick_conditions
from dnd_simulator.rules.modifiers import effective_speed
from dnd_simulator.rules.movement import resolve_abstract_move
from dnd_simulator.rules.validation import ActionContext

if TYPE_CHECKING:
    from dnd_simulator.service.action_dispatcher import ActionDispatcher

logger = structlog.get_logger(domain="round")

# Callback fired after each individual action within a turn.
# (creature, action, budget, error) — budget is None for peaceful turns, error is "" on success.
OnActionCallback = Callable[[Creature, Action, TurnBudget | None, str], None]


@dataclass
class RoundResult:
    """Result of a single round."""

    events: list[Event] = field(default_factory=list)
    should_stop: bool = False


class Round:
    """Orchestrates one game round: all active creatures act, then time advances.

    Combat: multi-action loop with budget (actions, bonus, movement).
    Peaceful: no budget — turn-ending actions auto-end, queries loop.
    """

    def __init__(
        self,
        world: World,
        creature_host: CreatureHost | None = None,
        dispatcher: ActionDispatcher | None = None,
        rng: random.Random | None = None,
        mutation_scope: Callable[[], AbstractContextManager[None]] | None = None,
    ) -> None:
        self._world = world
        self._host = creature_host or world.creature_host
        if dispatcher is None:
            from dnd_simulator.service.action_dispatcher import create_dispatcher

            dispatcher = create_dispatcher(world)
        self._dispatcher = dispatcher
        self._rng = rng or random.Random()
        self._mutation_scope = mutation_scope or nullcontext
        self._stop_flag = False
        self._on_round_end: Callable[[RoundResult], None] | None = None
        self._on_action: OnActionCallback | None = None

    def stop(self) -> None:
        """Signal the run_loop to exit after current round completes."""
        self._stop_flag = True

    @property
    def is_stopped(self) -> bool:
        """True if run_loop exited because stop() was requested (not a natural end)."""
        return self._stop_flag

    def set_on_round_end(self, callback: Callable[[RoundResult], None]) -> None:
        """Set callback invoked after each round with the round result."""
        self._on_round_end = callback

    def set_on_action(self, callback: OnActionCallback) -> None:
        """Set callback invoked after each action within a turn."""
        self._on_action = callback

    def clear_callbacks(self) -> None:
        """Detach transport callbacks before discarding a live round."""
        self._on_action = None
        self._on_round_end = None

    def _execute_action(
        self,
        creature: Creature,
        action: Action,
        ctx: ActionContext,
        emit_fn: EmitFn,
    ) -> ActionResult:
        """Execute action via dispatcher. Validates, checks budget, executes, consumes budget."""
        with self._mutation_scope():
            return self._dispatcher.dispatch(creature, action, ctx, emit_fn)

    def get_perceived_events(self, creature: Creature) -> list[PerceivedEvent]:
        """Return perceived events for a creature (delegates to CreatureHost)."""
        return self._host.get_perceived_events(creature)

    def run_creature_turn(
        self,
        creature: Creature,
        time: GameDateTime,
        query_fn: QueryFn,
        emit_fn: EmitFn,
    ) -> list[Action]:
        """Dispatch to combat or peaceful turn based on creature state."""
        with structlog.contextvars.bound_contextvars(
            entity_id=creature.id,
            entity_name=creature.name,
            phase="combat" if creature.in_combat else "peaceful",
            location_id=creature.location_id,
        ):
            if creature.in_combat:
                return self.run_combat_turn(creature, time, query_fn, emit_fn)
            return self.run_peaceful_turn(creature, time, query_fn, emit_fn)

    def _prepare_combat_turn(
        self,
        creature: Creature,
        emit_fn: EmitFn,
    ) -> ActionContext | None:
        """Set up a creature's combat turn: tick conditions, check incapacitation, create budget.

        Returns an ActionContext if the creature can act, or None if the turn is skipped.
        """
        with self._mutation_scope():
            self._host.reset_combat_turn_state(creature.id)

            expired = tick_conditions(creature.conditions)
            if expired:
                logger.info("conditions_expired", conditions=[c.value for c in expired])

            if is_incapacitated(creature.conditions):
                logger.info("turn_skipped_incapacitated")
                reasons = sorted(c.value for c in creature.conditions if is_incapacitated({c: None}))
                emit_fn(
                    Event(
                        event_type=EventType.TURN_SKIPPED,
                        source_layer="entities",
                        data=TurnSkippedPayload(creature.id, "incapacitated", tuple(reasons), creature.location_id),
                    )
                )
                return None

        weapon_info = "fists"
        if creature.equipped_weapon and creature.equipped_weapon.weapon_def:
            wd = creature.equipped_weapon.weapon_def
            grants = [a.value for a in wd.grant_actions] if wd.grant_actions else []
            weapon_info = f"{wd.attack_name} (grants: {grants})" if grants else wd.attack_name
        conds_info = {c.value: r for c, r in creature.conditions.items()} if creature.conditions else {}
        logger.debug("combat_turn_start", weapon=weapon_info, conditions=conds_info)

        with self._mutation_scope():
            speed = effective_speed(creature)
            if speed != creature.speed:
                logger.debug(
                    "speed_reduced",
                    base_speed=creature.speed,
                    effective_speed=speed,
                    conditions=[c.value for c in creature.conditions],
                )
            creature.turn_budget = TurnBudget(
                actions=get_num_actions(creature),
                bonus_actions=get_num_bonus_actions(creature),
                movement_remaining=speed,
                reaction=1,
            )
            creature.is_disengaging = False

        combat_state = self._host.get_combat(creature.location_id)
        return ActionContext(
            is_combat=True,
            current_turn_entity_id=creature.id,
            turn_budget=creature.turn_budget,
            combat_state=combat_state,
            get_entity=self._host.get_entity,
            rng=self._rng,
        )

    def _build_combat_awareness(
        self,
        creature: Creature,
        ctx: ActionContext,
        time: GameDateTime,
        query_fn: QueryFn,
    ) -> PeacefulAwareness | CombatAwareness:
        """Build awareness for a combat turn iteration."""
        assert creature.turn_budget is not None
        available = self._dispatcher.get_available_actions(creature, ctx)
        awareness = replace(
            self._host.build_awareness(creature, time, query_fn),
            turn_budget=creature.turn_budget,
            available_actions=available,
            available_items=self._host.build_available_items(creature),
            equipped=self._host.build_equipped(creature),
            reachable=self._host.compute_reachable(creature, ctx.combat_state, creature.turn_budget),
        )

        if isinstance(awareness, CombatAwareness):
            logger.debug(
                "combat_awareness",
                actions=[a.value for a in awareness.available_actions],
                weapon=awareness.self_weapon,
                conditions=[c.value for c in awareness.self_conditions],
                items=[{"id": i.id, "type": i.item_type, "name": i.name} for i in awareness.available_items],
            )
        return awareness

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

        with self._mutation_scope():
            ctx = self._prepare_combat_turn(creature, emit_fn)
        if ctx is None:
            return []

        # Wire OA callback if in active combat
        if ctx.combat_state is not None:
            on_leave_reach = self._make_on_leave_reach(ctx.combat_state, time, query_fn, emit_fn)
            ctx = replace(ctx, on_leave_reach=on_leave_reach)

        assert creature.turn_budget is not None
        actions: list[Action] = []
        consecutive_failures = 0

        while True:
            if not creature.is_alive:
                break

            awareness = self._build_combat_awareness(creature, ctx, time, query_fn)
            events = self._host.get_perceived_events(creature)

            action = creature.brain.choose_action(creature, awareness, events)

            if action.name == ActionType.END_TURN:
                break

            # Resolve abstract move (toward/away_from) to concrete direction for any creature
            if action.name == ActionType.MOVE and ("toward" in action.params or "away_from" in action.params):
                action = resolve_abstract_move(action, creature, self._host.get_combat(creature.location_id))

            result = self._execute_action(creature, action, ctx, emit_fn)

            if result.success:
                consecutive_failures = 0
            else:
                consecutive_failures += 1
                logger.info("action_failed", action=action.name.value, error=result.error)
                if self._on_action:
                    self._on_action(creature, action, creature.turn_budget, result.error)
                if consecutive_failures >= 3:
                    logger.warning("consecutive_failures_end_turn", failures=consecutive_failures)
                    break
                continue

            actions.append(action)

            if self._on_action:
                self._on_action(creature, action, creature.turn_budget, result.error)

            if creature.turn_budget.turn_over:
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
            get_entity=self._host.get_entity,
            rng=self._rng,
        )

        while True:
            if not creature.is_alive:
                break

            available = self._dispatcher.get_available_actions(creature, ctx)
            awareness = replace(
                self._host.build_peaceful_awareness(creature, time, query_fn),
                available_actions=available,
                available_items=self._host.build_available_items(creature),
                equipped=self._host.build_equipped(creature),
                merchants=self._host.build_merchants(creature, self._world.time.hour),
            )
            events = self._host.get_perceived_events(creature)

            logger.debug(
                "peaceful_awareness",
                creature_id=creature.id,
                actions=[a.value for a in awareness.available_actions],
                items=[{"id": i.id, "type": i.item_type, "name": i.name} for i in awareness.available_items],
            )

            action = creature.brain.choose_action(creature, awareness, events)

            if action.name == ActionType.END_TURN:
                break

            # Dispatcher handles validation + execution
            result = self._execute_action(creature, action, ctx, emit_fn)
            if not result.success:
                logger.warning("action_failed", action=action.name.value, error=result.error)
                if self._on_action:
                    self._on_action(creature, action, None, result.error)
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
        trigger: ReactionTrigger,
        options: list[ReactionOption],
        candidates: list[Creature],
        emit_fn: EmitFn | None = None,
    ) -> list[Action]:
        """Ask candidates whether they want to react to the trigger.

        Each candidate with reaction budget and a brain gets choose_reaction().
        If not SKIP, the action is dispatched. Returns list of reactions taken.
        """
        reactions: list[Action] = []
        _emit: EmitFn = emit_fn or (lambda e: ActionResult())

        for creature in candidates:
            if creature.brain is None or not creature.is_alive:
                continue
            if creature.turn_budget is None or creature.turn_budget.reaction <= 0:
                continue

            action = creature.brain.choose_reaction(creature, trigger, options)

            if action.name == ActionType.SKIP:
                continue

            combat_state = self._host.get_combat(creature.location_id)
            ctx = ActionContext(
                is_combat=True,
                current_turn_entity_id=creature.id,
                turn_budget=creature.turn_budget,
                combat_state=combat_state,
                get_entity=self._host.get_entity,
                rng=self._rng,
            )
            result = self._execute_action(creature, action, ctx, _emit)
            if result.success:
                reactions.append(action)

        return reactions

    def _make_on_leave_reach(
        self,
        combat_state: CombatState,
        time: GameDateTime,
        query_fn: QueryFn,
        emit_fn: EmitFn,
    ) -> Callable[[Creature, Position, Position, list[Creature]], bool]:
        """Create on_leave_reach callback for movement handlers.

        Returns a closure that builds a LEAVING_REACH trigger, asks reactors
        via check_reactions, and returns True if the mover is still alive.
        """

        def on_leave_reach(
            mover: Creature,
            from_pos: Position,
            to_pos: Position,
            reactors: list[Creature],
        ) -> bool:
            trigger = ReactionTrigger(
                trigger_type=TriggerType.LEAVING_REACH,
                source_creature_id=mover.id,
                data={
                    "mover_id": mover.id,
                    "from_pos": (from_pos.x, from_pos.y),
                    "to_pos": (to_pos.x, to_pos.y),
                },
            )
            options = [
                ReactionOption(
                    action_type=ActionType.OPPORTUNITY_ATTACK,
                    description=f"Melee attack against {mover.name}",
                    params={"target_id": mover.id},
                )
            ]
            # Process reactors one at a time — stop if mover dies from an OA
            for reactor in reactors:
                if not mover.is_alive:
                    break
                self.check_reactions(trigger, options, [reactor], emit_fn)
            return mover.is_alive

        return on_leave_reach

    def run_round(self, *, skip_activation: bool = False) -> RoundResult:
        """Execute one round: combat turns (initiative order), then peaceful turns, then advance time.

        ``skip_activation`` is set by ``run_loop``, which already activated this iteration —
        avoids running activation (and its materialization) twice per loop step.
        """
        query_fn = self._world.make_query_fn("entities")
        emit_fn = self._world.make_emit_fn("entities")
        time = self._world.time

        # Activate creatures near players, dormify the rest, materialize squads
        if not skip_activation:
            self._host.update_activation(
                time, query_fn=query_fn, emit_fn=emit_fn, location_graph=self._world.location_graph
            )

        active_count = len(self._host.get_active_creatures())
        combat_locations = list(self._host.get_combat_locations())
        logger.info(
            "round_start", game_time=str(time), active_creatures=active_count, combat_locations=len(combat_locations)
        )

        # Combat rounds: iterate by initiative order per location
        for location_id in list(self._host.get_combat_locations()):
            combat = self._host.get_combat(location_id)
            if not combat:
                continue
            self._host.log_round_start(location_id, combat.round_number)
            for entity_id in list(combat.turn_order):
                entity = self._host.get_entity(entity_id)
                if isinstance(entity, Creature) and entity.is_alive and entity.active and entity.in_combat:
                    with self._mutation_scope():
                        entity.is_dodging = False  # dodge lasts until start of next turn
                        entity.is_disengaging = False
                    self.run_creature_turn(entity, time, query_fn, emit_fn)
            # End of round — check for combat exit
            with self._mutation_scope():
                self._host.end_combat_round(location_id)

        # Peaceful turns: creatures not in combat
        for creature in self._host.get_active_creatures():
            if creature.in_combat or not creature.is_alive or not creature.active:
                continue
            self.run_creature_turn(creature, time, query_fn, emit_fn)

        # Advance time by one round (6 seconds)
        with self._mutation_scope():
            tick_events = self._world.advance_time(TimeDelta.from_rounds(1))

        logger.info("round_end", game_time=str(self._world.time), tick_events=len(tick_events))
        return RoundResult(events=tick_events)

    def _activate(self) -> None:
        """Update activation with materialization support."""
        qfn = self._world.make_query_fn("entities")
        efn = self._world.make_emit_fn("entities")
        with self._mutation_scope():
            self._host.update_activation(
                self._world.time, query_fn=qfn, emit_fn=efn, location_graph=self._world.location_graph
            )

    def run_loop(self, max_rounds: int | None = None) -> None:
        """Run rounds until no active creatures remain or stop() is called."""
        rounds_run = 0
        while not self._stop_flag:
            # Update activation before checking — resolves stale state from previous round
            self._activate()
            active = self._host.get_active_creatures()
            logger.debug(
                "loop_check",
                active_count=len(active),
                active_ids=[c.id for c in active],
                stop_flag=self._stop_flag,
            )
            if not active:
                if not self._fast_forward():
                    logger.debug("loop_exit_no_active")
                    break
                continue  # re-check active after fast-forward
            # run_loop already activated this iteration — don't re-run it inside run_round.
            result = self.run_round(skip_activation=True)
            rounds_run += 1
            if self._on_round_end:
                self._on_round_end(result)
            if result.should_stop:
                break
            if max_rounds is not None and rounds_run >= max_rounds:
                break

    def _fast_forward(self) -> bool:
        """Advance time to the nearest intent wake point when no creatures are active.

        Returns True if time was advanced (loop should continue), False if
        there's nobody to wake up (loop should exit).
        """
        with self._mutation_scope():
            nearest_wake = self._host.get_nearest_wake_time()

            if nearest_wake is None:
                return False

            now = self._world.time.to_total_seconds()
            delta_seconds = nearest_wake - now
            if delta_seconds <= 0:
                # Timer already expired — just run update_activation
                self._activate()
                return True

            logger.info("fast_forward", delta_seconds=delta_seconds)
            tick_events = self._world.advance_time(TimeDelta(seconds=delta_seconds))
            self._activate()

        if self._on_round_end:
            self._on_round_end(RoundResult(events=tick_events))

        return True
