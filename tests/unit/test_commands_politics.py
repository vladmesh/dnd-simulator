"""Tests for PoliticsCommands mixin — patch_nation and patch_settlement."""

from __future__ import annotations

from unittest.mock import MagicMock

from dnd_simulator.service.game_service import GameService
from dnd_simulator.storage.store import SaveStore


def _make_service() -> GameService:
    store = MagicMock(spec=SaveStore)
    return GameService(store=store)


class TestPatchNation:
    def test_patch_wealth(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        from dnd_simulator.layers.politics.layer import PoliticsLayer

        politics: PoliticsLayer | None = None
        for layer in session.world.layers:
            if isinstance(layer, PoliticsLayer):
                politics = layer
                break
        assert politics is not None, "sword_vale must have a PoliticsLayer"

        nation_id = next(iter(politics._nations))
        original_military = politics._nations[nation_id].military

        svc.patch_nation(sid, nation_id, {"wealth": 999.0})

        nation = politics.get_nation(nation_id)
        assert nation.wealth == 999.0
        # Other fields unchanged
        assert nation.military == original_military

    def test_patch_multiple_fields(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        from dnd_simulator.layers.politics.layer import PoliticsLayer

        for layer in session.world.layers:
            if isinstance(layer, PoliticsLayer):
                nation_id = next(iter(layer._nations))
                break

        svc.patch_nation(sid, nation_id, {"wealth": 50.0, "military": 75.0, "stability": 90.0})

        nation = layer.get_nation(nation_id)
        assert nation.wealth == 50.0
        assert nation.military == 75.0
        assert nation.stability == 90.0


class TestPatchSettlement:
    def test_patch_population(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        from dnd_simulator.layers.settlements.layer import SettlementsLayer

        settlements_layer: SettlementsLayer | None = None
        for layer in session.world.layers:
            if isinstance(layer, SettlementsLayer):
                settlements_layer = layer
                break
        assert settlements_layer is not None, "sword_vale must have a SettlementsLayer"

        settlement_id = next(iter(settlements_layer._settlements))
        original_prosperity = settlements_layer._settlements[settlement_id].prosperity

        svc.patch_settlement(sid, settlement_id, {"population": 500})

        settlement = settlements_layer.get_settlement(settlement_id)
        assert settlement.population == 500
        assert settlement.prosperity == original_prosperity

    def test_patch_prosperity_and_defenses(self) -> None:
        svc = _make_service()
        session = svc.start_game("sword_vale")
        sid = session.session_id

        from dnd_simulator.layers.settlements.layer import SettlementsLayer

        for layer in session.world.layers:
            if isinstance(layer, SettlementsLayer):
                settlement_id = next(iter(layer._settlements))
                break

        svc.patch_settlement(sid, settlement_id, {"prosperity": 80.0, "defenses": 60.0})

        settlement = layer.get_settlement(settlement_id)
        assert settlement.prosperity == 80.0
        assert settlement.defenses == 60.0
