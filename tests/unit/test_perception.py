"""Tests for event perception and region log."""

from __future__ import annotations

from dnd_simulator.core.character import Ability, Attack, Character, DamageComponent, DamageType, Entity, Race
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, Query
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.perception import perceive_event


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _get_entity_fn(*entities: Entity):
    """Build a simple get_entity function from a list of entities."""
    by_id = {e.id: e for e in entities}
    return lambda eid: by_id.get(eid)


class TestPerceiveEvent:
    def test_say_from_other(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        speaker = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data={"entity_id": "smith", "text": "Добро пожаловать!"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, speaker))
        assert "says" in result
        assert "Добро пожаловать!" in result
        assert "dwarf" in result

    def test_say_from_self(self) -> None:
        observer = Character(id="smith", name="Smith", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data={"entity_id": "smith", "text": "Привет!"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "You say" in result

    def test_attack_observer_is_target(self) -> None:
        observer = Character(id="smith", name="Smith", location_id="r1")
        attacker = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "player", "target_id": "smith", "weapon": "longsword", "damage": 5},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, attacker))
        assert "attacks you" in result
        assert "longsword" in result
        assert "5 damage" in result

    def test_attack_observer_is_attacker(self) -> None:
        observer = Character(id="player", name="Hero", location_id="r1")
        target = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "player", "target_id": "smith", "weapon": "longsword"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, target))
        assert "You attack" in result

    def test_attack_observer_is_bystander(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        attacker = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        target = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_ATTACK,
            source_layer="entities",
            data={"attacker_id": "player", "target_id": "smith"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, attacker, target))
        assert "elf" in result
        assert "dwarf" in result
        assert "attacks" in result

    def test_death_other(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        victim = Character(id="smith", name="Smith", location_id="r1", race=Race.DWARF)
        event = Event(
            event_type=EventType.ENTITY_DIED,
            source_layer="entities",
            data={"entity_id": "smith"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer, victim))
        assert "dies" in result
        assert "dwarf" in result

    def test_death_self(self) -> None:
        observer = Character(id="smith", name="Smith", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_DIED,
            source_layer="entities",
            data={"entity_id": "smith"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "You die" in result

    def test_unknown_event(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        event = Event(
            event_type=EventType.WEATHER_CHANGED,
            source_layer="geography",
            data={},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "Something happened" in result

    def test_unknown_entity_id(self) -> None:
        observer = Character(id="guard", name="Guard", location_id="r1")
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data={"entity_id": "unknown_npc", "text": "Бу!"},
        )
        result = perceive_event(event, observer, _get_entity_fn(observer))
        assert "someone" in result
        assert "Бу!" in result


class TestRegionLog:
    def test_handle_event_logs_say(self) -> None:
        smith = Character(id="smith", name="Smith", location_id="r1")
        layer = EntitiesLayer(entities=[smith])
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data={"entity_id": "smith", "text": "Привет!"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        log = layer.get_perceived_log(smith)
        assert len(log) == 1
        assert "Привет!" in log[0]

    def test_log_only_for_same_region(self) -> None:
        smith = Character(id="smith", name="Smith", location_id="r1")
        guard = Character(id="guard", name="Guard", location_id="r2")
        layer = EntitiesLayer(entities=[smith, guard])
        event = Event(
            event_type=EventType.ENTITY_SAY,
            source_layer="entities",
            data={"entity_id": "smith", "text": "Привет!"},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        assert len(layer.get_perceived_log(smith)) == 1
        assert len(layer.get_perceived_log(guard)) == 0

    def test_new_perceived_events_tracks_index(self) -> None:
        smith = Character(id="smith", name="Smith", location_id="r1")
        player = Character(id="player", name="Hero", location_id="r1", race=Race.ELF)
        layer = EntitiesLayer(entities=[smith, player])

        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data={"entity_id": "player", "text": "Первое!"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        new1 = layer.get_new_perceived_events(smith)
        assert len(new1) == 1

        # Second call without new events — empty
        new2 = layer.get_new_perceived_events(smith)
        assert len(new2) == 0

        # Add another event
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data={"entity_id": "player", "text": "Второе!"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        new3 = layer.get_new_perceived_events(smith)
        assert len(new3) == 1
        assert "Второе!" in new3[0]

        # Full log still has everything
        full = layer.get_perceived_log(smith)
        assert len(full) == 2

    def test_non_logged_events_ignored(self) -> None:
        smith = Character(id="smith", name="Smith", location_id="r1")
        layer = EntitiesLayer(entities=[smith])
        event = Event(
            event_type=EventType.WEATHER_CHANGED,
            source_layer="geography",
            data={},
        )
        layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        assert len(layer.get_perceived_log(smith)) == 0

    def test_multiple_events_in_order(self) -> None:
        from dnd_simulator.core.combat import Position

        smith = Character(id="smith", name="Smith", location_id="r1", max_hp=100, current_hp=100)
        sword = Attack(
            name="longsword",
            ability=Ability.STR,
            damage=(DamageComponent("1d8", DamageType.SLASHING),),
        )
        player = Character(id="player", name="Hero", location_id="r1", race=Race.ELF, attacks=(sword,))
        layer = EntitiesLayer(entities=[smith, player])

        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_SAY,
                source_layer="entities",
                data={"entity_id": "player", "text": "Готовься!"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        # First attack starts combat — place in melee range, then attack again
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "player", "target_id": "smith", "weapon": "longsword"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        combat = layer.get_combat("r1")
        assert combat is not None
        combat.battle_map.set_position("player", Position(30, 30))
        combat.battle_map.set_position("smith", Position(35, 30))
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK,
                source_layer="entities",
                data={"attacker_id": "player", "target_id": "smith", "weapon": "longsword"},
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )

        log = layer.get_perceived_log(smith)
        assert "Готовься!" in log[0]
        assert "Combat started" in log[1]
        assert any("attacks you" in line for line in log)
