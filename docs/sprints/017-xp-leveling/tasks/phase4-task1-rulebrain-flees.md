# Task: RuleBrain — hostile NPC dashes away instead of fighting

**Date:** 2026-04-13
**Sprint:** 017-xp-leveling
**Phase:** 4 — E2E follow-up bug sweep

## Symptom

In the phase 3 E2E (world `level_up_test`), `xp_dummy` (faction `monsters`, AI `rule_based`, low WIS 8) consistently consumes its first turn dashing 30 ft + bonus-action Dash for another 30 ft, ending up far from the player even though it started adjacent and the player was the only valid hostile target.

Log evidence (from `docs/e2e-reports/017-phase3-level-up-2026-04-13.md`):
```
XP Dummy moved (30 ft)
человек ускоряется (+30 ft движения)
XP Dummy moved (10 ft)
```

The arena is supposed to be deterministic — one kill = L2. The dummy's flee response broke that determinism: the test only passed because the dummy had nowhere useful to go and ended back within reach.

## Investigation scope

This is **not** a fix-the-symptom task. Before any code change, write up a root-cause analysis in this file (Developer Notes section) covering:

1. **Where in `RuleBrain` (`src/dnd_simulator/rules/rule_brain.py`) does the action selection produce Dash?** Trace the decision path. Is there a "low HP → flee" branch? A "no weapon → kite" branch? A target-scoring heuristic that punishes adjacency?
2. **What inputs caused this branch to fire for `xp_dummy`?** Stats: HP 3, AC 8, STR 8, WIS 8, equipped weapon = none (relies on `attacks: [{name: flail, ...}]`). Was it the missing weapon? The HP ratio? The faction? Reproduce in a unit test that loads the dummy and asks for its first action.
3. **What's the intended behavior for hostile-faction creatures placed for combat?** The current heuristic might be correct for, say, a wounded bandit who should retreat — but wrong for a "minion" placed specifically to be killed. Is the current behavior a feature or a bug for the general case?

Only after the RCA is in writing, propose 2–3 alternative fixes and pick one with rationale. Do not reach for the first thing that makes the dummy stand still.

## Possible directions (do not pre-commit to one)

- **Per-creature `combat_stance` field** (enum: AGGRESSIVE / DEFENSIVE / SKIRMISH / FLEE) on `Creature`, read by `RuleBrain`. Lets content-authors decide. Aligns with project's "data-driven" principle.
- **`role`-based default policy** in RuleBrain (roles like `commoner` flee at low HP, `warrior` fights). Implicit, less data, more magic.
- **Drop the flee heuristic entirely if the creature has no escape route** (graph reachability check). Fixes the symptom without new schema.
- **Don't dash if the only hostile is in reach AND the creature has a melee attack** — the most surgical fix; argues that dashing past your own attack range is never correct for a creature that can hit something this turn.

The chosen fix must:
- Have a clear **why-this-not-other** justification in Developer Notes.
- Include at least one unit test asserting the new behavior on `xp_dummy`-shaped creatures, and at least one **regression** test asserting that creatures who *should* retreat still do (e.g. low-HP bandit with friendly squad nearby, or a fleeing role).

## Tests First

Add to `tests/unit/test_rule_brain.py` (create if missing):

1. `test_rule_brain_low_wis_no_weapon_attacks_adjacent_hostile` — given a creature shaped like `xp_dummy` with a hostile player adjacent, the chosen action is `attack`, not `dash` / `move_to`.
2. `test_rule_brain_in_reach_with_melee_attack_does_not_dash` — explicit assertion of the surgical invariant.
3. `test_rule_brain_existing_flee_path_still_works` — pick whichever existing scenario in the codebase actually wants to retreat (find via `git grep` on `dash` usage in tests / fixtures) and assert it still does after the fix.

Tests must be **red** before implementation.

## Implementation

Whatever the chosen direction, follow project rules:
- No magic strings — use enums where applicable.
- `RuleBrain` lives in `rules/`, must stay pure (no I/O, no state).
- If a new `Creature` field is added — frozen dataclass field with sensible default; YAML schema (`schemas.py`) updated; `_to_npc` / monster spawn pipeline propagates it.
- Don't widen `RuleBrain` into a god class — extract decision helpers if the file grows.

## Acceptance Criteria

- [ ] Developer Notes contain a written RCA before any code changes
- [ ] `xp_dummy` (unmodified content) attacks adjacent hostile player on its first turn in the E2E
- [ ] At least one creature in the existing content base that should retreat still does so (regression)
- [ ] All existing rule-brain unit tests still pass
- [ ] `make check` green

## Status

`pending`
