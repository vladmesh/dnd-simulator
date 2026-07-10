"""World seed threading and deterministic layer RNG tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.core.models import GameDateTime, TimeDelta
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.geography.models import Region, Season, TerrainType, WeatherCondition
from dnd_simulator.layers.geography.weather import WeatherEngine
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.politics.models import Leader, LeaderTrait, Nation
from dnd_simulator.service.game_service import GameService
from dnd_simulator.storage.store import JsonFileStore


def _make_nations() -> list[Nation]:
    return [
        Nation(
            id="alpha",
            name="Alpha",
            regions=["alpha_region"],
            wealth=60.0,
            military=80.0,
            stability=35.0,
            leader=Leader(name="Aster", age=76, trait=LeaderTrait.MILITARIST),
        ),
        Nation(
            id="beta",
            name="Beta",
            regions=["beta_region"],
            wealth=55.0,
            military=55.0,
            stability=40.0,
            leader=Leader(name="Beryl", age=74, trait=LeaderTrait.DIPLOMAT),
        ),
    ]


def _make_politics(seed: int) -> PoliticsLayer:
    return PoliticsLayer(
        nations=_make_nations(),
        region_adjacency={"alpha_region": ["beta_region"], "beta_region": ["alpha_region"]},
        seed=seed,
    )


def _tick_politics(layer: PoliticsLayer, months: int) -> list[dict[str, object]]:
    snapshots: list[dict[str, object]] = []

    def query_fn(layer_name: str, query: object) -> object:
        raise AssertionError(f"unexpected query to {layer_name}: {query}")

    def emit_fn(event: object) -> object:
        raise AssertionError(f"unexpected event emit: {event}")

    for month in range(months):
        time = GameDateTime(year=1490, month=(month % 12) + 1, day=1, hour=0)
        layer.tick(TimeDelta(seconds=2_592_000), time, query_fn, emit_fn)  # type: ignore[arg-type]
        snapshots.append(layer.get_state())
    return snapshots


def _make_region() -> Region:
    return Region(
        id="greenvale",
        name="Greenvale",
        latitude=45.0,
        longitude=0.0,
        elevation=0.0,
        terrain=TerrainType.PLAINS,
        water_proximity=0.3,
        weather=WeatherCondition.CLEAR,
    )


def _weather_sequence(seed: int) -> list[WeatherCondition]:
    engine = WeatherEngine(seed=seed)
    region = _make_region()
    sequence: list[WeatherCondition] = []
    for _ in range(20):
        region.weather = engine.next_weather(region, Season.SUMMER, 20.0)
        sequence.append(region.weather)
    return sequence


def test_politics_seed_replays_same_outcomes_and_different_seed_diverges() -> None:
    assert _tick_politics(_make_politics(seed=42), months=18) == _tick_politics(_make_politics(seed=42), months=18)
    assert _tick_politics(_make_politics(seed=42), months=18) != _tick_politics(_make_politics(seed=43), months=18)


def test_weather_seed_replays_same_sequence_and_different_seed_diverges() -> None:
    assert _weather_sequence(42) == _weather_sequence(42)
    assert _weather_sequence(42) != _weather_sequence(43)


def test_game_service_threads_world_seed_to_layer_streams(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from dnd_simulator.layers.geography.layer import GeographyLayer

    monkeypatch.setenv("DND_WORLD_SEED", "42")
    first = GameService(store=JsonFileStore(tmp_path / "saves1"))
    second = GameService(store=JsonFileStore(tmp_path / "saves2"))

    world_a = first.start_game("sword_vale").world
    world_b = second.start_game("sword_vale").world

    assert world_a.seed == 42
    assert world_b.seed == 42

    samples_a = {
        "geography": tuple(world_a.get_layer(GeographyLayer)._weather._rng.random() for _ in range(3)),  # type: ignore[attr-defined]
        "politics": tuple(world_a.get_layer(PoliticsLayer)._rng.random() for _ in range(3)),  # type: ignore[attr-defined]
        "ecology": tuple(world_a.get_layer(EcologyLayer)._rng.random() for _ in range(3)),  # type: ignore[attr-defined]
        "entities": tuple(world_a.get_layer(EntitiesLayer)._rng.random() for _ in range(3)),  # type: ignore[attr-defined]
    }
    samples_b = {
        "geography": tuple(world_b.get_layer(GeographyLayer)._weather._rng.random() for _ in range(3)),  # type: ignore[attr-defined]
        "politics": tuple(world_b.get_layer(PoliticsLayer)._rng.random() for _ in range(3)),  # type: ignore[attr-defined]
        "ecology": tuple(world_b.get_layer(EcologyLayer)._rng.random() for _ in range(3)),  # type: ignore[attr-defined]
        "entities": tuple(world_b.get_layer(EntitiesLayer)._rng.random() for _ in range(3)),  # type: ignore[attr-defined]
    }

    assert samples_a == samples_b
    assert len(set(samples_a.values())) == len(samples_a)
