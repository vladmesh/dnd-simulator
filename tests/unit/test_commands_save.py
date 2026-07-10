"""Unit tests for SaveCommands load/list/delete — real JsonFileStore disk round-trip.

``save_game`` is exercised via integration ``test_save_roundtrip.py`` and
``autosave_all_sessions`` via ``test_autosave_all.py``; this file covers the
remaining gaps (``load_game`` state restore + brain reassignment, ``list_saves``,
``delete_save``) with a genuine on-disk round-trip rather than a mock store.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.core.brain import BrainType, PlayerBrain
from dnd_simulator.core.combat import BattleMap, CombatState
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.rules.dice import roll
from dnd_simulator.rules.rule_brain import RuleBrain
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_service(tmp_path: Path) -> GameService:
    return GameService(store=JsonFileStore(tmp_path / "saves"))


class TestLoadGameRoundTrip:
    def test_save_game_writes_versioned_envelope_with_meta(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id

        svc.save_game(sid, "snap")

        data = svc._store.load("snap", world=session.world_name)
        assert data["schema_version"] == 1
        assert data["meta"] == {
            "session_id": sid,
            "world_name": "sword_vale",
            "lang": session.lang,
            "default_player_faction": session.default_player_faction,
        }
        assert "dice_rng_state" in data["world"]

    def test_save_game_and_autosave_use_same_envelope_shape(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id

        svc.save_game(sid, "manual")
        svc.autosave_session(sid)

        manual = svc._store.load("manual", world=session.world_name)
        autosave = svc._store.load(f"session_{sid}", world=session.world_name)
        assert manual.keys() == autosave.keys() == {"schema_version", "meta", "world"}
        assert manual["meta"].keys() == autosave["meta"].keys()
        assert manual["world"].keys() == autosave["world"].keys()

    def test_legacy_save_without_schema_version_is_rejected(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id
        svc._store.save("legacy", {"world": session.world.save()}, world=session.world_name)

        with pytest.raises(ValueError, match=r"несовместимый сейв|incompatible save"):
            svc.load_game(sid, "legacy")

    def test_dice_rng_state_restored_on_load(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id
        session.dice_rng.seed(77)
        roll("1d20", rng=session.dice_rng)
        svc.save_game(sid, "dice")
        expected = roll("1d20", rng=session.dice_rng).total
        roll("1d20", rng=session.dice_rng)

        svc.load_game(sid, "dice")

        assert roll("1d20", rng=session.dice_rng).total == expected

    def test_sessions_own_independent_dice_sequences(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DND_DICE_SEED", "91")
        svc = _make_service(tmp_path)
        first = svc.start_game("sword_vale")
        second = svc.start_game("sword_vale")

        first_initial = roll("1d20", rng=first.dice_rng).total
        roll("5d20", rng=first.dice_rng)
        second_initial = roll("1d20", rng=second.dice_rng).total

        assert first_initial == second_initial

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

    def test_load_stops_old_round_and_resumes_once_for_restored_player(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id
        player = svc.create_player(
            sid,
            {
                "name": "Loader",
                "race": "human",
                "class": "fighter",
                "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
                "fighting_style": "defense",
            },
        )
        layer = svc._get_entities_layer(session)
        player.in_combat = True
        player.active = True
        layer._combat._combats[player.location_id] = CombatState(
            location_id=player.location_id,
            turn_order=[player.id],
            round_number=1,
            battle_map=BattleMap(width=60, height=60),
        )
        svc.save_game(sid, "combat")
        session._last_turn_msg = {"type": "stale"}
        session.start_round(player)
        old_thread = session._round_thread
        assert old_thread is not None

        svc.load_game(sid, "combat")

        assert not old_thread.is_alive()
        assert session._round is None
        assert session._round_thread is None
        assert session._player_brain is None
        assert session.get_last_turn_msg() is None
        restored_combat = svc._get_entities_layer(session).get_combat(player.location_id)
        assert restored_combat is not None
        assert restored_combat.round_number == 1

        restored_player = session.get_player()
        assert restored_player is not None
        first_round = session.start_round(restored_player)
        first_thread = session._round_thread
        second_round = session.start_round(restored_player)
        try:
            assert first_round is second_round
            assert session._round_thread is first_thread
            assert isinstance(restored_player.brain, PlayerBrain)
        finally:
            session.stop_round()

    def test_autosave_restore_is_paused_until_player_connection(self, tmp_path: Path) -> None:
        svc = _make_service(tmp_path)
        session = svc.start_game("sword_vale")
        sid = session.session_id
        svc.create_player(
            sid,
            {
                "name": "Restored",
                "race": "human",
                "class": "fighter",
                "ability_scores": {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8},
                "fighting_style": "defense",
            },
        )
        svc.autosave_session(sid)
        svc._sessions.pop(sid)

        restored = svc.get_session(sid)

        assert restored._round is None
        assert restored._round_thread is None
        assert restored._player_brain is None


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
