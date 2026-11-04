"""Coverage for missing nations and war declarations in diplomacy."""

from __future__ import annotations

import random

import pytest
from test_politics_diplomacy import _make_nation

from dnd_simulator.core.events import WarDeclaredPayload
from dnd_simulator.core.models import EventType
from dnd_simulator.layers.politics.diplomacy import _nations_are_neighbors, process_diplomacy
from dnd_simulator.layers.politics.models import DiplomaticStatus, Leader, LeaderTrait


@pytest.mark.parametrize(
    ("nid_a", "nid_b"),
    [("missing", "beta"), ("alpha", "missing"), ("missing_a", "missing_b")],
)
def test_missing_nations_are_not_neighbors(nid_a: str, nid_b: str) -> None:
    alpha = _make_nation(nation_id="alpha", regions=["region_a"])
    beta = _make_nation(nation_id="beta", regions=["region_b"])
    nations = {alpha.id: alpha, beta.id: beta}
    adjacency = {"region_a": ["region_b"], "region_b": ["region_a"]}

    assert not _nations_are_neighbors(nid_a, nid_b, nations, adjacency)


@pytest.mark.parametrize(("aggressor_id", "seed"), [("alpha", 31), ("beta", 15)])
@pytest.mark.parametrize("explicit_peace", [False, True])
def test_stronger_neighbor_declares_war(aggressor_id: str, seed: int, explicit_peace: bool) -> None:
    alpha = _make_nation(nation_id="alpha", name="Alpha", regions=["region_a"], military=10.0)
    beta = _make_nation(nation_id="beta", name="Beta", regions=["region_b"], military=10.0)
    nations = {alpha.id: alpha, beta.id: beta}
    aggressor = nations[aggressor_id]
    aggressor.military = 100.0
    aggressor.leader = Leader(name="Trader", age=40, trait=LeaderTrait.MERCHANT)
    target = beta if aggressor_id == "alpha" else alpha
    key = ("alpha", "beta")
    relations: dict[tuple[str, str], DiplomaticStatus] = {key: DiplomaticStatus.PEACE} if explicit_peace else {}
    war_durations: dict[tuple[str, str], int] = {}
    adjacency = {"region_a": ["region_b"], "region_b": ["region_a"]}

    events = process_diplomacy(nations, relations, war_durations, adjacency, random.Random(seed))

    assert relations == {key: DiplomaticStatus.WAR}
    assert war_durations == {key: 0}
    assert len(events) == 1
    event = events[0]
    assert event.event_type == EventType.WAR_DECLARED
    assert event.source_layer == "politics"
    assert event.data == WarDeclaredPayload(aggressor.id, target.id)
    assert event.description == f"{aggressor.name} declares war on {target.name}!"
