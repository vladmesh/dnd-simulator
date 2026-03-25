# Task: Abstract Squad Combat Formula

**Date:** 2026-03-25
**Sprint:** 004-monster-encounters
**Phase:** 2 — Generalize Encounters + Hostile AI

## Description

Pure function in `rules/` that resolves a squad encountering monsters abstractly — no Creature spawning, no battle map, no turns. Input: squad strength + encounter data. Output: who won, how much strength the squad lost.

Formula (simplest viable):
- Encounter power = sum of `(template.cr * count)` for each triggered entry
- If `squad.strength >= encounter_power`: squad wins, loses `ceil(encounter_power / 2)` strength
- If `squad.strength < encounter_power`: squad loses, loses `ceil(squad.strength / 2)` strength (retreats battered)
- Minimum strength after combat: 0
- Optional: ±1 randomness on strength loss (single die, not per-creature)

This is a standalone function — Phase 3 (EcologyLayer) will call it when squads move through encounter zones. For now, just the formula + tests.

Returns a result dataclass: `AbstractCombatResult(won: bool, strength_lost: int, encounter_power: float)`.

## Tests First

Scenarios:

1. **Strong squad vs weak encounter → wins, loses some strength.** Squad strength 10 vs encounter power 4. Squad wins, loses 2 strength.
2. **Weak squad vs strong encounter → loses, retreats.** Squad strength 3 vs encounter power 8. Squad loses, loses 2 strength.
3. **Equal strength → squad wins (defender advantage).** Squad strength 5 vs encounter power 5. Squad wins.
4. **Squad strength can't go below 0.** Squad strength 1 vs encounter power 20. Loses, strength loss capped.
5. **Empty encounter table → no combat, no losses.** No entries triggered. Return won=True, strength_lost=0.
6. **Multiple encounter entries sum power correctly.** Two triggered entries: CR 2 × 3 count + CR 1 × 2 count = 8 total power.

## Implementation

- Create `rules/abstract_combat.py` with `resolve_abstract_combat(squad_strength: int, encounter_entries: list[TriggeredEncounter]) -> AbstractCombatResult`
- `TriggeredEncounter` dataclass: `cr: float, count: int`
- `AbstractCombatResult` frozen dataclass: `won: bool, strength_lost: int, encounter_power: float`
- Pure function, no state, no I/O — follows `rules/` conventions
- No randomness in v1 (deterministic = easier to test). Can add ±1 jitter later.

## Acceptance Criteria

- [ ] Tests written and RED
- [ ] Implementation makes tests GREEN
- [ ] `make check` passes
- [ ] Formula is deterministic and handles edge cases (0 strength, empty encounters)
- [ ] No dependencies outside `rules/` and `core/`

## Status

`pending`
