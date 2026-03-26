# Task: Decompose resolve_attack and query dispatcher

**Date:** 2026-03-26
**Sprint:** 005-tech-sweep
**Phase:** 3 — Growing Files Split

## Description

Two oversized methods need decomposition:

### combat_manager.resolve_attack (186 LOC, lines 247-430)

Extract logical phases into private methods within CombatManager:

- `_build_attack_modifiers()` — weapon selection, modifier pipeline, dice bonus rolling (lines 270-298)
- `_check_sneak_attack()` — sneak attack eligibility check + ally adjacency on battle map (lines 300-333)
- `_build_attack_event()` — structured event data construction from AttackResult (lines 370-416)

The main `resolve_attack()` becomes an orchestrator: lookup entities → build modifiers → check sneak attack → resolve → apply damage → log events. ~40-50 LOC instead of 186.

### query_handler.query (127 LOC, lines 33-157)

Replace the `if/if/if` chain with a dispatch dict mapping QueryType → handler method. Each query type already has self-contained logic — extract into `_query_players()`, `_query_entities_at_location()`, etc. The `query()` method becomes a 5-line lookup + call.

## Tests First

Write tests that exercise the full chains being decomposed:

1. **Sneak attack with ally adjacency** — rogue attacks target, ally is within 5ft on battle map, sneak attack dice are added. Verifies the full resolve_attack pipeline including the extracted sneak attack check.
2. **Attack with dice bonuses (Bless)** — blessed attacker rolls, bless d4 is added to attack roll components in the event data. Verifies modifier building + event construction.
3. **Attack → death → combat end chain** — attacker kills target, death event + combat end events fire in correct order. Verifies the orchestrator flow holds after decomposition.
4. **Query dispatch coverage** — ENTITIES_AT_LOCATION, ALL_CREATURES with filters, COMBAT_INFO all return correct data. Verifies the dispatch dict pattern works identically to the if-chain.

## Implementation

1. Write tests (RED)
2. Extract combat_manager helper methods, keeping resolve_attack as orchestrator
3. Extract query handler methods, replace if-chain with dispatch dict
4. Verify tests GREEN + `make check`

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] resolve_attack is ≤60 LOC, with helpers as private methods
- [ ] query() uses dispatch dict, ≤10 LOC
- [ ] All existing tests pass (`make check`)
- [ ] No behavioral changes — same events, same query results

## Status

`done`

## Developer Notes

**resolve_attack:** 186 LOC → ~74 LOC orchestrator + 5 private helpers (_roll_attack_dice, _check_sneak_attack,
_build_attack_event, _build_damage_components, _handle_death). Slightly over the 60 LOC target because the
orchestrator retains logging and the resolve_attack call itself — further decomposition would obscure the flow.

**query():** 127 LOC if-chain → 6 LOC dispatch + 13 handler methods + ClassVar dispatch dict. Added `str()` casts
on params values to satisfy mypy strict mode (params type is `dict[str, object]`).

8 new tests verify the full attack pipeline (sneak attack with ally adjacency, bless dice in event data,
death→combat end ordering) and query dispatch (location filter, type filter, combat info, unknown query).
Added `Callable` import and `_QueryHandler` type alias for the dispatch dict.
