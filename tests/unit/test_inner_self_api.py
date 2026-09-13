"""GM HTTP API contracts for reading and replacing NPC inner-self cores."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.core.character import Alignment, Creature
from dnd_simulator.core.inner_self import (
    AlignmentAccumulation,
    BufferedPerceivedEvent,
    FreeformGoal,
    GoalStatus,
    GoalType,
    InnerSelf,
    Mood,
    Relationship,
    RelationshipType,
    TypedGoal,
)
from dnd_simulator.core.models import EventType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_client(tmp_path: Path) -> tuple[TestClient, GameService, str, Npc]:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    set_service(service)
    client = TestClient(app)
    response = client.post("/api/master/sessions", json={})
    assert response.status_code == HTTPStatus.OK
    session_id = str(response.json()["session_id"])
    npc = Npc(
        id="inner_npc",
        name="Inner NPC",
        location_id="silverport_city",
        alignment=Alignment.CHAOTIC_GOOD,
        inner_self=InnerSelf(
            relations=[Relationship("friend", RelationshipType.TRUSTS, 70)],
            mood=Mood.HAPPY,
            goals=[
                TypedGoal(GoalType.PROTECT, "friend", GoalStatus.ACTIVE),
                FreeformGoal("Keep the forge warm", GoalStatus.ACHIEVED),
            ],
            alignment=AlignmentAccumulation(law_chaos=2, good_evil=-1),
            journal="A quiet day.",
            thoughts=["The iron is late."],
            current_conversation="Discussing ore delivery.",
            perceived_event_buffer=[
                BufferedPerceivedEvent(
                    EventType.ENTITY_SAY,
                    actor_id="friend",
                    target_id="inner_npc",
                    description="The caravan has arrived.",
                    at_seconds=42,
                    heard=True,
                )
            ],
        ),
    )
    session = service._get_session(session_id)
    service._get_entities_layer(session).add_entity(npc)
    return client, service, session_id, npc


def _core_payload() -> dict[str, object]:
    return {
        "relations": [{"target_id": "rival", "type": "hates", "intensity": 80}],
        "mood": "angry",
        "goals": [
            {"kind": "typed", "type": "protect", "target_id": "friend", "status": "active"},
            {"kind": "freeform", "text": "Find a safer forge", "status": "active"},
        ],
    }


def _inner_self_url(session_id: str, npc_id: str = "inner_npc") -> str:
    return f"/api/master/sessions/{session_id}/creatures/{npc_id}/inner-self"


def test_get_inner_self_returns_complete_typed_view(tmp_path: Path) -> None:
    client, _, session_id, _ = _make_client(tmp_path)

    response = client.get(_inner_self_url(session_id))

    assert response.status_code == HTTPStatus.OK
    assert response.json() == {
        "relations": [{"target_id": "friend", "type": "trusts", "intensity": 70}],
        "mood": "happy",
        "goals": [
            {"kind": "typed", "type": "protect", "target_id": "friend", "status": "active"},
            {"kind": "freeform", "text": "Keep the forge warm", "status": "achieved"},
        ],
        "character_alignment": "chaotic_good",
        "alignment_accumulation": {"law_chaos": 2, "good_evil": -1},
        "journal": "A quiet day.",
        "thoughts": ["The iron is late."],
        "current_conversation": "Discussing ore delivery.",
        "perceived_event_buffer": [
            {
                "event_type": "entity_say",
                "actor_id": "friend",
                "target_id": "inner_npc",
                "description": "The caravan has arrived.",
                "at_seconds": 42,
                "heard": True,
            }
        ],
    }


def test_get_inner_self_rejects_non_bearers_and_unknown_creatures(tmp_path: Path) -> None:
    client, service, session_id, _ = _make_client(tmp_path)
    session = service._get_session(session_id)
    layer = service._get_entities_layer(session)
    layer.add_entity(PlayerCharacter(id="player", name="Player", location_id="silverport_city"))
    layer.add_entity(Creature(id="temporary", name="Temporary", location_id="silverport_city", temporary=True))

    for entity_id in ("player", "temporary", "missing"):
        response = client.get(_inner_self_url(session_id, entity_id))
        assert response.status_code == HTTPStatus.NOT_FOUND

        response = client.put(f"{_inner_self_url(session_id, entity_id)}/core", json=_core_payload())
        assert response.status_code == HTTPStatus.NOT_FOUND


def test_replace_inner_self_core_preserves_free_layer_and_read_reflects_change(tmp_path: Path) -> None:
    client, _, session_id, _ = _make_client(tmp_path)

    response = client.put(f"{_inner_self_url(session_id)}/core", json=_core_payload())

    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["relations"] == [{"target_id": "rival", "type": "hates", "intensity": 80}]
    assert data["mood"] == "angry"
    assert data["goals"] == _core_payload()["goals"]
    assert data["journal"] == "A quiet day."
    assert data["thoughts"] == ["The iron is late."]
    assert data["perceived_event_buffer"][0]["heard"] is True
    assert data["alignment_accumulation"] == {"law_chaos": 2, "good_evil": -1}

    reread = client.get(_inner_self_url(session_id))
    assert reread.status_code == HTTPStatus.OK
    assert reread.json() == data


@pytest.mark.parametrize(
    "invalid",
    [
        {"journal": "forbidden"},
        {"thoughts": ["forbidden"]},
        {"mood": "furious"},
        {"relations": [{"target_id": "rival", "type": "enemy", "intensity": 80}]},
        {"relations": [{"target_id": "rival", "type": "hates", "intensity": 0}]},
        {"relations": [{"target_id": "rival", "type": "hates", "intensity": 101}]},
        {
            "relations": [
                {"target_id": "rival", "type": "hates", "intensity": 80},
                {"target_id": "rival", "type": "hates", "intensity": 20},
            ]
        },
        {"relations": [{"target_id": "", "type": "hates", "intensity": 80}]},
        {"relations": [{"target_id": "inner_npc", "type": "hates", "intensity": 80}]},
        {
            "goals": [
                {"kind": "freeform", "text": "", "status": "active"},
            ]
        },
    ],
)
def test_replace_inner_self_core_rejects_invalid_payloads_atomically(
    tmp_path: Path, invalid: dict[str, object]
) -> None:
    client, _, session_id, _ = _make_client(tmp_path)
    original = client.get(_inner_self_url(session_id)).json()
    payload = _core_payload()
    payload.update(invalid)

    response = client.put(f"{_inner_self_url(session_id)}/core", json=payload)

    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
    assert client.get(_inner_self_url(session_id)).json() == original


def test_inner_self_openapi_declares_routes_models_and_enums(tmp_path: Path) -> None:
    client, _, _, _ = _make_client(tmp_path)

    schema = client.get("/openapi.json").json()
    paths = schema["paths"]
    assert "/api/master/sessions/{session_id}/creatures/{entity_id}/inner-self" in paths
    assert "/api/master/sessions/{session_id}/creatures/{entity_id}/inner-self/core" in paths
    components = schema["components"]["schemas"]
    assert "ReplaceInnerSelfCoreRequest" in components
    assert "InnerSelfResponse" in components
    assert set(components["Mood"]["enum"]) == {member.value for member in Mood}
    assert set(components["RelationshipType"]["enum"]) == {member.value for member in RelationshipType}
    assert set(components["GoalType"]["enum"]) == {member.value for member in GoalType}


def test_inner_self_core_edit_survives_save_and_load(tmp_path: Path) -> None:
    client, _, session_id, _ = _make_client(tmp_path)
    core_url = f"{_inner_self_url(session_id)}/core"
    assert client.put(core_url, json=_core_payload()).status_code == HTTPStatus.OK
    save = client.post(f"/api/master/sessions/{session_id}/save", params={"name": "edited_core"})
    assert save.status_code == HTTPStatus.OK

    changed_again = _core_payload()
    changed_again["mood"] = "neutral"
    assert client.put(core_url, json=changed_again).status_code == HTTPStatus.OK
    assert client.post(f"/api/master/sessions/{session_id}/saves/edited_core/load").status_code == HTTPStatus.OK

    restored = client.get(_inner_self_url(session_id)).json()
    assert restored["mood"] == "angry"
    assert restored["relations"] == [{"target_id": "rival", "type": "hates", "intensity": 80}]
