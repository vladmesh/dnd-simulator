"""Tests for squad event perception pipeline.

Squad events (SQUAD_MOVE, SQUAD_COMBAT, SQUAD_MATERIALIZED, SQUAD_DEMATERIALIZED)
must flow through the location log and appear as PerceivedEvents for players.
"""

from __future__ import annotations

from dnd_simulator.core.character import (
    Ability,
    AbilityScores,
    Attack,
    Character,
    Creature,
    DamageComponent,
    DamageType,
    Race,
)
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.perception import perceive_event


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _make_player(location: str = "forest_road") -> Character:
    return Character(
        id="player_1",
        name="Hero",
        location_id=location,
        race=Race.HUMAN,
    )


def _get_entity_fn(*entities: Creature | Character):
    by_id = {e.id: e for e in entities}
    return lambda eid: by_id.get(eid)


def _make_squad_move_event(squad_name: str, from_loc: str, to_loc: str) -> Event:
    return Event(
        event_type=EventType.SQUAD_MOVE,
        source_layer="ecology",
        data={
            "squad_id": "orc_patrol",
            "squad_name": squad_name,
            "from": from_loc,
            "to": to_loc,
        },
        description=f"{squad_name} moved from {from_loc} to {to_loc}",
    )


def _make_squad_combat_event(
    location: str,
    winner_name: str,
    loser_name: str,
    loser_strength: int = 0,
) -> Event:
    return Event(
        event_type=EventType.SQUAD_COMBAT,
        source_layer="ecology",
        data={
            "location_id": location,
            "winner_id": "guards",
            "winner_name": winner_name,
            "loser_id": "wolves",
            "loser_name": loser_name,
            "winner_strength": 12,
            "loser_strength": loser_strength,
        },
        description=f"{winner_name} defeated {loser_name}",
    )


class TestSquadMovePerception:
    """Squad movement events reach the player's perception."""

    def test_squad_move_to_player_location_perceived(self) -> None:
        """Player sees a squad arriving at their location."""
        player = _make_player("forest_road")
        layer = EntitiesLayer(entities=[player])

        event = _make_squad_move_event("Orc Patrol", "swamp", "forest_road")
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

        perceived = layer.get_perceived_events(player)
        assert len(perceived) == 1
        assert perceived[0].event_type == EventType.SQUAD_MOVE
        assert "Orc Patrol" in perceived[0].description

    def test_squad_move_away_not_perceived(self) -> None:
        """Player does NOT see squad events at other locations."""
        player = _make_player("forest_road")
        layer = EntitiesLayer(entities=[player])

        event = _make_squad_move_event("Orc Patrol", "swamp", "distant_cave")
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

        perceived = layer.get_perceived_events(player)
        assert len(perceived) == 0

    def test_squad_move_from_player_location_perceived(self) -> None:
        """Player sees a squad departing from their location."""
        player = _make_player("forest_road")
        layer = EntitiesLayer(entities=[player])

        event = _make_squad_move_event("Orc Patrol", "forest_road", "swamp")
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

        perceived = layer.get_perceived_events(player)
        assert len(perceived) == 1
        assert perceived[0].event_type == EventType.SQUAD_MOVE


class TestSquadCombatPerception:
    """Squad combat events reach the player's perception."""

    def test_squad_combat_at_player_location_perceived(self) -> None:
        """Player sees squad combat at their location."""
        player = _make_player("forest_road")
        layer = EntitiesLayer(entities=[player])

        event = _make_squad_combat_event("forest_road", "Town Guard", "Wolf Pack")
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

        perceived = layer.get_perceived_events(player)
        assert len(perceived) == 1
        assert perceived[0].event_type == EventType.SQUAD_COMBAT
        assert "Town Guard" in perceived[0].description
        assert "Wolf Pack" in perceived[0].description

    def test_squad_combat_at_other_location_not_perceived(self) -> None:
        """Player does NOT see squad combat at other locations."""
        player = _make_player("forest_road")
        layer = EntitiesLayer(entities=[player])

        event = _make_squad_combat_event("distant_cave", "Town Guard", "Wolf Pack")
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

        perceived = layer.get_perceived_events(player)
        assert len(perceived) == 0


class TestSquadMaterializationEvent:
    """_materialize_squad emits a SQUAD_MATERIALIZED event into the location log."""

    def test_materialize_squad_emits_event(self) -> None:
        """Materializing a squad produces a SQUAD_MATERIALIZED event visible to the player."""
        player = _make_player("forest_road")
        template = MonsterTemplate(
            id="orc",
            name="Orc",
            hp=15,
            ac=13,
            speed=30,
            ability_scores=AbilityScores(),
            attacks=(
                Attack(
                    name="greataxe",
                    ability=Ability.STR,
                    damage=(DamageComponent(dice="1d12", type=DamageType.SLASHING),),
                ),
            ),
            cr=0.5,
            faction_id="orcs",
        )
        layer = EntitiesLayer(entities=[player], monster_templates={"orc": template})

        squad_info = {
            "id": "orc_patrol",
            "name": "Orc Patrol",
            "faction_id": "orcs",
            "current_location_id": "forest_road",
            "member_templates": ["orc", "orc"],
            "strength": 4,
            "max_strength": 4,
        }

        layer._activation._materialize_squad("orc_patrol", squad_info, type(None))  # brain_cls unused in this test path

        perceived = layer.get_perceived_events(player)
        assert len(perceived) == 1
        assert perceived[0].event_type == EventType.SQUAD_MATERIALIZED
        assert "Orc Patrol" in perceived[0].description


class TestSquadDematerializationPerception:
    """SQUAD_DEMATERIALIZED events are perceived at the right location."""

    def test_dematerialize_event_perceived(self) -> None:
        """Player sees a dematerialization event at their location."""
        player = _make_player("forest_road")
        layer = EntitiesLayer(entities=[player])

        event = Event(
            event_type=EventType.SQUAD_DEMATERIALIZED,
            source_layer="entities",
            data={
                "squad_id": "orc_patrol",
                "squad_name": "Orc Patrol",
                "location_id": "forest_road",
                "new_strength": 3,
            },
            description="Squad orc_patrol dematerialized",
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)

        perceived = layer.get_perceived_events(player)
        assert len(perceived) == 1
        assert perceived[0].event_type == EventType.SQUAD_DEMATERIALIZED
        assert "Orc Patrol" in perceived[0].description


class TestPerceiveSquadEvents:
    """perceive_event produces readable descriptions for squad events."""

    def test_perceive_squad_move_arrival(self) -> None:
        observer = _make_player("forest_road")
        event = _make_squad_move_event("Orc Patrol", "swamp", "forest_road")
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "Orc Patrol" in result

    def test_perceive_squad_combat(self) -> None:
        observer = _make_player("forest_road")
        event = _make_squad_combat_event("forest_road", "Town Guard", "Wolf Pack", loser_strength=0)
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "Town Guard" in result
        assert "Wolf Pack" in result

    def test_perceive_squad_materialized(self) -> None:
        observer = _make_player("forest_road")
        event = Event(
            event_type=EventType.SQUAD_MATERIALIZED,
            source_layer="entities",
            data={
                "squad_id": "orc_patrol",
                "squad_name": "Orc Patrol",
                "location_id": "forest_road",
                "creature_count": 3,
            },
            description="Squad materialized",
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "Orc Patrol" in result

    def test_perceive_squad_dematerialized(self) -> None:
        observer = _make_player("forest_road")
        event = Event(
            event_type=EventType.SQUAD_DEMATERIALIZED,
            source_layer="entities",
            data={
                "squad_id": "orc_patrol",
                "squad_name": "Orc Patrol",
                "location_id": "forest_road",
                "new_strength": 3,
            },
            description="Squad dematerialized",
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "Orc Patrol" in result
