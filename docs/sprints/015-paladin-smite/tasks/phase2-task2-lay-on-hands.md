# Task: Lay on Hands Action

**Date:** 2026-04-11
**Sprint:** 015-paladin-smite
**Phase:** 2 — Paladin Class Foundation

## Description

Lay on Hands as a full action: spend N HP from the lay_on_hands pool to heal self or a touched ally. ActionType, ActionDef, handler, and action provider integration.

D&D 5e mechanics:
- Costs 1 action
- Touch range (self or adjacent creature in combat, any ally out of combat)
- Player chooses how many HP to spend (1 to pool remaining)
- No dice — flat healing equal to points spent
- Pool resets on long rest (already handled by Task 1)

Key changes:
- `ActionType.LAY_ON_HANDS` in `core/action.py`
- `ActionDef` registration in `core/action_defs.py` (cost_type=ACTION, targeted=True, provider_managed=True)
- `handle_lay_on_hands()` in `rules/handlers/items.py` — validates pool, spends amount, heals target
- Action provider: offer LAY_ON_HANDS when Paladin has lay_on_hands pool with current_uses > 0
- LLM tool schema: params include target_id (optional, default self) and amount (required int)

## Tests First

Scenarios (unit tests, mock emit_fn):

1. **Heal self** — Paladin with 20/25 HP and lay_on_hands pool at 15. Lay on Hands amount=5 on self → HP becomes 25/25, pool becomes 10. ActionResult success.
2. **Heal ally** — Paladin targets adjacent ally with 10/20 HP. Lay on Hands amount=8 → ally HP becomes 18/20, pool decrements by 8.
3. **Overheal clamps** — Target at 18/20 HP, amount=10 → heals only 2, but pool still decrements by full amount spent (D&D 5e: you choose how many to spend, excess is wasted). Actually, re-check: D&D 5e says "restore a number of hit points" — the excess is wasted. Pool decrements by the amount chosen, not the effective heal.
4. **Pool exhausted** — Pool at 0 → handler returns ActionResult(success=False) with error.
5. **Insufficient pool** — Pool at 3, amount=5 → handler returns error (can't spend more than remaining).
6. **Action provider** — Paladin with pool > 0 sees LAY_ON_HANDS in available actions. Pool at 0 → not offered.
7. **Non-Paladin** — Fighter trying LAY_ON_HANDS → handler returns error.
8. **Full chain: heal + rest recovery** — Spend entire pool, long rest, pool back to max, can heal again.

## Implementation

After tests are red:

1. Add `LAY_ON_HANDS = "lay_on_hands"` to ActionType enum
2. Register ActionDef: cost_type=ACTION, targeted=True, provider_managed=True, params schema (target_id: optional str, amount: int)
3. Write `handle_lay_on_hands()` in `rules/handlers/items.py`:
   - Validate actor is Paladin (isinstance Character, char_class == PALADIN)
   - Validate amount > 0 and amount <= pool.current_uses
   - `use_resource(actor, "lay_on_hands", amount=amount)`
   - Resolve target (self if no target_id, else find creature)
   - `target.heal(amount)`
   - Emit LAY_ON_HANDS event
4. Register handler in dispatcher
5. Add Paladin block to `ClassFeatureActionProvider` in action_provider.py
6. Add EventType.ENTITY_LAY_ON_HANDS if needed for perception/logging

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Paladin can heal self for variable HP amount
- [ ] Paladin can heal adjacent ally in combat
- [ ] Pool tracks spending correctly across multiple uses
- [ ] Action not offered when pool exhausted
- [ ] LLM schema exposes amount + target_id params

## Status

`pending`
