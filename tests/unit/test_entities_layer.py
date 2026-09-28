"""EntitiesLayer orchestration through its public API.

The sub-managers have their own suites (activation, awareness, materialization,
serialization, initiative). These tests drive the layer itself: that ``add_entity`` /
``remove_entity`` keep every index in step, that ``handle_event`` routes a world event
to the right manager and applies the combat-end hooks, and that activation, awareness,
combat and materialization agree with each other across a whole scene and a save/load.
"""

from __future__ import annotations

import random

from dnd_simulator.content_loader import parse_npc
from dnd_simulator.core.awareness import CombatAwareness, PeacefulAwareness
from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    CharClass,
    Creature,
    DamageComponent,
    DamageType,
)
from dnd_simulator.core.events import (
    AttackRequestedPayload,
    EntityDiedPayload,
    EntitySayPayload,
    WarDeclaredPayload,
)
from dnd_simulator.core.inner_self import InnerSelf
from dnd_simulator.core.intent import IntentType, TimedIntent, TravelIntent
from dnd_simulator.core.models import (
    ActionResult,
    Answer,
    Event,
    EventType,
    FactionRelation,
    GameDateTime,
    Query,
    QueryType,
)
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.core.squad import Squad, SquadBehavior, SquadType
from dnd_simulator.core.world import LayerError
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer

TIME = GameDateTime(year=1490, month=6, day=1, hour=10)


class _MissingDice(random.Random):
    """Seeded dice whose every d20 shows 2: no attack hits AC 10+, nobody dies mid-scenario.

    Initiative uses the same d20, so its order falls to DEX and the seeded tiebreaker.
    """

    def randint(self, a: int, b: int) -> int:
        if (a, b) == (1, 20):
            return 2
        return super().randint(a, b)


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _scores() -> AbilityScores:
    return AbilityScores.from_dict({"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10})


def _player(location: str = "forest") -> PlayerCharacter:
    return PlayerCharacter(
        id="hero",
        name="Hero",
        location_id=location,
        ability_scores=_scores(),
        max_hp=30,
        current_hp=30,
        ac=15,
        speed=30,
        char_class=CharClass.FIGHTER,
        attacks=(Attack(name="sword", ability=Ability.STR, damage=(DamageComponent("1d8", DamageType.SLASHING),)),),
    )


def _wolf_template() -> MonsterTemplate:
    return MonsterTemplate(
        id="wolf",
        name="Wolf",
        hp=11,
        ac=13,
        speed=40,
        ability_scores=_scores(),
        attacks=(Attack(name="bite", ability=Ability.STR, damage=(DamageComponent("1d4", DamageType.PIERCING),)),),
        cr=0.25,
        faction_id="wildlife",
    )


def _pack(strength: int = 6) -> Squad:
    return Squad(
        id="pack",
        name="Wolf pack",
        faction_id="wildlife",
        squad_type=SquadType.MONSTER_PACK,
        behavior=SquadBehavior.ROAM,
        current_location_id="forest",
        route=[],
        territory=["forest"],
        strength=strength,
        max_strength=6,
        member_templates=["wolf", "wolf", "wolf"],
        tick_interval=3600,
        member_crs=[0.25, 0.25, 0.25],
    )


class _World:
    """Ecology + entities wired the way ``World`` wires them (queries go down, events route)."""

    def __init__(self, entities: EntitiesLayer, ecology: EcologyLayer | None = None) -> None:
        self.ecology = ecology or EcologyLayer()
        self.entities = entities
        self._layers = {"ecology": self.ecology, "entities": entities}

    def query_fn(self, layer_name: str, query: Query) -> Answer:
        if layer_name not in self._layers:
            raise LayerError(f"no layer {layer_name!r} in this world")
        return self._layers[layer_name].query(query)

    def emit_fn(self, event: object) -> ActionResult:
        assert isinstance(event, Event)
        self.ecology.handle_event(event, self.query_fn, self.emit_fn)
        return ActionResult()

    def activate(self, time: GameDateTime = TIME) -> None:
        self.entities.update_activation(time, query_fn=self.query_fn, emit_fn=self.emit_fn)

    def attack(self, attacker_id: str, target_id: str) -> ActionResult:
        event = Event(
            event_type=EventType.ENTITY_ATTACK_REQUESTED,
            source_layer="entities",
            data=AttackRequestedPayload(attacker_id=attacker_id, target_id=target_id),
        )
        return self.entities.handle_event(event, self.query_fn, self.emit_fn)


def _wolves(layer: EntitiesLayer) -> list[Creature]:
    return [e for e in layer.get_active_creatures() if e.squad_id == "pack"]


# ---------------------------------------------------------------------------
# Indexes kept in step by add/remove
# ---------------------------------------------------------------------------


class TestEntityIndexes:
    @staticmethod
    def _watcher() -> Creature:
        return parse_npc(
            "watcher",
            {
                "name": "Watcher",
                "start_location": "tower",
                "triggers": [
                    {
                        "id": "war_duty",
                        "on": {"event": "war_declared", "match": {"aggressor_id": "north"}},
                        "until": {"event": "peace_declared", "match": {"nation_a_id": "north"}},
                    }
                ],
            },
        )

    @staticmethod
    def _war() -> Event:
        return Event(
            event_type=EventType.WAR_DECLARED,
            source_layer="politics",
            data=WarDeclaredPayload(aggressor_id="north", target_id="south"),
        )

    def test_added_entity_is_reachable_through_every_lookup(self) -> None:
        layer = EntitiesLayer()
        watcher = self._watcher()
        layer.add_entity(watcher)

        assert layer.get_entity("watcher") is watcher
        assert watcher in layer.get_active_creatures()
        assert [m.creature for m in layer.find_trigger_matches(self._war())] == [watcher]
        ids = [c["id"] for c in layer.query(Query(question=QueryType.ALL_CREATURES)).value]
        assert ids == ["watcher"]

    def test_removed_entity_leaves_every_lookup(self) -> None:
        watcher = self._watcher()
        layer = EntitiesLayer([watcher])

        layer.remove_entity("watcher")

        assert layer.get_entity("watcher") is None
        assert layer.get_active_creatures() == []
        assert layer.find_trigger_matches(self._war()) == []
        assert layer.query(Query(question=QueryType.ALL_CREATURES)).value == []

    def test_dormant_creature_is_not_an_active_creature(self) -> None:
        awake = Creature(id="awake", name="Awake", location_id="a")
        asleep = Creature(id="asleep", name="Asleep", location_id="a", active=False)
        layer = EntitiesLayer([awake, asleep])

        assert layer.get_active_creatures() == [awake]


class TestNearestWakeTime:
    def test_minimum_over_timed_and_travel_intents(self) -> None:
        sleeper = Creature(
            id="sleeper",
            name="Sleeper",
            location_id="inn",
            current_intent=TimedIntent(kind=IntentType.SLEEP, started_at_seconds=0, wake_at_seconds=900),
        )
        traveller = Creature(
            id="traveller",
            name="Traveller",
            location_id="road",
            current_intent=TravelIntent(
                started_at_seconds=0, destination_id="town", remaining_route=("town",), next_arrival_seconds=300
            ),
        )
        idle = Creature(id="idle", name="Idle", location_id="inn")
        layer = EntitiesLayer([sleeper, idle, traveller])

        assert layer.get_nearest_wake_time() == 300

        layer.remove_entity("traveller")
        assert layer.get_nearest_wake_time() == 900


# ---------------------------------------------------------------------------
# handle_event routing and combat-end hooks
# ---------------------------------------------------------------------------


class TestHandleEvent:
    def test_plain_event_is_logged_where_its_actor_stands(self) -> None:
        hero = _player(location="square")
        crier = Character(id="crier", name="Crier", location_id="square")
        stranger = Character(id="stranger", name="Stranger", location_id="docks")
        layer = EntitiesLayer([hero, crier, stranger])
        shout = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data=EntitySayPayload(entity_id="crier", text="Hear ye!"),
        )

        result = layer.handle_event(shout, _noop_query_fn, _noop_emit_fn)

        assert result.success
        heard = layer.query(Query(question=QueryType.NEW_RAW_EVENTS, params={"entity_id": "hero"})).value
        assert heard == [shout]
        elsewhere = layer.query(Query(question=QueryType.NEW_RAW_EVENTS, params={"entity_id": "stranger"})).value
        assert elsewhere == []

    def test_death_of_a_temporary_spawn_from_another_layer_keeps_it(self) -> None:
        # Only the entities layer's own death events clean up a temporary spawn.
        spawn = Creature(id="boar", name="Boar", location_id="forest", temporary=True, current_hp=0)
        layer = EntitiesLayer([spawn])
        death = Event(
            event_type=EventType.ENTITY_DIED,
            source_layer="ecology",
            data=EntityDiedPayload(entity_id="boar"),
        )

        layer.handle_event(death, _noop_query_fn, _noop_emit_fn)

        assert layer.get_entity("boar") is spawn

    def test_combat_ending_attack_digests_every_participant_once(self) -> None:
        # A one-hit kill ends the fight inside handle_event: the layer's combat-end hook
        # must consume the witnesses' buffers (COMBAT_ENDED), not leave them for later.
        hero = _player(location="square")
        hero.attacks = (
            Attack(name="maul", ability=Ability.STR, damage=(DamageComponent("50", DamageType.BLUDGEONING),)),
        )
        hero.faction_id = "town"
        rat = Creature(id="rat", name="Rat", location_id="square", max_hp=1, current_hp=1, ac=1, faction_id="vermin")
        witness = Character(
            id="witness",
            name="Witness",
            location_id="square",
            faction_id="town",
            inner_self=InnerSelf(),
        )

        class _HitDice(random.Random):
            def randint(self, a: int, b: int) -> int:
                return 15 if (a, b) == (1, 20) else super().randint(a, b)

        layer = EntitiesLayer([hero, rat, witness], dice_rng=_HitDice(0))
        attack = Event(
            event_type=EventType.ENTITY_ATTACK_REQUESTED,
            source_layer="entities",
            data=AttackRequestedPayload(attacker_id="hero", target_id="rat"),
        )

        def politics(layer_name: str, query: Query) -> Answer:
            if query.question is QueryType.FACTION_RELATION:
                same = query.params["a"] == query.params["b"]
                return Answer(value=FactionRelation.FRIENDLY if same else FactionRelation.HOSTILE)
            return Answer(value=None)

        layer.handle_event(attack, politics, _noop_emit_fn)

        assert not rat.is_alive
        assert layer.get_combat("square") is None
        assert layer.get_combat_locations() == []
        assert not hero.in_combat and not witness.in_combat
        assert witness.inner_self is not None
        assert witness.inner_self.perceived_event_buffer == []


# ---------------------------------------------------------------------------
# Activation + awareness + combat + materialization, one scene end to end
# ---------------------------------------------------------------------------


class TestSceneLifecycle:
    def _scene(self, pack: Squad) -> _World:
        layer = EntitiesLayer(
            [_player()],
            monster_templates={"wolf": _wolf_template()},
            seed=11,
            dice_rng=_MissingDice(5),
        )
        return _World(layer, EcologyLayer(squads=[pack]))

    def test_arrival_materializes_the_pack_into_awareness_and_a_fight(self) -> None:
        world = self._scene(_pack())
        layer = world.entities
        hero = layer.get_entity("hero")
        assert isinstance(hero, PlayerCharacter)

        world.activate()
        wolves = _wolves(layer)
        assert len(wolves) == 3
        assert all(w.active and w.temporary for w in wolves)

        peaceful = layer.build_awareness(hero, TIME, world.query_fn)
        assert isinstance(peaceful, PeacefulAwareness)
        assert {n.id for n in peaceful.nearby} == {w.id for w in wolves}

        result = world.attack("hero", wolves[0].id)
        assert result.success

        combat = layer.get_combat("forest")
        assert combat is not None
        assert layer.get_active_combat_for("hero") is combat
        assert set(combat.turn_order) == {"hero", *(w.id for w in wolves)}
        assert all(w.in_combat for w in wolves) and hero.in_combat

        fighting = layer.build_awareness(hero, TIME, world.query_fn)
        assert isinstance(fighting, CombatAwareness)
        assert {n.id for n in fighting.nearby} == {w.id for w in wolves}
        assert all(n.is_hostile for n in fighting.nearby)

        info = layer.query(Query(question=QueryType.COMBAT_INFO, params={"location_id": "forest"})).value
        assert info["turn_order"] == combat.turn_order
        assert set(info["positions"]) == set(combat.turn_order)

    def test_mid_fight_save_load_resumes_and_the_pack_goes_home_intact(self) -> None:
        pack = _pack()
        world = self._scene(pack)
        world.activate()
        wolf_ids = sorted(w.id for w in _wolves(world.entities))
        world.attack("hero", wolf_ids[0])
        live_combat = world.entities.get_combat("forest")
        assert live_combat is not None
        saved = world.entities.get_state()

        # A fresh layer built from content (the player only) plus the save.
        restored = EntitiesLayer([_player()], monster_templates={"wolf": _wolf_template()}, dice_rng=_MissingDice(6))
        restored.load_state(saved)
        world_after = _World(restored, world.ecology)  # the ecology side keeps the same live squad

        combat = restored.get_combat("forest")
        assert combat is not None
        assert combat.turn_order == live_combat.turn_order
        assert combat.battle_map.positions == live_combat.battle_map.positions
        assert sorted(w.id for w in _wolves(restored)) == wolf_ids
        hero = restored.get_entity("hero")
        assert isinstance(hero, PlayerCharacter) and hero.in_combat
        assert isinstance(restored.build_awareness(hero, TIME, world_after.query_fn), CombatAwareness)

        # A reload must not materialize the pack a second time.
        world_after.activate()
        assert sorted(w.id for w in _wolves(restored)) == wolf_ids

        # Two quiet rounds end the fight; everyone leaves combat, awareness is peaceful again.
        restored.end_combat_round("forest")
        restored.end_combat_round("forest")
        restored.end_combat_round("forest")
        assert restored.get_combat("forest") is None
        assert not any(c.in_combat for c in restored.get_active_creatures())
        assert isinstance(restored.build_awareness(hero, TIME, world_after.query_fn), PeacefulAwareness)

        # The hero walks away: the untouched pack dematerializes at full strength.
        hero.location_id = "road"
        world_after.activate()
        assert _wolves(restored) == []
        assert all(restored.get_entity(wid) is None for wid in wolf_ids)
        assert pack.strength == 6
