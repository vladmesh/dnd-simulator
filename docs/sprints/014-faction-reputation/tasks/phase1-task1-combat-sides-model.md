# Task: CombatSides Model + Build Algorithm

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 1 — Combat Sides + OA Fix

## Description

Create a pure `build_combat_sides()` function in `rules/combat_sides.py` that takes a list of creatures and a relation lookup callback, and returns a sides mapping. Add `sides` and `entity_to_side` fields to `CombatState`.

Algorithm (graph coloring):
- Creatures with same `faction_id` → same side.
- FRIENDLY factions → merge into one side.
- HOSTILE factions → different sides.
- NEUTRAL factions → different sides (neutrals don't join anyone).
- "Friend of both" (FRIENDLY to two warring factions): same `faction_id` wins, otherwise first encountered side.
- Creatures without `faction_id` → each gets its own side (hostile to everyone).

Data model on `CombatState`:
- `sides: dict[int, set[str]]` — side index → set of entity IDs.
- `entity_to_side: dict[str, int]` — entity ID → side index for O(1) lookups.

Helper: `are_allies(combat, entity_a_id, entity_b_id) -> bool` — True if same side.

## Tests First

Product-level scenarios in `tests/unit/test_combat_sides.py`:

1. **Same faction = same side.** Three goblins (faction "goblins") → all on side 0.
2. **Hostile factions = different sides.** Two goblins + two guards (factions HOSTILE) → side 0 vs side 1.
3. **Three factions, mixed relations.** Goblins HOSTILE to guards, bandits FRIENDLY to goblins → goblins+bandits vs guards (two sides, not three).
4. **Neutral faction = own side.** Merchants NEUTRAL to both goblins and guards → three sides (merchants fight alone).
5. **No faction = own side per creature.** Two creatures without faction_id → each on its own side, hostile to everyone.
6. **Friend-of-both resolution.** Mercenary faction FRIENDLY to both goblins and guards (who are HOSTILE to each other): mercenaries with `faction_id == "goblins"` join goblin side; mercenaries with `faction_id == "mercenaries"` join the first-encountered FRIENDLY side.
7. **are_allies helper.** Two creatures on same side → True, different sides → False.

## Implementation

1. Create `src/dnd_simulator/rules/combat_sides.py`:
   - Type: `RelationFn = Callable[[str, str], FactionRelation]`
   - `build_combat_sides(creatures: list[Creature], get_relation: RelationFn) -> tuple[dict[int, set[str]], dict[str, int]]`
   - Union-Find or simple iterative merge for grouping FRIENDLY factions.
   - `are_allies(combat: CombatState, a: str, b: str) -> bool`

2. Update `core/combat.py`:
   - Add `sides` and `entity_to_side` fields to `CombatState` (default empty).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Pure function — no I/O, no state mutation, no layer imports
- [ ] Handles edge cases: empty list, single creature, all same faction

## Status

`done`

## Developer Notes

Union-Find was the initial approach but it merges transitively — a faction FRIENDLY to two warring factions would incorrectly merge the warring factions into one side. Switched to greedy assignment: process factions in order, join the first existing side that has a FRIENDLY faction, or create a new side. This correctly handles "friend of both" by joining the first-encountered side without merging hostile factions together.
