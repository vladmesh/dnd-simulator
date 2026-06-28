"""Tests for WorldStateCommands mixin — god-mode world state aggregation."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from dnd_simulator.core.models import Answer, Query, QueryType
from dnd_simulator.service.game_service import GameService
from dnd_simulator.storage.store import SaveStore


def _make_service() -> GameService:
    store = MagicMock(spec=SaveStore)
    return GameService(store=store)


class TestGetWorldState:
    """GameService.get_world_state aggregates all layer data."""

    def test_returns_regions_with_weather(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        state = svc.get_world_state(sid)

        assert "regions" in state
        regions = state["regions"]
        assert isinstance(regions, list)
        assert len(regions) > 0
        # Each region has weather info merged in
        for region in regions:
            assert isinstance(region, dict)
            assert "weather" in region

    def test_returns_nations(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        state = svc.get_world_state(sid)

        assert "nations" in state
        nations = state["nations"]
        assert isinstance(nations, list)
        assert len(nations) > 0

    def test_returns_settlements(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        state = svc.get_world_state(sid)

        assert "settlements" in state
        settlements = state["settlements"]
        assert isinstance(settlements, list)
        # sword_vale has settlements
        assert len(settlements) > 0

    def test_returns_entities(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        state = svc.get_world_state(sid)

        assert "entities" in state
        entities = state["entities"]
        assert isinstance(entities, list)
        assert len(entities) > 0

    def test_returns_session_id_and_time(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        state = svc.get_world_state(sid)

        assert state["session_id"] == sid
        assert "time" in state

    def test_raises_on_unknown_session(self) -> None:
        store = MagicMock(spec=SaveStore)
        store.load.side_effect = KeyError("no such save")
        svc = GameService(store=store)

        with pytest.raises(ValueError, match=r"Session .* not found"):
            svc.get_world_state("nonexistent-session-id")

    def test_malformed_layer_answer_raises_typed_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A layer returning the wrong value type must surface a descriptive,
        typed error naming the layer/query — not a bare AssertionError (which is
        stripped under ``python -O``)."""
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        original = session.world.query_layer

        def corrupt(layer_name: str, query: Query) -> Answer:
            if layer_name == "geography" and query.question == QueryType.REGIONS:
                return Answer(value="not-a-list")
            return original(layer_name, query)

        monkeypatch.setattr(session.world, "query_layer", corrupt)

        with pytest.raises(RuntimeError) as exc:
            svc.get_world_state(sid)

        msg = str(exc.value).lower()
        assert "geography" in msg
        assert "regions" in msg
