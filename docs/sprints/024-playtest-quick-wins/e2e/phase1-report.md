# E2E Report: sprint024-phase1

**Date:** 2026-07-16
**Flags:** --no-llm
**Sections tested:** combat (playbook §3) + phase-relevant §10.4/10.5/10.6, §11.1/11.4; auto-discovered from phase 1 changes
**Stack:** LOG_LEVEL=DEBUG, LOG_DIR=/tmp/dnd-e2e-logs, world Sword Vale

## Summary

- Scenarios: 9 tested, 9 passed, 0 failed
- Quick fixes: 0
- Blockers: 0

Phase 1 unified combat movement-budget accounting (task 1), gated other-creature errors + faction spam out of the player log (task 2), and reworded Second Wind at full HP (task 3). All three verified — task 1 and task 2 through the live UI, task 3 through integration + unit tests (its full-HP path needs an HP reset that the combat run didn't hit).

## Results

### Section 3: Combat

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 3.1 | Initiate combat | pass | Attack marta → `Combat started! Initiative order: Marta, Adventurer`, sidebar swaps to Combat panel, round number shown |
| 3.2 | Attack and damage | pass | `You attack Brute (longsword slash) [d20(5)+4=9 vs AC 10], miss` and later a clean crit line — full roll + AC + damage-type breakdown, no placeholder leaks |
| 3.3 | End turn and NPC response | pass | Brute took its turn: `Brute moved (10 ft)` then `Brute attacks you (fists) [d20(20)+0=20 vs AC 19], CRIT! 2 damage (1 bludgeoning + 1 weapon_crit)`; new turn arrived, budget reset to full |
| 3.4 | Combat ends | pass | Verified in the marta one-shot: `human dies` → `Combat ended.` → sidebar returns to peaceful/loot |

### Phase-relevant dashboard/reaction scenarios

| # | Scenario | Status | Notes |
|---|----------|--------|-------|
| 10.5 | Combat layout switch | pass | Right column swaps to interactive Battle Map on combat start, back to Location after |
| 10.6 | Action bar budget display | pass | `Actions / Bonus / Movement / Reaction` row with live numbers; resets to `Movement: 30ft` at each turn start |
| 10.4 | Click-to-move + movement budget | pass | **task 1**: 15ft move (`You move to the west (15 ft)`) dropped budget exactly `Movement: 30ft → 15ft`; reachable-cell highlight shrank to the new 15ft radius |
| 11.1 / 11.4 | OA on leaving reach | pass | Leaving the adjacent Brute's reach drew an OA: `Brute attacks you (fists) (opportunity attack) [d20(12)+0=12 vs AC 19], miss` + `Brute seizes the opening against you!` |

### Auto-discovered scenarios (phase 1 changes)

| Scenario | Reason | Status | Notes |
|----------|--------|--------|-------|
| Movement budget accounting in combat | task 1 unified `MOVE`→FREE, `handle_move` charges actual `moved_ft` | pass | 3-cell straight move = 15ft charged exactly; budget resets per turn; reachable set recomputes from remaining movement |
| Player log cleanliness across NPC turns | task 2 gated other-creature errors + faction spam | pass | Two full rounds (my turn, OA, Brute move + attack + crit) — no leaked technical errors, no faction-spam lines in the player log |
| `faction_hostility_check` log level | task 2 moved it INFO→DEBUG | pass | 5 occurrences in backend log, all `"level": "debug"` |
| Second Wind at full HP wording | task 3 `healed == 0` message | n/a (test-covered) | Not repro'd in the E2E combat (player was damaged, so heal was non-zero). Covered by new integration test `test_fighter_second_wind_at_full_hp_reports_full_health` + unit tests |

## Quick Fixes

None.

## Findings

### Blockers
None.

### Minor
- NPC race renders in Russian (`человек`) while the UI chrome is English — the session was created without an explicit lang and the server default is RU. Pre-existing, out-of-scope `ui-language-mixing` (backlog), not a phase-1 regression.
- Perceived NPC identity shows race (`You attack human`) for an unfamiliar NPC (marta) but the given name for the spawned monster (`You attack Brute`). Existing `perceive()` behavior, unrelated to this phase.

## Log Analysis

- No errors, exceptions, or tracebacks in `/tmp/dnd-e2e-backend.log`.
- `faction_hostility_check` present only at DEBUG (task 2 gating confirmed).
- No `action_failed` events fired this run (the Brute was never blocked), so task 2's specific "blocked NPC action stays backend-only" path wasn't exercised live; it is unit-tested and the player log stayed clean throughout.
