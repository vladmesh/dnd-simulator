# Task: Sneak Attack Faction-Aware Ally Detection

**Date:** 2026-03-28
**Sprint:** 011-class-mechanics-l1
**Phase:** 3 — Cunning Action Choice & SA Faction Check

## Description

`CombatManager._check_sneak_attack` currently treats ANY alive creature within 5ft of the target as an "ally" for Sneak Attack eligibility. Per D&D 5e, only an **enemy of the target** (= ally of the attacker, i.e. same faction or FRIENDLY relation) qualifies.

Fix: use the PoliticsLayer `FACTION_RELATION` query to check whether each adjacent creature is friendly to the attacker. `handle_event` already receives `query_fn` — thread a faction-check callable through `resolve_attack` → `_check_sneak_attack`.

## Tests First

1. **SA granted when ally adjacent** — Rogue attacks goblin. A fighter (same faction as rogue, FRIENDLY) stands within 5ft of goblin. SA is eligible (no advantage needed).
2. **SA denied when only enemies adjacent** — Rogue attacks goblin. Another goblin (HOSTILE to rogue) stands within 5ft of target. SA is NOT eligible (no advantage, no friendly adjacent).
3. **SA denied when only neutral creatures adjacent** — Rogue attacks. A bystander (NEUTRAL faction) is within 5ft. SA is NOT eligible.
4. **SA still works via advantage regardless of adjacency** — Rogue has advantage. No allies adjacent. SA is eligible (advantage path unchanged).
5. **SA with no creatures adjacent at all** — Only attacker and target on map. No advantage. SA is NOT eligible.

## Implementation

1. Add `is_ally_fn` parameter (callable `(str, str) → bool`) to `_check_sneak_attack`. The callable takes two faction_ids and returns True if FRIENDLY.
2. In the adjacency loop (line 374-380), after checking `is_alive` and distance, also check `is_ally_fn(attacker.faction_id, adjacent.faction_id)`.
3. In `resolve_attack`, build the `is_ally_fn` closure from a `query_fn` parameter. Query `FACTION_RELATION` and check for `"friendly"`.
4. In `EntitiesLayer.handle_event`, pass `query_fn` through to `resolve_attack`.

## Acceptance Criteria

- [ ] Tests written and RED (before implementation)
- [ ] Implementation makes tests GREEN
- [ ] Existing tests still pass (`make check`)
- [ ] SA only counts FRIENDLY-faction creatures as allies for adjacency check
- [ ] Advantage-based SA path is unchanged (no faction check needed)

## Status

`pending`
