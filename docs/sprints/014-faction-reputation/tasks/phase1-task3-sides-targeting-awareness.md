# Task: Sides-Based Targeting + Awareness

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 1 — Combat Sides + OA Fix

## Description

Switch all in-combat hostility checks from ad-hoc faction relation queries to side-based lookups. Out of combat, faction relation queries remain (no sides exist yet).

Changes:
- `awareness_builder.build_combat_awareness()` — when building `nearby` list during combat, use `are_allies(combat, observer.id, other.id)` instead of `check_faction_hostility()`. Pass `CombatState` to the method. Outside combat, `check_faction_hostility()` still used.
- `combat_manager._is_faction_friendly()` — in combat, check `are_allies()`. This fixes sneak attack ally detection to be consistent with sides.
- `combat_manager.resolve_attack()` — the `is_ally` lambda for `find_adjacent_ally()` uses sides.

This ensures that ALL combat systems (targeting, OA, sneak attack, awareness) use a single source of truth: `CombatState.sides`.

## Tests First

Product-level scenarios:

1. **RuleBrain targets enemies, not allies.** Goblin in combat with goblins + guards. Goblin's awareness shows other goblins as `is_hostile=False`, guards as `is_hostile=True`. RuleBrain picks a guard, not another goblin.
2. **FRIENDLY factions seen as allies in combat.** Goblins + bandits (FRIENDLY) vs guards. Bandit's awareness: goblins `is_hostile=False`, guards `is_hostile=True`.
3. **Sneak attack ally adjacency uses sides.** Rogue (guards faction) flanking a goblin, guard adjacent to same goblin. `find_adjacent_ally` returns True (guard is on same side as rogue). Bandit adjacent → False (different side).
4. **Out-of-combat hostility still works.** Two creatures not in combat — `is_hostile` determined by faction relation query, not sides (sides don't exist).

## Implementation

1. `awareness_builder.build_combat_awareness()` — accept optional `CombatState`. If provided, determine `is_hostile` via `not are_allies(combat, observer.id, other.id)` for entities in the combat. If not provided or entity not in combat, fall back to `check_faction_hostility()`.

2. `combat_manager.resolve_attack()` — change the `is_ally` lambda: if combat has sides, use `are_allies(combat, attacker.id, eid)`.

3. Thread `CombatState` through from `entities/layer.py` → `awareness_builder` where needed.

4. Verify `_is_faction_friendly` is only used in `resolve_attack` and replace there. If used elsewhere, update consistently.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] All in-combat hostility uses sides as single source of truth
- [ ] Out-of-combat hostility unchanged (faction relation queries)
- [ ] No remaining calls to `check_faction_hostility()` for in-combat entities

## Status

`done`

## Developer Notes

Minimal changes to two files:

1. `awareness_builder.py` — `build_combat_awareness()` now checks `combat.entity_to_side` first. If sides exist and the observer is in them, `is_hostile = not are_allies(...)`. Falls back to `check_faction_hostility()` when no sides (combat started without query_fn).

2. `combat_manager.py` — `resolve_attack()` switches the `is_ally` lambda for `find_adjacent_ally()`: uses `are_allies()` when `combat.entity_to_side` is populated, otherwise falls back to `_is_faction_friendly()`.

`_is_faction_friendly()` kept as-is — still used as fallback. `check_faction_hostility()` on AwarenessBuilder also kept — used for peaceful awareness (out of combat) and as combat fallback.

No changes to `reactions.py` — it already uses `are_allies()` from task 2.
