"""Tests for world structure parsers rewritten to use Pydantic content models.

Covers: round-trip for regions/locations/nations/settlements,
validation errors, empty YAML, and full start_game integration.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from dnd_simulator.content_loader.schemas import (
    LocationContent,
    NationContent,
    RegionContent,
    SettlementContent,
)
from dnd_simulator.content_loader.world import (
    load_locations,
    load_nations,
    load_settlements,
    load_world,
)

GEOGRAPHY_PATH = Path("content/library/geography/sword_vale")
POLITICS_PATH = Path("content/library/politics/sword_vale")
SETTLEMENTS_PATH = Path("content/worlds/sword_vale/settlements")


# ---------------------------------------------------------------------------
# 1. Round-trip: regions
# ---------------------------------------------------------------------------


class TestRegionsRoundTrip:
    """Load sword_vale regions → verify data survives Pydantic path."""

    def test_load_regions_returns_nonempty(self) -> None:
        regions = load_world(GEOGRAPHY_PATH, lang="en")
        assert len(regions) > 0

    def test_region_fields_populated(self) -> None:
        regions = load_world(GEOGRAPHY_PATH, lang="en")
        region_by_id = {r.id: r for r in regions}
        # sword_vale has a "silverport" region
        assert "silverport" in region_by_id
        sp = region_by_id["silverport"]
        assert sp.name  # non-empty
        assert sp.terrain is not None
        assert sp.latitude != 0.0 or sp.longitude != 0.0  # has coordinates

    def test_region_connections_preserved(self) -> None:
        regions = load_world(GEOGRAPHY_PATH, lang="en")
        region_with_conns = [r for r in regions if r.connections]
        assert len(region_with_conns) > 0
        conn = region_with_conns[0].connections[0]
        assert conn.target_id
        assert conn.direction is not None

    def test_region_round_trip_via_schema(self) -> None:
        """Load → convert to schema → validate → fields match."""
        regions = load_world(GEOGRAPHY_PATH, lang="en")
        for region in regions:
            # Build a schema-compatible dict from the runtime Region
            schema_dict = {
                "name": {"en": region.name},
                "latitude": region.latitude,
                "longitude": region.longitude,
                "elevation": region.elevation,
                "terrain": region.terrain.value,
                "water_proximity": region.water_proximity,
                "connections": [{"target": c.target_id, "direction": c.direction.value} for c in region.connections],
            }
            model = RegionContent.model_validate(schema_dict)
            assert model.terrain == region.terrain
            assert model.latitude == region.latitude


# ---------------------------------------------------------------------------
# 2. Round-trip: locations
# ---------------------------------------------------------------------------


class TestLocationsRoundTrip:
    """Load sword_vale locations → verify data survives Pydantic path."""

    def test_load_locations_returns_nonempty(self) -> None:
        regions = load_world(GEOGRAPHY_PATH, lang="en")
        locations = load_locations(GEOGRAPHY_PATH, regions, lang="en")
        assert len(locations) > 0

    def test_location_fields_populated(self) -> None:
        regions = load_world(GEOGRAPHY_PATH, lang="en")
        locations = load_locations(GEOGRAPHY_PATH, regions, lang="en")
        some_loc = locations[0]
        assert some_loc.name
        assert some_loc.region_id

    def test_location_round_trip_via_schema(self) -> None:
        regions = load_world(GEOGRAPHY_PATH, lang="en")
        locations = load_locations(GEOGRAPHY_PATH, regions, lang="en")
        for loc in locations:
            schema_dict = {
                "name": {"en": loc.name},
                "region": loc.region_id,
                "settlement": loc.settlement_id,
                "description": {"en": loc.description} if loc.description else {},
                "neighbors": [{"target": e.target_id, "distance": e.distance_m} for e in loc.edges],
            }
            model = LocationContent.model_validate(schema_dict)
            assert model.region == loc.region_id


# ---------------------------------------------------------------------------
# 3. Round-trip: nations
# ---------------------------------------------------------------------------


class TestNationsRoundTrip:
    """Load sword_vale nations → verify data survives Pydantic path."""

    def test_load_nations_returns_nonempty(self) -> None:
        nations = load_nations(POLITICS_PATH, lang="en")
        assert len(nations) > 0

    def test_nation_fields_populated(self) -> None:
        nations = load_nations(POLITICS_PATH, lang="en")
        nation = nations[0]
        assert nation.name
        assert nation.id

    def test_nation_leader_preserved(self) -> None:
        nations = load_nations(POLITICS_PATH, lang="en")
        nations_with_leader = [n for n in nations if n.leader is not None]
        assert len(nations_with_leader) > 0
        leader = nations_with_leader[0].leader
        assert leader is not None
        assert leader.name
        assert leader.trait is not None

    def test_nation_round_trip_via_schema(self) -> None:
        nations = load_nations(POLITICS_PATH, lang="en")
        for nation in nations:
            leader_dict = None
            if nation.leader:
                leader_dict = {
                    "name": {"en": nation.leader.name},
                    "age": nation.leader.age,
                    "trait": nation.leader.trait.value,
                }
            schema_dict = {
                "name": {"en": nation.name},
                "regions": nation.regions,
                "wealth": nation.wealth,
                "military": nation.military,
                "stability": nation.stability,
                "leader": leader_dict,
            }
            model = NationContent.model_validate(schema_dict)
            assert model.wealth == nation.wealth


# ---------------------------------------------------------------------------
# 4. Round-trip: settlements
# ---------------------------------------------------------------------------


class TestSettlementsRoundTrip:
    """Load sword_vale settlements → verify data survives Pydantic path."""

    def test_load_settlements_returns_nonempty(self) -> None:
        settlements = load_settlements(SETTLEMENTS_PATH, lang="en")
        assert len(settlements) > 0

    def test_settlement_fields_populated(self) -> None:
        settlements = load_settlements(SETTLEMENTS_PATH, lang="en")
        s = settlements[0]
        assert s.name
        assert s.region_id
        assert s.type is not None

    def test_settlement_round_trip_via_schema(self) -> None:
        settlements = load_settlements(SETTLEMENTS_PATH, lang="en")
        for s in settlements:
            schema_dict = {
                "name": {"en": s.name},
                "region": s.region_id,
                "type": s.type.value,
                "population": s.population,
                "prosperity": s.prosperity,
                "defenses": s.defenses,
            }
            model = SettlementContent.model_validate(schema_dict)
            assert model.population == s.population


# ---------------------------------------------------------------------------
# 5. Validation error on bad region terrain
# ---------------------------------------------------------------------------


class TestValidationErrors:
    """Bad YAML data must produce clear Pydantic ValidationError."""

    def test_bad_terrain_raises_validation_error(self, tmp_path: Path) -> None:
        """Region with terrain: lava → ValidationError, not KeyError."""
        yaml_content = """
bad_region:
  name:
    en: Bad Region
  latitude: 0
  longitude: 0
  elevation: 0
  terrain: lava
  water_proximity: 0.0
"""
        regions_file = tmp_path / "regions.yaml"
        regions_file.write_text(yaml_content)
        with pytest.raises(ValidationError):
            load_world(tmp_path, lang="en")

    def test_missing_name_raises_validation_error(self, tmp_path: Path) -> None:
        """Region without name → ValidationError."""
        yaml_content = """
bad_region:
  latitude: 0
  longitude: 0
  elevation: 0
  terrain: plains
"""
        regions_file = tmp_path / "regions.yaml"
        regions_file.write_text(yaml_content)
        with pytest.raises(ValidationError):
            load_world(tmp_path, lang="en")

    def test_bad_direction_raises_validation_error(self, tmp_path: Path) -> None:
        """Connection with direction: up → ValidationError."""
        yaml_content = """
region_a:
  name:
    en: Region A
  latitude: 0
  longitude: 0
  elevation: 0
  terrain: plains
  connections:
    - target: region_b
      direction: up
"""
        regions_file = tmp_path / "regions.yaml"
        regions_file.write_text(yaml_content)
        with pytest.raises(ValidationError):
            load_world(tmp_path, lang="en")

    def test_bad_settlement_type_raises_validation_error(self, tmp_path: Path) -> None:
        """Settlement with type: metropolis → ValidationError."""
        yaml_content = """
bad_settlement:
  name:
    en: Bad
  region: r1
  type: metropolis
"""
        settlements_file = tmp_path / "settlements.yaml"
        settlements_file.write_text(yaml_content)
        with pytest.raises(ValidationError):
            load_settlements(tmp_path, lang="en")

    def test_bad_leader_trait_raises_validation_error(self, tmp_path: Path) -> None:
        """Nation with leader trait: tyrant → ValidationError."""
        yaml_content = """
bad_nation:
  name:
    en: Bad
  leader:
    name:
      en: Tyrant
    age: 40
    trait: tyrant
"""
        nations_file = tmp_path / "nations.yaml"
        nations_file.write_text(yaml_content)
        with pytest.raises(ValidationError):
            load_nations(tmp_path, lang="en")


# ---------------------------------------------------------------------------
# 7. Empty YAML returns empty list
# ---------------------------------------------------------------------------


class TestEmptyYaml:
    """Scaffolded (empty) layers produce empty results."""

    def test_empty_regions(self, tmp_path: Path) -> None:
        (tmp_path / "regions.yaml").write_text("")
        assert load_world(tmp_path, lang="en") == []

    def test_empty_locations(self, tmp_path: Path) -> None:
        regions = load_world(GEOGRAPHY_PATH, lang="en")
        # No locations.yaml at all
        assert load_locations(tmp_path, regions, lang="en") == []

    def test_empty_nations(self, tmp_path: Path) -> None:
        (tmp_path / "nations.yaml").write_text("")
        assert load_nations(tmp_path, lang="en") == []

    def test_empty_settlements(self, tmp_path: Path) -> None:
        (tmp_path / "settlements.yaml").write_text("")
        assert load_settlements(tmp_path, lang="en") == []


# ---------------------------------------------------------------------------
# 8. start_game still works with sword_vale
# ---------------------------------------------------------------------------


class TestStartGameIntegration:
    """Load sword_vale through GameService → session created, all layers present."""

    def test_start_game_creates_session(self, tmp_path: Path) -> None:
        from dnd_simulator.service import GameService
        from dnd_simulator.storage.store import JsonFileStore

        store = JsonFileStore(tmp_path / "saves")
        svc = GameService(store=store, content_dir=Path("content"))
        session = svc.start_game(world_name="sword_vale", lang="en")

        assert session is not None
        assert session.world is not None
        # All 5 layers present
        assert len(session.world.layers) == 5
