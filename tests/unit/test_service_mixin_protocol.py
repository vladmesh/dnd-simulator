"""Tests for service mixin Protocol base — verifies the inheritance chain works at runtime."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.service.game_service import GameService
from dnd_simulator.storage.store import SaveStore


def _make_service() -> GameService:
    store = MagicMock(spec=SaveStore)
    return GameService(store=store)


class TestMixinProtocol:
    """Verify each mixin method is callable through GameService without AttributeError."""

    def test_save_commands_accessible(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        # save_game from SaveCommands
        name = svc.save_game(sid, "test_save")
        assert name == "test_save"

    def test_creature_commands_accessible(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        # list_creatures from CreatureCommands
        creatures = svc.list_creatures(sid)
        assert isinstance(creatures, list)

    def test_time_commands_accessible(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        # advance_time from TimeCommands
        events = svc.advance_time(sid, hours=1)
        assert isinstance(events, list)

    def test_politics_commands_accessible(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        # patch_nation from PoliticsCommands — need a nation id
        from dnd_simulator.layers.politics.layer import PoliticsLayer

        for layer in session.world.layers:
            if isinstance(layer, PoliticsLayer):
                nations = layer._nations
                if nations:
                    nation_id = next(iter(nations))
                    svc.patch_nation(sid, nation_id, {"wealth": 100.0})
                break
