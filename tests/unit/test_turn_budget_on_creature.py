"""Tests for TurnBudget living on Creature instead of as a local variable.

Sprint 012, Phase 1, Task 1: budget must persist on creature between turns
so reactions (opportunity attacks) can consume it outside run_combat_turn.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.round import Round
from dnd_simulator.rules.validation import ActionContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class EndTurnBrain(Brain):
    """Brain that immediately ends turn — minimal, just to run a combat turn."""

    def choose_action(self, creature, awareness, events) -> Action:  # type: ignore[override]
        return Action(name=ActionType.END_TURN)


class OneAttackBrain(Brain):
    """Brain that attacks once then ends turn. Consumes action budget."""

    def __init__(self) -> None:
        self._called = False

    def choose_action(self, creature, awareness, events) -> Action:  # type: ignore[override]
        if not self._called:
            self._called = True
            return Action(name=ActionType.ATTACK, params={"target_id": "dummy"})
        return Action(name=ActionType.END_TURN)


def _make_creature(brain: Brain, speed: int = 30) -> Creature:
    return Creature(
        id="warrior",
        name="Warrior",
        location_id="arena",
        max_hp=20,
        current_hp=20,
        speed=speed,
        brain=brain,
        in_combat=True,
    )


def _make_round_with_creature(creature: Creature) -> Round:
    """Create a Round with minimal mocking — creature in combat at a location."""
    entities = MagicMock(spec=EntitiesLayer)
    entities.get_entity.return_value = creature
    entities.get_active_creatures.return_value = [creature]
    entities.get_combat_locations.return_value = ["arena"]
    entities.get_combat.return_value = CombatState(
        location_id="arena",
        turn_order=[creature.id],
        battle_map=BattleMap(width=60, height=60, positions={creature.id: Position(10, 10)}),
    )
    entities.build_awareness.return_value = CombatAwareness(
        self_hp=creature.current_hp,
        self_max_hp=creature.max_hp,
        self_ac=creature.ac,
        self_speed=creature.speed,
        self_weapon="fists",
        self_weapon_damage="1d4",
    )
    entities.get_perceived_events.return_value = []
    entities.reset_combat_turn_state.return_value = None

    world = MagicMock()
    world.time = GameDateTime()
    world._make_query_fn.return_value = MagicMock()
    world._make_emit_fn.return_value = MagicMock()

    return Round(world=world, creature_host=entities)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestTurnBudgetOnCreature:
    """TurnBudget must live on Creature, not as a local var in Round."""

    def test_budget_created_on_creature_at_turn_start(self) -> None:
        """After run_combat_turn, creature.turn_budget has expected initial values."""
        creature = _make_creature(EndTurnBrain(), speed=30)
        assert creature.turn_budget is None  # not set before turn

        rnd = _make_round_with_creature(creature)
        query_fn = MagicMock()
        emit_fn = MagicMock()
        rnd.run_combat_turn(creature, GameDateTime(), query_fn, emit_fn)

        assert creature.turn_budget is not None
        # Initial values: 1 action, 1 bonus, speed movement, 1 reaction
        assert creature.turn_budget.actions == 1  # EndTurnBrain doesn't consume
        assert creature.turn_budget.bonus_actions == 1
        assert creature.turn_budget.movement_remaining == 30
        assert creature.turn_budget.reaction == 1

    def test_budget_persists_after_turn_ends(self) -> None:
        """Budget stays on creature after turn — reactions need it between turns."""
        creature = _make_creature(EndTurnBrain())
        rnd = _make_round_with_creature(creature)
        rnd.run_combat_turn(creature, GameDateTime(), MagicMock(), MagicMock())

        budget = creature.turn_budget
        assert budget is not None
        # Budget is still there, not cleared
        assert isinstance(budget, TurnBudget)

    def test_budget_resets_on_next_turn(self) -> None:
        """Second combat turn creates a fresh budget, not carrying over."""
        creature = _make_creature(EndTurnBrain(), speed=25)
        rnd = _make_round_with_creature(creature)
        emit_fn = MagicMock()

        rnd.run_combat_turn(creature, GameDateTime(), MagicMock(), emit_fn)
        first_budget = creature.turn_budget
        assert first_budget is not None

        # Manually deplete something to verify it resets
        first_budget.movement_remaining = 0

        rnd.run_combat_turn(creature, GameDateTime(), MagicMock(), emit_fn)
        assert creature.turn_budget is not first_budget  # new object
        assert creature.turn_budget is not None
        assert creature.turn_budget.movement_remaining == 25  # fresh from speed

    def test_is_disengaging_resets_at_turn_start(self) -> None:
        """is_disengaging is cleared when a new combat turn begins."""
        creature = _make_creature(EndTurnBrain())
        creature.is_disengaging = True

        rnd = _make_round_with_creature(creature)
        # run_round resets is_disengaging before calling run_creature_turn
        # But we test via run_combat_turn which should also reset it
        rnd.run_combat_turn(creature, GameDateTime(), MagicMock(), MagicMock())

        assert creature.is_disengaging is False

    def test_action_context_receives_creature_budget(self) -> None:
        """ActionContext.turn_budget must be the same object as creature.turn_budget."""
        creature = _make_creature(EndTurnBrain())
        rnd = _make_round_with_creature(creature)

        # Intercept dispatcher calls to inspect the ActionContext
        captured_ctx: list[ActionContext] = []

        def capture_ctx(actor, ctx):  # type: ignore[no-untyped-def]
            captured_ctx.append(ctx)
            return [ActionType.END_TURN]

        rnd._dispatcher.get_available_actions = capture_ctx

        rnd.run_combat_turn(creature, GameDateTime(), MagicMock(), MagicMock())

        assert len(captured_ctx) >= 1
        ctx = captured_ctx[0]
        assert ctx.turn_budget is creature.turn_budget
