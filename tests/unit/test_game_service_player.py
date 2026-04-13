"""Unit tests for GameService player methods (sprint 017 phase 5 task 4).

Covers ``level_up_player`` and ``player_status`` — adapter-level endpoints
should be thin wrappers over these.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.core.class_features import FighterFeatures, FightingStyle, PaladinFeatures
from dnd_simulator.service import GameService
from dnd_simulator.service.dto import PlayerStatusData
from dnd_simulator.storage.store import JsonFileStore

FIGHTER_SCORES = {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8}
PALADIN_SCORES = {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 10, "cha": 12}


def _make_service(tmp_path: Path) -> GameService:
    return GameService(store=JsonFileStore(tmp_path / "saves"))


def _new_session_with_fighter(service: GameService) -> str:
    sid = service.start_game(world_name="sword_vale").session_id
    service.create_player(
        sid,
        {
            "name": "Thrain",
            "race": "dwarf",
            "class": "fighter",
            "alignment": "lawful_good",
            "ability_scores": FIGHTER_SCORES,
            "fighting_style": "defense",
        },
    )
    return sid


def _new_session_with_paladin(service: GameService) -> str:
    sid = service.start_game(world_name="sword_vale").session_id
    service.create_player(
        sid,
        {
            "name": "Arthur",
            "race": "human",
            "class": "paladin",
            "alignment": "lawful_good",
            "ability_scores": PALADIN_SCORES,
        },
    )
    return sid


class TestLevelUpPlayer:
    def test_happy_path_fighter(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        sid = _new_session_with_fighter(service)
        session = service.get_session(sid)
        player = session.get_player()
        assert player is not None
        player.level_up_available = True

        returned = service.level_up_player(sid, fighting_style=None)

        assert returned is player  # same instance mutated
        assert returned.level == 2
        assert session.get_player() is player
        feat = player.class_features[0]
        assert isinstance(feat, FighterFeatures)
        assert feat.level == 2

    def test_no_player_in_session_raises(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        sid = service.start_game(world_name="sword_vale").session_id
        with pytest.raises(ValueError, match="No player"):
            service.level_up_player(sid, fighting_style=None)

    def test_no_level_up_available_raises(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        sid = _new_session_with_fighter(service)
        # default level_up_available=False after creation
        with pytest.raises(ValueError, match="No level-up available"):
            service.level_up_player(sid, fighting_style=None)

    def test_paladin_missing_style_raises(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        sid = _new_session_with_paladin(service)
        player = service.get_session(sid).get_player()
        assert player is not None
        player.level_up_available = True
        with pytest.raises(ValueError, match="Paladin level 2 requires a fighting_style"):
            service.level_up_player(sid, fighting_style=None)

    def test_paladin_with_style_succeeds(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        sid = _new_session_with_paladin(service)
        player = service.get_session(sid).get_player()
        assert player is not None
        player.level_up_available = True
        service.level_up_player(sid, fighting_style=FightingStyle.DEFENSE)
        feat = player.class_features[0]
        assert isinstance(feat, PaladinFeatures)
        assert feat.level == 2
        assert feat.fighting_style == FightingStyle.DEFENSE


class TestPlayerStatus:
    def test_fighter_l1_derived_fields(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        sid = _new_session_with_fighter(service)

        data = service.player_status(sid)

        assert isinstance(data, PlayerStatusData)
        assert data.name == "Thrain"
        assert data.race == "dwarf"
        assert data.char_class == "fighter"
        assert data.level == 1
        assert data.experience == 0
        assert data.level_up_available is False
        assert data.xp_to_next_level == 300  # 0 xp → needs 300 to hit L2
        # Fighter with chain mail + shield + Defense fighting style
        assert data.ac > 10
        assert data.ability_scores == {
            "str": 15,
            "dex": 10,
            "con": 14,
            "int": 8,
            "wis": 12,
            "cha": 8,
        }
        # Fighter L1 has second_wind
        pool_ids = [p.id for p in data.resource_pools]
        assert "second_wind" in pool_ids

    def test_no_player_in_session_raises(self, tmp_path: Path) -> None:
        service = _make_service(tmp_path)
        sid = service.start_game(world_name="sword_vale").session_id
        with pytest.raises(ValueError, match="No player"):
            service.player_status(sid)
