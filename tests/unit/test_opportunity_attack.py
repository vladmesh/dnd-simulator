"""Tests for opportunity attack rules, handler, and disengage fix."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.action_defs import CostType, get_action_def
from dnd_simulator.core.character import Ability, AbilityScores, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.combat import BattleMap, Position
from dnd_simulator.core.conditions import Condition
from dnd_simulator.core.items import Item, ItemType, WeaponCategory, WeaponDef
from dnd_simulator.core.models import ActionResult, EventType
from dnd_simulator.core.turn_budget import ActionCost, TurnBudget
from dnd_simulator.rules.reactions import can_opportunity_attack, find_oa_triggers


def _make_creature(
    name: str = "Fighter",
    *,
    hp: int = 20,
    ac: int = 15,
    reach: int = 5,
    weapon: bool = True,
    is_disengaging: bool = False,
) -> Creature:
    """Create a minimal creature for OA tests."""
    c = Creature(
        id=name.lower().replace(" ", "_"),
        name=name,
        location_id="arena",
        ability_scores=AbilityScores(
            scores={
                Ability.STR: 16,
                Ability.DEX: 14,
                Ability.CON: 14,
                Ability.INT: 10,
                Ability.WIS: 12,
                Ability.CHA: 8,
            }
        ),
        max_hp=hp,
        current_hp=hp,
        ac=ac,
        speed=30,
        attacks=(
            Attack(
                name="longsword",
                ability=Ability.STR,
                damage=(DamageComponent("1d8", DamageType.SLASHING),),
                reach=reach,
            ),
        ),
    )
    c.is_disengaging = is_disengaging
    c.turn_budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=30, reaction=1)
    if weapon:
        c.equipped_weapon = Item(
            id="longsword",
            name="Longsword",
            item_type=ItemType.WEAPON,
            weapon_def=WeaponDef(
                weapon_id="longsword",
                attack_name="longsword",
                category=WeaponCategory.MARTIAL,
                damage=(DamageComponent("1d8", DamageType.SLASHING),),
                reach=reach,
                ability=Ability.STR,
            ),
        )
    return c


def _make_battle_map() -> BattleMap:
    return BattleMap(width=100, height=100)


# ---------------------------------------------------------------------------
# can_opportunity_attack
# ---------------------------------------------------------------------------


class TestCanOpportunityAttack:
    def test_basic_eligibility(self) -> None:
        """Reactor with sword, mover 5ft away, reactor has reaction → True."""
        reactor = _make_creature("Reactor")
        mover = _make_creature("Mover")
        bm = _make_battle_map()
        bm.set_position("reactor", Position(10, 10))
        bm.set_position("mover", Position(15, 10))

        assert can_opportunity_attack(reactor, mover, bm) is True

    def test_blocked_by_incapacitated(self) -> None:
        """Reactor is stunned → False."""
        reactor = _make_creature("Reactor")
        reactor.conditions[Condition.STUNNED] = 1
        mover = _make_creature("Mover")
        bm = _make_battle_map()
        bm.set_position("reactor", Position(10, 10))
        bm.set_position("mover", Position(15, 10))

        assert can_opportunity_attack(reactor, mover, bm) is False

    def test_blocked_by_no_reaction_budget(self) -> None:
        """Reactor's turn_budget.reaction == 0 → False."""
        reactor = _make_creature("Reactor")
        assert reactor.turn_budget is not None
        reactor.turn_budget.reaction = 0
        mover = _make_creature("Mover")
        bm = _make_battle_map()
        bm.set_position("reactor", Position(10, 10))
        bm.set_position("mover", Position(15, 10))

        assert can_opportunity_attack(reactor, mover, bm) is False

    def test_blocked_by_disengaging(self) -> None:
        """Mover has is_disengaging=True → False."""
        reactor = _make_creature("Reactor")
        mover = _make_creature("Mover", is_disengaging=True)
        bm = _make_battle_map()
        bm.set_position("reactor", Position(10, 10))
        bm.set_position("mover", Position(15, 10))

        assert can_opportunity_attack(reactor, mover, bm) is False

    def test_blocked_by_out_of_reach(self) -> None:
        """Mover is 10ft away, reactor has 5ft reach → False."""
        reactor = _make_creature("Reactor")
        mover = _make_creature("Mover")
        bm = _make_battle_map()
        bm.set_position("reactor", Position(10, 10))
        bm.set_position("mover", Position(20, 10))  # 10ft away

        assert can_opportunity_attack(reactor, mover, bm) is False

    def test_extended_reach(self) -> None:
        """Reactor has polearm (reach 10), mover 10ft away → True."""
        reactor = _make_creature("Reactor", reach=10)
        mover = _make_creature("Mover")
        bm = _make_battle_map()
        bm.set_position("reactor", Position(10, 10))
        bm.set_position("mover", Position(20, 10))  # 10ft away

        assert can_opportunity_attack(reactor, mover, bm) is True

    def test_reactor_is_mover(self) -> None:
        """Creature can't OA itself."""
        creature = _make_creature("Fighter")
        bm = _make_battle_map()
        bm.set_position("fighter", Position(10, 10))

        assert can_opportunity_attack(creature, creature, bm) is False

    def test_blocked_by_dead(self) -> None:
        """Dead reactor can't OA."""
        reactor = _make_creature("Reactor", hp=0)
        mover = _make_creature("Mover")
        bm = _make_battle_map()
        bm.set_position("reactor", Position(10, 10))
        bm.set_position("mover", Position(15, 10))

        assert can_opportunity_attack(reactor, mover, bm) is False

    def test_no_turn_budget(self) -> None:
        """Reactor without turn_budget (out of combat) → False."""
        reactor = _make_creature("Reactor")
        reactor.turn_budget = None
        mover = _make_creature("Mover")
        bm = _make_battle_map()
        bm.set_position("reactor", Position(10, 10))
        bm.set_position("mover", Position(15, 10))

        assert can_opportunity_attack(reactor, mover, bm) is False


# ---------------------------------------------------------------------------
# find_oa_triggers
# ---------------------------------------------------------------------------


class TestFindOaTriggers:
    def test_straight_path_triggers_on_leave(self) -> None:
        """Mover walks from (10,10) to (10,30) past enemy at (15,10) with 5ft reach.

        Enemy is within 5ft at (10,10). At (10,15) the mover is ~7ft away (diagonal).
        Actually with grid_distance: (15,10) to (10,15) = 5 straight + 5 diag... let me
        use positions where reach is clear.

        Enemy at (15,10), mover path: (10,10) → (10,15) → (10,20).
        Distance (15,10)→(10,10) = 5ft (in reach).
        Distance (15,10)→(10,15) = grid_distance((15,10),(10,15)) = 1 straight + 1 diag = 5+5=10 > 5.
        Wait: dx=1, dy=1 squares. min=1 diag, straight=0. diag_cost = 0*15 + 1*5 = 5. So distance=5ft.
        Hmm that means the mover is still in reach at (10,15).
        Distance (15,10)→(10,20) = dx=1, dy=2 squares. straight=1, diag=1. diag_cost=5, straight=5. total=10 > 5.
        So trigger at step from (10,15) to (10,20).
        """
        enemy = _make_creature("Enemy")
        mover = _make_creature("Mover")
        bm = _make_battle_map()
        bm.set_position("enemy", Position(15, 10))
        bm.set_position("mover", Position(10, 10))

        path = [Position(10, 10), Position(10, 15), Position(10, 20)]
        triggers = find_oa_triggers(path, mover, [enemy, mover], bm)

        # Enemy should trigger when mover leaves reach
        assert len(triggers) == 1
        step_idx, reactors = triggers[0]
        assert step_idx == 1  # leaving (10,15) → (10,20)
        assert reactors == [enemy]

    def test_two_enemies_on_path(self) -> None:
        """Two enemies at different points — both trigger."""
        enemy1 = _make_creature("Enemy1")
        enemy2 = _make_creature("Enemy2")
        mover = _make_creature("Mover")
        bm = _make_battle_map()
        # Enemy1 adjacent at start, enemy2 adjacent further along the path.
        # Both should trigger when mover walks past and leaves their 5ft reach.
        bm.set_position("enemy1", Position(15, 10))
        bm.set_position("enemy2", Position(15, 30))
        bm.set_position("mover", Position(10, 10))

        # Path goes from (10,10) to (10,45) in 5ft steps
        path = [Position(10, y) for y in range(10, 50, 5)]
        triggers = find_oa_triggers(path, mover, [enemy1, enemy2, mover], bm)

        # Both enemies should trigger
        reactor_ids = {r.id for _, reactors in triggers for r in reactors}
        assert "enemy1" in reactor_ids
        assert "enemy2" in reactor_ids

    def test_disengaging_mover_no_triggers(self) -> None:
        """Disengaging mover → empty list."""
        enemy = _make_creature("Enemy")
        mover = _make_creature("Mover", is_disengaging=True)
        bm = _make_battle_map()
        bm.set_position("enemy", Position(15, 10))
        bm.set_position("mover", Position(10, 10))

        path = [Position(10, 10), Position(10, 15), Position(10, 20)]
        triggers = find_oa_triggers(path, mover, [enemy, mover], bm)

        assert triggers == []


# ---------------------------------------------------------------------------
# ActionCost reaction support
# ---------------------------------------------------------------------------


class TestReactionCost:
    def test_cost_type_reaction_exists(self) -> None:
        """CostType.REACTION exists."""
        assert CostType.REACTION == "reaction"

    def test_action_cost_reaction_field(self) -> None:
        """ActionCost has reaction field."""
        cost = ActionCost(reaction=1)
        assert cost.reaction == 1

    def test_turn_budget_can_afford_reaction(self) -> None:
        """TurnBudget with reaction=1 can afford reaction cost."""
        budget = TurnBudget(reaction=1)
        cost = ActionCost(reaction=1)
        assert budget.can_afford(cost) is True

    def test_turn_budget_consume_reaction(self) -> None:
        """Consuming reaction cost sets reaction to 0."""
        budget = TurnBudget(reaction=1)
        cost = ActionCost(reaction=1)
        budget.consume(cost)
        assert budget.reaction == 0

    def test_turn_budget_cannot_afford_second_reaction(self) -> None:
        """After consuming reaction, can't afford another."""
        budget = TurnBudget(reaction=1)
        cost = ActionCost(reaction=1)
        budget.consume(cost)
        assert budget.can_afford(cost) is False

    def test_turn_budget_refund_reaction(self) -> None:
        """Refunding reaction cost restores it."""
        budget = TurnBudget(reaction=0)
        cost = ActionCost(reaction=1)
        budget.refund(cost)
        assert budget.reaction == 1

    def test_reaction_does_not_end_turn(self) -> None:
        """Having unused reaction doesn't count as turn_over."""
        budget = TurnBudget(actions=0, bonus_actions=0, movement_remaining=0, reaction=1)
        assert budget.turn_over is True  # reaction doesn't prevent turn_over


# ---------------------------------------------------------------------------
# OA ActionDef
# ---------------------------------------------------------------------------


class TestOaActionDef:
    def test_opportunity_attack_def_cost_type(self) -> None:
        """OA uses REACTION cost type."""
        d = get_action_def(ActionType.OPPORTUNITY_ATTACK)
        assert d.cost_type == CostType.REACTION

    def test_opportunity_attack_def_internal(self) -> None:
        """OA is internal — not offered by providers."""
        d = get_action_def(ActionType.OPPORTUNITY_ATTACK)
        assert d.internal is True

    def test_opportunity_attack_def_combat_only(self) -> None:
        d = get_action_def(ActionType.OPPORTUNITY_ATTACK)
        from dnd_simulator.core.action_defs import CombatMode

        assert d.combat_mode == CombatMode.COMBAT_ONLY


# ---------------------------------------------------------------------------
# OA handler
# ---------------------------------------------------------------------------


class TestOaHandler:
    def test_oa_handler_emits_event_and_consumes_reaction(self) -> None:
        """Handler resolves attack via emit_fn, emits OA event, consumes reaction."""
        from dnd_simulator.rules.handlers.reactions import handle_opportunity_attack

        reactor = _make_creature("Reactor")
        _make_creature("Target")  # target exists but handler only needs its ID
        assert reactor.turn_budget is not None
        assert reactor.turn_budget.reaction == 1

        bm = _make_battle_map()
        bm.set_position("reactor", Position(10, 10))
        bm.set_position("target", Position(15, 10))

        action = Action(
            name=ActionType.OPPORTUNITY_ATTACK,
            params={"target_id": "target"},
        )

        # emit_fn should be called — first with ENTITY_ATTACK (returns result), then with OPPORTUNITY_ATTACK log
        attack_result = ActionResult(success=True)
        events_emitted: list[object] = []

        def mock_emit(event: object) -> ActionResult:
            events_emitted.append(event)
            return attack_result

        ctx = MagicMock()
        ctx.turn_budget = reactor.turn_budget
        world = MagicMock()

        result = handle_opportunity_attack(reactor, action, mock_emit, ctx, world)

        assert result.success is True
        # Reaction is consumed by the dispatcher, not the handler.
        # Handler only resolves the attack and emits events.
        assert reactor.turn_budget.reaction == 1

        # Should have emitted ENTITY_ATTACK event (for combat_manager resolution)
        # and OPPORTUNITY_ATTACK event (for combat log)
        from dnd_simulator.core.models import Event

        attack_events = [e for e in events_emitted if isinstance(e, Event) and e.event_type == EventType.ENTITY_ATTACK]
        oa_events = [e for e in events_emitted if isinstance(e, Event) and e.event_type == EventType.OPPORTUNITY_ATTACK]
        assert len(attack_events) == 1
        assert len(oa_events) == 1
        assert attack_events[0].data["attacker_id"] == "reactor"
        assert attack_events[0].data["target_id"] == "target"


# ---------------------------------------------------------------------------
# Disengage handler
# ---------------------------------------------------------------------------


class TestDisengageHandler:
    def test_disengage_sets_is_disengaging(self) -> None:
        """handle_disengage sets actor.is_disengaging = True."""
        from dnd_simulator.rules.handlers.movement import handle_disengage

        actor = _make_creature("Fighter")
        assert actor.is_disengaging is False

        action = Action(name=ActionType.DISENGAGE)
        events: list[object] = []

        def mock_emit(event: object) -> ActionResult:
            events.append(event)
            return ActionResult()

        ctx = MagicMock()
        world = MagicMock()

        result = handle_disengage(actor, action, mock_emit, ctx, world)

        assert result.success is True
        assert actor.is_disengaging is True
