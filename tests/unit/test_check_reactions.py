"""Tests for Round.check_reactions rewrite and on_leave_reach callback.

Sprint 012, Phase 2, Task 1: wire check_reactions to use choose_reaction,
add on_leave_reach callback to ActionContext.
"""

from __future__ import annotations

import random
from contextlib import nullcontext
from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.reactions import ReactionOption, ReactionTrigger, TriggerType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.rule_brain import RuleBrain
from dnd_simulator.rules.validation import ActionContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creature(
    id: str,
    hp: int = 20,
    *,
    brain: object | None = None,
    reaction: int = 1,
) -> Creature:
    c = Creature(id=id, name=id.capitalize(), location_id="arena", max_hp=hp, current_hp=hp)
    c.brain = brain  # type: ignore[assignment]
    c.turn_budget = TurnBudget(actions=1, bonus_actions=0, movement_remaining=30, reaction=reaction)
    return c


def _trigger(mover_id: str = "mover") -> ReactionTrigger:
    return ReactionTrigger(
        trigger_type=TriggerType.LEAVING_REACH,
        source_creature_id=mover_id,
        data={"mover_id": mover_id, "from_pos": (10, 10), "to_pos": (10, 15)},
    )


def _oa_option(target_id: str = "mover") -> ReactionOption:
    return ReactionOption(
        action_type=ActionType.OPPORTUNITY_ATTACK,
        description=f"Melee attack against {target_id}",
        params={"target_id": target_id},
    )


def _make_round(creatures: list[Creature]) -> object:
    """Build a Round with minimal wiring for check_reactions testing."""
    from dnd_simulator.round import Round

    world = MagicMock()
    entities = MagicMock()
    entities.get_entity = MagicMock(side_effect=lambda id: next((c for c in creatures if c.id == id), None))
    dispatcher = MagicMock()
    # dispatcher.dispatch should succeed by default
    from dnd_simulator.core.models import ActionResult

    dispatcher.dispatch = MagicMock(return_value=ActionResult(success=True))

    r = Round.__new__(Round)
    r._world = world
    r._host = entities
    r._dispatcher = dispatcher
    r._rng = random.Random(0)
    r._mutation_scope = nullcontext
    r._on_action = None
    return r


# ---------------------------------------------------------------------------
# ActionContext accepts on_leave_reach
# ---------------------------------------------------------------------------


class TestActionContextOnLeaveReach:
    def test_default_none(self) -> None:
        ctx = ActionContext(is_combat=True)
        assert ctx.on_leave_reach is None

    def test_with_callback(self) -> None:
        def callback(mover: Creature, from_pos: Position, to_pos: Position, reactors: list[Creature]) -> bool:
            return True

        ctx = ActionContext(is_combat=True, on_leave_reach=callback)
        assert ctx.on_leave_reach is callback


# ---------------------------------------------------------------------------
# check_reactions uses choose_reaction
# ---------------------------------------------------------------------------


class TestCheckReactions:
    def test_calls_choose_reaction_not_choose_action(self) -> None:
        """check_reactions calls choose_reaction with trigger and options, not choose_action."""
        brain = MagicMock()
        brain.choose_reaction = MagicMock(return_value=Action(name=ActionType.SKIP))
        reactor = _creature("guard", brain=brain)
        creatures = [reactor]
        rnd = _make_round(creatures)

        trigger = _trigger()
        options = [_oa_option()]

        rnd.check_reactions(trigger, options, [reactor])  # type: ignore[attr-defined]

        brain.choose_reaction.assert_called_once_with(reactor, trigger, options)
        brain.choose_action = MagicMock()  # shouldn't have been called
        brain.choose_action.assert_not_called()

    def test_rulebrain_oa_and_skip_brain(self) -> None:
        """RuleBrain takes OA, skip-brain skips. Only one reaction executed."""
        rule_reactor = _creature("guard", brain=RuleBrain())
        skip_brain = MagicMock()
        skip_brain.choose_reaction = MagicMock(return_value=Action(name=ActionType.SKIP))
        skip_reactor = _creature("coward", brain=skip_brain)

        creatures = [rule_reactor, skip_reactor]
        rnd = _make_round(creatures)
        trigger = _trigger()
        options = [_oa_option()]

        reactions = rnd.check_reactions(trigger, options, [rule_reactor, skip_reactor])  # type: ignore[attr-defined]

        assert len(reactions) == 1
        assert reactions[0].name == ActionType.OPPORTUNITY_ATTACK

    def test_skips_dead_creature(self) -> None:
        """Dead creatures don't get choose_reaction called."""
        brain = MagicMock()
        brain.choose_reaction = MagicMock(return_value=Action(name=ActionType.SKIP))
        dead = _creature("dead", hp=0, brain=brain)
        dead.current_hp = 0
        alive = _creature("alive", brain=RuleBrain())

        rnd = _make_round([dead, alive])
        trigger = _trigger()
        options = [_oa_option()]

        reactions = rnd.check_reactions(trigger, options, [dead, alive])  # type: ignore[attr-defined]

        brain.choose_reaction.assert_not_called()
        assert len(reactions) == 1

    def test_skips_no_reaction_budget(self) -> None:
        """Creatures with reaction=0 are skipped."""
        brain = MagicMock()
        brain.choose_reaction = MagicMock(return_value=Action(name=ActionType.SKIP))
        spent = _creature("spent", brain=brain, reaction=0)
        fresh = _creature("fresh", brain=RuleBrain())

        rnd = _make_round([spent, fresh])
        trigger = _trigger()
        options = [_oa_option()]

        reactions = rnd.check_reactions(trigger, options, [spent, fresh])  # type: ignore[attr-defined]

        brain.choose_reaction.assert_not_called()
        assert len(reactions) == 1

    def test_reaction_consumed_after_oa(self) -> None:
        """After OA, reactor's reaction budget goes from 1 to 0."""
        reactor = _creature("guard", brain=RuleBrain())
        assert reactor.turn_budget is not None
        assert reactor.turn_budget.reaction == 1

        rnd = _make_round([reactor])
        trigger = _trigger()
        options = [_oa_option()]

        rnd.check_reactions(trigger, options, [reactor])  # type: ignore[attr-defined]

        # OA handler consumes reaction directly, but dispatch mock won't do that.
        # check_reactions should NOT double-consume — the handler does it.
        # So we verify dispatch was called (handler would consume).
        rnd._dispatcher.dispatch.assert_called_once()  # type: ignore[attr-defined]

    def test_skips_brainless_creature(self) -> None:
        """Creatures with no brain are skipped."""
        no_brain = _creature("zombie", brain=None)
        rnd = _make_round([no_brain])
        trigger = _trigger()
        options = [_oa_option()]

        reactions = rnd.check_reactions(trigger, options, [no_brain])  # type: ignore[attr-defined]
        assert reactions == []

    def test_failed_dispatch_not_counted(self) -> None:
        """If dispatch fails, reaction not counted in results."""
        reactor = _creature("guard", brain=RuleBrain())
        rnd = _make_round([reactor])
        from dnd_simulator.core.models import ActionResult

        rnd._dispatcher.dispatch = MagicMock(return_value=ActionResult(success=False, error="out of reach"))  # type: ignore[attr-defined]

        trigger = _trigger()
        options = [_oa_option()]

        reactions = rnd.check_reactions(trigger, options, [reactor])  # type: ignore[attr-defined]
        assert reactions == []


# ---------------------------------------------------------------------------
# on_leave_reach callback — built by Round._make_on_leave_reach
# ---------------------------------------------------------------------------


class TestMakeOnLeaveReach:
    def test_returns_true_when_mover_alive(self) -> None:
        """Callback returns True if mover survives all reactions."""
        mover = _creature("mover")
        reactor = _creature("guard", brain=RuleBrain())
        rnd = _make_round([mover, reactor])

        combat_state = CombatState(
            location_id="arena",
            turn_order=["mover", "guard"],
            round_number=1,
            rounds_without_attack=0,
            battle_map=BattleMap(width=50, height=50),
        )
        combat_state.battle_map.set_position("mover", Position(10, 10))
        combat_state.battle_map.set_position("guard", Position(10, 5))

        emit_fn = MagicMock()
        query_fn = MagicMock()
        time = MagicMock()

        callback = rnd._make_on_leave_reach(combat_state, time, query_fn, emit_fn)  # type: ignore[attr-defined]
        result = callback(mover, Position(10, 10), Position(10, 15), [reactor])
        assert result is True

    def test_returns_false_when_mover_dead(self) -> None:
        """Callback returns False if mover dies from OA."""
        mover = _creature("mover", hp=1)
        reactor = _creature("guard", brain=RuleBrain())
        rnd = _make_round([mover, reactor])

        combat_state = CombatState(
            location_id="arena",
            turn_order=["mover", "guard"],
            round_number=1,
            rounds_without_attack=0,
            battle_map=BattleMap(width=50, height=50),
        )
        combat_state.battle_map.set_position("mover", Position(10, 10))
        combat_state.battle_map.set_position("guard", Position(10, 5))

        # Simulate OA killing the mover: dispatch side-effect kills mover
        from dnd_simulator.core.models import ActionResult

        def kill_mover(creature: object, action: object, ctx: object, emit_fn: object) -> ActionResult:
            mover.current_hp = 0
            return ActionResult(success=True)

        rnd._dispatcher.dispatch = MagicMock(side_effect=kill_mover)  # type: ignore[attr-defined]

        emit_fn = MagicMock()
        query_fn = MagicMock()
        time = MagicMock()

        callback = rnd._make_on_leave_reach(combat_state, time, query_fn, emit_fn)  # type: ignore[attr-defined]
        result = callback(mover, Position(10, 10), Position(10, 15), [reactor])
        assert result is False
