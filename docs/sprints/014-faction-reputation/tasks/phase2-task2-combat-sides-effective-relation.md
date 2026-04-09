# Task: CombatSides Uses effective_relation

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 2 — Personal Reputation + effective_relation

## Description

Refactor `build_combat_sides` to use `effective_relation` instead of raw faction-to-faction lookups. The current algorithm groups creatures by `faction_id` first — this breaks the exile pattern (creature hostile to own faction gets grouped with them).

New algorithm: creature-level relation graph instead of faction-level grouping.

1. Build a relation graph between all creature pairs using `effective_relation`.
2. Group creatures that are mutually FRIENDLY into the same side (greedy, same approach as current — first FRIENDLY match wins).
3. Factionless creatures still get their own side.

Change `build_combat_sides` signature: callback becomes `Callable[[Creature, Creature], FactionRelation]` instead of `Callable[[str, str], FactionRelation]`. The function already receives `list[Creature]`, so creature-level callback is natural.

Update `combat_manager.py` to construct the new callback wrapping `effective_relation` + politics query.

## Tests First

Scenarios (extend existing `test_combat_sides.py`):

- **Exile pattern:** 3 goblins, one has reputation 10 with "goblin" faction. Two goblins on one side, exile on separate side.
- **Personal friendship:** Creature from hostile faction has reputation 80 with player's faction → joins player's side.
- **Mixed:** 5 creatures from 3 factions, some with personal overrides → sides reflect effective relations, not raw factions.
- **Backward compat:** All existing test scenarios still pass (no personal rep = same behavior as before).
- **Asymmetric rep:** A friendly to B's faction, B hostile to A's faction → they end up on different sides (hostility wins — can't be allies if one considers the other hostile).

## Implementation

1. Change `build_combat_sides` signature: `get_relation: Callable[[Creature, Creature], FactionRelation]` instead of `Callable[[str, str], FactionRelation]`.
2. Rewrite grouping: iterate creatures individually. For each creature, check effective relation against existing sides' members. FRIENDLY to all on a side → join. HOSTILE to any → skip that side. Create new side if no match.
3. Update `combat_manager.py:start_combat` — build callback: `lambda a, b: effective_relation(a, b, get_faction_relation_from_politics)`.
4. Update all existing tests to pass creatures through the new callback signature.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Exile creature gets separate side from own faction
- [ ] All existing combat_sides tests pass with no personal reputation (backward compat)

## Status

`pending`
