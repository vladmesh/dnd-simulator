"""Tests for the character creation API — Phase 2: derived stats + starting equipment.

The server computes HP, AC, gold, and equipment from class + ability scores.
The client no longer sends these fields directly.
"""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_client(tmp_path: Path) -> TestClient:
    store = JsonFileStore(tmp_path / "saves")
    service = GameService(store=store)
    set_service(service)
    return TestClient(app)


def _create_session(client: TestClient) -> str:
    resp = client.post("/api/master/sessions", json={"world_name": "sword_vale"})
    assert resp.status_code == HTTPStatus.OK
    return resp.json()["session_id"]


# -- Point buy presets --
# Standard array via point buy: {15, 14, 13, 12, 10, 8} = 9+7+5+4+2+0 = 27 pts
VALID_SCORES = {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8}
# Fighter-optimized: high STR + CON
FIGHTER_SCORES = {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8}
# Rogue-optimized: high DEX + CHA
ROGUE_SCORES = {"str": 8, "dex": 15, "con": 12, "int": 13, "wis": 10, "cha": 14}


class TestFighterCreation:
    """Fighter with point buy → correct HP, AC, equipment, gold."""

    def test_fighter_hp_from_class_and_con(self, tmp_path: Path) -> None:
        """Fighter L1 with CON 14 (+2 mod) → HP = d10 max (10) + 2 = 12."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Thrain",
                "race": "dwarf",
                "char_class": "fighter",
                "alignment": "lawful_good",
                "ability_scores": FIGHTER_SCORES,
                "fighting_style": "defense",
            },
        )
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["max_hp"] == 12
        assert data["hp"] == 12  # current_hp == max_hp at creation

    def test_fighter_gold_is_100(self, tmp_path: Path) -> None:
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Thrain",
                "race": "dwarf",
                "char_class": "fighter",
                "ability_scores": FIGHTER_SCORES,
                "fighting_style": "defense",
            },
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["gold"] == 100

    def test_fighter_ac_chain_mail_shield_defense(self, tmp_path: Path) -> None:
        """Fighter with Defense style: chain mail (16) + shield (+2) + Defense (+1) = 19."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Thrain",
                "race": "dwarf",
                "char_class": "fighter",
                "ability_scores": FIGHTER_SCORES,
                "fighting_style": "defense",
            },
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["ac"] == 19

    def test_fighter_ac_without_defense_style(self, tmp_path: Path) -> None:
        """Fighter with Dueling style: chain mail (16) + shield (+2) = 18 (no Defense bonus)."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Thrain",
                "race": "dwarf",
                "char_class": "fighter",
                "ability_scores": FIGHTER_SCORES,
                "fighting_style": "dueling",
            },
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["ac"] == 18

    def test_fighter_ability_scores_stored(self, tmp_path: Path) -> None:
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Thrain",
                "race": "dwarf",
                "char_class": "fighter",
                "ability_scores": FIGHTER_SCORES,
            },
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["ability_scores"] == FIGHTER_SCORES


class TestRogueCreation:
    """Rogue with point buy → correct HP, AC, equipment, gold."""

    def test_rogue_hp_from_class_and_con(self, tmp_path: Path) -> None:
        """Rogue L1 with CON 12 (+1 mod) → HP = d8 max (8) + 1 = 9."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Shadow",
                "race": "halfling",
                "char_class": "rogue",
                "ability_scores": ROGUE_SCORES,
            },
        )
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert data["max_hp"] == 9
        assert data["hp"] == 9

    def test_rogue_ac_leather_plus_dex(self, tmp_path: Path) -> None:
        """Rogue with DEX 15 (+2): leather armor (11 + DEX mod) = 13."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Shadow",
                "race": "halfling",
                "char_class": "rogue",
                "ability_scores": ROGUE_SCORES,
            },
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["ac"] == 13

    def test_rogue_gold_is_100(self, tmp_path: Path) -> None:
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Shadow",
                "race": "halfling",
                "char_class": "rogue",
                "ability_scores": ROGUE_SCORES,
            },
        )
        assert resp.status_code == HTTPStatus.OK
        assert resp.json()["gold"] == 100


class TestValidation:
    """Point buy, class, and fighting style validation at the API boundary."""

    def test_point_buy_over_budget_rejected(self, tmp_path: Path) -> None:
        """All 15s = 9*6 = 54 pts, way over 27."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Cheater",
                "char_class": "fighter",
                "ability_scores": {"str": 15, "dex": 15, "con": 15, "int": 15, "wis": 15, "cha": 15},
            },
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_score_out_of_range_rejected(self, tmp_path: Path) -> None:
        """Score 16 is above point buy max of 15."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Cheater",
                "char_class": "fighter",
                "ability_scores": {"str": 16, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 8},
            },
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_invalid_class_rejected(self, tmp_path: Path) -> None:
        """Only fighter and rogue are supported."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Gandalf",
                "char_class": "wizard",
                "ability_scores": VALID_SCORES,
            },
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_rogue_with_fighting_style_rejected(self, tmp_path: Path) -> None:
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Shadow",
                "char_class": "rogue",
                "ability_scores": ROGUE_SCORES,
                "fighting_style": "defense",
            },
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_fighter_without_fighting_style_ok(self, tmp_path: Path) -> None:
        """Fighting style is optional — fighter can skip it."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Thrain",
                "char_class": "fighter",
                "ability_scores": FIGHTER_SCORES,
            },
        )
        assert resp.status_code == HTTPStatus.OK

    def test_fighter_invalid_fighting_style_rejected(self, tmp_path: Path) -> None:
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Thrain",
                "char_class": "fighter",
                "ability_scores": FIGHTER_SCORES,
                "fighting_style": "not_a_style",
            },
        )
        assert resp.status_code == HTTPStatus.BAD_REQUEST

    def test_missing_ability_scores_rejected(self, tmp_path: Path) -> None:
        """ability_scores is required."""
        client = _make_client(tmp_path)
        sid = _create_session(client)
        resp = client.post(
            f"/api/player/sessions/{sid}/character",
            json={
                "name": "Lazy",
                "char_class": "fighter",
            },
        )
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
