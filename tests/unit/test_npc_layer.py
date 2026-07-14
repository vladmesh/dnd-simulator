"""Tests for the entities layer."""

from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.character import Creature, Entity, NpcRole
from dnd_simulator.core.events import AttackRequestedPayload, WeatherChangedPayload
from dnd_simulator.core.models import ActionResult, Answer, Event, EventType, GameDateTime, Query, QueryType, TimeDelta
from dnd_simulator.core.npc_memory import NpcMemory
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import (
    Npc,
    hour_in_range,
    resolve_schedule,
)

_TIME = GameDateTime(year=1490, month=6, day=1, hour=12)


def _noop_query_fn(layer: str, query: Query) -> Answer:
    return Answer(value=None)


def _noop_emit_fn(event: object) -> ActionResult:
    return ActionResult()


def _make_npcs() -> list[Npc]:
    return [
        Npc(
            id="smith",
            name="Edgar the Smith",
            location_id="silverport",
            role=NpcRole.BLACKSMITH,
            personality="Gruff but fair.",
            settlement_id="silverport_city",
            schedule=resolve_schedule(NpcRole.BLACKSMITH, "silverport_city"),
        ),
        Npc(
            id="guard",
            name="Guard Rodrik",
            location_id="silverport",
            role=NpcRole.GUARD,
            personality="Disciplined.",
            settlement_id="silverport_city",
            schedule=resolve_schedule(NpcRole.GUARD, "silverport_city"),
        ),
        Npc(
            id="farmer",
            name="Old Bran",
            location_id="highfield",
            role=NpcRole.FARMER,
            personality="Quiet.",
            settlement_id="highfield_town",
            schedule=resolve_schedule(NpcRole.FARMER, "highfield_town"),
        ),
    ]


def _make_layer() -> EntitiesLayer:
    return EntitiesLayer(entities=_make_npcs())


class TestHourInRange:
    def test_normal_range(self) -> None:
        assert hour_in_range(12, 8, 20) is True
        assert hour_in_range(7, 8, 20) is False
        assert hour_in_range(20, 8, 20) is False

    def test_midnight_wrap(self) -> None:
        assert hour_in_range(23, 22, 6) is True
        assert hour_in_range(0, 22, 6) is True
        assert hour_in_range(5, 22, 6) is True
        assert hour_in_range(6, 22, 6) is False
        assert hour_in_range(12, 22, 6) is False


class TestLayerBasics:
    def test_name(self) -> None:
        layer = _make_layer()
        assert layer.name == "entities"

    def test_handle_event_returns_empty(self) -> None:
        layer = _make_layer()
        event = Event(
            event_type=EventType.WEATHER_CHANGED,
            source_layer="geography",
            data=WeatherChangedPayload("r1", "clear", "rain", 10.0),
        )
        result = layer.handle_event(event, _noop_query_fn, _noop_emit_fn)
        assert result.success
        assert result.events == []


class TestGetEntity:
    def test_get_existing(self) -> None:
        layer = _make_layer()
        entity = layer.get_entity("smith")
        assert entity is not None
        assert entity.name == "Edgar the Smith"

    def test_get_missing(self) -> None:
        layer = _make_layer()
        assert layer.get_entity("nonexistent") is None

    def test_returns_direct_reference(self) -> None:
        layer = _make_layer()
        entity = layer.get_entity("smith")
        assert entity is not None
        entity.name = "Modified"
        assert layer.get_entity("smith") is not None
        assert layer.get_entity("smith").name == "Modified"


class TestAddRemove:
    def test_add_entity(self) -> None:
        layer = EntitiesLayer()
        wolf = Creature(id="wolf1", name="Dire Wolf", location_id="greenwood")
        layer.add_entity(wolf)
        assert layer.get_entity("wolf1") is wolf

    def test_remove_entity(self) -> None:
        layer = _make_layer()
        layer.remove_entity("smith")
        assert layer.get_entity("smith") is None

    def test_remove_nonexistent_is_noop(self) -> None:
        layer = _make_layer()
        layer.remove_entity("nonexistent")  # no error


class TestScheduleComputed:
    """Schedule is now computed, not stored as state."""

    def test_blacksmith_working_midday(self) -> None:
        smith = _make_npcs()[0]
        assert smith.scheduled_activity(12).value == "working"
        assert smith.scheduled_location(12) == "silverport_city_smithy"

    def test_blacksmith_sleeping_at_night(self) -> None:
        smith = _make_npcs()[0]
        assert smith.scheduled_activity(3).value == "sleeping"
        assert smith.scheduled_location(3) == "silverport_city_home"

    def test_blacksmith_idle_evening(self) -> None:
        smith = _make_npcs()[0]
        assert smith.scheduled_activity(20).value == "idle"
        assert smith.scheduled_location(20) == "silverport_city_tavern"

    def test_guard_working_daytime(self) -> None:
        guard = _make_npcs()[1]
        assert guard.scheduled_activity(14).value == "working"
        assert guard.scheduled_location(14) == "silverport_city_patrol"

    def test_guard_sleeping_at_night(self) -> None:
        guard = _make_npcs()[1]
        assert guard.scheduled_activity(23).value == "sleeping"

    def test_location_override(self) -> None:
        smith = _make_npcs()[0]
        smith.location_override = "tavern_special"
        assert smith.current_location(12) == "tavern_special"
        smith.location_override = None
        assert smith.current_location(12) == "silverport_city_smithy"


class TestEntitiesAtLocation:
    def test_entities_at_location(self) -> None:
        layer = _make_layer()
        result = layer.query(
            Query(question=QueryType.ENTITIES_AT_LOCATION, params={"location_id": "silverport", "hour": 12})
        )
        # NPCs are at their scheduled locations, not at "silverport"
        # Only non-NPC entities at "silverport" would show
        assert len(result.value) == 0

    def test_entity_info(self) -> None:
        layer = _make_layer()
        result = layer.query(Query(question=QueryType.ENTITY_INFO, params={"entity_id": "smith"}))
        assert result.value["name"] == "Edgar the Smith"
        assert result.value["role"] == "blacksmith"
        assert result.value["personality"] == "Gruff but fair."

    def test_unknown_query(self) -> None:
        layer = _make_layer()
        with pytest.raises(ValueError, match="Unknown entities query"):
            layer.query(Query(question="nonsense", params={}))


class TestMixedEntities:
    def test_player_and_npcs_coexist(self) -> None:
        npcs = _make_npcs()
        player = PlayerCharacter(id="player", name="Hero", location_id="silverport")
        layer = EntitiesLayer(entities=[*npcs, player])
        result = layer.query(
            Query(question=QueryType.ENTITIES_AT_LOCATION, params={"location_id": "silverport", "hour": 12})
        )
        names = {e["name"] for e in result.value}
        assert "Hero" in names
        # NPCs are at scheduled locations, not at "silverport" directly

    def test_creature_on_layer(self) -> None:
        wolf = Creature(id="wolf_alpha", name="Alpha Wolf", location_id="greenwood")
        layer = EntitiesLayer(entities=[wolf])
        entity = layer.get_entity("wolf_alpha")
        assert entity is not None
        assert entity.name == "Alpha Wolf"

    def test_tick_is_noop(self) -> None:
        """Tick does nothing — schedule is computed."""
        entity = Entity(id="rock", name="Magic Rock", location_id="cave")
        layer = EntitiesLayer(entities=[entity])
        layer.tick(TimeDelta(seconds=0), _TIME, _noop_query_fn, _noop_emit_fn)  # no error


class TestSaveLoad:
    def test_round_trip_preserves_location(self) -> None:
        layer = _make_layer()

        state = layer.get_state()
        new_layer = EntitiesLayer(entities=_make_npcs())
        new_layer.load_state(state)

        info = new_layer.query(Query(question=QueryType.ENTITY_INFO, params={"entity_id": "smith"}))
        assert info.value["location_id"] == "silverport"

    def test_npc_memory_persists(self) -> None:
        layer = _make_layer()
        smith = layer.get_entity("smith")
        assert isinstance(smith, Npc)
        smith.memory = NpcMemory(
            tags=["angry", "hates:orcs"],
            recent="War was declared last week.",
            inner_state="worried about iron supply",
            current_conversation="Player asked about iron supply.",
        )

        state = layer.get_state()
        new_layer = EntitiesLayer(entities=_make_npcs())
        new_layer.load_state(state)

        restored = new_layer.get_entity("smith")
        assert isinstance(restored, Npc)
        assert restored.memory.tags == ["angry", "hates:orcs"]
        assert restored.memory.recent == "War was declared last week."
        assert restored.memory.inner_state == "worried about iron supply"
        assert restored.memory.current_conversation == "Player asked about iron supply."

    def test_legacy_conversation_summary_without_memory_is_invalid(self) -> None:
        """Old saves without structured NPC memory fail validation."""
        layer = _make_layer()
        # Simulate old save format
        state = layer.get_state()
        entities = state["entities"]
        assert isinstance(entities, dict)
        smith_data = entities["smith"]
        assert isinstance(smith_data, dict)
        # Replace new memory format with legacy field
        del smith_data["memory"]
        smith_data["conversation_summary"] = "Old conversation data."

        new_layer = EntitiesLayer(entities=_make_npcs())
        with pytest.raises(ValueError, match="memory"):
            new_layer.load_state(state)

    def test_activation_persists(self) -> None:
        layer = _make_layer()
        smith = layer.get_entity("smith")
        assert smith is not None
        smith.active = False

        state = layer.get_state()
        new_layer = EntitiesLayer(entities=_make_npcs())
        new_layer.load_state(state)

        restored = new_layer.get_entity("smith")
        assert restored is not None
        assert restored.active is False

    def test_location_override_persists(self) -> None:
        layer = _make_layer()
        smith = layer.get_entity("smith")
        assert isinstance(smith, Npc)
        smith.location_override = "custom_spot"

        state = layer.get_state()
        new_layer = EntitiesLayer(entities=_make_npcs())
        new_layer.load_state(state)

        restored = new_layer.get_entity("smith")
        assert isinstance(restored, Npc)
        assert restored.location_override == "custom_spot"


def _mock_summarizer(updated_recent: str = "Fought in combat.") -> MagicMock:
    """Create a mock MemorySummarizer that returns updated memory."""
    summarizer = MagicMock()

    def _summarize(memory: NpcMemory, events: list[str], trigger: str) -> NpcMemory:
        return NpcMemory(
            tags=list(memory.tags),
            recent=updated_recent,
            inner_state="shaken",
            current_conversation="",
        )

    summarizer.summarize.side_effect = _summarize
    summarizer.needs_compression.return_value = False
    return summarizer


class TestCombatSummarization:
    """Test that combat end triggers NPC memory summarization."""

    def _setup_combat(self) -> tuple[EntitiesLayer, MagicMock]:
        """Set up a layer with two NPCs and a player, start real combat via attack."""
        player = PlayerCharacter(id="player", name="Hero", location_id="town_square")
        player.max_hp = 100
        player.current_hp = 100
        guard = Npc(
            id="guard",
            name="Guard",
            location_id="town_square",
            role=NpcRole.GUARD,
            personality="Brave.",
            settlement_id="town",
            memory=NpcMemory(tags=["loyal_to:player"]),
        )
        guard.max_hp = 100
        guard.current_hp = 100
        bandit = Npc(
            id="bandit",
            name="Bandit",
            location_id="town_square",
            role=NpcRole.COMMONER,
            personality="Ruthless.",
            settlement_id="town",
            memory=NpcMemory(tags=["hates:player"]),
        )
        bandit.max_hp = 100
        bandit.current_hp = 100
        summarizer = _mock_summarizer()
        layer = EntitiesLayer(entities=[player, guard, bandit], summarizer=summarizer)

        # Start combat via attack event (creates COMBAT_STARTED + attack log)
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK_REQUESTED,
                source_layer="entities",
                data=AttackRequestedPayload(**{"attacker_id": "player", "target_id": "bandit"}),
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        return layer, summarizer

    def _end_combat_by_idle(self, layer: EntitiesLayer) -> None:
        """End combat by having 2+ rounds without attacks."""
        # Round after setup attack: resets rounds_without_attack to 0
        layer.end_combat_round("town_square")
        # Two idle rounds → rounds_without_attack reaches 2 → combat ends
        layer.end_combat_round("town_square")
        layer.end_combat_round("town_square")

    def test_combat_ended_calls_summarizer_for_npcs(self) -> None:
        layer, summarizer = self._setup_combat()
        self._end_combat_by_idle(layer)

        # Summarizer called for guard and bandit, not for player
        assert summarizer.summarize.call_count == 2
        call_npcs = {call.args[0].tags[0] for call in summarizer.summarize.call_args_list}
        assert call_npcs == {"loyal_to:player", "hates:player"}

    def test_combat_ended_updates_npc_memory(self) -> None:
        layer, _ = self._setup_combat()
        self._end_combat_by_idle(layer)

        guard = layer.get_entity("guard")
        assert isinstance(guard, Npc)
        assert guard.memory.recent == "Fought in combat."
        assert guard.memory.inner_state == "shaken"

    def test_no_summarizer_does_nothing(self) -> None:
        """Without a summarizer, combat end doesn't crash."""
        player = PlayerCharacter(id="player", name="Hero", location_id="loc")
        npc = Npc(id="npc1", name="NPC", location_id="loc", role=NpcRole.GUARD, personality=".", settlement_id="s")
        npc.max_hp = 100
        npc.current_hp = 100
        layer = EntitiesLayer(entities=[player, npc])
        # Start combat
        layer.handle_event(
            Event(
                event_type=EventType.ENTITY_ATTACK_REQUESTED,
                source_layer="entities",
                data=AttackRequestedPayload(**{"attacker_id": "player", "target_id": "npc1"}),
            ),
            _noop_query_fn,
            _noop_emit_fn,
        )
        # End combat — no summarizer, should not raise
        layer.end_combat_round("loc")
        layer.end_combat_round("loc")

    def test_recent_overflow_triggers_second_call(self) -> None:
        layer, summarizer = self._setup_combat()
        summarizer.needs_compression.return_value = True
        self._end_combat_by_idle(layer)

        # 2 NPCs x (combat_ended + recent_overflow) = 4 calls
        assert summarizer.summarize.call_count == 4
        triggers = [call.args[2] for call in summarizer.summarize.call_args_list]
        assert triggers.count("combat_ended") == 2
        assert triggers.count("recent_overflow") == 2
