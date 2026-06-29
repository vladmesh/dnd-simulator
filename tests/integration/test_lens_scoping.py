"""Integration tests for the lens-scoping primitives (Sprint 020 phase 2 task 1).

Exercises the two additive, unenforced scoping helpers over real HTTP:
- ``GET /api/master/worlds?creator=`` filters worlds by author (worldbuilder lens).
- ``GET /api/master/sessions`` entries surface ``created_by`` + ``time`` (DM / admin lens).

Projection only — no 403s, no access checks. A creator filter is a query helper.
"""

from __future__ import annotations

import uuid
from http import HTTPStatus

import requests

# Base/system worlds shipped with test content — never owned by a personal creator.
BASE_WORLD_IDS = {"arena", "village", "sneak_test"}


def _uid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


class TestWorldsCreatorFilter:
    def test_creator_filter_scopes_to_author(self, api_url: str) -> None:
        creator = _uid("lens_alice")
        world_id = _uid("lens_world")
        resp = requests.post(
            f"{api_url}/worlds",
            json={"id": world_id, "name": "Lens World", "description": "scoped"},
            headers={"X-User-Id": creator, "X-Role": "worldbuilder"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.CREATED
        try:
            # Filtered: only the author's world, no base/system worlds.
            scoped = requests.get(f"{api_url}/worlds", params={"creator": creator}, timeout=5)
            assert scoped.status_code == HTTPStatus.OK
            scoped_ids = {w["id"] for w in scoped.json()}
            assert scoped_ids == {world_id}
            assert not (scoped_ids & BASE_WORLD_IDS)

            # Unfiltered: the new world plus the base worlds — behavior unchanged.
            full = requests.get(f"{api_url}/worlds", timeout=5)
            assert full.status_code == HTTPStatus.OK
            full_ids = {w["id"] for w in full.json()}
            assert world_id in full_ids
            assert full_ids >= BASE_WORLD_IDS
        finally:
            requests.delete(f"{api_url}/worlds/{world_id}", timeout=5)


class TestSessionListingAttribution:
    def test_listing_surfaces_created_by_and_time(self, api_url: str) -> None:
        creator = _uid("lens_dm")
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": "arena", "lang": "en"},
            headers={"X-User-Id": creator, "X-Role": "dm"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]
        try:
            listing = requests.get(f"{api_url}/sessions", timeout=5)
            assert listing.status_code == HTTPStatus.OK
            entry = next(s for s in listing.json() if s["session_id"] == session_id)
            assert entry["created_by"] == creator
            assert entry["time"]  # non-empty in-game clock string
        finally:
            requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)

    def test_headerless_session_still_listed(self, api_url: str) -> None:
        # No identity header → default user "local"; entry must still appear with attribution.
        resp = requests.post(
            f"{api_url}/sessions",
            json={"world_name": "arena", "lang": "en"},
            timeout=10,
        )
        assert resp.status_code == HTTPStatus.OK
        session_id = resp.json()["session_id"]
        try:
            listing = requests.get(f"{api_url}/sessions", timeout=5)
            assert listing.status_code == HTTPStatus.OK
            entry = next(s for s in listing.json() if s["session_id"] == session_id)
            assert entry["created_by"] == "local"
            assert entry["time"]
        finally:
            requests.delete(f"{api_url}/sessions/{session_id}", timeout=5)
