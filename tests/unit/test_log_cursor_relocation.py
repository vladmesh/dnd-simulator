"""The perception log cursor follows every location change of a creature.

The cursor is an index into the log of one location. A journey re-anchored it on arrival
(PR #75), but a GM move (``PATCH .../creatures/{id}`` with ``location_id``) or any other direct
location change left it indexing the old location's log: the player then missed the first events
at the destination (old index past its log end) or read the destination's history from before
it got there (old index inside it).
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.core.character import Character, Creature, Race
from dnd_simulator.core.events import EntitySayPayload
from dnd_simulator.core.models import Event, EventType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

TAVERN = "cursor_tavern"
MARKET = "cursor_market"


def _character(entity_id: str, location_id: str) -> Character:
    return Character(id=entity_id, name=entity_id.capitalize(), location_id=location_id, race=Race.HUMAN)


def _say(layer: EntitiesLayer, speaker_id: str, text: str) -> None:
    layer._event_log.record(
        Event(event_type=EventType.ENTITY_SAY, source_layer="test", data=EntitySayPayload(speaker_id, text))
    )


def _heard(layer: EntitiesLayer, creature: Creature) -> list[str]:
    return [str(event.data["text"]) for event in layer.get_perceived_events(creature) if "text" in event.data]


def _session(tmp_path: Path) -> tuple[TestClient, GameService, str, EntitiesLayer, PlayerCharacter]:
    """A live session: the player hero in the tavern, a barkeep there and a merchant at the market."""
    service = GameService(store=JsonFileStore(tmp_path / "saves"))
    set_service(service)
    client = TestClient(app)
    response = client.post("/api/master/sessions", json={})
    assert response.status_code == HTTPStatus.OK
    session_id = str(response.json()["session_id"])
    layer = service._get_entities_layer(service._get_session(session_id))
    hero = PlayerCharacter(id="hero", name="Hero", location_id=TAVERN, race=Race.HUMAN)
    for entity in (hero, _character("barkeep", TAVERN), _character("merchant", MARKET)):
        layer.add_entity(entity)
    return client, service, session_id, layer, hero


def _patch_location(client: TestClient, session_id: str, entity_id: str, location_id: str) -> None:
    response = client.patch(
        f"/api/master/sessions/{session_id}/creatures/{entity_id}", json={"location_id": location_id}
    )
    assert response.status_code == HTTPStatus.OK, response.text


class TestGmMove:
    def test_player_reads_the_first_event_at_the_destination(self, tmp_path: Path) -> None:
        client, _, sid, layer, hero = _session(tmp_path)
        for n in range(3):
            _say(layer, "barkeep", f"tavern {n}")
        assert _heard(layer, hero) == ["tavern 0", "tavern 1", "tavern 2"]

        _patch_location(client, sid, "hero", MARKET)
        _say(layer, "merchant", "Fresh apples!")

        assert _heard(layer, hero) == ["Fresh apples!"]

    def test_player_does_not_read_the_destination_history(self, tmp_path: Path) -> None:
        client, _, sid, layer, hero = _session(tmp_path)
        _say(layer, "barkeep", "tavern")
        for n in range(3):
            _say(layer, "merchant", f"before the hero came {n}")
        assert _heard(layer, hero) == ["tavern"]

        _patch_location(client, sid, "hero", MARKET)
        _say(layer, "merchant", "Welcome!")

        assert _heard(layer, hero) == ["Welcome!"]

    def test_a_read_before_any_event_at_the_destination_reads_nothing_and_loses_nothing(self, tmp_path: Path) -> None:
        client, _, sid, layer, hero = _session(tmp_path)
        _say(layer, "merchant", "old news")
        _patch_location(client, sid, "hero", MARKET)

        assert _heard(layer, hero) == []
        _say(layer, "merchant", "Welcome!")
        assert _heard(layer, hero) == ["Welcome!"]

    def test_round_trip_skips_what_was_said_while_away(self, tmp_path: Path) -> None:
        client, _, sid, layer, hero = _session(tmp_path)
        _say(layer, "barkeep", "hello")
        assert _heard(layer, hero) == ["hello"]

        _patch_location(client, sid, "hero", MARKET)
        _say(layer, "barkeep", "said while the hero was out")
        _patch_location(client, sid, "hero", TAVERN)
        _say(layer, "barkeep", "welcome back")

        assert _heard(layer, hero) == ["welcome back"]


class TestOtherLocationChanges:
    def test_session_player_location_setter(self, tmp_path: Path) -> None:
        _, service, sid, layer, hero = _session(tmp_path)
        session = service._get_session(sid)
        assert session.get_player() is hero
        for n in range(3):
            _say(layer, "barkeep", f"tavern {n}")
        layer.get_perceived_events(hero)

        session.player_location = MARKET
        _say(layer, "merchant", "Fresh apples!")

        assert _heard(layer, hero) == ["Fresh apples!"]

    def test_round_start_at_the_destination_is_read(self, tmp_path: Path) -> None:
        client, _, sid, layer, hero = _session(tmp_path)
        for n in range(3):
            _say(layer, "barkeep", f"tavern {n}")
        layer.get_perceived_events(hero)

        _patch_location(client, sid, "hero", MARKET)
        layer.log_round_start(MARKET, 1)

        assert [event.event_type for event in layer.get_perceived_events(hero)] == [EventType.ROUND_START]

    def test_raw_peek_follows_the_move(self, tmp_path: Path) -> None:
        client, _, sid, layer, hero = _session(tmp_path)
        for n in range(3):
            _say(layer, "barkeep", f"tavern {n}")
        layer.get_perceived_events(hero)

        _patch_location(client, sid, "hero", MARKET)
        _say(layer, "merchant", "Fresh apples!")

        assert [event.event_type for event in layer.get_new_raw_events(hero)] == [EventType.ENTITY_SAY]
