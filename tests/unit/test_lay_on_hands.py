"""Tests for Lay on Hands — Paladin action heal."""

from __future__ import annotations

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import (
    Character,
    CharClass,
    Creature,
    Race,
)
from dnd_simulator.core.class_features import PaladinFeatures
from dnd_simulator.core.models import ActionResult, Event
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.action_provider import ClassFeatureActionProvider
from dnd_simulator.rules.actions import action_cost
from dnd_simulator.rules.handlers.items import handle_lay_on_hands
from dnd_simulator.rules.resources import has_resource, reset_resources, use_resource
from dnd_simulator.rules.validation import ActionContext


def _paladin(
    *,
    current_hp: int = 20,
    max_hp: int = 25,
    level: int = 1,
    pool_uses: int | None = None,
) -> Character:
    if pool_uses is None:
        pool_uses = 5 * level
    return Character(
        id="paladin",
        name="Paladin",
        location_id="arena",
        max_hp=max_hp,
        current_hp=current_hp,
        ac=18,
        race=Race.HUMAN,
        char_class=CharClass.PALADIN,
        level=level,
        class_features=[PaladinFeatures()],
        resource_pools=[ResourcePool("lay_on_hands", 5 * level, pool_uses, RestType.LONG_REST)],
    )


def _ally(*, current_hp: int = 10, max_hp: int = 20) -> Character:
    return Character(
        id="ally",
        name="Ally",
        location_id="arena",
        max_hp=max_hp,
        current_hp=current_hp,
        ac=14,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
    )


def _ctx(*, is_combat: bool = True, entities: dict[str, Creature] | None = None) -> ActionContext:
    lookup = (lambda eid: entities[eid]) if entities else None
    return ActionContext(
        is_combat=is_combat,
        turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=30),
        get_entity=lookup,
    )


def _noop_emit(event: Event) -> ActionResult:
    return ActionResult()


# ---------------------------------------------------------------------------
# Action cost
# ---------------------------------------------------------------------------


class TestLayOnHandsCost:
    def test_is_action(self) -> None:
        cost = action_cost(Action(name=ActionType.LAY_ON_HANDS))
        assert cost.actions == 1
        assert cost.bonus_actions == 0


# ---------------------------------------------------------------------------
# Handler — heal self
# ---------------------------------------------------------------------------


class TestLayOnHandsHealSelf:
    def test_heal_self(self) -> None:
        """Paladin with 20/25 HP, pool at 15. Lay on Hands amount=5 → HP=25, pool=10."""
        paladin = _paladin(current_hp=20, max_hp=25, level=3, pool_uses=15)
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 5})
        result = handle_lay_on_hands(paladin, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success
        assert paladin.current_hp == 25
        # Pool decremented by amount spent
        pool = next(p for p in paladin.resource_pools if p.id == "lay_on_hands")
        assert pool.current_uses == 10

    def test_heal_self_implicit_target(self) -> None:
        """No target_id means heal self."""
        paladin = _paladin(current_hp=15, max_hp=25, level=1, pool_uses=5)
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 3})
        result = handle_lay_on_hands(paladin, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success
        assert paladin.current_hp == 18


# ---------------------------------------------------------------------------
# Handler — heal ally
# ---------------------------------------------------------------------------


class TestLayOnHandsHealAlly:
    def test_heal_ally(self) -> None:
        """Paladin targets ally with 10/20 HP. amount=8 → ally HP=18, pool -= 8."""
        paladin = _paladin(current_hp=25, max_hp=25, level=3, pool_uses=15)
        ally = _ally(current_hp=10, max_hp=20)
        entities = {"paladin": paladin, "ally": ally}
        action = Action(name=ActionType.LAY_ON_HANDS, params={"target_id": "ally", "amount": 8})
        result = handle_lay_on_hands(paladin, action, _noop_emit, _ctx(entities=entities), None)  # type: ignore[arg-type]
        assert result.success
        assert ally.current_hp == 18
        pool = next(p for p in paladin.resource_pools if p.id == "lay_on_hands")
        assert pool.current_uses == 7


# ---------------------------------------------------------------------------
# Handler — edge cases
# ---------------------------------------------------------------------------


class TestLayOnHandsEdgeCases:
    def test_overheal_clamps(self) -> None:
        """Target at 18/20 HP, amount=10. Heals only 2, pool still decrements by 10."""
        paladin = _paladin(current_hp=18, max_hp=20, level=3, pool_uses=15)
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 10})
        result = handle_lay_on_hands(paladin, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success
        assert paladin.current_hp == 20
        pool = next(p for p in paladin.resource_pools if p.id == "lay_on_hands")
        assert pool.current_uses == 5

    def test_pool_exhausted(self) -> None:
        """Pool at 0 → error."""
        paladin = _paladin(pool_uses=0)
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 1})
        result = handle_lay_on_hands(paladin, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False

    def test_insufficient_pool(self) -> None:
        """Pool at 3, amount=5 → error."""
        paladin = _paladin(pool_uses=3)
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 5})
        result = handle_lay_on_hands(paladin, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False

    def test_non_paladin_fails(self) -> None:
        """Fighter trying Lay on Hands → error."""
        fighter = Character(
            id="fighter",
            name="Fighter",
            location_id="arena",
            max_hp=20,
            current_hp=10,
            ac=16,
            race=Race.HUMAN,
            char_class=CharClass.FIGHTER,
            resource_pools=[ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)],
        )
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 5})
        result = handle_lay_on_hands(fighter, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False

    def test_plain_creature_fails(self) -> None:
        """Non-Character creature → error."""
        creature = Creature(id="wolf", name="Wolf", location_id="arena", max_hp=10, current_hp=5, ac=13)
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 1})
        result = handle_lay_on_hands(creature, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success is False


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class TestLayOnHandsProvider:
    def test_available_for_paladin_with_resource(self) -> None:
        paladin = _paladin(pool_uses=5)
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(paladin, _ctx())
        assert ActionType.LAY_ON_HANDS in actions

    def test_not_available_when_exhausted(self) -> None:
        paladin = _paladin(pool_uses=0)
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(paladin, _ctx())
        assert ActionType.LAY_ON_HANDS not in actions

    def test_not_available_for_fighter(self) -> None:
        fighter = Character(
            id="fighter",
            name="Fighter",
            location_id="arena",
            max_hp=20,
            current_hp=10,
            ac=16,
            race=Race.HUMAN,
            char_class=CharClass.FIGHTER,
            resource_pools=[ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)],
        )
        provider = ClassFeatureActionProvider()
        actions = provider.get_action_types(fighter, _ctx())
        assert ActionType.LAY_ON_HANDS not in actions


# ---------------------------------------------------------------------------
# Full chain: heal + rest recovery
# ---------------------------------------------------------------------------


class TestLayOnHandsRestRecovery:
    def test_spend_all_then_long_rest_recovers(self) -> None:
        """Spend entire pool, long rest, pool back to max, can heal again."""
        paladin = _paladin(current_hp=20, max_hp=25, level=1, pool_uses=5)

        # Spend the full pool
        use_resource(paladin, "lay_on_hands", amount=5)
        assert not has_resource(paladin, "lay_on_hands")

        # Long rest resets it
        reset_ids = reset_resources(paladin, RestType.LONG_REST)
        assert "lay_on_hands" in reset_ids

        pool = next(p for p in paladin.resource_pools if p.id == "lay_on_hands")
        assert pool.current_uses == 5

        # Can heal again
        paladin.current_hp = 20
        action = Action(name=ActionType.LAY_ON_HANDS, params={"amount": 3})
        result = handle_lay_on_hands(paladin, action, _noop_emit, _ctx(), None)  # type: ignore[arg-type]
        assert result.success
        assert paladin.current_hp == 23
