"""Tests for library catalog — template listing and compatibility filtering."""

from __future__ import annotations

from http import HTTPStatus
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

from dnd_simulator.adapters.api.app import app
from dnd_simulator.adapters.api.deps import set_service
from dnd_simulator.content_loader.library import (
    TemplateInfo,
    list_compatible_templates,
    list_templates,
)
from dnd_simulator.content_loader.manifest import LayerType
from dnd_simulator.service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _write_metadata(path: Path, data: dict[str, object]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    with (path / "metadata.yaml").open("w") as f:
        yaml.dump(data, f)


def _make_library(tmp_path: Path) -> Path:
    """Create a temp content dir with library templates for testing."""
    content_dir = tmp_path / "content"
    library = content_dir / "library"

    # Two geography templates
    _write_metadata(
        library / "geography" / "alpha",
        {
            "name": "Alpha Geography",
            "layer_type": "geography",
            "version": "1.0",
            "description": "Alpha world geography",
            "tags": ["fantasy"],
        },
    )
    _write_metadata(
        library / "geography" / "beta",
        {
            "name": "Beta Geography",
            "layer_type": "geography",
            "version": "2.0",
            "description": "Beta world geography",
            "tags": ["sci-fi"],
        },
    )

    # Two settlements templates — one compatible with alpha, one with beta
    _write_metadata(
        library / "settlements" / "alpha_towns",
        {
            "name": "Alpha Towns",
            "layer_type": "settlements",
            "version": "1.0",
            "description": "Towns for alpha",
            "tags": ["fantasy"],
            "requires_geography": ["alpha"],
        },
    )
    _write_metadata(
        library / "settlements" / "beta_cities",
        {
            "name": "Beta Cities",
            "layer_type": "settlements",
            "version": "1.0",
            "description": "Cities for beta",
            "tags": ["sci-fi"],
            "requires_geography": ["beta"],
        },
    )

    # A universal settlements template (no requires_geography)
    _write_metadata(
        library / "settlements" / "universal_hamlet",
        {
            "name": "Universal Hamlet",
            "layer_type": "settlements",
            "version": "1.0",
            "description": "Works anywhere",
            "tags": ["generic"],
        },
    )

    return content_dir


class TestListTemplates:
    def test_lists_all_geography_templates_sorted(self, tmp_path: Path) -> None:
        content_dir = _make_library(tmp_path)
        result = list_templates(content_dir, LayerType.GEOGRAPHY)
        assert len(result) == 2
        assert result[0].slug == "alpha"
        assert result[1].slug == "beta"
        assert all(isinstance(t, TemplateInfo) for t in result)

    def test_lists_settlements_templates(self, tmp_path: Path) -> None:
        content_dir = _make_library(tmp_path)
        result = list_templates(content_dir, LayerType.SETTLEMENTS)
        assert len(result) == 3
        slugs = [t.slug for t in result]
        assert slugs == ["alpha_towns", "beta_cities", "universal_hamlet"]

    def test_template_info_fields(self, tmp_path: Path) -> None:
        content_dir = _make_library(tmp_path)
        result = list_templates(content_dir, LayerType.GEOGRAPHY)
        alpha = result[0]
        assert alpha.slug == "alpha"
        assert alpha.name == "Alpha Geography"
        assert alpha.layer_type == LayerType.GEOGRAPHY
        assert alpha.version == "1.0"
        assert alpha.description == "Alpha world geography"
        assert alpha.tags == ["fantasy"]
        assert alpha.requires_geography == []

    def test_missing_metadata_raises(self, tmp_path: Path) -> None:
        content_dir = tmp_path / "content"
        # Directory exists but no metadata.yaml inside
        (content_dir / "library" / "geography" / "broken").mkdir(parents=True)
        with pytest.raises(RuntimeError, match=r"metadata\.yaml"):
            list_templates(content_dir, LayerType.GEOGRAPHY)

    def test_empty_layer_type_returns_empty(self, tmp_path: Path) -> None:
        content_dir = _make_library(tmp_path)
        # No ecology templates created
        result = list_templates(content_dir, LayerType.ECOLOGY)
        assert result == []

    def test_nonexistent_library_dir_returns_empty(self, tmp_path: Path) -> None:
        content_dir = tmp_path / "content"
        # No library dir at all
        result = list_templates(content_dir, LayerType.GEOGRAPHY)
        assert result == []


class TestCompatibilityFilter:
    def test_filters_by_geography(self, tmp_path: Path) -> None:
        content_dir = _make_library(tmp_path)
        result = list_compatible_templates(content_dir, LayerType.SETTLEMENTS, selected={"geography": "alpha"})
        slugs = [t.slug for t in result]
        assert "alpha_towns" in slugs
        assert "beta_cities" not in slugs

    def test_universal_template_always_included(self, tmp_path: Path) -> None:
        content_dir = _make_library(tmp_path)
        result = list_compatible_templates(content_dir, LayerType.SETTLEMENTS, selected={"geography": "alpha"})
        slugs = [t.slug for t in result]
        assert "universal_hamlet" in slugs

    def test_no_selection_returns_all(self, tmp_path: Path) -> None:
        content_dir = _make_library(tmp_path)
        result = list_compatible_templates(content_dir, LayerType.SETTLEMENTS, selected={})
        assert len(result) == 3

    def test_geography_has_no_requirements(self, tmp_path: Path) -> None:
        content_dir = _make_library(tmp_path)
        result = list_compatible_templates(content_dir, LayerType.GEOGRAPHY, selected={"geography": "anything"})
        # Geography templates never have requires_geography, so all are returned
        assert len(result) == 2


class TestLibraryApiEndpoint:
    def _make_client(self, tmp_path: Path) -> TestClient:
        store = JsonFileStore(tmp_path / "saves")
        service = GameService(store=store)
        set_service(service)
        return TestClient(app)

    def test_list_geography_templates(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        resp = client.get("/api/master/library/geography")
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert isinstance(data, list)
        slugs = [t["slug"] for t in data]
        assert "sword_vale" in slugs

    def test_list_settlements_filtered_by_geography(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        resp = client.get("/api/master/library/settlements?geography=sword_vale")
        assert resp.status_code == HTTPStatus.OK
        data = resp.json()
        assert isinstance(data, list)
        slugs = [t["slug"] for t in data]
        assert "sword_vale" in slugs

    def test_invalid_layer_type_returns_422(self, tmp_path: Path) -> None:
        client = self._make_client(tmp_path)
        resp = client.get("/api/master/library/bogus_layer")
        assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY
