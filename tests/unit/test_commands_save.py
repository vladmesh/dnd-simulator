"""Unit tests for SaveCommands load/list/delete — real JsonFileStore disk round-trip.

``save_game`` is exercised via integration ``test_save_roundtrip.py`` and
``autosave_all_sessions`` via ``test_autosave_all.py``; this file covers the
remaining gaps (``load_game`` state restore + brain reassignment, ``list_saves``,
``delete_save``) with a genuine on-disk round-trip rather than a mock store.
"""

from __future__ import annotations

from pathlib import Path

from dnd_simulator.core.brain import BrainType
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.rules.rule_brain import RuleBrain
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore

# Valid 27-point buy fighter (str 15 / dex 11 / con 14 / ...).
_PLAYER_DATA = {
    "name": "XP Hero",
    "race": "human",
    "class": "fighter",
    "alignment": "true_neutral",
    "ability_scores": {"str": 15, "dex": 11, "con": 14, "int": 10, "wis": 10, "cha": 9},
}


def _make_service(tmp_path: Path) -> GameService:
    return GameService(store=JsonFileStore(tmp_path / "saves"))


class TestLoadGameRoundTrip:
    def test_state_restored_to_saved_snapshot(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id

        svc.advance_time(sid, 5)
        saved_time = session.world.time
        svc.save_game(sid, "snap")

        # Diverge from the snapshot, then load it back.
        svc.advance_time(sid, 3)
        assert session.world.time != saved_time

        svc.load_game(sid, "snap")

        assert session.world.time == saved_time

    def test_brains_reassigned_on_load(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id
        svc.save_game(sid, "snap")

        layer = svc._get_entities_layer(session)
        npcs = [e for e in layer._entities.values() if isinstance(e, Npc) and e.ai_type == BrainType.RULE_BASED]
        assert npcs, "sword_vale should contain rule_based NPCs"
        npc_id = npcs[0].id

        # Corrupt the brain so a no-op load would leave it broken.
        npcs[0].brain = None

        svc.load_game(sid, "snap")

        restored = layer._entities[npc_id]
        assert isinstance(restored, Npc)
        assert isinstance(restored.brain, RuleBrain)


class TestListAndDeleteSaves:
    def test_list_saves_returns_saved_names(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        sid = svc.start_game("sword_vale").session_id

        svc.save_game(sid, "alpha")
        svc.save_game(sid, "beta")

        saves = svc.list_saves(sid)
        assert "alpha" in saves
        assert "beta" in saves

    def test_delete_save_removes_one(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        sid = svc.start_game("sword_vale").session_id

        svc.save_game(sid, "alpha")
        svc.save_game(sid, "beta")

        svc.delete_save(sid, "alpha")

        saves = svc.list_saves(sid)
        assert "alpha" not in saves
        assert "beta" in saves


class TestPlayerXpPersistence:
    """`experience`/`level_up_available` round-trip through the modern save path.

    Closes backlog ``player-xp-not-persisted``. Covers both load branches:
    re-apply onto an existing player (same session) and fresh ``parse_player``
    reconstruction (load into a session that has no player yet).
    """

    def test_level_up_flag_survives_reload_same_session(self, tmp_path: Path) -> None:
        """Existing-entity re-apply branch: an eligible player can still level up after reload."""
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id

        player = svc.create_player(sid, _PLAYER_DATA)
        # Cross the L2 threshold (300 XP); patch_creature recomputes level_up_available.
        svc.patch_creature(sid, player.id, {"experience": 300})
        assert player.level_up_available is True

        svc.save_game(sid, "xp_snap")

        # Diverge: zero the XP in-memory, then load the snapshot back.
        svc.patch_creature(sid, player.id, {"experience": 0})
        assert player.level_up_available is False

        svc.load_game(sid, "xp_snap")

        restored = session.get_player()
        assert restored is not None
        assert restored.experience == 300
        assert restored.level_up_available is True

        # The whole point: a reloaded eligible player still levels up (no "No level-up available").
        leveled = svc.level_up_player(sid, None)
        assert leveled.level == 2
        assert leveled.level_up_available is False

    def test_mid_level_xp_round_trips_into_fresh_session(self, tmp_path: Path) -> None:
        """Fresh parse_player branch: a below-threshold XP value survives load exactly."""
        svc = _make_service(tmp_path)
        src = svc.start_game("sword_vale")
        player = svc.create_player(src.session_id, _PLAYER_DATA)
        svc.patch_creature(src.session_id, player.id, {"experience": 150})
        assert player.level_up_available is False
        svc.save_game(src.session_id, "xp_mid")

        # Load into a brand-new session of the same world (no player present yet).
        dst = svc.start_game("sword_vale")
        assert dst.get_player() is None
        svc.load_game(dst.session_id, "xp_mid")

        loaded = dst.get_player()
        assert isinstance(loaded, PlayerCharacter)
        assert loaded.experience == 150
        assert loaded.level_up_available is False

    def test_autosave_preserves_xp_for_dev_evict_path(self, tmp_path: Path) -> None:
        """Regression for the dev StrictMode evict->restore: autosave then load into a fresh session."""
        svc = _make_service(tmp_path)
        src = svc.start_game("sword_vale")
        player = svc.create_player(src.session_id, _PLAYER_DATA)
        svc.patch_creature(src.session_id, player.id, {"experience": 450})
        assert player.level_up_available is True

        svc.autosave_session(src.session_id)

        dst = svc.start_game("sword_vale")
        svc.load_game(dst.session_id, f"session_{src.session_id}")

        loaded = dst.get_player()
        assert isinstance(loaded, PlayerCharacter)
        assert loaded.experience == 450
        assert loaded.level_up_available is True
