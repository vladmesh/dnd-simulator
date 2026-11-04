"""Tests for attack resolution through EntitiesLayer.handle_event and its helper module."""

from __future__ import annotations

import random

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.combat import BattleMap, CombatState, Position, Wall
from dnd_simulator.core.events import AttackRequestedPayload, EntityMovePayload
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
from dnd_simulator.core.modifiers import AttackModifiers, RollComponent
from dnd_simulator.core.rolls import D20Result, DiceResult, DieRoll
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.rules.checks import CheckResult
from dnd_simulator.rules.combat import AttackResult, DamageResult
from dnd_simulator.rules.handlers.attack_resolution import (
    build_attack_event,
    build_damage_components,
    resolve_combat_move,
    roll_attack_dice,
)


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _sword() -> Attack:
    return Attack(
        name="longsword",
        ability=Ability.STR,
        damage=(DamageComponent("1d8", DamageType.SLASHING),),
    )


def _attack_event(attacker_id: str = "attacker", target_id: str = "target") -> Event:
    return Event(
        event_type=EventType.ENTITY_ATTACK_REQUESTED,
        source_layer="entities",
        data=AttackRequestedPayload(**{"attacker_id": attacker_id, "target_id": target_id}),
    )


def _place_melee(layer: EntitiesLayer, location_id: str) -> None:
    """After combat starts, place attacker and target within melee range."""
    combat = layer.get_combat(location_id)
    if combat:
        combat.battle_map.set_position("attacker", Position(30, 30))
        combat.battle_map.set_position("target", Position(35, 30))


class TestAttackResolution:
    def test_attack_reduces_target_hp(self) -> None:
        scores = AbilityScores()
        scores[Ability.STR] = 18  # +4 modifier, should hit AC 10 most of the time
        attacker = Character(
            id="attacker", name="Fighter", location_id="r1", ability_scores=scores, attacks=(_sword(),)
        )
        target = Character(id="target", name="Goblin", location_id="r1", max_hp=20, current_hp=20, ac=5)
        layer = EntitiesLayer(entities=[attacker, target])

        # Run many attacks — at least some should hit
        hits = 0
        for i in range(20):
            target.current_hp = 20  # reset
            result = layer.handle_event(_attack_event(), _noop_query_fn, _noop_emit_fn)
            if i == 0:
                _place_melee(layer, "r1")  # fix positions after first attack starts combat
                continue
            assert result.success
            if target.current_hp < 20:
                hits += 1
        assert hits > 0, "No attacks hit in 20 tries"

    def test_attack_logs_to_region(self) -> None:
        attacker = Character(id="attacker", name="Fighter", location_id="r1", attacks=(_sword(),))
        target = Character(id="target", name="Goblin", location_id="r1", max_hp=20, current_hp=20, ac=5)
        layer = EntitiesLayer(entities=[attacker, target])

        layer.handle_event(_attack_event(), _noop_query_fn, _noop_emit_fn)
        _place_melee(layer, "r1")
        layer.handle_event(_attack_event(), _noop_query_fn, _noop_emit_fn)

        log = layer.get_perceived_log(target)
        assert len(log) >= 2  # combat_started + attack
        assert "Combat started" in log[0]
        assert any("attacks you" in line for line in log)

    def test_death_generates_event(self) -> None:
        attacker = Character(id="attacker", name="Fighter", location_id="r1", attacks=(_sword(),))
        target = Character(id="target", name="Goblin", location_id="r1", max_hp=1, current_hp=1, ac=1)
        layer = EntitiesLayer(entities=[attacker, target])

        # First attack starts combat — fix positions
        layer.handle_event(_attack_event(), _noop_query_fn, _noop_emit_fn)
        _place_melee(layer, "r1")

        # With AC 1, should hit easily; 1 HP means any damage kills
        result: ActionResult = ActionResult()
        for _ in range(20):
            target.current_hp = 1
            result = layer.handle_event(_attack_event(), _noop_query_fn, _noop_emit_fn)
            if not result.success:
                continue
            if result.events:
                break

        death_events = [e for e in result.events if e.event_type == EventType.ENTITY_DIED]
        assert len(death_events) == 1
        assert death_events[0].data.entity_id == "target"
        assert target.is_alive is False

    def test_unarmed_strike_when_no_weapons(self) -> None:
        """Creatures with no attacks fall back to unarmed strike (1 bludgeoning)."""
        scores = AbilityScores()
        scores[Ability.STR] = 18  # +4 modifier, should hit AC 5 easily
        attacker = Character(id="attacker", name="Monk", location_id="r1", attacks=(), ability_scores=scores)
        target = Character(id="target", name="Goblin", location_id="r1", max_hp=20, current_hp=20, ac=5)
        layer = EntitiesLayer(entities=[attacker, target])

        layer.handle_event(_attack_event(), _noop_query_fn, _noop_emit_fn)  # start combat
        _place_melee(layer, "r1")

        hits = 0
        for _ in range(20):
            target.current_hp = 20
            result = layer.handle_event(_attack_event(), _noop_query_fn, _noop_emit_fn)
            assert result.success  # unarmed strike always valid
            if target.current_hp < 20:
                hits += 1
        assert hits > 0, "No unarmed strikes hit in 20 tries"

    def test_nonexistent_target_returns_error(self) -> None:
        attacker = Character(id="attacker", name="Fighter", location_id="r1", attacks=(_sword(),))
        layer = EntitiesLayer(entities=[attacker])

        result = layer.handle_event(_attack_event(target_id="nonexistent"), _noop_query_fn, _noop_emit_fn)
        assert not result.success
        assert "nonexistent" in result.error

    # cross_region, dead_target, and out_of_reach are now tested via
    # the validator in tests/test_action_dispatcher.py::TestTargetValidation
    # and TestReachValidation. CombatManager only does mechanics.


def _mods(
    *,
    dice_bonuses: tuple[str, ...] = (),
    roll_components: tuple[RollComponent, ...] = (),
    advantage: bool = False,
    disadvantage: bool = False,
    target_ac: int = 12,
) -> AttackModifiers:
    return AttackModifiers(
        modifier=3,
        damage_bonus=0,
        dice_bonuses=dice_bonuses,
        advantage=advantage,
        disadvantage=disadvantage,
        force_crit=False,
        target_ac=target_ac,
        roll_components=roll_components,
    )


def _result(
    *,
    natural: int,
    total: int,
    hit: bool,
    critical: bool = False,
    alt: int | None = None,
    damage: tuple[DamageResult, ...] = (),
) -> AttackResult:
    d20 = D20Result(die=DieRoll(sides=20, result=natural), alt=DieRoll(sides=20, result=alt) if alt else None)
    check = CheckResult(success=hit, roll=natural, total=total, dc=12, critical=critical, d20=d20)
    return AttackResult(
        hit=hit,
        critical=critical,
        attack_check=check,
        damage=damage,
        total_damage=sum(d.amount for d in damage),
    )


class TestBuildAttackEvent:
    def test_critical_hit_with_advantage_keeps_alt_die_and_flat_components(self) -> None:
        mods = _mods(
            advantage=True,
            roll_components=(RollComponent("ability", 3), RollComponent("bless", 0, "1d4")),
            target_ac=15,
        )
        rolled = [RollComponent("bless", 2, "1d4")]
        payload = build_attack_event(
            "a", "t", _sword(), _result(natural=20, alt=7, total=25, hit=True, critical=True), mods, rolled
        )

        assert payload.hit is True
        assert payload.critical is True
        assert payload.ac == 15
        assert payload.weapon == "longsword"
        assert payload.attack_roll.natural == 20
        roll = payload.attack_roll
        assert roll.advantage is True
        assert roll.disadvantage is False
        assert roll.d20 == {"result": 20, "sides": 20}
        assert roll.d20_alt == {"result": 7, "sides": 20}
        # Unrolled dice component is replaced by its rolled counterpart, flat ones are kept.
        assert [(c.source, c.value, c.dice) for c in roll.components] == [("ability", 3, ""), ("bless", 2, "1d4")]

    def test_natural_one_miss_without_alt_die(self) -> None:
        payload = build_attack_event(
            "a", "t", _sword(), _result(natural=1, total=4, hit=False, critical=True), _mods(), []
        )

        assert payload.hit is False
        assert payload.attack_roll.d20 == {"result": 1, "sides": 20}
        assert payload.attack_roll.d20_alt is None
        assert payload.attack_roll.components == ()


class TestBuildDamageComponents:
    def test_rerolled_die_records_original_and_extra_components_use_primary_type(self) -> None:
        dice = DiceResult(expression="2d6", dice=(DieRoll(6, 5, original=1), DieRoll(6, 4)), flat=0, total=9)
        damage = (
            DamageResult(9, DamageType.SLASHING, source="weapon", dice="2d6", dice_result=dice),
            DamageResult(3, DamageType.FIRE, source="flame", dice="3"),
        )
        components = build_damage_components(
            _result(natural=15, total=18, hit=True, damage=damage), [RollComponent("dueling", 2)]
        )

        assert components[0].dice_detail == ({"sides": 6, "result": 5, "original": 1}, {"sides": 6, "result": 4})
        assert components[0].type == "slashing"
        assert components[1].dice_detail == ()
        assert components[1].type == "fire"
        assert (components[2].source, components[2].amount, components[2].type) == ("dueling", 2, "slashing")

    def test_miss_has_no_damage_and_flat_components_default_to_bludgeoning(self) -> None:
        assert build_damage_components(_result(natural=2, total=5, hit=False), ()) == ()
        components = build_damage_components(_result(natural=2, total=5, hit=False), (RollComponent("rage", 2),))
        assert len(components) == 1
        assert components[0].type == "bludgeoning"
        assert components[0].dice == ""


class TestRollAttackDice:
    def test_no_dice_bonuses_rolls_nothing(self) -> None:
        mods = _mods(roll_components=(RollComponent("ability", 3),))
        assert roll_attack_dice(mods, rng=random.Random(1)) == ([], 0)

    def test_rolls_only_dice_components_deterministically(self) -> None:
        mods = _mods(
            dice_bonuses=("1d4", "1d6"),
            roll_components=(
                RollComponent("ability", 3),
                RollComponent("bless", 0, "1d4"),
                RollComponent("guidance", 0, "1d6"),
            ),
        )
        rolled, total = roll_attack_dice(mods, rng=random.Random(7))
        again, again_total = roll_attack_dice(mods, rng=random.Random(7))

        assert rolled == again
        assert total == again_total == sum(rc.value for rc in rolled)
        assert [(rc.source, rc.dice) for rc in rolled] == [("bless", "1d4"), ("guidance", "1d6")]
        assert 1 <= rolled[0].value <= 4
        assert 1 <= rolled[1].value <= 6


def _move_event(entity_id: str, direction: str | None, ft: int = 5) -> Event:
    return Event(
        event_type=EventType.ENTITY_MOVE,
        source_layer="entities",
        data=EntityMovePayload(entity_id=entity_id, direction=direction, ft=ft),
    )


def _combat(positions: dict[str, Position], walls: list[Wall] | None = None) -> CombatState:
    return CombatState(
        location_id="r1",
        battle_map=BattleMap(width=60, height=60, positions=dict(positions), walls=walls or []),
    )


class TestResolveCombatMove:
    def _hero(self) -> Character:
        return Character(id="hero", name="Hero", location_id="r1")

    def test_creature_not_on_map_fails(self) -> None:
        recorded: list[Event] = []
        result = resolve_combat_move(self._hero(), _move_event("hero", "north"), _combat({}), recorded.append)
        assert not result.success
        assert result.error
        assert recorded == []

    def test_blocked_by_occupied_cell(self) -> None:
        combat = _combat({"hero": Position(30, 30), "ogre": Position(30, 35)})
        recorded: list[Event] = []
        result = resolve_combat_move(self._hero(), _move_event("hero", "north"), combat, recorded.append)
        assert not result.success
        assert result.error
        assert combat.battle_map.get_position("hero") == Position(30, 30)
        assert recorded == []

    def test_unknown_or_missing_direction_is_blocked(self) -> None:
        combat = _combat({"hero": Position(30, 30)})
        for direction in (None, "up"):
            result = resolve_combat_move(self._hero(), _move_event("hero", direction), combat, lambda _e: None)
            assert not result.success
        assert combat.battle_map.get_position("hero") == Position(30, 30)

    def test_successful_move_updates_position_and_records_event(self) -> None:
        combat = _combat({"hero": Position(30, 30)})
        recorded: list[Event] = []
        result = resolve_combat_move(self._hero(), _move_event("hero", "east", ft=10), combat, recorded.append)

        assert result.success
        assert combat.battle_map.get_position("hero") == Position(40, 30)
        assert len(recorded) == 1
        event = recorded[0]
        assert event.event_type == EventType.ENTITY_MOVE
        data = event.payload
        assert isinstance(data, EntityMovePayload)
        assert (data.entity_id, data.location_id) == ("hero", "r1")
        assert (data.from_x, data.from_y, data.to_x, data.to_y) == (30, 30, 40, 30)
        assert data.distance_ft == 10
