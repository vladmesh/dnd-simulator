"""Integration test configuration."""

import os

import pytest


@pytest.fixture
def backend_url() -> str:
    """Base URL of the running backend. Defaults to docker-compose service name."""
    return os.environ.get("BACKEND_URL", "http://backend:8001")
