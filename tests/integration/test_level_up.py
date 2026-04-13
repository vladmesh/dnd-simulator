"""Integration tests for POST /api/player/sessions/{sid}/level-up.

Sprint 017, Phase 2, Task 4 — full level-up flow covering Fighter, Rogue,
and Paladin L1→L2 transitions via the live REST stack.
"""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

import requests

WORLD = "combat_test"
LOCATION = "combat_floor"


def _scores(con: int = 10) -> dict[str, int]:
    return {"str": 15, "dex": 11, "con": con, "int": 10, "wis": 10, "cha": 9}


def _create(
    api_url: str,
    player_api_url: str,
    *,
    char_class: str = "fighter",
    con: int = 10,
) -> tuple[str, str]:
    resp = requests.post(f"{api_url}/sessions", json={"world_name": WORLD, "lang": "en"}, timeout=10)
    resp.raise_for_status()
    sid = resp.json()["session_id"]
    body: dict[str, Any] = {
        "name": "Level Hero",
        "race": "human",
        "char_class": char_class,
        "alignment": "true_neutral",
        "start_location": LOCATION,
        "ability_scores": _scores(con=con),
    }
    if char_class == "fighter":
        body["fighting_style"] = "defense"
    resp = requests.post(f"{player_api_url}/sessions/{sid}/character", json=body, timeout=10)
    resp.raise_for_status()
    return sid, resp.json()["player_id"]


def _bank_xp(api_url: str, sid: str, pid: str, xp: int = 300) -> None:
    """Directly grant the player ``xp`` via master PATCH (test-only shortcut)."""
    requests.patch(
        f"{api_url}/sessions/{sid}/creatures/{pid}",
        json={"experience": xp},
        timeout=10,
    ).raise_for_status()


def _status(player_api_url: str, sid: str) -> dict[str, Any]:
    resp = requests.get(f"{player_api_url}/sessions/{sid}/status", timeout=10)
    assert resp.status_code == HTTPStatus.OK
    return resp.json()


def _level_up(player_api_url: str, sid: str, fighting_style: str | None) -> requests.Response:
    body: dict[str, Any] = {"fighting_style": fighting_style}
    return requests.post(f"{player_api_url}/sessions/{sid}/level-up", json=body, timeout=10)


class TestFighterLevelUp:
    def test_fighter_l1_to_l2(self, api_url: str, player_api_url: str) -> None:
        sid, pid = _create(api_url, player_api_url, char_class="fighter", con=10)
        try:
            _bank_xp(api_url, sid, pid)
            status_before = _status(player_api_url, sid)
            assert status_before["level_up_available"] is True
            assert status_before["level"] == 1
            assert status_before["max_hp"] == 10  # Fighter L1, CON 10 → 10+0

            resp = _level_up(player_api_url, sid, fighting_style=None)
            assert resp.status_code == HTTPStatus.OK, resp.text
            data = resp.json()
            assert data["level"] == 2
            assert data["level_up_available"] is False
            assert data["max_hp"] == 16  # L1 10 + (die_avg 6 + CON 0)
            assert data["xp_to_next_level"] == 900 - 300

            pool_ids = {p["id"] for p in data["resource_pools"]}
            assert "action_surge" in pool_ids
            assert "second_wind" in pool_ids
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


class TestPaladinLevelUp:
    def test_paladin_requires_fighting_style(self, api_url: str, player_api_url: str) -> None:
        sid, pid = _create(api_url, player_api_url, char_class="paladin", con=10)
        try:
            _bank_xp(api_url, sid, pid)

            resp = _level_up(player_api_url, sid, fighting_style=None)
            assert resp.status_code == HTTPStatus.BAD_REQUEST
            assert "fighting_style" in resp.text.lower() or "fighting style" in resp.text.lower()

            resp = _level_up(player_api_url, sid, fighting_style="dueling")
            assert resp.status_code == HTTPStatus.OK, resp.text
            data = resp.json()
            assert data["level"] == 2
            assert data["level_up_available"] is False

            pool_ids = {p["id"] for p in data["resource_pools"]}
            assert "spell_slot_1" in pool_ids
            assert "lay_on_hands" in pool_ids
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


class TestRogueLevelUp:
    def test_rogue_l1_to_l2_hp_only(self, api_url: str, player_api_url: str) -> None:
        sid, pid = _create(api_url, player_api_url, char_class="rogue", con=10)
        try:
            _bank_xp(api_url, sid, pid)
            status_before = _status(player_api_url, sid)
            assert status_before["max_hp"] == 8  # d8 + CON 0

            resp = _level_up(player_api_url, sid, fighting_style=None)
            assert resp.status_code == HTTPStatus.OK, resp.text
            data = resp.json()
            assert data["level"] == 2
            assert data["max_hp"] == 13  # 8 + (d8 die_avg 5 + CON 0)
            assert data["resource_pools"] == status_before["resource_pools"]  # no new pools
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


class TestLevelUpFlag:
    def test_second_call_rejects(self, api_url: str, player_api_url: str) -> None:
        sid, pid = _create(api_url, player_api_url, char_class="fighter", con=10)
        try:
            _bank_xp(api_url, sid, pid)
            first = _level_up(player_api_url, sid, fighting_style=None)
            assert first.status_code == HTTPStatus.OK, first.text
            second = _level_up(player_api_url, sid, fighting_style=None)
            assert second.status_code == HTTPStatus.BAD_REQUEST
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)


class TestCurrentHpHealsByDelta:
    def test_current_hp_gains_delta(self, api_url: str, player_api_url: str) -> None:
        sid, pid = _create(api_url, player_api_url, char_class="fighter", con=10)
        try:
            _bank_xp(api_url, sid, pid)
            # Set current_hp to 5 before level-up
            requests.patch(
                f"{api_url}/sessions/{sid}/creatures/{pid}",
                json={"current_hp": 5},
                timeout=10,
            ).raise_for_status()

            resp = _level_up(player_api_url, sid, fighting_style=None)
            assert resp.status_code == HTTPStatus.OK, resp.text
            data = resp.json()
            # max_hp: 10 → 16 (delta 6). current_hp: 5 → 11.
            assert data["max_hp"] == 16
            assert data["hp"] == 11
        finally:
            requests.delete(f"{api_url}/sessions/{sid}", timeout=5)
