"""GM controls for creature activation and trigger runtime state."""

from __future__ import annotations

import threading
from http import HTTPStatus
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.content_loader import parse_npc
from dnd_simulator.core.events import WarDeclaredPayload
from dnd_simulator.core.models import Event, EventType, GameDateTime
from dnd_simulator.core.triggers import GmActivationOverride
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

TIME = GameDateTime(year=1490, month=6, day=1, hour=10)


def _trigger(trigger_id: str = "war_duty") -> dict[str, object]:
    return {
        "id": trigger_id,
        "on": {
            "event": "war_declared",
            "match": {"aggressor_id": "north", "target_id": "south"},
        },
        "until": {
            "event": "peace_declared",
            "match": {"nation_a_id": "north", "nation_b_id": "south"},
        },
    }


def _npc(
    npc_id: str = "prince",
    *,
    location: str = "far_keep",
    triggers: list[dict[str, object]] | None = None,
    always_active: bool = False,
    is_anchor: bool = False,
) -> Npc:
    npc = parse_npc(
        npc_id,
        {
            "name": npc_id,
            "start_location": location,
            "always_active": always_active,
            "triggers": triggers or [],
        },
    )
    npc.is_anchor = is_anchor
    return npc


def _war() -> Event:
    return Event(EventType.WAR_DECLARED, "politics", WarDeclaredPayload("north", "south"))


def _make_client(tmp_path: Path) -> tuple[TestClient, GameService, str]:
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    set_service(service)
    client = TestClient(app)
    response = client.post("/api/master/sessions", json={})
    assert response.status_code == HTTPStatus.OK
    return client, service, str(response.json()["session_id"])


def _add_controlled_npc(service: GameService, session_id: str) -> Npc:
    npc = _npc(triggers=[_trigger()])
    session = service._get_session(session_id)
    service._get_entities_layer(session).add_entity(npc)
    return npc


def test_manual_override_survives_passes_and_automatic_restores_trigger_reason() -> None:
    npc = _npc(triggers=[_trigger()])
    layer = EntitiesLayer([npc])
    world = World([layer], time=TIME)
    npc.active = False

    npc.gm_activation_override = GmActivationOverride.ACTIVE
    for _ in range(3):
        layer.update_activation(TIME)
        assert npc.active is True

    world.handle_event(_war())
    npc.gm_activation_override = GmActivationOverride.DORMANT
    layer.update_activation(TIME)
    assert npc.triggers[0].active is True
    assert npc.active is False

    npc.gm_activation_override = GmActivationOverride.AUTOMATIC
    layer.update_activation(TIME)
    assert npc.active is True


def test_manual_dormant_cannot_suppress_combat_anchor_scene_or_always_active() -> None:
    anchor = _npc("anchor", location="scene", is_anchor=True)
    scene_npc = _npc("scene_npc", location="scene")
    combatant = _npc("combatant")
    combatant.in_combat = True
    permanent = _npc("permanent", always_active=True)
    dead = _npc("dead")
    dead.current_hp = 0
    dead.gm_activation_override = GmActivationOverride.ACTIVE
    for npc in (anchor, scene_npc, combatant, permanent):
        npc.gm_activation_override = GmActivationOverride.DORMANT

    layer = EntitiesLayer([anchor, scene_npc, combatant, permanent, dead])
    layer.update_activation(TIME)

    assert anchor.active is True
    assert scene_npc.active is True
    assert combatant.active is True
    assert permanent.active is True
    assert dead.active is False


@pytest.mark.parametrize("override", list(GmActivationOverride))
def test_override_and_trigger_state_round_trip_without_yaml(override: GmActivationOverride) -> None:
    npc = _npc(triggers=[_trigger()])
    npc.gm_activation_override = override
    npc.triggers[0].active = True
    npc.triggers[0].armed = False
    state = EntitiesLayer([npc]).get_state()

    restored_layer = EntitiesLayer()
    restored_layer.load_state(state)
    restored = restored_layer.get_entity(npc.id)

    assert isinstance(restored, Npc)
    assert restored.gm_activation_override is override
    assert restored.triggers[0].armed is False
    assert restored.triggers[0].active is True


def test_master_api_controls_override_and_existing_trigger_without_losing_state(tmp_path: Path) -> None:
    client, service, session_id = _make_client(tmp_path)
    npc = _add_controlled_npc(service, session_id)
    npc.triggers[0].active = True

    response = client.put(
        f"/api/master/sessions/{session_id}/creatures/{npc.id}/activation",
        json={"override": "dormant"},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json()["gm_activation_override"] == "dormant"

    response = client.put(
        f"/api/master/sessions/{session_id}/creatures/{npc.id}/activation",
        json={"override": "automatic"},
    )
    assert response.status_code == HTTPStatus.OK
    assert npc.active is True

    response = client.put(
        f"/api/master/sessions/{session_id}/creatures/{npc.id}/triggers/war_duty",
        json={"armed": False},
    )
    assert response.status_code == HTTPStatus.OK
    assert response.json() == {"id": "war_duty", "armed": False, "active": True}
    assert npc.active is False
    definition = npc.triggers[0].definition
    World([service._get_entities_layer(service._get_session(session_id))], time=TIME).handle_event(_war())
    assert npc.triggers[0].active is True

    response = client.put(
        f"/api/master/sessions/{session_id}/creatures/{npc.id}/triggers/war_duty",
        json={"armed": True},
    )
    assert response.status_code == HTTPStatus.OK
    assert npc.triggers[0].definition is definition
    assert npc.triggers[0].active is True
    assert npc.active is True

    detail = client.get(f"/api/master/sessions/{session_id}/creatures/{npc.id}").json()
    assert detail["gm_activation_override"] == "automatic"
    assert detail["activation_triggers"] == [{"id": "war_duty", "armed": True, "active": True}]


def test_unknown_creature_and_trigger_are_4xx_without_partial_mutation(tmp_path: Path) -> None:
    client, service, session_id = _make_client(tmp_path)
    npc = _add_controlled_npc(service, session_id)

    missing_creature = client.put(
        f"/api/master/sessions/{session_id}/creatures/missing/activation",
        json={"override": "active"},
    )
    assert missing_creature.status_code == HTTPStatus.NOT_FOUND

    missing_trigger = client.put(
        f"/api/master/sessions/{session_id}/creatures/{npc.id}/triggers/missing",
        json={"armed": False},
    )
    assert missing_trigger.status_code == HTTPStatus.NOT_FOUND
    assert npc.gm_activation_override is GmActivationOverride.AUTOMATIC
    assert [(trigger.armed, trigger.active) for trigger in npc.triggers] == [(True, False)]


def test_control_mutation_waits_for_session_world_gate(tmp_path: Path) -> None:
    _, service, session_id = _make_client(tmp_path)
    npc = _add_controlled_npc(service, session_id)
    session = service._get_session(session_id)
    started = threading.Event()
    finished = threading.Event()

    def mutate() -> None:
        started.set()
        service.set_creature_activation_override(session_id, npc.id, GmActivationOverride.ACTIVE)
        finished.set()

    with session.mutate_world():
        thread = threading.Thread(target=mutate)
        thread.start()
        assert started.wait(timeout=1)
        assert finished.wait(timeout=0.05) is False
        assert npc.gm_activation_override is GmActivationOverride.AUTOMATIC

    thread.join(timeout=1)
    assert finished.is_set()
    assert npc.gm_activation_override is GmActivationOverride.ACTIVE
