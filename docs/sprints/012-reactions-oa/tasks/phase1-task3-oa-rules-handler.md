# Task: OA Rules + Handler + Disengage Fix

**Date:** 2026-03-30
**Sprint:** 012-reactions-oa
**Phase:** 1 — Reaction Infrastructure + OA Mechanics

## Description

Pure D&D 5e opportunity attack mechanics: eligibility rules, path scanning, the OA handler, and making Disengage actually do something. All testable with unit tests — no round/wiring integration.

### Concrete changes

- `ActionType.OPPORTUNITY_ATTACK` — new enum value.
- `CostType.REACTION` — new cost type.
- `ActionCost.reaction: int = 0` — new field on ActionCost.
- `TurnBudget.can_afford` / `consume` / `refund` — handle reaction cost.
- `TurnBudget.turn_over` — reaction does NOT count (you don't end your turn because you have unused reaction).
- `ActionDef` for OPPORTUNITY_ATTACK: cost=REACTION, targeted, combat_only, internal (not offered by providers — triggered by movement only).
- `rules/reactions.py` — pure functions:
  - `can_opportunity_attack(reactor: Creature, mover: Creature, battle_map: BattleMap) -> bool` — checks: reactor alive, not incapacitated, has reaction budget (`reactor.turn_budget.reaction > 0`), mover in reach (weapon reach via `get_weapon_reach`), mover not disengaging (`not mover.is_disengaging`), reactor is not the mover.
  - `find_oa_triggers(path: list[Position], mover: Creature, combatants: list[Creature], battle_map: BattleMap) -> list[tuple[int, list[Creature]]]` — for each step in the path, find combatants whose reach the mover is LEAVING (was in reach at step i, not in reach at step i+1). Return `(step_index, [reactors])` pairs.
- `rules/handlers/reactions.py` — new handler:
  - `handle_opportunity_attack(actor, action, emit_fn, ctx, world) -> ActionResult` — one melee attack against target. Uses `get_weapon_attack` → `resolve_attack` (same as normal attack handler). Emits OPPORTUNITY_ATTACK event. Does NOT consume reaction from budget (Round does that after success, same pattern as other costs — but actually, OA is dispatched outside the normal turn loop, so the handler SHOULD consume `actor.turn_budget.reaction -= 1` directly, since dispatcher won't do it for reactions). Decision: handler consumes reaction.
- `handle_disengage` — change from no-op to `actor.is_disengaging = True`. One line fix.
- `EventType.OPPORTUNITY_ATTACK` — new event type for combat log.

## Tests First

Scenarios (in `tests/unit/test_opportunity_attack.py`):

1. **OA eligibility — basic case.** Reactor with sword (reach 5), mover 5ft away, reactor has reaction budget → can_opportunity_attack returns True.
2. **OA blocked by incapacitated.** Reactor is stunned → False.
3. **OA blocked by no reaction budget.** Reactor's turn_budget.reaction == 0 → False.
4. **OA blocked by disengaging.** Mover has is_disengaging=True → False.
5. **OA blocked by out of reach.** Mover is 10ft away, reactor has 5ft reach → False.
6. **OA with extended reach.** Reactor has polearm (reach 10), mover 10ft away → True.
7. **find_oa_triggers on straight path.** Mover walks from (10,10) to (10,30) past an enemy at (15,10) with 5ft reach. Enemy should trigger at the step where mover leaves (10,10)→(10,15) area (distance goes from 5 to 10).
8. **find_oa_triggers — two enemies on same path.** Two enemies at different points along path — both trigger at their respective exit steps.
9. **find_oa_triggers — disengaging mover.** Same path setup but mover.is_disengaging=True → empty list.
10. **OA handler deals damage.** Set up reactor with weapon, target at adjacent position. Handler resolves melee attack (mock dice), emits OPPORTUNITY_ATTACK event, consumes reaction.
11. **CostType.REACTION + ActionCost.reaction.** TurnBudget with reaction=1, consume ActionCost(reaction=1) → reaction=0. Can't afford second reaction.
12. **Disengage handler sets is_disengaging.** Call handle_disengage → actor.is_disengaging is True.

## Implementation

1. Add `OPPORTUNITY_ATTACK` to `ActionType`, `REACTION` to `CostType`.
2. Add `reaction: int = 0` to `ActionCost`. Update `TurnBudget.can_afford/consume/refund` to handle reaction.
3. Register `ActionDef` for OPPORTUNITY_ATTACK (cost=REACTION, targeted, combat_only, internal=True).
4. Add `EventType.OPPORTUNITY_ATTACK` to event types.
5. Create `rules/reactions.py` with `can_opportunity_attack` and `find_oa_triggers`.
6. Create `rules/handlers/reactions.py` with `handle_opportunity_attack`.
7. Fix `handle_disengage` in `rules/handlers/movement.py` — set `actor.is_disengaging = True`.
8. Register handler in dispatcher setup.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] OA eligibility respects: alive, not incapacitated, has reaction, in reach, target not disengaging
- [ ] find_oa_triggers correctly identifies reach-exit steps
- [ ] OA handler reuses existing attack resolution (no duplicate damage logic)
- [ ] Disengage is no longer a no-op
- [ ] ActionCost supports reaction cost

## Status

`pending`
