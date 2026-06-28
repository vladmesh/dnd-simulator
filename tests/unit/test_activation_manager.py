"""Tests for ActivationManager extracted from EntitiesLayer."""

from __future__ import annotations

from unittest.mock import patch

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Creature,
    DamageComponent,
    DamageType,
)
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
from dnd_simulator.core.monster import EncounterEntry, MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer

_SWORD = Attack(
    name="longsword",
    ability=Ability.STR,
    damage=(DamageComponent("1d8", DamageType.SLASHING),),
)

_TIME_0 = GameDateTime(year=1490, month=6, day=1, hour=12)
_TIME_LATER = GameDateTime(year=1490, month=6, day=1, hour=12, minute=15)  # +15 min = 900 seconds


def _noop_query_fn(layer: str, query: Query) -> Answer:
    if layer == "ecology" and query.question in (QueryType.SQUADS_AT_LOCATION, QueryType.LAIRS_AT_LOCATION):
        return Answer(value=[])
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _wolf_template() -> MonsterTemplate:
    return MonsterTemplate(
        id="wolf",
        name="Wolf",
        hp=11,
        ac=13,
        speed=40,
        attacks=(_SWORD,),
        ability_scores=AbilityScores(),
        cr=0.25,
        faction_id="wild_beasts",
    )


class TestProximityActivation:
    """Player at location A activates NPCs there; moving to B activates B, dormifies A."""

    def test_npc_at_player_location_activates(self) -> None:
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="village",
            race="human",
            char_class="fighter",
        )
        npc_near = Creature(id="n1", name="Guard", location_id="village", active=False)
        npc_far = Creature(id="n2", name="Farmer", location_id="farm", active=False)

        layer = EntitiesLayer([player, npc_near, npc_far])
        layer.update_activation(_TIME_0)

        assert npc_near.active is True
        assert npc_far.active is False

    def test_moving_player_reactivates(self) -> None:
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="village",
            race="human",
            char_class="fighter",
        )
        npc_a = Creature(id="n1", name="Guard", location_id="village", active=False)
        npc_b = Creature(id="n2", name="Farmer", location_id="farm", active=False)

        layer = EntitiesLayer([player, npc_a, npc_b])
        layer.update_activation(_TIME_0)
        assert npc_a.active is True
        assert npc_b.active is False

        # Player moves to farm
        player.location_id = "farm"
        layer.update_activation(_TIME_0)
        assert npc_a.active is False
        assert npc_b.active is True


class TestEncounterCooldown:
    """Encounter cooldown prevents re-rolling within 600 game-seconds."""

    def test_cooldown_blocks_second_roll(self) -> None:
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="forest",
            race="human",
            char_class="fighter",
        )
        template = _wolf_template()
        encounter = EncounterEntry(template_id="wolf", chance=1.0, count_min=1, count_max=1)

        layer = EntitiesLayer(
            [player],
            monster_templates={"wolf": template},
            encounter_tables={"forest": [encounter]},
        )

        # First activation at forest — should trigger encounter
        with patch("random.random", return_value=0.0), patch("random.randint", return_value=1):
            layer.update_activation(_TIME_0, query_fn=_noop_query_fn)

        spawned_count_1 = sum(1 for e in layer._entities.values() if e.id.startswith("wolf_"))
        assert spawned_count_1 == 1

        # Player leaves and returns within cooldown (same time)
        player.location_id = "village"
        layer.update_activation(_TIME_0, query_fn=_noop_query_fn)
        player.location_id = "forest"
        layer.update_activation(_TIME_0, query_fn=_noop_query_fn)

        spawned_count_2 = sum(1 for e in layer._entities.values() if e.id.startswith("wolf_"))
        assert spawned_count_2 == spawned_count_1  # no new spawn

    def test_encounter_rolls_after_cooldown_expires(self) -> None:
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="forest",
            race="human",
            char_class="fighter",
        )
        template = _wolf_template()
        encounter = EncounterEntry(template_id="wolf", chance=1.0, count_min=1, count_max=1)

        layer = EntitiesLayer(
            [player],
            monster_templates={"wolf": template},
            encounter_tables={"forest": [encounter]},
        )

        # First encounter
        with patch("random.random", return_value=0.0), patch("random.randint", return_value=1):
            layer.update_activation(_TIME_0, query_fn=_noop_query_fn)

        spawned_count_1 = sum(1 for e in layer._entities.values() if e.id.startswith("wolf_"))
        assert spawned_count_1 == 1

        # Leave and come back after 900 seconds (> 600 cooldown)
        player.location_id = "village"
        layer.update_activation(_TIME_LATER, query_fn=_noop_query_fn)
        player.location_id = "forest"
        with patch("random.random", return_value=0.0), patch("random.randint", return_value=1):
            layer.update_activation(_TIME_LATER, query_fn=_noop_query_fn)

        spawned_count_2 = sum(1 for e in layer._entities.values() if e.id.startswith("wolf_"))
        assert spawned_count_2 == 2  # new wolf spawned


class TestSquadMaterialization:
    """Squad materialization spawns creatures on player arrival, despawns on departure."""

    def _make_layer_with_squad(self) -> tuple[EntitiesLayer, PlayerCharacter]:
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="camp",
            race="human",
            char_class="fighter",
        )
        template = _wolf_template()
        layer = EntitiesLayer([player], monster_templates={"wolf": template})
        return layer, player

    def _squad_query_fn(self, active_squad: bool = True) -> object:
        """Returns a query_fn that provides squad info at 'camp' when active_squad=True."""

        def query_fn(target: str, query: Query) -> Answer:
            if target == "ecology" and query.question == QueryType.SQUADS_AT_LOCATION:
                if active_squad and query.params.get("location_id") == "camp":
                    return Answer(
                        value=[
                            {
                                "id": "squad_1",
                                "name": "Wolf Pack",
                                "member_templates": ["wolf", "wolf", "wolf"],
                                "strength": 100,
                                "max_strength": 100,
                                "faction_id": "wild_beasts",
                                "current_location_id": "camp",
                            }
                        ]
                    )
                return Answer(value=[])
            if target == "ecology" and query.question == QueryType.LAIRS_AT_LOCATION:
                return Answer(value=[])
            return Answer(value=None)

        return query_fn

    def test_squad_spawns_on_player_arrival(self) -> None:
        layer, _player = self._make_layer_with_squad()
        query_fn = self._squad_query_fn(active_squad=True)

        layer.update_activation(_TIME_0, query_fn=query_fn, emit_fn=_noop_emit_fn)

        wolves = [e for e in layer._entities.values() if e.id.startswith("wolf_")]
        assert len(wolves) == 3

    def test_squad_despawns_on_player_departure(self) -> None:
        layer, player = self._make_layer_with_squad()
        query_fn = self._squad_query_fn(active_squad=True)

        layer.update_activation(_TIME_0, query_fn=query_fn, emit_fn=_noop_emit_fn)
        wolves_before = [e for e in layer._entities.values() if e.id.startswith("wolf_")]
        assert len(wolves_before) == 3

        # Player leaves — squad no longer at active location
        player.location_id = "village"
        no_squad_qfn = self._squad_query_fn(active_squad=False)
        layer.update_activation(_TIME_0, query_fn=no_squad_qfn, emit_fn=_noop_emit_fn)

        wolves_after = [e for e in layer._entities.values() if e.id.startswith("wolf_")]
        assert len(wolves_after) == 0

    def test_squad_strength_reduced_after_kill(self) -> None:
        layer, player = self._make_layer_with_squad()
        query_fn = self._squad_query_fn(active_squad=True)

        # Materialize
        layer.update_activation(_TIME_0, query_fn=query_fn, emit_fn=_noop_emit_fn)
        wolves = [e for e in layer._entities.values() if isinstance(e, Creature) and e.id.startswith("wolf_")]
        assert len(wolves) == 3

        # Kill one wolf
        wolves[0].current_hp = 0

        # Dematerialize (player leaves)
        emitted: list[Event] = []

        def capture_emit(event: object) -> ActionResult:
            if isinstance(event, Event):
                emitted.append(event)
            return ActionResult()

        player.location_id = "village"
        no_squad_qfn = self._squad_query_fn(active_squad=False)
        layer.update_activation(_TIME_0, query_fn=no_squad_qfn, emit_fn=capture_emit)

        # Check strength was reduced in emitted event
        demat_events = [e for e in emitted if e.event_type == EventType.SQUAD_DEMATERIALIZED]
        assert len(demat_events) == 1
        # 2 alive out of 3 spawned, original strength 100 → ~67
        new_strength = demat_events[0].data["new_strength"]
        assert new_strength < 100
        assert new_strength > 0


class TestHostileEncounterAutoCombat:
    """Encounter-spawned hostile creatures auto-start combat."""

    def test_hostile_spawn_starts_combat(self) -> None:
        player = PlayerCharacter(
            id="p1",
            name="Hero",
            location_id="forest",
            race="human",
            char_class="fighter",
            faction_id="adventurers",
        )
        template = _wolf_template()
        encounter = EncounterEntry(template_id="wolf", chance=1.0, count_min=1, count_max=1)

        layer = EntitiesLayer(
            [player],
            monster_templates={"wolf": template},
            encounter_tables={"forest": [encounter]},
        )

        def hostile_query_fn(target: str, query: Query) -> Answer:
            if target == "politics" and query.question == QueryType.FACTION_RELATION:
                return Answer(value=FactionRelation.HOSTILE)
            if target == "ecology" and query.question in (
                QueryType.SQUADS_AT_LOCATION,
                QueryType.LAIRS_AT_LOCATION,
            ):
                return Answer(value=[])
            return Answer(value=None)

        with patch("random.random", return_value=0.0), patch("random.randint", return_value=1):
            layer.update_activation(_TIME_0, query_fn=hostile_query_fn)

        # Combat should have started at forest
        combat = layer._combat.get_combat("forest")
        assert combat is not None
        assert len(combat.turn_order) >= 2
