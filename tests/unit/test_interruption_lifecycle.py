"""Interruption lifecycle consistency across the real session boundary (Sprint 022 phase 4 task 2).

Phase 4 task 1 built one idempotent interruption helper wired to damage, combat entry, and
scene arrival. This file pins that behaviour *through* save/load, repeated activation, and the
session world-mutation gate: a stale round or a repeated activation pass must not replay a
reached leg, restore a cleared intent, grant rest twice, or hand out two player turns, and a
snapshot taken while an interruption commits must be internally consistent.

Groups A and C use a real ``GameService`` + on-disk ``JsonFileStore`` + ``sword_vale`` so the
actual ``save_game``/``load_game`` commands and the ``GameSession`` gate are exercised. Group B
drives ``Round.run_loop`` synchronously over a minimal travel world so the "exactly once"
invariants are deterministic and free of NPC noise.
"""

from __future__ import annotations

import threading
from pathlib import Path

from dnd_simulator.core.action import END_TURN
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness, PerceivedEvent
from dnd_simulator.core.brain import PlayerBrain
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Creature,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.intent import IntentInterruptReason, IntentType, TimedIntent, TravelIntent
from dnd_simulator.core.location import Location, LocationEdge, LocationGraph
from dnd_simulator.core.models import GameDateTime, TimeDelta
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.resource import ResourcePool, RestType
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.intent_completion import interrupt_intent
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.layer import GeographyLayer
from dnd_simulator.layers.geography.models import Region, TerrainType
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.settlements.layer import SettlementsLayer
from dnd_simulator.round import Round
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

_FIGHTER = {
    "name": "Wanderer",
    "race": "human",
    "class": "fighter",
    "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
    "fighting_style": "defense",
}

_CLAWS = Attack(
    name="claws",
    ability=Ability.STR,
    damage=(DamageComponent("1d6", DamageType.SLASHING),),
)


def _service(tmp_path: Path) -> GameService:
    return GameService(store=JsonFileStore(tmp_path / "saves"))


# ---------------------------------------------------------------------------
# Group A — real save_game/load_game commands around an interruption
# ---------------------------------------------------------------------------


class TestSaveLoadAroundInterruption:
    """save_game/load_game restore one internally consistent pre- or post-interruption state."""

    def test_journey_survives_save_load_then_stops_at_occupied_scene(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id
        start, mid, dest = "silverport_city_docks", "silverport_city_tavern", "silverport_city_market"
        player = svc.create_player(sid, {**_FIGHTER, "start_location": start})
        player.is_anchor = True
        layer = svc._get_entities_layer(session)
        layer.add_entity(Creature(id="scene_host", name="Host", location_id=mid, is_anchor=True))

        now = session.world.time.to_total_seconds()
        graph = session.world.location_graph
        route = graph.shortest_route(start, dest)
        assert route == (mid, dest)  # two legs, tavern is the intermediate node
        first_leg = graph.travel_seconds(start, mid)
        player.current_intent = TravelIntent(now, dest, route, now + first_leg)

        svc.save_game(sid, "mid_journey")

        # Diverge in the live session, then load the mid-journey snapshot back.
        session.world.advance_time(TimeDelta(seconds=first_leg))
        layer.update_activation(
            session.world.time,
            query_fn=session.world.make_query_fn("entities"),
            location_graph=graph,
        )
        assert svc.get_session(sid).get_player().location_id == mid  # diverged

        svc.load_game(sid, "mid_journey")
        restored = svc.get_session(sid).get_player()
        assert restored is not None
        assert restored.location_id == start
        assert restored.current_intent == TravelIntent(now, dest, route, now + first_leg)

        # Reach the occupied intermediate scene: the traveler stops there, intent cleared.
        session.world.advance_time(TimeDelta(seconds=first_leg))
        for _ in range(3):  # repeated activation must not replay the reached leg
            layer.update_activation(
                session.world.time,
                query_fn=session.world.make_query_fn("entities"),
                location_graph=graph,
            )
        restored = svc.get_session(sid).get_player()
        assert restored.location_id == mid
        assert restored.current_intent is None
        assert restored.active is True

    def test_save_after_sleep_interrupted_by_damage_grants_no_rest(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id
        player = svc.create_player(sid, {**_FIGHTER, "start_location": "silverport_greenwood_road"})
        player.is_anchor = True
        pool = ResourcePool("second_wind", 1, 0, RestType.SHORT_REST)
        player.resource_pools = [pool]
        player.current_hp = 5

        now = session.world.time.to_total_seconds()
        player.current_intent = TimedIntent(IntentType.SLEEP, now, now + 8 * 3600, rest_type=RestType.LONG_REST)

        # Damage wakes the sleeper before the timer; interruption grants no rest.
        assert interrupt_intent(player, IntentInterruptReason.DAMAGE) is True
        assert interrupt_intent(player, IntentInterruptReason.DAMAGE) is False  # idempotent no-op

        svc.save_game(sid, "post_damage")
        # Diverge, then load the post-interruption snapshot.
        player.current_hp = 20
        svc.load_game(sid, "post_damage")

        restored = svc.get_session(sid).get_player()
        assert restored is not None
        assert restored.current_intent is None  # cleared intent stays cleared
        assert restored.current_hp == 5  # no long-rest heal applied
        assert restored.resource_pools[0].current_uses == 0  # no pool reset

    def test_save_after_combat_interruption_preserves_combat_and_cleared_intent(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id
        loc = "silverport_greenwood_road"
        player = svc.create_player(sid, {**_FIGHTER, "start_location": loc})
        player.is_anchor = True
        layer = svc._get_entities_layer(session)
        enemy = Creature(
            id="ambusher",
            name="Ambusher",
            location_id=loc,
            max_hp=11,
            current_hp=11,
            ac=13,
            speed=30,
            ability_scores=AbilityScores(),
            attacks=(_CLAWS,),
            faction_id="wild_beasts",
        )
        layer.add_entity(enemy)

        now = session.world.time.to_total_seconds()
        player.current_intent = TimedIntent(IntentType.WAIT, now, now + 3600)
        player.active = True
        enemy.active = True

        combat = layer._combat.start_combat(loc)
        assert combat is not None
        assert player.in_combat is True
        assert player.current_intent is None

        svc.save_game(sid, "post_combat")
        # Diverge, then load the post-interruption snapshot.
        player.in_combat = False
        layer._combat._combats.clear()
        svc.load_game(sid, "post_combat")

        restored_layer = svc._get_entities_layer(session)
        restored = svc.get_session(sid).get_player()
        assert restored is not None
        assert restored.current_intent is None
        assert restored.in_combat is True
        assert restored.location_id == loc
        assert restored_layer.get_combat(loc) is not None


# ---------------------------------------------------------------------------
# Group B — deterministic round loop: resume advances each leg exactly once
# ---------------------------------------------------------------------------


def _travel_world(entities: list[Creature]) -> World:
    region = Region(
        id="r1",
        name="Test Field",
        terrain=TerrainType.PLAINS,
        latitude=45.0,
        longitude=0.0,
        elevation=100,
        water_proximity=0.0,
        connections=[],
    )
    geography = GeographyLayer(regions=[region])
    settlements = SettlementsLayer(settlements=[], region_terrains={"r1": TerrainType.PLAINS})
    politics = PoliticsLayer(
        nations=[],
        region_terrains={"r1": TerrainType.PLAINS},
        region_adjacency={},
        region_income_fn=settlements.get_region_income,
    )
    return World(
        layers=[geography, politics, settlements, EntitiesLayer(entities=list(entities))],
        time=GameDateTime(year=1, month=1, day=1, hour=10),
        location_graph=LocationGraph(
            [
                Location("start", "Start", "r1", edges=(LocationEdge("road", 1000),)),
                Location("road", "Road", "r1", edges=(LocationEdge("goal", 2000),)),
                Location("goal", "Goal", "r1"),
            ]
        ),
    )


class _CountingPlayerBrain(PlayerBrain):
    """PlayerBrain that ends every turn immediately and counts how many turns it is offered."""

    def __init__(self) -> None:
        super().__init__()
        self.turns = 0

        def on_turn(
            creature: Creature,
            awareness: PeacefulAwareness | CombatAwareness,
            events: list[PerceivedEvent],
        ) -> None:
            self.turns += 1
            self.submit_action(END_TURN)

        self.set_on_turn(on_turn)


class TestReconnectResumesJourneyOnce:
    def test_resumed_round_advances_each_leg_once_and_a_second_run_is_a_noop(self) -> None:
        brain = _CountingPlayerBrain()
        traveler = PlayerCharacter(id="traveler", name="Traveler", location_id="start", brain=brain)
        traveler.current_intent = TravelIntent(
            GameDateTime(year=1, month=1, day=1, hour=10).to_total_seconds(),
            "goal",
            ("road", "goal"),
            GameDateTime(year=1, month=1, day=1, hour=10).to_total_seconds() + 720,
        )
        world = _travel_world([traveler])
        layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        # A disconnect stops the round mid-journey; a reconnect starts a fresh round that
        # must fast-forward through the remaining legs exactly once and return control.
        Round(world, layer).run_loop(max_rounds=3)
        assert traveler.location_id == "goal"
        assert traveler.current_intent is None
        turns_after_arrival = brain.turns
        assert turns_after_arrival >= 1
        time_at_arrival = world.time.to_total_seconds()

        # A stale round re-entering must not replay a leg or teleport the traveler.
        Round(world, layer).run_loop(max_rounds=1)
        assert traveler.location_id == "goal"
        assert traveler.current_intent is None
        # Exactly one extra playable turn per extra round; no duplicated arrival turn.
        assert brain.turns == turns_after_arrival + 1
        assert world.time.to_total_seconds() == time_at_arrival + 6

    def test_repeated_activation_after_scene_interruption_does_not_replay(self) -> None:
        now = GameDateTime(year=1, month=1, day=1, hour=10).to_total_seconds()
        traveler = Creature(id="traveler", name="Traveler", location_id="start", is_anchor=True)
        traveler.current_intent = TravelIntent(now, "goal", ("road", "goal"), now)
        scene_host = Creature(id="host", name="Host", location_id="road", is_anchor=True)
        world = _travel_world([traveler, scene_host])
        layer = next(la for la in world.layers if isinstance(la, EntitiesLayer))

        for _ in range(4):
            layer.update_activation(world.time, location_graph=world.location_graph)

        assert traveler.location_id == "road"  # stopped at the occupied intermediate node
        assert traveler.current_intent is None
        assert traveler.active is True


# ---------------------------------------------------------------------------
# Group C — snapshot and interruption stay atomic under the session gate
# ---------------------------------------------------------------------------


class TestConcurrentSnapshotAndInterruption:
    def test_snapshot_never_sees_torn_interruption_state(self, tmp_path: Path) -> None:
        svc = _service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id
        loc = "silverport_greenwood_road"
        player = svc.create_player(sid, {**_FIGHTER, "start_location": loc})
        player.is_anchor = True
        layer = svc._get_entities_layer(session)
        enemy = Creature(
            id="ambusher",
            name="Ambusher",
            location_id=loc,
            max_hp=11,
            current_hp=11,
            ac=13,
            speed=30,
            ability_scores=AbilityScores(),
            attacks=(_CLAWS,),
            faction_id="wild_beasts",
        )
        layer.add_entity(enemy)
        now = session.world.time.to_total_seconds()
        player.current_intent = TimedIntent(IntentType.WAIT, now, now + 3600)
        player.active = True
        enemy.active = True

        errors: list[str] = []
        wait_intent = TimedIntent(IntentType.WAIT, now, now + 3600)
        start_barrier = threading.Barrier(2)
        stop = threading.Event()

        def interrupt() -> None:
            start_barrier.wait()
            # Production drives combat entry through Round._execute_action under this exact
            # gate. Toggle enter/exit combat repeatedly so a snapshot racing without the gate
            # has many windows to observe a half-applied interruption.
            while not stop.is_set():
                with session.mutate_world():
                    layer._combat.start_combat(loc)
                with session.mutate_world():
                    layer._combat._combats.clear()
                    player.in_combat = False
                    player.current_intent = wait_intent
                    player.active = True
                    enemy.active = True

        def snapshot() -> None:
            start_barrier.wait()
            for _ in range(400):
                save = session.build_save_game()
                ent = save.world.layers.entities
                psave = ent.entities[player.id]
                has_combat = loc in ent.combats
                pre = psave.current_intent is not None and not psave.in_combat and not has_combat
                post = psave.current_intent is None and psave.in_combat and has_combat
                if not (pre or post):
                    errors.append(
                        f"torn: intent={psave.current_intent is not None} "
                        f"in_combat={psave.in_combat} has_combat={has_combat}"
                    )
                    break
            stop.set()

        threads = [threading.Thread(target=interrupt), threading.Thread(target=snapshot)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
