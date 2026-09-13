"""Inner-self domain, serialization, and v1-save migration coverage."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from dnd_simulator.core.brain import BrainType
from dnd_simulator.core.character import AbilityScores, Creature
from dnd_simulator.core.inner_self import (
    THOUGHT_BUFFER_CAPACITY,
    AlignmentAccumulation,
    FreeformGoal,
    GoalStatus,
    GoalType,
    InnerSelf,
    Mood,
    Relationship,
    RelationshipType,
    TypedGoal,
)
from dnd_simulator.core.monster import MonsterTemplate
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _full_inner_self() -> InnerSelf:
    inner_self = InnerSelf(
        relations=[Relationship(f"target-{relation.value}", relation, intensity=75) for relation in RelationshipType],
        mood=Mood.ALERTED,
        goals=[
            TypedGoal(GoalType.KILL, "enemy", GoalStatus.ACTIVE),
            TypedGoal(GoalType.PROTECT, "ally", GoalStatus.ACHIEVED),
            FreeformGoal("Find a quiet place to think", GoalStatus.FAILED),
        ],
        alignment=AlignmentAccumulation(law_chaos=19, good_evil=-24),
        journal="A complete personal record.",
        current_conversation="The player asked about the road.",
    )
    for index in range(THOUGHT_BUFFER_CAPACITY + 2):
        inner_self.add_thought(f"thought-{index}")
    return inner_self


def test_full_inner_self_round_trips_losslessly() -> None:
    npc = Npc(id="npc", name="NPC", location_id="square", inner_self=_full_inner_self())
    state = EntitiesLayer(entities=[npc]).get_state()
    restored_layer = EntitiesLayer()
    restored_layer.load_state(state)
    restored = restored_layer.get_entity("npc")
    assert isinstance(restored, Npc)
    assert restored.inner_self == npc.inner_self


def test_thought_buffer_evicts_oldest_entry() -> None:
    inner_self = InnerSelf()
    for index in range(THOUGHT_BUFFER_CAPACITY + 1):
        inner_self.add_thought(str(index))
    assert inner_self.thoughts == [str(index) for index in range(1, THOUGHT_BUFFER_CAPACITY + 1)]


def test_buffered_heard_flag_round_trips_and_missing_field_defaults_false() -> None:
    from dnd_simulator.core.inner_self import BufferedPerceivedEvent
    from dnd_simulator.core.models import EventType

    inner_self = InnerSelf(
        perceived_event_buffer=[BufferedPerceivedEvent(EventType.ENTITY_SAY, "speaker", None, "Hi", 1, True)]
    )
    restored = InnerSelf.from_dict(inner_self.to_dict())
    assert restored == inner_self
    data = inner_self.to_dict()
    data["perceived_event_buffer"][0].pop("heard")
    assert InnerSelf.from_dict(data).perceived_event_buffer[0].heard is False


def test_player_and_temporary_spawn_do_not_carry_inner_self() -> None:
    player = PlayerCharacter(id="player", name="Hero", location_id="square")
    template = MonsterTemplate(
        id="wolf", name="Wolf", hp=7, ac=12, speed=40, ability_scores=AbilityScores(), attacks=(), cr=0.25
    )
    temporary = template.spawn("forest", "wolf-1")
    assert player.inner_self is None
    assert temporary.temporary is True
    assert temporary.inner_self is None


def test_service_core_attachment_excludes_player_and_temporary_creatures(tmp_path: Path) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    session = service.start_game("sword_vale")
    layer = service._get_entities_layer(session)
    player = PlayerCharacter(id="test-player", name="Hero", location_id="silverport_city_gate")
    temporary = Creature(id="temporary", name="Temporary", location_id="silverport_city_gate", temporary=True)
    persistent = Creature(id="persistent", name="Persistent", location_id="silverport_city_gate")
    for entity in (player, temporary, persistent):
        layer.add_entity(entity)

    service._assign_brains(layer)

    assert player.inner_self is None
    assert temporary.inner_self is None
    assert persistent.inner_self is not None

    for entity in (player, temporary, persistent):
        entity.inner_self = None
        service.set_creature_brain(session.session_id, entity.id, BrainType.RULE_BASED)

    assert player.inner_self is None
    assert temporary.inner_self is None
    assert persistent.inner_self is not None

    spawned = service.spawn_creature(
        session.session_id,
        {
            "id": "spawned-persistent",
            "name": "Spawned Persistent",
            "entity_type": "monster",
            "start_location": "silverport_city_gate",
            "hp": 8,
            "ac": 12,
            "speed": 30,
        },
    )
    assert isinstance(spawned, Creature)
    assert spawned.temporary is False
    assert spawned.inner_self is not None


def test_v1_save_migrates_relations_mood_and_journal_then_resaves_v2(tmp_path: Path) -> None:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    session = service.start_game("sword_vale")
    saved = service._build_save_game(session.session_id).model_dump(mode="json")
    legacy = deepcopy(saved)
    legacy["schema_version"] = 1
    entities = legacy["world"]["layers"]["entities"]["entities"]
    npc_data = next(data for data in entities.values() if data["entity_type"] == "npc")
    npc_data.pop("inner_self")
    npc_data["memory"] = {
        "tags": [
            "hates:orc",
            "hates:orc",
            "fears:dragon",
            "happy",
            "happy",
            "scared",
            "in_mourning",
            "fleeing",
            "unknown",
        ],
        "recent": "Saw danger.",
        "inner_state": "Still standing.",
        "current_conversation": "Run!",
    }
    service._store.save("legacy", legacy, world=session.world_name)

    service.load_game(session.session_id, "legacy")
    entities = service._get_entities_layer(session)._entities.values()
    restored = next(entity for entity in entities if isinstance(entity, Npc))
    assert restored.inner_self is not None
    assert restored.inner_self.mood is Mood.SCARED
    assert restored.inner_self.relation_targets(RelationshipType.HATES) == {"orc"}
    assert restored.inner_self.relation_targets(RelationshipType.FEARS) == {"dragon"}
    assert len(restored.inner_self.relations) == 2
    assert restored.inner_self.journal == "Saw danger.\n\nStill standing."
    assert restored.inner_self.current_conversation == "Run!"

    service.save_game(session.session_id, "migrated")
    assert service._store.load("migrated", world=session.world_name)["schema_version"] == 2
