# Task: Wire Sides into Combat — OA Fix + Combat End

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 1 — Combat Sides + OA Fix

## Description

Integrate `build_combat_sides()` into the combat lifecycle: build sides at combat start, filter OA triggers by side, fix combat end condition.

Changes:
- `combat_manager.start_combat()` — call `build_combat_sides()` using politics layer `get_faction_relation` as callback. Store result on `CombatState`.
- `rules/reactions.py: find_oa_triggers()` — add `combat_state: CombatState` parameter. Filter out reactors on the same side as the mover using `are_allies()`.
- `combat_manager._has_opposing_factions()` — replace faction_id counting with: count sides that still have alive members, combat continues if ≥ 2 non-empty sides.
- `combat_manager._remove_from_combat()` — remove entity from `sides` and `entity_to_side` when removed from combat.
- `round.py` — pass `CombatState` to `find_oa_triggers()` in the movement callback.

## Tests First

Product-level scenarios:

1. **OA bug fix (the main bug).** Three goblins in combat with a guard. Goblin moves away from another goblin → no OA triggered. Goblin moves away from guard → OA triggered.
2. **Mixed factions OA.** Goblins + bandits (FRIENDLY) vs guards. Bandit moves away from goblin → no OA. Bandit moves away from guard → OA.
3. **Combat ends when one side eliminated.** Two goblins vs two guards. Both guards die → combat ends (even though two goblins remain, they're on the same side).
4. **Combat continues with 2+ sides alive.** Three-way fight (goblins vs guards vs neutral merchants). Kill all merchants → combat continues (goblins vs guards). Kill all guards → combat ends.
5. **Creature removal updates sides.** Remove a creature from combat → entity_to_side and sides updated, no stale references.

## Implementation

1. `combat_manager.start_combat()` — after creating `CombatState`, call `build_combat_sides()` with creatures and a relation lookup that queries politics layer. Assign to `combat.sides` and `combat.entity_to_side`.

2. `rules/reactions.py` — add `combat_state` parameter to `find_oa_triggers()`. In the reactor filter loop, add: `if are_allies(combat_state, mover.id, c.id): continue`.

3. `combat_manager._has_opposing_factions()` — rewrite to check `combat.sides`: count sides where at least one entity is alive, return `count >= 2`.

4. `combat_manager._remove_from_combat()` — also remove from `combat.sides[side]` and `combat.entity_to_side`.

5. `round.py` — update `_make_on_leave_reach` and callers to pass combat state through to `find_oa_triggers()`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Goblins no longer OA each other (the original bug is fixed)
- [ ] Combat ends correctly based on sides, not raw faction count

## Status

`pending`
