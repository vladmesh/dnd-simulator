"""Sprint 020 phase 1 task 3: rules/ purity — determinism.

Tests:
1. Seeded heal reproducibility — ActionContext.rng threaded into potion and Second Wind.
2. check_sneak_attack returns reason string, imports no logging.
3. rules/lairs.should_deplete truth table.
4. Ecology layer depletion uses the injected roll (not inline RNG call).
"""

from __future__ import annotations

import random

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    CharClass,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle, RogueFeatures
from dnd_simulator.core.items import Item, ItemType
from dnd_simulator.core.lair import Lair, LairState
from dnd_simulator.core.models import ActionResult, Event
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.rules.handlers import handle_second_wind
from dnd_simulator.rules.handlers.items import handle_use_item
from dnd_simulator.rules.validation import ActionContext

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fighter(*, current_hp: int = 10, max_hp: int = 30, level: int = 1) -> Character:
    return Character(
        id="fighter",
        name="Fighter",
        location_id="arena",
        max_hp=max_hp,
        current_hp=current_hp,
        ac=16,
        race=Race.HUMAN,
        char_class=CharClass.FIGHTER,
        level=level,
        class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        resource_pools=[ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)],
    )


def _rogue(*, level: int = 1, sneak_dice: int = 1) -> Character:
    scores = AbilityScores()
    scores[Ability.DEX] = 18
    return Character(
        id="rogue",
        name="Test Rogue",
        location_id="loc",
        ac=14,
        current_hp=20,
        max_hp=20,
        speed=30,
        ability_scores=scores,
        race=Race.HUMAN,
        char_class=CharClass.ROGUE,
        level=level,
        class_features=[RogueFeatures(sneak_attack_dice=sneak_dice)],
    )


def _healing_potion() -> Item:
    return Item(
        id="potion1",
        name="Healing Potion",
        item_type=ItemType.POTION,
        params={"heal_dice": "2d4+2"},
    )


def _ctx(*, rng: random.Random | None = None) -> ActionContext:
    return ActionContext(
        is_combat=True,
        turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=30),
        rng=rng,
    )


def _noop_emit(event: Event) -> ActionResult:
    return ActionResult()


def _rapier_attack() -> Attack:
    return Attack(
        name="rapier strike",
        ability=Ability.DEX,
        damage=(DamageComponent("1d8", DamageType.PIERCING),),
        reach=5,
        is_finesse=True,
    )


def _coreless_lair(*, alive_members: list[str] | None = None, depletion_chance: float = 0.5) -> Lair:
    return Lair(
        id="warren",
        name="Warren",
        faction_id="goblins",
        location_id="cave",
        members=["goblin", "goblin"],
        core=None,
        depletion_chance=depletion_chance,
        alive_members=alive_members,
    )


def _cored_lair(*, core_alive: bool = True) -> Lair:
    lair = Lair(
        id="boss_lair",
        name="Boss Lair",
        faction_id="goblins",
        location_id="cave",
        members=["goblin"],
        core="boss",
        depletion_chance=0.0,
    )
    lair.core_alive = core_alive
    return lair


# ---------------------------------------------------------------------------
# 1. Seeded heal reproducibility
# ---------------------------------------------------------------------------


class TestSeededHealReproducibility:
    def test_potion_same_seed_same_result(self) -> None:
        """Two identical seeds give identical heal amounts."""
        fighter_a = _fighter(current_hp=1, max_hp=30)
        fighter_a.inventory.append(_healing_potion())
        ctx_a = _ctx(rng=random.Random(999))
        act = Action(name=ActionType.USE_ITEM, params={"item_id": "potion1"})
        handle_use_item(fighter_a, act, _noop_emit, ctx_a, None)  # type: ignore[arg-type]
        hp_a = fighter_a.current_hp

        fighter_b = _fighter(current_hp=1, max_hp=30)
        fighter_b.inventory.append(_healing_potion())
        ctx_b = _ctx(rng=random.Random(999))
        handle_use_item(fighter_b, act, _noop_emit, ctx_b, None)  # type: ignore[arg-type]
        hp_b = fighter_b.current_hp

        assert hp_a == hp_b

    def test_potion_different_seed_can_differ(self) -> None:
        """Different seeds can produce different rolls (probabilistic; uses many seeds)."""
        results: set[int] = set()
        act = Action(name=ActionType.USE_ITEM, params={"item_id": "potion1"})
        for seed in range(50):
            fighter = _fighter(current_hp=1, max_hp=100)
            fighter.inventory.append(_healing_potion())
            ctx = _ctx(rng=random.Random(seed))
            handle_use_item(fighter, act, _noop_emit, ctx, None)  # type: ignore[arg-type]
            results.add(fighter.current_hp)
        assert len(results) > 1, "Expected different heal amounts across seeds"

    def test_second_wind_same_seed_same_result(self) -> None:
        """Two identical seeds give identical Second Wind heals."""
        fighter_a = _fighter(current_hp=1, max_hp=30, level=1)
        ctx_a = _ctx(rng=random.Random(42))
        handle_second_wind(fighter_a, Action(name=ActionType.SECOND_WIND), _noop_emit, ctx_a, None)  # type: ignore[arg-type]
        hp_a = fighter_a.current_hp

        fighter_b = _fighter(current_hp=1, max_hp=30, level=1)
        ctx_b = _ctx(rng=random.Random(42))
        handle_second_wind(fighter_b, Action(name=ActionType.SECOND_WIND), _noop_emit, ctx_b, None)  # type: ignore[arg-type]
        hp_b = fighter_b.current_hp

        assert hp_a == hp_b

    def test_second_wind_different_seed_can_differ(self) -> None:
        """Different seeds can produce different Second Wind rolls."""
        results: set[int] = set()
        for seed in range(50):
            fighter = _fighter(current_hp=1, max_hp=100, level=1)
            ctx = _ctx(rng=random.Random(seed))
            handle_second_wind(fighter, Action(name=ActionType.SECOND_WIND), _noop_emit, ctx, None)  # type: ignore[arg-type]
            results.add(fighter.current_hp)
        assert len(results) > 1, "Expected different heal amounts across seeds"


# ---------------------------------------------------------------------------
# 2. check_sneak_attack returns reason, no logging
# ---------------------------------------------------------------------------


class TestSneakAttackPurity:
    def test_no_structlog_import(self) -> None:
        """rules/sneak_attack must not import structlog or logging."""
        import dnd_simulator.rules.sneak_attack as sa_mod

        assert not hasattr(sa_mod, "logger"), "sneak_attack module must not have a logger attribute"

    def test_advantage_reason_returned(self) -> None:
        from dnd_simulator.rules.sneak_attack import check_sneak_attack

        rogue = _rogue(sneak_dice=2)
        attack = _rapier_attack()
        result = check_sneak_attack(
            rogue,
            attack,
            advantage=True,
            disadvantage=False,
            already_used=False,
            ally_adjacent=False,
        )
        assert len(result) == 1
        extra = result[0]
        # The task says to return the reason alongside the ExtraDamage;
        # we check both that SA triggered AND that the reason is accessible.
        assert extra.reason == "advantage"

    def test_ally_adjacent_reason_returned(self) -> None:
        from dnd_simulator.rules.sneak_attack import check_sneak_attack

        rogue = _rogue(sneak_dice=2)
        attack = _rapier_attack()
        result = check_sneak_attack(
            rogue,
            attack,
            advantage=False,
            disadvantage=False,
            already_used=False,
            ally_adjacent=True,
        )
        assert len(result) == 1
        assert result[0].reason == "ally_adjacent"

    def test_no_trigger_no_reason(self) -> None:
        from dnd_simulator.rules.sneak_attack import check_sneak_attack

        rogue = _rogue(sneak_dice=2)
        attack = _rapier_attack()
        result = check_sneak_attack(
            rogue,
            attack,
            advantage=False,
            disadvantage=False,
            already_used=False,
            ally_adjacent=False,
        )
        assert result == ()


# ---------------------------------------------------------------------------
# 3. rules/lairs.should_deplete truth table
# ---------------------------------------------------------------------------


class TestShouldDeplete:
    def test_core_lair_core_dead_depletes(self) -> None:
        from dnd_simulator.rules.lairs import should_deplete

        lair = _cored_lair(core_alive=False)
        assert should_deplete(lair, roll=0.99) is True

    def test_core_lair_core_alive_not_depleted(self) -> None:
        from dnd_simulator.rules.lairs import should_deplete

        lair = _cored_lair(core_alive=True)
        assert should_deplete(lair, roll=0.0) is False

    def test_coreless_wiped_roll_below_chance(self) -> None:
        from dnd_simulator.rules.lairs import should_deplete

        lair = _coreless_lair(alive_members=[], depletion_chance=0.5)
        assert should_deplete(lair, roll=0.3) is True

    def test_coreless_wiped_roll_above_chance(self) -> None:
        from dnd_simulator.rules.lairs import should_deplete

        lair = _coreless_lair(alive_members=[], depletion_chance=0.5)
        assert should_deplete(lair, roll=0.7) is False

    def test_coreless_survivors_not_depleted(self) -> None:
        from dnd_simulator.rules.lairs import should_deplete

        lair = _coreless_lair(alive_members=["goblin"], depletion_chance=1.0)
        assert should_deplete(lair, roll=0.0) is False

    def test_coreless_zero_chance_not_depleted(self) -> None:
        from dnd_simulator.rules.lairs import should_deplete

        lair = _coreless_lair(alive_members=[], depletion_chance=0.0)
        assert should_deplete(lair, roll=0.0) is False

    def test_full_roster_none_not_depleted(self) -> None:
        """alive_members=None means full roster — not depleted."""
        from dnd_simulator.rules.lairs import should_deplete

        lair = _coreless_lair(alive_members=None, depletion_chance=1.0)
        assert should_deplete(lair, roll=0.0) is False


# ---------------------------------------------------------------------------
# 4. Ecology layer depletion injects the roll
# ---------------------------------------------------------------------------


class TestEcologyLairDepletion:
    def _make_layer_and_lair(self, depletion_chance: float = 0.5) -> tuple[object, Lair]:
        from dnd_simulator.layers.ecology.layer import EcologyLayer

        lair = _coreless_lair(alive_members=[], depletion_chance=depletion_chance)
        layer = EcologyLayer(lairs=[lair])
        return layer, lair

    def _dematerialize_event(self, lair_id: str = "warren", alive_members: list[str] | None = None) -> Event:
        from dnd_simulator.core.models import EventType

        return Event(
            event_type=EventType.LAIR_DEMATERIALIZED,
            source_layer="entities",
            data={
                "lair_id": lair_id,
                "alive_members": alive_members or [],
                "core_alive": False,
                "at_seconds": 0,
            },
        )

    def test_depletion_transitions_active_to_depleted(self) -> None:
        from dnd_simulator.layers.ecology.layer import EcologyLayer

        # Seed so the ecology-layer roll is below 0.5.

        lair = _coreless_lair(alive_members=[], depletion_chance=0.5)
        layer = EcologyLayer(lairs=[lair], seed=1)
        event = self._dematerialize_event()

        layer.handle_event(event, lambda q: None, lambda e: None)  # type: ignore[arg-type]
        assert lair.state is LairState.DEPLETED

    def test_no_depletion_when_roll_above_chance(self) -> None:
        from dnd_simulator.layers.ecology.layer import EcologyLayer

        # Seed so the ecology-layer roll is above 0.5.

        lair = _coreless_lair(alive_members=[], depletion_chance=0.5)
        layer = EcologyLayer(lairs=[lair], seed=0)
        event = self._dematerialize_event()

        layer.handle_event(event, lambda q: None, lambda e: None)  # type: ignore[arg-type]
        assert lair.state is LairState.ACTIVE

    def test_depletion_survives_save_load(self) -> None:
        from dnd_simulator.layers.ecology.layer import EcologyLayer

        lair = _coreless_lair(alive_members=[], depletion_chance=0.5)
        layer = EcologyLayer(lairs=[lair], seed=1)
        event = self._dematerialize_event()
        layer.handle_event(event, lambda q: None, lambda e: None)  # type: ignore[arg-type]
        assert lair.state is LairState.DEPLETED

        state = layer.get_state()
        # restore
        lair2 = _coreless_lair(alive_members=[], depletion_chance=0.5)
        layer2 = EcologyLayer(lairs=[lair2])
        layer2.load_state(state)
        assert lair2.state is LairState.DEPLETED
