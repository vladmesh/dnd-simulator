# Task: effective_relation Pure Function + Reputation Field

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 2 — Personal Reputation + effective_relation

## Description

Add `reputation: dict[str, int]` field to `Creature` (sparse, default empty). Create `rules/reputation.py` with `effective_relation(a: Creature, b: Creature, get_faction_relation: RelationFn) -> FactionRelation` — the single source of truth for how two creatures relate.

Logic:
1. If A has a personal reputation entry for B's `faction_id` → apply thresholds: 75+ FRIENDLY, 25-74 NEUTRAL, <25 HOSTILE.
2. Otherwise → fall back to `get_faction_relation(a.faction_id, b.faction_id)`.
3. Same `faction_id` is NOT automatically FRIENDLY — personal rep overrides it (exile pattern). But if neither has personal overrides for the other's faction, same faction = FRIENDLY (via fallback).

Thresholds are constants in the module (not magic numbers scattered around).

## Tests First

Scenarios for `effective_relation`:

- Two creatures, same faction, no personal reputation → FRIENDLY (via faction fallback).
- Two creatures, different factions, faction relation HOSTILE, no personal rep → HOSTILE.
- Creature A has reputation 80 with B's faction → FRIENDLY regardless of faction-to-faction relation.
- Creature A has reputation 50 with B's faction → NEUTRAL regardless of faction-to-faction relation.
- Creature A has reputation 10 with B's faction → HOSTILE regardless of faction-to-faction relation.
- **Exile:** Creature with reputation 10 with OWN faction → HOSTILE to same-faction creatures.
- Threshold boundaries: rep=75 → FRIENDLY, rep=74 → NEUTRAL, rep=25 → NEUTRAL, rep=24 → HOSTILE.
- Creature with no faction_id → NEUTRAL to everyone (no crash).
- Asymmetric: A has personal rep for B's faction but B doesn't for A's → each direction resolved independently.

## Implementation

1. Add `reputation: dict[str, int] = field(default_factory=dict)` to `Creature` in `core/character.py`.
2. Create `rules/reputation.py`:
   - Constants: `FRIENDLY_THRESHOLD = 75`, `HOSTILE_THRESHOLD = 25`.
   - `reputation_to_relation(rep: int) -> FactionRelation` — pure threshold function.
   - `effective_relation(a: Creature, b: Creature, get_faction_relation: RelationFn) -> FactionRelation`.
   - Re-export `RelationFn` type from `combat_sides.py` or define shared type.
3. No callers yet — that's task 2 and 3.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Thresholds are named constants, not magic numbers
- [ ] Exile pattern works: same faction + low personal rep = HOSTILE

## Status

`pending`
