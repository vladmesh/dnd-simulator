"""Tests for reputation system — effective_relation pure function."""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import FactionRelation
from dnd_simulator.rules.reputation import (
    FRIENDLY_THRESHOLD,
    HOSTILE_THRESHOLD,
    effective_relation,
    reputation_to_relation,
)


def _make_creature(id: str, faction_id: str = "", reputation: dict[str, int] | None = None) -> Creature:
    return Creature(
        id=id,
        name=id,
        location_id="loc",
        faction_id=faction_id,
        reputation=reputation or {},
    )


def _relation_map(*pairs: tuple[str, str, FactionRelation]):
    """Build a relation lookup from explicit pairs. Same faction = FRIENDLY, unspecified = NEUTRAL."""
    lookup: dict[tuple[str, str], FactionRelation] = {}
    for a, b, rel in pairs:
        lookup[(a, b)] = rel
        lookup[(b, a)] = rel

    def get_relation(a: str, b: str) -> FactionRelation:
        if a == b:
            return FactionRelation.FRIENDLY
        return lookup.get((a, b), FactionRelation.NEUTRAL)

    return get_relation


class TestReputationToRelation:
    def test_high_rep_friendly(self) -> None:
        assert reputation_to_relation(80) == FactionRelation.FRIENDLY

    def test_mid_rep_neutral(self) -> None:
        assert reputation_to_relation(50) == FactionRelation.NEUTRAL

    def test_low_rep_hostile(self) -> None:
        assert reputation_to_relation(10) == FactionRelation.HOSTILE

    def test_boundary_friendly_at_threshold(self) -> None:
        assert reputation_to_relation(FRIENDLY_THRESHOLD) == FactionRelation.FRIENDLY

    def test_boundary_below_friendly(self) -> None:
        assert reputation_to_relation(FRIENDLY_THRESHOLD - 1) == FactionRelation.NEUTRAL

    def test_boundary_neutral_at_hostile_threshold(self) -> None:
        assert reputation_to_relation(HOSTILE_THRESHOLD) == FactionRelation.NEUTRAL

    def test_boundary_hostile_below_threshold(self) -> None:
        assert reputation_to_relation(HOSTILE_THRESHOLD - 1) == FactionRelation.HOSTILE


class TestEffectiveRelation:
    def test_same_faction_no_rep_friendly(self) -> None:
        """Same faction, no personal reputation → FRIENDLY via fallback."""
        a = _make_creature("a", "goblins")
        b = _make_creature("b", "goblins")
        assert effective_relation(a, b, _relation_map()) == FactionRelation.FRIENDLY

    def test_different_factions_hostile_no_rep(self) -> None:
        """Different factions, faction relation HOSTILE, no personal rep → HOSTILE."""
        a = _make_creature("a", "goblins")
        b = _make_creature("b", "guards")
        get_rel = _relation_map(("goblins", "guards", FactionRelation.HOSTILE))
        assert effective_relation(a, b, get_rel) == FactionRelation.HOSTILE

    def test_personal_rep_friendly_overrides_faction_hostile(self) -> None:
        """A has rep 80 with B's faction → FRIENDLY despite faction-level HOSTILE."""
        a = _make_creature("a", "goblins", reputation={"guards": 80})
        b = _make_creature("b", "guards")
        get_rel = _relation_map(("goblins", "guards", FactionRelation.HOSTILE))
        assert effective_relation(a, b, get_rel) == FactionRelation.FRIENDLY

    def test_personal_rep_neutral(self) -> None:
        """A has rep 50 with B's faction → NEUTRAL."""
        a = _make_creature("a", "goblins", reputation={"guards": 50})
        b = _make_creature("b", "guards")
        get_rel = _relation_map(("goblins", "guards", FactionRelation.HOSTILE))
        assert effective_relation(a, b, get_rel) == FactionRelation.NEUTRAL

    def test_personal_rep_hostile(self) -> None:
        """A has rep 10 with B's faction → HOSTILE."""
        a = _make_creature("a", "goblins", reputation={"guards": 10})
        b = _make_creature("b", "guards")
        get_rel = _relation_map(("goblins", "guards", FactionRelation.FRIENDLY))
        assert effective_relation(a, b, get_rel) == FactionRelation.HOSTILE

    def test_exile_pattern(self) -> None:
        """Creature with rep 10 with OWN faction → HOSTILE to same-faction creatures."""
        exile = _make_creature("exile", "goblins", reputation={"goblins": 10})
        loyal = _make_creature("loyal", "goblins")
        assert effective_relation(exile, loyal, _relation_map()) == FactionRelation.HOSTILE

    def test_no_faction_neutral(self) -> None:
        """Creature with no faction_id → NEUTRAL to everyone."""
        a = _make_creature("a", "")
        b = _make_creature("b", "guards")
        assert effective_relation(a, b, _relation_map()) == FactionRelation.NEUTRAL

    def test_both_no_faction_neutral(self) -> None:
        """Both creatures without faction → NEUTRAL."""
        a = _make_creature("a", "")
        b = _make_creature("b", "")
        assert effective_relation(a, b, _relation_map()) == FactionRelation.NEUTRAL

    def test_target_no_faction_neutral(self) -> None:
        """Target has no faction → NEUTRAL (can't look up rep for empty faction)."""
        a = _make_creature("a", "guards")
        b = _make_creature("b", "")
        assert effective_relation(a, b, _relation_map()) == FactionRelation.NEUTRAL

    def test_asymmetric_rep(self) -> None:
        """A has personal rep for B's faction, B doesn't for A's → each direction independent."""
        a = _make_creature("a", "goblins", reputation={"guards": 80})
        b = _make_creature("b", "guards")
        get_rel = _relation_map(("goblins", "guards", FactionRelation.HOSTILE))
        # A→B: personal rep 80 → FRIENDLY
        assert effective_relation(a, b, get_rel) == FactionRelation.FRIENDLY
        # B→A: no personal rep → faction fallback HOSTILE
        assert effective_relation(b, a, get_rel) == FactionRelation.HOSTILE
