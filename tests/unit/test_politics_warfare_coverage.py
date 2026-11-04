"""Coverage for warfare with missing nations and non-conquering relations."""

from __future__ import annotations

import random
from copy import deepcopy

import pytest
from test_politics_warfare import _make_nation

from dnd_simulator.layers.politics.models import DiplomaticStatus
from dnd_simulator.layers.politics.warfare import _find_border_region, process_wars


@pytest.mark.parametrize("missing_ids", [("alpha",), ("beta",), ("alpha", "beta")])
def test_find_border_region_with_missing_nations(missing_ids: tuple[str, ...]) -> None:
    alpha = _make_nation(nation_id="alpha", regions=["region_a"])
    beta = _make_nation(nation_id="beta", regions=["region_c"])
    nations = {nation.id: nation for nation in (alpha, beta) if nation.id not in missing_ids}
    before = deepcopy(nations)
    adjacency = {"region_a": ["region_c"], "region_c": ["region_a"]}

    assert _find_border_region("alpha", "beta", nations, adjacency) is None
    assert nations == before


@pytest.mark.parametrize(
    "status",
    [DiplomaticStatus.PEACE, DiplomaticStatus.TRADE_AGREEMENT, DiplomaticStatus.ALLIANCE],
)
def test_non_war_relations_leave_nations_unchanged(status: DiplomaticStatus) -> None:
    alpha = _make_nation(nation_id="alpha", regions=["region_a"], military=80.0)
    beta = _make_nation(nation_id="beta", regions=["region_c"], military=40.0)
    nations = {alpha.id: alpha, beta.id: beta}
    before = deepcopy(nations)
    adjacency = {"region_a": ["region_c"], "region_c": ["region_a"]}

    events = process_wars(nations, {("alpha", "beta"): status}, {}, adjacency, random.Random(42))

    assert events == []
    assert nations == before


@pytest.mark.parametrize("missing_ids", [("alpha",), ("beta",), ("alpha", "beta")])
def test_wars_with_missing_nations_are_skipped(missing_ids: tuple[str, ...]) -> None:
    alpha = _make_nation(nation_id="alpha", regions=["region_a"], military=80.0)
    beta = _make_nation(nation_id="beta", regions=["region_c"], military=40.0)
    nations = {nation.id: nation for nation in (alpha, beta) if nation.id not in missing_ids}
    before = deepcopy(nations)
    relations = {("alpha", "beta"): DiplomaticStatus.WAR}
    adjacency = {"region_a": ["region_c"], "region_c": ["region_a"]}

    events = process_wars(nations, relations, {("alpha", "beta"): 3}, adjacency, random.Random(42))

    assert events == []
    assert nations == before


@pytest.mark.parametrize(
    "adjacency",
    [{}, {"region_a": ["region_x"], "region_c": ["region_y"]}],
    ids=["missing-adjacency", "disconnected-regions"],
)
def test_war_without_shared_border_applies_costs_without_conquest(adjacency: dict[str, list[str]]) -> None:
    alpha = _make_nation(nation_id="alpha", regions=["region_a"], military=80.0)
    beta = _make_nation(nation_id="beta", regions=["region_c"], military=40.0)
    nations = {alpha.id: alpha, beta.id: beta}
    relations = {("alpha", "beta"): DiplomaticStatus.WAR}

    events = process_wars(nations, relations, {("alpha", "beta"): 3}, adjacency, random.Random(42))

    assert events == []
    assert (alpha.regions, alpha.military, alpha.stability) == (["region_a"], 78.0, 70.0)
    assert (beta.regions, beta.military, beta.stability) == (["region_c"], 36.0, 67.0)


def test_stalemate_costs_military_without_conquest_or_stability_loss() -> None:
    alpha = _make_nation(nation_id="alpha", regions=["region_a"])
    beta = _make_nation(nation_id="beta", regions=["region_c"])
    nations = {alpha.id: alpha, beta.id: beta}
    relations = {("alpha", "beta"): DiplomaticStatus.WAR}
    adjacency = {"region_a": ["region_c"], "region_c": ["region_a"]}

    events = process_wars(nations, relations, {("alpha", "beta"): 3}, adjacency, random.Random(0))

    assert events == []
    assert (alpha.regions, alpha.military, alpha.stability) == (["region_a"], 49.0, 70.0)
    assert (beta.regions, beta.military, beta.stability) == (["region_c"], 49.0, 70.0)
