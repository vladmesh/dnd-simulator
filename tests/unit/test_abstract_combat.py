"""Tests for abstract squad combat resolution formula."""

from __future__ import annotations

from dnd_simulator.rules.abstract_combat import (
    AbstractCombatResult,
    TriggeredEncounter,
    resolve_abstract_combat,
)


class TestAbstractCombatResolution:
    """Squad vs encounter resolved by strength comparison formula."""

    def test_strong_squad_wins_loses_some_strength(self) -> None:
        """Squad strength 10 vs encounter power 4 → wins, loses ceil(4/2)=2."""
        entries = [TriggeredEncounter(cr=2.0, count=2)]  # power = 4
        result = resolve_abstract_combat(squad_strength=10, encounters=entries)
        assert result == AbstractCombatResult(won=True, strength_lost=2, encounter_power=4.0)

    def test_weak_squad_loses_retreats_battered(self) -> None:
        """Squad strength 3 vs encounter power 8 → loses, loses ceil(3/2)=2."""
        entries = [TriggeredEncounter(cr=2.0, count=4)]  # power = 8
        result = resolve_abstract_combat(squad_strength=3, encounters=entries)
        assert result == AbstractCombatResult(won=False, strength_lost=2, encounter_power=8.0)

    def test_equal_strength_squad_wins(self) -> None:
        """Squad strength == encounter power → squad wins (defender advantage)."""
        entries = [TriggeredEncounter(cr=2.5, count=2)]  # power = 5
        result = resolve_abstract_combat(squad_strength=5, encounters=entries)
        assert result.won is True

    def test_strength_loss_cannot_exceed_current(self) -> None:
        """Squad strength 1 vs encounter power 20 → loses, loses ceil(1/2)=1."""
        entries = [TriggeredEncounter(cr=10.0, count=2)]  # power = 20
        result = resolve_abstract_combat(squad_strength=1, encounters=entries)
        assert result.won is False
        assert result.strength_lost == 1
        assert result.encounter_power == 20.0

    def test_empty_encounters_no_combat(self) -> None:
        """No encounters triggered → won=True, no losses."""
        result = resolve_abstract_combat(squad_strength=5, encounters=[])
        assert result == AbstractCombatResult(won=True, strength_lost=0, encounter_power=0.0)

    def test_multiple_entries_sum_power(self) -> None:
        """Two entries: CR 2 x 3 + CR 1 x 2 = 8 total power."""
        entries = [
            TriggeredEncounter(cr=2.0, count=3),  # 6
            TriggeredEncounter(cr=1.0, count=2),  # 2
        ]
        result = resolve_abstract_combat(squad_strength=10, encounters=entries)
        assert result.encounter_power == 8.0
        assert result.won is True
        assert result.strength_lost == 4  # ceil(8/2)

    def test_zero_strength_squad(self) -> None:
        """Squad with 0 strength always loses, loses 0."""
        entries = [TriggeredEncounter(cr=1.0, count=1)]
        result = resolve_abstract_combat(squad_strength=0, encounters=entries)
        assert result.won is False
        assert result.strength_lost == 0

    def test_fractional_cr_sums_correctly(self) -> None:
        """CR 0.25 x 4 goblins = 1.0 encounter power."""
        entries = [TriggeredEncounter(cr=0.25, count=4)]
        result = resolve_abstract_combat(squad_strength=10, encounters=entries)
        assert result.encounter_power == 1.0
        assert result.won is True
        assert result.strength_lost == 1  # ceil(1.0/2)
