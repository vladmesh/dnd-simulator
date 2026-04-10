"""Tests for reputation system — effective_relation pure function + kill reputation drops."""

from __future__ import annotations

from dnd_simulator.core.character import Creature
from dnd_simulator.core.models import FactionRelation
from dnd_simulator.rules.reputation import (
    BASE_KILL_REPUTATION_DELTA,
    FRIENDLY_THRESHOLD,
    HOSTILE_THRESHOLD,
    apply_reputation_drop,
    compute_kill_reputation_delta,
    default_rep_for_faction,
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


class TestComputeKillReputationDelta:
    def test_normal_kill_full_delta(self) -> None:
        """Victim in good standing (default 100) → full base_delta."""
        victim = _make_creature("v", "bandits")
        assert compute_kill_reputation_delta(20, victim) == 20

    def test_outcast_kill_zero_delta(self) -> None:
        """Victim with 0 rep with own faction → 0 delta."""
        victim = _make_creature("v", "bandits", reputation={"bandits": 0})
        assert compute_kill_reputation_delta(20, victim) == 0

    def test_partial_standing_scales_linearly(self) -> None:
        """Victim with 50 rep → half the base delta."""
        victim = _make_creature("v", "bandits", reputation={"bandits": 50})
        assert compute_kill_reputation_delta(20, victim) == 10

    def test_factionless_victim_zero_delta(self) -> None:
        """Victim with no faction → 0 delta (no faction to offend)."""
        victim = _make_creature("v", "")
        assert compute_kill_reputation_delta(20, victim) == 0

    def test_low_standing_rounds_down(self) -> None:
        """Victim with 30 rep, base 20 → 6 (integer division)."""
        victim = _make_creature("v", "bandits", reputation={"bandits": 30})
        assert compute_kill_reputation_delta(20, victim) == 6


class TestApplyReputationDrop:
    def test_normal_kill_drops_reputation_no_relation_fn(self) -> None:
        """Without faction relation fn, falls back to 100 (backward compat)."""
        killer = _make_creature("k", "kingdom")
        victim = _make_creature("v", "bandits")
        delta = apply_reputation_drop(killer, victim, BASE_KILL_REPUTATION_DELTA)
        assert delta == BASE_KILL_REPUTATION_DELTA
        # Without get_faction_relation: defaults to 100 (legacy behavior).
        assert killer.reputation["bandits"] == 100 - BASE_KILL_REPUTATION_DELTA

    def test_hostile_faction_kill_no_drop(self) -> None:
        """Killing a member of a hostile faction: initial rep = 0, delta clamped to 0."""
        killer = _make_creature("k", "kingdom")
        victim = _make_creature("v", "goblins")
        get_rel = _relation_map(("kingdom", "goblins", FactionRelation.HOSTILE))
        delta = apply_reputation_drop(killer, victim, BASE_KILL_REPUTATION_DELTA, get_rel)
        assert delta == 0
        assert killer.reputation["goblins"] == 0

    def test_friendly_faction_kill_full_drop(self) -> None:
        """Killing a member of a friendly faction: initial rep = 100, full drop."""
        killer = _make_creature("k", "kingdom")
        victim = _make_creature("v", "allies")
        get_rel = _relation_map(("kingdom", "allies", FactionRelation.FRIENDLY))
        delta = apply_reputation_drop(killer, victim, BASE_KILL_REPUTATION_DELTA, get_rel)
        assert delta == BASE_KILL_REPUTATION_DELTA
        assert killer.reputation["allies"] == 80

    def test_neutral_faction_kill_partial_drop(self) -> None:
        """Killing a member of a neutral faction: initial rep = 50."""
        killer = _make_creature("k", "kingdom")
        victim = _make_creature("v", "merchants")
        get_rel = _relation_map()  # unspecified = NEUTRAL
        delta = apply_reputation_drop(killer, victim, BASE_KILL_REPUTATION_DELTA, get_rel)
        assert delta == BASE_KILL_REPUTATION_DELTA
        assert killer.reputation["merchants"] == 30

    def test_outcast_kill_no_change(self) -> None:
        """Killing an outcast (0 rep with own faction) → no rep change."""
        killer = _make_creature("k", "kingdom")
        victim = _make_creature("v", "bandits", reputation={"bandits": 0})
        delta = apply_reputation_drop(killer, victim, BASE_KILL_REPUTATION_DELTA)
        assert delta == 0
        assert "bandits" not in killer.reputation

    def test_repeated_kills_friendly_faction(self) -> None:
        """Two kills of friendly faction stack: 100→80→60."""
        killer = _make_creature("k", "kingdom")
        v1 = _make_creature("v1", "allies")
        v2 = _make_creature("v2", "allies")
        get_rel = _relation_map(("kingdom", "allies", FactionRelation.FRIENDLY))
        apply_reputation_drop(killer, v1, 20, get_rel)
        apply_reputation_drop(killer, v2, 20, get_rel)
        assert killer.reputation["allies"] == 60

    def test_repeated_kills_accumulate_from_personal_rep(self) -> None:
        """Once personal rep exists, subsequent kills use it (not faction default)."""
        killer = _make_creature("k", "kingdom", reputation={"bandits": 80})
        v1 = _make_creature("v1", "bandits")
        v2 = _make_creature("v2", "bandits")
        apply_reputation_drop(killer, v1, 20)
        apply_reputation_drop(killer, v2, 20)
        assert killer.reputation["bandits"] == 40

    def test_reputation_floors_at_zero(self) -> None:
        """Rep can't go below 0 even with massive delta."""
        killer = _make_creature("k", "kingdom", reputation={"bandits": 5})
        victim = _make_creature("v", "bandits")
        delta = apply_reputation_drop(killer, victim, 20)
        assert killer.reputation["bandits"] == 0
        assert delta == 5  # Only 5 was actually subtracted

    def test_factionless_victim_no_change(self) -> None:
        """Killing factionless creature → no reputation change."""
        killer = _make_creature("k", "kingdom")
        victim = _make_creature("v", "")
        delta = apply_reputation_drop(killer, victim, 20)
        assert delta == 0
        assert killer.reputation == {}

    def test_killing_own_faction_drops_own_rep(self) -> None:
        """Killing a member of your own faction drops rep with your own faction."""
        killer = _make_creature("k", "bandits")
        victim = _make_creature("v", "bandits")
        get_rel = _relation_map()
        delta = apply_reputation_drop(killer, victim, 20, get_rel)
        assert delta == 20
        assert killer.reputation["bandits"] == 80


class TestDefaultRepForFaction:
    def test_hostile_faction_zero(self) -> None:
        killer = _make_creature("k", "kingdom")
        get_rel = _relation_map(("kingdom", "goblins", FactionRelation.HOSTILE))
        assert default_rep_for_faction(killer, "goblins", get_rel) == 0

    def test_neutral_faction_fifty(self) -> None:
        killer = _make_creature("k", "kingdom")
        get_rel = _relation_map()  # default NEUTRAL
        assert default_rep_for_faction(killer, "merchants", get_rel) == 50

    def test_friendly_faction_hundred(self) -> None:
        killer = _make_creature("k", "kingdom")
        get_rel = _relation_map(("kingdom", "allies", FactionRelation.FRIENDLY))
        assert default_rep_for_faction(killer, "allies", get_rel) == 100

    def test_same_faction_hundred(self) -> None:
        killer = _make_creature("k", "kingdom")
        get_rel = _relation_map()
        assert default_rep_for_faction(killer, "kingdom", get_rel) == 100

    def test_no_killer_faction_fifty(self) -> None:
        killer = _make_creature("k", "")
        get_rel = _relation_map()
        assert default_rep_for_faction(killer, "goblins", get_rel) == 50
