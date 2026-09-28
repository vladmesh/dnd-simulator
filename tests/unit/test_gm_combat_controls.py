"""GM hot controls on creatures in an active combat: delete and kill go through the combat removal path."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState
from dnd_simulator.core.models import EventType
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

ARENA = "gm_combat_arena"


def _creature(creature_id: str, faction_id: str) -> Creature:
    return Creature(
        id=creature_id,
        name=creature_id,
        location_id=ARENA,
        max_hp=10,
        current_hp=10,
        ac=10,
        speed=30,
        faction_id=faction_id,
        active=True,
    )


def _make_fight(tmp_path: Path, *enemies: str) -> tuple[TestClient, GameService, str, EntitiesLayer, CombatState]:
    """A live session with a hero fighting ``enemies`` (one shared hostile faction) at ARENA."""
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    set_service(service)
    client = TestClient(app)
    response = client.post("/api/master/sessions", json={})
    assert response.status_code == HTTPStatus.OK
    session_id = str(response.json()["session_id"])
    layer = service._get_entities_layer(service._get_session(session_id))
    layer.add_entity(_creature("hero", "heroes"))
    for enemy_id in enemies:
        layer.add_entity(_creature(enemy_id, "raiders"))
    combat = layer._combat.start_combat(ARENA)
    assert combat is not None
    return client, service, session_id, layer, combat


def _event_types(layer: EntitiesLayer) -> list[EventType]:
    return [event.event_type for event in layer._location_log[ARENA]]


class TestGmDeleteInCombat:
    def test_delete_frees_cell_initiative_and_side(self, tmp_path: Path) -> None:
        client, _, sid, layer, combat = _make_fight(tmp_path, "raider_a", "raider_b")

        response = client.delete(f"/api/master/sessions/{sid}/creatures/raider_a")

        assert response.status_code == HTTPStatus.OK
        assert layer.get_entity("raider_a") is None
        assert layer.get_combat(ARENA) is combat
        assert "raider_a" not in combat.turn_order
        assert "raider_a" not in combat.battle_map.positions
        assert "raider_a" not in combat.battle_map.corpses
        assert "raider_a" not in combat.entity_to_side
        assert layer.get_active_combat_for("raider_a") is None

    def test_delete_of_last_enemy_ends_combat(self, tmp_path: Path) -> None:
        client, _, sid, layer, _ = _make_fight(tmp_path, "raider_a")
        hero = layer.get_entity("hero")
        assert isinstance(hero, Creature)

        response = client.delete(f"/api/master/sessions/{sid}/creatures/raider_a")

        assert response.status_code == HTTPStatus.OK
        assert layer.get_combat(ARENA) is None
        assert layer.get_active_combat_for("hero") is None
        assert hero.in_combat is False
        assert EventType.COMBAT_ENDED in _event_types(layer)

    def test_delete_outside_combat_still_removes(self, tmp_path: Path) -> None:
        client, _, sid, layer, combat = _make_fight(tmp_path, "raider_a")
        bystander = _creature("bystander", "raiders")
        bystander.location_id = "elsewhere"
        layer.add_entity(bystander)

        response = client.delete(f"/api/master/sessions/{sid}/creatures/bystander")

        assert response.status_code == HTTPStatus.OK
        assert layer.get_entity("bystander") is None
        assert layer.get_combat(ARENA) is combat


class TestGmKillInCombat:
    def test_patch_hp_zero_leaves_corpse_and_initiative(self, tmp_path: Path) -> None:
        client, _, sid, layer, combat = _make_fight(tmp_path, "raider_a", "raider_b")
        cell = combat.battle_map.get_position("raider_a")
        raider = layer.get_entity("raider_a")
        assert isinstance(raider, Creature)

        response = client.patch(f"/api/master/sessions/{sid}/creatures/raider_a", json={"current_hp": 0})

        assert response.status_code == HTTPStatus.OK
        assert raider.is_alive is False
        assert raider.in_combat is False
        assert layer.get_combat(ARENA) is combat
        assert "raider_a" not in combat.turn_order
        assert "raider_a" not in combat.battle_map.positions
        assert combat.battle_map.corpses["raider_a"] == cell
        assert layer.get_entity("raider_a") is raider  # the corpse stays lootable
        assert EventType.ENTITY_DIED in _event_types(layer)

    def test_patch_hp_zero_on_last_enemy_ends_combat(self, tmp_path: Path) -> None:
        _, service, sid, layer, _ = _make_fight(tmp_path, "raider_a")
        hero = layer.get_entity("hero")
        assert isinstance(hero, Creature)

        service.patch_creature(sid, "raider_a", {"current_hp": 0})

        assert layer.get_combat(ARENA) is None
        assert hero.in_combat is False
        types = _event_types(layer)
        assert types.index(EventType.ENTITY_DIED) < types.index(EventType.COMBAT_ENDED)

    def test_patch_hp_on_living_combatant_keeps_it_in_combat(self, tmp_path: Path) -> None:
        _, service, sid, layer, combat = _make_fight(tmp_path, "raider_a")

        service.patch_creature(sid, "raider_a", {"current_hp": 3})

        assert layer.get_combat(ARENA) is combat
        assert "raider_a" in combat.turn_order
        assert "raider_a" in combat.battle_map.positions
