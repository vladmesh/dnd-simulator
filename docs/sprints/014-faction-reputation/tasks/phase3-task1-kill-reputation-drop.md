# Task: Kill Reputation Drop

**Date:** 2026-04-10
**Sprint:** 014-faction-reputation
**Phase:** 3 — Reputation Dynamics + Auto-hostility

## Description

When a creature kills another creature, the killer's reputation with the victim's faction drops. The drop is scaled by the victim's standing with their own faction: killing an outcast (~0 rep with own faction) costs almost nothing; killing a respected member (100 rep) costs the full base delta.

Formula: `delta = base_delta * (victim_rep_with_own_faction / 100)`

Where `victim_rep_with_own_faction` defaults to 100 if the victim has no personal override (most creatures — they're in good standing with their own faction by default).

Add `EventType.REPUTATION_CHANGED` and emit it from `_handle_death` so downstream systems (perception, frontend) can react.

## Tests First

Scenarios in `tests/unit/test_reputation.py` (extend existing file):

1. **Normal kill drops reputation.** Creature A (kingdom) kills creature B (bandits, no personal rep override → default 100). A's reputation with "bandits" drops by `base_delta`.
2. **Outcast kill costs nothing.** Creature A kills creature B whose reputation with own faction is 0. Delta = `base_delta * 0/100` = 0. A's reputation unchanged.
3. **Partial standing scales linearly.** Victim has rep 50 with own faction. Delta = `base_delta * 50/100` = half.
4. **Killing factionless creature has no effect.** Victim has no `faction_id` → no reputation change.
5. **Repeated kills accumulate.** Kill two bandits in sequence → reputation drops twice, stacking.
6. **Reputation floors at 0.** Even if delta would push below 0, clamp to 0.

Test the pure function directly. Separately, test that `_handle_death` calls it and emits the event (unit test with combat_manager).

## Implementation

1. Add `REPUTATION_CHANGED = "reputation_changed"` to `EventType` in `core/models.py`.
2. Add pure function `compute_kill_reputation_delta(base_delta: int, victim: Creature) -> int` to `rules/reputation.py`. Returns the actual delta (0 if victim has no faction). Uses `victim.reputation.get(victim.faction_id, 100)` for victim's standing with own faction.
3. Add `apply_reputation_drop(killer: Creature, victim: Creature, base_delta: int) -> int` to `rules/reputation.py`. Calls `compute_kill_reputation_delta`, mutates `killer.reputation[victim.faction_id]`, returns actual delta applied. Clamps to 0.
4. Wire into `CombatManager._handle_death`: after marking target dead, call `apply_reputation_drop`, emit `REPUTATION_CHANGED` event with data `{entity_id, faction_id, old_rep, new_rep, delta, reason: "kill"}`.
5. `_handle_death` needs to know the attacker — thread `attacker_id` through from `resolve_attack`.
6. Define `BASE_KILL_REPUTATION_DELTA = 20` as a constant in `rules/reputation.py` (tunable later).

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] Killing a normal creature drops reputation by BASE_KILL_REPUTATION_DELTA
- [ ] Killing an outcast (0 rep with own faction) drops reputation by ~0
- [ ] REPUTATION_CHANGED event emitted with correct data
- [ ] Reputation never goes below 0

## Status

`done`

## Developer Notes

Implemented as planned. Pure functions `compute_kill_reputation_delta` and `apply_reputation_drop` in `rules/reputation.py`. Default own-faction rep is 100, so most creatures take full penalty. `_handle_death` now receives the attacker to compute and emit `REPUTATION_CHANGED` events. 11 new tests cover the pure functions (delta scaling, outcast, floor at 0, own-faction kill). All 1867 existing tests pass unchanged.
