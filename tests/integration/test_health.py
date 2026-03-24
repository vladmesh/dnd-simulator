"""Smoke test: backend starts and responds to /health."""

from http import HTTPStatus

import requests


def test_backend_health(backend_url: str) -> None:
    resp = requests.get(f"{backend_url}/health", timeout=5)
    assert resp.status_code == HTTPStatus.OK
    assert resp.json()["status"] == "ok"
