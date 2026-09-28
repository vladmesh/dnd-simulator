"""GM hot controls on creatures (issue ae4bde95c6d2043858d0).

Delete and kill in an active combat go through the combat removal path; a spawn into a running
fight joins it on its ``combat_position`` cell; ``gold`` patches apply to any creature; a container
is not a creature for ``GET /creatures/{id}``.
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.core.character import Creature
from dnd_simulator.core.combat import CombatState, Position
from dnd_simulator.core.container import Container
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


def _brute(**extra: object) -> dict[str, object]:
    return {
        "id": "brute",
        "name": "Brute",
        "entity_type": "monster",
        "start_location": ARENA,
        "hp": 20,
        "ac": 12,
        "speed": 30,
        **extra,
    }


def _free_cell(combat: CombatState) -> Position:
    taken = set(combat.battle_map.positions.values())
    return next(Position(x, y) for x in range(0, 60, 5) for y in range(0, 60, 5) if Position(x, y) not in taken)


class TestGmSpawnIntoCombat:
    def test_spawn_with_combat_position_joins_fight_on_that_cell(self, tmp_path: Path) -> None:
        client, _, sid, layer, combat = _make_fight(tmp_path, "raider_a")
        cell = _free_cell(combat)

        response = client.post(f"/api/master/sessions/{sid}/creatures", json=_brute(combat_position=[cell.x, cell.y]))

        assert response.status_code == HTTPStatus.OK
        brute = layer.get_entity("brute")
        assert isinstance(brute, Creature)
        assert brute.combat_position == (cell.x, cell.y)
        assert combat.battle_map.get_position("brute") == cell
        assert combat.turn_order[-1] == "brute"  # joins at the end of the initiative order
        assert layer.get_active_combat_for("brute") is combat
        assert brute.in_combat is True
        assert brute.turn_budget is not None and brute.turn_budget.reaction == 1

    def test_spawn_without_position_joins_fight_on_a_free_cell(self, tmp_path: Path) -> None:
        client, _, sid, layer, combat = _make_fight(tmp_path, "raider_a")
        taken = set(combat.battle_map.positions.values())

        response = client.post(f"/api/master/sessions/{sid}/creatures", json=_brute())

        assert response.status_code == HTTPStatus.OK
        assert layer.get_active_combat_for("brute") is combat
        assert combat.battle_map.get_position("brute") not in taken

    def test_spawn_joins_own_side_when_sides_are_built(self, tmp_path: Path) -> None:
        client, _, sid, _, combat = _make_fight(tmp_path, "raider_a")
        combat.sides = {0: {"hero"}, 1: {"raider_a"}}
        combat.entity_to_side = {"hero": 0, "raider_a": 1}

        response = client.post(f"/api/master/sessions/{sid}/creatures", json=_brute())

        assert response.status_code == HTTPStatus.OK
        assert combat.entity_to_side["brute"] == 2  # factionless: a side of its own
        assert combat.sides[2] == {"brute"}

    def test_spawn_on_occupied_cell_is_rejected_and_spawns_nothing(self, tmp_path: Path) -> None:
        client, _, sid, layer, combat = _make_fight(tmp_path, "raider_a")
        cell = combat.battle_map.get_position("raider_a")
        assert cell is not None
        order = list(combat.turn_order)

        response = client.post(f"/api/master/sessions/{sid}/creatures", json=_brute(combat_position=[cell.x, cell.y]))

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "occupied" in response.json()["detail"]
        assert layer.get_entity("brute") is None
        assert combat.turn_order == order
        assert "brute" not in combat.battle_map.positions

    def test_spawn_off_the_map_is_rejected_and_spawns_nothing(self, tmp_path: Path) -> None:
        client, _, sid, layer, combat = _make_fight(tmp_path, "raider_a")

        response = client.post(f"/api/master/sessions/{sid}/creatures", json=_brute(combat_position=[100, 0]))

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert "outside" in response.json()["detail"]
        assert layer.get_entity("brute") is None
        assert "brute" not in combat.turn_order

    def test_spawn_with_cell_index_instead_of_feet_is_rejected(self, tmp_path: Path) -> None:
        client, _, sid, layer, _ = _make_fight(tmp_path, "raider_a")

        response = client.post(f"/api/master/sessions/{sid}/creatures", json=_brute(combat_position=[3, 4]))

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert layer.get_entity("brute") is None

    def test_spawn_with_existing_id_is_rejected(self, tmp_path: Path) -> None:
        client, _, sid, layer, combat = _make_fight(tmp_path, "raider_a")
        raider = layer.get_entity("raider_a")
        order = list(combat.turn_order)

        response = client.post(f"/api/master/sessions/{sid}/creatures", json={**_brute(), "id": "raider_a"})

        assert response.status_code == HTTPStatus.BAD_REQUEST
        assert layer.get_entity("raider_a") is raider
        assert combat.turn_order == order

    def test_spawn_outside_combat_keeps_position_for_the_next_fight(self, tmp_path: Path) -> None:
        client, _, sid, layer, combat = _make_fight(tmp_path, "raider_a")
        spawn = _brute(combat_position=[10, 10])
        spawn["start_location"] = "elsewhere"

        response = client.post(f"/api/master/sessions/{sid}/creatures", json=spawn)

        assert response.status_code == HTTPStatus.OK
        brute = layer.get_entity("brute")
        assert isinstance(brute, Creature)
        assert brute.combat_position == (10, 10)
        assert layer.get_active_combat_for("brute") is None
        assert "brute" not in combat.battle_map.positions


class TestGmPatchGold:
    def test_patch_gold_on_monster_applies(self, tmp_path: Path) -> None:
        client, _, sid, layer, _ = _make_fight(tmp_path, "raider_a")

        response = client.patch(f"/api/master/sessions/{sid}/creatures/raider_a", json={"gold": 25})

        assert response.status_code == HTTPStatus.OK
        raider = layer.get_entity("raider_a")
        assert isinstance(raider, Creature)
        assert raider.gold == 25
        assert client.get(f"/api/master/sessions/{sid}/creatures/raider_a").json()["gold"] == 25


class TestGmGetContainer:
    def test_get_container_is_not_found(self, tmp_path: Path) -> None:
        client, _, sid, layer, _ = _make_fight(tmp_path, "raider_a")
        layer.add_entity(Container(id="chest", name="Chest", location_id=ARENA, gold=5))

        response = client.get(f"/api/master/sessions/{sid}/creatures/chest")

        assert response.status_code == HTTPStatus.NOT_FOUND
        assert "chest" in response.json()["detail"]

    def test_get_unknown_id_is_not_found(self, tmp_path: Path) -> None:
        client, _, sid, _, _ = _make_fight(tmp_path, "raider_a")

        assert client.get(f"/api/master/sessions/{sid}/creatures/nobody").status_code == HTTPStatus.NOT_FOUND
