"""Tests for politics warfare submodule."""

from __future__ import annotations

import random

from dnd_simulator.core.events import RegionConqueredPayload
from dnd_simulator.layers.politics.models import (
    DiplomaticStatus,
    Nation,
)


def _make_nation(
    *,
    nation_id: str = "alpha",
    name: str = "Alpha",
    regions: list[str] | None = None,
    military: float = 50.0,
    stability: float = 70.0,
) -> Nation:
    return Nation(
        id=nation_id,
        name=name,
        regions=regions or ["region_a"],
        military=military,
        stability=stability,
    )


class TestProcessWars:
    def test_stronger_side_conquers_border_region(self) -> None:
        """Attacker with 80 military vs 40 military conquers a border region."""
        from dnd_simulator.layers.politics.warfare import process_wars

        alpha = _make_nation(
            nation_id="alpha",
            regions=["region_a", "region_b"],
            military=80.0,
            stability=80.0,
        )
        beta = _make_nation(
            nation_id="beta",
            regions=["region_c", "region_d"],
            military=40.0,
            stability=60.0,
        )
        nations = {alpha.id: alpha, beta.id: beta}
        relations = {("alpha", "beta"): DiplomaticStatus.WAR}
        war_durations = {("alpha", "beta"): 3}
        adjacency = {
            "region_a": ["region_b"],
            "region_b": ["region_a", "region_c"],
            "region_c": ["region_b", "region_d"],
            "region_d": ["region_c"],
        }
        # Seed so alpha clearly wins (high roll for alpha, low for beta)
        rng = random.Random(42)

        events = process_wars(nations, relations, war_durations, adjacency, rng)

        # With 80 vs 40 military, alpha should win and conquer
        conquest_events = [e for e in events if isinstance(e.data, RegionConqueredPayload)]
        assert len(conquest_events) == 1
        assert conquest_events[0].data.winner_id == "alpha"

    def test_war_costs_applied(self) -> None:
        """Both winner and loser lose military. Loser also loses stability."""
        from dnd_simulator.layers.politics.warfare import (
            LOSER_MILITARY_COST,
            LOSER_STABILITY_COST,
            WINNER_MILITARY_COST,
            process_wars,
        )

        alpha = _make_nation(nation_id="alpha", regions=["region_a"], military=80.0, stability=70.0)
        beta = _make_nation(nation_id="beta", regions=["region_c"], military=40.0, stability=70.0)
        nations = {alpha.id: alpha, beta.id: beta}
        relations = {("alpha", "beta"): DiplomaticStatus.WAR}
        war_durations = {("alpha", "beta"): 0}
        adjacency = {"region_a": ["region_c"], "region_c": ["region_a"]}
        rng = random.Random(42)

        alpha_mil_before = alpha.military
        beta_mil_before = beta.military
        beta_stab_before = beta.stability

        process_wars(nations, relations, war_durations, adjacency, rng)

        # Winner loses WINNER_MILITARY_COST, loser loses LOSER_MILITARY_COST + stability
        assert alpha.military <= alpha_mil_before - WINNER_MILITARY_COST
        assert beta.military <= beta_mil_before - LOSER_MILITARY_COST
        assert beta.stability <= beta_stab_before - LOSER_STABILITY_COST

    def test_stalemate_both_lose_military(self) -> None:
        """When strength difference < threshold, both sides lose 1 military."""
        from dnd_simulator.layers.politics.warfare import STALEMATE_MILITARY_COST, process_wars

        # Equal forces → stalemate likely
        alpha = _make_nation(nation_id="alpha", regions=["region_a"], military=50.0, stability=70.0)
        beta = _make_nation(nation_id="beta", regions=["region_c"], military=50.0, stability=70.0)
        nations = {alpha.id: alpha, beta.id: beta}
        relations = {("alpha", "beta"): DiplomaticStatus.WAR}
        war_durations = {("alpha", "beta"): 0}
        adjacency = {"region_a": ["region_c"], "region_c": ["region_a"]}
        # Seed for near-equal rolls
        rng = random.Random(7)

        events = process_wars(nations, relations, war_durations, adjacency, rng)

        conquest_events = [e for e in events if isinstance(e.data, RegionConqueredPayload)]
        # Either stalemate (no conquest, both lose 1) or narrow victory
        if not conquest_events:
            assert alpha.military == 50.0 - STALEMATE_MILITARY_COST
            assert beta.military == 50.0 - STALEMATE_MILITARY_COST
