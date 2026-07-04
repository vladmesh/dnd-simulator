"""Architecture guards for sprint 016 phase 3 — core boundaries.

These tests assert the structural decoupling wins made during phase 3 so
future edits can't silently regress them (e.g. a drive-by `import` that
re-couples round.py to EntitiesLayer).
"""

from __future__ import annotations

from pathlib import Path

from dnd_simulator.core.creature_host import CreatureHost
from dnd_simulator.layers.entities.layer import EntitiesLayer

SRC = Path(__file__).resolve().parents[2] / "src" / "dnd_simulator"


def _read(path: str) -> str:
    return (SRC / path).read_text(encoding="utf-8")


class TestRoundLayerIndependence:
    """round.py must not import from layers/ — it uses the CreatureHost protocol."""

    def test_round_does_not_import_from_layers(self) -> None:
        source = _read("round.py")
        for line in source.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            assert "from dnd_simulator.layers" not in stripped, (
                f"round.py must not import from dnd_simulator.layers — found: {stripped!r}"
            )
            assert "import dnd_simulator.layers" not in stripped, (
                f"round.py must not import dnd_simulator.layers — found: {stripped!r}"
            )

    def test_round_does_not_reference_entities_layer_type(self) -> None:
        source = _read("round.py")
        assert "EntitiesLayer" not in source, (
            "round.py must not reference EntitiesLayer — use CreatureHost protocol instead"
        )


class TestCreatureHostProtocol:
    """EntitiesLayer must structurally satisfy CreatureHost (runtime check)."""

    def test_entities_layer_is_a_creature_host(self) -> None:
        layer = EntitiesLayer(entities=[])
        assert isinstance(layer, CreatureHost)

    def test_world_creature_host_returns_entities_layer(self) -> None:
        from dnd_simulator.core.models import GameDateTime
        from dnd_simulator.core.world import World

        layer = EntitiesLayer(entities=[])
        world = World(layers=[layer], time=GameDateTime(year=1, month=1, day=1))
        assert world.creature_host is layer

    def test_world_creature_host_raises_when_missing(self) -> None:
        import pytest

        from dnd_simulator.core.models import GameDateTime
        from dnd_simulator.core.world import World

        world = World(layers=[], time=GameDateTime(year=1, month=1, day=1))
        with pytest.raises(RuntimeError, match="CreatureHost"):
            _ = world.creature_host


class TestWorldGetLayer:
    """World.get_layer/find_layer resolve a layer by type with fail-fast semantics."""

    def test_get_layer_returns_matching_layer(self) -> None:
        from dnd_simulator.core.models import GameDateTime
        from dnd_simulator.core.world import World

        layer = EntitiesLayer(entities=[])
        world = World(layers=[layer], time=GameDateTime(year=1, month=1, day=1))
        assert world.get_layer(EntitiesLayer) is layer

    def test_get_layer_raises_with_type_name_when_missing(self) -> None:
        import pytest

        from dnd_simulator.core.models import GameDateTime
        from dnd_simulator.core.world import LayerNotFoundError, World

        world = World(layers=[], time=GameDateTime(year=1, month=1, day=1))
        with pytest.raises(LayerNotFoundError, match="EntitiesLayer"):
            world.get_layer(EntitiesLayer)

    def test_find_layer_returns_none_when_missing(self) -> None:
        from dnd_simulator.core.models import GameDateTime
        from dnd_simulator.core.world import World

        world = World(layers=[], time=GameDateTime(year=1, month=1, day=1))
        assert world.find_layer(EntitiesLayer) is None


class TestLlmDoesNotImportLayers:
    """llm/ must not import from layers/ — use core types and Protocols instead."""

    def test_llm_module_has_no_layer_imports(self) -> None:
        llm_dir = SRC / "llm"
        offenders: list[str] = []
        for py in llm_dir.rglob("*.py"):
            for lineno, line in enumerate(py.read_text(encoding="utf-8").splitlines(), start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                if "from dnd_simulator.layers" in stripped or "import dnd_simulator.layers" in stripped:
                    offenders.append(f"{py.relative_to(SRC)}:{lineno}: {stripped}")
        assert not offenders, "llm/ must not depend on layers/:\n" + "\n".join(offenders)
