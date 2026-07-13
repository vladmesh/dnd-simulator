"""Tests for politics diplomacy submodule."""

from __future__ import annotations

import random

from dnd_simulator.core.events import PeaceDeclaredPayload, TradeAgreementPayload
from dnd_simulator.layers.politics.models import (
    DiplomaticStatus,
    Leader,
    LeaderTrait,
    Nation,
)


def _make_nation(
    *,
    nation_id: str = "alpha",
    name: str = "Alpha",
    regions: list[str] | None = None,
    military: float = 50.0,
    leader: Leader | None = None,
) -> Nation:
    return Nation(
        id=nation_id,
        name=name,
        regions=regions or ["region_a"],
        military=military,
        leader=leader,
    )


class TestProcessDiplomacy:
    def test_long_war_eventually_makes_peace(self) -> None:
        """Two nations at war for 20+ months have a chance to sign peace."""
        from dnd_simulator.layers.politics.diplomacy import process_diplomacy

        alpha = _make_nation(nation_id="alpha", regions=["region_a"])
        beta = _make_nation(nation_id="beta", regions=["region_b"])
        nations = {alpha.id: alpha, beta.id: beta}
        relations: dict[tuple[str, str], DiplomaticStatus] = {("alpha", "beta"): DiplomaticStatus.WAR}
        war_durations: dict[tuple[str, str], int] = {("alpha", "beta"): 20}
        adjacency = {"region_a": ["region_b"], "region_b": ["region_a"]}

        # Try multiple seeds — peace should happen within a few attempts at 20 months
        peace_happened = False
        for seed in range(100):
            # Reset state
            relations[("alpha", "beta")] = DiplomaticStatus.WAR
            war_durations[("alpha", "beta")] = 20
            rng = random.Random(seed)
            events = process_diplomacy(nations, relations, war_durations, adjacency, rng)
            peace_events = [e for e in events if isinstance(e.data, PeaceDeclaredPayload)]
            if peace_events:
                peace_happened = True
                assert relations[("alpha", "beta")] == DiplomaticStatus.PEACE
                assert ("alpha", "beta") not in war_durations
                break

        assert peace_happened, "Peace should happen at least once in 100 seeds with 20 months of war"

    def test_merchant_leader_proposes_trade(self) -> None:
        """A merchant leader can establish a trade agreement with a peaceful neighbor."""
        from dnd_simulator.layers.politics.diplomacy import process_diplomacy

        merchant = Leader(name="Trader", age=40, trait=LeaderTrait.MERCHANT)
        alpha = _make_nation(nation_id="alpha", regions=["region_a"], leader=merchant)
        beta = _make_nation(nation_id="beta", regions=["region_b"])
        nations = {alpha.id: alpha, beta.id: beta}
        relations: dict[tuple[str, str], DiplomaticStatus] = {("alpha", "beta"): DiplomaticStatus.PEACE}
        war_durations: dict[tuple[str, str], int] = {}
        adjacency = {"region_a": ["region_b"], "region_b": ["region_a"]}

        trade_happened = False
        for seed in range(200):
            relations[("alpha", "beta")] = DiplomaticStatus.PEACE
            rng = random.Random(seed)
            events = process_diplomacy(nations, relations, war_durations, adjacency, rng)
            trade_events = [e for e in events if isinstance(e.data, TradeAgreementPayload)]
            if trade_events:
                trade_happened = True
                assert relations[("alpha", "beta")] == DiplomaticStatus.TRADE_AGREEMENT
                break

        assert trade_happened, "Merchant leader should propose trade at least once in 200 seeds"

    def test_non_neighbors_no_diplomacy(self) -> None:
        """Nations without shared borders don't interact diplomatically."""
        from dnd_simulator.layers.politics.diplomacy import process_diplomacy

        alpha = _make_nation(nation_id="alpha", regions=["region_a"])
        beta = _make_nation(nation_id="beta", regions=["region_b"])
        nations = {alpha.id: alpha, beta.id: beta}
        relations: dict[tuple[str, str], DiplomaticStatus] = {}
        war_durations: dict[tuple[str, str], int] = {}
        # No adjacency between regions
        adjacency: dict[str, list[str]] = {"region_a": [], "region_b": []}
        rng = random.Random(42)

        events = process_diplomacy(nations, relations, war_durations, adjacency, rng)

        assert events == []
