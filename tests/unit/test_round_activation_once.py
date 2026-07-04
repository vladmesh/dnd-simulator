"""Pin: run_loop activates exactly once per iteration (phase 3 task 3).

The review flagged activation running twice per loop step — run_loop._activate() then
run_round() re-activating — which double-runs the heaviest per-round op and risks double
materialization. run_round(skip_activation=True) fixes it; standalone run_round still activates.
"""

from __future__ import annotations

from dnd_simulator.core.location import LocationGraph
from dnd_simulator.core.models import GameDateTime
from dnd_simulator.core.world import World
from dnd_simulator.layers.entities.layer import EntitiesLayer
from dnd_simulator.round import Round


class _CountingHost:
    """Wraps a real host, counting update_activation calls; delegates everything else."""

    def __init__(self, inner: object) -> None:
        self._inner = inner
        self.activation_calls = 0

    def update_activation(self, *args: object, **kwargs: object) -> None:
        self.activation_calls += 1
        self._inner.update_activation(*args, **kwargs)  # type: ignore[attr-defined]

    def __getattr__(self, name: str) -> object:
        return getattr(self._inner, name)


def _empty_world() -> World:
    return World(
        layers=[EntitiesLayer(entities=[])],
        time=GameDateTime(year=1, month=1, day=1, hour=10),
        location_graph=LocationGraph([]),
    )


def test_run_round_standalone_activates_once() -> None:
    world = _empty_world()
    host = _CountingHost(world.creature_host)
    rnd = Round(world, creature_host=host)  # type: ignore[arg-type]
    rnd.run_round()
    assert host.activation_calls == 1


def test_run_round_skip_activation_does_not_activate() -> None:
    world = _empty_world()
    host = _CountingHost(world.creature_host)
    rnd = Round(world, creature_host=host)  # type: ignore[arg-type]
    rnd.run_round(skip_activation=True)
    assert host.activation_calls == 0


def test_run_loop_activates_once_per_iteration() -> None:
    """One loop iteration with no active creatures: only the run_loop._activate() call fires."""
    world = _empty_world()
    host = _CountingHost(world.creature_host)
    rnd = Round(world, creature_host=host)  # type: ignore[arg-type]
    # No active creatures and no wake times -> loop activates once, finds nobody, exits.
    rnd.run_loop(max_rounds=1)
    assert host.activation_calls == 1
