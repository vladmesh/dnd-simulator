"""World seed threading and deterministic layer RNG tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import GameDateTime, TimeDelta
from dnd_simulator.core.player import PlayerCharacter
from dnd_simulator.layers.ecology.layer import EcologyLayer
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.layers.entities.models import Npc
from dnd_simulator.layers.geography.models import Region, Season, TerrainType, WeatherCondition
from dnd_simulator.layers.geography.weather import WeatherEngine
from dnd_simulator.layers.politics.layer import PoliticsLayer
from dnd_simulator.layers.politics.models import Leader, LeaderTrait, Nation
from dnd_simulator.rules.dice import set_global_seed
from dnd_simulator.service.game_service import GameService
from dnd_simulator.service.session import GameSession
from dnd_simulator.storage.store import JsonFileStore

CONTENT_DIR = Path(__file__).resolve().parents[2] / "content"
FIGHTER_SCORES = {"str": 15, "dex": 10, "con": 14, "int": 8, "wis": 12, "cha": 8}


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


def _world_save_after_month(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, world_seed: int) -> dict[str, object]:
    monkeypatch.setenv("DND_WORLD_SEED", str(world_seed))
    set_global_seed(123)
    service = GameService(store=JsonFileStore(tmp_path / f"saves-{world_seed}"), content_dir=CONTENT_DIR)
    session = service.start_game("test_vale")
    for _ in range(31 * 24):
        session.world.advance_time(TimeDelta(seconds=3600))
    return session.world.save()


def test_same_world_seed_replays_full_world_save(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    save_a = _world_save_after_month(tmp_path / "a", monkeypatch, world_seed=42)
    save_b = _world_save_after_month(tmp_path / "b", monkeypatch, world_seed=42)

    assert save_a == save_b


def test_different_world_seed_changes_full_world_save(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    save_a = _world_save_after_month(tmp_path / "a", monkeypatch, world_seed=42)
    save_b = _world_save_after_month(tmp_path / "b", monkeypatch, world_seed=43)

    assert save_a != save_b


def _session_with_player(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    world_seed: int,
    location: str,
) -> GameSession:
    monkeypatch.setenv("DND_WORLD_SEED", str(world_seed))
    set_global_seed(123)
    service = GameService(store=JsonFileStore(tmp_path / f"saves-{world_seed}"), content_dir=CONTENT_DIR)
    session = service.start_game("test_vale")
    service.create_player(
        session.session_id,
        {
            "name": "Scout",
            "race": "human",
            "class": "fighter",
            "alignment": "true_neutral",
            "ability_scores": FIGHTER_SCORES,
            "fighting_style": "defense",
            "start_location": location,
        },
    )
    return session


def _activate(session: GameSession) -> None:
    entities = session.world.get_layer(EntitiesLayer)
    entities.update_activation(
        session.world.time,
        query_fn=session.world.make_query_fn("entities"),
        emit_fn=session.world.make_emit_fn("entities"),
    )


def _spawned_names_at(session: GameSession, location_id: str) -> list[str]:
    entities = session.world.get_layer(EntitiesLayer)
    return sorted(
        entity.name
        for entity in entities._entities.values()
        if isinstance(entity, Creature)
        and not isinstance(entity, (PlayerCharacter, Npc))
        and entity.location_id == location_id
        and entity.is_alive
    )


def test_same_world_seed_replays_encounter_spawns(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    session_a = _session_with_player(tmp_path / "a", monkeypatch, world_seed=42, location="crossroads_tavern")
    session_b = _session_with_player(tmp_path / "b", monkeypatch, world_seed=42, location="crossroads_tavern")

    _activate(session_a)
    _activate(session_b)

    assert _spawned_names_at(session_a, "crossroads_tavern") == _spawned_names_at(session_b, "crossroads_tavern")
