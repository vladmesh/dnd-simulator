# Task: TurnBudget on Creature + is_disengaging

**Date:** 2026-03-30
**Sprint:** 012-reactions-oa
**Phase:** 1 — Reaction Infrastructure + OA Mechanics

## Description

Move TurnBudget from a local variable in `Round.run_combat_turn()` to a field on `Creature`. D&D 5e: action/bonus/movement/reaction budget lasts from the start of your turn to the start of your next turn. Reactions happen between turns, so the budget must be accessible outside the turn method.

Also add `is_disengaging: bool` on Creature (same pattern as `is_dodging`), reset at turn start.

### Concrete changes

- `Creature.turn_budget: TurnBudget | None = None` — new field.
- `Creature.is_disengaging: bool = False` — new field.
- `Round.run_combat_turn()` — create budget on `creature.turn_budget` instead of local var. Pass `creature.turn_budget` into `ActionContext`. Remove local `budget` variable.
- `Round.run_round()` — reset `creature.is_disengaging = False` at turn start (next to `is_dodging` reset).
- `EntitiesLayer.reset_combat_turn_state()` — also reset `is_disengaging = False` here if it's the right place.
- No behavioral changes — existing tests must still pass with budget living on creature.

## Tests First

Scenarios (in `tests/unit/test_turn_budget_on_creature.py`):

1. **Budget created on creature at turn start.** Create a Creature with speed 30, give it a brain. After `run_combat_turn`, `creature.turn_budget` is not None and has expected initial values (1 action, 1 bonus, 30 movement, 1 reaction).
2. **Budget persists after turn ends.** After `run_combat_turn` completes, `creature.turn_budget` still holds the depleted budget (not reset to None). This is critical — reactions between turns read from this budget.
3. **Budget resets at start of NEXT turn.** On second call to `run_combat_turn` for the same creature, budget is freshly created (not carried over from previous turn).
4. **is_disengaging resets at turn start.** Set `creature.is_disengaging = True`, run a turn — it's False at the start of the turn.
5. **ActionContext receives creature's budget.** Verify dispatcher receives ActionContext with `turn_budget` pointing to `creature.turn_budget` (same object, not a copy).

## Implementation

1. Add `turn_budget` and `is_disengaging` fields to `Creature` in `core/character.py`.
2. In `Round.run_combat_turn()`: replace `budget = TurnBudget(...)` with `creature.turn_budget = TurnBudget(...)`. Replace all `budget` references with `creature.turn_budget`. Update `ActionContext` construction.
3. In `Round.run_round()`: add `creature.is_disengaging = False` next to `creature.is_dodging = False`.
4. Check `reset_combat_turn_state` — add `is_disengaging` reset if appropriate.
5. Run `make check` — zero behavioral change expected.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] `creature.turn_budget` is set during combat turn and persists after
- [ ] No local `budget` variable in `run_combat_turn` — everything goes through `creature.turn_budget`
- [ ] `is_disengaging` resets at turn start

## Status

`done`

## Developer Notes

Straightforward refactor. Added `turn_budget: TurnBudget | None` and `is_disengaging: bool` to Creature. Replaced all local `budget` variable usage in `run_combat_turn` with `creature.turn_budget`. Reset `is_disengaging` both in `run_combat_turn` (at budget creation) and in `run_round` (alongside `is_dodging`). No existing tests broke — zero behavioral change.
