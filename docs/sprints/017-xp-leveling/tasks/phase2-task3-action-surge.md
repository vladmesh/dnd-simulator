# Task: Action Surge action + handler (Fighter L2)

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 2 — Level-up mechanics + Paladin L2 fix

## Description

Add the Action Surge action for Fighter L2+. Spending a bonus action on the
current turn grants one additional Action that may be used immediately (same
turn). Pool is `action_surge` (1 use, short-rest reset — already created in
task 2). Modelled after Second Wind as a `provider_managed=True` SELF action.

## Tests First

Product-level integration scenarios (over the live stack):

- **Fighter L1 cannot Action Surge**: turn budget has no `action_surge` in the
  action list; attempting it returns a validation error.
- **Fighter L2 gains an extra Action**: Fighter L2 in combat. Base turn budget
  has 1 Action. Player attacks (budget.actions → 0), then uses Action Surge
  (bonus action spent, pool consumed), then attacks again (second attack
  resolves — a second `longsword slash` appears in the combat log).
- **Action Surge costs a bonus action**: After Action Surge, the same turn
  cannot use another bonus-action ability (e.g. Second Wind) until next turn.
- **Short rest resets Action Surge**: Use Action Surge, end combat, take short
  rest. `action_surge` pool back to 1 use.
- **No stack**: Using Action Surge twice on one turn fails the second time
  (pool empty).

## Implementation

1. `core/action.py`: add `ActionType.ACTION_SURGE`.
2. `core/action_defs.py`: register `ACTION_SURGE` —
   - `cost_type=BONUS_ACTION`, `combat_only=True`, `target_mode=SELF`,
     `target_scope=NONE`, `provider_managed=True`.
3. `rules/handlers/` — add `action_surge.py` handler:
   - Validate pool exists and has uses via `has_resource`.
   - Consume 1 use (`use_resource`).
   - Grant +1 to `creature.turn_budget.actions`.
   - Emit a log event (see Second Wind handler for the shape).
4. Register the handler in the dispatcher wiring (mirror Second Wind / Lay on
   Hands registration points).
5. Extend `ClassFeatureActionProvider` (rules/action_provider.py): if creature
   is Fighter and `has_resource("action_surge")`, probe-validate and append.
   Note: the L2 gate is implicit — the pool only exists at L2+.

## Acceptance Criteria

- [ ] Tests RED first
- [ ] Implementation GREEN
- [ ] `make check` passes
- [ ] Fighter L2 can perform two Actions in a single turn via Action Surge
- [ ] Action Surge consumes a bonus action and the `action_surge` pool use
- [ ] Short rest refills `action_surge`
- [ ] Fighter L1 never sees the action in their available actions

## Status

`pending`
