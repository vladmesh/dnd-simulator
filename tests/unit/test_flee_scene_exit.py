"""Flee as a real exit from the scene (dnd-simulator-275).

Covers the eligibility rule (no enemy within 15 ft, one rule for every brain), the
player's and NPCs' flee as one travel edge, anonymous fleers returning to their squad
as survivors, the abandoned scene after the player leaves, save/load after a flee, and
the invariant: no active creature stands at a combat location outside that combat.

The scenario tests run a full in-process World (geography, politics, settlements,
ecology, entities) through ``Round`` with seeded RNGs.
"""

from __future__ import annotations

import json
import random

import pytest

from dnd_simulator.core.action import END_TURN, Action, ActionType
from dnd_simulator.core.awareness import (
    CombatAwareness,
    CombatEntity,
    FleeDestination,
    FleeStatus,
    PeacefulAwareness,
    PerceivedEvent,
)
from dnd_simulator.core.brain import Brain
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    CharClass,
    Creature,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.class_features import FighterFeatures, FightingStyle
from dnd_simulator.core.combat import BattleMap, CombatState, Position
from dnd_simulator.core.events import EntityDiedPayload
from dnd_simulator.core.intent import TravelIntent
from dnd_simulator.core.lair import Lair, LairMemberRole, LairOrigin
from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.models import Event, EventType, FactionRelation, GameDateTime, TimeDelta
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType
from dnd_simulator.core.turn_budget import TurnBudget
from dnd_simulator.core.world import World
from dnd_simulator.i18n import language_context
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.round import Round
from dnd_simulator.rules.flee import (
    FLEE_SAFE_DISTANCE_FT,
    FleeBlock,
    choose_flee_destination,
    flee_blocker,
    flee_status,
)
from dnd_simulator.rules.rule_brain import RuleBrain
from dnd_simulator.rules.validation import ActionContext, validate_action

# ---------------------------------------------------------------------------
# Pure eligibility rule
# ---------------------------------------------------------------------------


def _fighter(cid: str, faction: str = "") -> Creature:
    return Creature(id=cid, name=cid, location_id="arena", faction_id=faction, in_combat=True)


def _combat(positions: dict[str, tuple[int, int]], sides: dict[str, int] | None = None) -> CombatState:
    bm = BattleMap(width=60, height=60)
    for cid, (x, y) in positions.items():
        bm.set_position(cid, Position(x, y))
    combat = CombatState(location_id="arena", turn_order=list(positions), battle_map=bm)
    if sides:
        combat.entity_to_side = dict(sides)
        for cid, side in sides.items():
            combat.sides.setdefault(side, set()).add(cid)
    return combat


class TestEligibilityRule:
    def _lookup(self, *creatures: Creature):  # type: ignore[no-untyped-def]
        by_id = {c.id: c for c in creatures}
        return by_id.get

    def test_enemy_at_15ft_blocks(self) -> None:
        me, foe = _fighter("me"), _fighter("foe")
        combat = _combat({"me": (0, 0), "foe": (15, 0)}, {"me": 0, "foe": 1})
        assert FLEE_SAFE_DISTANCE_FT == 15
        assert flee_blocker(me, combat, self._lookup(me, foe)) is FleeBlock.ENEMIES_TOO_CLOSE

    def test_enemy_at_20ft_allows(self) -> None:
        me, foe = _fighter("me"), _fighter("foe")
        combat = _combat({"me": (0, 0), "foe": (20, 0)}, {"me": 0, "foe": 1})
        assert flee_blocker(me, combat, self._lookup(me, foe)) is None

    def test_ally_within_15ft_does_not_block(self) -> None:
        me, friend, foe = _fighter("me"), _fighter("friend"), _fighter("foe")
        combat = _combat({"me": (0, 0), "friend": (5, 0), "foe": (30, 0)}, {"me": 0, "friend": 0, "foe": 1})
        assert flee_blocker(me, combat, self._lookup(me, friend, foe)) is None

    def test_dead_enemy_does_not_block(self) -> None:
        me, foe = _fighter("me"), _fighter("foe")
        foe.current_hp = 0
        combat = _combat({"me": (0, 0), "foe": (5, 0)}, {"me": 0, "foe": 1})
        assert flee_blocker(me, combat, self._lookup(me, foe)) is None

    def test_sideless_combat_uses_factions(self) -> None:
        """Encounter auto-combats have no sides: a same-faction neighbour is no enemy."""
        me, friend, foe = _fighter("me", "vale"), _fighter("friend", "vale"), _fighter("foe", "wildlife")
        combat = _combat({"me": (0, 0), "friend": (5, 0), "foe": (40, 0)})
        assert flee_blocker(me, combat, self._lookup(me, friend, foe)) is None
        combat.battle_map.set_position("foe", Position(10, 0))
        assert flee_blocker(me, combat, self._lookup(me, friend, foe)) is FleeBlock.ENEMIES_TOO_CLOSE

    def test_no_exit_blocks(self) -> None:
        me, foe = _fighter("me"), _fighter("foe")
        combat = _combat({"me": (0, 0), "foe": (40, 0)}, {"me": 0, "foe": 1})
        assert flee_blocker(me, combat, self._lookup(me, foe), exits=[]) is FleeBlock.NO_EXIT

    @pytest.mark.parametrize("actor_kind", ["player", "npc"])
    def test_validation_rejects_ineligible_flee_for_player_and_npc(self, actor_kind: str) -> None:
        actor: Creature = (
            PlayerCharacter(id="me", name="Me", location_id="arena", race=Race.HUMAN, char_class=CharClass.FIGHTER)
            if actor_kind == "player"
            else Npc(id="me", name="Me", location_id="arena")
        )
        foe = _fighter("foe")
        combat = _combat({"me": (0, 0), "foe": (10, 0)}, {"me": 0, "foe": 1})
        ctx = ActionContext(is_combat=True, combat_state=combat, get_entity={"me": actor, "foe": foe}.get)
        error = validate_action(actor, Action(name=ActionType.FLEE), ctx)
        assert error is not None
        assert error.code == "FLEE_BLOCKED"
        assert error.message == "Enemies are too close to flee"
        with language_context("ru"):
            error_ru = validate_action(actor, Action(name=ActionType.FLEE), ctx)
        assert error_ru is not None
        assert error_ru.message == "Враги слишком близко, сбежать не выйдет"

        combat.battle_map.set_position("foe", Position(20, 0))
        assert validate_action(actor, Action(name=ActionType.FLEE), ctx) is None

    def test_npc_destination_rule(self) -> None:
        options = [FleeDestination("a", "A", 600), FleeDestination("b", "B", 300), FleeDestination("c", "C", 900)]
        assert choose_flee_destination(options, home_first_hop="c") == "c"
        assert choose_flee_destination(options) == "b"  # quickest edge when nobody is anywhere
        assert choose_flee_destination(options, enemy_presence={"b": 2}) == "a"  # away from enemies
        assert choose_flee_destination([]) is None


# ---------------------------------------------------------------------------
# RuleBrain never emits an ineligible flee
# ---------------------------------------------------------------------------


def _npc_awareness(distance: int, *, hp: int = 1, flee: FleeStatus | None = None) -> CombatAwareness:
    return CombatAwareness(
        self_hp=hp,
        self_max_hp=20,
        self_ac=12,
        self_speed=30,
        self_weapon="bite",
        self_weapon_damage="1d4",
        self_x=0,
        self_y=0,
        nearby=[
            CombatEntity(
                id="foe", description="Foe", is_wounded=False, is_hostile=True, distance_ft=distance, x=distance, y=0
            )
        ],
        turn_budget=TurnBudget(actions=1, bonus_actions=1, movement_remaining=30, reaction=1),
        flee=flee,
    )


class TestRuleBrainObeysEligibility:
    @pytest.mark.parametrize("distance", [5, 10, 15])
    def test_never_flees_with_enemy_within_15ft(self, distance: int) -> None:
        npc = Npc(id="n1", name="Guard", location_id="arena", max_hp=20, current_hp=1)
        brain = RuleBrain()
        # Several decisions in a row: none of them may be a flee.
        for _ in range(3):
            action = brain.choose_action(npc, _npc_awareness(distance), [])
            assert action.name is not ActionType.FLEE

    def test_backs_off_when_pinned_outside_reach(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="arena", max_hp=20, current_hp=1)
        action = RuleBrain().choose_action(npc, _npc_awareness(10), [])
        assert action.name is ActionType.MOVE

    def test_flees_at_20ft(self) -> None:
        npc = Npc(id="n1", name="Guard", location_id="arena", max_hp=20, current_hp=1)
        assert RuleBrain().choose_action(npc, _npc_awareness(20), []).name is ActionType.FLEE

    def test_server_flee_status_overrides_distance(self) -> None:
        """No exit (or any server-side block) — the brain does not try."""
        npc = Npc(id="n1", name="Guard", location_id="arena", max_hp=20, current_hp=1)
        blocked = FleeStatus(allowed=False, reason_key=FleeBlock.NO_EXIT.value, reason="There is nowhere to flee")
        action = RuleBrain().choose_action(npc, _npc_awareness(40, flee=blocked), [])
        assert action.name is not ActionType.FLEE


# ---------------------------------------------------------------------------
# Scenario world
# ---------------------------------------------------------------------------

_TIME = GameDateTime(year=1490, month=6, day=1, hour=12)
_ABILITY = AbilityScores.from_dict({"str": 12, "dex": 12, "con": 12, "int": 10, "wis": 10, "cha": 10})
_BITE = Attack(name="bite", ability=Ability.STR, damage=(DamageComponent("1d4", DamageType.PIERCING),), reach=5)


class _ScriptedBrain(Brain):
    """Plays a fixed list of actions, then ends every later turn."""

    def __init__(self, actions: list[Action] | None = None) -> None:
        self.actions = list(actions or [])
        self.seen: list[PeacefulAwareness | CombatAwareness] = []

    def choose_action(
        self, creature: Creature, awareness: PeacefulAwareness | CombatAwareness, events: list[PerceivedEvent]
    ) -> Action:
        self.seen.append(awareness)
        return self.actions.pop(0) if self.actions else END_TURN


def _template(tid: str, faction: str, hp: int = 11) -> MonsterTemplate:
    return MonsterTemplate(
        id=tid,
        name=tid.capitalize(),
        hp=hp,
        ac=12,
        speed=40,
        ability_scores=_ABILITY,
        attacks=(_BITE,),
        cr=0.25,
        faction_id=faction,
    )


class _Scene:
    """Clearing with a wolf pack (squad, strength 6/6 → 3 wolves) and a named bandit.

    ``clearing`` — ``road`` (1 km) — ``far``; ``clearing`` — ``ridge`` (2 km).
    ``road`` rolls a neutral boar encounter with chance 1.0.
    Player (+ optional guard) of faction ``vale`` against wolves + bandit (friendly to each other).
    """

    def __init__(self, *, with_guard: bool = False, start_fight: bool = True, lairs: list[Lair] | None = None) -> None:
        self.graph = LocationGraph(
            [
                Location(
                    "clearing",
                    "Clearing",
                    "r1",
                    edges=(LocationEdge("road", 1000), LocationEdge("ridge", 2000)),
                ),
                Location(
                    "road", "Forest Road", "r1", edges=(LocationEdge("clearing", 1000), LocationEdge("far", 1000))
                ),
                Location("ridge", "Ridge", "r1", edges=(LocationEdge("clearing", 2000),)),
                Location("far", "Far Hamlet", "r1", edges=(LocationEdge("road", 1000),)),
            ]
        )
        region = Region(
            id="r1",
            name="Wilds",
            terrain=TerrainType.FOREST,
            latitude=45.0,
            longitude=0.0,
            elevation=100,
            water_proximity=0.0,
            connections=[],
        )
        self.squad = Squad(
            id="pack",
            name="Wolf Pack",
            faction_id="wildlife",
            squad_type=SquadType.MONSTER_PACK,
            behavior=SquadBehavior.ROAM,
            current_location_id="clearing",
            route=[],
            territory=["clearing"],
            strength=6,
            max_strength=6,
            member_templates=["wolf", "wolf", "wolf"],
            tick_interval=10**9,
            member_crs=[0.25, 0.25, 0.25],
        )
        self.player = PlayerCharacter(
            id="hero",
            name="Hero",
            location_id="clearing",
            race=Race.HUMAN,
            char_class=CharClass.FIGHTER,
            faction_id="vale",
            max_hp=30,
            current_hp=30,
            resource_pools=[ResourcePool("second_wind", 1, 1, RestType.SHORT_REST)],
            class_features=[FighterFeatures(fighting_style=FightingStyle.DEFENSE)],
        )
        self.player_brain = _ScriptedBrain()
        self.player.brain = self.player_brain
        self.bandit = Npc(
            id="grak",
            name="Grak",
            location_id="clearing",
            faction_id="bandits",
            max_hp=20,
            current_hp=7,  # already wounded
            attacks=(_BITE,),
            xp_value=100,
        )
        self.bandit.brain = RuleBrain()
        entities: list[Creature] = [self.player, self.bandit]
        self.guard: Npc | None = None
        if with_guard:
            self.guard = Npc(id="guard", name="Guard", location_id="clearing", faction_id="vale", max_hp=30)
            self.guard.brain = _ScriptedBrain()
            entities.append(self.guard)

        self.ecology = EcologyLayer(squads=[self.squad], location_graph=self.graph, lairs=lairs)
        self.entities = EntitiesLayer(
            entities=list(entities),
            monster_templates={"wolf": _template("wolf", "wildlife"), "boar": _template("boar", "beasts")},
            encounter_tables={"road": [EncounterEntry("boar", chance=1.0, count_min=1, count_max=1)]},
            seed=7,
            dice_rng=random.Random(7),
        )
        politics = PoliticsLayer(
            nations=[],
            region_terrains={"r1": TerrainType.FOREST},
            region_adjacency={},
            faction_relations={("bandits", "wildlife"): FactionRelation.FRIENDLY},
        )
        self.world = World(
            layers=[
                GeographyLayer(regions=[region]),
                politics,
                SettlementsLayer(settlements=[], region_terrains={"r1": TerrainType.FOREST}),
                self.ecology,
                self.entities,
            ],
            time=_TIME,
            location_graph=self.graph,
        )
        self.round = Round(self.world, self.entities, rng=random.Random(7))
        if not start_fight:
            return  # a bare world, e.g. the target of a save/load

        # Materialize the pack, then start the fight with sides and fixed positions.
        self.round._activate()
        self.wolves = sorted(
            (e for e in self.entities._entities.values() if isinstance(e, Creature) and e.squad_id == "pack"),
            key=lambda c: c.id,
        )
        assert len(self.wolves) == 3
        combat = self.entities._combat.start_combat("clearing", self.world.make_query_fn("entities"))
        assert combat is not None
        self.combat = combat
        self.place("hero", 0, 0)
        if self.guard is not None:
            self.place("guard", 0, 5)
        for index, wolf in enumerate(self.wolves):
            self.place(wolf.id, 40, 20 + 10 * index)
        self.place("grak", 50, 50)

    def place(self, entity_id: str, x: int, y: int) -> None:
        self.combat.battle_map.set_position(entity_id, Position(x, y))

    def combat_turn(self, creature: Creature) -> list[Action]:
        return self.round.run_combat_turn(
            creature, self.world.time, self.world.make_query_fn("entities"), self.world.make_emit_fn("entities")
        )

    def ctx(self, creature: Creature) -> ActionContext:
        creature.turn_budget = TurnBudget(actions=1, bonus_actions=1, movement_remaining=30, reaction=1)
        return self.round._build_action_context(creature, turn_budget=creature.turn_budget)

    def dispatch(self, creature: Creature, action: Action):  # type: ignore[no-untyped-def]
        return self.round._dispatcher.dispatch(
            creature, action, self.ctx(creature), self.world.make_emit_fn("entities")
        )

    def kill(self, creature: Creature) -> None:
        """A death as the attack path records it (temporary spawns are removed)."""
        creature.current_hp = 0
        self.entities.handle_event(
            Event(
                event_type=EventType.ENTITY_DIED,
                source_layer="entities",
                data=EntityDiedPayload(creature.id, creature.location_id, self.player.id, None),
            ),
            self.world.make_query_fn("entities"),
            self.world.make_emit_fn("entities"),
        )
        self.entities._combat.remove_from_combat(creature.location_id, creature.id)

    def assert_no_ghosts(self) -> None:
        for location_id in self.entities.get_combat_locations():
            assert self.entities._combat.scene_outsiders(location_id) == []


def _flee_to(destination: str) -> Action:
    return Action(name=ActionType.FLEE, params={"destination_id": destination})


# ---------------------------------------------------------------------------
# Player flee
# ---------------------------------------------------------------------------


class TestPlayerFlee:
    def test_ui_payload_tells_whether_and_where(self) -> None:
        scene = _Scene()
        status = flee_status(scene.player, scene.combat, scene.entities.get_entity, scene.graph)
        assert status.allowed is True
        assert [(d.id, d.name) for d in status.destinations] == [("road", "Forest Road"), ("ridge", "Ridge")]
        assert status.destinations[0].travel_seconds == scene.graph.travel_seconds("clearing", "road")

        scene.place(scene.wolves[0].id, 10, 0)
        blocked = flee_status(scene.player, scene.combat, scene.entities.get_entity, scene.graph)
        assert blocked.allowed is False
        assert blocked.reason_key == "enemies_too_close"
        assert blocked.reason == "Enemies are too close to flee"
        assert blocked.destinations == status.destinations
        assert ActionType.FLEE not in scene.round._dispatcher.get_available_actions(
            scene.player, scene.ctx(scene.player)
        )

    def test_combat_turn_awareness_carries_flee_status(self) -> None:
        scene = _Scene()
        scene.combat_turn(scene.player)
        awareness = scene.player_brain.seen[0]
        assert isinstance(awareness, CombatAwareness)
        assert awareness.flee is not None and awareness.flee.allowed
        assert {d.id for d in awareness.flee.destinations} == {"road", "ridge"}
        assert ActionType.FLEE in awareness.available_actions

    def test_missing_or_non_adjacent_destination_rejected(self) -> None:
        scene = _Scene()
        for action, error in (
            (Action(name=ActionType.FLEE), "Choose a neighbouring location to flee to"),
            (_flee_to("far"), "You can only flee to a neighbouring location"),
            (_flee_to("nowhere"), "You can only flee to a neighbouring location"),
        ):
            ctx = scene.ctx(scene.player)
            result = scene.round._dispatcher.dispatch(scene.player, action, ctx, scene.world.make_emit_fn("entities"))
            assert result.success is False
            assert result.error == error
            assert ctx.turn_budget is not None and ctx.turn_budget.actions == 1  # nothing spent
            assert scene.entities.get_active_combat_for(scene.player.id) is scene.combat
            assert scene.player.current_intent is None

    def test_enemy_close_rejects_with_reason(self) -> None:
        scene = _Scene()
        scene.place(scene.wolves[0].id, 15, 0)
        result = scene.dispatch(scene.player, _flee_to("road"))
        assert result.success is False
        assert result.error == "Enemies are too close to flee"
        assert scene.entities.get_active_combat_for(scene.player.id) is scene.combat

    def test_flee_is_one_travel_edge_with_arrival_encounter(self) -> None:
        scene = _Scene(with_guard=True)  # guard keeps fighting: player + guard + 3 wolves + bandit
        assert len(scene.combat.turn_order) == 6
        departed = scene.world.time.to_total_seconds()
        scene.player_brain.actions = [_flee_to("road")]
        actions = scene.combat_turn(scene.player)

        assert [a.name for a in actions] == [ActionType.FLEE]
        intent = scene.player.current_intent
        assert isinstance(intent, TravelIntent)
        assert intent.remaining_route == ("road",)
        assert intent.next_arrival_seconds == departed + scene.graph.travel_seconds("clearing", "road")
        assert scene.player.active is False
        assert scene.player.in_combat is False
        assert scene.entities.get_active_combat_for(scene.player.id) is None
        # The fight goes on without the player: guard against wolves + bandit.
        assert scene.entities.get_combat("clearing") is scene.combat
        assert scene.player.id not in scene.combat.turn_order
        scene.assert_no_ghosts()

        # The guard ends its turns; the wolves/bandit fight it. Run until the player has arrived
        # and the arrival activation has rolled the road's table.
        scene.round.run_loop(max_rounds=400)
        assert scene.world.time.to_total_seconds() >= intent.next_arrival_seconds
        assert scene.player.location_id == "road"
        assert scene.player.current_intent is None
        spawns = [e for e in scene.entities._entities.values() if isinstance(e, Creature) and e.id.startswith("boar_")]
        assert len(spawns) == 1 and spawns[0].location_id == "road"
        assert any(e.event_type is EventType.ENCOUNTER_SPAWNED for e in scene.entities._location_log["road"])
        # Nobody followed the player.
        assert all(
            c.id == scene.player.id or c.id.startswith("boar_")
            for c in scene.entities._entities.values()
            if isinstance(c, Creature) and c.location_id == "road"
        )
        scene.assert_no_ghosts()

    def test_arrival_matches_ordinary_travel(self) -> None:
        """Flee and plain travel over the same edge arrive at the same time and roll the same table."""
        fled, travelled = _Scene(), _Scene()
        fled.player_brain.actions = [_flee_to("road")]
        fled.combat_turn(fled.player)
        # Ordinary travel from the same spot once the fight is over.
        travelled.entities._combat._end_combat("clearing")
        travelled.player_brain.actions = [Action(name=ActionType.TRAVEL, params={"destination_id": "road"})]
        travelled.round.run_peaceful_turn(
            travelled.player,
            travelled.world.time,
            travelled.world.make_query_fn("entities"),
            travelled.world.make_emit_fn("entities"),
        )
        assert fled.player.current_intent == travelled.player.current_intent
        for scene in (fled, travelled):
            scene.round.run_loop(max_rounds=2)
        assert fled.world.time == travelled.world.time
        assert fled.player.location_id == travelled.player.location_id == "road"
        assert sorted(e.id for e in fled.entities._entities.values() if e.location_id == "road") == sorted(
            e.id for e in travelled.entities._entities.values() if e.location_id == "road"
        )


# ---------------------------------------------------------------------------
# The abandoned scene after the player leaves
# ---------------------------------------------------------------------------


class TestSceneAfterPlayerLeaves:
    def test_squad_dematerializes_named_npc_stays_wounded(self) -> None:
        scene = _Scene()
        scene.kill(scene.wolves[0])  # one wolf of three dies before the flee
        scene.player_brain.actions = [_flee_to("ridge")]
        scene.combat_turn(scene.player)

        # Only the wolves' side is left: the combat ended with the player's exit.
        assert scene.entities.get_combat("clearing") is None
        scene.assert_no_ghosts()

        scene.round._activate()  # the next activation pass (nobody holds the clearing any more)
        assert not [e for e in scene.entities._entities.values() if isinstance(e, Creature) and e.squad_id == "pack"]
        assert scene.squad.strength == 4  # 2 of 3 spawned wolves alive → 6 * 2/3
        assert scene.bandit.location_id == "clearing"
        assert scene.bandit.current_hp == 7
        assert scene.bandit.is_alive
        assert scene.player.location_id == "clearing" and isinstance(scene.player.current_intent, TravelIntent)
        assert scene.player.current_intent.destination_id == "ridge"

    def test_random_encounter_dematerializes(self) -> None:
        scene = _Scene()
        boar = _template("boar", "wildlife").spawn("clearing", "boar_99")
        scene.entities.add_entity(boar)
        scene.entities._combat.remove_from_combat("clearing", "grak")  # keep the fight wolves + boar vs hero
        scene.combat.turn_order.append(boar.id)
        scene.combat.entity_to_side[boar.id] = scene.combat.entity_to_side[scene.wolves[0].id]
        scene.combat.sides[scene.combat.entity_to_side[boar.id]].add(boar.id)
        scene.place(boar.id, 55, 0)
        boar.in_combat = True

        scene.player_brain.actions = [_flee_to("road")]
        scene.combat_turn(scene.player)
        assert scene.entities.get_combat("clearing") is None
        assert scene.entities.get_entity(boar.id) is None  # the encounter went back where it came from


# ---------------------------------------------------------------------------
# NPC flee
# ---------------------------------------------------------------------------


class TestNpcFlee:
    def test_anonymous_fleer_returns_to_squad_alive(self) -> None:
        scene = _Scene(with_guard=True)
        wolf = scene.wolves[0]
        wolf.current_hp = 1  # badly hurt, far from everyone → RuleBrain flees
        actions = scene.combat_turn(wolf)
        assert [a.name for a in actions] == [ActionType.FLEE]
        assert scene.entities.get_entity(wolf.id) is None
        assert wolf.id not in scene.combat.turn_order
        # 3+ participants and both sides still stand: the fight goes on.
        assert scene.entities.get_combat("clearing") is scene.combat
        scene.assert_no_ghosts()

        # Witnesses saw it happen; a fleer is not a kill.
        seen = scene.entities.get_perceived_events(scene.player)
        flee_events = [e for e in seen if e.event_type is EventType.ENTITY_FLEE]
        assert len(flee_events) == 1
        assert "flees the fight toward" in flee_events[0].description
        assert "Wolf" in flee_events[0].description
        assert scene.guard is not None and scene.guard.inner_self is not None
        assert any(e.event_type is EventType.ENTITY_FLEE for e in scene.guard.inner_self.perceived_event_buffer)
        assert scene.player.experience == 0

        # Kill one, end the fight, let the player leave: 2 of 3 wolves survived (one of them fled).
        scene.kill(scene.wolves[1])
        scene.entities._combat._end_combat("clearing")
        scene.player.location_id = "road"
        scene.round._activate()
        assert scene.squad.strength == 4

    def test_named_fleer_moves_to_neighbour_with_its_wounds(self) -> None:
        scene = _Scene(with_guard=True)
        bandit = scene.bandit
        bandit.current_hp = 2
        actions = scene.combat_turn(bandit)
        assert [a.name for a in actions] == [ActionType.FLEE]
        intent = bandit.current_intent
        assert isinstance(intent, TravelIntent)
        assert intent.remaining_route == (intent.destination_id,)
        assert intent.destination_id in {"road", "ridge"}
        assert bandit.active is False
        assert bandit.id not in scene.combat.turn_order
        assert scene.entities.get_combat("clearing") is scene.combat  # wolves still fight
        scene.assert_no_ghosts()

        seen = scene.entities.get_perceived_events(scene.player)
        destination_name = scene.graph.get(intent.destination_id).name
        assert any(e.event_type is EventType.ENTITY_FLEE and destination_name in e.description for e in seen), (
            "witness text names the direction"
        )

        # Time passes: the bandit is at the neighbour, still wounded, and stays there.
        scene.world.advance_time(TimeDelta(seconds=intent.next_arrival_seconds - scene.world.time.to_total_seconds()))
        scene.round._activate()
        assert bandit.location_id == intent.destination_id
        assert bandit.current_hp == 2
        assert bandit.location_override == intent.destination_id
        assert scene.player.experience == 0
        assert not any(
            e.event_type is EventType.XP_GAINED for log in scene.entities._location_log.values() for e in log
        )

    def test_npc_ignores_brain_supplied_destination(self) -> None:
        """An LLM-style NPC action naming a foreign neighbour does not steer the flee."""
        scene = _Scene()
        scene.bandit.current_hp = 2
        # The rule's pick: no home to head for, nobody anywhere else → the quicker edge, ``road``.
        result = scene.dispatch(scene.bandit, _flee_to("ridge"))
        assert result.success is True
        assert isinstance(scene.bandit.current_intent, TravelIntent)
        assert scene.bandit.current_intent.destination_id == "road"

    def test_squad_member_heads_for_its_squad(self) -> None:
        scene = _Scene()
        scene.squad.current_location_id = "ridge"  # the pack has moved on to a neighbour
        wolf = scene.wolves[0]
        result = scene.dispatch(wolf, _flee_to("road"))  # a brain-supplied direction is ignored
        assert result.success is True
        assert scene.entities.get_entity(wolf.id) is None
        fled = [e for e in scene.entities._location_log["clearing"] if e.event_type is EventType.ENTITY_FLEE]
        assert [e.data.destination_id for e in fled] == ["ridge"]  # type: ignore[union-attr]
        seen = scene.entities.get_perceived_events(scene.player)
        assert any(e.event_type is EventType.ENTITY_FLEE and "Ridge" in e.description for e in seen)

    def test_lair_member_heads_for_its_lair(self) -> None:
        den = Lair(id="den", name="Den", faction_id="wildlife", location_id="ridge", members=["wolf"])
        scene = _Scene(lairs=[den])
        denizen = _template("wolf", "wildlife").spawn("clearing", "wolf_den_1")
        denizen.lair_origin = LairOrigin(lair_id="den", template_id="wolf", role=LairMemberRole.MEMBER)
        denizen.brain = RuleBrain()
        denizen.in_combat = True
        scene.entities.add_entity(denizen)
        side = scene.combat.entity_to_side[scene.wolves[0].id]
        scene.combat.turn_order.append(denizen.id)
        scene.combat.entity_to_side[denizen.id] = side
        scene.combat.sides[side].add(denizen.id)
        scene.place(denizen.id, 60, 0)

        assert scene.dispatch(denizen, Action(name=ActionType.FLEE)).success is True
        fled = [e for e in scene.entities._location_log["clearing"] if e.event_type is EventType.ENTITY_FLEE]
        assert [e.data.destination_id for e in fled] == ["ridge"]  # type: ignore[union-attr]

    def test_squad_member_without_a_home_hop_flees_away(self) -> None:
        scene = _Scene()  # the pack is right here: no hop home, the quicker empty edge wins
        assert scene.dispatch(scene.wolves[0], Action(name=ActionType.FLEE)).success is True
        fled = [e for e in scene.entities._location_log["clearing"] if e.event_type is EventType.ENTITY_FLEE]
        assert [e.data.destination_id for e in fled] == ["road"]  # type: ignore[union-attr]

    def test_always_active_named_fleer_arrives_only_at_the_boundary(self) -> None:
        scene = _Scene(with_guard=True)
        bandit = scene.bandit
        bandit.always_active = True
        bandit.current_hp = 2
        assert [a.name for a in scene.combat_turn(bandit)] == [ActionType.FLEE]
        intent = bandit.current_intent
        assert isinstance(intent, TravelIntent)
        destination = intent.destination_id

        # The next activation pass, before arrival: still on the road, not at the destination,
        # and not an active outsider on the scene it left.
        scene.round._activate()
        assert scene.world.time.to_total_seconds() < intent.next_arrival_seconds
        assert bandit.location_id == "clearing"
        assert bandit.current_location(scene.world.time.hour) == "clearing"
        assert bandit.active is False
        assert bandit.current_intent == intent
        scene.assert_no_ghosts()

        scene.world.advance_time(TimeDelta(seconds=intent.next_arrival_seconds - scene.world.time.to_total_seconds()))
        scene.round._activate()
        assert bandit.current_intent is None
        assert bandit.location_id == destination
        assert bandit.current_location(scene.world.time.hour) == destination
        assert bandit.current_hp == 2
        assert bandit.active is True  # always_active again once it has arrived

    def test_last_enemy_fleeing_ends_combat(self) -> None:
        scene = _Scene()
        scene.kill(scene.wolves[0])
        scene.kill(scene.wolves[1])
        scene.entities._combat.remove_from_combat("clearing", "grak")
        scene.bandit.in_combat = False
        last = scene.wolves[2]
        last.current_hp = 1
        scene.combat_turn(last)
        assert scene.entities.get_combat("clearing") is None
        assert scene.player.in_combat is False
        scene.assert_no_ghosts()


# ---------------------------------------------------------------------------
# Save/load right after a flee
# ---------------------------------------------------------------------------


def _reload(scene: _Scene) -> EntitiesLayer:
    state = json.loads(json.dumps(scene.entities.get_state()))
    fresh = EntitiesLayer(
        monster_templates={"wolf": _template("wolf", "wildlife"), "boar": _template("boar", "beasts")}
    )
    fresh.load_state(state)
    return fresh


def _assert_invariant(layer: EntitiesLayer) -> None:
    for location_id in layer.get_combat_locations():
        assert layer._combat.scene_outsiders(location_id) == []


class TestSaveLoadAfterFlee:
    def test_after_player_flee(self) -> None:
        scene = _Scene(with_guard=True)
        scene.player_brain.actions = [_flee_to("road")]
        scene.combat_turn(scene.player)
        loaded = _reload(scene)
        _assert_invariant(loaded)
        player = loaded.get_entity("hero")
        assert isinstance(player, Creature)
        assert player.active is False
        assert isinstance(player.current_intent, TravelIntent)
        assert player.current_intent.destination_id == "road"
        combat = loaded.get_combat("clearing")
        assert combat is not None and "hero" not in combat.turn_order
        assert loaded.get_active_combat_for("hero") is None

    def test_after_npc_flee(self) -> None:
        scene = _Scene(with_guard=True)
        scene.bandit.current_hp = 2
        scene.combat_turn(scene.bandit)
        scene.wolves[0].current_hp = 1
        scene.combat_turn(scene.wolves[0])
        loaded = _reload(scene)
        _assert_invariant(loaded)
        bandit = loaded.get_entity("grak")
        assert isinstance(bandit, Npc)
        assert bandit.active is False
        assert bandit.current_hp == 2
        assert isinstance(bandit.current_intent, TravelIntent)
        assert bandit.location_override == bandit.current_intent.destination_id
        assert loaded.get_entity(scene.wolves[0].id) is None
        combat = loaded.get_combat("clearing")
        assert combat is not None
        assert "grak" not in combat.turn_order and scene.wolves[0].id not in combat.turn_order

    def test_fled_squad_member_still_counted_alive_after_save_load(self) -> None:
        def strength_after_fled_wolf(save_load: bool) -> int:
            scene = _Scene()
            wolf = scene.wolves[0]
            wolf.current_hp = 1
            assert [a.name for a in scene.combat_turn(wolf)] == [ActionType.FLEE]
            scene.kill(scene.wolves[1])
            target = scene
            if save_load:
                state = json.loads(json.dumps(scene.world.save()))
                target = _Scene(start_fight=False)
                target.world.load(state)
                assert target.entities.get_entity(wolf.id) is None
                assert target.entities._activation._spawn_counter == scene.entities._activation._spawn_counter
            target.entities._combat._end_combat("clearing")
            target.player.location_id = "road"  # the player leaves the clearing
            target.round._activate()
            assert not [
                e for e in target.entities._entities.values() if isinstance(e, Creature) and e.squad_id == "pack"
            ]
            return target.squad.strength

        # 2 of 3 spawned wolves survived (one of them fled) → 6 * 2/3, with or without a save in between.
        assert strength_after_fled_wolf(save_load=False) == 4
        assert strength_after_fled_wolf(save_load=True) == 4

    def test_save_without_materialization_loads_empty_trackers(self) -> None:
        scene = _Scene()
        state = json.loads(json.dumps(scene.entities.get_state()))
        assert state["materialization"]["squads"]["pack"]["creature_ids"] == [w.id for w in scene.wolves]
        del state["materialization"]  # a save written before the trackers were persisted
        fresh = EntitiesLayer(monster_templates={"wolf": _template("wolf", "wildlife")})
        fresh.load_state(state)
        assert fresh._materialized_squads == {}
        assert fresh._materialized_lairs == {}
        assert fresh._activation._withdrawn_survivors == set()
