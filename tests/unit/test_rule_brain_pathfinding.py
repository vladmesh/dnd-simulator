"""RuleBrain walks a real path to an attack cell (dnd-simulator-278).

The brain used to step 5 ft by compass direction and bumped into allies and walls: three
failed moves per turn, then the ``consecutive_failures_end_turn`` guard in ``Round`` ended
the turn. These scenarios run a full combat turn through ``Round`` and assert the turn has
no failed action at all.
"""

from __future__ import annotations

from collections.abc import MutableMapping
from itertools import pairwise
from typing import Any

import structlog

from dnd_simulator.core.action import Action, ActionType
from dnd_simulator.core.awareness import CombatAwareness, CombatEntity
from dnd_simulator.core.character import Ability, Attack, Creature, DamageComponent, DamageType
from dnd_simulator.core.combat import BattleMap, CombatState, Position, Wall
from dnd_simulator.core.location import Location, LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.round import Round
from dnd_simulator.rules.movement import grid_distance
from dnd_simulator.rules.rule_brain import RuleBrain

_CLUB = Attack(name="club", ability=Ability.STR, damage=(DamageComponent("1d4", DamageType.BLUDGEONING),), reach=5)


def _creature(cid: str, *, brain: RuleBrain | None = None) -> Creature:
    return Creature(
        id=cid,
        name=cid,
        location_id="cave",
        attacks=(_CLUB,),
        max_hp=500,
        current_hp=500,
        speed=30,
        brain=brain,
        in_combat=True,
    )


def _make_world(creatures: list[Creature]) -> tuple[World, EntitiesLayer]:
    region = Region(
        id="cave",
        name="Cave",
        terrain=TerrainType.MOUNTAINS,
        latitude=45.0,
        longitude=0.0,
        elevation=100,
        water_proximity=0.0,
        connections=[],
    )
    geography = GeographyLayer(regions=[region])
    settlements = SettlementsLayer(settlements=[], region_terrains={"cave": TerrainType.MOUNTAINS})
    politics = PoliticsLayer(
        nations=[],
        region_terrains={"cave": TerrainType.MOUNTAINS},
        region_adjacency={},
        region_income_fn=settlements.get_region_income,
    )
    entities = EntitiesLayer(entities=list(creatures))
    world = World(
        layers=[geography, politics, settlements, entities],
        time=GameDateTime(year=1, month=1, day=1, hour=10),
        location_graph=LocationGraph([Location(id="cave", name="Cave", region_id="cave")]),
    )
    return world, entities


def _start_combat(
    entities: EntitiesLayer,
    placement: dict[str, tuple[tuple[int, int], int]],
    walls: list[Wall] | None = None,
) -> CombatState:
    """Place each creature at its cell on its side and register the fight at the cave."""
    bm = BattleMap(width=60, height=60, walls=list(walls or []))
    combat = CombatState(location_id="cave", turn_order=list(placement), battle_map=bm)
    for cid, ((x, y), side) in placement.items():
        bm.set_position(cid, Position(x, y))
        combat.entity_to_side[cid] = side
        combat.sides.setdefault(side, set()).add(cid)
    entities._combat._combats["cave"] = combat
    return combat


def _run_turn(
    world: World, entities: EntitiesLayer, actor: Creature
) -> tuple[list[Action], list[str], list[MutableMapping[str, Any]]]:
    """Run the actor's combat turn; return executed actions, every action error, and the captured logs."""
    game_round = Round(world, entities)
    errors: list[str] = []

    def on_action(_c: Creature, _a: Action, _b: TurnBudget | None, error: str = "") -> None:
        if error:
            errors.append(error)

    game_round.set_on_action(on_action)
    with structlog.testing.capture_logs() as logs:
        actions = game_round.run_combat_turn(
            actor, world.time, world.make_query_fn("entities"), world.make_emit_fn("entities")
        )
    return actions, errors, logs


def _assert_no_failures(errors: list[str], logs: list[MutableMapping[str, Any]]) -> None:
    assert errors == []
    events = [entry["event"] for entry in logs]
    assert "action_failed" not in events
    assert "consecutive_failures_end_turn" not in events


class TestTargetBehindAlly:
    def test_goes_around_the_ally_and_attacks(self) -> None:
        goblin = _creature("goblin", brain=RuleBrain())
        ally = _creature("ally")
        hero = _creature("hero")
        world, entities = _make_world([goblin, ally, hero])
        # Straight north from the goblin: its ally, then the hero.
        combat = _start_combat(entities, {"goblin": ((10, 10), 0), "ally": ((10, 15), 0), "hero": ((10, 20), 1)})

        actions, errors, logs = _run_turn(world, entities, goblin)

        _assert_no_failures(errors, logs)
        assert [a.name for a in actions] == [ActionType.MOVE_TO, ActionType.ATTACK]
        goblin_pos = combat.battle_map.get_position("goblin")
        assert goblin_pos is not None
        assert goblin_pos not in (Position(10, 10), Position(10, 15))
        assert grid_distance(goblin_pos, Position(10, 20)) <= 5

    def test_long_detour_moves_then_dashes_without_failures(self) -> None:
        """A wall of allies leaves only a long way round: move, Dash, move on — never a failed step."""
        goblin = _creature("goblin", brain=RuleBrain())
        allies = [_creature(f"ally{x}") for x in range(0, 61, 5) if x != 55]
        hero = _creature("hero")
        world, entities = _make_world([goblin, *allies, hero])
        # An ally line across y=15 with the only gap at x=55; the hero stands behind it.
        placement: dict[str, tuple[tuple[int, int], int]] = {"goblin": ((10, 10), 0)}
        placement.update({a.id: ((int(a.id[4:]), 15), 0) for a in allies})
        placement["hero"] = ((10, 25), 1)
        combat = _start_combat(entities, placement)

        actions, errors, logs = _run_turn(world, entities, goblin)

        _assert_no_failures(errors, logs)
        names = [a.name for a in actions]
        assert names[:3] == [ActionType.MOVE_TO, ActionType.DASH, ActionType.MOVE_TO]
        goblin_pos = combat.battle_map.get_position("goblin")
        assert goblin_pos is not None
        assert goblin_pos.y > 15  # went through the gap at x=55 instead of bumping into the line


class TestWallBetween:
    def test_routes_around_the_wall_and_attacks(self) -> None:
        goblin = _creature("goblin", brain=RuleBrain())
        hero = _creature("hero")
        world, entities = _make_world([goblin, hero])
        # The wall at x=20 blocks every east step for y < 20; the hero stands just past it.
        combat = _start_combat(
            entities,
            {"goblin": ((10, 10), 0), "hero": ((25, 10), 1)},
            walls=[Wall(x1=20, y1=0, x2=20, y2=20)],
        )

        actions, errors, logs = _run_turn(world, entities, goblin)

        _assert_no_failures(errors, logs)
        assert [a.name for a in actions] == [ActionType.MOVE_TO, ActionType.ATTACK]
        goblin_pos = combat.battle_map.get_position("goblin")
        assert goblin_pos is not None
        assert goblin_pos.x >= 20  # crossed to the hero's side of the wall
        assert grid_distance(goblin_pos, Position(25, 10)) <= 5


class TestEnclosedTarget:
    def test_walled_in_target_gets_a_dodge_not_failed_moves(self) -> None:
        goblin = _creature("goblin", brain=RuleBrain())
        hero = _creature("hero")
        world, entities = _make_world([goblin, hero])
        # A closed 3x3 room (cells 20..30) around the hero: no attack cell can be reached.
        room = [
            Wall(x1=20, y1=20, x2=20, y2=35),
            Wall(x1=35, y1=20, x2=35, y2=35),
            Wall(x1=20, y1=20, x2=35, y2=20),
            Wall(x1=20, y1=35, x2=35, y2=35),
        ]
        combat = _start_combat(entities, {"goblin": ((0, 0), 0), "hero": ((25, 25), 1)}, walls=room)

        actions, errors, logs = _run_turn(world, entities, goblin)

        _assert_no_failures(errors, logs)
        assert [a.name for a in actions] == [ActionType.DODGE]
        assert combat.battle_map.get_position("goblin") == Position(0, 0)

    def test_surrounded_target_switches_to_a_reachable_enemy(self) -> None:
        """The hero's own guards fill every cell around the hero: fight a guard instead."""
        goblin = _creature("goblin", brain=RuleBrain())
        hero = _creature("hero")
        rings = [(x, y) for x in (25, 30, 35) for y in (25, 30, 35) if (x, y) != (30, 30)]
        guards = [_creature(f"guard{i}") for i in range(len(rings))]
        world, entities = _make_world([goblin, hero, *guards])
        placement: dict[str, tuple[tuple[int, int], int]] = {"goblin": ((10, 30), 0), "hero": ((30, 30), 1)}
        placement.update({g.id: (cell, 1) for g, cell in zip(guards, rings, strict=True)})
        # The hero is badly wounded, so the goblin's scoring picks the hero first.
        hero.current_hp = 10
        _start_combat(entities, placement)

        actions, errors, logs = _run_turn(world, entities, goblin)

        _assert_no_failures(errors, logs)
        assert [a.name for a in actions] == [ActionType.MOVE_TO, ActionType.ATTACK]
        assert str(actions[1].params["target_id"]).startswith("guard")


class TestNoMapKnowledge:
    def test_brain_without_a_map_never_moves(self) -> None:
        """Awareness without map bounds gives no path: the brain must not guess a compass step."""
        goblin = _creature("goblin")
        awareness = CombatAwareness(
            self_hp=500,
            self_max_hp=500,
            self_ac=10,
            self_speed=30,
            self_weapon="club",
            self_weapon_damage="1d4",
            self_x=0,
            self_y=0,
            nearby=[CombatEntity(id="hero", description="Hero", is_hostile=True, distance_ft=30, x=30, y=0)],
            turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=30, reaction=1),
        )
        action = RuleBrain().choose_action(goblin, awareness, [])
        assert action.name not in (ActionType.MOVE, ActionType.MOVE_TO, ActionType.DASH)


def _ready_to_react(creature: Creature) -> Creature:
    """Give a bystander the reaction it would have mid-round, so leaving its reach provokes."""
    creature.turn_budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=30, reaction=1)
    creature.brain = RuleBrain()
    return creature


def _leaves_reach_of(path_cells: list[Position], reactor: Position, reach: int = 5) -> bool:
    return any(grid_distance(reactor, cur) <= reach < grid_distance(reactor, nxt) for cur, nxt in pairwise(path_cells))


class TestAvoidsOpportunityAttacks:
    """Issue combat-pathfinding-avoidance: an approach must not walk out of a bystander's reach needlessly."""

    def test_takes_a_safe_detour_past_a_bystander(self) -> None:
        goblin = _creature("goblin", brain=RuleBrain())
        hero = _creature("hero")
        guard = _ready_to_react(_creature("guard"))
        world, entities = _make_world([goblin, hero, guard])
        # The straight line to the hero (y=10) passes through the guard's reach and out of it again at x=35;
        # a walk along y=5 stays clear of it and costs no more.
        hero.current_hp = 10  # wounded: the goblin's scoring targets the hero, not the nearer guard
        combat = _start_combat(entities, {"goblin": ((10, 10), 0), "hero": ((40, 10), 1), "guard": ((25, 15), 1)})

        actions, errors, logs = _run_turn(world, entities, goblin)

        _assert_no_failures(errors, logs)
        assert guard.turn_budget is not None
        assert guard.turn_budget.reaction == 1  # no opportunity attack was taken
        moves = [a for a in actions if a.name == ActionType.MOVE_TO]
        assert moves
        cells = [Position(10, 10), *(Position(int(str(a.params["x"])), int(str(a.params["y"]))) for a in moves)]
        assert not _leaves_reach_of(cells, Position(25, 15))
        assert actions[-1].name == ActionType.ATTACK
        assert actions[-1].params["target_id"] == "hero"
        goblin_pos = combat.battle_map.get_position("goblin")
        assert goblin_pos is not None
        assert grid_distance(goblin_pos, Position(40, 10)) <= 5

    def test_engaged_mover_has_no_safe_path_and_keeps_the_old_route(self) -> None:
        """Every step away from an adjacent guard provokes: the route is the one taken without the threat."""

        def final_cell(guard_can_react: bool) -> tuple[Position | None, int]:
            goblin = _creature("goblin", brain=RuleBrain())
            hero = _creature("hero")
            guard = _creature("guard")
            if guard_can_react:
                _ready_to_react(guard)
            world, entities = _make_world([goblin, hero, guard])
            hero.current_hp = 10
            combat = _start_combat(entities, {"goblin": ((10, 10), 0), "hero": ((40, 10), 1), "guard": ((10, 15), 1)})
            actions, errors, logs = _run_turn(world, entities, goblin)
            _assert_no_failures(errors, logs)
            assert actions[0].name == ActionType.MOVE_TO
            reaction = guard.turn_budget.reaction if guard.turn_budget is not None else 1
            return combat.battle_map.get_position("goblin"), reaction

        threatened_cell, reaction_left = final_cell(guard_can_react=True)
        unthreatened_cell, _ = final_cell(guard_can_react=False)
        assert threatened_cell == unthreatened_cell
        assert threatened_cell is not None
        assert grid_distance(threatened_cell, Position(40, 10)) <= 5
        assert reaction_left == 0  # the unavoidable opportunity attack was taken

    def test_long_detour_is_not_taken(self) -> None:
        """A wall leaves only a long way round the guard: take the direct route and the opportunity attack."""
        goblin = _creature("goblin", brain=RuleBrain())
        hero = _creature("hero")
        guard = _ready_to_react(_creature("guard"))
        world, entities = _make_world([goblin, hero, guard])
        hero.current_hp = 10
        # Walls seal the cells south of y=10 east of x=20, so the only way round the guard is north of it:
        # 40 ft against the direct 25 ft, more than the detour the goblin accepts.
        combat = _start_combat(
            entities,
            {"goblin": ((10, 10), 0), "hero": ((40, 10), 1), "guard": ((25, 15), 1)},
            walls=[Wall(x1=20, y1=0, x2=20, y2=10), Wall(x1=20, y1=10, x2=65, y2=10)],
        )

        _actions, errors, logs = _run_turn(world, entities, goblin)

        _assert_no_failures(errors, logs)
        assert guard.turn_budget is not None
        assert guard.turn_budget.reaction == 0
        goblin_pos = combat.battle_map.get_position("goblin")
        assert goblin_pos is not None
        assert grid_distance(goblin_pos, Position(40, 10)) <= 5

    def test_long_reach_target_is_still_approached(self) -> None:
        """Entering a reach never provokes: the target's own long reach does not stop the approach."""
        goblin = _creature("goblin", brain=RuleBrain())
        pike = Attack(
            name="pike", ability=Ability.STR, damage=(DamageComponent("1d10", DamageType.PIERCING),), reach=10
        )
        hero = _ready_to_react(_creature("hero"))
        hero.attacks = (pike,)
        world, entities = _make_world([goblin, hero])
        combat = _start_combat(entities, {"goblin": ((10, 10), 0), "hero": ((35, 10), 1)})

        actions, errors, logs = _run_turn(world, entities, goblin)

        _assert_no_failures(errors, logs)
        assert [a.name for a in actions] == [ActionType.MOVE_TO, ActionType.ATTACK]
        assert hero.turn_budget is not None
        assert hero.turn_budget.reaction == 1
        goblin_pos = combat.battle_map.get_position("goblin")
        assert goblin_pos is not None
        assert grid_distance(goblin_pos, Position(35, 10)) <= 5
